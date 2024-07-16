"""
============================================================
pds-nucleus-product-completion-checker.py (batch processing)
============================================================

Lambda function to check if the staging S3 bucket has received a complete product
with all required files. This lambda function is triggered periodically.

"""

import logging
import boto3
import os
import time
import http.client
import base64
import ast
import uuid

from xml.dom import minidom
from datetime import datetime

s3_client = boto3.client('s3')
mwaa_client = boto3.client('mwaa')

logger = logging.getLogger("pds-nucleus-product-completion-checker-logger")
rds_data = boto3.client('rds-data')


mwaa_cli_command = 'dags trigger'

# Read environment variables from lambda configurations
dag_name = os.environ.get('AIRFLOW_DAG_NAME')
pds_node_name = os.environ.get('PDS_NODE_NAME')
es_url = os.environ.get('ES_URL')
replace_prefix_with = os.environ.get('REPLACE_PREFIX_WITH')
efs_mount_path = os.environ.get('EFS_MOUNT_PATH')
sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')
es_auth_file = os.environ.get('ES_AUTH_CONFIG_FILE_PATH')
pds_nucleus_config_bucket_name = os.environ.get('PDS_NUCLEUS_CONFIG_BUCKET_NAME')
mwaa_env_name = os.environ.get('PDS_MWAA_ENV_NAME')

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

    # The limit 100 was used in following query to avoid the error "Database returned more than the allowed response size limit"
    # The remaining records will be retrieved in the subsequent queries.


    sql =   """
                SELECT DISTINCT s3_url_of_product_label from product
                WHERE completion_status = 'INCOMPLETE' and
                pds_node = :pds_node_param and
                s3_url_of_product_label
                NOT IN (SELECT s3_url_of_product_label  from product_data_file_mapping
                where s3_url_of_data_file
                NOT IN (SELECT s3_url_of_data_file from data_file)) and s3_url_of_product_label
                IN (SELECT s3_url_of_product_label  from product_data_file_mapping) limit 100;
            """

    pds_node_param = {'name': 'pds_node_param',
                                         'value': {'stringValue': pds_node_name}}

    param_set = [pds_node_param]

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql,
        parameters=param_set)
    logger.debug(f"Number of completed product labels : {str(response['records'])}")
    logger.debug(f"Number of completed product labels : {str(len(response['records']))}")

    n = 10
    count = 0
    list_of_product_labels_to_process = []

    for record in response['records']:

        count = count + 1

        for data_dict in record:
            for data_type, s3_url_of_product_label in data_dict.items():
                update_product_completion_status_in_database(s3_url_of_product_label, 'COMPLETE')
                list_of_product_labels_to_process.append(s3_url_of_product_label)

        if count == n:
            submit_data_to_nucleus(list_of_product_labels_to_process)
            count = 0
            list_of_product_labels_to_process = []

    submit_data_to_nucleus(list_of_product_labels_to_process)
    count = 0
    list_of_product_labels_to_process = []

def update_product_completion_status_in_database(s3_url_of_product_label, completion_status):
    """ Updates the product processing status of the given s3_url_of_product_label """
    sql = """
            UPDATE product
            SET completion_status = :completion_status_param,
            last_updated_epoch_time = :last_updated_epoch_time_param
            WHERE s3_url_of_product_label = :s3_url_of_product_label_param
                """

    completion_status_param = {'name': 'completion_status_param', 'value': {'stringValue': completion_status}}
    last_updated_epoch_time_param = {'name': 'last_updated_epoch_time_param',
                                     'value': {'longValue': round(time.time() * 1000)}}
    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}

    param_set = [completion_status_param, last_updated_epoch_time_param, s3_url_of_product_label_param]

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql,
        parameters=param_set)

    logger.debug(f"Response for update_product_completion_status_in_database: {str(response)}")

def submit_data_to_nucleus(list_of_product_labels_to_process):
    """ Submits data to Nucleus """

    if len(list_of_product_labels_to_process) > 0:
        create_harvest_configs_and_trigger_nucleus(list_of_product_labels_to_process)


