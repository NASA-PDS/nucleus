#!/bin/bash
# Exit on error, undefined var, or failed pipe; ensures safe script execution
set -euo pipefail
trap 'echo "Build failed — cleaning up..."; rm -rf package' ERR

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Building Lambda package..."

# Move to script directory
cd "$(dirname "$0")"

# Clean old build and create package folder
rm -rf package && mkdir -p package

# Use AWS SAM build image for Python 3.13 (x86_64)
docker run \
  --rm \
  --platform linux/amd64 \
  --volume "$PWD":/var/task \
  --workdir /var/task \
  public.ecr.aws/sam/build-python3.13 \
  bash --login -c "
    set -euo pipefail
    echo 'Installing dependencies...'
    pip install --requirement requirements.txt --target /var/task/package
    echo 'Copying handler...'
    cp --verbose /var/task/pds_nucleus_alb_auth.py /var/task/package/
  "

# Validate that package directory exists and is not empty
if [[ ! -d "package" ]] || [[ -z "$(ls -A package)" ]]; then
  echo 'ERROR: package directory is empty or missing.' >&2
  exit 1
fi

# Zip the Lambda package
(cd package && zip -qr ../lambda_package.zip .)

# Build complete
echo "Lambda package built successfully at $(pwd)/lambda_package.zip"
