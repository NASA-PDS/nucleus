from setuptools import setup, find_packages

setup(
    name="pds.nucleus",
    version="0.1.0-dev",
    packages=find_packages(where="utils"),
    package_dir={"": "utils"},
)
