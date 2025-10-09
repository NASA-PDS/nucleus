# Nucleus

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.7996080.svg)](https://doi.org/10.5281/zenodo.7996080)

PDS **Nucleus** is a software platform used to create workflows for the Planetary Data System (PDS).

---

## User Documentation

Please visit the documentation at:  
👉 https://nasa-pds.github.io/nucleus/

---

## Developers

https://github.com/NASA-PDS/nucleus/graphs/contributors 

### Prerequisites

The prerequisites to deploy and use Nucleus are available at:
https://github.com/NASA-PDS/nucleus/tree/main/terraform#prerequisites-to-deploy-nucleus-baseline-system  

---

## Test

The **Nucleus** workflows are tested using a basic **Registry Loader** workflow, which is deployed as part of the initial Nucleus deployment.  
This workflow includes several PDS tools such as **Validate**, **Harvest**, and **Archive**.

To test Nucleus:

1. Log in to the Nucleus web interface (URL and user credentials can be obtained from the Planetary Data System team).  
2. Execute the **basic registry loader** workflow.  
3. Verify that each workflow task reaches a **successful** state.  

A successful execution of all tasks in this workflow indicates that the Nucleus integration test has passed.

---

## Deploy

The Terraform-based Nucleus deployment guide is available at:  
https://github.com/NASA-PDS/nucleus/tree/main/terraform

---

### Design

Requirements, trade studies, and design documents are available at:  
https://github.com/NASA-PDS/nucleus/tree/main/docs  
or in the `docs` directory within the source package.

---

### User Documentation and Documentation Management

User documentation is managed with **Sphinx**, which is also installed in your Python virtual environment when you run:

```bash
python3 -m venv venv
source venv/bin/activate
pip install 'sphinx~=8.2.3' 'sphinx_rtd_theme~=3.0.2' 'myst-parser~=4.0.1'
sphinx-build -b html docs/source docs/build/html
