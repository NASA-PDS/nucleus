Prerequisites




1) An EC2 instance to execute terraform 

     - Amazon Linux EC2 instance with Architecture 64 bit (x86) - it is recommended to use the MCP Amazon Linux 2023 EKS-Optimized 1.34 20260218T173831

 (t2.large), because it has Python 3.x preinstalled properly.

2) Intall terraform in EC2
       

sudo yum update -y
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
sudo yum install -y terraform
terraform -version




3) Install docker in EC2


sudo amazon-linux-extras enable docker
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo systemctl status docker
sudo usermod -aG docker $(whoami)



Make sure to logout and login to EC2 instance to apply above changes.




4) Update the s3:PutObject permissions of S3 bucket called pds-logs-<venue> (E.g.: pds-logs-prod, pds-logs-dev) by adding resource "arn:aws:s3:::pds-logs-<venue>/nucleus/*" to the list of resources as follows. Do not delete any existing statements.




 

{
   "Effect": "Allow",
   "Principal": {
        "AWS": "arn:aws:iam::<PDS-LOGGING-ACCOUNT-ID>:root"
     },
   "Action": "s3:PutObject",
   "Resource": [ 
         "arn:aws:s3:::pds-logs-prod/registry-api-lb/AWSLogs/<ALB-ACCOUNT-ID>/*",
         "arn:aws:s3:::pds-logs-prod/nucleus/*"
    ]
}

 

4b) (NEW) Nucleus does not create the staging or archive buckets (`pds_archive_bucket_names`) - they must already exist and be readable/writable by Nucleus's IAM roles. If a bucket is in the same AWS account as Nucleus, no bucket policy is needed (access is granted via the IAM role policies in `terraform-modules/iam/iam.tf`). If a bucket is in a different AWS account (e.g. a discipline node's own account), add a bucket policy granting the following to the relevant `pds_nucleus_ecs_task_role-<NODE>` / `pds_nucleus_harvest_ecs_task_role-<NODE>` principals: `s3:GetBucket*`, `s3:GetObject*`, `s3:List*`, `s3:PutObject`, `s3:PutObjectTagging`.

5) A specific or new discipline node might need to be configured by the Dev team so that the required OpenSearch test index are available, see https://nasa-pds.github.io/registry/admin/create_reg.html and Registry.




6) In the public subnets that will be used for the Nucleus ALB, make sure to make the following port range open (This was based on an advice given by AWS, to use Cognito with an ALB).

Custom TCP

	

TCP (6)

	

1024 - 65535

	

0.0.0.0/0

	

Allow



7) IAM permissions (NEW): Deploying requires two AWS identities - an admin identity with IAM-creation permissions (for Step 0 below), and a developer identity with the scoped policy in `terraform/DEVELOPER_IAM_POLICY.md` (no IAM-creation permissions needed) for the rest of the deploy.

For more information,  https://github.com/NASA-PDS/nucleus/blob/main/terraform/README.md#prerequisites-to-deploy-nucleus-baseline-system




Deployment Procedure




Note: If terraform fails for any reason, first try to apply new AWS credentials, use terraform init  followed by terraform apply . Repeat terraform  init  and terraform apply  few times before other troubleshooting. 



0) Apply IAM roles first (NEW): Using the admin identity, run `terraform init` and `terraform apply -target=module.iam` once to create the `pds_nucleus_*` IAM roles. Only needs to be re-run when `terraform-modules/iam/iam.tf` changes. All steps below can then be run by a developer identity (see `terraform/DEVELOPER_IAM_POLICY.md`).


Deploy baseline system: https://github.com/NASA-PDS/nucleus/tree/main/terraform#steps-to-deploy-the-pds-nucleus-baseline-system.
For step 4, use the approprepate terraform.tfvars  file below (select based on your AWS account such as MCP Dev, MCP Prod)  and save it as ./terraform/terraform.tfvars  file.

Make sure to use appropriate Tags in the terraform.tfvars  file such as tag_managedby and tag_component.

Important Note: PDS Nucleus system has a large number of AWS resources and `terraform apply` command can take a long time (30 minutes to over 1 hour) to complete. Also, it can fail due to network delays or AWS Credential expiration. If there is a failure, please enter new AWS Credentials and execute `terraform apply` command again. There were situations, it was required to execute `terraform apply` multiple times due to network delays and AWS credential expiration.

