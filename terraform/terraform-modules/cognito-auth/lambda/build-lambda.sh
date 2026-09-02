#!/bin/bash
# Exit on error, undefined var, or failed pipe; ensures safe script execution
set -euo pipefail

PACKAGE_DIR="package"

trap 'echo "Build failed — cleaning up..."; rm -rf "$PACKAGE_DIR"' ERR

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Building Lambda package..."

# Move to script directory
cd "$(dirname "$0")"

# Clean old build, old zip, and create package folder
rm -rf "$PACKAGE_DIR" lambda_package.zip
mkdir -p "$PACKAGE_DIR"

# Use AWS SAM build image for Python 3.13 (x86_64)
# Explicitly matching current host user UID/GID solves permissions across Linux, macOS, and WSL.
docker run \
  --rm \
  --user "$(id -u):$(id -g)" \
  --platform linux/amd64 \
  --volume "$PWD":/var/task \
  --workdir /var/task \
  --env HOME=/tmp \
  public.ecr.aws/sam/build-python3.13 \
  pip install --no-cache-dir --requirement requirements.txt --target "/var/task/$PACKAGE_DIR"

# Copy the handler script into the newly populated package directory
echo "Copying handler..."
cp --verbose pds_nucleus_alb_auth.py "$PACKAGE_DIR/"

# Validate that package directory exists and is not empty
if [[ ! -d "$PACKAGE_DIR" ]] || [[ -z "$(ls -A "$PACKAGE_DIR")" ]]; then
  echo 'ERROR: package directory is empty or missing.' >&2
  exit 1
fi

# Zip the Lambda package
(cd "$PACKAGE_DIR" && zip -qr "../lambda_package.zip" .)

# Build complete
echo "Lambda package built successfully at $(pwd)/lambda_package.zip"
