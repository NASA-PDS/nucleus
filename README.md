
# Nucleus

PDS Nucleus is a software platform used to create workflows for planetary data.

### Documentation

To build the documentation:

    python3 -m venv venv
    source venv/bin/activate
    pip install -e '.[dev]'
    sphinx-build -b html docs/source docs/build/html

Publish the pages on gh-pages branch


