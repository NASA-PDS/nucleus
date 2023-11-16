"""
=========================================
pds-nucleus-product-writer.py
=========================================

Lambda function to copy files from PDS Nucleus S3 staging bucket to an EFS volume and also update
the PDS_Nucleus database to keep track of received files.
This lambda function is triggered by pds-nucleus-s3-event-lambda-invoker lambda function when a
new file (other than a .fz file) is copied to the staging S3 bucket.
"""

import json
import urllib.parse
import logging
import shutil
import boto3
import os
import time
from xml.dom import minidom

s3 = boto3.client('s3')
logger = logging.getLogger("pds-nucleus-product-writer-logger")
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')

node_name = 'PDS_ENG'
es_url = 'https://search-pds-mcp-dev-w2hvvbz4afns4vn6owmge5275u.us-west-2.es.amazonaws.com:443'
es_auth_file = '/mnt/data/configs/es-auth.cfg'
replace_prefix = '/mnt/data/'
replace_prefix_with = 'http://localhost:81/archive'

rds_data = boto3.client('rds-data')

# Main lambda handler
def lambda_handler(event, context):

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    s3_url_of_data_file = "s3://" + bucket + "/" + key
    s3_url_of_product_label = "s3://" + bucket + "/" + key

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    try:

        # TODO:  Product label received (THIS CAN BE LBLX )
        if s3_url_of_data_file.lower().endswith(".xml") and not s3_url_of_data_file.lower().endswith(".aux.xml"):
            logger.info(f"Received product file: {s3_url_of_data_file}" )
            copy_file_to_efs(bucket, key, efs_mount_path)
            # create_harvest_config_xml(bucket, key, efs_mount_path)
            save_product_processing_status_in_database(s3_url_of_product_label, "INCOMPLETE")
            save_files_for_product_label(s3_url_of_product_label, bucket, key)

        # Data file received
        elif not s3_url_of_data_file.lower().endswith("/"): # Not a directory
            logger.info(f"Received data file: {s3_url_of_data_file}" )
            copy_file_to_efs(bucket, key, efs_mount_path)
            save_data_file_in_database(s3_url_of_data_file)

        return f"Event for s3://{bucket}/{key} processed."
    except Exception as e:
        logger.error(f"Error processing S3 event: {event}. Exception: {str(e)}")
        raise e


# Creates a mapping record in the database for product and relevant files
def save_product_data_file_mapping_in_database(s3_url_of_product_label, s3_url_of_data_file):

    logger.info(f'Save product data file mapping {s3_url_of_product_label} --> {s3_url_of_data_file}')
    sql = """
            INSERT INTO product_data_file_mapping
            (
                s3_url_of_product_label,
                s3_url_of_data_file,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                :s3_url_of_data_file_param,
                :last_updated_epoch_time_param
                )
            """

    s3_url_of_product_label_param = {'name':'s3_url_of_product_label_param', 'value':{'stringValue': s3_url_of_product_label}}
    s3_url_of_data_file_param = {'name':'s3_url_of_data_file_param', 'value':{'stringValue': s3_url_of_data_file}}
    last_updated_epoch_time_param = {'name':'last_updated_epoch_time_param', 'value':{'longValue': round(time.time()*1000)}}

    param_set = [s3_url_of_product_label_param, s3_url_of_data_file_param, last_updated_epoch_time_param]

    response = rds_data.execute_statement(
        resourceArn = db_clust_arn,
        secretArn = db_secret_arn,
        database = 'pds_nucleus',
        sql = sql,
        parameters = param_set)

     logger.debug(str(response))

# Creates a record for product
def save_product_processing_status_in_database(s3_url_of_product_label, processing_status):

    logger.info(f'Save product processing status for: {s3_url_of_product_label}')

    sql = """
            INSERT INTO product
            (
                s3_url_of_product_label,
                processing_status,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_product_label_param,
                :processing_status_param,
                :last_updated_epoch_time_param
                )
            """

    s3_url_of_product_label_param = {'name':'s3_url_of_product_label_param', 'value':{'stringValue': s3_url_of_product_label}}
    processing_status_param = {'name':'processing_status_param', 'value':{'stringValue': processing_status}}
    last_updated_epoch_time_param = {'name':'last_updated_epoch_time_param', 'value':{'longValue': round(time.time()*1000)}}

    param_set = [s3_url_of_product_label_param, processing_status_param, last_updated_epoch_time_param]

    response = rds_data.execute_statement(
        resourceArn = db_clust_arn,
        secretArn = db_secret_arn,
        database = 'pds_nucleus',
        sql = sql,
        parameters = param_set)

     logger.debug(str(response))

