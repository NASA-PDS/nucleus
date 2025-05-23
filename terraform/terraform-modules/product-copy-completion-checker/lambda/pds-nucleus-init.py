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
        drop_product_table()
        drop_datafile_table()
        drop_product_datafile_mapping_table()
        drop_product_processing_status_table()

        create_product_table()
        create_datafile_table()
        create_product_datafile_mapping_table()
        create_product_processing_status_table()
        return f"Processed lambda request ID: {context.aws_request_id}"
    except Exception as e:
        logger.error(f"Error creating database tables. Exception: {str(e)}")
        raise e


def drop_product_table():
    """ Drop product table """
    sql =   """
               DROP TABLE IF EXISTS product;
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for drop_product_table()  : {str(response)}")


def create_product_table():
    """ Create product table """
    sql =   """
               CREATE TABLE product
               (
                   s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
                   completion_status VARCHAR(50),
                   last_updated_epoch_time BIGINT,
                   pds_node VARCHAR(10),
                   PRIMARY KEY (s3_url_of_product_label)
               );
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_product_table()  : {str(response)}")


def drop_datafile_table():
    """ Drop datafile table """
    sql =   """
                DROP TABLE IF EXISTS data_file;
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for drop_datafile_table()  : {str(response)}")


def create_datafile_table():
    """ Created datafile table """
    sql =   """
                CREATE TABLE data_file
                (
                    s3_url_of_data_file     VARCHAR(1000) CHARACTER SET latin1,
                    original_s3_url_of_data_file_name VARCHAR(1500) CHARACTER SET latin1,
                    last_updated_epoch_time BIGINT,
                    pds_node VARCHAR(10),
                    PRIMARY KEY (s3_url_of_data_file)
                );
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_datafile_table()  : {str(response)}")


def drop_product_datafile_mapping_table():
    """ Created product_datafile_mapping table """
    sql =   """
              DROP TABLE IF EXISTS product_data_file_mapping;
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_product_datafile_mapping_table()  : {str(response)}")


def create_product_datafile_mapping_table():
    """ Create product_datafile_mapping table """
    sql =   """
              CREATE TABLE product_data_file_mapping
              (
                  s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
                  s3_url_of_data_file VARCHAR(1500) CHARACTER SET latin1,
                  last_updated_epoch_time BIGINT,
                  pds_node VARCHAR(10),
                  PRIMARY KEY (s3_url_of_product_label, s3_url_of_data_file)
              );
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_product_datafile_mapping_table()  : {str(response)}")


def drop_product_processing_status_table():
    """ Drop product processing status table """
    sql =   """
               DROP TABLE IF EXISTS product_processing_status;
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for drop_product_processing_status_table()  : {str(response)}")


def create_product_processing_status_table():
    """ Create product processing status table """
    sql =   """
               CREATE TABLE product_processing_status
               (
                   s3_url_of_product_label VARCHAR(1500) CHARACTER SET latin1,
                   processing_status VARCHAR(50),
                   last_updated_epoch_time BIGINT,
                   pds_node VARCHAR(10),
                   batch_number VARCHAR(100),
                   PRIMARY KEY (s3_url_of_product_label)
               );
             """
    response = rds_data.execute_statement(
        resourceArn=db_clust_arn,
        secretArn=db_secret_arn,
        database='pds_nucleus',
        sql=sql)
    logger.debug(f"Response for create_product_processing_status_table()  : {str(response)}")
