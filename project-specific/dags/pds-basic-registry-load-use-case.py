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
ECS_SUBNETS = ["<COMMA SEPARATED LIST OF SUBNETS>"]
ECS_SECURITY_GROUPS = ["<COMMA SEPARATED LIST OF SECURITY GROUPS>"]
ECS_AWS_LOGS_GROUP = "/ecs/pds-airflow"

pds_product_label = "default.xml"

dag = DAG(
        dag_id="PDS_Basic_Registry_Use_Case",
        schedule_interval=None,
        catchup=False,
        start_date=days_ago(1)
)

# Print start time
print_start_time = BashOperator(
    task_id='Print_Start_Time',
    dag=dag,
    bash_command='date',
)

# PDS Validate Task
validate = EcsRunTaskOperator(
    task_id="validate",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-validate-task-definition:9",
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
    task_id="harvest",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-airflow-harvest:4",
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
                "name": "pds-airflow-harvest",
                "command": [' -c ' + '{{ dag_run.conf["pds_harvest_config_file"] }}'],
            },
        ],
    },
    awslogs_group="/pds/ecs/harvest",
    awslogs_stream_prefix="ecs/pds-airflow-harvest",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500
)

# PDS Validate Ref with Manifest Task
validate_ref = EcsRunTaskOperator(
    task_id="validate_ref",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-validate-ref-task-definition:3",
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
                "name": "pds-validate-ref-task",
                "command": ['{{ dag_run.conf["harvest_manifest_file_path"] }}',
                            '--auth-opensearch', '{{ dag_run.conf["pds_harvest_config_file"] }}'
                            ],
            },
        ],
    },
    awslogs_group="/pds/ecs/validate-ref",
    awslogs_stream_prefix="ecs/pds-validate-ref-task",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=1000
)


# Print end time
print_end_time = BashOperator(
    task_id='Print_End_Time',
    dag=dag,
    bash_command='date',
    trigger_rule=TriggerRule.ALL_SUCCESS
)

# Workflow
print_start_time >> validate >> harvest >> validate_ref >> print_end_time
