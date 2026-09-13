# PDS Validate and Harvest DAG (Airflow 3 compatible, TEMPLATE)
# Same as pds-basic-registry-load-use-case but without the Data_Archive task.

import boto3
import json
import re
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowFailException
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.hooks.logs import AwsLogsHook
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta
from typing import Any

# -------------------------------------------------------------------
# Retry-aware ECS operator for Validate
# -------------------------------------------------------------------
# The `validate` tool exits 1 when it ran successfully but found real
# data problems (e.g. missing referenced file) — a deterministic result
# that retrying will not change. Any other non-zero exit (task crashed,
# never started, OOM, etc.) is a genuine infra failure worth retrying.
# We distinguish the two so only infra failures consume the task's retries.
class EcsRunTaskOperatorWithMaxLogs(EcsRunTaskOperator):
    """Base class: fetch max available CloudWatch logs after task execution."""
    def execute(self, context: Any) -> str | None:
        """Execute task synchronously and fetch CloudWatch logs."""
        try:
            result = super().execute(context)
        except Exception:
            # Task failed; try to fetch and log CloudWatch logs before re-raising
            self._fetch_and_log_cloudwatch_logs()
            raise
        
        # Task succeeded; also fetch logs for visibility
        self._fetch_and_log_cloudwatch_logs()
        return result

    def _fetch_and_log_cloudwatch_logs(self):
        """Fetch and log all available CloudWatch logs."""
        if not self.awslogs_group or not self.awslogs_stream_prefix:
            return
        try:
            logs_client = AwsLogsHook(
                aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region
            ).conn
            # Build log stream name from task ARN
            if self.arn:
                task_id = self.arn.rsplit("/", 1)[-1]
                log_stream = f"{self.awslogs_stream_prefix}/{self.arn.split('/')[-3]}/{task_id}"
                try:
                    logs_resp = logs_client.get_log_events(
                        logGroupName=self.awslogs_group,
                        logStreamName=log_stream,
                        startFromHead=True,
                    )
                    events = logs_resp.get("events", [])
                    if events:
                        self.log.info(f"--- CloudWatch logs ({len(events)} lines) ---")
                        for event in events:
                            self.log.info(event["message"])
                except logs_client.exceptions.ResourceNotFoundException:
                    self.log.warning(f"Log stream not found: {log_stream}")
        except Exception as e:
            self.log.warning(f"Could not fetch CloudWatch logs: {e}")


class ValidateEcsRunTaskOperator(EcsRunTaskOperatorWithMaxLogs):
    def execute(self, context):
        try:
            # This will run the parent execute(), which also fetches the logs
            return super().execute(context)
        except Exception as e:
            exit_code = None
            if self.arn:
                try:
                    resp = self.hook.get_conn().describe_tasks(
                        cluster=self.cluster, tasks=[self.arn]
                    )
                    exit_code = next(
                        (
                            c.get("exitCode")
                            for c in resp["tasks"][0].get("containers", [])
                            if c.get("name") == "pds-validate"
                        ),
                        None,
                    )
                except Exception:
                    pass  # if we can't determine exit code, fall back to retrying

            if exit_code == 1:
                raise AirflowFailException(
                    f"{e} (validate exited 1 — data validation failure, not retrying)"
                ) from e
            raise


class HarvestEcsRunTaskOperator(EcsRunTaskOperatorWithMaxLogs):
    """ECS operator for Harvest task that checks for failed files in summary.
    
    The harvest tool always exits 0 even when files fail to parse. This operator
    parses CloudWatch logs to detect the [SUMMARY] line with failed file count
    and fails the task if any files failed.
    """
    def execute(self, context: Any) -> str | None:
        """Execute task synchronously, fetch logs, and check for failed files."""
        # This will run the parent execute(), which also fetches the logs
        result = super().execute(context)
        
        # Task succeeded (exit 0), but check if harvest had failed files
        self._check_harvest_summary()
        return result

    def _check_harvest_summary(self):
        """Parse CloudWatch logs and fail if any files failed to harvest."""
        if not self.awslogs_group or not self.awslogs_stream_prefix:
            return
        try:
            logs_client = AwsLogsHook(
                aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region
            ).conn
            if self.arn:
                task_id = self.arn.rsplit("/", 1)[-1]
                log_stream = f"{self.awslogs_stream_prefix}/{self.arn.split('/')[-3]}/{task_id}"
                try:
                    logs_resp = logs_client.get_log_events(
                        logGroupName=self.awslogs_group,
                        logStreamName=log_stream,
                        startFromHead=True,
                    )
                    events = logs_resp.get("events", [])
                    for event in events:
                        msg = event["message"]
                        if "[SUMMARY]" in msg and "Failed files:" in msg:
                            # Extract failed file count
                            parts = msg.split("Failed files:")
                            if len(parts) > 1:
                                try:
                                    failed_count = int(parts[1].strip().split()[0])
                                    if failed_count > 0:
                                        raise AirflowFailException(
                                            f"Harvest completed with {failed_count} failed files (missing from EFS)"
                                        )
                                except (ValueError, IndexError):
                                    pass
                except logs_client.exceptions.ResourceNotFoundException:
                    self.log.warning(f"Log stream not found: {log_stream}")
        except AirflowFailException:
            raise
        except Exception as e:
            self.log.warning(f"Could not check harvest summary: {e}")

