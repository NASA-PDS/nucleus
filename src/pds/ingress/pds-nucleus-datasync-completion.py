"""
==============================================
pds-nucleus-datasync-completion.py
==============================================

Lambda function to read each data transfer report JSON file and update the Nucleus database tables ()
(product table, product_data_file_mapping table and data_file table) based on the list of verified
files found in the data transfer report. This lambda function is asynchronously called by
the lambda function called pds-nucleus-datasync-completion-trigger.py.

"""

import boto3
import logging
import json
import os
import time
from xml.dom import minidom

datasync_reports_s3_bucket_name = "pds-nucleus-datassync-reports"

logger = logging.getLogger("pds-nucleus-datasync-completion")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')

s3_bucket_name = "pds-nucleus-staging"
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')

rds_data = boto3.client('rds-data')

def lambda_handler(event, context):
    """ Lambda Handler - The entry point of lambda """

    logger.info(f"Lambda Request ID: {context.aws_request_id}")
    logger.info(f"Event: {event}")

    content_object = s3.Object('pds-nucleus-datassync-reports', str(event["s3_key"]))
    transfer_report_file_content = content_object.get()['Body'].read().decode('utf-8')
    transfer_report_json_content = json.loads(transfer_report_file_content)
    verified_file_obj_list = transfer_report_json_content['Verified']

    logger.debug(f"verified_file_obj_list: {verified_file_obj_list}")

    list_of_files = []

    # Process each file in verified file list
    for file_obj in verified_file_obj_list:

        obj_name = file_obj['RelativePath']
        obj_type = file_obj['SrcMetadata']['Type']

        if obj_type == 'Regular':  # Not a directory

            if obj_name.endswith('.fz'):
                file_to_extract = f"/mnt/data/{s3_bucket_name}" + obj_name
                extract_file(file_to_extract)
                obj_name = obj_name.rstrip(",.fz")

            s3_url_of_file = "s3://" + s3_bucket_name + obj_name

            s3_key = obj_name[1:]

            handle_file_types(s3_url_of_file, s3_bucket_name, s3_key)

            list_of_files.append(s3_url_of_file)

    logger.debug(f"List_of_files received: {list_of_files}")



def handle_file_types(s3_url_of_file, s3_bucket, s3_key):
    """ Invokes functions based on the file type """

    try:
        # TODO:  Product label received (THIS CAN BE LBLX )
        if s3_url_of_file.lower().endswith(".xml") and not s3_url_of_file.lower().endswith(".aux.xml"):
            logger.debug(f"Received product file: {s3_url_of_file}")
            save_product_processing_status_in_database(s3_url_of_file, "INCOMPLETE")
            save_files_for_product_label(s3_url_of_file, s3_bucket, s3_key)

        # Data file received
        elif not s3_url_of_file.lower().endswith("/"):  # Not a directory
            logger.info(f"Received data file: {s3_url_of_file}")
            save_data_file_in_database(s3_url_of_file)

    except Exception as e:
        logger.error(f"Error processing . Exception: {str(e)}")
        raise e


def extract_file(file_to_extract):
    """ Extracts .fz to files to .fits """

    logger.debug(f"Extraction file {file_to_extract}...")

    try:
        os.system(f'funpack {os.path.normpath(file_to_extract)}')
        logger.info(f'Unpacked file: {os.path.normpath(file_to_extract)}')
    except Exception as e:
        logger.error(f"Error extracting file: {file_to_extract}. Exception: {str(e)}")
        raise e


def save_product_data_file_mapping_in_database(s3_url_of_product_label, s3_url_of_data_file):
    """ Creates a mapping record in the database for product and relevant files """

    logger.info(f"Saving product data file mapping {s3_url_of_product_label} --> {s3_url_of_data_file} in database")
    sql = """
            REPLACE INTO product_data_file_mapping
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

    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}
    s3_url_of_data_file_param = {'name': 's3_url_of_data_file_param', 'value': {'stringValue': s3_url_of_data_file}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}

    param_set = [s3_url_of_product_label_param, s3_url_of_data_file_param, last_updated_epoch_time_param]

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database='pds_nucleus',
            sql=sql,
            parameters=param_set)

        logger.debug(str(response))
    except Exception as e:
        logger.error(f"Error updating product_data_file_mapping table. Exception: {str(e)}")
        raise e


def save_product_processing_status_in_database(s3_url_of_product_label, processing_status):
    """ Creates a record for product """

    logger.debug(f"Saving product processing status for: {s3_url_of_product_label} in database")

    sql = """
            REPLACE INTO product
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

    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}
    processing_status_param = {'name': 'processing_status_param', 'value': {'stringValue': processing_status}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}

    param_set = [s3_url_of_product_label_param, processing_status_param, last_updated_epoch_time_param]

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database='pds_nucleus',
            sql=sql,
            parameters=param_set)
        logger.debug(str(response))

    except Exception as e:
        logger.error(f"Error writing to product table. Exception: {str(e)}")
        raise e


def save_data_file_in_database(s3_url_of_data_file):
    """ Creates a record for data file """

    logger.debug(f"Saving data file name in database: {s3_url_of_data_file} in database")

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

    try:
        response = rds_data.execute_statement(
            resourceArn=db_clust_arn,
            secretArn=db_secret_arn,
            database='pds_nucleus',
            sql=sql,
            parameters=param_set)

        logger.debug(str(response))

    except Exception as e:
        logger.error(f"Error updating data_file table. Exception: {str(e)}")
        raise e


def save_files_for_product_label(s3_url_of_product_label, bucket, key):
    """ Creates a record for product label """

    s3_base_dir = s3_url_of_product_label.rsplit('/', 1)[0]

    try:
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)

    except Exception as e:
        logger.error(f"Error getting S3 object: for bucker: {bucket} and key: {key}. Exception: {str(e)}")
        raise e

    try:
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
