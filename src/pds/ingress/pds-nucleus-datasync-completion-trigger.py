"""
============================================================
pds-nucleus-datasync-completion-trigger.py
============================================================    =

Lambda function that get triggered when the PDS Nucleus Staging S3 Bucket to EFS datasync task is completed.
This function reads the list of data transfer verification reports created by a specific DataSync task
and asynchronously call the pds-nucleus-datasync-completion.py for each data transfer verification
report JSON file.

"""

import boto3
import logging
import json
import os

datasync_reports_s3_bucket_name = "pds-nucleus-datassync-reports"

logger = logging.getLogger("pds-nucleus-datasync-completion-trigger")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')

s3_bucket_name = "pds-nucleus-staging"
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')

rds_data = boto3.client('rds-data')

# Define the client to interact with AWS Lambda
client = boto3.client('lambda')


def lambda_handler(event, context):
    """ Lambda Handler """

    logger.info(f"Lambda Request ID: {context.aws_request_id}")
    logger.info(f"Event: {event}")
    resource = event['resources']

    resource_list = resource[0].split("/")
    task_id = resource_list[1]
    exec_id = resource_list[3]

    prefix = f"Detailed-Reports/{task_id}/{exec_id}/{exec_id}.files-verified-"

    datasync_reports_s3_bucket = s3.Bucket(datasync_reports_s3_bucket_name)

    list_of_files = []

    # Loop through the list of json files with the prefix files-verified-
    for transfer_report in datasync_reports_s3_bucket.objects.filter(Prefix=prefix):
        # Define the input parameters that will be passed
        # on to the child function
        inputParams = {
            "s3_key": transfer_report.key
        }

        logger.debug(f"inputParams: {str(inputParams)}")
        response = client.invoke(
            FunctionName='arn:aws:lambda:us-west-2:441083951559:function:pds-nucleus-datasync-completion',
            InvocationType='Event',
            Payload=json.dumps(inputParams)
        )

    logger.debug(f"List_of_files received: {list_of_files}")
