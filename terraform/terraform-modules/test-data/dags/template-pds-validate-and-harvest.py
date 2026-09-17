# PDS Validate and Harvest DAG (Airflow 3 compatible, TEMPLATE)
# Same as pds-basic-registry-load-use-case but without the Data_Archive task.

import boto3
import json
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowFailException, AirflowSkipException
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta

from pds_airflow_custom_operators import (
    ValidateEcsRunTaskOperator,
    HarvestEcsRunTaskOperator,
)
from pds_log_parsers import (
    batch_number_from_config_dir,
    build_manifest_key,
    common_directory,
    format_human_report,
    harvested_count,
)
from pds_registry_client import registry_url_for, verify_products_against_registry


# -------------------------------------------------------------------
# ECS configuration (TEMPLATE — injected by Terraform)
# -------------------------------------------------------------------
ECS_CLUSTER_NAME    = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE     = "FARGATE"
ECS_SUBNETS         = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ${pds_nucleus_ecs_security_groups}
AWS_REGION          = "${aws_region}"

# -------------------------------------------------------------------
# Database configuration (TEMPLATE — injected by Terraform). Used only by
# Generate_Summary_Report, to write product_tracking via the RDS Data API.
# -------------------------------------------------------------------
DB_CLUSTER_ARN = "${pds_db_cluster_arn}"
DB_SECRET_ARN  = "${pds_db_secret_arn}"
DB_NAME        = "${pds_db_name}"
PDS_NODE_NAME  = "${pds_node_name}"
REGISTRY_SEARCH_URL_PREFIX_DEFAULT = "${pds_registry_search_url_prefix_default}"

rds_data = boto3.client("rds-data")

# A CloudWatch log event may not exceed 256 KB. Leave headroom for the log
# framing that Airflow adds around the message.
MAX_SUMMARY_EVENT_BYTES = 200_000

# Harvest_Data runs with trigger_rule=ALL_DONE (below), so it fires even when
# Validate_Products failed. If harvest itself then fails, an in-place task
# retry often can't fix it -- the EFS copy or the manifest it read may need
# to be regenerated too -- so the whole DAG restarts from List_Products_In_Batch
# instead of just retrying Harvest_Data, up to this many times.
MAX_DAG_RESTARTS_ON_HARVEST_FAILURE = 3

# Cap on per-product events (channel 2 below emits one per product, not just
# failures). Sized well above any realistic product_batch_size so normal runs
# never hit it; it exists only so a misconfigured batch of many thousands of
# products can't turn into an unbounded log stream.
MAX_PRODUCT_EVENTS = 5000

# -------------------------------------------------------------------
# Read the batch's product list (used below for the XCom-visible task)
# -------------------------------------------------------------------
def _read_product_list(s3_config_dir):
    bucket = s3_config_dir.replace("s3://", "").split("/")[0]
    key = "/".join(s3_config_dir.replace("s3://", "").split("/")[1:] + ["product_list.txt"])
    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    return [line for line in body.decode("utf-8").splitlines() if line]

