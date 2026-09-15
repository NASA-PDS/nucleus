"""
============================================================
pds-nucleus-product-completion-checker.py
(Airflow 3 / MWAA compatible)
============================================================
"""
import os
import json
import time
import uuid
import http.client
import base64
import binascii
import logging
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from botocore.config import Config
from socket import timeout as socket_timeout

# -------------------------------------------------------------------
# AWS Clients
# -------------------------------------------------------------------

# Boto2 client configs with different timeout settings
fast_cfg = Config(connect_timeout=2, read_timeout=5, retries={'mode': 'standard'})
std_cfg  = Config(connect_timeout=5, read_timeout=15, retries={'mode': 'standard'})
heavy_cfg = Config(connect_timeout=5, read_timeout=50, retries={'mode': 'standard'})

# Boto2 clients with suitable configs
sts = boto3.client('sts', config=fast_cfg)
mwaa = boto3.client('mwaa', config=fast_cfg)
s3 = boto3.client('s3', config=std_cfg)
rds = boto3.client('rds-data', config=heavy_cfg)


# -------------------------------------------------------------------
# Logger
# -------------------------------------------------------------------
logger = logging.getLogger("pds-nucleus-product-completion-checker")
logger.setLevel(getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO))
logger.propagate = False
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


# -------------------------------------------------------------------
# Env Vars
# -------------------------------------------------------------------
DAG_NAME = os.environ["AIRFLOW_DAG_NAME"]
PDS_NODE = os.environ["PDS_NODE_NAME"]
PDS_DATA_SOURCE = os.environ["PDS_DATA_SOURCE_NAME"]
DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ["DB_NAME"]
MWAA_ENV_NAME = os.environ["PDS_MWAA_ENV_NAME"]
CONFIG_BUCKET = os.environ["PDS_NUCLEUS_CONFIG_BUCKET_NAME"]
HOT_ARCHIVE_BUCKET = os.environ["PDS_HOT_ARCHIVE_S3_BUCKET_NAME"]

OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
OPENSEARCH_REGISTRY = os.environ["OPENSEARCH_REGISTRY_NAME"]
OPENSEARCH_CRED_URL = os.environ["OPENSEARCH_CREDENTIAL_RELATIVE_URL"]
REPLACE_PREFIX_WITH = os.environ["REPLACE_PREFIX_WITH"]
HARVEST_REPLACE_PREFIX = os.environ["HARVEST_REPLACE_PREFIX"]

# Owned here, not hardcoded in the DAG template: passed through to Airflow via
# trigger_airflow()'s payload so the DAG's registry check uses the same,
# Terraform-configured prefix rather than duplicating it as a DAG constant.
PDS_REGISTRY_SEARCH_URL_PREFIX = os.environ["PDS_REGISTRY_SEARCH_URL_PREFIX"]

PRODUCT_BATCH_SIZE = int(os.environ.get("PRODUCT_BATCH_SIZE", "500"))

# Delay between successive batch dispatches within one invocation's drain
# loop (lambda_handler), so a large backlog doesn't fire DAG triggers (and
# the ECS task-launch/poll traffic each one starts) back-to-back with no
# pacing at all.
DRAIN_LOOP_PACING_SECONDS = float(os.environ.get("DRAIN_LOOP_PACING_SECONDS", "1"))

# fetch_data_files() looks up data files with one query per chunk instead of
# one per product. A 500-product IN clause is only ~95 KB at realistic PDS
# URL lengths (comfortably under the Data API's request size limit), but
# chunking bounds how large a single query gets if PRODUCT_BATCH_SIZE grows.
DATA_FILE_QUERY_CHUNK_SIZE = 200

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
S3_PREFIX = "s3://"
EFS_MOUNT = "/mnt/data"
MWAA_CMD = "dags trigger"

# -------------------------------------------------------------------
# Global Vars
# -------------------------------------------------------------------
expected_bucket_owner = None

try:
    expected_bucket_owner = sts.get_caller_identity()["Account"]
