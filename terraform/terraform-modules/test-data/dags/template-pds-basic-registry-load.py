# PDS Basic Registry Load Use Case DAG (Airflow 3 compatible, TEMPLATE)

from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowSkipException
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta

# -------------------------------------------------------------------
# ECS configuration (TEMPLATE — injected by Terraform)
# -------------------------------------------------------------------
ECS_CLUSTER_NAME = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE = "FARGATE"
ECS_SUBNETS = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ${pds_nucleus_ecs_security_groups}
AWS_REGION = "${aws_region}"

# -------------------------------------------------------------------
# DAG definition
# -------------------------------------------------------------------
dag = DAG(
    dag_id="${pds_nucleus_basic_registry_dag_id}",
    schedule=None,
    catchup=False,
    start_date=datetime(2024, 1, 1),
    tags=["pds", "nucleus", "${pds_node_name}"],
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

# Harvest_Data runs with trigger_rule=ALL_DONE (below), so it fires even when
# Validate_Products failed. If harvest itself then fails, an in-place task
# retry often can't fix it -- the EFS copy or the manifest it read may need
# to be regenerated too -- so the whole DAG restarts from Config_Init
# instead of just retrying Harvest_Data, up to this many times.
MAX_DAG_RESTARTS_ON_HARVEST_FAILURE = 3


@task(task_id="Prepare_Harvest_Restart", trigger_rule=TriggerRule.ONE_FAILED, dag=dag)
def _prepare_harvest_restart(**context):
    """
    Runs only when Harvest_Data fails (trigger_rule=ONE_FAILED). Computes the
    conf and run_id for restarting the whole DAG, or skips (via
    AirflowSkipException, which also skips the downstream
    TriggerDagRunOperator -- its default trigger_rule is ALL_SUCCESS) once
    MAX_DAG_RESTARTS_ON_HARVEST_FAILURE is reached, so this can't loop
    forever.

    This used to be a plain on_failure_callback that called trigger_dag()
    directly. That's an ORM/direct-DB call, and Airflow 3's task execution
    model runs callback and task code alike in an isolated worker process
    with no direct DB access -- it raises "Direct database access via the
    ORM is not allowed in Airflow 3.0" the moment it actually fires (found
    via the sibling template-pds-validate-and-harvest.py DAG hitting exactly
    this). TriggerDagRunOperator, unlike a raw trigger_dag() call, goes
    through the supported Task Execution API, so the restart is done as a
    real downstream task instead of a callback.

    dag_run.conf carries the restart counter forward across attempts so
    this can't loop forever.
    """
    dag_run = context["dag_run"]
    conf = dict(dag_run.conf or {})
    attempt = int(conf.get("dag_restart_attempt", 0))

    if attempt >= MAX_DAG_RESTARTS_ON_HARVEST_FAILURE:
        print(
            f"Harvest failed after {attempt} whole-DAG restart(s); "
            f"giving up (max {MAX_DAG_RESTARTS_ON_HARVEST_FAILURE})."
        )
        raise AirflowSkipException("Max harvest-restart attempts reached")

    conf["dag_restart_attempt"] = attempt + 1
    new_run_id = f"{dag_run.run_id}__restart{attempt + 1}"
    print(
        f"Harvest failed; restarting whole DAG as {new_run_id} "
        f"(attempt {attempt + 1} of {MAX_DAG_RESTARTS_ON_HARVEST_FAILURE})"
    )
    return {"conf": conf, "run_id": new_run_id}


_harvest_restart_prep = _prepare_harvest_restart()

restart_dag_on_harvest_failure = TriggerDagRunOperator(
    task_id="Restart_Whole_Dag_On_Harvest_Failure",
    trigger_dag_id="${pds_nucleus_basic_registry_dag_id}",
    trigger_run_id=_harvest_restart_prep["run_id"],
    conf=_harvest_restart_prep["conf"],
    wait_for_completion=False,
    dag=dag,
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
    deferrable=True,
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
    deferrable=True,
    dag=dag,
)

# -------------------------------------------------------------------
# VALIDATE
# -------------------------------------------------------------------
validate = EcsRunTaskOperator(
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
    dag=dag,
)

# -------------------------------------------------------------------
# HARVEST
# -------------------------------------------------------------------
harvest = EcsRunTaskOperator(
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
    # ALL_DONE: harvest runs even when Validate_Products failed -- a
    # validation failure on some products shouldn't block harvest from
    # loading the ones that did pass.
    trigger_rule=TriggerRule.ALL_DONE,
    # 0, not the DAG-level default of 5: an in-place retry of just this task
    # is not the recovery path here -- see _prepare_harvest_restart above,
    # which restarts the whole DAG (up to 3x) instead once this task's
    # single attempt fails.
    retries=0,
    dag=dag,
)

# -------------------------------------------------------------------
# ARCHIVE + CLEANUP
# -------------------------------------------------------------------
data_archive = EcsRunTaskOperator(
    task_id="Data_Archive",
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
                    "ARCHIVE",
                    "{{ dag_run.conf['pds_hot_archive_bucket_name'] }}",
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
    waiter_delay=10,
    trigger_rule=TriggerRule.ALL_DONE,
    dag=dag,
)

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
    deferrable=True,
    trigger_rule=TriggerRule.ALL_DONE,
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
    deferrable=True,
    trigger_rule=TriggerRule.ALL_DONE,
    dag=dag,
)

# -------------------------------------------------------------------
# WORKFLOW
# -------------------------------------------------------------------
(
        print_start_time
        >> config_init
        >> config_s3_to_efs_copy
        >> validate
        >> harvest
        >> data_archive
        >> config_s3_to_efs_copy_cleanup
        >> config_init_cleanup
        >> print_end_time
)

# Separate branch off Harvest_Data, alongside the ALL_DONE cleanup chain
# above: only runs when Harvest_Data itself fails (trigger_rule=ONE_FAILED
# on Prepare_Harvest_Restart), restarting the whole DAG rather than retrying
# just this task.
harvest >> _harvest_restart_prep >> restart_dag_on_harvest_failure
