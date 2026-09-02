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
# The container writes as its default root user; only root can relax the
# permissions on the files it just created, so do it inside the same
# container invocation (chmod -R a+rwX) before it exits. This lets any host
# user (WSL, macOS, or the EC2 deploy user) later read/rebuild/delete the
# package dir, without depending on UID/GID mapping — which fails if the
# host user doesn't own the mounted directory (e.g. on EC2).
docker run \
  --rm \
  --platform linux/amd64 \
  --volume "$PWD":/var/task \
  --workdir /var/task \
  public.ecr.aws/sam/build-python3.13 \
  bash -c "pip install --no-cache-dir --requirement requirements.txt --target /var/task/$PACKAGE_DIR && chmod -R a+rwX /var/task/$PACKAGE_DIR"

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
