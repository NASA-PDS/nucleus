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
# DAG and Tasks Definitions
##################################################################################

dag = DAG(
        dag_id="${pds_nucleus_s3_backlog_processor_dag_id}",
        schedule_interval=None,
        catchup=False,
        start_date=days_ago(1),
        default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=2),
        },
        params={
            "s3_bucket_name": "<enter bucket name>",
            "s3_bucket_prefix": "<prefix (S3 path to start listing the objects from>",
            "sqs_queue_url": "<SQS queue which is used to save files names in the database>",
            "aws_region": "<aws_region>"
        },
)

# Print start time
print_start_time = BashOperator(
    task_id='Print_Start_Time',
    dag=dag,
    bash_command='date'
)

# PDS  Nucleus S3 Backlog Processor
process_s3_backlog = EcsRunTaskOperator(
    task_id="Process_S3_Backlog",
    dag=dag,
    cluster=ECS_CLUSTER_NAME,
    task_definition="pds-nucleus-s3-backlog-processor-task-definition-${pds_node_name}",
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
                    "name": "pds-nucleus-s3-backlog-processor-task",
                    "environment": [
                        {
                            "name": "S3_BUCKET_NAME",
                            "value": "{{ dag_run.conf['s3_bucket_name'] }}"
                        },
                        {
                            "name": "S3_BUCKET_PREFIX",
                            "value": "{{ dag_run.conf['s3_bucket_prefix'] }}"
                        },
                        {
                            "name": "SQS_QUEUE_URL",
                            "value": "{{ dag_run.conf['sqs_queue_url'] }}"
                        },
                        {
                            "name": "AWS_REGION",
                            "value": "{{ dag_run.conf['aws_region'] }}"
                        }
                    ],
                },
            ],
    },
    awslogs_group="/pds/ecs/process-s3-backlog",
    awslogs_stream_prefix="ecs/process-s3-backlog-${pds_node_name}",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
)


# Print end time
print_end_time = BashOperator(
    task_id='Print_End_Time',
    dag=dag,
    bash_command='date',
    trigger_rule=TriggerRule.ALL_DONE
)

# Workflow
print_start_time >> process_s3_backlog >> print_end_time

