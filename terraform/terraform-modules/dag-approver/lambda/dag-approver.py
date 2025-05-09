import boto3
import io
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

strings_to_avoid_env = os.environ.get('STRINGS_TO_AVOID')
pds_nucleus_airflow_dag_bucket = os.environ.get('PDS_NUCLEUS_AIRFLOW_DAG_BUCKET_NAME')


def lambda_handler(event, context):
    try:
        s3 = boto3.client('s3')
        s3_bucket = event['Records'][0]['s3']['bucket']['name']
        s3_key = event['Records'][0]['s3']['object']['key']

        logger.info(f"File copied to: s3://{s3_bucket}/{s3_key}")

        if not s3_key.startswith("To-Be-Approved-DAGs/"):
            logger.error(f"File was not copied to s3://{s3_bucket}/To-Be-Approved-DAGs/. Please copy the new DAG file to the s3://{s3_bucket}/To-Be-Approved-DAGs/")
            return

        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        file_content = response['Body'].read()

        try:
            file_content_str = file_content.decode('utf-8')
        except UnicodeDecodeError:
            logger.warning("File content is not UTF-8 encoded.  Will not search for strings.")
            file_content_str = None

        search_strings = [s.strip() for s in strings_to_avoid_env.split(',')] if strings_to_avoid_env else []

        if file_content_str:
            found_strings = [s for s in search_strings if s in file_content_str]

            if found_strings:
                logger.info(f"Found strings: {found_strings}")
                rejected_dag_key = f"Rejected-DAGs/{s3_key.split('/')[-1]}"
                rejected_log_key = f"Rejected-DAGs/{s3_key.split('/')[-1]}.rejected.log"
                to_be_approved_dag = {'Bucket': s3_bucket, 'Key': s3_key}
                s3.copy_object(CopySource=to_be_approved_dag, Bucket=s3_bucket, Key=rejected_dag_key)
                logger.info(f"File moved to s3://{s3_bucket}/{rejected_dag_key}")

                s3.put_object(Bucket=s3_bucket, Key=rejected_log_key, Body=f"DAG: {s3_key} is rejected due to restricted string(s): {', '.join(found_strings)}.")
                logger.info(f"Rejection log file created at s3://{s3_bucket}/{rejected_log_key}")
                s3.delete_object(Bucket=s3_bucket, Key=s3_key)
                logger.info(f"Original file deleted: s3://{s3_bucket}/{s3_key}")
            else:
                approved_dag_key = f"Approved-DAGs/{s3_key.split('/')[-1]}"
                nucleus_dag_key = f"dags/PDS_SBN/{s3_key.split('/')[-1]}"
                to_be_approved_dag = {'Bucket': s3_bucket, 'Key': s3_key}

                s3.copy_object(CopySource=to_be_approved_dag, Bucket=s3_bucket, Key=approved_dag_key)
                logger.info(f"File moved to s3://{s3_bucket}/{approved_dag_key}")

                s3.copy_object(CopySource=to_be_approved_dag, Bucket=pds_nucleus_airflow_dag_bucket, Key=nucleus_dag_key)
                logger.info(f"File copied to s3://{pds_nucleus_airflow_dag_bucket}/{nucleus_dag_key}")

                s3.delete_object(Bucket=s3_bucket, Key=s3_key)
                logger.info("The DAG is approved and deployed to Nucleus")
                logger.info(f"Original file deleted: s3://{s3_bucket}/{s3_key}")
        else:
            logger.warning("Skipping string search because file content could not be decoded.")

    except Exception as e:
        logger.error(f"Error processing S3 event: {e}")
        raise
