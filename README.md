# Nucleus

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.7996080.svg)](https://doi.org/10.5281/zenodo.7996080)

PDS Nucleus is a software platform used to create workflows for managing data archives.

## User Documentation

Please visit the documentation at: https://nasa-pds.github.io/doi-service/

## Developers

## Prerequisites

- Python 3.9 or above
- Access to Planetary Data Cloud

## Test

TBD

## Deploy

See in this repository:

    https://github.com/NASA-PDS/nucleus/tree/main/terraform

## Documentation Management

Documentation about the documentation is described in this section.


### Design

See in this repository:

    https://github.com/NASA-PDS/nucleus/tree/main/docs

or the `docs` directory in the source package.

### User Documentation

User documentation is managed with Sphinx, which is also installed in your Python virtual environment when you run `pip install --editable .[dev]`:

    python3 -m venv venv
    source venv/bin/activate
    pip install -e '.[dev]'
    sphinx-build -b html docs/source docs/build/html

Publish the pages on gh-pages branch
