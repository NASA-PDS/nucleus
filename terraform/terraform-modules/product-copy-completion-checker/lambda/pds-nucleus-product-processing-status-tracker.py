# This lambda is used to store the product processing status in database

import boto3
import logging
import json
import os
import time
from xml.dom import minidom

logger = logging.getLogger("pds-nucleus-datasync-completion")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')

s3_bucket_name = "pds-nucleus-staging"
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')
# pds_node = os.environ.get('PDS_NODE_NAME')

rds_data = boto3.client('rds-data')

def lambda_handler(event, context):

    print(event)

    s3_url_of_product_label_list = event['productsList']
    processing_status = event['processingStatus']
    pds_node = event['pdsNode']
    batch_number = event['batchNumber']

    for s3_url_of_product_label in s3_url_of_product_label_list.split(','):

        print(f'Saving the processing status of {s3_url_of_product_label} as {processing_status}')
        save_product_processing_status_in_database(s3_url_of_product_label, processing_status, pds_node, batch_number)

def save_product_processing_status_in_database(s3_url_of_product_label, processing_status, pds_node, batch_number):
    """ Save processing status for product """

    logger.debug(f"Saving product processing status for: {s3_url_of_product_label} in database")

    sql = """
            REPLACE INTO product_processing_status
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
            """

    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}
    processing_status_param = {'name': 'processing_status_param', 'value': {'stringValue': processing_status}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}
    pds_node_param = {'name': 'pds_node_param', 'value': {'stringValue': pds_node}}
    batch_number_param = {'name': 'batch_number_param', 'value': {'stringValue': batch_number}}

    param_set = [s3_url_of_product_label_param, processing_status_param, last_updated_epoch_time_param, pds_node_param, batch_number_param]

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database='pds_nucleus',
            sql=sql,
            parameters=param_set)
        logger.debug(str(response))

    except Exception as e:
        logger.error(f"Error writing to product_processing_status table. Exception: {str(e)}")
        raise e
