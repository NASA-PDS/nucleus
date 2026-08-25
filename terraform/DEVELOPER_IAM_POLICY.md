# Developer Deployment IAM Policy

## Purpose

This repo's Terraform is split into two deployment phases:

1. **Admin phase** — an operator with IAM-creation permissions runs:
   ```bash
   terraform apply -target=module.iam
   ```
   This creates/updates the 10 roles defined in
   [`terraform-modules/iam/iam.tf`](terraform-modules/iam/iam.tf):
   `pds_nucleus_alb_auth_lambda_execution_role`,
   `pds_nucleus_airflow_admin_role`, `pds_nucleus_airflow_op_role`,
   `pds_nucleus_airflow_user_role`, `pds_nucleus_airflow_viewer_role`,
   `pds_nucleus_ecs_task_role-*`, `pds_nucleus_harvest_ecs_task_role-*`,
   `pds_nucleus_ecs_task_execution_role`, `pds_nucleus_mwaa_execution_role`,
   `pds_nucleus_lambda_execution_role-*`.

2. **Developer phase** — a role/user **without any IAM-creation permissions**
   runs a normal `terraform apply`, which deploys everything else (ALB,
   ECS task definitions, Lambda functions, MWAA environment, Cognito, S3,
   CloudWatch, SSM, etc.). This only works because those resources
   *reference* the role ARNs created in phase 1 — they never create,
   modify, or delete an IAM role/policy.

No changes to any `.tf` file are required to support this split. The policy
below is attached only to the AWS identity developers assume.

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
    },
    {
      "Sid": "WhoAmI",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
```

Notes on the resource ARNs:
- `pds_nucleus_*` is a safe wildcard scope — every role created by
  `module.iam` is prefixed `pds_nucleus_` (verified against
  `terraform-modules/iam/iam.tf`). This policy grants **no** access to any
  IAM role outside this naming convention.
- `mcp-tenantOperator-APIG` is the permission-boundary policy name looked
  up in [`terraform-modules/ecs-ecr/ecs_ecr.tf:9`](terraform-modules/ecs-ecr/ecs_ecr.tf)
  via `var.permission_boundary_for_iam_roles`. If that variable is changed
  to point at a different policy, update this ARN/name to match.
- **Nothing in this policy allows `iam:CreateRole`, `iam:PutRolePolicy`,
  `iam:AttachRolePolicy`, `iam:DeleteRole`, `iam:CreatePolicy`, or any other
  IAM write action.** The developer role can never create, modify, or
  delete an IAM principal or policy.

## Why each statement is needed, and what breaks without it

### `ReadOwnIamRolesAndPolicy` (`iam:GetRole`, `iam:GetRolePolicy`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:ListInstanceProfilesForRole`)

Terraform refreshes **every** resource already in state before planning —
including the 10 IAM roles created in the admin phase, even though the
developer never created them. Every `terraform plan`/`apply` shows this in
the log:
```
module.iam.aws_iam_role.pds_nucleus_alb_auth_lambda_execution_role: Refreshing state...
module.iam.aws_iam_role.pds_nucleus_ecs_task_role[0]: Refreshing state...
...
```

**Without this permission:** every `terraform plan`/`apply` run by the
developer role fails immediately during the refresh phase with
`AccessDenied` errors on `iam:GetRole` (and related `List*`/`Get*` calls),
before Terraform even gets to plan the resources the developer is actually
allowed to change.

### `ReadExternalPermissionBoundaryPolicy` (`iam:GetPolicy`)

`terraform-modules/ecs-ecr/ecs_ecr.tf:9` has:
```hcl
data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}
```
This is a read-only lookup used elsewhere in the ECS/ECR module's rendered
templates.

**Without this permission:** any `apply` that touches `module.ecs_ecr`
fails at this data source with `AccessDenied` on `iam:GetPolicy`, blocking
the entire developer-phase apply even for unrelated resources in the same
module.

### `PassOnlyThesePrebuiltRoles` (`iam:PassRole`)

Several resources the developer *is* allowed to create/update attach an
existing IAM role to an AWS service:

| Resource | File | Role passed |
|---|---|---|
| `aws_lambda_function` (SQS-triggered, x3) | `terraform-modules/product-copy-completion-checker/product-copy-completion-checker.tf:168,203,346` | `pds_nucleus_lambda_execution_role-*` |
| `aws_ecs_task_definition` (x5) | `terraform-modules/ecs-ecr/ecs_ecr.tf:239-480` | `pds_nucleus_ecs_task_role-*` / `pds_nucleus_harvest_ecs_task_role-*` + `pds_nucleus_ecs_task_execution_role` |
| `aws_lambda_function` (ALB auth) | `terraform-modules/cognito-auth/cognito-auth.tf:105` | `pds_nucleus_alb_auth_lambda_execution_role` |
| `aws_mwaa_environment` | `terraform-modules/mwaa-env/mwaa_env.tf:12` | `pds_nucleus_mwaa_execution_role` |

This is an **AWS-enforced check**, not a Terraform requirement: AWS itself
rejects `lambda:CreateFunction`/`UpdateFunctionConfiguration`,
`ecs:RegisterTaskDefinition`, and `airflow:CreateEnvironment`/
`UpdateEnvironment` calls unless the caller has `iam:PassRole` on the role
ARN being attached. There is no way to avoid this if the developer role is
responsible for deploying or updating any of the resources in the table
above — this cannot be worked around at the Terraform config level.

**Without this permission:** every `apply` that creates or updates any of
the resources above fails with `AccessDenied: ... is not authorized to
perform: iam:PassRole on resource: ...`. This is the single most common
failure mode you will see if this statement is missing or scoped too
narrowly (e.g. missing a `pds_node_names` suffix variant).

### `WhoAmI` (`sts:GetCallerIdentity`)

`terraform-modules/ecs-ecr/ecs_ecr.tf:15` and other modules call
`data "aws_caller_identity" "current" {}` to inject the account ID into
generated templates/ARNs. This is an STS action, not IAM, but is included
here since it's part of the same "who am I / what can I touch" read-only
surface and is required for nearly every module to render correctly.

**Without this permission:** any module using
`data.aws_caller_identity.current.account_id` fails during plan with
`AccessDenied` on `sts:GetCallerIdentity`.

## What this policy deliberately does NOT allow

- Creating, updating, or deleting any IAM role, policy, or instance profile.
- Attaching or detaching managed/inline policies on any role.
- Passing any role outside the `pds_nucleus_*` naming convention.
- Reading any IAM role/policy outside `pds_nucleus_*` and the single named
  permission-boundary policy.

If a future module needs to attach a *new* role name pattern, this policy's
`Resource` ARNs must be updated by the same admin who manages
`module.iam` — a developer holding only this policy cannot create the role
themselves, by design.
