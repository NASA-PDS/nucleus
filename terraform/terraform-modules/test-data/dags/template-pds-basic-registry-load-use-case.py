# PDS Basic Registry Load Use Case DAG
#
# This DAG is a very basic workflow with validate tool and harvest tool. This was just added as an example DAG for
# Nucleus baseline deployment.

import boto3
import json
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from datetime import timedelta

# ECS configurations
ECS_CLUSTER_NAME = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE = "FARGATE"
ECS_SUBNETS = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ["${pds_nucleus_ecs_security_groups}"]
LAMBDA_FUNCTION_NAME = "pds_nucleus_product_processing_status_tracker"


##################################################################################
# Success/Failure monitoring
##################################################################################

# Save product processing status validate_successful
def save_product_processing_status_validate_successful(context):
    client = boto3.client('lambda')

    response = client.invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType='Event',
        Payload=json.dumps({
            "productsList": context["dag_run"].conf["list_of_product_labels_to_process"],
            "pdsNode": context["dag_run"].conf["pds_node_name"],
            "processingStatus": "validate_successful",
            "batchNumber": context["dag_run"].conf["batch_number"],
        }),
    )

    print(response)

# Save product processing status validate_failed
def save_product_processing_status_validate_failed(context):
    client = boto3.client('lambda')

    response = client.invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType='Event',
        Payload=json.dumps({
            "productsList": context["dag_run"].conf["list_of_product_labels_to_process"],
            "pdsNode": context["dag_run"].conf["pds_node_name"],
            "processingStatus": "validate_failed",
            "batchNumber": context["dag_run"].conf["batch_number"],
        }),
    )

    print(response)

# Save product processing status harvest_successful
def save_product_processing_status_harvest_successful(context):
    client = boto3.client('lambda')

    response = client.invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType='Event',
        Payload=json.dumps({
            "productsList": context["dag_run"].conf["list_of_product_labels_to_process"],
            "pdsNode": context["dag_run"].conf["pds_node_name"],
            "processingStatus": "harvest_successful",
            "batchNumber": context["dag_run"].conf["batch_number"],
        }),
    )

    print(response)


# Save product processing status harvest_failed
def save_product_processing_status_harvest_failed(context):
    client = boto3.client('lambda')

    response = client.invoke(
        FunctionName=LAMBDA_FUNCTION_NAME,
        InvocationType='Event',
        Payload=json.dumps({
            "productsList": context["dag_run"].conf["list_of_product_labels_to_process"],
            "pdsNode": context["dag_run"].conf["pds_node_name"],
            "processingStatus": "harvest_failed",
            "batchNumber": context["dag_run"].conf["batch_number"],
        }),
    )

    print(response)



##################################################################################
# DAG and Tasks Definitions
##################################################################################

dag = DAG(
        dag_id="${pds_nucleus_basic_registry_dag_id}",
        schedule_interval=None,
        catchup=False,
        start_date=days_ago(1),
        default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=2)
    },
)

# Print start time
print_start_time = BashOperator(
    task_id='Print_Start_Time',
    dag=dag,
    bash_command='date'
)

# PDS Validate Task
validate = EcsRunTaskOperator(
    task_id="Validate_Products",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-validate-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-validate",
                "command": ['{{ dag_run.conf["list_of_product_labels_to_process"] }}'],
            },
        ],
    },
    awslogs_group="/pds/ecs/validate-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-validate",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    on_success_callback=save_product_processing_status_validate_successful,
    on_failure_callback=save_product_processing_status_validate_failed,
)

# PDS Harvest Task
harvest = EcsRunTaskOperator(
    task_id="Harvest_Data",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-airflow-registry-loader-harvest-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
            "containerOverrides": [
                {
                    "name": "pds-registry-loader-harvest",
                    "environment": [
                        {
                            "name": "HARVEST_CFG",
                            "value": "{{ dag_run.conf['efs_config_dir'] }}/harvest.cfg"
                        }
                    ]
                },
            ],
    },
    awslogs_group="/pds/ecs/harvest-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-registry-loader-harvest",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
    on_success_callback=save_product_processing_status_harvest_successful,
    on_failure_callback=save_product_processing_status_harvest_failed,
)

# PDS Nucleus Config Init Task
config_init = EcsRunTaskOperator(
    task_id="Config_Init",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-config-init-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-config-init",
                "command": ['{{ dag_run.conf["s3_config_dir"] }}','{{ dag_run.conf["efs_config_dir"] }}'],
            },
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-config-init-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)

# PDS Nucleus S3 to EFS Copy Task
config_s3_to_efs_copy = EcsRunTaskOperator(
    task_id="Config_S3_to_EFS_Copy",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-s3-to-efs-copy",
                "command": ['{{ dag_run.conf["efs_config_dir"] }}','COPY'],

            },
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)

# PDS Nucleus Config Init Cleanup Task
config_init_cleanup = EcsRunTaskOperator(
    task_id="Config_Init_Cleanup",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-config-init-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-config-init",
                "command": ['{{ dag_run.conf["s3_config_dir"] }}','{{ dag_run.conf["efs_config_dir"] }}','DELETE'],
            },
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-config-init-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE
)


# PDS Nucleus Archive Task
data_archive = EcsRunTaskOperator(
    task_id="Data_Archive",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-s3-to-efs-copy",
                "command": ['{{ dag_run.conf["efs_config_dir"] }}','ARCHIVE','{{ dag_run.conf["pds_hot_archive_bucket_name"] }}', '{{ dag_run.conf["pds_cold_archive_bucket_name"] }}'],

            },
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE
)



# PDS Nucleus S3 to EFS Copy Cleanup Task
config_s3_to_efs_copy_cleanup = EcsRunTaskOperator(
    task_id="Config_S3_to_EFS_Copy_Cleanup",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition-${pds_node_name}",
    launch_type=ECS_LAUNCH_TYPE,
    network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-s3-to-efs-copy",
                "command": ['{{ dag_run.conf["efs_config_dir"] }}','DELETE'],

            },
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE
)


# Print end time
print_end_time = BashOperator(
    task_id='Print_End_Time',
    dag=dag,
    bash_command='date',
    trigger_rule=TriggerRule.ALL_DONE
)

# Workflow
print_start_time >> config_init  >> config_s3_to_efs_copy >> validate  >> harvest >> data_archive >> config_s3_to_efs_copy_cleanup >> config_init_cleanup >> print_end_time