except ClientError as e:
    logger.error(f"Critical: Failed to retrieve AWS Account ID from STS: {e}")
    raise e
except Exception as e:
    logger.error(f"Unexpected error during initialization: {e}")
    raise e


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def generate_batch_name() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    return f"{ts}{uuid.uuid4().hex}"


def s3_to_efs_path(s3_url: str) -> str:
    """
    s3://pds-sbn-staging-dev/sbn/999/file.xml
    -> /mnt/data/pds-sbn-staging-dev/sbn/999/file.xml
    """
    return s3_url.replace(S3_PREFIX, f"{EFS_MOUNT}/", 1)


# -------------------------------------------------------------------
# Lambda Handler
# -------------------------------------------------------------------

def lambda_handler(event, context):
    logger.info(f"Lambda Request ID: {context.aws_request_id}")
    logger.info(f"PDS_NODE_NAME: {PDS_NODE}")

    reset_stale_dispatching()
    total_dispatched = 0

    # Keep processing until the queue is drained or 30 s remain on the clock
    while context.get_remaining_time_in_millis() > 30_000:
        claim_id = str(uuid.uuid4())
        products = claim_completed_products(claim_id)

        if not products:
            logger.info("No completed products found")
            break

        batch          = generate_batch_name()
        # CONFIG_BUCKET is shared per node (not per data source) to keep the original IAM S3
        # resource pattern intact, so data sources are isolated by key prefix instead.
        s3_config_dir  = f"{S3_PREFIX}{CONFIG_BUCKET}/dag-data/{PDS_DATA_SOURCE}/{batch}"
        efs_config_dir = f"{EFS_MOUNT}/dag-data/{PDS_DATA_SOURCE}/{batch}"

        logger.info(f"Preparing batch {batch} ({len(products)} products) claim={claim_id}")

        try:
            prepare_harvest_files(
                batch=batch,
                products=products,
                s3_config_dir=s3_config_dir,
            )
            trigger_airflow(batch, s3_config_dir, efs_config_dir)
            mark_products_complete(products)
        except Exception:
            mark_products_incomplete(products)
            raise

        # Archive is best-effort: DAG is already triggered so a failure here
        # must not roll back to INCOMPLETE (that would cause a duplicate DAG run).
        try:
            archive_completed_products(products)
        except Exception as e:
            logger.exception(f"Archive step failed for batch {batch}, rows remain in active table: {e}")

        total_dispatched += len(products)

        if len(products) < PRODUCT_BATCH_SIZE:
            break  # fewer than limit → queue is drained

        # Pace successive DAG triggers. An unpaced drain loop fires
        # trigger_airflow() as fast as it can loop -- fine for a handful of
        # batches, but against a large backlog it's what drove ECS
        # DescribeTasks (and, per the same throttle-error handling just
        # added to trigger_airflow, potentially MWAA's own trigger API)
        # past their account-level rate limits.
        time.sleep(DRAIN_LOOP_PACING_SECONDS)

    return {
        "status": "SUCCESS",
        "count": total_dispatched,
    }


# -------------------------------------------------------------------
# DB Logic
# -------------------------------------------------------------------

DISPATCHING_TIMEOUT_MS = 30 * 60 * 1000  # 30 minutes


def reset_stale_dispatching():
    """Reset products stuck in DISPATCHING (e.g. from a crashed invocation) back to INCOMPLETE."""
    threshold = int(time.time() * 1000) - DISPATCHING_TIMEOUT_MS
    resp = rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql="""
            UPDATE product
            SET completion_status = 'INCOMPLETE', dispatch_claim = NULL
            WHERE pds_node = :node
              AND completion_status = 'DISPATCHING'
              AND last_updated_epoch_time < :threshold
        """,
        parameters=[
            {"name": "node", "value": {"stringValue": PDS_NODE}},
            {"name": "threshold", "value": {"longValue": threshold}},
        ],
    )
    count = resp.get("numberOfRecordsUpdated", 0)
    if count:
        logger.warning(f"Reset {count} stale DISPATCHING products to INCOMPLETE")