# -------------------------------------------------------------------
# DAG definition
# -------------------------------------------------------------------
dag = DAG(
    dag_id="${pds_validate_and_harvest_dag_id}",
    schedule=None,
    catchup=False,
    start_date=datetime(2024, 1, 1),
    tags=["pds", "nucleus", "${pds_node_name}"],
    # Every run of this DAG is a single sequential chain (list_products >>
    # ... >> print_end_time), so exactly one task is ever running per active
    # run -- max_active_tasks therefore has to move together with
    # max_active_runs, or it becomes the new binding cap on its own.
    #
    # 25 = the ECS Fargate capacity actually budgeted to this pipeline,
    # divided across the DAGs currently running against it. Account vCPU
    # quota is 256; each task uses 4 vCPU, so 64 tasks is the account's hard
    # ceiling; ~50 of that is earmarked for this pipeline (other services
    # share the same account/cluster); with only PDS_IMG backlog + realtime
    # actually active right now, that's 50 / 2 = 25 per DAG. Revisit this
    # division when another node (e.g. SBN) starts running -- or better,
    # replace it with a shared Airflow Pool sized to the real 50-task budget
    # so it doesn't need re-dividing by hand every time a node is added.
    max_active_runs=260,
    max_active_tasks=260,
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
        #
        # "-a archived" because a product left at the default "staged" is not
        # treated as part of the archive; "--overwrite" because without it
        # harvest skips anything already registered, so a re-run silently
        # loads nothing and never picks up a corrected label.
        "harvest_extra_args": "-a archived --overwrite",
        # Whether a data integrity failure in the summary should fail the DAG
        # run. Turn off to let a batch finish green while its problems are
        # still reported.
        "fail_on_data_integrity_error": True,
        # Registry verification: an independent check of the live public PDS
        # registry, not just Nucleus's own harvest result. Editable here so
        # it can be disabled from the UI with no redeploy if the registry
        # API becomes unreachable or starts rate-limiting Nucleus.
        "registry_check_enabled": True,
        "registry_check_max_workers": 8,
        "registry_check_timeout_seconds": 5,
        # Fallback only -- the trigger's conf carries the authoritative,
        # Terraform-configured value (see pds_registry_search_url_prefix in
        # terraform.tfvars); this default only applies to a manual
        # "Trigger DAG w/ config" run.
        "registry_search_url_prefix": REGISTRY_SEARCH_URL_PREFIX_DEFAULT,
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
# List products being processed in this batch (visible in the
# task's XCom tab in the Airflow UI, instead of digging through logs).
# -------------------------------------------------------------------
@task(task_id="List_Products_In_Batch", dag=dag)
def list_products_in_batch(**context):
    products = _read_product_list(context["dag_run"].conf["s3_config_dir"])
    # Only the count is logged. The full list is returned to XCom, where the
    # UI shows it and the summary task reads it, so printing each product
    # here would just repeat all of them in the log.
    print(f"{len(products)} product(s) in this batch")
    return products

list_products = list_products_in_batch()

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
    awslogs_group="/pds/ecs/pds-nucleus-config-init-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    # No custom log parsing depends on this one running synchronously
    # (unlike Validate_Products/Harvest_Data), so it's safe to free the
    # MWAA worker slot while ECS runs this.
    deferrable=True,
    # 6s, not 1s: every EcsRunTaskOperator in this DAG polls ECS
    # DescribeTasks at this interval while waiting. At 1s, ~20 concurrent
    # DAG runs (each with one such operator active, since max_active_tasks
    # tracks max_active_runs) pushed the combined poll rate past ECS's
    # account-level DescribeTasks throttle limit, failing tasks with
    # ThrottlingException. 6s matches boto3's own built-in ECS waiter
    # default, which exists for the same reason.
    waiter_delay=6,
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
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=True,
    waiter_delay=6,
    dag=dag,
)

# -------------------------------------------------------------------
# VALIDATE
# -------------------------------------------------------------------
validate = ValidateEcsRunTaskOperator(
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
    awslogs_group="/pds/ecs/validate-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-validate",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=False,
    waiter_delay=6,
    # No explicit retries override: ValidateEcsRunTaskOperator already
    # distinguishes real data-validation failures (no retry, fails fast)
    # from genuine infra failures (retried per the DAG-level default).
    dag=dag,
)

# -------------------------------------------------------------------
# HARVEST
# -------------------------------------------------------------------
harvest = HarvestEcsRunTaskOperator(
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
    awslogs_group="/pds/ecs/harvest-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-registry-loader-harvest",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    deferrable=False,
    waiter_delay=6,
    # execute() pulls max available CloudWatch logs
    # and checks the [SUMMARY] line for failed files. If any files failed,
    # the task fails (since files missing from EFS indicate upstream copy failure).
    #
    # ALL_DONE: harvest runs even when Validate_Products failed -- a
    # validation failure on some products shouldn't block harvest from
    # loading the ones that did pass.
    trigger_rule=TriggerRule.ALL_DONE,
    # 0, not the DAG-level default of 5: an in-place retry of just this task
    # is not the recovery path here -- see _prepare_harvest_restart below,
    # which restarts the whole DAG (up to 3x) instead once this task's
    # single attempt fails.
    retries=0,
    dag=dag,
)


