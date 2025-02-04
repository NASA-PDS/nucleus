#!/bin/bash

echo "Building lambda package..."
mkdir $path_module/lambda/venv
python3 -m venv $path_module/lambda/venv
source $path_module/lambda/venv/bin/activate
pip install --platform manylinux2014_x86_64 --target=package --implementation cp --python-version 3.12 --only-binary=:all: --upgrade -r "$path_module"/lambda/requirements.txt --target $path_module/lambda/package/
deactivate
rm -rf $path_module/lambda/venv
