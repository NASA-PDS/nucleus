# Use an AWS Lambda image for a consistent build environment
# This image is explicitly for the x86_64 architecture, which is what we need for Lambda function.
FROM public.ecr.aws/lambda/python:3.12-x86_64

# Set the working directory inside the container
WORKDIR /var/task

# Install the 'dnf' package manager for installing utilities
# and then install 'zip' utility.
RUN dnf install -y zip && dnf clean all

# Copy the requirements file into the container.
COPY requirements.txt .

# Install Python dependencies for the x86_64 architecture into a 'python' subdirectory.
# The `pip install` command will now place all packages in a directory called `python`.
# This is the key change to align with Lambda's expected directory structure for packages.
RUN pip install --target=python -r requirements.txt

# Copy the actual lambda function code into the container's root directory.
COPY pds_nucleus_alb_auth.py .

# This CMD is not strictly necessary for this use case, as the container
# is used for building and the `zip` command is executed via `docker run`.
CMD ["ls"]
