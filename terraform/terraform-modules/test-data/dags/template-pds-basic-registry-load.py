# PDS Basic Registry Load Use Case DAG (Airflow 3 compatible, TEMPLATE)

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
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
    default_args={
        "retries": 5,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=15),
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
                    }
                ],
            }
        ]
    },
    trigger_rule=TriggerRule.ALL_DONE,
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
    waiter_delay=1,
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
