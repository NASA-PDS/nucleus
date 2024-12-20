# PDS Nucleus Baseline Deployment

The Terraform scripts in this directory deploy a minimum viable product (MVP) of PDS Nucleus data pipeline
system on AWS Cloud. Currently, Nucleus is based on Amazon Managed Workflows for Apache Airflow (MWAA).
Therefore, as a result of the Terraform scripts in this directory following things will be created.
- AWS Security Group for MWAA
- S3 Bucket for DAGs - AWS S3 Bucket with relevant bucket policies to keep Airflow DAG files and Python requirements file
- S3 Bucket for Configs - AWS S3 Bucket to keep temporary configurations related with PDS data to be processed
- S3 Buckets for Staging- AWS S3 Buclet to keep the PDS staging data (will be copied by the PDS Data Upload Manager)
- Python requirements.txt file to introduce the additional Python packages required by DAGs
- An example DAG file with a basic PDS Registry use case
- Amazon Managed Workflows for Apache Airflow (MWAA)
- RDS MySQL database to determine the completion of PDS Data products received
- Lambda functions to determine the completion of PDS Data products received and trigger PDS Nucleus workflow executions
- ECS Cluster to execute PDS ECS tasks
- ECS Task definitions


## Prerequisites to Deploy Nucleus Baseline System

1. An AWS Account with permissions to deploy following AWS services
   - Amazon Managed Workflows for Apache Airflow (MWAA)
   - AWS Security Groups
   - AWS S3 Bucket with relevant bucket policies
   - ECS Cluster and ECS Tasks
   - EFS File System
   - ECR

2. Ability to get AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN for the AWS account

3. Terraform is installed in local environment (This was tested with Terraform v1.5.7. Any higher version should also work)
 - Instructions to install Terraform is available at https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli

4. A VPC and one or more subnets should be available on AWS (obtain the VPC ID and subnet IDs from AWS console or from the AWS
system admin team of your AWS account)

5. Docker service is installed and running (Instructions to install Docker: https://docs.docker.com/engine/install/)

6. PDS Registry (OpenSearch) is accessible from the AWS account which is used to deploy PDS Nucleus)


## Steps to Deploy the PDS Nucleus Baseline System

1. Checkout the https://github.com/NASA-PDS/nucleus repository.

```shell
git clone https://github.com/NASA-PDS/nucleus.git
```

2. Open a terminal and change current working directory to the `nucleus/terraform` directory.

```shell
cd nucleus/terraform
```

3. Set the following environment variables in terminal window using export command.
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_SESSION_TOKEN
    - AWS_DEFAULT_REGION
    - AWS_ACCOUNT_ID

4. Create a `terraform.tfvars` file locally under `./terraform/terraform.tfvars` and enter the value for variables specified in `variables.tf` file at `nucleus/terraform/terraform-modules/mwaa-env/variables.tf`. Ensure these values match with your AWS Setup and also the variable value types (ex: string `" "`, number `1`, list(string)`[" "]`, etc). Most of the below values can be obtained by the system admin team of your AWS account.

