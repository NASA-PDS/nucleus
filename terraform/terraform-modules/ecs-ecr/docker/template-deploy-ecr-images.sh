#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration (Terraform-provided variables) ---
echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region "${aws_region}" | docker login --username AWS --password-stdin "${ecs_registry}"

echo "Login successful."

# --- Deploy pds-nucleus-config-init ECR image ---
echo "Building and pushing pds-nucleus-config-init..."
cd ./terraform-modules/ecs-ecr/docker/config-init
# Explicitly build for the linux/amd64 platform
docker buildx build --platform linux/amd64 --load -t pds-nucleus-config-init .
docker tag pds-nucleus-config-init:latest "${ecs_registry}/pds-nucleus-config-init:latest"
docker push "${ecs_registry}/pds-nucleus-config-init:latest"
cd - > /dev/null

# --- Deploy pds-nucleus-s3-to-efs-copy ECR image ---
echo "Building and pushing pds-nucleus-s3-to-efs-copy..."
cd ./terraform-modules/ecs-ecr/docker/s3-to-efs-copy
# Explicitly build for the linux/amd64 platform
docker buildx build --platform linux/amd64 --load -t pds-nucleus-s3-to-efs-copy .
docker tag pds-nucleus-s3-to-efs-copy:latest "${ecs_registry}/pds-nucleus-s3-to-efs-copy:latest"
docker push "${ecs_registry}/pds-nucleus-s3-to-efs-copy:latest"
cd - > /dev/null

# --- Deploy pre-built images from public registry ---

# Deploy pds-registry-loader-harvest ECR image
echo "Pulling nasapds/registry-loader and pushing to ECR repo pds-registry-loader-harvest..."
docker image pull --platform linux/amd64 nasapds/registry-loader
docker tag nasapds/registry-loader:latest "${ecs_registry}/pds-registry-loader-harvest:latest"
docker push "${ecs_registry}/pds-registry-loader-harvest:latest"

# Deploy pds-validate ECR image
echo "Pulling nasapds/validate and pushing to ECR repo pds-validate..."
docker image pull --platform linux/amd64 nasapds/validate
docker tag nasapds/validate:latest "${ecs_registry}/pds-validate:latest"
docker push "${ecs_registry}/pds-validate:latest"

# Deploy pds-nucleus-tools-java ECR image
echo "Pulling nasapds/nucleus-tools-java and pushing to ECR repo pds-nucleus-tools-java..."
docker image pull --platform linux/amd64 nasapds/nucleus-tools-java
docker tag nasapds/nucleus-tools-java:latest "${ecs_registry}/pds-nucleus-tools-java:latest"
docker push "${ecs_registry}/pds-nucleus-tools-java:latest"

echo "" # Add a blank line for readability
echo "All images have been successfully built, rebased (if needed), tagged, and pushed to ECR."