def claim_completed_products(claim_id: str) -> list:
    """
    Atomically mark eligible INCOMPLETE products as DISPATCHING under claim_id,
    then return their URLs. Two concurrent invocations get disjoint sets because
    MySQL serialises the UPDATE on the completion_status='INCOMPLETE' predicate.

    The pds_node predicate is what makes this an index seek rather than a full
    table scan. The only index covering completion_status is idx_node_status
    (pds_node, completion_status), and MySQL cannot use a composite index whose
    leading column is absent from the WHERE clause. Every row in this database
    belongs to PDS_NODE already -- one database per data source -- so the
    predicate selects nothing different, it just lets the planner reach the index.
    """
    rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql="""
            UPDATE product p
            SET p.completion_status = 'DISPATCHING',
                p.dispatch_claim = :claim,
                p.last_updated_epoch_time = :ts
            WHERE p.pds_node = :node
              AND p.completion_status = 'INCOMPLETE'
              AND EXISTS (
                  SELECT 1 FROM product_data_file_mapping m
                  WHERE m.s3_url_of_product_label = p.s3_url_of_product_label
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM product_data_file_mapping m
                  LEFT JOIN data_file df
                    ON df.s3_url_of_data_file = m.s3_url_of_data_file
                  WHERE m.s3_url_of_product_label = p.s3_url_of_product_label
                    AND df.s3_url_of_data_file IS NULL
              )
            LIMIT :limit
        """,
        parameters=[
            {"name": "node",  "value": {"stringValue": PDS_NODE}},
            {"name": "claim", "value": {"stringValue": claim_id}},
            {"name": "ts",    "value": {"longValue": int(time.time() * 1000)}},
            {"name": "limit", "value": {"longValue": PRODUCT_BATCH_SIZE}},
        ],
    )

    resp = rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql="SELECT s3_url_of_product_label FROM product WHERE dispatch_claim = :claim AND completion_status = 'DISPATCHING'",
        parameters=[{"name": "claim", "value": {"stringValue": claim_id}}],
    )

    products = [r[0]["stringValue"] for r in resp.get("records", [])]
    logger.info(f"Claimed {len(products)} products with claim_id={claim_id}")
    return products


def _build_url_params(products):
    return [{"name": f"p{i}", "value": {"stringValue": p}} for i, p in enumerate(products)]


def _set_product_status(products, status, with_timestamp=True, clear_claim=False):
    placeholders = ", ".join(f":p{i}" for i in range(len(products)))
    params = _build_url_params(products)
    set_parts = ["completion_status = :status"]
    if with_timestamp:
        params.append({"name": "ts", "value": {"longValue": int(time.time() * 1000)}})
        set_parts.append("last_updated_epoch_time = :ts")
    if clear_claim:
        set_parts.append("dispatch_claim = NULL")
    params.append({"name": "status", "value": {"stringValue": status}})
    rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql=f"UPDATE product SET {', '.join(set_parts)} WHERE s3_url_of_product_label IN ({placeholders})",
        parameters=params,
    )


def mark_products_complete(products):
    _set_product_status(products, 'COMPLETE')
    _upsert_tracking_sent_to_nucleus(products)


def mark_products_incomplete(products):
    # No product_tracking write here: there is no clean SENT_TO_NUCLEUS-
    # equivalent stage for "dispatch attempt failed" -- the row just stays
    # at whatever stage it already reached (typically still RECEIVED,
    # since this path runs before a product has ever been dispatched
    # successfully), which is already the correct state to leave it in.
    _set_product_status(products, 'INCOMPLETE', with_timestamp=False, clear_claim=True)