Some of the failures may even not look like an expiry (E.g.:  Error running command './terraform-modules/ecs-ecr/docker/deploy-ecr-images.sh': exit status 127.) 

If you receive A group with the name already exists . error, execute terraform init  again followed by terraform apply .




Provide nucleus deployed URL to Dev team: Make sure to note the `pds_nucleus_airflow_ui_url` printed as an output at the end of the `terraform apply` command results and share it with the Dev team. 

Example:


Outputs:

pds_nucleus_airflow_ui_url = "https://pds-nucleus-12345678.us-west-2.elb.amazonaws.com:4443/aws_mwaa/aws-console-sso"




Plug nucleus to a staging S3 bucket: Create event notification in staging S3 bucket (this step was originally automated in terraform. However, in MCP Prod a staging S3 bucket is already available and it is safer to do this step manually to avoid issues).

             For each staging bucket (E.g: pds-sbn-staging-prod in MCP Prod)

Visit the the staging S3 bucket in AWS Console under S3 buckets.
Go to staging S3 bucket properties.
Under Event notifications → Create event notification.
Given any name to event name such as "File copy event".
Under Event types → Select the check box forAll object create events (s3:ObjectCreated:*).
Under Destination → Select SQS queue.
Under Specify SQS queue → Choose from your SQS queues → Select pds-nucleus-files-to-save-in-database-<NODE NAME> (E.g.: pds-nucleus-files-to-save-in-database-PDS_SBN)
Save changes.

      4. Add newly created pds_nucleus_harvest_ecs_task_role tasks role(s) to OpenSearch Data Access Control: 

              a.  Visit the  Amazon OpenSearch Service → Serverless: Security → Data access control → pds-mcp-<venue>-data-access (E.g.: pds-mcp-prod-data-access).

              b. Press Edit in top right corner of the page.

              c. Under the Rule that has "Read Write Access", add the newly created pds_nucleus_harvest_ecs_task_role(s) as a Principle (E.g.: pds_nucleus_harvest_ecs_task_role-PDS_SBN)

              d. Save changes.

      


User Accounts and Access Permissions Setup

Visit nucleus-dum-cognito-user-pool Cognito user pool in AWS Console ( Amazon Cognito-> User pools → nucleus-dum-cognito-user-pool )
Add a user  (Users menu - > Create user → Enter user name and email → Select to send email invitation → Mark email address as verified → Generate a password → Create user)
Add the created user to PDS_NUCLEUS_AIRFLOW_VIEWER Cognito user group (Click on the user name in list of users → Add user to group → Add to PDS_NUCLEUS_AIRFLOW_VIEWER)
Dev Init Setup
Login to the AWS Console with your AWS Account.
Make sure that the correct AWS Region is selected and search for "Managed Apache Airflow".
Visit the "Managed Apache Airflow" (Amazon MWAA) page and check the list of environments. 
Find the relevant Amazon MWAA environment (Default name: PDS-Nucleus-Airflow-Env) and click on
Open Airflow UI link to open the Airflow UI.
Make sure if there is a DAG available and enable the DAG (toggle button near DAG name) if it is in disable status.




Configure a user friendly URL with CloudFront


             CloudFront Setup for Nucleus




Uninstalling Nucleus 


The Terraform state of Nucleus is kept in an S3 bucket. Therefore, it is possible to easily destroy the Nucleus environment created using Terraform as follows, even from a different computer.

 1. Make sure to use the appropriate terraform.tfvars  file below (select based on your AWS account such as MCP Dev, MCP Prod)  and save it as ./terraform/terraform.tfvars  file.

 2. Destroy the baseline Nucleus system: https://github.com/NASA-PDS/nucleus/tree/main/terraform#steps-to-uninstall-the-pds-nucleus-baseline-system

 Note: A developer-scoped identity can't delete the `pds_nucleus_*` IAM roles. For a full teardown, also run `terraform destroy -target=module.iam` with the admin identity.




 

