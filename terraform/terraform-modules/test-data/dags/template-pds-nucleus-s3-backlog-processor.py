# PDS S3 Backlog Processor DAG
#
# This DAG processes existing files in an S3 bucket (backlog),
# instead of being triggered by S3 events.

import boto3
import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models.param import Param


# --------------------------------------------------------------------------------------
# ECS configurations (templated)
# --------------------------------------------------------------------------------------

ECS_CLUSTER_NAME = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE = "FARGATE"
ECS_SUBNETS = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ${pds_nucleus_ecs_security_groups}
LAMBDA_FUNCTION_NAME = "pds_nucleus_product_processing_status_tracker"


# --------------------------------------------------------------------------------------
# DAG Definition
# --------------------------------------------------------------------------------------

dag = DAG(
    dag_id="${pds_nucleus_s3_backlog_processor_dag_id}",
    schedule=None,                   # Airflow 3 uses "schedule"
    catchup=False,
    start_date=datetime(2024, 1, 1),  # replaces deprecated days_ago()
    default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=2),
    },
    params={
        "s3_bucket_name": Param(
            default="<S3 bucket name>",
            type="string",
            pattern="^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$",
            minLength=3,
            maxLength=63,
        ),
        "s3_bucket_prefix": Param(
            default="<prefix (S3 path to start listing the objects from>",
            type=["null", "string"],
            pattern="^([^/]+/)*[^/]+/?$",
        ),
        "sqs_queue_url": Param(
            default="<SQS queue which is used to save files names in the database>",
            type="string",
            pattern="^https:\\/\\/sqs\\.us-west-2\\.amazonaws\\.com\\/\\d+\\/pds-nucleus.*$",
        ),
        "aws_region": Param(
            default="<aws_region>",
            type="string",
            pattern="^(us|eu|ap|ca|sa|af|me)-[a-z]+-\\d{1}$",
        ),
    },
)


# --------------------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------------------

print_start_time = BashOperator(
    task_id="Print_Start_Time",
    bash_command="date",
    dag=dag,
)


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
        }
    },
    overrides={
        "containerOverrides": [
            {
                "name": "pds-nucleus-s3-backlog-processor",
                "environment": [
                    {
                        "name": "MAINCLASS",
                        "value": "gov.nasa.pds.nucleus.ingress.PDSNucleusS3BackLogProcessor",
                    },
                    {
                        "name": "S3_BUCKET_PREFIX",
                        "value": "{{ params['s3_bucket_prefix'] }}",
                    },
                    {
                        "name": "SQS_QUEUE_URL",
                        "value": "{{ params['sqs_queue_url'] }}",
                    },
                    {
                        "name": "AWS_REGION",
                        "value": "{{ params['aws_region'] }}",
                    },
                    {
                        "name": "S3_BUCKET_NAME",
                        "value": "{{ params['s3_bucket_name'] }}",
                    },
                ],
            }
        ],
    },
    awslogs_group="/pds/ecs/pds-nucleus-s3-backlog-processor-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-backlog-processor",
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
)


# Print end time
print_end_time = BashOperator(
    task_id="Print_End_Time",
    bash_command="date",
    dag=dag,
    trigger_rule=TriggerRule.ALL_DONE,
)


# --------------------------------------------------------------------------------------
# Workflow
# --------------------------------------------------------------------------------------

print_start_time >> process_s3_backlog >> print_end_time
