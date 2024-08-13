#!/bin/bash

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 441083951559.dkr.ecr.us-west-2.amazonaws.com

# Deploy pds-nucleus-config-init ECR image
cd ./terraform-modules/ecs-ecr/docker/config-init
docker build -t pds-nucleus-config-init .
docker tag pds-nucleus-config-init:latest 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-config-init:latest
docker push 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-config-init:latest

# Deploy pds-nucleus-s3-to-efs-copy ECR image
cd ../s3-to-efs-copy
docker build -t pds-nucleus-s3-to-efs-copy .
docker tag pds-nucleus-s3-to-efs-copy:latest 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-s3-to-efs-copy:latest
docker push 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-nucleus-s3-to-efs-copy:latest

# Deploy pds-registry-loader-harvest ECR image
docker image pull nasapds/registry-loader
docker tag nasapds/registry-loader:latest 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-registry-loader-harvest:latest
docker push 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-registry-loader-harvest:latest

# Deploy pds-validate ECR image
docker image pull nasapds/validate
docker tag nasapds/validate:latest 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-validate:latest
docker push 441083951559.dkr.ecr.us-west-2.amazonaws.com/pds-validate:latest