# Grouped so the grid view shows one collapsed row instead of two -- these
# two tasks are skipped on every normal run (trigger_rule=ONE_FAILED only
# engages them when Harvest_Data fails), and a pair of skip icons on every
# single column was pure visual noise for the common case.
with TaskGroup(group_id="Harvest_Restart_On_Failure", dag=dag) as harvest_restart_group:

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
        with no direct DB access -- it raised "Direct database access via the
        ORM is not allowed in Airflow 3.0" the first time this actually fired.
        TriggerDagRunOperator, unlike a raw trigger_dag() call, goes through
        the supported Task Execution API, so the restart is done as a real
        downstream task instead of a callback.

        dag_run.conf carries the restart counter forward across attempts.
        batch_number stays the same (still the same logical batch), but
        s3_config_dir/efs_config_dir get a restart-specific suffix -- reusing
        them would race with this run's own ALL_DONE cleanup chain, which
        deletes those same paths concurrently.
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
        restart_suffix = f"__restart{attempt + 1}"
        if conf.get("s3_config_dir"):
            conf["s3_config_dir"] = conf["s3_config_dir"] + restart_suffix
        if conf.get("efs_config_dir"):
            conf["efs_config_dir"] = conf["efs_config_dir"] + restart_suffix
        print(
            f"Harvest failed; restarting whole DAG as {new_run_id} "
            f"(attempt {attempt + 1} of {MAX_DAG_RESTARTS_ON_HARVEST_FAILURE})"
        )
        return {"conf": conf, "run_id": new_run_id}


    _harvest_restart_prep = _prepare_harvest_restart()

    restart_dag_on_harvest_failure = TriggerDagRunOperator(
        task_id="Restart_Whole_Dag_On_Harvest_Failure",
        trigger_dag_id="${pds_validate_and_harvest_dag_id}",
        trigger_run_id=_harvest_restart_prep["run_id"],
        conf=_harvest_restart_prep["conf"],
        wait_for_completion=False,
        dag=dag,
    )

# -------------------------------------------------------------------
# CLEANUP
# -------------------------------------------------------------------
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
    awslogs_group="/pds/ecs/pds-nucleus-s3-to-efs-copy-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-s3-to-efs-copy",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
    deferrable=True,
    waiter_delay=6,
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
    awslogs_group="/pds/ecs/pds-nucleus-config-init-${pds_node_name}",
    awslogs_stream_prefix="ecs/pds-nucleus-config-init",
    awslogs_region=AWS_REGION,
    awslogs_fetch_interval=timedelta(seconds=1),
    number_logs_exception=500,
    trigger_rule=TriggerRule.ALL_DONE,
    deferrable=True,
    waiter_delay=6,
    dag=dag,
)

