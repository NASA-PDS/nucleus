++++++++++++++
User's Guide
++++++++++++++

PDS Nucleus is a software platform used to create workflows for planetary data. Nucleus is primarily based on Apache Airflow, which is a widely used open-source platform for developing, scheduling, and monitoring workflows in industry. Workflows are one of the most important concepts in Nucleus.


In Apache Airflow, the workflow definition is called a **DAG (Directional Acyclic Graph)**. The first tutorial provides a guide to create a new workflow, or DAG in Nucleus.

Each workflow is made of steps which run **operators** deployed on AWS. To create a DAG, you need some operators ready to be used by Nucleus, the second tutorial provides a guide to create a new operator.

.. toctree::
  :maxdepth: 1

  Create Airflow DAG <create_a_dag>
  Create an Operator <create_an_operator>
