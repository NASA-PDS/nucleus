"""
=========================================
pds-nucleus-s3-event-lambda-invoker.py
=========================================

Lambda function to invoke other lambda functions based on the type of the files received.
This lambda function is triggered by S3 bucket events when a new file is copied to the staging S3 bucket.

"""

import boto3
import json
import logging
import urllib.parse

lambda_client = boto3.client('lambda', region_name='us-west-2')
logger = logging.getLogger("pds-nucleus-s3-event-lambda-invoker-logger")


def lambda_handler(event, context):

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    if key.lower().endswith(".fz"):
        lambda_client.invoke(FunctionName='pds-nucleus-fz-to-fits-convertor',
                             InvocationType='Event', Payload=json.dumps(event))
        logger.info(f"Invoked pds-nucleus-fz-to-fits-convertor")

    else:
        lambda_client.invoke(FunctionName='pds-nucleus-product-writer',
                             InvocationType='Event', Payload=json.dumps(event))
        logger.info(f"Invoked pds-nucleus-product-writer")

    return True
