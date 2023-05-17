============================================
Creating a Workflow in PDS Nucleus
============================================

PDS Nucleus is a software platform used to create workflows for planetary data. Nucleus is primarily based on Apache Airflow, which is a widely used open-source platform for developing, scheduling, and monitoring workflows in industry. Workflows are one of the most important concepts in Nucleus.

--------------------------------------
Overview of Steps to Create a Workflow
--------------------------------------

The following steps are required to develop a workflow in Nucleus.

However, some of the steps to be executed by a person who has access permissions to create AWS
resources such as ECS Task Definitions. Once those resources are created, it is fairly simple to
create a DAG that uses previously created AWS resources.

The following steps can be divided in to 2 sections.

Section 1: Creating AWS resources to be used by the Airflow DAG - To be executed with access to create AWS resources

Section 2: Creating actual Airflow DAG - To be executed by a PDS Node operator

---------------------------------------------------------------------------------------------------------------------
Section 1: Creating AWS resources to be used by the Airflow DAG - To be executed with access to create AWS resources
---------------------------------------------------------------------------------------------------------------------
1)  Create and push the docker image to ECR.

2)  Create an EFS volume to share data/configuration files between docker containers (optional, only if the use case must share data/configuration between tasks).

3)  Make sure that you have an ECS Cluster to execute ECS tasks.

4)  Create an ECS task (This can be done through AWS Console or Terraform).

    a. Create container definition
    b. Create ECS task definition (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/create-task-definition.html )

---------------------------------------------------------------------------------------------------------------------
Section 2: Creating actual Airflow DAG  - To be executed by a PDS Node operator
---------------------------------------------------------------------------------------------------------------------

1) Implement a DAG (workflow) primarily using the Airflow ECS Operator.

    a. https://airflow.apache.org/docs/apache-airflow/stable/tutorial/fundamentals.html
    b. https://docs.aws.amazon.com/mwaa/latest/userguide/samples-ecs-operator.html

2)  Upload DAGs to S3 bucket.

3) Observe if the DAG is loaded in the Airflow UI.

4) Trigger the DAG(workflow).


The following section is a basic tutorial prepared to guide you through the Nucleus workflow creation process.

========
Tutorial
========

This tutorial shows a way to develop a very basic Airflow workflow. The following section will elaborate each of the above steps with more details as we go through the tutorial.

This tutorial will build a very basic workflow with 3 tasks as follows.

.. code-block::

    | Print Start Time |  ->	  | Execute PDS Validate Tool Help |    ->      | Print End Time |


----------------------------------------------------------------------------------------------------------------------
Section 1: Creating AWS resources to be used by the Airflow DAG - To be executed with access to create AWS resources
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


---------------------------------------------------------------------------------------------------------------------
Section 2: Creating actual Airflow DAG  - To be executed by a PDS Node operator
---------------------------------------------------------------------------------------------------------------------

Step 1: Implement DAG with Airflow ECS Operator
================================================

In Airflow, a DAG (Directed Acyclic Graph) is a collection of tasks that you want to execute, organized in a way that reflects their relationships and dependencies. A DAG is defined in a Python script, which represents the DAGs structure (tasks and their dependencies) as code.

The following Airflow document explains the basic concepts such as DAGs.
https://airflow.apache.org/docs/apache-airflow/1.10.10/concepts.html#

While DAGs describe how to run a workflow, Operators determine what gets done by a task.

Some of the common operators are:

BashOperator - executes a bash command
PythonOperator - calls an arbitrary Python function
EmailOperator - sends an email
SimpleHttpOperator - sends an HTTP request
ECSOperator - runs a task defined in AWS ECS (runs a docker container on an ECS Cluster)

Since most of the PDS components can be executed as a docker container (which is defined as an ECS task), we can use the ECSOperator to execute tasks.
For example:

The validate tool can be represented as a task in an Airflow Dag as follows. Note that the name of the ECS task definition to be executed (pds-validate-tutorial-task) is given as the value for task_definition.


.. code-block::

       # PDS Validate Tool
       pds_validate = ECSOperator(
           task_id="Validate_Task",
           dag=dag,
           cluster=ECS_CLUSTER_NAME,
           task_definition="pds-validate-tutorial-task",
           launch_type=ECS_LAUNCH_TYPE,
           network_configuration={
               "awsvpcConfiguration": {
                   "securityGroups": ECS_SECURITY_GROUPS,
                   "subnets": ECS_SUBNETS,
               },
           },
           overrides={
               "containerOverrides": [],
           },
           awslogs_group=ECS_AWS_LOGS_GROUP,
           awslogs_stream_prefix="ecs/pds-validate-tutorial-task"
       )


