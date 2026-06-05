#!/bin/bash
# Exit on error, undefined var, or failed pipe; standard production guardrails
set -euo pipefail

# Safe local cleanup — no sudo required
trap 'echo "Build failed — cleaning up..."; rm -rf package' ERR

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Lambda package build..."

# Navigate to the script's directory regardless of where it was invoked
cd "$(dirname "$0")"

# Wipe the old directory cleanly
rm -rf package
mkdir -p package

# Get the absolute physical path to guarantee volume mount stability across OS types
ABS_PATH=$(pwd -P)

# Run the AWS SAM Docker image natively. 
# Explicitly matching current host user UID/GID solves permissions across Linux, macOS, and WSL.
docker run \
  --rm \
  --user "$(id -u):$(id -g)" \
  --platform linux/amd64 \
  --volume "${ABS_PATH}":/var/task \
  --workdir /var/task \
  --env HOME=/tmp \
  public.ecr.aws/sam/build-python3.13 \
  pip install --no-cache-dir --requirement requirements.txt --target /var/task/package

# Copy the handler script into the newly populated package directory
echo "Copying handler script..."
cp pds_nucleus_alb_auth.py package/

# Final validation before packing
if [[ ! -d "package" ]] || [[ -z "$(ls -A package)" ]]; then
  echo "ERROR: Package directory is empty or missing after build phase." >&2
  exit 1
fi

# Package into a deployment zip
echo "Archiving dependencies into deployment package..."
(cd package && zip -qr ../lambda_package.zip .)

echo "Lambda package successfully built at: ${ABS_PATH}/lambda_package.zip"