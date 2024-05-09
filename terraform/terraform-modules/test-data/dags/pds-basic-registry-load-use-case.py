# PDS Basic Registry Load Use Case DAG
#
# This DAG is a very basic workflow with validate tool and harvest tool. This was just added as an example DAG for
# Nucleus baseline deployment.

import boto3
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from datetime import timedelta

# ECS configurations
ECS_CLUSTER_NAME = "pds-nucleus-ecs"
ECS_LAUNCH_TYPE = "FARGATE"
ECS_SUBNETS = ["subnet-04106ac3731f5e30d","subnet-0f7c425a189ee6434"]
ECS_SECURITY_GROUPS = ["sg-0a95365772d429093"]

# pds_product_label = "default.xml"

dag = DAG(
        dag_id="pds-basic-registry-load-use-case",
        schedule_interval=None,
        catchup=False,
        start_date=days_ago(1),
        default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=2),
        # "retry_exponential_backoff": True,
        # "max_retry_delay": timedelta(hours=2),
    },
)

# Print start time
print_start_time = BashOperator(
    task_id='Print_Start_Time',
    dag=dag,
    bash_command='date',
    doc_md = """\
        #Title"
        Here's a [url](www.airbnb.com)
        """
)

# PDS Validate Task
validate = EcsRunTaskOperator(
    task_id="Validate_Products",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-validate-task-definition",
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
                "name": "pds-validate-task",
                "command": ['{{ dag_run.conf["list_of_product_labels_to_process"] }}'],
            },
        ],
    },
    awslogs_group="/pds/ecs/validate",
    awslogs_stream_prefix="ecs/pds-validate-task",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)

# PDS Harvest Task
harvest = EcsRunTaskOperator(
    task_id="Harvest_Data",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-airflow-registry-loader-harvest-task-definition",
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
                "command": [' -c ' + '{{ dag_run.conf["efs_config_dir"] }}' + '/harvest.cfg'],
            },
        ],
    },
    awslogs_group="/pds/ecs/harvest",
    awslogs_stream_prefix="ecs/pds-registry-loader-harvest",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE
)

# PDS Nucleus Config Init Task
config_init = EcsRunTaskOperator(
    task_id="Config_Init",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-config-init-task-definition",
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
    awslogs_group="/pds/ecs/pds-nucleus-config-init",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)

# PDS Nucleus S3 to EFS Copy Task
config_s3_to_efs_copy = EcsRunTaskOperator(
    task_id="Config_S3_to_EFS_Copy",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition",
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
                "command": ['{{ dag_run.conf["efs_config_dir"] }}'],

            },
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)

# PDS Nucleus Config Init Cleanup Task
config_init_cleanup = EcsRunTaskOperator(
    task_id="Config_Init_Cleanup",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-config-init-task-definition",
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
    awslogs_group="/pds/ecs/pds-nucleus-config-init",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)


# PDS Nucleus S3 to EFS Copy Cleanup Task
config_s3_to_efs_copy_cleanup = EcsRunTaskOperator(
    task_id="Config_S3_to_EFS_Copy_Cleanup",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-to-efs-copy-task-definition",
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
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)


# Print end time
print_end_time = BashOperator(
    task_id='Print_End_Time',
    dag=dag,
    bash_command='date',
    trigger_rule=TriggerRule.ALL_SUCCESS
)

# Workflow
print_start_time >> config_init  >> config_s3_to_efs_copy >> validate >> harvest  >> config_s3_to_efs_copy_cleanup >> config_init_cleanup >> print_end_time
