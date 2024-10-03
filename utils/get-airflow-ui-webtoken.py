# Copyright 2024, California Institute of Technology ("Caltech").
# U.S. Government sponsorship acknowledged.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other
# materials provided with the distribution.
# * Neither the name of Caltech nor its operating division, the Jet Propulsion
# Laboratory, nor the names of its contributors may be used to endorse or
# promote products derived from this software without specific prior written
# permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import boto3
import getpass

# Set constants

# Obtain the Cognito identity pool ID from the PDS Engineering Team
IDENTITY_POOL_ID = '<IDENTITY_POOL_ID>'

# Obtain the AWS Account ID of Nucleus Deployment from the PDS Engineering Team
AWS_ACCOUNT_ID = '<AWS_ACCOUNT_ID>'

# Obtain the Cognito user pool ID from the PDS Engineering Team
COGNITO_USER_POOL_ID = '<COGNITO_USER_POOL_ID>'

# Obtain the Cognito Client ID from the PDS Engineering Team
COGNITO_CLIENT_ID = 'COGNITO_CLIENT_ID'

# AWS Region
REGION = 'us-west-2'

# Obtain the Nucleus Airflow Environment Name from the PDS Engineering Team
NUCLEUS_AIRFLOW_ENVIRONMENT_NAME = '<NUCLEUS_AIRFLOW_ENVIRONMENT_NAME>'


# The following code obtains an ID token using the USER_PASSWORD_AUTH auth flow of client_idp.initiate_auth().
# This code interactively requests for username and password to obtain the ID token.

# Create Cognito IDP client
client_idp = boto3.client('cognito-idp', region_name=REGION)

# Promt the user to enter the username and password
username = input('Enter your Cognito username: ')
password = getpass.getpass('Enter your Cognito password: ')
auth_params = {
    "USERNAME": username,
    "PASSWORD": password
}

# Get tokens from Cognito
response = client_idp.initiate_auth(
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters=auth_params,
    ClientId=COGNITO_CLIENT_ID
)

# Read ID token
id_token = response['AuthenticationResult']['IdToken']

# Create Cognito Identity client
client_identify = boto3.client('cognito-identity', region_name=REGION)

# Get Identify ID
response_identity_get_id = client_identify.get_id(
    AccountId=AWS_ACCOUNT_ID,
    IdentityPoolId=IDENTITY_POOL_ID,
    Logins={
        'cognito-idp.us-west-2.amazonaws.com/' + COGNITO_USER_POOL_ID: id_token
    }
)
IDENTITY_ID = response_identity_get_id['IdentityId']

# Get temporary AWS credentials for the identity
aws_credentials = client_identify.get_credentials_for_identity(
    IdentityId=IDENTITY_ID,
    Logins={
        'cognito-idp.us-west-2.amazonaws.com/' + COGNITO_USER_POOL_ID: id_token
    }
)

access_key_id = aws_credentials['Credentials']['AccessKeyId']
secret_key = aws_credentials['Credentials']['SecretKey']
session_token = aws_credentials['Credentials']['SessionToken']

mwaa = boto3.client(
    'mwaa',
    aws_access_key_id=access_key_id,
    aws_secret_access_key=secret_key,
    aws_session_token=session_token,
    region_name=REGION,
)

response = mwaa.create_web_login_token(
    Name=NUCLEUS_AIRFLOW_ENVIRONMENT_NAME
)

webServerHostName = response["WebServerHostname"]
webToken = response["WebToken"]
airflowUIUrl = 'https://{0}/aws_mwaa/aws-console-sso?login=true#{1}'.format(webServerHostName, webToken)

print("Here is your Nucleus Airflow UI URL: ")
print(airflowUIUrl)