# -------------------------------------------------------------------
# ECS configuration (TEMPLATE — injected by Terraform)
# -------------------------------------------------------------------
ECS_CLUSTER_NAME    = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE     = "FARGATE"
ECS_SUBNETS         = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ${pds_nucleus_ecs_security_groups}
AWS_REGION          = "${aws_region}"

# -------------------------------------------------------------------
# Read the batch's product list (used below for the XCom-visible task)
# -------------------------------------------------------------------
def _read_product_list(s3_config_dir):
    bucket = s3_config_dir.replace("s3://", "").split("/")[0]
    key = "/".join(s3_config_dir.replace("s3://", "").split("/")[1:] + ["product_list.txt"])
    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    return [line for line in body.decode("utf-8").splitlines() if line]

# -------------------------------------------------------------------
# Extract product LIDVIDs from manifest file
# -------------------------------------------------------------------
def _extract_manifest_products(efs_config_dir):
    """Read manifest file and extract S3 URLs."""
    manifest_path = f"{efs_config_dir}/harvest_manifest.txt"
    try:
        with open(manifest_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading manifest: {e}")
        return []

# -------------------------------------------------------------------
# Parse CloudWatch logs to extract product LIDVIDs
# -------------------------------------------------------------------
def _parse_validate_logs(logs_client, log_group, log_stream):
    """Extract validated product LIDVIDs from validate logs."""
    validated_products = []
    try:
        logs_resp = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            startFromHead=True,
        )
        events = logs_resp.get("events", [])
        for event in events:
            msg = event["message"]
            if "Product_Observational" in msg or "Product_Bundle" in msg:
                match = re.search(r'urn:nasa:pds:[\w\-\.]+:[\w\-\.]+:[\w\-\.]+:[\w\-\.]+', msg)
                if match:
                    validated_products.append(match.group(0))
    except Exception as e:
        print(f"Error parsing validate logs: {e}")
    return validated_products

def _parse_harvest_logs(logs_client, log_group, log_stream):
    """Extract harvested product LIDVIDs from harvest logs."""
    harvested_products = []
    try:
        logs_resp = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            startFromHead=True,
        )
        events = logs_resp.get("events", [])
        for event in events:
            msg = event["message"]
            if "Processing" in msg and ".xml" in msg:
                match = re.search(r's3://[\w\-\.]+/[\w\-\./]+\.xml', msg)
                if match:
                    harvested_products.append(match.group(0))
    except Exception as e:
        print(f"Error parsing harvest logs: {e}")
    return harvested_products

# -------------------------------------------------------------------
# DAG definition
# -------------------------------------------------------------------
dag = DAG(
    dag_id="${pds_validate_and_harvest_dag_id}",
    schedule=None,
    catchup=False,
    start_date=datetime(2024, 1, 1),
    default_args={
        "retries": 5,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=15),
    },
    params={
        # Extra CLI switches for the `harvest` command (e.g. "-O -f").
        # Shows up as an editable field in the Airflow UI's "Trigger DAG w/ config" form.
        # Some supported harvest flags (see harvest -h):
        #   -O, --overwrite       Overwrite registered products
        #   -f, --force           Force load products even when namespace schema or attribute
        #                         type cannot be resolved. Affected fields will not be indexed.
        #   -a, --archive-status  Set the archive status for all products defaulting to staged
        "harvest_extra_args": "",
    },
)

# -------------------------------------------------------------------
# Utility tasks
# -------------------------------------------------------------------
print_start_time = BashOperator(
    task_id="Print_Start_Time",
    bash_command="date",
    dag=dag,
)

print_end_time = BashOperator(
    task_id="Print_End_Time",
    bash_command="date",
    trigger_rule=TriggerRule.ALL_DONE,
    dag=dag,
)

# -------------------------------------------------------------------
# List products being processed in this batch (visible in the
# task's XCom tab in the Airflow UI, instead of digging through logs).
# -------------------------------------------------------------------
@task(task_id="List_Products_In_Batch", dag=dag)
def list_products_in_batch(**context):
    products = _read_product_list(context["dag_run"].conf["s3_config_dir"])
    print(f"{len(products)} product(s) in this batch:")
    for p in products:
        print(p)
    return products

