"""
============================================================
pds-nucleus-init.py
============================================================

Lambda function to initialize PDS database tables for a single PDS node.

Expected event payload:
  { "pds_node_name": "PDS_IMG" }

Creates a dedicated database (pds_nucleus_pds_img) inside the shared Aurora
cluster, then drops and recreates all tables within it.
"""

import logging
import boto3
import os

logger = logging.getLogger("pds-nucleus-init-logger")
rds_data = boto3.client('rds-data')

db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')


def db_name_for_node(pds_node_name: str) -> str:
    return f"pds_nucleus_{pds_node_name.lower()}"


def lambda_handler(event, context):
    """ Main lambda handler """

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    pds_node_name = event.get('pds_node_name')
    if not pds_node_name:
        raise ValueError("Event must contain 'pds_node_name'")

    db_name = db_name_for_node(pds_node_name)
    logger.info(f"Initialising database: {db_name}")

    try:
        create_database(db_name)

        drop_product_table(db_name)
        drop_datafile_table(db_name)
        drop_product_datafile_mapping_table(db_name)
        drop_product_processing_status_table(db_name)
        drop_product_archive_table(db_name)
        drop_product_datafile_mapping_archive_table(db_name)

        create_product_table(db_name)
        create_datafile_table(db_name)
        create_product_datafile_mapping_table(db_name)
        create_product_processing_status_table(db_name)
        create_product_archive_table(db_name)
        create_product_datafile_mapping_archive_table(db_name)

        return f"Processed lambda request ID: {context.aws_request_id}"
    except Exception as e:
        logger.error(f"Error initialising database {db_name}. Exception: {str(e)}")
        raise e


def _execute(sql, database=None):
    kwargs = dict(resourceArn=db_clust_arn, secretArn=db_secret_arn, sql=sql)
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
        CREATE TABLE product
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
        CREATE TABLE data_file
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
        CREATE TABLE product_data_file_mapping
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


def drop_product_processing_status_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product_processing_status;", db_name)
    logger.debug(f"drop_product_processing_status_table: {str(response)}")


def create_product_processing_status_table(db_name):
    sql = """
        CREATE TABLE product_processing_status
        (
            s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
            processing_status       VARCHAR(50),
            last_updated_epoch_time BIGINT,
            pds_node                VARCHAR(10),
            batch_number            VARCHAR(100),
            PRIMARY KEY (s3_url_of_product_label)
        );
    """
    response = _execute(sql, db_name)
    logger.debug(f"create_product_processing_status_table: {str(response)}")


def drop_product_archive_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product_archive;", db_name)
    logger.debug(f"drop_product_archive_table: {str(response)}")


def create_product_archive_table(db_name):
    sql = """
        CREATE TABLE product_archive
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


def drop_product_datafile_mapping_archive_table(db_name):
    response = _execute("DROP TABLE IF EXISTS product_data_file_mapping_archive;", db_name)
    logger.debug(f"drop_product_datafile_mapping_archive_table: {str(response)}")


def create_product_datafile_mapping_archive_table(db_name):
    sql = """
        CREATE TABLE product_data_file_mapping_archive
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