def _upsert_tracking_sent_to_nucleus(products):
    """Advance product_tracking.status to SENT_TO_NUCLEUS for a successfully
    dispatched batch, alongside the existing write to product above.

    Always overwritten on duplicate -- unlike RECEIVED (set once, at file
    arrival, and never regressed after), reaching this function means a
    real dispatch just happened, so SENT_TO_NUCLEUS is correct to write
    even if the product had already been dispatched before (e.g. a
    reprocessed/re-harvested product legitimately re-enters the pipeline).

    One parameter set per product via batch_execute_statement (a multi-row
    insert, not an IN-clause update, since each row's s3 url differs) --
    same pattern as save_product_data_file_mappings_in_database in the
    sibling s3-file-event-processor Lambda.
    """
    if not products:
        return

    sql = """
            INSERT INTO product_tracking
            (
                s3_url_of_product_label,
                status,
                pds_node,
                first_seen_epoch_time,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                'SENT_TO_NUCLEUS',
                :pds_node_param,
                :first_seen_epoch_time_param,
                :last_updated_epoch_time_param
                )
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                last_updated_epoch_time = VALUES(last_updated_epoch_time)
            """

    ts = int(time.time() * 1000)
    param_sets = [
        [
            {"name": "s3_url_of_product_label_param", "value": {"stringValue": p}},
            {"name": "pds_node_param",                  "value": {"stringValue": PDS_NODE}},
            {"name": "first_seen_epoch_time_param",     "value": {"longValue": ts}},
            {"name": "last_updated_epoch_time_param",   "value": {"longValue": ts}},
        ]
        for p in products
    ]

    try:
        rds.batch_execute_statement(
            resourceArn=DB_CLUSTER_ARN,
            secretArn=DB_SECRET_ARN,
            database=DB_NAME,
            sql=sql,
            parameterSets=param_sets,
        )
    except Exception as e:
        logger.exception(f"Error upserting product_tracking status. Exception: {str(e)}")
        raise e


def archive_completed_products(products):
    """
    Move COMPLETE product rows and their mappings out of the active tables into
    archive tables so the completion checker always scans a small hot set.

    Order: INSERT (idempotent with IGNORE) before DELETE, mappings before product,
    so a crash at any point leaves data in at least one table.
    """
    placeholders = ", ".join(f":p{i}" for i in range(len(products)))
    params = _build_url_params(products)
    params.append({"name": "ts", "value": {"longValue": int(time.time() * 1000)}})

    steps = [
        # 1. archive product rows
        f"""
            INSERT IGNORE INTO product_archive
                (s3_url_of_product_label, completion_status, last_updated_epoch_time,
                 pds_node, archived_epoch_time)
            SELECT s3_url_of_product_label, completion_status, last_updated_epoch_time,
                   pds_node, :ts
            FROM product
            WHERE s3_url_of_product_label IN ({placeholders})
        """,
        # 2. archive mapping rows
        f"""
            INSERT IGNORE INTO product_data_file_mapping_archive
                (s3_url_of_product_label, s3_url_of_data_file, last_updated_epoch_time,
                 pds_node, archived_epoch_time)
            SELECT s3_url_of_product_label, s3_url_of_data_file, last_updated_epoch_time,
                   pds_node, :ts
            FROM product_data_file_mapping
            WHERE s3_url_of_product_label IN ({placeholders})
        """,
        # 3. archive data_file rows referenced by these products
        f"""
            INSERT IGNORE INTO data_file_archive
                (s3_url_of_data_file, original_s3_url_of_data_file_name,
                 last_updated_epoch_time, pds_node, archived_epoch_time)
            SELECT DISTINCT df.s3_url_of_data_file, df.original_s3_url_of_data_file_name,
                   df.last_updated_epoch_time, df.pds_node, :ts
            FROM data_file df
            WHERE df.s3_url_of_data_file IN (
                SELECT DISTINCT m.s3_url_of_data_file
                FROM product_data_file_mapping m
                WHERE m.s3_url_of_product_label IN ({placeholders})
            )
        """,
        # 4. delete active mappings
        f"DELETE FROM product_data_file_mapping WHERE s3_url_of_product_label IN ({placeholders})",
        # 5. delete orphaned data_file rows -- but only if no OTHER, still-
        # active product also maps to it. Step 4 already removed this
        # batch's own mappings above, so anything still in
        # product_data_file_mapping at this point belongs to a different,
        # not-yet-archived product. Without this guard, a data file shared
        # between two products gets deleted the moment the first product is
        # archived, permanently stranding the second: its NOT EXISTS check
        # in claim_completed_products() would find that data_file missing
        # forever, even though the file genuinely exists in S3.
        f"""
            DELETE FROM data_file
            WHERE s3_url_of_data_file IN (
                SELECT DISTINCT m.s3_url_of_data_file
                FROM product_data_file_mapping_archive m
                WHERE m.s3_url_of_product_label IN ({placeholders})
            )
            AND NOT EXISTS (
                SELECT 1 FROM product_data_file_mapping m2
                WHERE m2.s3_url_of_data_file = data_file.s3_url_of_data_file
            )
        """,
        # 6. delete active product rows last
        f"DELETE FROM product WHERE s3_url_of_product_label IN ({placeholders})",
    ]

    deleted_products = None
    deleted_data_files = None
    for i, sql in enumerate(steps):
        resp = rds.execute_statement(
            resourceArn=DB_CLUSTER_ARN,
            secretArn=DB_SECRET_ARN,
            database=DB_NAME,
            sql=sql,
            parameters=params,
        )
        if i == 4:  # DELETE FROM data_file
            deleted_data_files = resp.get("numberOfRecordsUpdated")
        elif i == 5:  # DELETE FROM product
            deleted_products = resp.get("numberOfRecordsUpdated")

    if deleted_products != len(products):
        logger.warning(
            f"Archive count mismatch: claimed {len(products)} products but "
            f"deleted {deleted_products} rows from 'product' table"
        )

    logger.info(f"Archived {len(products)} completed products and {deleted_data_files} data files")


