# Terraform script to create the baseline MWAA environment for Nucleus

resource "aws_mwaa_environment" "pds_nucleus_airflow_env" {

  name              = var.airflow_env_name
  airflow_version   = var.airflow_version
  environment_class = var.airflow_env_class

  dag_s3_path        = var.airflow_dags_path
  execution_role_arn = var.pds_nucleus_mwaa_execution_role_arn

  requirements_s3_path = var.airflow_requirements_path

  min_workers           = 1
  max_workers           = 10
  webserver_access_mode = "PUBLIC_ONLY"

  network_configuration {
    security_group_ids = [var.nucleus_security_group_id]
    subnet_ids         = var.subnet_ids
  }

  source_bucket_arn = var.airflow_dags_bucket_arn

  airflow_configuration_options = {
    "core.load_default_connections" = "false"
    "core.load_examples"            = "false"
    "webserver.dag_default_view"    = "tree"
    "webserver.dag_orientation"     = "TB"
    "logging.logging_level"         = "INFO"
  }

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "DEBUG"
    }

    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }

    task_logs {
      enabled   = true
      log_level = "INFO"
    }

    webserver_logs {
      enabled   = true
      log_level = "ERROR"
    }

    worker_logs {
      enabled   = true
      log_level = "CRITICAL"
    }
  }

  timeouts {
    create = "4h"
    update = "4h"
    delete = "1h"
  }
}
