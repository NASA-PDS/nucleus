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
import logging
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from botocore.config import Config

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

PRODUCT_BATCH_SIZE = int(os.environ.get("PRODUCT_BATCH_SIZE", "200"))

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

    total_dispatched = 0

    # Keep processing until the queue is drained or 30 s remain on the clock
    while context.get_remaining_time_in_millis() > 30_000:
        products = fetch_completed_products()

        if not products:
            logger.info("No completed products found")
            break

        batch          = generate_batch_name()
        s3_config_dir  = f"{S3_PREFIX}{CONFIG_BUCKET}/dag-data/{batch}"
        efs_config_dir = f"{EFS_MOUNT}/dag-data/{batch}"

        logger.info(f"Preparing batch {batch} ({len(products)} products)")
        mark_products_dispatching(products)

        try:
            prepare_harvest_files(
                batch=batch,
                products=products,
                s3_config_dir=s3_config_dir,
            )
            trigger_airflow(batch, products, s3_config_dir, efs_config_dir)
            mark_products_complete(products)
        except Exception:
            mark_products_incomplete(products)
            raise

        # Archive is best-effort: DAG is already triggered so a failure here
        # must not roll back to INCOMPLETE (that would cause a duplicate DAG run).
        try:
            archive_completed_products(products)
        except Exception as e:
            logger.error(f"Archive step failed for batch {batch}, rows remain in active table: {e}")

        total_dispatched += len(products)

        if len(products) < PRODUCT_BATCH_SIZE:
            break  # fewer than limit → queue is drained

    return {
        "status": "SUCCESS",
        "count": total_dispatched,
    }


# -------------------------------------------------------------------
# DB Logic
# -------------------------------------------------------------------

def fetch_completed_products():
    sql = """
        SELECT DISTINCT p.s3_url_of_product_label
        FROM product p
        WHERE p.completion_status = 'INCOMPLETE'
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
    """

    resp = rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql=sql,
        parameters=[
            {"name": "limit", "value": {"longValue": PRODUCT_BATCH_SIZE}},
        ],
    )

    products = [r[0]["stringValue"] for r in resp.get("records", [])]
    logger.info(f"Completed products found: {len(products)}")
    return products


def _build_url_params(products):
    return [{"name": f"p{i}", "value": {"stringValue": p}} for i, p in enumerate(products)]


def _set_product_status(products, status, with_timestamp=True):
    placeholders = ", ".join(f":p{i}" for i in range(len(products)))
    params = _build_url_params(products)
    if with_timestamp:
        params.append({"name": "ts", "value": {"longValue": int(time.time() * 1000)}})
        set_clause = "completion_status = :status, last_updated_epoch_time = :ts"
    else:
        set_clause = "completion_status = :status"
    params.append({"name": "status", "value": {"stringValue": status}})
    rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql=f"UPDATE product SET {set_clause} WHERE s3_url_of_product_label IN ({placeholders})",
        parameters=params,
    )


def mark_products_complete(products):    _set_product_status(products, 'COMPLETE')
def mark_products_dispatching(products): _set_product_status(products, 'DISPATCHING')
def mark_products_incomplete(products):  _set_product_status(products, 'INCOMPLETE', with_timestamp=False)


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
        # 3. delete active mappings
        f"DELETE FROM product_data_file_mapping WHERE s3_url_of_product_label IN ({placeholders})",
        # 4. delete active product rows last
        f"DELETE FROM product WHERE s3_url_of_product_label IN ({placeholders})",
    ]

    for sql in steps:
        rds.execute_statement(
            resourceArn=DB_CLUSTER_ARN,
            secretArn=DB_SECRET_ARN,
            database=DB_NAME,
            sql=sql,
            parameters=params,
        )

    logger.info(f"Archived {len(products)} completed products")


# -------------------------------------------------------------------
# Harvest File Preparation (S3 ONLY)
# -------------------------------------------------------------------

def _build_harvest_cfg(batch):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<harvest>
  <registry auth="/etc/es-auth.cfg">file:///mnt/data/dag-data/{batch}/connection.xml</registry>

  <load>
    <files>
      <manifest>/mnt/data/dag-data/{batch}/harvest_manifest.txt</manifest>
    </files>
  </load>

  <fileInfo>
    <fileRef replacePrefix="/mnt/data/pds-sbn-staging-dev"
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
    # Phase 1: static files and DB fetches run fully in parallel
    with ThreadPoolExecutor(max_workers=min(12, len(products) + 2)) as pool:
        f_cfg  = pool.submit(upload_text, s3_config_dir, "harvest.cfg",   _build_harvest_cfg(batch))
        f_conn = pool.submit(upload_text, s3_config_dir, "connection.xml", _build_connection_xml())
        data_futures = {pool.submit(fetch_data_files, p): p for p in products}
        data_files_by_product = {data_futures[f]: f.result() for f in as_completed(data_futures)}
        f_cfg.result()
        f_conn.result()

    # Phase 2: assemble content that depends on DB results, upload in parallel
    manifest  = "\n".join(s3_to_efs_path(p) for p in products) + "\n"
    all_files = [url for p in products for url in [p] + data_files_by_product[p]]

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_manifest = pool.submit(upload_text, s3_config_dir, "harvest_manifest.txt", manifest)
        f_list     = pool.submit(upload_text, s3_config_dir, "data_file_list.txt",   "\n".join(all_files))
        f_manifest.result()
        f_list.result()


def fetch_data_files(product_label):
    sql = """
        SELECT df.original_s3_url_of_data_file_name
        FROM product_data_file_mapping m
        JOIN data_file df
          ON df.s3_url_of_data_file = m.s3_url_of_data_file
        WHERE m.s3_url_of_product_label = :p
    """

    resp = rds.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        database=DB_NAME,
        sql=sql,
        parameters=[{"name": "p", "value": {"stringValue": product_label}}],
    )

    return [r[0]["stringValue"] for r in resp.get("records", [])]


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

def trigger_airflow(batch, products, s3_config_dir, efs_config_dir):
    payload = {
        "batch_number": batch,
        "pds_node_name": PDS_NODE,
        "s3_config_dir": s3_config_dir,
        "efs_config_dir": efs_config_dir,
        "pds_hot_archive_bucket_name": HOT_ARCHIVE_BUCKET,
        "list_of_product_labels_to_process": [
            s3_to_efs_path(p) for p in products
        ],
    }

    logger.info(f"Triggering DAG {DAG_NAME} batch={batch}")

    token = mwaa.create_cli_token(Name=MWAA_ENV_NAME)
    conn = http.client.HTTPSConnection(token["WebServerHostname"], timeout=10)

    conf = json.dumps(payload).replace('"', '\\"')
    cmd = f'{MWAA_CMD} {DAG_NAME} -c "{conf}"'

    try:
        conn.request(
            "POST",
            "/aws_mwaa/cli/",
            cmd,
            headers={
                "Authorization": f"Bearer {token['CliToken']}",
                "Content-Type": "text/plain",
            },
        )

        resp = conn.getresponse()
        body = base64.b64decode(resp.read()).decode("utf-8", errors="replace")

        logger.info(f"MWAA status={resp.status}")
        logger.debug(body)

        if resp.status >= 300 or "Error" in body or "Traceback" in body:
            raise RuntimeError(f"MWAA trigger failed: status={resp.status} body={body}")

    finally:
        conn.close()