# This lambda is triggered by an SQS queue which has messages with the paths of files copied to
# EFS. This function updates the Nucleus database tables () (product table, product_data_file_mapping
# table and data_file table) based on the file names received in the SQS messages.

import boto3
import logging
import json
import os
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("pds-nucleus-datasync-completion")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

s3_client = boto3.client('s3')

db_clust_arn  = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
pds_node      = os.environ.get('PDS_NODE_NAME')
db_name       = os.environ.get('DB_NAME')

rds_data = boto3.client('rds-data')

def _process_record(record):
    s3_event = json.loads(record.get("body"))
    logger.info(f"s3_event: {s3_event}")

    if s3_event.get("backlog") == 'true':
        s3_bucket = s3_event.get("s3_bucket")
        s3_key    = s3_event.get("s3_key")
    else:
        s3_bucket = s3_event['Records'][0]["s3"]["bucket"]["name"]
        s3_key    = s3_event['Records'][0]["s3"]["object"]["key"]

    logger.info(f"s3_bucket: {s3_bucket}, s3_key: {s3_key}")
    s3_url_of_file = f"s3://{s3_bucket}/{s3_key}"
    handle_file_types(s3_url_of_file, s3_bucket, s3_key)


def lambda_handler(event, context):
    logger.info(f"event: {event}")
    records = event['Records']

    failures = []
    with ThreadPoolExecutor(max_workers=min(len(records), 20)) as pool:
        futures = {pool.submit(_process_record, r): r['messageId'] for r in records}
        for future, msg_id in futures.items():
            try:
                future.result()
            except Exception as e:
                logger.exception(f"Failed to process message {msg_id}: {e}")
                failures.append({'itemIdentifier': msg_id})

    return {'batchItemFailures': failures}


def handle_file_types(s3_url_of_file, s3_bucket, s3_key):
    """ Invokes functions based on the file type """

    try:
        # TODO:  Product label received (THIS CAN BE LBLX )
        if s3_url_of_file.lower().endswith(".xml") and not s3_url_of_file.lower().endswith(".aux.xml"):
            logger.debug(f"Received product file: {s3_url_of_file}")
            save_product_completion_status_in_database(s3_url_of_file, "INCOMPLETE")
            save_files_for_product_label(s3_url_of_file, s3_bucket, s3_key)

        # Data file received
        elif not s3_url_of_file.lower().endswith("/"):  # Not a directory
            logger.info(f"Received data file: {s3_url_of_file}")
            save_data_file_in_database(s3_url_of_file)

    except Exception as e:
        logger.error(f"Error processing . Exception: {str(e)}")
        raise e


def save_product_data_file_mappings_in_database(s3_url_of_product_label, file_names, s3_base_dir):
    """ Inserts all product-to-data-file mappings in a single batch call """

    if not file_names:
        return

    logger.info(f"Saving {len(file_names)} mappings for {s3_url_of_product_label}")
    sql = """
            INSERT INTO product_data_file_mapping
            (
                s3_url_of_product_label,
                s3_url_of_data_file,
                pds_node,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                :s3_url_of_data_file_param,
                :pds_node_param,
                :last_updated_epoch_time_param
                )
            ON DUPLICATE KEY UPDATE
                last_updated_epoch_time = VALUES(last_updated_epoch_time)
            """

    ts = round(time.time() * 1000)
    param_sets = [
        [
            {'name': 's3_url_of_product_label_param', 'value': {'stringValue': s3_url_of_product_label}},
            {'name': 's3_url_of_data_file_param',     'value': {'stringValue': f"{s3_base_dir}/{fn}"}},
            {'name': 'pds_node_param',                'value': {'stringValue': pds_node}},
            {'name': 'last_updated_epoch_time_param', 'value': {'longValue': ts}},
        ]
        for fn in file_names
    ]

    try:
        rds_data.batch_execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database=db_name,
            sql=sql,
            parameterSets=param_sets)
    except Exception as e:
        logger.exception(f"Error batch-inserting product_data_file_mapping. Exception: {str(e)}")
        raise e


def save_product_completion_status_in_database(s3_url_of_product_label, completion_status):
    """ Creates a product completion status record for product """

    logger.debug(f"Saving product processing status for: {s3_url_of_product_label} in database")

    sql = """
            INSERT INTO product
            (
                s3_url_of_product_label,
                completion_status,
                pds_node,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                :completion_status_param,
                :pds_node_param,
                :last_updated_epoch_time_param
                )
            ON DUPLICATE KEY UPDATE
                last_updated_epoch_time = VALUES(last_updated_epoch_time)
            """

    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}
    completion_status_param = {'name': 'completion_status_param', 'value': {'stringValue': completion_status}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}
    pds_node_param = {'name': 'pds_node_param', 'value': {'stringValue': pds_node}}

    param_set = [s3_url_of_product_label_param, completion_status_param, last_updated_epoch_time_param, pds_node_param]

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database=db_name,
            sql=sql,
            parameters=param_set)
        logger.debug(str(response))

    except Exception as e:
        logger.error(f"Error writing to product table. Exception: {str(e)}")
        raise e


def save_data_file_in_database(s3_url_of_data_file):

    original_s3_url_of_data_file_name = s3_url_of_data_file

    # Handle .fz files
    if s3_url_of_data_file.endswith('.fz'):
        s3_url_of_data_file = s3_url_of_data_file[:-3]

    """ Creates a record for data file """

    logger.debug(f"Saving data file name in database: {s3_url_of_data_file} in database")

    sql = """
            INSERT INTO data_file
            (
                s3_url_of_data_file,
                original_s3_url_of_data_file_name,
                last_updated_epoch_time,
                pds_node)
            VALUES(
                :s3_url_of_data_file_param,
                :original_s3_url_of_data_file_name_param,
                :last_updated_epoch_time_param,
                :pds_node_param
                )
            ON DUPLICATE KEY UPDATE
                last_updated_epoch_time = VALUES(last_updated_epoch_time)
            """

    s3_url_of_data_file_param = {'name': 's3_url_of_data_file_param', 'value': {'stringValue': s3_url_of_data_file}}
    original_s3_url_of_data_file_name_param = {'name': 'original_s3_url_of_data_file_name_param', 'value': {'stringValue': original_s3_url_of_data_file_name}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}
    pds_node_param = {'name': 'pds_node_param', 'value': {'stringValue': pds_node}}

    param_set = [s3_url_of_data_file_param, original_s3_url_of_data_file_name_param, last_updated_epoch_time_param, pds_node_param]

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database=db_name,
            sql=sql,
            parameters=param_set)

        logger.debug(str(response))

    except Exception as e:
        logger.error(f"Error updating data_file table. Exception: {str(e)}")
        raise e


def save_files_for_product_label(s3_url_of_product_label, bucket, key):
    """ Parses the product XML label and batch-inserts all data file mappings """

    s3_base_dir = s3_url_of_product_label.rsplit('/', 1)[0]

    try:
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        content_str = s3_response['Body'].read().decode()

        root = ET.fromstring(content_str)
        file_names = [
            el.text.strip()
            for el in root.iter()
            if el.tag.split('}')[-1] == 'file_name' and el.text and el.text.strip()
        ]

        logger.debug(f"Found {len(file_names)} file references in {s3_url_of_product_label}")
        save_product_data_file_mappings_in_database(s3_url_of_product_label, file_names, s3_base_dir)

    except Exception as e:
        logger.error(f"Error handling missing files for product label: {s3_url_of_product_label}. Exception: {str(e)}")
        raise e
