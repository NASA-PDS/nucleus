"""
============================================================
pds-nucleus-product-completion-checker.py (batch processing)
============================================================    =

Lambda function to check if the staging S3 bucket has received a complete product
with all required files. This lambda function is triggered periodically.

"""

import json
import urllib.parse
import logging
import shutil
import boto3
import os
import time
import http.client
import base64
import ast
import uuid

from xml.dom import minidom

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
mwaa_client = boto3.client('mwaa')

logger = logging.getLogger("pds-nucleus-product-completion-checker-logger")
rds_data = boto3.client('rds-data')

mwaa_env_name = 'PDS-Nucleus-Airflow-Env'
mwaa_cli_command = 'dags trigger'

# Read environment variables from lambda configurations
dag_name = os.environ.get('AIRFLOW_DAG_NAME')
node_name = os.environ.get('NODE_NAME')
es_url = os.environ.get('ES_URL')
replace_prefix_with = os.environ.get('REPLACE_PREFIX_WITH')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')
sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')

es_auth_file = efs_mount_path + '/configs/es-auth.cfg'
replace_prefix = efs_mount_path

def lambda_handler(event, context):
    """ Main lambda handler """

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    try:
        process_completed_products()
        return f"Processed lambda request ID: {context.aws_request_id}"
    except Exception as e:
        logger.error(f"Error processing S3 event: {event}. Exception: {str(e)}")
        raise e


def process_completed_products():
    """ Identifies and processes completed products """

    logger.debug("Checking completed products...")

    sql =   """
                SELECT DISTINCT s3_url_of_product_label from product
                WHERE processing_status = 'INCOMPLETE' and s3_url_of_product_label
                NOT IN (SELECT s3_url_of_product_label  from product_data_file_mapping
                where s3_url_of_data_file
                NOT IN (SELECT s3_url_of_data_file from data_file)) and s3_url_of_product_label
                IN (SELECT s3_url_of_product_label  from product_data_file_mapping);
            """

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)

    logger.debug(f"Number of completed product labels : {str(len(response['records']))}")

    n = 10
    count = 0
    list_of_product_labels_to_process = []

    for record in response['records']:

        count = count + 1

        for data_dict in record:
            for data_type, s3_url_of_product_label in data_dict.items():
                update_product_processing_status_in_database(s3_url_of_product_label, 'COMPLETE')
                list_of_product_labels_to_process.append(s3_url_of_product_label)

        if count == n:
            submit_data_to_nucleus(list_of_product_labels_to_process)
            count = 0
            list_of_product_labels_to_process = []

    submit_data_to_nucleus(list_of_product_labels_to_process)
    count = 0
    list_of_product_labels_to_process = []

def update_product_processing_status_in_database(s3_url_of_product_label, processing_status):
    """ Updates the product processing status of the given s3_url_of_product_label """
    sql = """
            UPDATE product
            SET processing_status = :processing_status_param,
            last_updated_epoch_time = :last_updated_epoch_time_param
            WHERE s3_url_of_product_label = :s3_url_of_product_label_param
                """

    processing_status_param = {'name': 'processing_status_param', 'value': {'stringValue': processing_status}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}
    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}

    param_set = [processing_status_param, last_updated_epoch_time_param, s3_url_of_product_label_param]

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql,
        parameters=param_set)

    logger.debug(f"Response for update_product_processing_status_in_database: {str(response)}")

def submit_data_to_nucleus(list_of_product_labels_to_process):
    """ Submits data to Nucleus """

    if len(list_of_product_labels_to_process) > 0:
        create_harvest_config_xml_and_trigger_nucleus(list_of_product_labels_to_process)


