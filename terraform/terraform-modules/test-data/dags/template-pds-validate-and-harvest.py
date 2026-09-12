# PDS Validate and Harvest DAG (Airflow 3 compatible, TEMPLATE)
# Same as pds-basic-registry-load-use-case but without the Data_Archive task.

import boto3
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowFailException
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.hooks.logs import AwsLogsHook
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.utils.state import State
from airflow.api.common.trigger_dag import trigger_dag
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
    """Base class: on deferred resume, pull max available CloudWatch logs."""
    def execute_complete(self, context: Any, event: dict[str, Any] | None = None) -> str | None:
        """Resume from deferral and pull max available log lines from CloudWatch."""
        try:
            result = super().execute_complete(context, event)
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
    def execute_complete(self, context: Any, event: dict[str, Any] | None = None) -> str | None:
        """Resume from deferral, fetch logs, and check for failed files."""
        try:
            result = super().execute_complete(context, event)
        except Exception:
            raise
        
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
    deferrable=True,
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
    deferrable=True,
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
    deferrable=True,
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
    deferrable=True,
    waiter_delay=1,
    # execute_complete() pulls max available CloudWatch logs
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
    deferrable=True,
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
    deferrable=True,
    waiter_delay=1,
    dag=dag,
)

# -------------------------------------------------------------------
# DAG RESTART ON FAILURE
# -------------------------------------------------------------------
@task(task_id="Restart_DAG_On_Failure", trigger_rule=TriggerRule.ALL_DONE, dag=dag)
def restart_dag_on_failure(**context):
    """Check if any task failed; if so, trigger a new DAG run for retry."""
    dag_run = context["dag_run"]
    
    # Clean, native way to get failed tasks for this specific run
    failed_tasks = dag_run.get_task_instances(state=State.FAILED)
    
    if not failed_tasks:
        print("No failed tasks. DAG completed successfully.")
        return

    # If we are here, something failed. Check retry limits.
    retry_count = dag_run.conf.get("retry_count", 0)
    if retry_count >= 3:
        raise AirflowFailException(f"Max DAG retries (3) exceeded. Failed tasks: {[t.task_id for t in failed_tasks]}")
    
    new_retry = retry_count + 1
    print(f"DAG has failed tasks. Triggering retry attempt {new_retry}/3...")
    
    # Trigger the new DAG natively (No AWS CLI required)
    trigger_dag(
        dag_id=context["dag"].dag_id,
        run_id=f"retry_{new_retry}_{dag_run.run_id}",
        conf={
            "s3_config_dir": dag_run.conf["s3_config_dir"],
            "efs_config_dir": dag_run.conf["efs_config_dir"],
            "retry_count": new_retry
        },
        replace_microseconds=False
    )

    # Fail the current DAG run so the UI accurately shows it didn't succeed
    raise AirflowFailException("Failing current DAG run because upstream tasks failed. A retry DAG run has been triggered.")

restart_dag = restart_dag_on_failure()

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
    >> print_end_time
    >> restart_dag
)
