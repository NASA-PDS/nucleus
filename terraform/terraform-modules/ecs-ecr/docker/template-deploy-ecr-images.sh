#!/bin/bash

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com

# Deploy pds-nucleus-config-init ECR image
cd ./terraform-modules/ecs-ecr/docker/config-init
docker build --platform linux/amd64 -t pds-nucleus-config-init .
docker tag pds-nucleus-config-init:latest "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-config-init:latest
docker push "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-config-init:latest

# Deploy pds-nucleus-s3-to-efs-copy ECR image
cd ../s3-to-efs-copy
docker build --platform linux/amd64 -t pds-nucleus-s3-to-efs-copy .
docker tag pds-nucleus-s3-to-efs-copy:latest "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-s3-to-efs-copy:latest
docker push "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-s3-to-efs-copy:latest

# Deploy pds-registry-loader-harvest ECR image
docker image pull nasapds/registry-loader
docker tag nasapds/registry-loader:latest "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-registry-loader-harvest:latest
docker push "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-registry-loader-harvest:latest

# Deploy pds-validate ECR image
docker image pull nasapds/validate
docker tag nasapds/validate:latest "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-validate:latest
docker push "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-validate:latest

# Deploy pds_nucleus_s3_backlog_processor ECR image
docker image pull nasapds/nucleus-tools-java
docker tag nasapds/nucleus-tools-java:latest "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-tools-java:latest
docker push "${pds_nucleus_aws_account_id}".dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-tools-java:latest

