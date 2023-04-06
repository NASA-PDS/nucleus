# PDS Registry Load Use Case DAG
# This DAG is under development. This was just added as an example DAG for Nucleus baseline deployment.

import datetime
import os
import datetime as dt
import boto3

from airflow import DAG
from airflow.contrib.operators.ecs_operator import ECSOperator
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule
from http import client
from airflow import DAG
from airflow.providers.amazon.aws.operators.ecs import ECSOperator
from airflow.utils.dates import days_ago

# ECS configurations
ECS_CLUSTER_NAME            ="pds-nucleus-ecc-tf"
ECS_LAUNCH_TYPE             ="FARGATE"
ECS_SUBNETS                 = ["<COMMA SEPERATED LIST OF SUBNETS>"]
ECS_SECURITY_GROUPS         = ["<COMMA SEPERATED LIST OF SECURITY GROUPS>"]
ECS_AWSLOGS_GROUP           = "/ecs/pds-airflow-ecs-tf"



with DAG(
    dag_id="PDS_Registry_Use_Case",
    schedule_interval=None,
    catchup=False,
    start_date=days_ago(1)
) as dag:
    client=boto3.client('ecs')

    # Download data
    download_data = BashOperator(task_id='Download_Data',
                            bash_command='echo "Download_Data"')

    # Validate data 1 - This task is under development. This just added as an example DAG for Nucleus baseline deployment
    validate_data_1 = BashOperator(task_id='Validate_Data_1',
                            bash_command='echo "Validate_Data"')

    # Validate data 2 - This task is under development. This just added as an example DAG for Nucleus baseline deployment
    validate_data_2 = BashOperator(task_id='Validate_Data_2',
                            bash_command='echo "Validate_Data"')

   # Registry Loader
    harvest_and_load_data = ECSOperator(
        task_id="Harvest_and_Load_Data",
        dag=dag,
        cluster=ECS_CLUSTER_NAME,
        task_definition="pds-airflow-registry-loader-terraform",
        launch_type=ECS_LAUNCH_TYPE,
        network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            },
        },
        overrides={
            "containerOverrides": [],
        },
        awslogs_group=ECS_AWSLOGS_GROUP,
        awslogs_stream_prefix=f"ecs/reg loader"
    )

    # Execute integration tests
    run_integration_tests = ECSOperator(
        task_id="Execute_Integration_Tests",
        dag=dag,
        cluster=ECS_CLUSTER_NAME,
        task_definition="pds-airflow-integration-test-terraform",
        launch_type="FARGATE",
        overrides={
            "containerOverrides": [
                {
                    "name": "pds-airflow-integration-test-container",
                    "command": ["run","https://raw.githubusercontent.com/NASA-PDS/registry/main/docker/postman/postman_collection.json","--env-var","baseUrl=http://10.21.246.222:8080"],
                },
            ],
        },
        network_configuration={
                    "awsvpcConfiguration": {
                        "securityGroups": ECS_SECURITY_GROUPS,
                        "subnets": ECS_SUBNETS,
                    },
                },
        awslogs_group=ECS_AWSLOGS_GROUP,
        awslogs_stream_prefix=f"ecs/integration_tests"
    )


    # Print end date
    print_end_date = BashOperator(
        task_id='Print_End_Date',
        bash_command='date',
        trigger_rule=TriggerRule.ALL_DONE
    )

    # Workflow
    download_data >> validate_data_1 >> harvest_and_load_data >> run_integration_tests >> validate_data_2 >> print_end_date
