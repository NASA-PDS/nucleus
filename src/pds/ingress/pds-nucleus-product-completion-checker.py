"""
=========================================
pds-nucleus-product-completion-checker.py
=========================================

Lambda function to check if the staging S3 bucket has received a complete product 
with all required file. This lambda function is triggered by S3 bucket events
when a new file is copied to the staging S3 bucket.

"""

import json
import urllib.parse
import logging
import shutil
import boto3
import os
from xml.dom import minidom
from boto3.dynamodb.conditions import Key, Attr

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
logger = logging.getLogger("pds-nucleus-product-completion-checker-logger")

# Main lambda handler
def lambda_handler(event, context):

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    s3_url_of_data_file = "s3://" + bucket + "/" + key
    s3_url_of_product_label = "s3://" + bucket + "/" + key
    efs_mount_path = os.environ.get('EFS_MOUNT_PATH')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    try:

        # Product label received
        if s3_url_of_data_file.lower().endswith(".xml"):

            missing_files = handle_missing_files_for_product_label(s3_url_of_product_label, bucket, key)

            copy_file_to_efs(bucket, key, efs_mount_path)

            # If there are any missing files for the given product label
            if len(missing_files) > 0:
                save_incomplete_product(s3_url_of_product_label, missing_files)
            else:
                product_completed(s3_url_of_product_label)

        # Data file received
        elif not s3_url_of_data_file.lower().endswith("/"): # Not a directory
            copy_file_to_efs(bucket, key, efs_mount_path)
            save_received_file(s3_url_of_data_file)
            update_existing_incomplete_products(s3_url_of_data_file)
            delete_expected_file(s3_url_of_data_file)

        return f"Event for s3://{bucket}/{key} processed."
    except Exception as e:
        logger.error(f"Error processing S3 event: {event}. Exception: {str(e)}")
        raise e


# Handles the missing files detected for a product label
def handle_missing_files_for_product_label(s3_url_of_product_label, bucket, key):
    s3_base_dir = s3_url_of_product_label.rsplit('/',1)[0]

    logger.info('Get s3_response for key {} from bucket {}'.format(key, bucket))

    try:
        s3_response = s3.get_object(Bucket=bucket, Key=key)

        # Get the Body object in the S3 get_object() response
        s3_object_body = s3_response.get('Body')

        # Read the data in bytes format and convert it to string
        content_str = s3_object_body.read().decode()

        # parse xml
        xmldoc = minidom.parseString(content_str)
        missing_files_from_product_label = xmldoc.getElementsByTagName('file_name')

        missing_files = []

        for x in missing_files_from_product_label:

            s3_url_of_data_file = s3_base_dir + "/" + x.firstChild.nodeValue

            # Check received file table
            items = check_in_received_file_table(s3_url_of_data_file)

            # File is already received
            if items:
                logger.debug(f"The file is already received: {items['s3_url_of_data_file']}")
            else:

                missing_files.append(str(s3_url_of_data_file))
                update_expected_files(s3_url_of_data_file, s3_url_of_product_label)
                logger.debug(f"Missing files: {str(missing_files)}")

        return missing_files

    except Exception as e:
        logger.error(f"Error handling  missing files for product label: {s3_url_of_product_label}. Exception: {str(e)}")
        raise e


# Saves received files
def save_received_file(s3_url_of_data_file):
    received_data_files_table = dynamodb.Table('received_data_files')

    received_data_files_table.put_item(
        Item={
            's3_url_of_data_file': s3_url_of_data_file
        }
    )


# Returns an expected file response (with list of product labels) for a given s3_url_of_data_file
def get_expected_file(s3_url_of_data_file):
    expected_data_files_table = dynamodb.Table('expected_data_files')

    expected_data_files_table_get_response = expected_data_files_table.get_item(Key={
            "s3_url_of_data_file": str(s3_url_of_data_file)
        }
    )

    json_string_expected_files = json.dumps(expected_data_files_table_get_response, default=set_default)
    expected_data_files_get_response_json = json.loads(json_string_expected_files)
    expected_files_items = expected_data_files_get_response_json.get('Item')

    return expected_files_items


