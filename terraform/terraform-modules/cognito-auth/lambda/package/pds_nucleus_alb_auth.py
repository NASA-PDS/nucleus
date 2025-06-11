'''
This lambda function is developed based on the Technical Guide "Accessing a private Amazon MWAA environment using
federated identities" by AWS.

https://d1.awsstatic.com/whitepapers/accessing-a-private-amazon-mwaa-environment-using-federated-identities.pdf and
https://github.com/aws-samples/alb-sso-mwaa

'''

import os
import json
import logging
import requests
import boto3
from datetime import timezone, datetime
import re
from botocore.config import Config
import urllib.request
from jose import jwt

sts = boto3.client('sts')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
ALB_COOKIE_NAME = os.getenv('ALB_COOKIE_NAME','AWSELBAuthSessionCookie').strip()

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
AIRFLOW_ENV_NAME = os.getenv("AIRFLOW_ENV_NAME")

COGNITO_GROUP_TO_ROLE_MAP = json.loads(os.environ.get('COGNITO_GROUP_TO_ROLE_MAP', '{}'))

if not COGNITO_GROUP_TO_ROLE_MAP:
    COGNITO_GROUP_TO_ROLE_MAP = [
        {"cognito-group":"PDS_NUCLEUS_AIRFLOW_ADMIN", "iam-role":"pds_nucleus_airflow_admin_role"},
        {"cognito-group":"PDS_NUCLEUS_AIRFLOW_OP", "iam-role":"pds_nucleus_airflow_op_role"},
        {"cognito-group":"PDS_NUCLEUS_AIRFLOW_USER", "iam-role":"pds_nucleus_airflow_user_role"},
        {"cognito-group":"PDS_NUCLEUS_AIRFLOW_VIEWER", "iam-role":"pds_nucleus_airflow_viewer_role"}
    ]

keys_url = 'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format(AWS_REGION, COGNITO_USER_POOL_ID)

#  Download the public keys only on cold start instead of re-downloading the public keys every time
with urllib.request.urlopen(keys_url) as f:
    response = f.read()
jsonWebKeys = json.loads(response.decode('utf-8'))['keys']


def lambda_handler(event, context):

    path = event['path']
    query_params = event.get("multiValueQueryStringParameters")
    headers = event['multiValueHeaders']

    if 'x-amzn-oidc-data' in headers:
        encoded_jwt = headers['x-amzn-oidc-data'][0]
        encoded_access_token = headers['x-amzn-oidc-accesstoken'][0]

        user_claims = validate_jwt_and_get_jwt_claims(encoded_jwt, 'oidc-data')
        decoded_access_token = validate_jwt_and_get_jwt_claims(encoded_access_token, 'oidc-accesstoken')

        # Check for invalid tokens
        if  user_claims is None or decoded_access_token is None:
            logger.error("Invalid token")
            return close(headers, "Unauthorized", status_code=401)

        iam_role_arn = get_iam_role_arn(decoded_access_token)

        if iam_role_arn is None:
            logger.error("Invalid token")
            return close(headers, "Unauthorized", status_code=401)

        if path == '/aws_mwaa/aws-console-sso':
            redirect = login(headers=headers, query_params=query_params, user_claims=user_claims, iam_role_arn=iam_role_arn)
        else:
            redirect = close(headers, f"Bad request: {path}, {query_params}, {headers}", status_code=400)
    elif path == '/logout':
        redirect = logout(headers=headers, query_params=query_params)
    else:
        redirect = close(headers, f"Bad request: {path}, {query_params}, {headers}", status_code=400)

    if not redirect:
        redirect = close(headers, f"Runtime error", status_code=500)

    return redirect


def logout(headers, query_params):
    """
    Function that returns a redirection to an appropriate URL that includes a web login token.
    """
    retval = ""

    try:
        alb_cookie_name = os.getenv("ALB_COOKIE_NAME", "AWSELBAuthSessionCookie")
        cookie = headers.get('cookie')
        if cookie:
            m=re.search(f"{alb_cookie_name}[^=]*", cookie[0])
            alb_cookie_name = m.group(0) if m else alb_cookie_name

            time_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
            headers['Set-Cookie'] = [ f"{alb_cookie_name}=deleted;Expires={time_now};Path=/", f"{alb_cookie_name}=deleted;Expires={time_now};Path=/" ]
            retval = close(headers, "Logout OK", status_code=200)
        else:
            retval = close(headers, "Logout failed", status_code=400)
    except Exception as error:
        logger.error(str(error))
        retval = close(headers, "Logout failed", status_code=500)

    return retval


