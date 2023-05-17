#!/bin/bash

aws s3 cp s3://nucleus-airflow-dags-bucket/staging/default-config/ /def-cfg/ --recursive
aws s3 cp s3://nucleus-airflow-dags-bucket/staging/scripts/ /usr/local/bin/ --recursive