# -------------------------------------------------------------------
# Harvest File Preparation (S3 ONLY)
# -------------------------------------------------------------------

def _build_harvest_cfg(batch):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<harvest>
  <registry auth="/etc/es-auth.cfg">file:///mnt/data/dag-data/{PDS_DATA_SOURCE}/{batch}/connection.xml</registry>

  <load>
    <files>
      <manifest>/mnt/data/dag-data/{PDS_DATA_SOURCE}/{batch}/harvest_manifest.txt</manifest>
    </files>
  </load>

  <fileInfo>
    <fileRef replacePrefix="{HARVEST_REPLACE_PREFIX}"
             with="{REPLACE_PREFIX_WITH}" />
  </fileInfo>
</harvest>
"""


def _build_connection_xml():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<registry_connection index="{OPENSEARCH_REGISTRY}">
  <ec2_credential_url endpoint="{OPENSEARCH_ENDPOINT}">{OPENSEARCH_CRED_URL}</ec2_credential_url>
</registry_connection>
"""


def prepare_harvest_files(batch, products, s3_config_dir):
    chunks = [
        products[i : i + DATA_FILE_QUERY_CHUNK_SIZE]
        for i in range(0, len(products), DATA_FILE_QUERY_CHUNK_SIZE)
    ]

    # Phase 1: static files and DB fetches run fully in parallel
    with ThreadPoolExecutor(max_workers=min(12, len(chunks) + 2)) as pool:
        f_cfg  = pool.submit(upload_text, s3_config_dir, "harvest.cfg",   _build_harvest_cfg(batch))
        f_conn = pool.submit(upload_text, s3_config_dir, "connection.xml", _build_connection_xml())
        data_futures = [pool.submit(fetch_data_files, chunk) for chunk in chunks]
        try:
            data_files_by_product = {}
            for f in as_completed(data_futures):
                data_files_by_product.update(f.result())
        finally:
            # Always surface upload errors even if a DB fetch failed first
            f_cfg.result()
            f_conn.result()

    # Phase 2: assemble content that depends on DB results, upload in parallel
    manifest     = "\n".join(s3_to_efs_path(p) for p in products) + "\n"
    all_files    = [url for p in products for url in [p] + data_files_by_product[p]]
    product_list = "\n".join(products) + "\n"

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_manifest = pool.submit(upload_text, s3_config_dir, "harvest_manifest.txt", manifest)
        f_list     = pool.submit(upload_text, s3_config_dir, "data_file_list.txt",   "\n".join(all_files) + "\n")
        f_products = pool.submit(upload_text, s3_config_dir, "product_list.txt",     product_list)
        f_manifest.result()
        f_list.result()
        f_products.result()


