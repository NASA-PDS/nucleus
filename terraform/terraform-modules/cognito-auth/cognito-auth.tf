# Terraform script to implement Cognito authentication for MWAA.
# --------------------------------------------------------------
#
# This code is implemented based on the following references:
#  - Application load balancer single-sign-on for Amazon MWAA (https://github.com/aws-samples/alb-sso-mwaa)
#  - Accessing a private Amazon MWAA environment using federated identities (https://d1.awsstatic.com/whitepapers/accessing-a-private-amazon-mwaa-environment-using-federated-identities.pdf )

resource "aws_security_group" "nucleus_alb_security_group" {
  name        = var.nucleus_auth_alb_security_group_name
  description = "PDS Nucleus ALB security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = var.auth_alb_listener_port
    to_port     = var.auth_alb_listener_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

resource "aws_s3_bucket" "pds_nucleus_auth_alb_logs" {
  bucket = "pds-nucleus-auth-alb-logs"
}

resource "aws_s3_bucket_logging" "pds_nucleus_auth_alb_logs_bucket_logging" {
  bucket = aws_s3_bucket.pds_nucleus_auth_alb_logs.id

  target_bucket = aws_s3_bucket.pds_nucleus_auth_alb_logs.id
  target_prefix = "auth-alb-logs-bucket-logs"
}

#  logging bucket for pds_nucleus_auth_alb_logs bucket
resource "aws_s3_bucket" "pds_nucleus_auth_alb_logs_bucket_logs" {
  bucket = "pds-nucleus-auth-alb-logs-bucket-logs"
}

data "aws_iam_policy_document" "pds_nucleus_auth_alb_logs_bucket_logs_bucket_policy" {
  statement {
    sid    = "s3-log-delivery"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.pds_nucleus_auth_alb_logs_bucket_logs.arn}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "pds_nucleus_auth_alb_logs_bucket_logs_policy" {
  bucket = aws_s3_bucket.pds_nucleus_auth_alb_logs_bucket_logs.id
  policy = data.aws_iam_policy_document.pds_nucleus_auth_alb_logs_bucket_logs_bucket_policy.json
}

data "aws_iam_policy_document" "pds_nucleus_auth_alb_logs_s3_bucket_policy" {
  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.aws_elb_account_id_for_the_region}:root"]
    }
    actions = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.pds_nucleus_auth_alb_logs.arn}/*"]
  }
}

resource "aws_s3_bucket_policy" "logs_prod_policy" {
  bucket = aws_s3_bucket.pds_nucleus_auth_alb_logs.id

  policy = data.aws_iam_policy_document.pds_nucleus_auth_alb_logs_s3_bucket_policy.json
}

resource "aws_lb" "pds_nucleus_auth_alb" {
  name               = var.auth_alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.nucleus_alb_security_group.id]
  subnets            = var.auth_alb_subnet_ids

  access_logs {
    enabled  = true
    bucket  = aws_s3_bucket.pds_nucleus_auth_alb_logs.id
    prefix  = "auth-alb-access-logs"
  }
}

resource "aws_lb_target_group" "mwaa_auth_alb_lambda_tg" {
  name                               = "pds-nucleus-auth-alb-lambda-tg"
  lambda_multi_value_headers_enabled = true
  target_type                        = "lambda"
}

data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}

data "aws_iam_policy_document" "assume_role_lambda" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_iam_policy_document" "alb_auth_lambda_execution_role_policy" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_alb_auth_lambda_execution_role" {
  name = "pds_nucleus_alb_auth_lambda_execution_role"

  inline_policy {
    name   = "alb_auth_lambda_execution_role_policy"
    policy = data.aws_iam_policy_document.alb_auth_lambda_execution_role_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.assume_role_lambda.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


resource "null_resource" "install_dependencies" {
  provisioner "local-exec" {
    command = "bash ${path.module}/lambda/build-lambda.sh"

    environment = {
      path_module = path.module
    }
  }

  triggers = {
    dependencies_versions = filemd5("${path.module}/lambda/requirements.txt")
    source_versions       = filemd5("${path.module}/lambda/package/pds_nucleus_alb_auth.py")
  }
}

data "archive_file" "pds_nucleus_auth_alb_function_zip_packages" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/package"
  output_path = "${path.module}/lambda/pds_nucleus_alb_auth_layer.zip"

  depends_on = [null_resource.install_dependencies]
}

resource "aws_lambda_function" "pds_nucleus_auth_alb_function" {
  function_name    = "pds_nucleus_alb_auth"
  filename         = data.archive_file.pds_nucleus_auth_alb_function_zip_packages.output_path
  source_code_hash = data.archive_file.pds_nucleus_auth_alb_function_zip_packages.output_base64sha256
  role             = aws_iam_role.pds_nucleus_alb_auth_lambda_execution_role.arn
  runtime          = "python3.12"
  handler          = "pds_nucleus_alb_auth.lambda_handler"
  timeout          = 10

  environment {

    variables = {
      AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id,
      COGNITO_USER_POOL_ID = var.cognito_user_pool_id,
      AIRFLOW_ENV_NAME     = var.airflow_env_name
    }
  }

  depends_on = [data.archive_file.pds_nucleus_auth_alb_function_zip_packages]
}

# Create CloudWatch Log Group for pds_nucleus_s3_file_file_event_processor_function for each PDS Node
resource "aws_cloudwatch_log_group" "pds_nucleus_auth_alb" {
  name = "/aws/lambda/pds_nucleus_auth_alb"
  retention_in_days = 30
}

resource "aws_lambda_permission" "lambda_permissions_auth_alb" {
  statement_id  = "AllowExecutionFromlb"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pds_nucleus_auth_alb_function.function_name
  principal     = "elasticloadbalancing.amazonaws.com"
  source_arn    = aws_lb_target_group.mwaa_auth_alb_lambda_tg.arn
}

resource "aws_lb_target_group_attachment" "mwaa_auth_alb_lambda_tg_attachment" {
  target_group_arn = aws_lb_target_group.mwaa_auth_alb_lambda_tg.arn
  target_id        = aws_lambda_function.pds_nucleus_auth_alb_function.arn
  depends_on       = [aws_lambda_permission.lambda_permissions_auth_alb]
}

data "aws_cognito_user_pool" "cognito_user_pool" {
  user_pool_id = var.cognito_user_pool_id
}

# Default Listener
resource "aws_lb_listener" "front_end" {
  load_balancer_arn = aws_lb.pds_nucleus_auth_alb.arn
  port              = var.auth_alb_listener_port
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = var.auth_alb_listener_certificate_arn

  default_action {
    type = "authenticate-cognito"

    authenticate_cognito {
      user_pool_arn       = "arn:aws:cognito-idp:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:userpool/${data.aws_cognito_user_pool.cognito_user_pool.user_pool_id}"
      user_pool_client_id = aws_cognito_user_pool_client.cognito_user_pool_client_for_mwaa.id
      user_pool_domain    = var.cognito_user_pool_domain
    }
  }

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mwaa_auth_alb_lambda_tg.arn
  }
}

# ALB listener path /aws_mwaa/aws-console-sso to access Airflow UI
resource "aws_lb_listener_rule" "aws_console_sso_rule" {
  listener_arn = aws_lb_listener.front_end.arn
  priority     = 100

  action {
    type             = "authenticate-cognito"
    target_group_arn = aws_lb_target_group.mwaa_auth_alb_lambda_tg.arn
    authenticate_cognito {
      user_pool_arn = "arn:aws:cognito-idp:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:userpool/${data.aws_cognito_user_pool.cognito_user_pool.user_pool_id}"
      user_pool_client_id = aws_cognito_user_pool_client.cognito_user_pool_client_for_mwaa.id
      user_pool_domain    = var.cognito_user_pool_domain
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mwaa_auth_alb_lambda_tg.arn
  }

  condition {
    path_pattern {
      values = ["/aws_mwaa/aws-console-sso"]
    }
  }
}

# Cognito user pool client
resource "aws_cognito_user_pool_client" "cognito_user_pool_client_for_mwaa" {
  name                                 = "pds-nucleus-airflow-ui-client"
  user_pool_id                         = data.aws_cognito_user_pool.cognito_user_pool.id
  generate_secret                      = true
  callback_urls                        = ["https://${aws_lb.pds_nucleus_auth_alb.dns_name}:${var.auth_alb_listener_port}/oauth2/idpresponse"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid"]
  supported_identity_providers         = ["COGNITO"]
}

# Common assume role policy
data "aws_iam_policy_document" "pds_nucleus_airflow_assume_role" {
  statement {
    effect = "Allow"
    actions = [
      "sts:AssumeRole"
    ]
    principals {
      type = "AWS"
      identifiers = ["arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role/${aws_iam_role.pds_nucleus_alb_auth_lambda_execution_role.name}/${aws_lambda_function.pds_nucleus_auth_alb_function.function_name}"]
    }
  }
}


# Airflow Admin Role

data "aws_iam_policy_document" "pds_nucleus_airflow_admin_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Admin"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_admin_role" {
  name = "pds_nucleus_airflow_admin_role"

  inline_policy {
    name   = "pds_nucleus_airflow_admin_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_admin_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

resource "aws_cognito_user_group" "pds_nucleus_admin_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_ADMIN"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow Admin Cognito User Group"
  precedence   = 50
  role_arn     = aws_iam_role.pds_nucleus_admin_role.arn
}



# Airflow Op Role

data "aws_iam_policy_document" "pds_nucleus_airflow_op_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Op"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_op_role" {
  name = "pds_nucleus_airflow_op_role"

  inline_policy {
    name   = "pds_nucleus_airflow_op_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_op_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

resource "aws_cognito_user_group" "pds_nucleus_op_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_OP"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow Op Cognito User Group"
  precedence   = 55
  role_arn     = aws_iam_role.pds_nucleus_op_role.arn
}


# Airflow User Role

data "aws_iam_policy_document" "pds_nucleus_airflow_user_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/User"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_user_role" {
  name = "pds_nucleus_airflow_user_role"

  inline_policy {
    name   = "pds_nucleus_airflow_user_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_user_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

resource "aws_cognito_user_group" "pds_nucleus_user_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_USER"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow User Cognito User Group"
  precedence   = 60
  role_arn     = aws_iam_role.pds_nucleus_user_role.arn
}



# Airflow Viewer Role

data "aws_iam_policy_document" "pds_nucleus_airflow_viewer_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Viewer"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_viewer_role" {
  name = "pds_nucleus_airflow_viewer_role"

  inline_policy {
    name   = "pds_nucleus_airflow_viewer_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_viewer_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

resource "aws_cognito_user_group" "pds_nucleus_viewer_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_VIEWER"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow Viewer Cognito User Group"
  precedence   = 65
  role_arn     = aws_iam_role.pds_nucleus_viewer_role.arn
}
