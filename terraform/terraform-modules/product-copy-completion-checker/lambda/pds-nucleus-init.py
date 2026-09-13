"""
============================================================
pds-nucleus-init.py
============================================================

Lambda function to initialize PDS database tables for a single PDS data
source.

Expected event payload:
  { "pds_node_name": "PDS_IMG", "pds_data_source_name": "backlog" }

Creates a dedicated database (pds_nucleus_pds_img_backlog) inside the shared
Aurora cluster and creates any missing tables within it. One database per data
source, so multiple data sources under the same node do not share tables.

This runs again on every deploy: the Terraform aws_lambda_invocation has a
replace_triggered_by on this function, so changing this file re-invokes it.
It is therefore idempotent -- CREATE TABLE IF NOT EXISTS, no drops -- because a
re-deploy must not destroy the in-flight state of a running pipeline.

Pass {"reset_tables": true} to drop and recreate instead. That is destructive
and is never sent by Terraform; it exists for rebuilding a scratch environment.
"""

import logging
import boto3
import os

logger = logging.getLogger("pds-nucleus-init-logger")
rds_data = boto3.client('rds-data')

db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')


def db_name_for_data_source(pds_node_name: str, pds_data_source_name: str) -> str:
    return f"pds_nucleus_{pds_node_name.lower()}_{pds_data_source_name.lower()}"


def lambda_handler(event, context):
    """ Main lambda handler """

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    pds_node_name = event.get('pds_node_name')
    if not pds_node_name:
        raise ValueError("Event must contain 'pds_node_name'")

    pds_data_source_name = event.get('pds_data_source_name')
    if not pds_data_source_name:
        raise ValueError("Event must contain 'pds_data_source_name'")

    db_name = db_name_for_data_source(pds_node_name, pds_data_source_name)
    reset_tables = bool(event.get('reset_tables', False))
    logger.info(f"Initialising database: {db_name} (reset_tables={reset_tables})")

    try:
        create_database(db_name)

        if reset_tables:
            logger.warning(f"reset_tables requested: dropping all tables in {db_name}")
            drop_product_table(db_name)
            drop_datafile_table(db_name)
            drop_product_datafile_mapping_table(db_name)
            drop_product_archive_table(db_name)
            drop_datafile_archive_table(db_name)
            drop_product_datafile_mapping_archive_table(db_name)

        create_product_table(db_name)
        create_datafile_table(db_name)
        create_product_datafile_mapping_table(db_name)
        create_product_archive_table(db_name)
        create_datafile_archive_table(db_name)
        create_product_datafile_mapping_archive_table(db_name)

        return f"Processed lambda request ID: {context.aws_request_id}"
    except Exception as e:
        logger.exception(f"Error initialising database {db_name}. Exception: {str(e)}")
        raise e


def _execute(sql, database=None):
    kwargs = {'resourceArn': db_clust_arn, 'secretArn': db_secret_arn, 'sql': sql}
    if database:
        kwargs['database'] = database
    return rds_data.execute_statement(**kwargs)


def create_database(db_name):
    """ Create the per-node database if it does not already exist """
    # No database= parameter — CREATE DATABASE is a server-level statement
    response = _execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
    logger.debug(f"create_database({db_name}): {str(response)}")


def drop_product_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product;", db_name)
    logger.debug(f"drop_product_table: {str(response)}")


def create_product_table(db_name):
    sql = """
        CREATE TABLE IF NOT EXISTS product
        (
            s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
            completion_status       VARCHAR(50),
            last_updated_epoch_time BIGINT,
            pds_node                VARCHAR(10),
            dispatch_claim          VARCHAR(36) NULL,
            PRIMARY KEY (s3_url_of_product_label),
            INDEX idx_node_status (pds_node, completion_status),
            INDEX idx_dispatch_claim (dispatch_claim)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_product_table: {str(response)}")


def drop_datafile_table(db_name):
    response = _execute("DROP TABLE IF EXISTS data_file;", db_name)
    logger.debug(f"drop_datafile_table: {str(response)}")


def create_datafile_table(db_name):
    sql = """
        CREATE TABLE IF NOT EXISTS data_file
        (
            s3_url_of_data_file               VARCHAR(1000) CHARACTER SET latin1,
            original_s3_url_of_data_file_name VARCHAR(1500) CHARACTER SET latin1,
            last_updated_epoch_time           BIGINT,
            pds_node                          VARCHAR(10),
            PRIMARY KEY (s3_url_of_data_file)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_datafile_table: {str(response)}")


def drop_product_datafile_mapping_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product_data_file_mapping;", db_name)
    logger.debug(f"drop_product_datafile_mapping_table: {str(response)}")


def create_product_datafile_mapping_table(db_name):
    sql = """
        CREATE TABLE IF NOT EXISTS product_data_file_mapping
        (
            s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
            s3_url_of_data_file     VARCHAR(1500) CHARACTER SET latin1,
            last_updated_epoch_time BIGINT,
            pds_node                VARCHAR(10),
            PRIMARY KEY (s3_url_of_product_label, s3_url_of_data_file),
            INDEX idx_data_file (s3_url_of_data_file)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_product_datafile_mapping_table: {str(response)}")


def drop_product_archive_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product_archive;", db_name)
    logger.debug(f"drop_product_archive_table: {str(response)}")


def create_product_archive_table(db_name):
    sql = """
        CREATE TABLE IF NOT EXISTS product_archive
        (
            s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
            completion_status       VARCHAR(50),
            last_updated_epoch_time BIGINT,
            pds_node                VARCHAR(10),
            archived_epoch_time     BIGINT,
            PRIMARY KEY (s3_url_of_product_label),
            INDEX idx_archive_node (pds_node)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_product_archive_table: {str(response)}")


def drop_datafile_archive_table(db_name):
    response = _execute("DROP TABLE IF EXISTS data_file_archive;", db_name)
    logger.debug(f"drop_datafile_archive_table: {str(response)}")


def create_datafile_archive_table(db_name):
    """Archive counterpart of data_file.

    The completion checker's archive step inserts into this table, but nothing
    ever created it, so that step raised on every batch. Its caller treats the
    archive as best-effort and only logs the failure, so the three DELETEs that
    follow the insert never ran and the active tables grew without bound.

    Columns mirror data_file, plus archived_epoch_time, matching the pattern of
    the other two archive tables.
    """
    sql = """
        CREATE TABLE IF NOT EXISTS data_file_archive
        (
            s3_url_of_data_file               VARCHAR(1000) CHARACTER SET latin1,
            original_s3_url_of_data_file_name VARCHAR(1500) CHARACTER SET latin1,
            last_updated_epoch_time           BIGINT,
            pds_node                          VARCHAR(10),
            archived_epoch_time               BIGINT,
            PRIMARY KEY (s3_url_of_data_file)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_datafile_archive_table: {str(response)}")


def drop_product_datafile_mapping_archive_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product_data_file_mapping_archive;", db_name)
    logger.debug(f"drop_product_datafile_mapping_archive_table: {str(response)}")


def create_product_datafile_mapping_archive_table(db_name):
    sql = """
        CREATE TABLE IF NOT EXISTS product_data_file_mapping_archive
        (
            s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
            s3_url_of_data_file     VARCHAR(1500) CHARACTER SET latin1,
            last_updated_epoch_time BIGINT,
            pds_node                VARCHAR(10),
            archived_epoch_time     BIGINT,
            PRIMARY KEY (s3_url_of_product_label, s3_url_of_data_file)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_product_datafile_mapping_archive_table: {str(response)}")
