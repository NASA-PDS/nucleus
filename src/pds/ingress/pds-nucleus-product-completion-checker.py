"""
==============================================
pds-nucleus-product-completion-checker.py
==============================================

Lambda function to check if the staging S3 bucket has received a complete product
with all required files. This lambda function is triggered periodically.

"""

import json
import logging
import os
import time

import boto3

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
logger = logging.getLogger("pds-nucleus-product-completion-checker-logger")
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
rds_data = boto3.client('rds-data')


# Main lambda handler
def lambda_handler(event, context):
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    try:
        process_completed_products()
        return f"Processed."
    except Exception as e:
        logger.error(f"Error processing S3 event: {event}. Exception: {str(e)}")
        raise e


# Identifies and processes completed products
def process_completed_products():
    logger.info(f'Checking completed products')

    sql = """
            select distinct s3_url_of_product_label from product where s3_url_of_product_label
            NOT IN (select distinct s3_url_of_product_label  from product_data_file_mapping
            where s3_url_of_data_file
            NOT IN (select s3_url_of_data_file from data_file));
            """

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)

    logger.info("Number of completed product labels: " + str(len(response['records'])))

    for record in response['records']:
        for data_dict in record:
            for data_type, data_value in data_dict.items():
                update_product_processing_status_in_database(data_value, 'COMPLETE')
                notify_completed_product(data_value)
                time.sleep(1 / 100)


# Updates the product processing status of the given s3_url_of_product_label
def update_product_processing_status_in_database(s3_url_of_product_label, processing_status):
    sql = f"""
        UPDATE product
        SET processing_status = '{processing_status}'
        # SET last_updated_epoch_time = {round(time.time() * 1000)}
        WHERE s3_url_of_product_label = '{s3_url_of_product_label}'
            """

    logger.debug(sql)

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)

    logger.info("response = " + str(response))


# Sends a notification to SQS on product copy completion
def notify_completed_product(s3_url_of_product_label):
    efs_mount_path = os.environ.get('EFS_MOUNT_PATH')
    sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
    efs_product_label_file_location = s3_url_of_product_label.replace("s3:/", efs_mount_path, 1)

    sqs = boto3.client('sqs')

    message = {
        "s3_url_of_product_label": s3_url_of_product_label,
        "efs_product_label_file_location": efs_product_label_file_location,
    }

    sqs.send_message(
        QueueUrl=sqs_queue_url,
        MessageBody=json.dumps(message)
    )

    logger.info('SQS Message sent for the completed product')
