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


## Secret Detection

The following commands can be used to detect secrets in the code.

1) Setup a pythion virtual environment.

```shell
mkdir ~/Tools
python3 -m venv ~/Tools/detect-secrets
source ~/Tools/detect-secrets/bin/activate
pip install git+https://github.com/NASA-AMMOS/slim-detect-secrets.git@exp
```

2) Execute the following command in Nucleus root directory to scan the code for secrets.

```shell
detect-secrets scan --disable-plugin AbsolutePathDetectorExperimental \
    --exclude-files '\.secrets\..*' \
    --exclude-files '\.git.*' \
    --exclude-files '\.pre-commit-config\.yaml' \
    --exclude-files '\.mypy_cache' \
    --exclude-files '\.pytest_cache' \
    --exclude-files '\.tox' \
    --exclude-files '\.venv' \
    --exclude-files 'venv' \
    --exclude-files 'dist' \
    --exclude-files 'build' \
    --exclude-files '.*\.egg-info' \
    --exclude-files '.*\.tfstate' \
    --exclude-files '.*\.tfvars'
    > .secrets.baseline
```

3) Execute the following command in Nucleus root directory to audit the possible secrets detected.

```shell
detect-secrets audit .secrets.baseline
```

This will create a `.secrets.baseline` in Nucleus root directory. Commit and push that file, in order to pass the checks in GitHub during a pull request.
