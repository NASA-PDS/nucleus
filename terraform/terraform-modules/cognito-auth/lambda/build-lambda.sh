#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Define variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="${SCRIPT_DIR}"

# This is the directory on the host machine where the lambda source code and dependencies will be placed.
PACKAGE_DIR="${PROJECT_DIR}/package"
DOCKER_IMAGE_NAME="pds-nucleus-lambda-builder"

echo "Cleaning up old package directory..."
# Remove old packages to ensure a clean install
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

echo "Building Docker image for x86_64..."
# The --platform flag is a good practice for cross-compilation on Apple Silicon.
docker build --platform linux/amd64 -t "$DOCKER_IMAGE_NAME" -f "${PROJECT_DIR}/Dockerfile" "${PROJECT_DIR}"

# Check if docker build was successful
if [ $? -ne 0 ]; then
    echo "ERROR: Docker image build failed!"
    exit 1
fi

echo "Copying built dependencies and source code from Docker container to host..."
# Create a temporary container
CONTAINER_ID=$(docker create "$DOCKER_IMAGE_NAME")

# Copy the contents of the 'python' folder (the dependencies) to the host's package directory.
# The `.` at the end of the source path is crucial here. It copies the contents of the folder,
# not the folder itself.
echo "Extracting Python dependencies..."
docker cp "$CONTAINER_ID":/var/task/python/. "$PACKAGE_DIR"

# Copy the pds_nucleus_alb_auth.py file to the host's package directory.
echo "Copying lambda handler file..."
docker cp "$CONTAINER_ID":/var/task/pds_nucleus_alb_auth.py "$PACKAGE_DIR"/pds_nucleus_alb_auth.py

# Clean up the temporary container
docker rm "$CONTAINER_ID"

# Check if docker cp was successful
if [ $? -ne 0 ]; then
    echo "ERROR: Docker container run or file copy failed!"
    exit 1
fi

echo "Source code and dependencies are ready in the '$PACKAGE_DIR' directory."
echo "Verifying contents of the package directory on host machine..."
ls -R "$PACKAGE_DIR"

echo "Terraform's 'archive_file' data source will now create the final zip package."