# Creates a record for data file
def save_data_file_in_database(s3_url_of_data_file):

    logger.info(f'Save datafile: {s3_url_of_data_file}')

    sql = """
            REPLACE INTO data_file
            (
                s3_url_of_data_file,
                last_updated_epoch_time)
            VALUES(
                :s3_url_of_data_file_param,
                :last_updated_epoch_time_param
                )
            """

    s3_url_of_data_file_param = {'name':'s3_url_of_data_file_param', 'value':{'stringValue': s3_url_of_data_file}}
    last_updated_epoch_time_param = {'name':'last_updated_epoch_time_param', 'value':{'longValue': round(time.time()*1000)}}

    param_set = [s3_url_of_data_file_param, last_updated_epoch_time_param]

    response = rds_data.execute_statement(
        resourceArn = db_clust_arn,
        secretArn = db_secret_arn,
        database = 'pds_nucleus',
        sql = sql,
        parameters = param_set)

    logger.debug(str(response))


# Creates a record for product label
def save_files_for_product_label(s3_url_of_product_label, bucket, key):
    s3_base_dir = s3_url_of_product_label.rsplit('/',1)[0]

    logger.info(f'Get s3_response for key: {key} from bucket: {bucket}')

    try:
        s3_response = s3.get_object(Bucket=bucket, Key=key)

        # Get the Body object in the S3 get_object() response
        s3_object_body = s3_response.get('Body')

        # Read the data in bytes format and convert it to string
        content_str = s3_object_body.read().decode()

        # parse xml
        xmldoc = minidom.parseString(content_str)
        expected_files_from_product_label = xmldoc.getElementsByTagName('file_name')

        for x in expected_files_from_product_label:
            s3_url_of_data_file = s3_base_dir + "/" + x.firstChild.nodeValue
            save_product_data_file_mapping_in_database(s3_url_of_product_label, s3_url_of_data_file)

    except Exception as e:
        logger.error(f"Error handling  missing files for product label: {s3_url_of_product_label}. Exception: {str(e)}")
        raise e

# Copies a file from S3 to EFS
def copy_file_to_efs(s3_bucket, s3_key, efs_mount_path):
    path_of_product = s3_bucket + "/" + s3_key
    download_dir = os.path.dirname('/tmp/' + path_of_product)
    download_file_path = os.path.normpath('/tmp/' + path_of_product)

    try:
        # Download the file from S3 (only /tmp has permissions to download)
        logger.info(f"File downloading to : {download_file_path}")
        os.makedirs(download_dir, exist_ok=True)
        s3.download_file(s3_bucket, s3_key,  download_file_path)
        logger.info(f"File downloaded: {download_file_path}")
    except Exception as e:
        logger.error(f"Error downloading file from S3. s3_bucket: {s3_bucket}, s3_key: {s3_key}, efs_mount_path: {efs_mount_path}, Exception: {str(e)}")

    # Move the file to the /mnt/data directory
    destination_path = efs_mount_path + os.path.dirname(path_of_product)
    destination_file = efs_mount_path + path_of_product

    try:
        os.makedirs(destination_path, exist_ok=True)

        if os.path.isfile(os.path.normpath(destination_file)):
            os.remove(os.path.normpath(destination_file))
            logger.debug(f"Deleted existing file in: {os.path.normpath(destination_file)}")

        shutil.move(download_file_path, os.path.normpath(destination_path))
        logger.info(f"File moved to: {destination_path}")
 except Exception as e:
        logger.error(f"Error moving file to : {destination_path}. Exception: {str(e)}")

    return {
        'statusCode': 200,
        'body': 'File downloaded and moved successfully'
    }