Smoke Test Procedure
Obtain the value of `pds_nucleus_airflow_ui_url`  from Step 4 of the deployment procedure above.
Access the URL presented as pds_nucleus_airflow_ui_url  in a web browser (Chrome web browser is preferred).
Use the Cognito username and password created in "User Accounts and Access Permissions Setup" above to login.
Observe the available DAG.
Download the SBN CSS test data zip from the SBN CSS Test Data below and extract ZIP file to a local machine.
Use the PDS Data Upload Manager  tool (https://github.com/NASA-PDS/data-upload-manager) to upload the SBN CSS test data to the staging S3 bucket (pds-sbn-staging-prod in MCP Prod).
Alternatively you can directly upload the SBN CSS test data to staging S3 bucket, if PDS Data Upload Manager tool is unavailable.
Wait for 2 minutes and observe the DAG progress on Airflow UI.
Make sure the whole workflow in the DAG is completed with green color tasks.




terraform.tfvars (for MCP Dev)
venue                                 = "dev"
region                                = "us-west-2"
vpc_id                                = "vpc-02f8cc4962d6f8dc6"
subnet_ids                            = ["subnet-07833269aab07a81f", "subnet-06f9e015c018c9b38"]
auth_alb_subnet_ids                   = ["subnet-0930e42eff2f4917a", "subnet-07c14be78d855bdea"]
vpc_cidr                              = "10.2.0.0/16"
permission_boundary_for_iam_roles     = "mcp-tenantOperator-APIG"
permission_boundary_for_iam_roles_arn = "arn:aws:iam::123456789012:policy/mcp-tenantOperator-APIG"
database_availability_zones           = ["us-west-2a"]
aws_secretmanager_key_arn             = "arn:aws:kms:us-west-2:123456789012:key/e4122ffc-cc8c-4be5-af12-25da8d5eb123"

# Set node specific values the following lists in correct order. For the list of node names
# the following node name format should be used.
# (PDS_ATM, PDS_ENG, PDS_GEO, PDS_IMG, PDS_NAIF, PDS_RMS, PDS_SBN, PSA, JAXA, ROSCOSMOS)

pds_node_names                                   = ["PDS_SBN", "PDS_IMG"]
pds_archive_bucket_names                         = ["pds-sbn-archive-hot-test", "pds-img-archive-prod"]
pds_nucleus_opensearch_url                       = "https://p5qmxrldysl1gy759hqf.us-west-2.aoss.amazonaws.com"
pds_nucleus_opensearch_registry_names            = ["en-registry", "en-registry"]
pds_nucleus_opensearch_credential_relative_url   = "http://169.254.170.2/AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"
pds_nucleus_harvest_replace_prefix_with_list     = ["s3://pds-sbn-nucleus-staging", "s3://pds-img-nucleus-staging"]
pds_registry_loader_harvest_version             = "1.3.2"
pds_validate_version                            = "latest"
pds_nucleus_opensearch_collection_arns           = ["arn:aws:aoss:us-west-2:123456789012:collection/p5qmxrldysl1gy759hqf", "arn:aws:aoss:us-west-2:123456789012:collection/p5qmxrldysl1gy759hqf"]
pds_nucleus_opensearch_cognito_identity_pool_ids = ["us-west-2:9a3cff4d-a28c-4763-a5e3-844ddfab0764", "us-west-2:9a3cff4d-a28c-4763-a5e3-844ddfab0764"]

airflow_env_name                             = "pds-nucleus-airflow-env"
mwaa_dag_s3_bucket_name                      = "pds-nucleus-airflow-dags-bucket-dev"
pds_nucleus_staging_bucket_name_postfix      = "staging-dev"
pds_nucleus_config_bucket_name_postfix       = "config-dev"
pds_shared_logs_bucket_name                  = "pds-logs-dev"

pds_nucleus_default_airflow_dag_id      = "validate-and-harvest"
pds_nucleus_s3_backlog_processor_dag_id = "pds-nucleus-s3-backlog-processor"

nucleus_cloudfront_origin_hostname = "pds-sit.mcp.nasa.gov"

cognito_user_pool_id              = "us-west-2_U26l4oajh"
cognito_user_pool_domain          = "pds-registry"
auth_alb_listener_certificate_arn = "arn:aws:acm:us-west-2:123456789012:certificate/ca8e3327-a0ed-42b4-8898-f5e87a69f519"
aws_elb_account_id_for_the_region = "123456789012"

# Tags
tag_tenant    = "en"                    # Owner Discipline Node (en, sbn, img, atm etc.)
tag_venue     = "pds-cds-dev"          # Environment (pds-cds-dev, pds-cds-prod)
tag_component = "nucleus"               # Component name
tag_cicd      = "iac"                   # Deployment method (iac, cd, etc.)
tag_managedby = "pds-operator@jpl.nasa.gov"  # PDS Team Email



terraform.tfvars (for MCP Prod)
venue                             = "prod"
region                            = "us-west-2"
vpc_id                            = "vpc-0211c4c0ef7e4e266"
subnet_ids                        = ["subnet-0476a07ebfcaaea3a", "subnet-0ac3ac3ab93fa2f89"]
auth_alb_subnet_ids               = ["subnet-0bc9dd5f94e3e8796", "subnet-0eb9dcd5dfceb5de1"]
vpc_cidr                          = "10.3.0.0/16"
permission_boundary_for_iam_roles = "mcp-tenantOperator-APIG"
permission_boundary_for_iam_roles_arn = "arn:aws:iam::<ALB-ACCOUNT-ID>:policy/mcp-tenantOperator-APIG"
database_availability_zones       = ["us-west-2a"]
aws_secretmanager_key_arn         = "arn:aws:kms:us-west-2:<ALB-ACCOUNT-ID>:key/a8285656-f5c0-49b5-af7e-0255109c6ac5"
 
 
# Set node specific values the following lists in correct order. For the list of node names
# the following node name format should be used.
# (PDS_ATM, PDS_ENG, PDS_GEO, PDS_IMG, PDS_NAIF, PDS_RMS, PDS_SBN, PSA, JAXA, ROSCOSMOS)
 
pds_node_names                                   = ["PDS_SBN"]
pds_archive_bucket_names                         = ["pds-sbn-archive-prod"]




pds_nucleus_opensearch_url                       = "https://b3rqys09xmx9i19yn64i.us-west-2.aoss.amazonaws.com"
pds_nucleus_opensearch_registry_names            = ["nucleus-sbn-registry"]
pds_nucleus_opensearch_credential_relative_url   = "http://169.254.170.2/AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"
pds_nucleus_harvest_replace_prefix_with_list     = ["s3://pds-sbn-staging-prod"]
pds_nucleus_opensearch_collection_arns           = ["arn:aws:aoss:us-west-2:<ALB-ACCOUNT-ID>:collection/b3rqys09xmx9i19yn64i"]
pds_nucleus_opensearch_cognito_identity_pool_ids = ["us-west-2:9a3cff4d-a28c-4763-a5e3-844ddfab0764"]
 
airflow_env_name                             = "pds-nucleus-airflow-env"
mwaa_dag_s3_bucket_name                      = "pds-nucleus-airflow-dags-bucket-prod"
pds_nucleus_staging_bucket_name_postfix      = "staging-prod"
pds_nucleus_config_bucket_name_postfix       = "config-prod"
pds_shared_logs_bucket_name                  = "pds-logs-prod"
 
pds_nucleus_default_airflow_dag_id      = "pds-basic-registry-load-use-case"
pds_nucleus_s3_backlog_processor_dag_id = "pds-nucleus-s3-backlog-processor"

nucleus_cloudfront_origin_hostname = "pds-sit.mcp.nasa.gov" 

cognito_user_pool_id              = "us-west-2_IXimOAJPC"
cognito_user_pool_domain          = "pds-prod-nucleus-dum"
auth_alb_listener_certificate_arn = "arn:aws:acm:us-west-2:<ALB-ACCOUNT-ID>:certificate/72e0101b-e630-4ab7-99a0-ed76c0c52daf"
aws_elb_account_id_for_the_region = "<PDS-LOGGING-ACCOUNT-ID>"


# Tags
tag_tenant    = "en"                    # Owner Discipline Node (en, sbn, img, atm etc.)
tag_venue     = "pds-cds-dev"          # Environment (pds-cds-dev, pds-cds-prod)
tag_component = "nucleus"               # Component name
tag_cicd      = "iac"                   # Deployment method (iac, cd, etc.)
tag_managedby = "pds-operator@jpl.nasa.gov"  # PDS Team Email














SBN CSS Test Data

The SBN CSS test data in the following zip file can be used for the smoke test.
