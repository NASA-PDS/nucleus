# PDS S3 Backlog Processor DAG
#
# Processes existing files in an S3 bucket (backlog) instead of being
# triggered by live S3 events.
#
# Accepts a list of S3 prefixes and fans out one ECS task per prefix so
# multiple path roots can be processed in a single DAG run.

from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models.param import Param


# -------------------------------------------------------------------
# ECS configuration (TEMPLATE — injected by Terraform)
# -------------------------------------------------------------------
ECS_CLUSTER_NAME    = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE     = "FARGATE"
ECS_SUBNETS         = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ${pds_nucleus_ecs_security_groups}


# -------------------------------------------------------------------
# DAG definition
# -------------------------------------------------------------------
with DAG(
    dag_id="${pds_nucleus_s3_backlog_processor_dag_id}",
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
        "s3_bucket_name": Param(
            default="<S3 bucket name>",
            type="string",
            pattern="^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$",
            minLength=3,
            maxLength=63,
        ),
        "s3_bucket_prefixes": Param(
            default=["<prefix>"],
            type="array",
            minItems=1,
            description="List of S3 key prefixes to process. One ECS task is launched per prefix.",
        ),
        "sqs_queue_url": Param(
            default="<SQS queue URL used to register files in the database>",
            type="string",
            pattern="^https:\\/\\/sqs\\.us-west-2\\.amazonaws\\.com\\/\\d+\\/pds-nucleus.*$",
        ),
        "aws_region": Param(
            default="us-west-2",
            type="string",
            pattern="^(us|eu|ap|ca|sa|af|me)-[a-z]+-\\d{1}$",
        ),
    },
) as dag:

    # -------------------------------------------------------------------
    # Build one set of ECS container overrides per prefix at runtime.
    # Using a @task so the params list is resolved from XCom, not at
    # DAG-parse time (params are only available during a DAG run).
    # -------------------------------------------------------------------
    @task
    def build_overrides(**context):
        prefixes       = context["params"]["s3_bucket_prefixes"]
        sqs_queue_url  = context["params"]["sqs_queue_url"]
        aws_region     = context["params"]["aws_region"]
        s3_bucket_name = context["params"]["s3_bucket_name"]
        return [
            {
                "containerOverrides": [
                    {
                        "name": "pds-nucleus-s3-backlog-processor",
                        "environment": [
                            {
                                "name":  "MAINCLASS",
                                "value": "gov.nasa.pds.nucleus.ingress.PDSNucleusS3BackLogProcessor",
                            },
                            {"name": "S3_BUCKET_PREFIX", "value": prefix},
                            {"name": "SQS_QUEUE_URL",    "value": sqs_queue_url},
                            {"name": "AWS_REGION",       "value": aws_region},
                            {"name": "S3_BUCKET_NAME",   "value": s3_bucket_name},
                        ],
                    }
                ]
            }
            for prefix in prefixes
        ]

    print_start_time = BashOperator(
        task_id="Print_Start_Time",
        bash_command="date",
    )

    overrides = build_overrides()

    # One ECS task spawned per prefix via dynamic task mapping.
    process_s3_backlog = EcsRunTaskOperator.partial(
        task_id="Process_S3_Backlog",
        cluster=ECS_CLUSTER_NAME,
        task_definition="pds-nucleus-s3-backlog-processor-task-definition-${pds_node_name}",
        launch_type=ECS_LAUNCH_TYPE,
        network_configuration={
            "awsvpcConfiguration": {
                "securityGroups": ECS_SECURITY_GROUPS,
                "subnets": ECS_SUBNETS,
            }
        },
        awslogs_group="/pds/ecs/pds-nucleus-s3-backlog-processor-${pds_node_name}",
        awslogs_stream_prefix="ecs/pds-nucleus-s3-backlog-processor",
        awslogs_fetch_interval=timedelta(seconds=1),
        number_logs_exception=500,
        trigger_rule=TriggerRule.ALL_DONE,
    ).expand(overrides=overrides)

    print_end_time = BashOperator(
        task_id="Print_End_Time",
        bash_command="date",
        trigger_rule=TriggerRule.ALL_DONE,
    )

    print_start_time >> overrides >> process_s3_backlog >> print_end_time
