# Docker image to copy config files and scripts from an S3 bucket to EFS

The files in this directory builds a docker image which is used to
copy config files and scripts from an S3 bucket to EFS.

This docker image will be pushed to the AWS ECR and then it will be
used by an ECS task.

## Steps to build and push the docker image to ECR

1. Go to [AWS ECR](https://us-west-2.console.aws.amazon.com/ecr/repositories?region=us-west-2).
2. Create a new repository called `pds-s3-to-efs-copy` or make sure if there is a 
repository available with the name `pds-s3-to-efs-copy`.
3. Click on the repository name `pds-s3-to-efs-copy`.
4. View Push Commands and note the push command for your operating system.
5. Open a terminal window and change directory to the directory containing the Dockerfile 
(same directory which contains this README file).
6. Execute Push Commands to push the docker image to the `pds-s3-to-efs-copy` 
repository on AWS ECR.