def _upsert_product_tracking(products):
    """Write the batch-completion facts (lidvid, statuses, registry URL) into
    product_tracking, alongside whatever the file-arrival and batch-dispatch
    writers already put there -- same first-write-wins-vs-always-overwrite
    split as those two: everything written here is the current state of the
    batch's result, so it's always overwritten on a re-run, unlike
    ingestion_source. Only products with a known S3 URL are written -- that
    column is the table's primary key.

    A write failure here is logged and swallowed, not raised: this table is
    a search/reporting aid, not the data-integrity check itself (that's the
    registry-vs-harvest comparison above, which already fails the DAG on
    its own terms).
    """
    rows = [p for p in products if p["s3_url"]]
    if not rows:
        return

    sql = """
            INSERT INTO product_tracking
            (
                s3_url_of_product_label,
                lidvid,
                pds_node,
                status,
                validate_status,
                harvest_status,
                registry_status,
                registry_url,
                batch_number,
                dag_run_id,
                first_seen_epoch_time,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                :lidvid_param,
                :pds_node_param,
                'DATA_INTEGRITY_CHECKED',
                :validate_status_param,
                :harvest_status_param,
                :registry_status_param,
                :registry_url_param,
                :batch_number_param,
                :dag_run_id_param,
                :first_seen_epoch_time_param,
                :last_updated_epoch_time_param
                )
            ON DUPLICATE KEY UPDATE
                lidvid = VALUES(lidvid),
                status = VALUES(status),
                validate_status = VALUES(validate_status),
                harvest_status = VALUES(harvest_status),
                registry_status = VALUES(registry_status),
                registry_url = VALUES(registry_url),
                batch_number = VALUES(batch_number),
                dag_run_id = VALUES(dag_run_id),
                last_updated_epoch_time = VALUES(last_updated_epoch_time)
            """

    ts = int(datetime.utcnow().timestamp() * 1000)
    param_sets = [
        [
            {"name": "s3_url_of_product_label_param", "value": {"stringValue": p["s3_url"]}},
            {"name": "lidvid_param",                   "value": {"stringValue": p["lidvid"]} if p["lidvid"] else {"isNull": True}},
            {"name": "pds_node_param",                 "value": {"stringValue": PDS_NODE_NAME}},
            {"name": "validate_status_param",          "value": {"stringValue": p["validate_status"]}},
            {"name": "harvest_status_param",            "value": {"stringValue": p["harvest_status"]}},
            {"name": "registry_status_param",           "value": {"stringValue": p["registry_status"]}},
            {"name": "registry_url_param",              "value": {"stringValue": p["registry_url"]} if p["registry_url"] else {"isNull": True}},
            {"name": "batch_number_param",               "value": {"stringValue": p["batch_number"]} if p["batch_number"] else {"isNull": True}},
            {"name": "dag_run_id_param",                 "value": {"stringValue": p["dag_run_id"]}},
            {"name": "first_seen_epoch_time_param",      "value": {"longValue": ts}},
            {"name": "last_updated_epoch_time_param",    "value": {"longValue": ts}},
        ]
        for p in rows
    ]

    rds_data.batch_execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql=sql,
        parameterSets=param_sets,
    )


