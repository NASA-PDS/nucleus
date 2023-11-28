"""
=========================================
pds-nucleus-fz-to-fits-converter.py
=========================================

Lambda function to extract fz files (to get .fits files).
This lambda function is triggered by pds-nucleus-s3-event-lambda-invoker lambda function when a
new .fz file is copied to the staging S3 bucket.

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

# Read environment variables from lambda configurations
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')

rds_data = boto3.client('rds-data')

# Main lambda handler


def lambda_handler(event, context):

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    copy_file_to_efs(bucket, key, efs_mount_path)


# Copies a file from S3 to EFS
def copy_file_to_efs(s3_bucket, s3_key, efs_mount_path):
    path_of_product = s3_bucket + "/" + s3_key
    download_dir = os.path.dirname('/tmp/' + path_of_product)
    download_file_path = os.path.normpath('/tmp/' + path_of_product)

    try:
        # Download the file from S3 (only /tmp has permissions to download)
        logger.info(f"File downloading to : {download_file_path}")
        os.makedirs(download_dir, exist_ok=True)
        s3.download_file(s3_bucket, s3_key, download_file_path)
        logger.info(f"File downloaded: {download_file_path}")
    except Exception as e:
        logger.error(
            f"Error downloading file from S3. s3_bucket: {s3_bucket}, s3_key: {s3_key}, efs_mount_path: {efs_mount_path}, Exception: {str(e)}")

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

        # Unpack .fz files
        if destination_file.lower().endswith(".fz"):

            s3_key_renamed = s3_key.rstrip(",.fz")
            logger.info(f'Renamed to {s3_key_renamed}')

            uncompressed_file = os.path.normpath(destination_file).rstrip(",.fz")
            logger.info(f'Uncompressed_file name = {uncompressed_file}')

            if os.path.isfile(os.path.normpath(uncompressed_file)):
                os.remove(os.path.normpath(uncompressed_file))
                logger.debug(f"Deleted existing file in: {os.path.normpath(uncompressed_file)}")

            os.system(f'funpack {os.path.normpath(destination_file)}')
            logger.info(f'Unpacked {os.path.normpath(destination_file)}')

            s3_url_of_data_file = "s3://" + s3_bucket + "/" + s3_key_renamed
            save_data_file_in_database(s3_url_of_data_file)

    except Exception as e:
        logger.error(f"Error moving file to : {destination_path}. Exception: {str(e)}")

    return {
        'statusCode': 200,
        'body': 'File downloaded and moved successfully'
    }


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

    s3_url_of_data_file_param = {'name': 's3_url_of_data_file_param', 'value': {'stringValue': s3_url_of_data_file}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}

    param_set = [s3_url_of_data_file_param, last_updated_epoch_time_param]

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql,
        parameters=param_set)

    logger.debug(f"response = {str(response)}")
