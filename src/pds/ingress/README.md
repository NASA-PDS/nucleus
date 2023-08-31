# PDS Nucleus - Product Copy Completion Checker Lambda

This is a lambda function implementation based on the Design queuing service for streaming data into
Nucleus https://github.com/NASA-PDS/nucleus/issues/60 


### Steps to use this lambda authorizer function:

1. Get the source code as follows.
```shell
git clone https://github.com/NASA-PDS/nucleus.git
```

2. Change current directory to `eus-git/nucleus/src/pds/ingress`

```shell
cd nucleus/src/pds/ingress
```

3Create a deployment package as a ZIP file.

```shell
zip -r pds-nucleus-product-completion-checker.zip .
```

5. Create a lambda function on AWS as explained in https://docs.aws.amazon.com/lambda/latest/dg/getting-started.html

6. Deploy the previously created ZIP file as explained in https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-package.html#gettingstarted-package-zip

7. After deploying the lambda function, go to the lambda function in AWS Console and  click on Configuration -> Environment variables.

8. Configure the following 2 environment variables.
    * EFS_MOUNT_PATH (E.g: /mnt/data/)
    * SQS_QUEUE_URL	(E.g.: https://sqs.us-west-2.amazonaws.com/<account-id>>/pds-nucleus-ready-to-process-products)

9. Click on Code -> Runtime settings -> Edit and set the `pds-nucleus-product-completion-checker.lambda_handler` as Handler.

After above steps, the lambda function can be triggered by an S3 event notification when a file is copied to Nucleus 
staging S3 bucket
