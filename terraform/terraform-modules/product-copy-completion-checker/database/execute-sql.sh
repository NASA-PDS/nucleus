#!/bin/bash
# execute-sql.sh

# Connect to the database and execute SQL file
mysql --host=terraform-20240418054136603700000001.ckswokhegusf.us-west-2.rds.amazonaws.com --port=3306 --user=admin --password=foobarbaz --database=pds_nucleus  < /Users/rameshm/project/pds/Nucleus/test_prod_prod_deploy_terraform/nucleus/terraform/terraform-modules/product-copy-completion-checker/database/pds-nucleus-database.sql
