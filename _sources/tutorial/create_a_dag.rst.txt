++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
Create an Airflow DAG (Workflow)
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

---------------------------------------------------------------------------------------------------------------------
Overview
---------------------------------------------------------------------------------------------------------------------

This tutorial shows a way to develop a very basic Airflow workflow. The following section will elaborate each of the above steps with more details as we go through the tutorial.

This tutorial will build a very basic workflow with 3 tasks as follows.

.. code-block::

    | Print Start Time |  ->	  | Execute PDS Validate Tool Help |    ->      | Print End Time |

.. warning::

	For this tutorial you need an ECS task definition to be created as described in :doc:`create_an_operator` .

  .. note::

  	The tutorial should be executed by a PDS Node operator

The steps are:

1) Implement a DAG (workflow) primarily using the Airflow ECS Operator.

    a. https://airflow.apache.org/docs/apache-airflow/stable/tutorial/fundamentals.html
    b. https://docs.aws.amazon.com/mwaa/latest/userguide/samples-ecs-operator.html

2)  Upload DAGs to S3 bucket.

3) Observe if the DAG is loaded in the Airflow UI.

4) Trigger the DAG (workflow).


---------------------------------------------------------------------------------------------------------------------
Detailed Tutorial
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
