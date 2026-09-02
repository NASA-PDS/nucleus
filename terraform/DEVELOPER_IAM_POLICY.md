# Developer Deployment IAM Policy

## TL;DR

Deployment is a 2-step process, no code changes needed:

```bash
# Step 1 — admin (has IAM-creation permissions)
terraform apply -target=module.iam

# Step 2 — developer (policy below, NO IAM-creation permissions)
terraform apply
```

The developer role can deploy everything else (ALB, ECS, Lambda, MWAA,
Cognito, S3, CloudWatch, SSM...) because those resources only *reference*
the roles admin already created — they never create/modify/delete IAM.

Attach the policy below to the AWS identity developers assume.

## The Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOwnIamRolesAndPolicy",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:ListInstanceProfilesForRole"
      ],
      "Resource": "arn:aws:iam::*:role/pds_nucleus_*"
    },
    {
      "Sid": "ReadExternalPermissionBoundaryPolicy",
      "Effect": "Allow",
      "Action": "iam:GetPolicy",
      "Resource": "arn:aws:iam::*:policy/mcp-tenantOperator-APIG"
    },
    {
      "Sid": "PassOnlyThesePrebuiltRoles",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/pds_nucleus_*"
    }
  ]
}
```

## Why each statement is needed

| Statement | Needed for | If missing |
|---|---|---|
| `ReadOwnIamRolesAndPolicy` | Terraform refreshes the 10 IAM roles already in state on every `plan`/`apply`, even though dev didn't create them | `AccessDenied` on `iam:GetRole` — blocks every apply, before dev's own resources are even planned |
| `ReadExternalPermissionBoundaryPolicy` | `data "aws_iam_policy" "mcp_operator_policy"` lookup in `ecs_ecr.tf:9` | `AccessDenied` on `iam:GetPolicy` — blocks all of `module.ecs_ecr` |
| `PassOnlyThesePrebuiltRoles` | Attaching an existing role to a new/updated Lambda, ECS task def, or MWAA env (see table below) | `AccessDenied: ... iam:PassRole` — this is the one you'll hit most often |

`sts:GetCallerIdentity` (used by `data "aws_caller_identity" "current"` across most modules) is not included above — AWS allows this action for any authenticated principal regardless of attached policy, so no explicit grant is needed.

## Where `iam:PassRole` is actually used

Four places in the code attach a role that admin already created to a
resource dev deploys. AWS enforces `iam:PassRole` at the API level for all
of these — it can't be avoided by changing the Terraform code.

**MWAA environment** — `terraform-modules/mwaa-env/mwaa_env.tf:12`
```hcl
resource "aws_mwaa_environment" "pds_nucleus_airflow_env" {
  execution_role_arn = var.pds_nucleus_mwaa_execution_role_arn
```

**ALB auth Lambda** — `terraform-modules/cognito-auth/cognito-auth.tf:105`
```hcl
resource "aws_lambda_function" "pds_nucleus_auth_alb_function" {
  role = var.pds_nucleus_alb_auth_lambda_execution_role_arn
```

**ECS task definitions (x5)** — `terraform-modules/ecs-ecr/ecs_ecr.tf:239-240`
```hcl
task_role_arn      = var.pds_nucleus_harvest_ecs_task_role_arns[count.index]
execution_role_arn = var.pds_nucleus_ecs_task_execution_role_arn
```

**S3 event processor Lambdas (x3)** — `terraform-modules/product-copy-completion-checker/product-copy-completion-checker.tf:168`
```hcl
resource "aws_lambda_function" "pds_nucleus_s3_file_file_event_processor_function" {
  role = var.pds_nucleus_lambda_execution_role_arns[count.index]
```

## What this policy does NOT allow

- No `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy`, `iam:DeleteRole`, or any other IAM write action.
- No `iam:PassRole` on any role outside `pds_nucleus_*`.
- No read access to any IAM role/policy outside `pds_nucleus_*` and the single named permission-boundary policy.

If a new module needs a role outside the `pds_nucleus_*` pattern, admin
must update this policy's `Resource` ARNs — a developer holding only this
policy cannot create or pass that role themselves, by design.