In addition, the following values should be set in the above JSON:

    **cluster:** The ECS cluster created/checked in the previous steps of the tutorial.

    **securityGroups:** A comma separated list of security groups. These are the same security groups used by the Managed Workflows for Apache Airflow (MWAA). It is possible to check this security group by visiting the https://us-west-2.console.aws.amazon.com/mwaa/home?region=us-west-2#environments/PDS-Nucleus-Airflow-Env and checking for VPC security group(s).

    **subnets:** A comma separated list of subnets. These are the same subnets used by the Managed Workflows for Apache Airflow (MWAA). It is possible to check this security group by visiting the https://us-west-2.console.aws.amazon.com/mwaa/home?region=us-west-2#environments/PDS-Nucleus-Airflow-Env and checking for Subnets.

    **awslogs_stream_prefix:** Any prefix that can be used to identify AWS logs for this ECS Task.

Also, the Airflow BashOperator can be used to print the start date and end date as follows.

.. code-block::

      # Print start date
       print_start_date = BashOperator(
           task_id='Print_Start_Date',
           bash_command='date',
           trigger_rule=TriggerRule.ALL_DONE
       )



Finally, the flow of tasks can be represented as follows.

.. code-block::

   # Workflow
   print_start_date >> pds_validate >> print_end_date



The above example is a very simple workflow. It is possible to define parallel paths in the workflows as follows.

.. code-block::

    # Parallel Paths in the Workflow
	Task_a >> Task_b >> Task_c >> Task_d >> Task_e
	Task_b >> Task_f >> Task_d


Read more about creating DAGs in following links:

a) https://airflow.apache.org/docs/apache-airflow/stable/tutorial/fundamentals.html

b) https://docs.aws.amazon.com/mwaa/latest/userguide/samples-ecs-operator.html


The completed DAG should look as follows. Save this DAG in a python file called pds-validate-tutorial.py.


.. code-block::

    # PDS Nucleus Tutorial Use Case DAG

    from airflow import DAG
    from airflow.operators.bash import BashOperator
    from airflow.providers.amazon.aws.operators.ecs import ECSOperator
    from airflow.utils.dates import days_ago
    from airflow.utils.trigger_rule import TriggerRule


    # ECS configurations
    ECS_CLUSTER_NAME = "pds-nucleus-ecc-tf"
    ECS_LAUNCH_TYPE = "FARGATE"
    ECS_SUBNETS = [<COMMA SEPERATED LIST OF SUBNET IDs>]
    ECS_SECURITY_GROUPS = [<COMMA SEPERATED LIST OF SECURITY GROUPS>]
    ECS_AWS_LOGS_GROUP = "/ecs/pds-airflow-ecs-tf"


    with DAG(
           dag_id="Nucleus_Tutorial",
           schedule_interval=None,
           catchup=False,
           start_date=days_ago(1)
    ) as dag:


       # Print start date
       print_start_date = BashOperator(
           task_id='Print_Start_Date',
           bash_command='date',
           trigger_rule=TriggerRule.ALL_DONE
       )


       # PDS Validate Tool
       pds_validate = ECSOperator(
           task_id="Validate_Task",
           dag=dag,
           cluster=ECS_CLUSTER_NAME,
           task_definition="pds-validate-tutorial-task",
           launch_type=ECS_LAUNCH_TYPE,
           network_configuration={
               "awsvpcConfiguration": {
                   "securityGroups": ECS_SECURITY_GROUPS,
                   "subnets": ECS_SUBNETS,
               },
           },
           overrides={
               "containerOverrides": [],
           },
           awslogs_group=ECS_AWS_LOGS_GROUP,
           awslogs_stream_prefix="ecs/pds-validate-tutorial-task"
       )


       # Print end date
       print_end_date = BashOperator(
           task_id='Print_End_Date',
           bash_command='date',
           trigger_rule=TriggerRule.ALL_DONE
       )


       # Workflow
       print_start_date >> pds_validate >> print_end_date


Step 2: Upload the DAG to S3 Bucket
====================================

To make the DAG that we created above available to Nucleus, it is required to upload the DAG file (pds-validate-tutorial.py) to a specific location in an S3 bucket.

1. Login to AWS (NGAP) with  NGAPShApplicationDeveloper role.

2. Visit the dags directory of nucleus-airflow-dags-bucket (https://s3.console.aws.amazon.com/s3/buckets/nucleus-airflow-dags-bucket?region=us-west-2&prefix=dags/&showversions=false ).

3. Upload the pds-validate-tutorial.py file using the “Upload” button.


Step 3: Observe if the DAG is Loaded in Airflow UI
===================================================
1. Login to AWS (NGAP) with  NGAPShApplicationDeveloper role.

2. Visit Airflow UI of Nucleus (https://us-west-2.console.aws.amazon.com/mwaa/home?region=us-west-2#environments/PDS-Nucleus-Airflow-Env/sso).

3. Click on the DAGs menu.

4. Wait until a DAG called “Nucleus_Tutorial'' appears in the list of DAGs.


Step 4:  Trigger the DAG
========================

1. After the “Nucleus_Tutorial” appears in the list of DAGs, click on the “Play” button at the right side of the DAG (under the “Actions”).

2. Select the option “Trigger DAG”.

3. Click on the name of the DAG “Nucleus_Tutorial” to see the details of the DAG.

4. Click on the tab called “Graph” to see the progress of the DAG.