def fetch_data_files(product_labels):
    """Look up data files for a chunk of products in a single query.

    One round trip per chunk instead of one per product: at 500 products
    and DATA_FILE_QUERY_CHUNK_SIZE=200 that's 3 RDS Data API calls instead
    of 500, which was the dominant cost of preparing a large batch.
    """
    if not product_labels:
        return {}

    placeholders = ", ".join(f":p{i}" for i in range(len(product_labels)))
    sql = f"""
        SELECT m.s3_url_of_product_label, df.original_s3_url_of_data_file_name
        FROM product_data_file_mapping m
        JOIN data_file df
          ON df.s3_url_of_data_file = m.s3_url_of_data_file
        WHERE m.s3_url_of_product_label IN ({placeholders})
    """
    parameters = [
        {"name": f"p{i}", "value": {"stringValue": label}}
        for i, label in enumerate(product_labels)
    ]

    resp = rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql=sql,
        parameters=parameters,
    )

    # Every product in the chunk gets an entry, even with no data files, so
    # callers can index this dict by product label the same way they could
    # index the old per-product list result.
    files_by_product = {label: [] for label in product_labels}
    for record in resp.get("records", []):
        files_by_product[record[0]["stringValue"]].append(record[1]["stringValue"])
    return files_by_product


def upload_text(s3_dir, name, content):
    bucket = s3_dir.replace(S3_PREFIX, "").split("/")[0]
    key = "/".join(s3_dir.replace(S3_PREFIX, "").split("/")[1:] + [name])

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ExpectedBucketOwner=expected_bucket_owner,
    )


# -------------------------------------------------------------------
# MWAA Trigger
# -------------------------------------------------------------------

_THROTTLING_ERROR_CODES = {
    "ThrottlingException",
    "Throttling",
    "TooManyRequestsException",
    "RequestLimitExceeded",
    "ProvisionedThroughputExceededException",
}


def _is_throttling_error(client_error: ClientError) -> bool:
    return client_error.response.get("Error", {}).get("Code") in _THROTTLING_ERROR_CODES


def _decode_mwaa_cli_response(raw):
    """
    Decodes an MWAA CLI response body (JSON envelope with base64-encoded
    stdout/stderr), falling back to plain text if it isn't that envelope.
    """
    try:
        resp_json = json.loads(raw)
        stdout = base64.b64decode(resp_json.get("stdout", "")).decode("utf-8", errors="replace")
        stderr = base64.b64decode(resp_json.get("stderr", "")).decode("utf-8", errors="replace")
        return stdout + stderr
    except (json.JSONDecodeError, binascii.Error):
        return raw.decode("utf-8", errors="replace")


# MWAA CLI tokens are valid for 60 seconds (AWS-documented). Cached and
# reused across batches within one invocation instead of refetched per
# batch -- the drain loop below can dispatch dozens of batches per
# invocation, and CreateCliToken is a control-plane API call with its own
# throttle limit, the same class of problem as the ECS DescribeTasks
# throttling this pipeline hit under burst load.
_MWAA_TOKEN_TTL_SECONDS = 60
_MWAA_TOKEN_REFRESH_MARGIN_SECONDS = 10
_mwaa_token_cache = {"host": None, "token": None, "expires_at": 0.0}


