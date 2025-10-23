#!/bin/bash
 # Exit on error, undefined var, or failed pipe; ensures safe script execution
set -euo pipefail

# Build Lambda package for AWS (Python 3.13, Amazon Linux 2023)

echo "Building Lambda package inside Docker (Amazon Linux 2023, Python 3.13)..."

# Move to script directory
cd "$(dirname "$0")"

# Clean old build and create package folder
rm -rf package
mkdir -p package

# Use AWS SAM build image for Python 3.13 (x86_64)
docker run --rm --platform linux/amd64 \
  -v "$PWD":/var/task \
  -w /var/task \
  public.ecr.aws/sam/build-python3.13 \
  bash -c "
    set -euo pipefail
    echo 'Installing dependencies...'
    pip install -r requirements.txt --target /var/task/package
    echo 'Copying handler...'
    cp /var/task/pds_nucleus_alb_auth.py /var/task/package/
  "

# Check that package directory exists and is not empty
if [ ! -d "package" ] || [ -z "$(ls -A package)" ]; then
  echo 'ERROR: package directory empty or missing.'
  exit 1
fi

# Build complete
echo "Lambda package built successfully at $(pwd)/package"
