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

1. Some of the libraries used in the ECS containers of PDS Nucleus are platform specific. Therefore, please execute the deployment 
from an Amazon Linux EC2 instance with Architecture 64 bit (x86) with about 120 GB of disk space. In the following points, this EC2 instance is
referred as the "local machine" or "local environment". 

2. An AWS Account with permissions to deploy following AWS services
   - Amazon Managed Workflows for Apache Airflow (MWAA)
   - AWS Security Groups
   - AWS S3 Bucket with relevant bucket policies
   - ECS Cluster and ECS Tasks
   - EFS File System
   - ECR

3. Ability to get AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN for the AWS account

4. Terraform is installed in local environment (This was tested with Terraform v1.5.7. Any higher version should also work)
 - Instructions to install Terraform is available at https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli

5. Python 3.11 or above is installed in local system. Please verify it with the follwing command.
```
python3 --version
```
   
6. A VPC and one or more subnets should be available on AWS (obtain the VPC ID and subnet IDs from AWS console or from the AWS
system admin team of your AWS account)

7. Docker service is installed and running (Instructions to install Docker: [https://docs.docker.com/engine/install/](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-docker.html))

8. PDS Registry (OpenSearch) is accessible from the AWS account which is used to deploy PDS Nucleus)

9. A Cognito User Pool to manage Nucleus users

10. A certificate to be used for the ALB Listener facing Airflow UI


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

4. Create a `terraform.tfvars` file locally under `./terraform/terraform.tfvars` and enter the value for variables specified in `variables.tf` file at `nucleus/terraform/terraform-modules/mwaa-env/variables.tf`. Ensure these values match with your AWS Setup and also the variable value types (ex: string `" "`, number `1`, list(string)`[" "]`, etc). Most of the below values can be obtained by the system admin team of your AWS account.

Note: A sample `terraform.tfvars` file with placeholder values is available at [`terraform/terraform.tfvars.example`](./terraform.tfvars.example) for your reference.

    - venue      : Name of the Cloud venue to deploy PDS Nucleus (E.g: "dev", "test")
    - region     : AWS Region
    - vpc_id     : VPC ID of your AWS VPC
    - subnet_ids : List of Private Subnet IDs to be used for the MWAA
    - auth_alb_subnet_ids : List of Subnet IDs to be used for the Auth ALB
    - vpc_cidr   : VPC CIDR for MWAA (E.g.: "10.1.0.0/16")
    - permission_boundary_for_iam_roles : The name of the permission boundary to be used when creating IAM roles, can be obtained from the MCP System Admins or PDS Engineering Node team
    - permission_boundary_for_iam_roles_arn : The ARN of the permission boundary for IAM roles can be obtained from the MCP System Admins or PDS Engineering Node team
    - database_availability_zones : RDS database availability zones (E.g.: ["us-west-2a"])
    - aws_secretmanager_key_arn : The ARN of aws/secretmanager key obtained from KMS -> AWS managed keys (E.g.: "arn:aws:kms:us-west-2:12345678:key/12345-1234-1234-1234-12345abcd")

    - Set node specific values the following lists in correct order
      - pds_node_names : List of PDS Node names to be supported (E.g.: ["PDS_SBN", "PDS_IMG", "PDS_EN"]).The following node name format should be used.
          - (PDS_ATM, PDS_ENG, PDS_GEO, PDS_IMG, PDS_NAIF, PDS_RMS, PDS_SBN, PSA, JAXA, ROSCOSMOS)
          - Please check https://nasa-pds.github.io/registry/user/harvest_job_configuration.html for PDS Node name descriptions.

      - pds_archive_bucket_names : List of Node specific archive bucket names, usualy in another AWS account (E.g.: ["pds-sbn-archive-dev", "pds-img-archive-dev"])
            - The archive buckets should have S3 bucket permissions to allow the each Node specific `pds_nucleus_ecs_task_role-NODE_NAME` to write data, and the Node specific `pds_nucleus_lambda_execution_role-NODE_NAME` to read data (used by the completion-detection Lambda to determine when a PDS data product has finished being written to the archive bucket).

            The following S3 bucket policy is an example to allow the `pds_nucleus_ecs_task_role-NODE_NAME` role to write to, and the `pds_nucleus_lambda_execution_role-NODE_NAME` role to read from, the NODE_NAME archive bucket. Replace `<account_id_of_aws_account_with_nucleus>`, `NODE_NAME` and `<node-archive-bucket-name>` with the actual values for your environment.
         
   ```json
                    {
                      "Version": "2012-10-17",
                      "Statement": [
                          {
                              "Sid": "AllowECSAccountToPutObjects",
                              "Effect": "Allow",
                              "Principal": {
                                  "AWS": "arn:aws:iam::<account_id_of_aws_account_with_nucleus>:role/pds_nucleus_ecs_task_role-NODE_NAME"
                              },
                              "Action": "s3:PutObject",
                              "Resource": "arn:aws:s3:::<node-archive-bucket-name>/*"
                          },
                          {
                              "Sid": "AllowECSAccountToAbortMultipartUploads",
                              "Effect": "Allow",
                              "Principal": {
                                  "AWS": "arn:aws:iam::<account_id_of_aws_account_with_nucleus>:role/pds_nucleus_ecs_task_role-NODE_NAME"
                              },
                              "Action": "s3:AbortMultipartUpload",
                              "Resource": "arn:aws:s3:::<node-archive-bucket-name>/*"
                          },
                          {
                              "Sid": "AllowLambdaAccountToReadObjects",
                              "Effect": "Allow",
                              "Principal": {
                                  "AWS": "arn:aws:iam::<account_id_of_aws_account_with_nucleus>:role/pds_nucleus_lambda_execution_role-NODE_NAME"
                              },
                              "Action": [
                                  "s3:GetObject",
                                  "s3:ListBucket"
                              ],
                              "Resource": [
                                  "arn:aws:s3:::<node-archive-bucket-name>",
                                  "arn:aws:s3:::<node-archive-bucket-name>/*"
                              ]
                          }
                      ]
                  }
   ```

      - pds_nucleus_opensearch_url : OpenSearch URL to be used with Harvest tool
      - pds_nucleus_opensearch_registry_names : List of Node specific OpenSearch registry names (E.g.: ["pds-nucleus-sbn-registry", "pds-nucleus-img-registry"])
      - pds_nucleus_opensearch_credential_relative_url : Opensearch Credential URL (E.g.: "http://<IP ADDRESS>/AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
      - pds_nucleus_opensearch_collection_arns : List of Node specific OpenSearch Collection ARNs (E.g.: ["arn:aws:aoss:us-west-2:12345678:collection/abcdefgh", "arn:aws:aoss:us-west-2:12345678:collection/abcdefgh"])
      - pds_nucleus_opensearch_cognito_identity_pool_ids : List of Node specific OpenSearch Cognito Identity Pool IDs (E.g.: ["us-west-2:12345-abcd-abcd-abcd-1234abcdef", "us-west-2:12345-abcd-abcd-abcd-1234abcdef"])
      - pds_nucleus_harvest_replace_prefix_with_list : List of Node specific harvest replace-with strings (E.g.: ["s3://pds-sbn-nucleus-staging","s3://pds-img-nucleus-staging"])
      - pds_nucleus_harvest_replace_prefix_list : List of Node specific EFS path prefixes to replace in harvest config (E.g.: ["/mnt/data/pds-sbn-staging-dev", "/mnt/data/pds-img-staging-dev"])

    - pds_registry_loader_harvest_version : Docker image version tag for nasapds/registry-loader (E.g.: "1.3.2", "latest")
    - pds_validate_version : Docker image version tag for nasapds/validate (E.g.: "latest")
    - airflow_env_name: Name of the Nucleus Airflow environment (E.g.: "pds-nucleus-airflow-env")
    - mwaa_dag_s3_bucket_name : S3 Bucket name to keep Airflow DAG files (E.g.: pds-nucleus-airflow-dags-bucket-mcp-test)
    - pds_nucleus_staging_bucket_name_postfix : Postfix of the S3 Bucket name to keep PDS staging data files (E.g.: staging-mcp-dev)
    - pds_nucleus_config_bucket_name_postfix : Postfix of the S3 Bucket name to keep temporary configurations (E.g.: pds-nucleus-config-mcp-test)
    - pds_shared_logs_bucket_name : Name of the shared PDS logs S3 bucket (E.g.: pds-logs-dev, pds-logs-prod)

    - pds_nucleus_default_airflow_dag_id : The default example DAG to be included for testing (E.g.: pds-basic-registry-load-use-case)
    - pds_nucleus_s3_backlog_processor_dag_id : The DAG ID of the S3 Backlog Processer DAG (E.g: pds-nucleus-s3-backlog-processor)

    - cognito_user_pool_id : The ID of the Cognito user pool which is used to create Nucleus user accounts
    - cognito_user_pool_domain : Cognito domain name of the Cognito user pool which is used to create Nucleus user accounts
    - auth_alb_listener_certificate_arn : ARN of the certificate to be used for the ALB Listener facing Airflow UI
    - nucleus_cloudfront_origin_hostname : Hostname of the Nucleus Cloudfront origin (E.g: pds-sit.mcp.nasa.gov)
    - aws_elb_account_id_for_the_region : The standard ELB account ID for the AWS region. For US West (Oregon), this is  797873946194. Read more at https://docs.aws.amazon.com/elasticloadbalancing/latest/application/enable-access-logging.html)

    - Mandatory tag variables
      - tag_tenant : Owner Discipline Node (E.g.: en, sbn, img, atm etc.)
      - tag_venue : Environment (E.g.: pds-cds-dev, pds-cds-prod)
      - tag_component : Component name (E.g.: nucleus)
      - tag_cicd : Deployment method (E.g.: iac, cd, etc.)
      - tag_managedby : PDS Team email address responsible for managing the deployment


> Note: `terraform.tfvars` is only used to test with your configuration with the actual values in your AWS account. This file will not be uploaded to GitHub as it's ignored by Git. Once testing is completed successfully work with your admin to get the values for these tested variables updated via GitHub secrets, which are dynamically passed in during runtime.

A sample file with placeholder values for all of the above variables is checked into the repository at
[`terraform/terraform.tfvars.example`](./terraform.tfvars.example). Copy it to `terraform.tfvars` and replace the
placeholder values with the actual values for your AWS environment:

```shell
cp terraform.tfvars.example terraform.tfvars
```


5. Make sure to have an S3 bucket available in the AWS account to keep Terraform remote state. 
The name of the S3 bucket should match with the bucket name in the `terraform/backend.tf` file. 
If a bucket to keep the Terraform remote state is not available, please create a new bucket.

6. Initialize Terraform working directory.

```shell
terraform init
```

7. [Optional] Check the Terraform plan to see the changes to be applied.

```shell
terraform plan
```

8. Deploy Nucleus baseline system using Terraform apply.

Note: The following command may fail due to AWS credential expiry. Try the following command multiple times with new AWS credentials.

```shell
terraform apply
```

9. Wait for `terraform apply` command to be completed. If it fails due to expiration of AWS credentials, please provide a new set of AWS credentials and execute `terraform apply` again.

10. Note the `pds_nucleus_airflow_ui_url` printed as an output at the end of the `terraform apply` command results. 

Example:

```shell
Outputs:

pds_nucleus_airflow_ui_url = "https://pds-nucleus-12345678.us-west-2.elb.amazonaws.com/aws_mwaa/aws-console-sso"
```

11. Login to the AWS Console with your AWS Account.

12. Make sure that the correct AWS Region is selected and search for "Managed Apache Airflow".

13. Visit the "Managed Apache Airflow" (Amazon MWAA) page and check the list of environments. 

14. Find the relevant Amazon MWAA environment (Default name: PDS-Nucleus-Airflow-Env) and click on
    Open Airflow UI link to open the Airflow UI.

15. The DAGs can be added to the Airflow by uploading Airflow DAG files to the DAG folder of S3 bucket
configured as `mwaa_dag_s3_bucket_name` in the `terraform.tfvars` file.


## Steps to Access Nucleus Airflow UI With Cognito Credentials

Only some users have direct access to AWS and those users can access Airflow UI as explained in the step 9 to 12
in the above section. However, there is another way to access Airflow UI using a Cognito account as follows.

### Approach 1: Using the Web Based Login

1. Make sure you have a Cognito user created in the Cognito user pool with required role (Cognito group). The PDS engineering node team can
   help with this.

2. Access the pds_nucleus_airflow_ui_url obtained in the step 9. of the section above.

Example:

```shell
Outputs:

pds_nucleus_airflow_ui_url = "https://pds-nucleus-12345678.us-west-2.elb.amazonaws.com/aws_mwaa/aws-console-sso"
```

3. Use the Cognito username and password to login.


### Approach 2: Using a Web Token

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