def _get_mwaa_cli_token():
    now = time.monotonic()
    if now < _mwaa_token_cache["expires_at"]:
        return _mwaa_token_cache["host"], _mwaa_token_cache["token"]

    response = mwaa.create_cli_token(Name=MWAA_ENV_NAME)
    _mwaa_token_cache["host"] = response["WebServerHostname"]
    _mwaa_token_cache["token"] = response["CliToken"]
    _mwaa_token_cache["expires_at"] = now + _MWAA_TOKEN_TTL_SECONDS - _MWAA_TOKEN_REFRESH_MARGIN_SECONDS
    return _mwaa_token_cache["host"], _mwaa_token_cache["token"]


def _invalidate_mwaa_cli_token():
    _mwaa_token_cache["expires_at"] = 0.0


def _trigger_airflow_once(run_id, cmd):
    """
    Makes one MWAA CLI trigger attempt. Returns once the DAG run is
    triggered (or already existed); raises otherwise, including for a
    non-2xx/error response, so the caller's retry loop can decide whether
    that's transient (network) or terminal (bad response).
    """
    host, cli_token = _get_mwaa_cli_token()
    conn = http.client.HTTPSConnection(host, timeout=30)
    try:
        conn.request(
            "POST",
            "/aws_mwaa/cli/",
            cmd,
            headers={
                "Authorization": f"Bearer {cli_token}",
                "Content-Type": "text/plain",
            },
        )

        resp = conn.getresponse()
        body = _decode_mwaa_cli_response(resp.read())

        logger.info(f"MWAA status={resp.status}")
        logger.debug(body)

        # A prior attempt for this exact run_id may have already succeeded
        # server-side even though that attempt raised (e.g. response timeout).
        # Treat "already exists" as confirmation of success, not a failure.
        if "already exists" in body.lower():
            logger.info(f"DAG run {run_id} already exists — treating as already triggered")
            return

        if resp.status >= 300 or "Error" in body or "Traceback" in body:
            raise RuntimeError(f"MWAA trigger failed: status={resp.status} body={body}")
    finally:
        conn.close()


def trigger_airflow(batch, s3_config_dir, efs_config_dir):
    payload = {
        "batch_number": batch,
        "pds_node_name": PDS_NODE,
        "s3_config_dir": s3_config_dir,
        "efs_config_dir": efs_config_dir,
        "pds_hot_archive_bucket_name": HOT_ARCHIVE_BUCKET,
        "registry_search_url_prefix": PDS_REGISTRY_SEARCH_URL_PREFIX,
    }

    # batch is already a globally-unique name; using it as the Airflow run_id
    # makes triggering idempotent — if a retry occurs after an ambiguous
    # failure (e.g. response timeout after MWAA already started the run),
    # MWAA rejects the duplicate trigger instead of starting a second DAG run.
    run_id = f"batch__{batch}"

    logger.info(f"Triggering DAG {DAG_NAME} batch={batch} run_id={run_id}")

    conf = json.dumps(payload).replace('"', '\\"')
    cmd = f'{MWAA_CMD} {DAG_NAME} -r "{run_id}" -c "{conf}"'

    # Retry with exponential backoff for transient failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            _trigger_airflow_once(run_id, cmd)
            return
        except (socket_timeout, TimeoutError, ConnectionError, ClientError) as e:
            # A ClientError that isn't throttling (e.g. a permissions error)
            # won't be fixed by retrying -- fail fast the same as any other
            # non-retryable error below.
            if isinstance(e, ClientError) and not _is_throttling_error(e):
                logger.exception("MWAA trigger failed (non-retryable)")
                raise
            _invalidate_mwaa_cli_token()
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                logger.warning(f"MWAA trigger attempt {attempt + 1} failed transiently: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.exception(f"MWAA trigger failed after {max_retries} attempts")
                raise
        except Exception:
            logger.exception("MWAA trigger failed (non-retryable)")
            raise