# This lambda stores the product processing status written back by MWAA DAG task callbacks.

import boto3
import logging
import os
import time

logger = logging.getLogger("pds-nucleus-datasync-completion")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

db_clust_arn  = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')

rds_data = boto3.client('rds-data')


def lambda_handler(event, context):

    s3_url_of_product_label_list = event['productsList']
    processing_status = event['processingStatus']
    pds_node          = event['pdsNode']
    batch_number      = event['batchNumber']
    db_name           = f"pds_nucleus_{pds_node.lower()}"

    logger.info(
        f"Processing status update: pdsNode={pds_node}, batchNumber={batch_number}, "
        f"processingStatus={processing_status}, productCount="
        f"{len(s3_url_of_product_label_list) if isinstance(s3_url_of_product_label_list, list) else 'n/a'}"
    )

    if isinstance(s3_url_of_product_label_list, str):
        s3_url_of_product_label_list = s3_url_of_product_label_list.split(',')

    for s3_url_of_product_label in s3_url_of_product_label_list:
        print(f'Saving the processing status of {s3_url_of_product_label} as {processing_status}')
        save_product_processing_status_in_database(
            s3_url_of_product_label, processing_status, pds_node, batch_number, db_name)


def save_product_processing_status_in_database(
        s3_url_of_product_label, processing_status, pds_node, batch_number, db_name):
    """ Save processing status for product """

    logger.debug(f"Saving product processing status for: {s3_url_of_product_label} in database")

    sql = """
            INSERT INTO product_processing_status
            (
                s3_url_of_product_label,
                processing_status,
                pds_node,
                batch_number,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                :processing_status_param,
                :pds_node_param,
                :batch_number_param,
                :last_updated_epoch_time_param
                )
            ON DUPLICATE KEY UPDATE
                processing_status       = VALUES(processing_status),
                batch_number            = VALUES(batch_number),
                last_updated_epoch_time = VALUES(last_updated_epoch_time)
            """

    param_set = [
        {'name': 's3_url_of_product_label_param', 'value': {'stringValue': s3_url_of_product_label}},
        {'name': 'processing_status_param',        'value': {'stringValue': processing_status}},
        {'name': 'pds_node_param',                 'value': {'stringValue': pds_node}},
        {'name': 'batch_number_param',             'value': {'stringValue': batch_number}},
        {'name': 'last_updated_epoch_time_param',  'value': {'longValue': round(time.time() * 1000)}},
    ]

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database=db_name,
            sql=sql,
            parameters=param_set)
        logger.debug(str(response))

    except Exception as e:
        logger.error(f"Error writing to product_processing_status table. Exception: {str(e)}")
        raise e
