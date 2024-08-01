# Terraform script to create the common resources for PDS Nucleus
module "common" {
  source = "./terraform-modules/common"

  vpc_id                  = var.vpc_id
  vpc_cidr                = var.vpc_cidr
  mwaa_dag_s3_bucket_name = var.mwaa_dag_s3_bucket_name
}

# The Terraform module to create the PDS Nucleus Baseline System (without any project specific components)
module "mwaa-env" {
  source = "./terraform-modules/mwaa-env"

  vpc_id                            = var.vpc_id
  vpc_cidr                          = var.vpc_cidr
  subnet_ids                        = var.subnet_ids
  nucleus_security_group_id         = module.common.pds_nucleus_security_group_id
  airflow_dags_bucket_arn           = module.common.pds_nucleus_airflow_dags_bucket_arn
  permission_boundary_for_iam_roles = var.permission_boundary_for_iam_roles
  airflow_env_name                  = var.airflow_env_name
  depends_on                        = [module.common]
}

# The following modules are specific to PDS Registry and are under development. These modules are currently
# capable of successfully deploying some ECS tasks related with PDS Registry. However, these modules
# can be disabled (comment-out) to keep the PDS Nucleus Baseline System clean and to avoid confusions.

module "efs" {
  source = "./terraform-modules/efs"

  subnet_ids                = var.subnet_ids
  nucleus_security_group_id = module.common.pds_nucleus_security_group_id

  depends_on = [module.common]
}

module "ecs_ecr" {
  source = "./terraform-modules/ecs-ecr"

  pds_nucleus_ecs_cluster_name = var.pds_nucleus_ecs_cluster_name

  efs_file_system_id           = module.efs.efs_file_system_id
  pds_data_access_point_id     = module.efs.efs_access_point_id_pds-data

  pds_registry_loader_harvest_cloudwatch_logs_group  = var.pds_registry_loader_harvest_cloudwatch_logs_group
  pds_registry_loader_harvest_cloudwatch_logs_region = var.region

  pds_validate_cloudwatch_logs_group  = var.pds_validate_cloudwatch_logs_group
  pds_validate_cloudwatch_logs_region = var.region
  pds_validate_ref_cloudwatch_logs_group  = var.pds_validate_ref_cloudwatch_logs_group
  pds_validate_ref_cloudwatch_logs_region = var.region

  pds_nucleus_config_init_cloudwatch_logs_group  = var.pds_nucleus_config_init_cloudwatch_logs_group
  pds_nucleus_config_init_cloudwatch_logs_region = var.region
  pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group = var.pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group

  permission_boundary_for_iam_roles = var.permission_boundary_for_iam_roles

  pds_node_names = var.pds_node_names

  aws_secretmanager_key_arn = var.aws_secretmanager_key_arn

  depends_on = [module.common, module.efs]
}

module "product-copy-completion-checker" {
  source                                  = "./terraform-modules/product-copy-completion-checker"
  database_port                           = var.database_port
  vpc_id                                  = var.vpc_id
  permission_boundary_for_iam_roles       = var.permission_boundary_for_iam_roles
  nucleus_security_group_id               = module.common.pds_nucleus_security_group_id
  pds_nucleus_staging_bucket_name_postfix = var.pds_nucleus_staging_bucket_name_postfix
  pds_nucleus_config_bucket_name          = var.pds_nucleus_config_bucket_name
  subnet_ids                              = var.subnet_ids
  pds_nucleus_default_airflow_dag_id      = var.pds_nucleus_default_airflow_dag_id

  pds_node_names                                = var.pds_node_names
  pds_nucleus_opensearch_urls                   = var.pds_nucleus_opensearch_urls
  pds_nucleus_harvest_replace_prefix_with_list  = var.pds_nucleus_harvest_replace_prefix_with_list

  database_availability_zones = var.database_availability_zones
  airflow_env_name            = var.airflow_env_name
  region                      = var.region

  depends_on = [module.common]
}

module "test-data" {
  source                             = "./terraform-modules/test-data"
  pds_nucleus_ecs_cluster_name       = var.pds_nucleus_ecs_cluster_name
  pds_nucleus_ecs_subnets            = var.subnet_ids
  pds_nucleus_security_group_id      = module.common.pds_nucleus_security_group_id
  mwaa_dag_s3_bucket_name            = var.mwaa_dag_s3_bucket_name
  pds_nucleus_default_airflow_dag_id = var.pds_nucleus_default_airflow_dag_id
  pds_node_names                     = var.pds_node_names
  depends_on                         = [module.common, module.ecs_ecr]
}

module "archive" {
  source                             = "./terraform-modules/archive"
  pds_node_names                     = var.pds_node_names
  depends_on                         = [module.common, module.ecs_ecr]
}