list_products = list_products_in_batch()

# -------------------------------------------------------------------
# CONFIG INIT
# -------------------------------------------------------------------
config_init = EcsRunTaskOperator(
    task_id="Config_Init",
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-config-init-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
        "awsvpcConfiguration": {
            "securityGroups": ECS_SECURITY_GROUPS,
            "subnets": ECS_SUBNETS,
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-config-init",
                "command": [
                    "{{ dag_run.conf['s3_config_dir'] }}",
                    "{{ dag_run.conf['efs_config_dir'] }}",
                    "COPY",
                ],
            }
        ]
    },
    awslogs_group="/pds/ecs/pds-nucleus-config-init-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=False,
    waiter_delay=1,
    dag=dag,
)

config_s3_to_efs_copy = EcsRunTaskOperator(
    task_id="Config_S3_to_EFS_Copy",
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
        "awsvpcConfiguration": {
            "securityGroups": ECS_SECURITY_GROUPS,
            "subnets": ECS_SUBNETS,
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-s3-to-efs-copy",
                "command": [
                    "{{ dag_run.conf['efs_config_dir'] }}",
                    "COPY",
                ],
            }
        ]
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=False,
    waiter_delay=1,
    dag=dag,
)

# -------------------------------------------------------------------
# VALIDATE
# -------------------------------------------------------------------
validate = ValidateEcsRunTaskOperator(
    task_id="Validate_Products",
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-validate-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
        "awsvpcConfiguration": {
            "securityGroups": ECS_SECURITY_GROUPS,
            "subnets": ECS_SUBNETS,
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-validate",
                "command": [
                    "--target-manifest",
                    "{{ dag_run.conf['efs_config_dir'] }}/harvest_manifest.txt",
                ],
            }
        ]
    },
    awslogs_group="/pds/ecs/validate-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-validate",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=False,
    waiter_delay=1,
    # No explicit retries override: ValidateEcsRunTaskOperator already
    # distinguishes real data-validation failures (no retry, fails fast)
    # from genuine infra failures (retried per the DAG-level default).
    dag=dag,
)

# -------------------------------------------------------------------
# HARVEST
# -------------------------------------------------------------------
harvest = HarvestEcsRunTaskOperator(
    task_id="Harvest_Data",
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-registry-loader-harvest-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
        "awsvpcConfiguration": {
            "securityGroups": ECS_SECURITY_GROUPS,
            "subnets": ECS_SUBNETS,
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-registry-loader-harvest",
                "environment": [
                    {
                        "name": "HARVEST_CFG",
                        "value": "{{ dag_run.conf['efs_config_dir'] }}/harvest.cfg",
                    },
                    {
                        # Extra CLI switches for the `harvest` command, editable via the DAG's
                        # "harvest_extra_args" param (Trigger DAG w/ config UI) or dag_run.conf.
                        "name": "HARVEST_EXTRA_ARGS",
                        "value": "{{ params.harvest_extra_args }}",
                    },
                ],
            }
        ]
    },
    awslogs_group="/pds/ecs/harvest-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-registry-loader-harvest",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=False,
    waiter_delay=1,
    # execute() pulls max available CloudWatch logs
    # and checks the [SUMMARY] line for failed files. If any files failed,
    # the task fails (since files missing from EFS indicate upstream copy failure).
    dag=dag,
)

# -------------------------------------------------------------------
# CLEANUP
# -------------------------------------------------------------------
config_s3_to_efs_copy_cleanup = EcsRunTaskOperator(
    task_id="Config_S3_to_EFS_Copy_Cleanup",
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
        "awsvpcConfiguration": {
            "securityGroups": ECS_SECURITY_GROUPS,
            "subnets": ECS_SUBNETS,
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-s3-to-efs-copy",
                "command": [
                    "{{ dag_run.conf['efs_config_dir'] }}",
                    "DELETE",
                ],
            }
        ]
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
    deferrable=False,
    waiter_delay=1,
    dag=dag,
)

config_init_cleanup = EcsRunTaskOperator(
    task_id="Config_Init_Cleanup",
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-config-init-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
        "awsvpcConfiguration": {
            "securityGroups": ECS_SECURITY_GROUPS,
            "subnets": ECS_SUBNETS,
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-config-init",
                "command": [
                    "{{ dag_run.conf['s3_config_dir'] }}",
                    "{{ dag_run.conf['efs_config_dir'] }}",
                    "DELETE",
                ],
            }
        ]
    },
    awslogs_group="/pds/ecs/pds-nucleus-config-init-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
    deferrable=False,
    waiter_delay=1,
    dag=dag,
)

