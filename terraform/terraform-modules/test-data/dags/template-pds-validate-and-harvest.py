# PDS Validate and Harvest DAG (Airflow 3 compatible, TEMPLATE)
# Same as pds-basic-registry-load-use-case but without the Data_Archive task.

import boto3
import json
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowFailException
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta

from pds_airflow_custom_operators import (
    ValidateEcsRunTaskOperator,
    HarvestEcsRunTaskOperator,
)
from pds_log_parsers import (
    build_manifest_key,
    common_directory,
    format_human_report,
    harvested_count,
    relative_path,
)


# -------------------------------------------------------------------
# ECS configuration (TEMPLATE — injected by Terraform)
# -------------------------------------------------------------------
ECS_CLUSTER_NAME    = "${pds_nucleus_ecs_cluster_name}"
ECS_LAUNCH_TYPE     = "FARGATE"
ECS_SUBNETS         = ${pds_nucleus_ecs_subnets}
ECS_SECURITY_GROUPS = ${pds_nucleus_ecs_security_groups}
AWS_REGION          = "${aws_region}"

# A CloudWatch log event may not exceed 256 KB. Leave headroom for the log
# framing that Airflow adds around the message.
MAX_SUMMARY_EVENT_BYTES = 200_000

# Cap on per-product issue events. When a whole batch is broken, every
# product is an issue, and emitting one event each would flood the log with
# the same finding repeated. The batch event already carries the full list.
MAX_PRODUCT_ISSUE_EVENTS = 25

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
        "harvest_extra_args": "",
        # Whether a data integrity failure in the summary should fail the DAG
        # run. Turn off to let a batch finish green while its problems are
        # still reported.
        "fail_on_data_integrity_error": True,
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
    deferrable=False,
    waiter_delay=1,
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
    deferrable=False,
    waiter_delay=1,
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
    waiter_delay=1,
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
    waiter_delay=1,
    # execute() pulls max available CloudWatch logs
    # and checks the [SUMMARY] line for failed files. If any files failed,
    # the task fails (since files missing from EFS indicate upstream copy failure).
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
    deferrable=False,
    waiter_delay=1,
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
    deferrable=False,
    waiter_delay=1,
    dag=dag,
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
            "registered, so this run loaded nothing new. Pass "
            "harvest_extra_args='-O' to overwrite them."
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

    # Each product's location below the shared prefix. Keeping this rather
    # than only the file name makes the compression lossless: the full URL
    # is s3_prefix + "/" + path. Products sitting in different
    # subdirectories would otherwise all collapse to a bare file name with
    # no way to tell where they came from.
    s3_prefix = common_directory(manifest_urls)
    path_by_name = {
        build_manifest_key(url): relative_path(url, s3_prefix) for url in manifest_urls
    }

    # "validate_status", not a bare "status": a product that passed
    # validation has only been checked, not necessarily registered. Calling
    # that "passed" on its own invites reading a validated-but-never-loaded
    # product as fully ingested.
    products = [
        {
            "name": name,
            "path": path_by_name.get(name, name),
            "lidvid": lidvid_by_name.get(name),
            "validate_status": status_by_name[name],
            "harvest_status": batch_harvest_status,
        }
        for name in sorted(status_by_name)
    ]

    summary = {
        "batch_id": dag_run.run_id,
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
        "products": products,
    }

    # A CloudWatch log event is capped at 256 KB. Drop the per-product list
    # rather than let the whole report be truncated on a very large batch;
    # the counts and the reconciliation lists still get through.
    payload = json.dumps(summary, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_SUMMARY_EVENT_BYTES:
        summary["products"] = []
        summary["products_omitted"] = len(products)
        payload = json.dumps(summary, separators=(",", ":"))

    # Channel 1: one batch-level event. Metric filters read scalars from it,
    # e.g. $.counts.received or $.status, to drive a CloudWatch dashboard.
    print(f"PDS_BATCH_SUMMARY_JSON: {payload}")

    # Channel 2: one event per product that needs attention. CloudWatch Logs
    # Insights flattens a JSON array by index (products.0.name,
    # products.1.name, ...), so per-product status cannot be queried out of
    # the batch event above. A separate event per product makes it
    # queryable. Only non-passing products are emitted, so a healthy batch
    # adds nothing to the log.
    issues = [
        product for product in products if product["validate_status"] != "passed"
    ]
    for issue in issues[:MAX_PRODUCT_ISSUE_EVENTS]:
        print(
            "PDS_PRODUCT_ISSUE_JSON: "
            + json.dumps(
                {
                    "batch_id": summary["batch_id"],
                    "name": issue["name"],
                    # Spelled out in full here. These events are capped and
                    # are what an operator acts on, so the location should
                    # not have to be reassembled from the batch event.
                    "s3_url": f"{s3_prefix}/{issue['path']}" if s3_prefix else issue["path"],
                    "lidvid": issue["lidvid"],
                    "validate_status": issue["validate_status"],
                    "harvest_status": issue["harvest_status"],
                },
                separators=(",", ":"),
            )
        )
    if len(issues) > MAX_PRODUCT_ISSUE_EVENTS:
        print(
            f"{len(issues)} products need attention; "
            f"logged the first {MAX_PRODUCT_ISSUE_EVENTS}. "
            "The batch event above lists them all."
        )

    print(
        f"Batch {summary['status']}: received={received_count} "
        f"validated={passed_count} harvested={harvest_count} "
        f"not_validated={len(not_validated)} unexpected={len(unexpected)} "
        f"issues={len(issues)}"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")

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
            f"Batch {summary['batch_id']} failed data integrity: "
            + "; ".join(failures)
        )

    # Return only the counts. Airflow echoes the returned value into the
    # task log, so returning the full report would put it in CloudWatch too.
    return {
        "batch_id": summary["batch_id"],
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
