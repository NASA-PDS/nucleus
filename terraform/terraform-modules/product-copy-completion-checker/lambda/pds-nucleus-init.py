"""
============================================================
pds-nucleus-init.py
============================================================    =

Lambda function to initialize PDS database tables and other initial setup.

"""

import logging
import boto3
import os

logger = logging.getLogger("pds-nucleus-init-logger")
rds_data = boto3.client('rds-data')

# Read environment variables from lambda configurations
db_clust_arn = os.environ.get('DB_CLUSTER_ARN')
db_secret_arn = os.environ.get('DB_SECRET_ARN')

def lambda_handler(event, context):
    """ Main lambda handler """

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    logger.info(f"Lambda Request ID: {context.aws_request_id}")

    try:
        create_product_table()
        create_datafile_table()
        create_product_datafile_mapping_table()
        return f"Processed lambda request ID: {context.aws_request_id}"
    except Exception as e:
        logger.error(f"Error creating database tables. Exception: {str(e)}")
        raise e

def create_product_table():
    """ Created product table """
    sql =   """
                   CREATE TABLE product
                   (
                       s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
                       processing_status VARCHAR(10),
                       last_updated_epoch_time BIGINT,
                       PRIMARY KEY (s3_url_of_product_label)
                   );
             """

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_product_table()  : {str(response)}")


def create_datafile_table():
    """ Created datafile table """
    sql =   """
                  CREATE TABLE data_file
                  (
                      s3_url_of_data_file VARCHAR(1000) CHARACTER SET latin1,
                      last_updated_epoch_time BIGINT,
                      PRIMARY KEY (s3_url_of_data_file)
                  );
             """

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_datafile_table()  : {str(response)}")


def create_product_datafile_mapping_table():
    """ Created product_datafile_mapping table """
    sql =   """
                  CREATE TABLE product_data_file_mapping
                  (
                      s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
                      s3_url_of_data_file VARCHAR(1500) CHARACTER SET latin1,
                      last_updated_epoch_time BIGINT,
                      PRIMARY KEY (s3_url_of_product_label, s3_url_of_data_file)
                  );
             """

    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_product_datafile_mapping_table()  : {str(response)}")