def create_harvest_config_xml_and_trigger_nucleus(list_of_product_labels_to_process):
    """ Creates harvest manifest file and harvest config file and trigger Nucleus workflow """

    logger.debug('List of product labels to process:' + str(list_of_product_labels_to_process))

    efs_mount_path = os.environ.get('EFS_MOUNT_PATH')

    harvest_config_dir = efs_mount_path + '/harvest-configs'

    file_name =  os.path.basename(list_of_product_labels_to_process[0].replace("s3:/", efs_mount_path, 1) )

    harvest_manifest_content = ""
    list_of_product_labels_to_process_with_file_paths = []

    for s3_url_of_product_label in list_of_product_labels_to_process:
        efs_product_label_file_location = s3_url_of_product_label.replace("s3:/", efs_mount_path, 1)
        harvest_manifest_content = harvest_manifest_content + efs_product_label_file_location + '\n'
        list_of_product_labels_to_process_with_file_paths.append(efs_product_label_file_location)

    # Generate a random suffix for harvest config file name and manifest file name to avoid conflicting duplicate file names
    random_suffix = uuid.uuid4().hex

    try:
        os.makedirs(harvest_config_dir, exist_ok=True)
        harvest_config_file_path = harvest_config_dir + '/harvest_' + file_name + '_' + random_suffix + '.cfg'
        harvest_manifest_file_path = harvest_config_dir + '/harvest_manifest_' + file_name + '_' + random_suffix + '.txt'

        logger.debug(f"Manifest content: {str(harvest_manifest_content)}")

        # Create harvest manifest file
        f = open(harvest_manifest_file_path, "w")
        f.writelines(harvest_manifest_content)
        f.close()

        logger.info(f"Created harvest manifest file: {harvest_manifest_file_path}")

        harvest_config_xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>

            <harvest nodeName="{node_name}">
              <files>
                <manifest>{harvest_manifest_file_path}</manifest>
              </files>
              <registry url="{es_url}" index="registry" auth="{es_auth_file}" />
              <autogenFields/>
              <fileInfo>
                <!-- UPDATE with your own local path and base url where pds4 archive is published -->
                <fileRef replacePrefix="{replace_prefix}" with="{replace_prefix_with}" />
              </fileInfo>
            </harvest>
            """

        with open(harvest_config_file_path, "w") as f:
            f.write(harvest_config_xml_content)

        logger.info(f"Created harvest config XML file: {harvest_config_file_path}")
    except Exception as e:
        logger.error(f"Error creating harvest config files in : {harvest_config_dir}. Exception: {str(e)}")
        return

    trigger_nucleus_workflow(harvest_manifest_file_path, harvest_config_file_path,
                             list_of_product_labels_to_process_with_file_paths)

    logger.info(f"Triggered Nucleus workflow: {dag_name} for product label: {efs_product_label_file_location}")


def trigger_nucleus_workflow(harvest_manifest_file_path, pds_harvest_config_file, list_of_product_labels_to_process):
    """ Triggers Nucleus workflow with parameters """

    # Convert list to comma seperated list
    delim = ","
    temp = list(map(str, list_of_product_labels_to_process))
    comma_seperated_list_of_product_labels_to_process = delim.join(temp)

    # Get web token
    mwaa_cli_token = mwaa_client.create_cli_token(
        Name=mwaa_env_name
    )

    harvest_manifest_file_path_key = "harvest_manifest_file_path"
    harvest_manifest_file_path_value = harvest_manifest_file_path
    pds_harvest_config_file_key = "pds_harvest_config_file"
    pds_harvest_config_file_value = pds_harvest_config_file
    list_of_product_labels_to_process_key = "list_of_product_labels_to_process"
    list_of_product_labels_to_process_value = str(comma_seperated_list_of_product_labels_to_process)

    conf = "{\"" + harvest_manifest_file_path_key + "\":\"" + harvest_manifest_file_path_value + "\", \"" + pds_harvest_config_file_key + "\":\"" + \
        pds_harvest_config_file_value + "\", \"" + list_of_product_labels_to_process_key + \
        "\":\"" + list_of_product_labels_to_process_value + "\"}"

    logger.info(f"Triggering Nucleus workflow {dag_name} with parameters : {conf}")

    try:
        conn = http.client.HTTPSConnection(mwaa_cli_token['WebServerHostname'])
        payload = "dags trigger {0} -c '{1}'".format(dag_name, conf)
        headers = {
            'Authorization': 'Bearer ' + mwaa_cli_token['CliToken'],
            'Content-Type': 'text/plain'
        }
        conn.request("POST", "/aws_mwaa/cli", payload, headers)
        response = conn.getresponse()
        data = response.read()
        dict_str = data.decode("UTF-8")
        mydata = ast.literal_eval(dict_str)
        return base64.b64decode(mydata['stdout'])

    except Exception as e:
        logger.error(f"Error triggering Nucleus workflow {dag_name} with parameters : {conf}. Exception: {str(e)}")