# -------------------------------------------------------------------
# SUMMARY REPORT
# -------------------------------------------------------------------
@task(task_id="Generate_Summary_Report", trigger_rule=TriggerRule.ALL_DONE, dag=dag)
def generate_summary_report(**context):
    """Generate comprehensive summary report with product tracking."""
    dag_run = context["dag_run"]
    ti = context["task_instance"]
    
    batch_id = dag_run.run_id
    efs_config_dir = dag_run.conf.get("efs_config_dir", "")
    s3_config_dir = dag_run.conf.get("s3_config_dir", "")
    
    # Extract manifest products
    manifest_products = _extract_manifest_products(efs_config_dir)
    
    # Parse validate and harvest logs
    logs_hook = AwsLogsHook(aws_conn_id="aws_default", region_name=AWS_REGION)
    logs_client = logs_hook.conn
    
    validate_log_group = "/pds/ecs/validate-${pds_node_name}"
    validate_log_stream_prefix = "ecs/pds-validate"
    
    harvest_log_group = "/pds/ecs/harvest-${pds_node_name}"
    harvest_log_stream_prefix = "ecs/pds-registry-loader-harvest"
    
    validated_products = []
    harvested_products = []
    
    # Try to find and parse validate logs
    try:
        log_streams_resp = logs_client.describe_log_streams(
            logGroupName=validate_log_group,
            logStreamNamePrefix=validate_log_stream_prefix,
            orderBy="LastEventTime",
            descending=True,
            limit=1
        )
        if log_streams_resp.get("logStreams"):
            latest_stream = log_streams_resp["logStreams"][0]["logStreamName"]
            validated_products = _parse_validate_logs(logs_client, validate_log_group, latest_stream)
    except Exception as e:
        print(f"Could not fetch validate logs: {e}")
    
    # Try to find and parse harvest logs
    try:
        log_streams_resp = logs_client.describe_log_streams(
            logGroupName=harvest_log_group,
            logStreamNamePrefix=harvest_log_stream_prefix,
            orderBy="LastEventTime",
            descending=True,
            limit=1
        )
        if log_streams_resp.get("logStreams"):
            latest_stream = log_streams_resp["logStreams"][0]["logStreamName"]
            harvested_products = _parse_harvest_logs(logs_client, harvest_log_group, latest_stream)
    except Exception as e:
        print(f"Could not fetch harvest logs: {e}")
    
    # Calculate data integrity
    manifest_set = set(manifest_products)
    validated_set = set(validated_products)
    harvested_set = set(harvested_products)
    
    missing_from_validation = list(manifest_set - validated_set)
    missing_from_harvest = list(validated_set - harvested_set)
    all_match = (len(manifest_set) == len(validated_set) == len(harvested_set) and 
                 manifest_set == validated_set == harvested_set)
    
    # Generate summary report
    summary = {
        "batch_id": batch_id,
        "batch_size": len(manifest_products),
        "timing": {
            "start_time": dag_run.start_date.isoformat() if dag_run.start_date else None,
            "end_time": datetime.utcnow().isoformat(),
        },
        "manifest": {
            "count": len(manifest_products),
            "s3_urls": manifest_products,
        },
        "validation": {
            "count": len(validated_products),
            "lidvids": validated_products,
        },
        "harvest": {
            "count": len(harvested_products),
            "s3_urls": harvested_products,
        },
        "data_integrity": {
            "manifest_count": len(manifest_products),
            "validated_count": len(validated_products),
            "harvested_count": len(harvested_products),
            "all_match": all_match,
            "missing_from_validation": missing_from_validation,
            "missing_from_harvest": missing_from_harvest,
            "status": "COMPLETE" if all_match else "INCOMPLETE",
        },
        "status": "SUCCESS" if all_match else "WARNING",
    }
    
    # Log the summary as a single CloudWatch event
    summary_json = json.dumps(summary, indent=2)
    print(f"PDS_BATCH_SUMMARY_JSON: {json.dumps(summary)}")
    print(f"\n=== BATCH SUMMARY REPORT ===")
    print(summary_json)
    print(f"=== END SUMMARY REPORT ===")
    
    return summary

summary_report = generate_summary_report()

# -------------------------------------------------------------------
# WORKFLOW
# -------------------------------------------------------------------
(
    print_start_time
    >> list_products
    >> config_init
    >> config_s3_to_efs_copy
    >> validate
    >> harvest
    >> config_s3_to_efs_copy_cleanup
    >> config_init_cleanup
    >> summary_report
    >> print_end_time
)
