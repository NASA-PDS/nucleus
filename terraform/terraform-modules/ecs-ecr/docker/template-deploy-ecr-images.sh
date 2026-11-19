#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Logging in to Amazon ECR..."
for attempt in 1 2 3 4 5; do
  if aws ecr get-login-password --region "${aws_region}" | docker login --username AWS --password-stdin "${ecs_registry}"; then
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "ECR login failed after $attempt attempts."
    exit 1
  fi
  echo "ECR login attempt $attempt failed (likely transient DNS/VPN issue), retrying in $((attempt * 10))s..."
  sleep $((attempt * 10))
done

echo "Login successful."

# --- Deploy pds-nucleus-config-init ECR image ---
echo "Building and pushing pds-nucleus-config-init..."
cd ./terraform-modules/ecs-ecr/docker/config-init
# Explicitly build for the linux/amd64 platform
docker build --platform linux/amd64 -t pds-nucleus-config-init .
docker tag pds-nucleus-config-init:latest "${ecs_registry}/pds-nucleus-config-init:latest"
docker push "${ecs_registry}/pds-nucleus-config-init:latest"
cd - > /dev/null

# --- Deploy pds-nucleus-s3-to-efs-copy ECR image ---
echo "Building and pushing pds-nucleus-s3-to-efs-copy..."
cd ./terraform-modules/ecs-ecr/docker/s3-to-efs-copy
# Explicitly build for the linux/amd64 platform
docker build --platform linux/amd64 -t pds-nucleus-s3-to-efs-copy .
docker tag pds-nucleus-s3-to-efs-copy:latest "${ecs_registry}/pds-nucleus-s3-to-efs-copy:latest"
docker push "${ecs_registry}/pds-nucleus-s3-to-efs-copy:latest"
cd - > /dev/null

# --- Deploy pds-registry-loader-harvest ECR image ---
# Built from source instead of pulled from Docker Hub, so the fixed
# Dockerfile (Alpine+JRE) actually ships. registry_loader_version is now
# a git ref (branch or tag), not a Docker Hub tag.
echo "Building pds-registry-loader-harvest from NASA-PDS/registry-loader@${registry_loader_version} and pushing to ECR..."
rm -rf /tmp/registry-loader-build
git clone --depth 1 --branch "${registry_loader_version}" https://github.com/NASA-PDS/registry-loader.git /tmp/registry-loader-build
docker build --platform linux/amd64 -f /tmp/registry-loader-build/docker/Dockerfile --target full -t pds-registry-loader-harvest /tmp/registry-loader-build
docker tag pds-registry-loader-harvest:latest "${ecs_registry}/pds-registry-loader-harvest:latest"
docker push "${ecs_registry}/pds-registry-loader-harvest:latest"
rm -rf /tmp/registry-loader-build

# Deploy pds-validate ECR image
echo "Pulling nasapds/validate and pushing to ECR repo pds-validate..."
docker image pull --platform linux/amd64 nasapds/validate:${validate_version}
docker tag nasapds/validate:${validate_version} "${ecs_registry}/pds-validate:latest"
docker push "${ecs_registry}/pds-validate:latest"

# Deploy pds-nucleus-tools-java ECR image
echo "Pulling nasapds/nucleus-tools-java and pushing to ECR repo pds-nucleus-tools-java..."
docker image pull --platform linux/amd64 nasapds/nucleus-tools-java
docker tag nasapds/nucleus-tools-java:latest "${ecs_registry}/pds-nucleus-tools-java:latest"
docker push "${ecs_registry}/pds-nucleus-tools-java:latest"

echo "" # Add a blank line for readability
echo "All images have been successfully built, rebased (if needed), tagged, and pushed to ECR."