def login(headers, query_params=None, user_claims=None,iam_role_arn=None):
    """
    Function that returns a redirection to Airflow UI with a web login token.
    """
    redirect = ""

    try:
        user_name = user_claims.get('username', "") if user_claims else ""
        mwaa = get_mwaa_client(iam_role_arn, user=user_name)
        logger.debug(f"Create Airflow web login token for environment: '{AIRFLOW_ENV_NAME}'")
        if AIRFLOW_ENV_NAME:
            response = mwaa.create_web_login_token(Name=AIRFLOW_ENV_NAME)
            mwaa_web_token = response.get("WebToken")
            host = response.get("WebServerHostname")
            logger.info('Redirecting with Amazon MWAA WebToken')
            redirect = {
                'statusCode': 302,
                'statusDescription': '302 Found',
                'multiValueHeaders': {
                    'Location':[f'https://{host}/aws_mwaa/aws-console-sso?login=true#{mwaa_web_token}']
                }
            }
    except Exception as error:
        logger.error(str(error))

    if not redirect:
        redirect = close(headers, "Login Failed. Please check your Cognito user groups with the help of PDS Engineering Node.",
                         status_code=401)

    return redirect

def get_mwaa_client(role_arn, user):
    """
    Returns an Amazon MWAA client under the given IAM role.
    """
    mwaa = None
    try:
        response = sts.assume_role(RoleArn=role_arn, RoleSessionName=user, DurationSeconds=900)
        credentials = response.get('Credentials')
        config = Config(user_agent=user)

        mwaa = boto3.client(
            'mwaa',
            aws_access_key_id=credentials.get('AccessKeyId'),
            aws_secret_access_key=credentials.get('SecretAccessKey'),
            aws_session_token=credentials.get('SessionToken'),
            region_name = AWS_REGION,
            config=config)
    except Exception as error:
        logger.error(str(error))
    return mwaa

def get_json_webkey_with_kid(kid):
    """
    Returns the JSON Web Key that matches the given key ID.
    """
    for jwk in jsonWebKeys:
        if jwk['kid'] == kid:
            return jwk
    return None

def validate_jwt_and_get_jwt_claims(encoded_jwt, token_type):
    """
    Validates the JWT token for digital signature and other criteria and returns JWT claims.

    :param encoded_jwt: Encodec JWT (Cognito token)
    :return: Payload containing JWT claims
    """
    payload = None

    try:

        headers = jwt.get_unverified_headers(encoded_jwt)
        kid = headers['kid']
        alg = headers['alg']


        if token_type == 'oidc-data':
            url = 'https://public-keys.auth.elb.' + AWS_REGION + '.amazonaws.com/' + kid
            req = requests.get(url)
            pub_key = req.text

        if token_type == 'oidc-accesstoken':
            pub_key = get_json_webkey_with_kid(kid)

        # Verify the token and get the payload
        payload = jwt.decode(
            encoded_jwt,
            pub_key,
            algorithms=[alg],
            issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
            options={
                "verify_aud": True,
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "require": ["token_use", "exp", "iss", "sub"],
            },
        )
        logger.info("Token is valid")
    except jwt.ExpiredSignatureError as error:
        logger.error("Token has expired.")
        logger.error(error)
    except jwt.JWTError as error:
        logger.error("Invalid token.")
        logger.error(error)
    except Exception as error:
        logger.error(error)

    return payload



def get_iam_role_arn(jwt_payload):
    """
    Returns the name of an IAM role based on the 'custom:idp-groups' contained in the JWT token .

    This list contains the mappings between Cognito groups and their corresponding IAM role.
    The list is sorted by precedence, so, if a user belongs to more than one group, it's given
    mapped to a role that contains more permissions

    """

    role_arn = ''

    if 'cognito:groups' in jwt_payload:
        user_groups = jwt_payload['cognito:groups']
        user_name = jwt_payload['username']

        for mapping in COGNITO_GROUP_TO_ROLE_MAP:
            if mapping['cognito-group'] in user_groups:
                role_name = mapping['iam-role']
                logger.info(f"User : {user_name} logs in with Role: {role_name}")
                role_arn = f'arn:aws:iam::{AWS_ACCOUNT_ID}:role/{role_name}'
                break
    return role_arn


def parse_groups(groups):
    """    Converts the groups SAML claim content to a list of strings     """
    groups = groups.replace('[', '').replace(']', '').replace(' ', '')
    return groups.split(',')


def close(headers, message, status_code=200):
    body = f'<html><body><h3>{message}</h3></body></html>'
    headers['Content-Type'] = ['text/html']
    return {
        'statusCode': status_code,
        'multiValueHeaders': headers,
        'body': body,
        'isBase64Encoded': False
    }
