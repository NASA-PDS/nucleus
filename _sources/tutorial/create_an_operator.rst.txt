=====================
Create an Operator
=====================


---------------------------------------------------------------------------------------------------------------------
Overview
---------------------------------------------------------------------------------------------------------------------

An operator is an AWS resource to be used by the Airflow DAG, to run a step of the workflow.

.. note::

	This tutorial need to be executed with access to create AWS resources.


The steps are:

1)  Create and push the docker image to ECR.

2)  Create an EFS volume to share data/configuration files between docker containers (optional, only if the use case must share data/configuration between tasks).

3)  Make sure that you have an ECS Cluster to execute ECS tasks.

4)  Create an ECS task (This can be done through AWS Console or Terraform).

    a. Create container definition
    b. Create ECS task definition (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/create-task-definition.html )



----------------------------------------------------------------------------------------------------------------------
Detailed Tutorial
----------------------------------------------------------------------------------------------------------------------

Step 1: Create and push the docker image to ECR
===============================================

For this example, we will be using the PDS Validate image.


1. Login to AWS (NGAP) with  NGAPShApplicationDeveloper role.

2. Create a new ECR repository called “pds-validate-tutorial”.

    a. Follow the instructions in https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html (In Step 6 for the repository name, enter pds-validate-tutorial.
    b. For all other values, you may select default values for the purpose of this tutorial).

3. Login to AWS (NGAP) on a web browser and visit Amazon ECR ( https://us-west-2.console.aws.amazon.com/ecr/repositories?region=us-west-2).

4. Click on the repository pds-validate-tutorial.

5. Click on the “View push commands” button.

6. Notice the “Push commands for pds-validate-tutorial” specific to your operating system (macOS/Linux or Windows).

7. Make sure that the docker desktop or docker daemon is running on your local computer.

8. Open a terminal window in the local machine.

9. Clone the git repository of the validate tool.

.. code-block::

    git clone https://github.com/NASA-PDS/validate.git

10.  Change directory to validate/docker/.

.. code-block::

    cd validate/docker/

11.  Make sure AWS CLI version 2.7 or above is set up on your local computer with the following NGAP AWS environment variables. Values for these variables can be obtained from the NGAP Kion.

.. code-block::

    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_SESSION_TOKEN
    AWS_DEFAULT_REGION

12.  Execute the “Push commands for pds-validate-tutorial” that you noticed in the Step 6 above, one after another. This will push the docker image of the PDS validate tool to pds-validate-tutorial ECR repository.

13.  Wait for image push to be completed, visit the pds-validate-tutorial ECR repository on the web browser and check if the image is available in the pds-validate-tutorial ECR repository.

14.  Notice the ECR image URL of the PDS Validate tool.


Step 2: Make sure that you have an ECS Cluster to execute ECS tasks
===================================================================

1. Login to AWS (NGAP) with  NGAPShApplicationDeveloper role.

2. Visit Amazon Elastic Container Service (ECS) on NGAP (https://us-west-2.console.aws.amazon.com/ecs/v2/clusters?region=us-west-2 ).

3. Make sure that there is an ECS Cluster available for you to execute ECS tasks.

4. If an ECS Cluster is not available, create a new ECS Cluster.

    a) Visit ECS Cluster creation page (https://us-west-2.console.aws.amazon.com/ecs/v2/create-cluster?region=us-west-2).

    b) For the cluster name, enter pds-nucleus-ecs-cluster.

    c) Select a VPC and subnets (if you are not sure about the correct VPC and subnets to select, please contact the NGAP system admin team).

    d) Under the “Infrastructure” section, make sure that “AWS Fargate (serverless)” is selected.

    e) Press the “Create” button to create the cluster.


Step 3: Create an ECS Task Definition
=====================================

It is required to create ECS task definitions for each docker container to be used in the workflow. In this tutorial we use only one docker container (the docker container of PDS Validate tool) and therefore we will create only one ECS task definition.

1. Login to AWS (NGAP) with  NGAPShApplicationDeveloper role.

2. Visit Amazon Elastic Container Service – Task Definitions on NGAP (https://us-west-2.console.aws.amazon.com/ecs/v2/task-definitions?region=us-west-2 ).

3. Click on “Create new task definition”.

4. Select “Create new task definition with JSON”.

        a. Copy the following JSON text and paste it to overwrite the default content in the task definition JSON.



        .. code-block:: json

            {
                "family": "pds-validate-tutorial-task",
                "containerDefinitions": [
                    {
                        "name": " pds-validate- tutorial-task",
                        "image": "<ECR IMAGE URL OF VALIDATE TOOL>",
                        "cpu": 0,
                        "memory": 128,
                        "portMappings": [],
                        "essential": true,
                        "entryPoint": [],
                        "command": [],
                        "environment": [],
                        "mountPoints": [],
                        "volumesFrom": [],
                        "logConfiguration": {
                            "logDriver": "awslogs",
                            "options": {
                                "awslogs-group": "/ecs/pds-validate-tool",
                                "awslogs-region": "us-west-2",
                                "awslogs-stream-prefix": "ecs"
                            }
                        }
                    }
                ],
                "taskRoleArn": "<TASK ROLE ARN>",
                "executionRoleArn": "<EXECUTION ROLE ARN>",
                "networkMode": "awsvpc",
                "volumes": [],
                "requiresCompatibilities": [
                    "EC2",
                    "FARGATE"
                ],
                "cpu": "4096",
                "memory": "8192",
                "runtimePlatform": {
                    "operatingSystemFamily": "LINUX"
                }
            }



        b. Replace the “<IMAGE>” value with the image URL of PDS Validate ECR image URL (which can be found by visiting the ECR image of PDS Validate tool). E.g.: 12345678.dkr.ecr.us-west-2.amazonaws.com/pds-validate-tutorial:latest.

        c.  Replace the “<TASK ROLE ARN>" value with the Task Role, IAM role ARN (This can be obtained from the NGAP system admin team or by checking the IAM roles on your NGAP account).

        d. Replace the “<EXECUTION ROLE ARN>" value with the Execution Role, IAM role ARN (This can be obtained from the NGAP system admin team or by checking the IAM roles on your NGAP account).

        e. Change the CPU and memory values of the above JSON, if it is required to allocate higher values.


5. Press the “Create” button to create the Task Definition.

6. Visit Cloud Watch (https://us-west-2.console.aws.amazon.com/cloudwatch/home?region=us-west-2#logsV2:log-groups ) and create a Cloud Watch Log Group called “/ecs/pds-validate-tutorial-task” to save the logs related to this ECS task.