# -------------------------------------------------------------------
# SUMMARY REPORT
# -------------------------------------------------------------------
@task(task_id="Generate_Summary_Report", trigger_rule=TriggerRule.ALL_DONE, dag=dag)
def generate_summary_report(**context):
    """Reconcile the products received, validated and harvested in this batch.

    Every input is read from XCom because this task runs in the MWAA worker,
    which does not mount the EFS volume the ECS containers write to.
    """
    dag_run = context["dag_run"]
    ti = context["task_instance"]
    conf = dag_run.conf or {}

    # Two identifiers, deliberately kept apart. batch_number names the work:
    # it is minted by the trigger, appears in the S3 config directory and
    # survives a re-run. dag_run_id names one Airflow attempt at that work.
    # Reporting only the run id, as this task used to, left no way to line a
    # report up with the batch the rest of the pipeline talks about.
    dag_run_id = dag_run.run_id
    # A hand-triggered run has no batch_number in its conf, so fall back to
    # the config directory, whose last segment is the batch name.
    batch_number = conf.get("batch_number") or batch_number_from_config_dir(
        conf.get("s3_config_dir", "")
    )
    # Recorded in the report because it decides whether an already-
    # registered product is overwritten or skipped, which is the difference
    # between a re-run that updates the registry and one that does nothing.
    harvest_extra_args = context["params"].get("harvest_extra_args", "")

    def pull(task_id, key, default):
        value = ti.xcom_pull(task_ids=task_id, key=key)
        return default if value is None else value

    # Everything the batch was asked to process.
    manifest_urls = pull("List_Products_In_Batch", "return_value", [])

    validate_passed = pull("Validate_Products", "validate_passed", [])
    validate_failed = pull("Validate_Products", "validate_failed", [])
    validate_skipped = pull("Validate_Products", "validate_skipped", [])
    validate_summary = pull("Validate_Products", "validate_summary", {})
    harvest_summary = pull("Harvest_Data", "harvest_summary", {})

    # The manifest holds S3 URLs while validate logs EFS paths, so compare on
    # file name rather than on the full location.
    manifest_keys = {build_manifest_key(url) for url in manifest_urls}
    # Every product validate had something to say about, whatever the
    # verdict. Counting only the passing ones would report a product that
    # validate explicitly failed as one it never looked at.
    assessed_keys = {
        build_manifest_key(item["file"])
        for item in validate_passed + validate_failed + validate_skipped
    }

    unexpected = sorted(assessed_keys - manifest_keys)

    received_count = len(manifest_urls)
    passed_count = len(validate_passed)

    # Validate publishes its XComs only after a successful run, and its
    # parser yields nothing if the expected report lines are absent. Empty
    # results therefore mean "validate reported nothing", which is not the
    # same as "these products failed validation". Track the difference so
    # the report cannot accuse 166 good products of not being validated.
    validate_reported = bool(
        validate_passed or validate_failed or validate_skipped or validate_summary
    )

    # Only meaningful once validate has reported. Without its results every
    # product would be listed here, which reads as a data problem when the
    # real problem is the missing report.
    not_validated = sorted(manifest_keys - assessed_keys) if validate_reported else []

    # Harvest only reports a count if it emitted a [SUMMARY] line. Treat a
    # missing count as unknown rather than assuming it matched, so a silent
    # harvest failure cannot be reported as SUCCESS.
    harvest_count = harvested_count(harvest_summary)
    harvest_count_known = harvest_count is not None

    # harvest skips a product it considers already registered. That is not an
    # error, but it does mean this run did not load it, so report it.
    harvest_skipped = harvest_summary.get("skipped_files", 0)

    counts_match = received_count == passed_count and (
        not harvest_count_known or harvest_count == received_count
    )

    # Every product received should end up either newly loaded or recognised
    # as already registered. A shortfall means harvest dropped some without
    # saying so, which the loaded count alone would not reveal.
    harvest_accounted = (
        not harvest_count_known or harvest_count + harvest_skipped == received_count
    )

    # Conditions that mean the batch cannot be trusted. Each is phrased as
    # the finding itself so the DAG failure message says what is wrong.
    failures = []
    if not validate_reported:
        failures.append("validate published no results, so nothing was verified")
    if validate_failed:
        failures.append(f"{len(validate_failed)} product(s) failed validation")
    if not_validated:
        failures.append(f"{len(not_validated)} product(s) were never validated")
    if unexpected:
        failures.append(
            f"{len(unexpected)} validated product(s) were not in the manifest"
        )
    if not harvest_count_known:
        failures.append("harvest reported no count, so the load is unverified")
    if harvest_summary.get("failed_files"):
        failures.append(
            f"harvest failed on {harvest_summary['failed_files']} file(s)"
        )
    if not harvest_accounted:
        failures.append(
            f"harvest accounted for {(harvest_count or 0) + harvest_skipped} of "
            f"{received_count} product(s)"
        )

    # Worth surfacing, but not wrong. Re-running an already-ingested batch
    # legitimately loads nothing, and failing on that would make every
    # repeat run red.
    warnings = []
    if harvest_count_known and not harvest_count and harvest_skipped:
        warnings.append(
            f"harvest skipped all {harvest_skipped} product(s) as already "
            "registered, so this run loaded nothing new. harvest_extra_args "
            f"was '{harvest_extra_args}'; without --overwrite harvest leaves "
            "registered products untouched."
        )
    if validate_skipped:
        warnings.append(f"validate skipped {len(validate_skipped)} product(s)")

    all_match = not failures and not warnings

    # One entry per product, holding only what cannot be derived: the file
    # name, its LIDVID and its status. The directory is identical for every
    # product in a batch, so it is recorded once as a prefix instead of being
    # repeated on all 166 entries.
    default_status = "not_validated" if validate_reported else "unknown"
    status_by_name = {name: default_status for name in manifest_keys}
    for status, items in (
        ("passed", validate_passed),
        ("failed", validate_failed),
        ("skipped", validate_skipped),
    ):
        for item in items:
            status_by_name[build_manifest_key(item["file"])] = status

    # What happened to these products in the registry. harvest reports only
    # batch totals, never per-product lines, so this can only be stated when
    # the totals leave no doubt: either everything was loaded or everything
    # was skipped. Any mix is "unknown" rather than a guess about which
    # product fell in which group.
    if not harvest_count_known:
        batch_harvest_status = "unknown"
    elif harvest_count == received_count and not harvest_skipped:
        batch_harvest_status = "loaded"
    elif harvest_skipped == received_count and not harvest_count:
        batch_harvest_status = "already_registered"
    else:
        batch_harvest_status = "unknown"

    lidvid_by_name = {
        build_manifest_key(item["file"]): item["lidvid"]
        for item in validate_passed + validate_failed + validate_skipped
    }

    # The full S3 URL of every product. An entry is read on its own far
    # more often than as part of the whole report, and a bare file name
    # plus a prefix held somewhere else is not something you can paste into
    # an s3 command or a browser. s3_prefix stays in the report as a
    # heading; the report shortens these against it for display.
    s3_prefix = common_directory(manifest_urls)
    url_by_name = {build_manifest_key(url): url for url in manifest_urls}

    # "validate_status", not a bare "status": a product that passed
    # validation has only been checked, not necessarily registered. Calling
    # that "passed" on its own invites reading a validated-but-never-loaded
    # product as fully ingested.
    products = [
        {
            # Repeated on every entry so a product found on its own still
            # names where it came from. The XCom list below is read without
            # the surrounding report, and a product pulled out of a log
            # search has nothing else to tie it back to its batch.
            "batch_number": batch_number,
            "dag_run_id": dag_run_id,
            "name": name,
            "s3_url": url_by_name.get(name),
            "lidvid": lidvid_by_name.get(name),
            "validate_status": status_by_name[name],
            "harvest_status": batch_harvest_status,
        }
        for name in sorted(status_by_name)
    ]

    # Registry verification: independent of Nucleus's own harvest result,
    # confirm each product is actually discoverable in the live public PDS
    # registry. Checked for every product with a known lidvid, regardless
    # of validate/harvest outcome -- even a product that failed validation
    # or whose batch harvest status is "unknown" may already be in the
    # registry from a prior run, and that's worth knowing either way. The
    # only gate is the registry_check_enabled kill switch.
    registry_check_enabled = context["params"].get("registry_check_enabled", True)
    registry_max_workers = context["params"].get("registry_check_max_workers", 8)
    registry_timeout = context["params"].get("registry_check_timeout_seconds", 5)
    # conf (set by the trigger) is authoritative; params is only the
    # fallback for a manual "Trigger DAG w/ config" run.
    registry_search_url_prefix = conf.get("registry_search_url_prefix") or context["params"].get(
        "registry_search_url_prefix"
    )

    to_verify = products if registry_check_enabled else []
    registry_status_by_name = verify_products_against_registry(
        to_verify, registry_search_url_prefix, max_workers=registry_max_workers, timeout=registry_timeout
    )
    for product in products:
        product["registry_status"] = registry_status_by_name.get(product["name"], "not_checked")
        product["registry_url"] = (
            registry_url_for(product["lidvid"], registry_search_url_prefix) if product["lidvid"] else None
        )

    registry_checked = len(registry_status_by_name)
    registry_confirmed = sum(1 for s in registry_status_by_name.values() if s == "confirmed")
    registry_not_found = sum(1 for s in registry_status_by_name.values() if s == "not_found")
    registry_unknown = sum(1 for s in registry_status_by_name.values() if s == "unknown")
    # The actionable signal: harvest says this product is loaded/registered,
    # but the live registry doesn't confirm it. Always a hard failure, not a
    # warning -- by the time this task runs, Config_S3_To_Efs_Copy_Cleanup
    # and Config_Init_Cleanup have already run after Harvest, so there is
    # already a real gap since harvest finished, not an immediate check.
    registry_harvest_mismatch = sum(
        1
        for p in products
        if p["harvest_status"] in ("loaded", "already_registered")
        and p["registry_status"] not in ("confirmed", "not_checked")
    )
    if registry_harvest_mismatch:
        failures.append(
            f"registry did not confirm {registry_harvest_mismatch} of {registry_checked} "
            "harvest-claimed product(s)"
        )

    # Recomputed: all_match was already set above, before this batch's
    # registry-mismatch failure (if any) existed.
    all_match = not failures and not warnings

    summary = {
        "batch_number": batch_number,
        "dag_run_id": dag_run_id,
        "status": "FAILED" if failures else ("WARNING" if warnings else "SUCCESS"),
        "timing": {
            "start_time": dag_run.start_date.isoformat() if dag_run.start_date else None,
            "end_time": datetime.utcnow().isoformat(),
        },
        "counts": {
            "received": received_count,
            "validated": passed_count,
            "validation_failed": len(validate_failed),
            "validation_skipped": len(validate_skipped),
            "harvested": harvest_count,
            "harvest_skipped": harvest_skipped,
            "registry_checked": registry_checked,
            "registry_confirmed": registry_confirmed,
            "registry_not_found": registry_not_found,
            "registry_unknown": registry_unknown,
            "registry_harvest_mismatch": registry_harvest_mismatch,
        },
        "tool_summaries": {
            "validate": validate_summary,
            "harvest": harvest_summary,
        },
        "data_integrity": {
            "validate_results_reported": validate_reported,
            "harvest_count_reported": harvest_count_known,
            "counts_match": counts_match,
            "harvest_accounted": harvest_accounted,
            "not_validated": not_validated,
            "unexpected_products": unexpected,
            "failures": failures,
            "warnings": warnings,
            "all_match": all_match,
            "status": "COMPLETE" if all_match else "INCOMPLETE",
        },
        "s3_prefix": s3_prefix,
        "efs_prefix": common_directory([item["file"] for item in validate_passed]),
        "harvest_status": batch_harvest_status,
        "harvest_extra_args": harvest_extra_args,
    }

    # A CloudWatch log event is capped at 256 KB. The product list itself is
    # never in this event (channel 2 below carries it instead); the only
    # fields here that can still grow unboundedly are the two name lists in
    # data_integrity, so trim those rather than let CloudWatch truncate the
    # whole event on an unusually large batch.
    payload = json.dumps(summary, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_SUMMARY_EVENT_BYTES:
        summary["data_integrity"]["not_validated"] = []
        summary["data_integrity"]["not_validated_omitted"] = len(not_validated)
        summary["data_integrity"]["unexpected_products"] = []
        summary["data_integrity"]["unexpected_products_omitted"] = len(unexpected)
        payload = json.dumps(summary, separators=(",", ":"))

    # Channel 1: one batch-level event. Metric filters read scalars from it,
    # e.g. $.counts.received or $.status, to drive a CloudWatch dashboard.
    print(f"PDS_BATCH_SUMMARY_JSON: {payload}")

    # Channel 2: one event per product in the batch, every product, not just
    # failures. CloudWatch Logs Insights flattens a JSON array by index
    # (products.0.name, products.1.name, ...), so per-product status cannot
    # be queried out of the batch event above; a separate event per product
    # makes it queryable, and this is the only place in CloudWatch that
    # carries the product list. MWAA wraps each print() in Airflow's own
    # log-line prefix, so the event is not itself valid JSON and $.-style
    # field discovery will not work -- query it with an explicit parse, e.g.:
    #
    #   filter @message like /PDS_PRODUCT_JSON/
    #   | parse @message /"name":"(?<name>[^"]*)"/
    #   | parse @message /"validate_status":"(?<validate_status>[^"]*)"/
    #   | filter validate_status != "passed"
    for product in products[:MAX_PRODUCT_EVENTS]:
        print(
            "PDS_PRODUCT_JSON: "
            + json.dumps(
                {
                    "batch_number": batch_number,
                    "dag_run_id": dag_run_id,
                    "name": product["name"],
                    "s3_url": product["s3_url"],
                    "lidvid": product["lidvid"],
                    "validate_status": product["validate_status"],
                    "harvest_status": product["harvest_status"],
                    "registry_status": product["registry_status"],
                    "registry_url": product["registry_url"],
                },
                separators=(",", ":"),
            )
        )
    if len(products) > MAX_PRODUCT_EVENTS:
        print(
            f"{len(products) - MAX_PRODUCT_EVENTS} product event(s) omitted; "
            f"logged the first {MAX_PRODUCT_EVENTS} of {len(products)}. "
            "The full list is still in the report and the products XCom."
        )

    issues = [
        product for product in products if product["validate_status"] != "passed"
    ]
    # Printed last, after the (possibly hundreds of) per-product events
    # above, so the human-readable one-line verdict is what's visible at
    # the bottom of the task log rather than buried above them.
    print(
        f"Batch {summary['status']}: received={received_count} "
        f"validated={passed_count} harvested={harvest_count} "
        f"not_validated={len(not_validated)} unexpected={len(unexpected)} "
        f"issues={len(issues)}"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")

    # Searchable record of this batch's result, independent of CloudWatch --
    # see product_tracking. Best-effort: a write failure here is not a
    # data-integrity problem with the batch itself, so it's logged and
    # swallowed rather than failing a run that is otherwise fine.
    try:
        _upsert_product_tracking(products)
    except Exception as e:
        print(f"WARNING: failed to write product_tracking: {e}")

    # Channel 3: the human-readable report, for users who only have the
    # Airflow UI. It goes to XCom rather than the log because MWAA stores
    # task logs in CloudWatch, so printing it would duplicate the whole
    # report into CloudWatch alongside the JSON event.
    # Pushed before any failure below, so the report is still there to read
    # in the UI on a run that fails.
    ti.xcom_push(key="report", value=format_human_report(summary, products))
    ti.xcom_push(key="products", value=products)

    # Fail the run on a bad batch, now that everything above has been
    # reported. AirflowFailException rather than a plain raise: this verdict
    # is computed from XComs that will not change, so the DAG-level retries
    # would replay the same failure five times to no purpose.
    if failures and context["params"]["fail_on_data_integrity_error"]:
        raise AirflowFailException(
            f"Batch {batch_number or dag_run_id} failed data integrity: "
            + "; ".join(failures)
        )

    # Return only the counts. Airflow echoes the returned value into the
    # task log, so returning the full report would put it in CloudWatch too.
    return {
        "batch_number": batch_number,
        "dag_run_id": dag_run_id,
        "status": summary["status"],
        "counts": summary["counts"],
        "s3_prefix": s3_prefix,
        # The checks behind the status, not just its verdict. Without these
        # an INCOMPLETE result gives no clue which reconciliation failed.
        # Counts only for the product lists, which can be long and are
        # already in the batch event.
        "data_integrity": {
            "status": summary["data_integrity"]["status"],
            "validate_results_reported": validate_reported,
            "harvest_count_reported": harvest_count_known,
            "counts_match": counts_match,
            "harvest_accounted": harvest_accounted,
            "not_validated": len(not_validated),
            "unexpected_products": len(unexpected),
            "warnings": warnings,
        },
    }


summary_report = generate_summary_report()

# -------------------------------------------------------------------
# WORKFLOW
# -------------------------------------------------------------------
(
    print_start_time
    >> list_products
    >> config_init
    >> config_s3_to_efs_copy
    >> validate
    >> harvest
    >> config_s3_to_efs_copy_cleanup
    >> config_init_cleanup
    >> summary_report
    >> print_end_time
)

# Separate branch off Harvest_Data, alongside the ALL_DONE cleanup chain
# above: only runs when Harvest_Data itself fails (trigger_rule=ONE_FAILED
# on Prepare_Harvest_Restart), restarting the whole DAG rather than retrying
# just this task.
harvest >> harvest_restart_group
