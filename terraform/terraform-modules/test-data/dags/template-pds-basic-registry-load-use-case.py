# PDS Basic Registry Load Use Case DAG (Airflow 3 compatible, TEMPLATE)

import boto3
import json
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

LAMBDA_FUNCTION_NAME = "pds_nucleus_product_processing_status_tracker"

# -------------------------------------------------------------------
# Status callbacks
# -------------------------------------------------------------------
def _invoke_status_lambda(context, status):
    boto3.client("lambda").invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps({
            "productsList": context["dag_run"].conf["list_of_product_labels_to_process"],
            "pdsNode": context["dag_run"].conf["pds_node_name"],
            "processingStatus": status,
            "batchNumber": context["dag_run"].conf["batch_number"],
        }),
    )

def validate_success(context):
    _invoke_status_lambda(context, "validate_successful")

def validate_failure(context):
    _invoke_status_lambda(context, "validate_failed")

def harvest_success(context):
    _invoke_status_lambda(context, "harvest_successful")

def harvest_failure(context):
    _invoke_status_lambda(context, "harvest_failed")

# -------------------------------------------------------------------
# DAG definition
# -------------------------------------------------------------------
dag = DAG(
    dag_id="${pds_nucleus_basic_registry_dag_id}",
    schedule=None,
    catchup=False,
    start_date=datetime(2024, 1, 1),
    default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=2),
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
                ],
            }
        ]
    },
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
                "environment": [
                    {
                        "name": "PRODUCT_LABELS",
                        "value": "{{ dag_run.conf['list_of_product_labels_to_process'] | tojson }}",
                    }
                ],
            }
        ]
    },
    on_success_callback=validate_success,
    on_failure_callback=validate_failure,
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
    on_success_callback=harvest_success,
    on_failure_callback=harvest_failure,
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
