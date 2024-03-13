"""
==============================================
pds-nucleus-datasync-completion.py
==============================================

Lambda function to read each data transfer report JSON file, get a list of verified
files found in the data transfer report and end the file path and s3 bucket details to a SQS queue.

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
sqs_queue_url = os.environ.get('SQS_QUEUE_URL')

rds_data = boto3.client('rds-data')

sqs = boto3.client('sqs')
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    """ Lambda Handler """


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

            # handle_file_types(s3_url_of_file, s3_bucket_name, s3_key)
            # send_file_url_to_lambda(s3_url_of_file, s3_bucket_name, s3_key)
            send_file_url_to_queue(s3_url_of_file, s3_bucket_name, s3_key)

            list_of_files.append(s3_url_of_file)

    logger.debug(f"List_of_files received: {list_of_files}")



def send_file_url_to_queue(s3_url_of_file, s3_bucket, s3_key):

    inputParams = {
            "s3_url_of_file": s3_url_of_file,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key
    }

    logger.info(f"Sending message : {inputParams}")

    response = sqs.send_message(
        QueueUrl=sqs_queue_url,
        MessageBody=json.dumps(inputParams)
    )

    logger.info(f"Sent message with response: {response}")