Note:  Examples of `terraform.tfvars` files are available at `terraform/variables` directory for your reference.

    - env        : Name of the Cloud environment to deploy PDS Nucleus (E.g: "mcp-dev", "mcp-test")
    - region     : AWS Region
    - vpc_id     : VPC ID of your AWS VPC
    - subnet_ids : List of Private Subnet IDs to be used for the MWAA
    - vpc_cidr   : VPC CIDR for MWAA (E.g.: "10.1.0.0/16")
    - permission_boundary_for_iam_roles : The permission boundary for IAM roles can be obtained from the MCP System Admins or PDS Engineering Node team
    - database_availability_zones : RDS database availability zones (E.g.: ["us-west-2a"])
    - aws_secretmanager_key_arn : The ARN of aws/secretmanager key obtained from KMS -> AWS managed keys (E.g.: "arn:aws:kms:us-west-2:12345678:key/12345-1234-1234-1234-12345abcd")

    - Set node specific values the following lists in correct order
      - pds_node_names = List of PDS Node names to be supported (E.g.: ["PDS_SBN", "PDS_IMG", "PDS_EN"]).The following node name format should be used.
          - (PDS_ATM, PDS_ENG, PDS_GEO, PDS_IMG, PDS_NAIF, PDS_RMS, PDS_SBN, PSA, JAXA, ROSCOSMOS)
          - Please check https://nasa-pds.github.io/registry/user/harvest_job_configuration.html for PDS Node name descriptions.
      - pds_nucleus_opensearch_urls : List of Node specific OpenSearch URLs (E.g.: ["https://abcdef.us-west-2.aoss.amazonaws.com", "https://opqrst.us-west-2.aoss.amazonaws.com"])
      - pds_nucleus_opensearch_credential_relative_url : Opensearch Credential URL (E.g.: "http://<IP ADDRESS>/AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
      - pds_nucleus_harvest_replace_prefix_with_list : List of harvest replace with strings (E.g.: ["s3://pds-sbn-nucleus-staging","s3://pds-img-nucleus-staging"])
      
    - pds_nucleus_harvest_replace_prefix_with : Prefix to replace in PDS Harvest tool
    - airflow_env_name: Name of the Nucleus Airflow environment (E.g.: "pds-nucleus-airflow-env")
    - mwaa_dag_s3_bucket_name : S3 Bucket name to keep Airflow DAG files (E.g.: pds-nucleus-airflow-dags-bucket-mcp-test)
    - pds_nucleus_staging_bucket_name_postfix : Postfix of the S3 Bucket name to keep PDS staging data files (E.g.: staging-mcp-dev)
    - pds_nucleus_hot_archive_bucket_name_postfix : Postfix of the S3 Bucket name to keep PDS hot archive data files (E.g.: archive-hot-mcp-dev)
    - pds_nucleus_cold_archive_bucket_name_postfix : Postfix of the S3 Bucket name to keep PDS cold archive data files (E.g.: archive-cold-mcp-dev)
    - pds_nucleus_config_bucket_name  : S3 Bucket name to keep temporary configurations (E.g.: pds-nucleus-config-mcp-test)
    - pds_nucleus_default_airflow_dag_id : The default example DAG to be included for testing (E.g.: pds-basic-registry-load-use-case)
    - pds_registry_loader_harvest_task_role_arn: An IAM role which is associated with a Cognito user group


> Note: `terraform.tfvars` is only used to test with your configuration with the actual values in your AWS account. This file will not be uploaded to GitHub as it's ignored by Git. Once testing is completed successfully work with your admin to get the values for these tested variables updated via GitHub secrets, which are dynamically passed in during runtime.

```
# Example terraform.tfvars

env                               = "mcp-test"
region                            = "us-west-2"
vpc_id                            = "vpc-12345678"
subnet_ids                        = ["subnet-123456789", "subnet-987654321"]
vpc_cidr                          = "10.2.0.0/16"
permission_boundary_for_iam_roles = "permission_boundary_role_name"
database_availability_zones       = ["us-west-2a"]
aws_secretmanager_key_arn         = "arn:aws:kms:us-west-2:12345678:key/12345-1234-1234-1234-12345abcd"


# Set node specific values the following lists in correct order. For the list of node names
# the following node name format should be used.
# (PDS_ATM, PDS_ENG, PDS_GEO, PDS_IMG, PDS_NAIF, PDS_RMS, PDS_SBN, PSA, JAXA, ROSCOSMOS)
# Please check https://nasa-pds.github.io/registry/user/harvest_job_configuration.html for PDS Node name descriptions.

pds_node_names                                 = ["PDS_SBN", "PDS_IMG"]
pds_nucleus_opensearch_urls                    = ["https://abcdef.us-west-2.aoss.amazonaws.com", "https://opqrst.us-west-2.aoss.amazonaws.com"]
pds_nucleus_opensearch_credential_relative_url = "http://<IP ADDRESS>/AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"
pds_nucleus_harvest_replace_prefix_with_list   = ["s3://pds-sbn-nucleus-staging", "s3://pds-img-nucleus-staging"]


airflow_env_name                             = "pds-nucleus-airflow-env"
mwaa_dag_s3_bucket_name                      = "pds-nucleus-airflow-dags-bucket-mcp-dev"
pds_nucleus_staging_bucket_name_postfix      = "staging-mcp-dev"
pds_nucleus_hot_archive_bucket_name_postfix  = "archive-hot-mcp-dev"
pds_nucleus_cold_archive_bucket_name_postfix = "archive-cold-mcp-dev"
pds_nucleus_config_bucket_name               = "pds-nucleus-config-mcp-dev"

pds_nucleus_default_airflow_dag_id = "pds-basic-registry-load-use-case"

pds_registry_loader_harvest_task_role_arn = "arn:aws:iam::12345678:role/harvest-task-role"
```


5. Make sure to have an S3 bucket available in the AWS account to keep Terraform remote state. 
The name of the S3 bucket should match with the bucket name in the `terraform/backend.tf` file. 
If a bucket to keep the Terraform remote state is not available, please create a new bucket.

6. Initialize Terraform working directory.

```shell
terraform init
```

6. [Optional] Check the Terraform plan to see the changes to be applied.

```shell
terraform plan
```

7. Deploy Nucleus baseline system using Terraform apply.

Note: The following command may fail due to AWS credential expiry. Try the following command multiple times with new AWS credentials.

```shell
terraform apply
```

8. Wait for `terraform apply` command to be completed. If it fails due to expiration of AWS credentials, please provide a new set of AWS credentials and execute `terraform apply` again.

9. Login to the AWS Console with your AWS Account.

10. Make sure that the correct AWS Region is selected and search for "Managed Apache Airflow".

11. Visit the "Managed Apache Airflow" (Amazon MWAA) page and check the list of environments.

12. Find the relevant Amazon MWAA environment (Default name: PDS-Nucleus-Airflow-Env) and click on
    Open Airflow UI link to open the Airflow UI.

13. The DAGs can be added to the Airflow by uploading Airflow DAG files to the DAG folder of S3 bucket
configured as `mwaa_dag_s3_bucket_name` in the `terraform.tfvars` file.

14. Go to the AWS Secret manager (https://us-west-2.console.aws.amazon.com/secretsmanager/listsecrets?region=us-west-2) and locate the secrets in the following format.
    - pds/nucleus/opensearch/creds/<PDS NODE NAME>/user
    - pds/nucleus/opensearch/creds/<PDS NODE NAME>/password
   
    E.g.: 
      - pds/nucleus/opensearch/creds/PDS_IMG/user
      - pds/nucleus/opensearch/creds/PDS_SBN/user
      - pds/nucleus/opensearch/creds/PDS_IMG/password
      - pds/nucleus/opensearch/creds/PDS_SBN/password

15. Obtain the Opensearch username and password for each PDS Node and update the above secrets with relevant usernames and passwords.
      - To update a secret, click on a secret -> Retrieve secret value -> Edit -> Save 


15. Use the PDS Data Upload Manager (DUM) tool to upload files to pds_nucleus_staging_bucket.


## Steps to Access Nucleus Airflow UI With Cognito Credentials

Only some users have direct access to AWS and those users can access Airflow UI as explained in the step 9 to 12
in the above section. However, there is another way to access Airflow UI using a Cognito account as follows.

1. Make sure you have a Cognito user created in the Cognito user pool with required role (Cognito group). The PDS engineering node team can 
help with this.

2. Download the `get-airflow-ui-webtoken.py` python script from https://github.com/NASA-PDS/nucleus/blob/airflow-ui-web-token/utils/get-airflow-ui-webtoken.py

3. Create a python virtual environment as follows. 

```shell
python3 -m venv venv   
```

4. Activate python virtual environment.

```shell
source venv/bin/activate
```

5. Install boto3

```shell
 pip install boto3 
```

6. Execute the `get-airflow-ui-webtoken.py` python script and provide the Cognito username and password when prompted.

```shell
python get-airflow-ui-webtoken.py
```

7. Copy the generated Nucleus Airflow UI web token and paste that in a webbrowser address bar to access the Airflow UI.


## Steps to Uninstall the PDS Nucleus Baseline System

1. Open a terminal and change current working directory to the `nucleus/terraform` directory.

```shell
cd nucleus/terraform
```

2. Uninstall Nucleus baseline system using Terraform destroy.

```shell
terraform destroy
```

3. The above command will fail to remove the non-empty S3 buckets (expected behaviour). Note the S3 bucket names failed to delete in 
the output of the above `terraform destroy` command and empty those S3 buckets manually as explained in 
https://docs.aws.amazon.com/AmazonS3/latest/userguide/empty-bucket.html.

4. Execute the following command again to remove the remaining S3 buckets.

```shell
terraform destroy
```

## Troubleshooting


- Error saving credentials: error storing credentials - err: exec: "docker-credential-desktop": executable file not found in $PATH, out: ``

check: https://stackoverflow.com/questions/67642620/docker-credential-desktop-not-installed-or-not-available-in-path
