# PDS Nucleus Baseline Deployment

The Terraform scripts in this directory deploy a minimum viable product (MVP) of PDS Nucleus data pipeline
system on AWS Cloud. Currently, Nucleus is based on Amazon Managed Workflows for Apache Airflow (MWAA).
Therefore, as a result of the Terraform scripts in this directory following things will be created.
- AWS Security Group for MWAA
- AWS S3 Bucket with relevant bucket policies to keep Airflow DAG files and Python requirements file
- Dags directory in S# bucket to keep Airflow DAG files
- Python requirements.txt file to introduce the additional Python packages required by DAGs
- Amazon Managed Workflows for Apache Airflow (MWAA)


Note: In addition to the above components, there are Terraform modules, container definitions and a DAG file
included to deploy PDS Registry related ECS tasks, a DAG and an EFS file system that can be used to demonstrate
an example PDS Registry use case. However, these additional components are not part of the MVP of
PDS Nucleus data pipeline. These PDS Registry related terraform modules are still under development (not part of the PDS Nucleus Baseline Deployment task)
and are kept disabled in the main.tf terraform file.


## Prerequisites to Deploy Nucleus Baseline System

1. An AWS Account with permissions to deploy following AWS services
   - Amazon Managed Workflows for Apache Airflow (MWAA)
   - AWS Security Groups
   - AWS S3 Bucket with relevant bucket policies
   - ECS Cluster and ECS Tasks
   - EFS File System
   - ECR (at least readonly access)

2. Ability to get AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN for the AWS account

3. Terraform is installed in local environment (This was tested with Terraform v1.3.7. Any higher version should also work)
 - Instructions to install Terraform is available at https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli

4. A VPC and one or more subnets should be available on AWS (obtain the VPC ID and subnet IDs from AWS console or from the AWS
system admin team of your AWS account)

5. An EFS Filesystem is created with the following access points (Please note the File system ID and access point IDs to be used later in `terraform.tfvars` file).
   * registry_loader_scripts_access_point_id - with name `scripts` and with path `/registry/docker/scripts` 
   * registry_loader_default_configs_access_point_id - with name `default-config` and with path `/registry/docker/default-config`


## Steps to Deploy the PDS Nucleus Baseline System

1. Checkout the https://github.com/NASA-PDS/nucleus repository.

```shell
git clone https://github.com/NASA-PDS/nucleus.git
```

2. Open a terminal and change current working directory to the `nucleus/terraform` directory.

```shell
cd nucleus/terraform
```

3. Set following environment variables in terminal window
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_SESSION_TOKEN
    - AWS_DEFAULT_REGION

4. Create a `terraform.tfvars` file locally under `./terraform/terraform.tfvars` and enter the value for variables specified in `variables.tf` file at `nucleus/terraform/terraform-modules/mwaa-env/variables.tf`. Ensure these values match with your AWS Setup and also the variable value types (ex: string `" "`, number `1`, list(string)`[" "]`, etc). Most of the below values can be obtained by the system admin team of your AWS account.

    - vpc_id:  VPC ID of your AWS VPC
    - vpc_cidr: VPC CIDR for MWAA (E.g.: "10.1.0.0/16")
    - nucleus_security_group_ingress_cidr: List of ingress CIDRs for the Nucleus Security Group to be created (E.g.: "10.21.240.0/20")
    - subnet_ids: List of Subnet IDs to be used for the MWAA
    - airflow_execution_role: Airflow AWS Execution Role
    - efs_file_system_id: The File system ID of the EFS volume mentioned under the prerequisites 
    - registry_loader_scripts_access_point_id: The access point ID of the `scripts` access point of EFS volume mentioned under the prerequisites
    - registry_loader_default_configs_access_point_id: The access point ID of the `default-config` access point of EFS volume mentioned under the prerequisites
    - task_role_arn = "arn:aws:iam::<account-id>:role/pds-nucleus-mwaa-execution-role"
    - execution_role_arn = "arn:aws:iam::<account-id>:role/pds-nucleus-mwaa-execution-role"
    - mwaa_dag_s3_bucket_name = "pds-nucleus-airflow-dags-bucket-mcp-dev"

> Note: `terraform.tfvars` is only used to test with your configuration with the actual values in your AWS account. This file will not be uploaded to GitHub as it's ignored by Git. Once testing is completed successfully work with your admin to get the values for these tested variables updated via GitHub secrets, which are dynamically passed in during runtime.

```
# Example terraform.tfvars

region = "us-west-2"
vpc_id = "vpc-12345678"
subnet_ids = ["subnet-12121212121","subnet-32323232323223"]
vpc_cidr = "10.1.0.0/16"
nucleus_security_group_ingress_cidr = ["0.0.0.0/0"]
airflow_execution_role = "arn:aws:iam::<account-id>:role/pds-nucleus-mwaa-execution-role"
efs_file_system_id = "fs-123232"
registry_loader_scripts_access_point_id = "fsap-2121213232"
registry_loader_default_configs_access_point_id = "fsap-1212323"
task_role_arn = "arn:aws:iam::<account-id>:role/pds-nucleus-mwaa-execution-role"
execution_role_arn = "arn:aws:iam::<account-id>:role/pds-nucleus-mwaa-execution-role"
mwaa_dag_s3_bucket_name = "pds-nucleus-airflow-dags-bucket-mcp-dev"
```

5. Initialize Terraform working directory.

```shell
terraform init
```

6. [Optional] Check the Terraform plan to see the changes to be applied.

```shell
terraform plan
```

7. Deploy Nucleus baseline system using Terraform apply.

```shell
terraform apply
```

8. Login to the AWS Console with your AWS Account.

9. Make sure that the correct AWS Region is selected and search for "Managed Apache Airflow".

10. Visit the "Managed Apache Airflow" (Amazon MWAA) page and check the list of environments.

11. Find the relevant Amazon MWAA environment (Default name: PDS-Nucleus-Airflow-Env) and click on
    Open Airflow UI link to open the Airflow UI.

12. The DAGs can be added to the Airflow by uploading Airflow DAG files to the DAG folder of S3 bucket
configured in the `mwaa_env.tf` file (Default S3 Bucket name: nucleus-airflow-dags-bucket).