# Returns incomplete products
def get_incomplete_products(s3_url_of_product_label):
    incomplete_products_table = dynamodb.Table('incomplete_products')

    incomplete_products_table_get_response = incomplete_products_table.get_item(Key={
            "s3_url_of_product_label": str(s3_url_of_product_label)
        }
    )

    json_string_incomplete_products = json.dumps(incomplete_products_table_get_response, default=set_default)
    incomplete_products_table_get_response_json = json.loads(json_string_incomplete_products)
    incomplete_products_table_items = incomplete_products_table_get_response_json.get('Item')

    return incomplete_products_table_items


# Checks for s3_url_of_data_file in received files table
def check_in_received_file_table(s3_url_of_data_file):
    # Check received file table
    received_data_files_table = dynamodb.Table('received_data_files')

    received_data_files_table_get_response = received_data_files_table.get_item(Key={
        "s3_url_of_data_file": str(s3_url_of_data_file)
    })

    json_string = json.dumps(received_data_files_table_get_response, default=set_default)
    received_data_files_table_get_response_json = json.loads(json_string)
    items = received_data_files_table_get_response_json.get('Item')

    return items


# Saves incomplete product label with a list if missing files
def save_incomplete_product(s3_url_of_product_label, missing_files):
    incomplete_products_table = dynamodb.Table('incomplete_products')

    incomplete_products_table.put_item(
        Item={
            's3_url_of_product_label': s3_url_of_product_label,
            'missing_files': missing_files
        }
    )


# Updates exiting incomplete products
def update_existing_incomplete_products(s3_url_of_data_file):
    expected_files_items = get_expected_file(s3_url_of_data_file)

    # If this is an already expected file (i.e.: another product was also expecting this)
    if expected_files_items:
        expected_files_product_label_list = expected_files_items['s3_urls_of_product_labels']
        logger.info("expected_files_product_label_list = " + str(expected_files_product_label_list))

        for expected_files_product_label in expected_files_product_label_list:

            incomplete_products_table_items = get_incomplete_products(expected_files_product_label)

            if incomplete_products_table_items:
                missing_files_list = incomplete_products_table_items['missing_files']
                s3_url_of_product_label = incomplete_products_table_items['s3_url_of_product_label']
                missing_files_list.remove(s3_url_of_data_file)

                if len(missing_files_list) > 0:
                    save_incomplete_product(s3_url_of_product_label, missing_files_list)
                else:
                    product_completed(s3_url_of_product_label)


# Updates expected files
def update_expected_files(s3_url_of_data_file, s3_url_of_product_label):
    expected_files_items = get_expected_file(s3_url_of_data_file)
    expected_files_product_label_set = set()

    if expected_files_items:
        expected_files_product_label_set = set(expected_files_items['s3_urls_of_product_labels'])

    expected_files_product_label_set.add(s3_url_of_product_label)
    save_expected_files(s3_url_of_data_file, expected_files_product_label_set)


# Saves expected files
def save_expected_files(s3_url_of_data_file, expected_files_product_label_set):
    expected_data_files_table = dynamodb.Table('expected_data_files')

    expected_data_files_table.put_item(
        Item={
            's3_url_of_data_file': s3_url_of_data_file,
            's3_urls_of_product_labels': expected_files_product_label_set
        }
    )


# Deletes expected files
def delete_expected_file(s3_url_of_data_file):
    expected_data_files_table = dynamodb.Table('expected_data_files')

    expected_data_files_table.delete_item(Key={
            "s3_url_of_data_file": str(s3_url_of_data_file)
        }
    )


# Deletes incomplete products
def delete_incomplete_product(s3_url_of_product_label):
    incomplete_products_table = dynamodb.Table('incomplete_products')

    incomplete_products_table.delete_item(Key={
            "s3_url_of_product_label": str(s3_url_of_product_label)
        }
    )


# Processes complete products
def product_completed(s3_url_of_product_label):
    logger.info("PRODUCT COMPLETED")
    delete_incomplete_product(s3_url_of_product_label)
    notify_product(s3_url_of_product_label)


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


# Sends a notification to SQS on product copy completion
def notify_product(s3_url_of_product_label):
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

# Uses to convert a set to list for JSON serializing
def set_default(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError
