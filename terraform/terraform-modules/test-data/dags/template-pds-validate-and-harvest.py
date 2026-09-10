# PDS Validate and Harvest DAG (Airflow 3 compatible, TEMPLATE)
# Same as pds-basic-registry-load-use-case but without the Data_Archive task.

import asyncio
import boto3
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException, AirflowFailException
from airflow.models import BaseOperator
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.triggers.base import BaseTrigger, TriggerEvent
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta

# -------------------------------------------------------------------
# Retry-aware ECS operator for Validate
# -------------------------------------------------------------------
# The `validate` tool exits 1 when it ran successfully but found real
# data problems (e.g. missing referenced file) — a deterministic result
# that retrying will not change. Any other non-zero exit (task crashed,
# never started, OOM, etc.) is a genuine infra failure worth retrying.
# We distinguish the two so only infra failures consume the task's retries.
class EcsRunTaskOperatorWithArnXCom(EcsRunTaskOperator):
    """Pushes the started ECS task's ARN to XCom (key='ecs_task_arn') so a
    downstream deferrable log-fetch task can locate the exact CloudWatch log
    stream, on both the success path and the (deferred) failure path."""
    def execute(self, context):
        try:
            return super().execute(context)
        finally:
            self._push_arn(context)

    def execute_complete(self, context, event=None):
        try:
            return super().execute_complete(context, event)
        finally:
            self._push_arn(context)

    def _push_arn(self, context):
        if self.arn:
            context["ti"].xcom_push(key="ecs_task_arn", value=self.arn)


class ValidateEcsRunTaskOperator(EcsRunTaskOperatorWithArnXCom):
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
# Deferrable CloudWatch log fetcher — used after Validate/Harvest to pull
# and print the full log stream contents (regardless of task outcome),
# without holding a worker slot while polling CloudWatch.
# -------------------------------------------------------------------
class CloudWatchLogsFetchTrigger(BaseTrigger):
    def __init__(self, log_group, log_stream, region):
        super().__init__()
        self.log_group = log_group
        self.log_stream = log_stream
        self.region = region

    def serialize(self):
        return (
            f"{__name__}.CloudWatchLogsFetchTrigger",
            {
                "log_group": self.log_group,
                "log_stream": self.log_stream,
                "region": self.region,
            },
        )

    async def run(self):
        messages, error = await asyncio.to_thread(self._fetch_all_log_events)
        yield TriggerEvent({"messages": messages, "error": error})

    def _fetch_all_log_events(self):
        client = boto3.client("logs", region_name=self.region)
        messages = []
        next_token = None
        try:
            while True:
                kwargs = {
                    "logGroupName": self.log_group,
                    "logStreamName": self.log_stream,
                    "startFromHead": True,
                }
                if next_token:
                    kwargs["nextToken"] = next_token
                resp = client.get_log_events(**kwargs)
                events = resp.get("events", [])
                messages.extend(e["message"] for e in events)
                new_token = resp.get("nextForwardToken")
                if not events or new_token == next_token:
                    break
                next_token = new_token
            return messages, None
        except client.exceptions.ResourceNotFoundException:
            return messages, f"Log stream '{self.log_stream}' not found in '{self.log_group}' (task may not have started)."


class ShowEcsCloudWatchLogsOperator(BaseOperator):
    template_fields = ("ecs_task_arn", "log_group", "stream_prefix", "container_name")

    def __init__(self, *, ecs_task_arn, log_group, stream_prefix, container_name, region, **kwargs):
        super().__init__(**kwargs)
        self.ecs_task_arn = ecs_task_arn
        self.log_group = log_group
        self.stream_prefix = stream_prefix
        self.container_name = container_name
        self.region = region

    def execute(self, context):
        if not self.ecs_task_arn:
            print("No ECS task ARN available (upstream task may not have started) — skipping log fetch.")
            return []
        ecs_task_id = self.ecs_task_arn.rsplit("/", 1)[-1]
        log_stream = f"{self.stream_prefix}/{self.container_name}/{ecs_task_id}"
        self.defer(
            trigger=CloudWatchLogsFetchTrigger(
                log_group=self.log_group,
                log_stream=log_stream,
                region=self.region,
            ),
            method_name="execute_complete",
        )

    def execute_complete(self, context, event=None):
        event = event or {}
        messages = event.get("messages", [])
        error = event.get("error")
        print(f"--- Full CloudWatch log stream ({len(messages)} lines) ---")
        for line in messages:
            print(line)
        if error:
            raise AirflowException(error)
        return messages


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

show_validate_logs = ShowEcsCloudWatchLogsOperator(
    task_id="Show_Validate_Logs",
    ecs_task_arn="{{ ti.xcom_pull(task_ids='Validate_Products', key='ecs_task_arn') }}",
    log_group="/pds/ecs/validate-${pds_node_name}",
    stream_prefix="ecs/pds-validate",
    container_name="pds-validate",
    region=AWS_REGION,
    trigger_rule=TriggerRule.ALL_DONE,
    dag=dag,
)

# -------------------------------------------------------------------
# HARVEST
# -------------------------------------------------------------------
harvest = EcsRunTaskOperatorWithArnXCom(
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
    trigger_rule=TriggerRule.ALL_DONE,
    deferrable=True,
    waiter_delay=1,
    dag=dag,
)

show_harvest_logs = ShowEcsCloudWatchLogsOperator(
    task_id="Show_Harvest_Logs",
    ecs_task_arn="{{ ti.xcom_pull(task_ids='Harvest_Data', key='ecs_task_arn') }}",
    log_group="/pds/ecs/harvest-${pds_node_name}",
    stream_prefix="ecs/pds-registry-loader-harvest",
    container_name="pds-registry-loader-harvest",
    region=AWS_REGION,
    trigger_rule=TriggerRule.ALL_DONE,
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
# WORKFLOW
# -------------------------------------------------------------------
(
    print_start_time
    >> list_products
    >> config_init
    >> config_s3_to_efs_copy
    >> validate
    >> show_validate_logs
    >> harvest
    >> show_harvest_logs
    >> config_s3_to_efs_copy_cleanup
    >> config_init_cleanup
    >> print_end_time
)
