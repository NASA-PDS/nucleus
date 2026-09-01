# Nucleus Deployment — Step by Step

## Prerequisites

1. EC2 instance to run Terraform (Amazon Linux 2023, x86, t2.large recommended).

2. Install Terraform on the EC2 instance.
   ```bash
   sudo yum update -y
   sudo yum install -y yum-utils
   sudo yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
   sudo yum install -y terraform
   terraform -version
   ```

3. Install Docker on the EC2 instance, add your user to the `docker` group, then logout/login.
   ```bash
   sudo amazon-linux-extras enable docker
   sudo yum install -y docker
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo systemctl status docker
   sudo usermod -aG docker $(whoami)
   ```

4. Add `arn:aws:s3:::pds-logs-<venue>/nucleus/*` to the `pds-logs-<venue>` bucket policy. Do not remove existing statements.
   ```json
   {
     "Effect": "Allow",
     "Principal": { "AWS": "arn:aws:iam::<PDS-LOGGING-ACCOUNT-ID>:root" },
     "Action": "s3:PutObject",
     "Resource": ["arn:aws:s3:::pds-logs-<venue>/nucleus/*"]
   }
   ```

5. Confirm staging/archive buckets already exist and are accessible by Nucleus's IAM roles. If in a different AWS account, add a bucket policy granting these actions to `pds_nucleus_ecs_task_role-<NODE>` / `pds_nucleus_harvest_ecs_task_role-<NODE>`:
   ```
   s3:GetBucket*, s3:GetObject*, s3:List*, s3:PutObject, s3:PutObjectTagging
   ```
   **Caveat:** AWS resolves the role ARN in a bucket policy to the role's internal unique ID at save time. If `module.iam` is later destroyed/recreated (e.g. `terraform apply -target=module.iam` after a role change), the role gets a new unique ID even though the ARN string is unchanged — the old bucket policy statement becomes stale and access silently breaks with `403 ... no resource-based policy allows`. If this happens, remove and re-add the same statement in the bucket policy to force AWS to re-resolve the ARN.

6. Confirm/create the OpenSearch index for the discipline node. See https://nasa-pds.github.io/registry/admin/create_reg.html

7. Open this inbound rule on the Nucleus ALB's public subnets (required for Cognito + ALB):
   ```
   Type: Custom TCP | Protocol: TCP | Port range: 1024-65535 | Source: 0.0.0.0/0 | Allow
   ```

8. Have two AWS identities ready:
   - **Admin identity** — IAM-creation permissions.
   - **Developer identity** — see `DEVELOPER_IAM_POLICY.md` (no IAM-creation permissions needed).

## Deploy

1. Initialize Terraform.
   ```bash
   terraform init
   ```

2. **Admin identity** — create the `pds_nucleus_*` IAM roles (only needed again if `terraform-modules/iam/iam.tf` changes).
   ```bash
   terraform apply -target=module.iam
   ```

3. Save the correct `terraform.tfvars` content (Dev or Prod — see wiki) as `./terraform/terraform.tfvars`.

4. **Developer identity** — deploy everything else.
   ```bash
   terraform apply
   ```

5. If `apply` fails (network/credential expiry/random errors like `exit status 127`), retry a few times before deeper troubleshooting.
   ```bash
   terraform init && terraform apply
   ```

6. Note the `pds_nucleus_airflow_ui_url` output and share it with the Dev team.
   ```
   pds_nucleus_airflow_ui_url = "https://pds-nucleus-12345678.us-west-2.elb.amazonaws.com:4443/aws_mwaa/aws-console-sso"
   ```

## Post-Deploy: Connect Staging Bucket

1. Open the staging S3 bucket in AWS Console.
2. Properties → Event notifications → Create event notification.
3. Name it (e.g. "File copy event").
4. Event type: `s3:ObjectCreated:*`.
5. Destination: SQS queue.
6. Select queue: `pds-nucleus-files-to-save-in-database-<NODE>`.
7. Save.

## Post-Deploy: OpenSearch Access

1. Amazon OpenSearch Service → Serverless → Security → Data access control → `pds-mcp-<venue>-data-access`.
2. Edit.
3. Add `pds_nucleus_harvest_ecs_task_role-<NODE>` as Principal under the Read/Write rule.
4. Save.

## Post-Deploy: User Setup

1. Cognito → User pools → `nucleus-dum-cognito-user-pool`.
2. Create user, verify email, generate password.
3. Add user to `PDS_NUCLEUS_AIRFLOW_VIEWER` group.

## Post-Deploy: Enable Airflow DAG

1. AWS Console → Managed Apache Airflow (MWAA).
2. Open the `PDS-Nucleus-Airflow-Env` environment → Open Airflow UI.
3. Enable the DAG if disabled.

## Smoke Test

1. Open the `pds_nucleus_airflow_ui_url` output URL in Chrome.
2. Log in with the Cognito user created above.
3. Download SBN CSS test data.
4. Upload it to the staging bucket (via PDS Data Upload Manager, or directly).
5. Wait 2 minutes, check DAG progress in Airflow UI — all tasks should turn green.

## Uninstall

1. Copy the correct `terraform.tfvars` into `./terraform/terraform.tfvars`.

2. **Developer identity** — destroy everything except IAM roles.
   ```bash
   terraform destroy
   ```

3. **Admin identity** — remove the IAM roles (developer identity can't do this).
   ```bash
   terraform destroy -target=module.iam
   ```