def create_harvest_configs_and_trigger_nucleus(list_of_product_labels_to_process):
    """ Creates harvest manifest file and harvest config file and trigger Nucleus workflow """

    logger.debug('List of product labels to process:' + str(list_of_product_labels_to_process))

    harvest_manifest_content = ""
    list_of_product_labels_to_process_with_file_paths = []
    list_of_s3_urls_to_copy = []

    for s3_url_of_product_label in list_of_product_labels_to_process:
        efs_product_label_file_location = s3_url_of_product_label.replace("s3:/", efs_mount_path, 1)
        harvest_manifest_content = harvest_manifest_content + efs_product_label_file_location + '\n'
        list_of_product_labels_to_process_with_file_paths.append(efs_product_label_file_location)

        # Update list of S3 URLs to copy (from s3 to EFS in Nucleus)
        list_of_s3_urls_to_copy.append(s3_url_of_product_label)
        list_of_s3_urls_to_copy.extend(get_list_of_data_files(s3_url_of_product_label))

    # Generate a random suffix for harvest config file name and manifest file name to avoid conflicting duplicate file names
    current_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    random_batch_number = current_time + uuid.uuid4().hex

    try:
        harvest_config_file_path = 'harvest.cfg'
        harvest_manifest_file_path = 'harvest_manifest.txt'
        list_of_data_files_to_copy_file_path =  'data_file_list.txt'

        logger.debug(f"Manifest content: {str(harvest_manifest_content)}")

        # Create harvest manifest file
        f = open(f"/tmp/{harvest_manifest_file_path}", "w")
        f.writelines(harvest_manifest_content)
        f.close()

        logger.info(f"Created harvest manifest file: {harvest_manifest_file_path}")

        s3_config_dir = f"s3://{pds_nucleus_config_bucket_name}/dag-data/{random_batch_number}"
        efs_config_dir = f"/mnt/data/dag-data/{random_batch_number}"

        # Create harvest manifets file
        harvest_config_xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>

            <harvest nodeName="{pds_node_name}">
              <files>
                <manifest>{efs_config_dir + '/' + harvest_manifest_file_path}</manifest>
              </files>
              <registry url="{es_url}" index="registry" auth="{es_auth_file}" />
              <autogenFields/>
              <fileInfo>
                <!-- UPDATE with your own local path and base url where pds4 archive is published -->
                <fileRef replacePrefix="{replace_prefix}" with="{replace_prefix_with}" />
              </fileInfo>
            </harvest>
            """

        with open(f"/tmp/{harvest_config_file_path}", "w") as f:
            f.write(harvest_config_xml_content)

        logger.info(f"Created harvest config XML file: {harvest_config_file_path}")


        # Create file in S3 with list of files to copy
        with open(f"/tmp/{list_of_data_files_to_copy_file_path}", 'w') as f:
            for line in list_of_s3_urls_to_copy:
                f.write("%s\n" % line)

        logger.info(f"Created S3 file list file: {list_of_data_files_to_copy_file_path}")

        s3_client.upload_file(f"/tmp/{harvest_config_file_path}", pds_nucleus_config_bucket_name, f"dag-data/{random_batch_number}/{harvest_config_file_path}")
        s3_client.upload_file(f"/tmp/{harvest_manifest_file_path}", pds_nucleus_config_bucket_name, f"dag-data/{random_batch_number}/{harvest_manifest_file_path}")
        s3_client.upload_file(f"/tmp/{list_of_data_files_to_copy_file_path}", pds_nucleus_config_bucket_name, f"dag-data/{random_batch_number}/{list_of_data_files_to_copy_file_path}")

    except Exception as e:
        logger.error(f"Error creating harvest config files in s3 bucker: {pds_nucleus_config_bucket_name}. Exception: {str(e)}")
        return

    trigger_nucleus_workflow(random_batch_number, list_of_product_labels_to_process_with_file_paths, s3_config_dir, efs_config_dir)

    logger.info(f"Triggered Nucleus workflow: {dag_name} for product labels: {list_of_product_labels_to_process_with_file_paths}")



def get_list_of_data_files(s3_url_of_product_label):
    """ Retruns a lits of data file S3 URLs for a given product file """

    list_of_data_files = []

    sql =   """
                SELECT DISTINCT s3_url_of_data_file from product_data_file_mapping
                WHERE s3_url_of_product_label =  :s3_url_of_product_label_param
            """

    s3_url_of_product_label_param = {'name': 's3_url_of_product_label_param',
                                     'value': {'stringValue': s3_url_of_product_label}}

    param_set = [s3_url_of_product_label_param]

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql,
        parameters=param_set)

    for record in response['records']:
        for data_dict in record:
            for data_type, s3_url_of_data_file in data_dict.items():

                # Rename .fits to .fits.fz
                if s3_url_of_data_file.endswith('.fits'):
                    s3_url_of_data_file = s3_url_of_data_file + ".fz"

                list_of_data_files.append(s3_url_of_data_file)

    print(str(list_of_data_files))

    return list_of_data_files


def trigger_nucleus_workflow(random_batch_number, list_of_product_labels_to_process, s3_config_dir, efs_config_dir):
    """ Triggers Nucleus workflow with parameters """

    # Convert list to comma seperated list
    delim = ","
    temp = list(map(str, list_of_product_labels_to_process))
    comma_seperated_list_of_product_labels_to_process = delim.join(temp)

    # Get web token
    mwaa_cli_token = mwaa_client.create_cli_token(
        Name=mwaa_env_name
    )

    s3_config_dir_key = "s3_config_dir"
    s3_config_dir_value = s3_config_dir

    efs_config_dir_key = "efs_config_dir"
    efs_config_dir_value = efs_config_dir

    list_of_product_labels_to_process_key = "list_of_product_labels_to_process"
    list_of_product_labels_to_process_value = str(comma_seperated_list_of_product_labels_to_process)

    pds_node_name_key = "pds_node_name"
    pds_node_name_value = pds_node_name

    batch_number_key = "batch_number"
    batch_number_value = random_batch_number

    conf = "{\"" + \
            s3_config_dir_key + "\":\"" + s3_config_dir_value + "\",\"" + \
            list_of_product_labels_to_process_key + "\":\"" + list_of_product_labels_to_process_value + "\",\"" + \
            pds_node_name_key + "\":\"" + pds_node_name_value + "\",\"" + \
            batch_number_key + "\":\"" + batch_number_value + "\",\"" + \
            efs_config_dir_key + "\":\"" + efs_config_dir_value + "\"}"

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
        data_to_decode = ast.literal_eval(dict_str)
        return base64.b64decode(data_to_decode['stdout'])

    except Exception as e:
        logger.error(f"Error triggering Nucleus workflow {dag_name} with parameters : {conf}. Exception: {str(e)}")
