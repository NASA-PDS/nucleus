# Terraform script to implement Cognito authentication for MWAA.
# --------------------------------------------------------------
#
# This code is implemented based on the following references:
#  - Application load balancer single-sign-on for Amazon MWAA (https://github.com/aws-samples/alb-sso-mwaa)
#  - Accessing a private Amazon MWAA environment using federated identities (https://d1.awsstatic.com/whitepapers/accessing-a-private-amazon-mwaa-environment-using-federated-identities.pdf )


# PDS shared logs bucket to keep ALB logs
data "aws_s3_bucket" "pds_shared_logs_bucket" {
  bucket = var.pds_shared_logs_bucket_name
}

resource "aws_lb" "pds_nucleus_auth_alb" {
  name               = var.auth_alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.nucleus_auth_alb_security_group_id]
  subnets            = var.auth_alb_subnet_ids

  access_logs {
    enabled  = true
    bucket  = data.aws_s3_bucket.pds_shared_logs_bucket.id
    prefix  = "nucleus/auth-alb-access-logs"
  }
}

resource "aws_lb_target_group" "mwaa_auth_alb_lambda_tg" {
  name                               = "pds-nucleus-auth-alb-lambda-tg"
  lambda_multi_value_headers_enabled = true
  target_type                        = "lambda"
}


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

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
  function_name    = var.pds_nucleus_auth_alb_function_name
  filename         = data.archive_file.pds_nucleus_auth_alb_function_zip_packages.output_path
  source_code_hash = data.archive_file.pds_nucleus_auth_alb_function_zip_packages.output_base64sha256
  role             = var.pds_nucleus_alb_auth_lambda_execution_role_arn
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
  name              = "/aws/lambda/${var.pds_nucleus_auth_alb_function_name}"
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
      user_pool_arn       = "arn:aws:cognito-idp:${var.region}:${data.aws_caller_identity.current.account_id}:userpool/${data.aws_cognito_user_pool.cognito_user_pool.user_pool_id}"
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
      user_pool_arn = "arn:aws:cognito-idp:${var.region}:${data.aws_caller_identity.current.account_id}:userpool/${data.aws_cognito_user_pool.cognito_user_pool.user_pool_id}"
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
  callback_urls                        = ["https://${aws_lb.pds_nucleus_auth_alb.dns_name}/oauth2/idpresponse", "https://${var.nucleus_cloudfront_origin_hostname}/oauth2/idpresponse"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid"]
  supported_identity_providers         = ["COGNITO"]
}

resource "aws_cognito_user_group" "pds_nucleus_admin_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_ADMIN"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow Admin Cognito User Group"
  precedence   = 50
}

resource "aws_cognito_user_group" "pds_nucleus_op_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_OP"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow Op Cognito User Group"
  precedence   = 55
}


resource "aws_cognito_user_group" "pds_nucleus_user_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_USER"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow User Cognito User Group"
  precedence   = 60
}


resource "aws_cognito_user_group" "pds_nucleus_viewer_cognito_user_group" {
  name         = "PDS_NUCLEUS_AIRFLOW_VIEWER"
  user_pool_id = data.aws_cognito_user_pool.cognito_user_pool.id
  description  = "PDS Nucleus Airflow Viewer Cognito User Group"
  precedence   = 65
}



output "pds_nucleus_airflow_ui_urls" {
  value = ["https://${aws_lb.pds_nucleus_auth_alb.dns_name}/aws_mwaa/aws-console-sso", "https://${var.nucleus_cloudfront_origin_hostname}/nucleus"]
}
