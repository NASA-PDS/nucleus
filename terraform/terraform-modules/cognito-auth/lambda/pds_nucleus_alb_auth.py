'''
This lambda function is developed based on the Technical Guide "Accessing a private Amazon MWAA environment using
federated identities" by AWS.

https://d1.awsstatic.com/whitepapers/accessing-a-private-amazon-mwaa-environment-using-federated-identities.pdf and
https://github.com/aws-samples/alb-sso-mwaa

'''

import os
import json
import html
import logging
import requests
import boto3
from datetime import timezone, datetime
import re
from botocore.config import Config
import urllib.parse
import urllib.request
from jose import jwt

sts = boto3.client('sts')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
ALB_COOKIE_NAME = os.getenv('ALB_COOKIE_NAME','AWSELBAuthSessionCookie').strip()

ALLOWED_ALGORITHMS_OIDC_DATA = ['ES256']
ALLOWED_ALGORITHMS_ACCESS_TOKEN = ['RS256']

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
AIRFLOW_ENV_NAME = os.getenv("AIRFLOW_ENV_NAME")

# For the /nucleus/products search route.
DB_CLUSTER_ARN = os.getenv("DB_CLUSTER_ARN")
DB_SECRET_ARN = os.getenv("DB_SECRET_ARN")
PDS_TRACKING_DATABASE_NAMES = json.loads(os.environ.get("PDS_TRACKING_DATABASE_NAMES", "[]"))
PRODUCT_TRACKING_PAGE_SIZE = 100

# Columns a caller may filter on. An explicit allowlist, not f-string
# interpolation of arbitrary query-string keys, keeps this from becoming a
# SQL injection point through the column name itself.
PRODUCT_TRACKING_FILTERABLE_COLUMNS = {
    "lidvid": "=",
    "s3_url_of_product_label": "LIKE",
    "status": "=",
    "validate_status": "=",
    "harvest_status": "=",
    "registry_status": "=",
    "pds_node": "=",
}

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

        if path.lower() == '/nucleus/products':
            user_name = user_claims.get('username', "") if user_claims else ""
            redirect = search_products(headers=headers, query_params=query_params,
                                        iam_role_arn=iam_role_arn, user=user_name)
        elif path.lower().startswith('/nucleus') or path == '/aws_mwaa/aws-console-sso':
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


PRODUCT_TRACKING_COLUMNS = [
    "s3_url_of_product_label", "lidvid", "pds_node", "ingestion_source",
    "status", "validate_status", "harvest_status",
    "registry_status", "registry_url", "batch_number", "dag_run_id",
    "last_updated_epoch_time",
]


def get_rds_data_client(role_arn, user):
    """
    Returns an RDS Data API client under the given IAM role, same pattern as
    get_mwaa_client above.
    """
    rds_data = None
    try:
        response = sts.assume_role(RoleArn=role_arn, RoleSessionName=user, DurationSeconds=900)
        credentials = response.get('Credentials')
        config = Config(user_agent=user)

        rds_data = boto3.client(
            'rds-data',
            aws_access_key_id=credentials.get('AccessKeyId'),
            aws_secret_access_key=credentials.get('SecretAccessKey'),
            aws_session_token=credentials.get('SessionToken'),
            region_name=AWS_REGION,
            config=config)
    except Exception as error:
        logger.error(str(error))
    return rds_data


def _single_query_param(query_params, key):
    """ multiValueQueryStringParameters values are lists; take the first. """
    if not query_params or key not in query_params:
        return None
    values = query_params[key]
    return values[0] if values else None


def _build_where_clause(query_params):
    """
    Builds a parameterized WHERE clause from an allowlisted set of filters,
    shared by both the row query and the summary/pie-chart query so the
    summary always reflects whatever the caller is currently filtered to.

    Column names come only from PRODUCT_TRACKING_FILTERABLE_COLUMNS, never
    from the query string itself, so this can't become a SQL injection point
    through the column name; values are always bound parameters.
    """
    where_parts = []
    parameters = []
    for column, operator in PRODUCT_TRACKING_FILTERABLE_COLUMNS.items():
        value = _single_query_param(query_params, column)
        if not value:
            continue
        param_name = f"{column}_param"
        if operator == "LIKE":
            where_parts.append(f"{column} LIKE :{param_name}")
            parameters.append({"name": param_name, "value": {"stringValue": f"%{value}%"}})
        else:
            where_parts.append(f"{column} = :{param_name}")
            parameters.append({"name": param_name, "value": {"stringValue": value}})
    return (" WHERE " + " AND ".join(where_parts)) if where_parts else "", parameters


def _current_page(query_params):
    """1-indexed; anything malformed or below 1 falls back to page 1."""
    raw = _single_query_param(query_params, "page")
    try:
        page = int(raw)
    except (TypeError, ValueError):
        return 1
    return page if page >= 1 else 1


def _build_product_tracking_query(query_params):
    """
    Builds a parameterized, paginated SELECT from an allowlisted set of
    filters. Ordered by most-recently-updated first, so page N means the
    same thing on every request rather than an arbitrary row order.

    Pagination is applied per database, not globally across the merged
    result -- each database contributes up to PRODUCT_TRACKING_PAGE_SIZE
    rows per page. Simpler than a true cross-database cursor, and with the
    row counts this table sees, "page 3" being approximate across combined
    databases is an acceptable trade for not needing distributed paging.
    """
    where_sql, parameters = _build_where_clause(query_params)
    page = _current_page(query_params)
    offset = (page - 1) * PRODUCT_TRACKING_PAGE_SIZE

    parameters = list(parameters) + [
        {"name": "limit_param", "value": {"longValue": PRODUCT_TRACKING_PAGE_SIZE}},
        {"name": "offset_param", "value": {"longValue": offset}},
    ]
    sql = (
        f"SELECT {', '.join(PRODUCT_TRACKING_COLUMNS)} FROM product_tracking"
        f"{where_sql} ORDER BY last_updated_epoch_time DESC "
        "LIMIT :limit_param OFFSET :offset_param"
    )
    return sql, parameters


PRODUCT_TRACKING_SUMMARY_COLUMNS = [
    "total", "backlog_count", "realtime_count", "validated_count",
    "harvested_count", "registry_checked_count", "all_good_count", "issues_count",
]


def _build_product_tracking_summary_query(query_params):
    """
    One aggregate query per database (no row fan-out) computing every
    number the summary panel and pie chart need, filtered by the same
    criteria as the current search.
    """
    where_sql, parameters = _build_where_clause(query_params)
    sql = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN ingestion_source = 'backlog' THEN 1 ELSE 0 END) AS backlog_count,
            SUM(CASE WHEN ingestion_source = 'realtime' THEN 1 ELSE 0 END) AS realtime_count,
            SUM(CASE WHEN validate_status = 'passed' THEN 1 ELSE 0 END) AS validated_count,
            SUM(CASE WHEN harvest_status IN ('loaded', 'already_registered') THEN 1 ELSE 0 END) AS harvested_count,
            SUM(CASE WHEN registry_status IS NOT NULL AND registry_status <> 'not_checked' THEN 1 ELSE 0 END) AS registry_checked_count,
            SUM(CASE WHEN status = 'DATA_INTEGRITY_CHECKED'
                      AND validate_status = 'passed'
                      AND harvest_status IN ('loaded', 'already_registered')
                      AND registry_status = 'confirmed'
                 THEN 1 ELSE 0 END) AS all_good_count,
            SUM(CASE WHEN status = 'DATA_INTEGRITY_CHECKED'
                      AND NOT (validate_status = 'passed'
                               AND harvest_status IN ('loaded', 'already_registered')
                               AND registry_status = 'confirmed')
                 THEN 1 ELSE 0 END) AS issues_count
        FROM product_tracking{where_sql}
    """
    return sql, parameters


def _compute_product_tracking_summary(rds_data, query_params):
    """Sums the per-database aggregate counts into one summary dict."""
    sql, parameters = _build_product_tracking_summary_query(query_params)
    totals = {col: 0 for col in PRODUCT_TRACKING_SUMMARY_COLUMNS}

    for database in PDS_TRACKING_DATABASE_NAMES:
        try:
            response = rds_data.execute_statement(
                resourceArn=DB_CLUSTER_ARN,
                secretArn=DB_SECRET_ARN,
                database=database,
                sql=sql,
                parameters=parameters,
            )
            records = response.get("records", [])
            if not records:
                continue
            row = _field_value_row(records[0], PRODUCT_TRACKING_SUMMARY_COLUMNS)
            for col in PRODUCT_TRACKING_SUMMARY_COLUMNS:
                # COUNT(*) comes back as a proper longValue, but MySQL's
                # SUM(CASE WHEN ... THEN 1 ELSE 0 END) returns a DECIMAL,
                # which the RDS Data API represents as a stringValue (e.g.
                # "45", possibly "45.0000") -- += against the int
                # accumulator below would raise TypeError for every SUM()
                # column if not coerced here. float() first since int()
                # rejects a decimal-point string directly.
                totals[col] += int(float(row.get(col) or 0))
        except Exception as error:
            logger.error(f"product_tracking summary query failed for {database}: {error}")

    # Anything that hasn't reached DATA_INTEGRITY_CHECKED yet, derived
    # rather than queried again -- status can only be NULL, RECEIVED,
    # SENT_TO_NUCLEUS or DATA_INTEGRITY_CHECKED, and the checked stage
    # already splits cleanly into all_good_count + issues_count above.
    totals["in_progress_count"] = totals["total"] - totals["all_good_count"] - totals["issues_count"]
    return totals


def _field_value(field):
    if field.get("isNull"):
        return None
    for key in ("stringValue", "longValue", "doubleValue", "booleanValue"):
        if key in field:
            return field[key]
    return None


def _record_to_dict(record):
    return {col: _field_value(field) for col, field in zip(PRODUCT_TRACKING_COLUMNS, record)}


def _field_value_row(record, columns):
    """Same idea as _record_to_dict, but against an arbitrary column list --
    used for the summary query, whose columns differ from PRODUCT_TRACKING_COLUMNS."""
    return {col: _field_value(field) for col, field in zip(columns, record)}


def search_products(headers, query_params, iam_role_arn, user):
    """
    Runs a filtered search against product_tracking, across every
    node/data-source database, and renders the merged results.

    Real WHERE-clause search/filter, not a log query language -- reuses the
    same Cognito-authenticated, role-mapped identity already proven above
    for MWAA login, just pointed at a SQL query instead of a redirect.
    """
    rds_data = get_rds_data_client(iam_role_arn, user)
    if rds_data is None:
        return close(headers, "Search failed. Please check your Cognito user groups with the help of PDS Engineering Node.",
                     status_code=401)

    sql, parameters = _build_product_tracking_query(query_params)

    products = []
    for database in PDS_TRACKING_DATABASE_NAMES:
        try:
            response = rds_data.execute_statement(
                resourceArn=DB_CLUSTER_ARN,
                secretArn=DB_SECRET_ARN,
                database=database,
                sql=sql,
                parameters=parameters,
            )
            products.extend(_record_to_dict(r) for r in response.get("records", []))
        except Exception as error:
            logger.error(f"product_tracking query failed for {database}: {error}")

    accept = (headers.get("accept") or headers.get("Accept") or [""])[0]
    if "application/json" in accept:
        return _products_json_response(headers, products)

    summary = _compute_product_tracking_summary(rds_data, query_params)
    return _products_html_response(headers, query_params, products, summary)


def _products_json_response(headers, products):
    headers['Content-Type'] = ['application/json']
    return {
        'statusCode': 200,
        'multiValueHeaders': headers,
        'body': json.dumps(products),
        'isBase64Encoded': False,
    }


def _pie_chart_html(segments):
    """
    Renders a pie chart as a plain CSS conic-gradient plus a text legend --
    no JS, no external charting library, consistent with this file's
    zero-new-dependency convention. `segments` is a list of
    (label, count, color) tuples.
    """
    total = sum(count for _, count, _ in segments)
    if total <= 0:
        return "<p>No data yet.</p>"

    stops = []
    cursor = 0.0
    for _, count, color in segments:
        pct = count / total * 100
        stops.append(f"{color} {cursor:.2f}% {(cursor + pct):.2f}%")
        cursor += pct
    gradient = ", ".join(stops)

    legend_rows = "".join(
        f'<div style="margin-bottom:4px;">'
        f'<span style="display:inline-block;width:12px;height:12px;background:{color};'
        f'margin-right:6px;border-radius:2px;"></span>'
        f'{html.escape(label)}: {count} ({(count / total * 100):.1f}%)'
        f'</div>'
        for label, count, color in segments
    )
    return (
        '<div style="display:flex;align-items:center;gap:24px;">'
        f'<div style="width:160px;height:160px;border-radius:50%;'
        f'background:conic-gradient({gradient});flex-shrink:0;"></div>'
        f'<div>{legend_rows}</div>'
        '</div>'
    )


def _summary_panel_html(summary):
    def stat(label, count):
        return f'<div style="margin-bottom:2px;"><b>{count}</b> {html.escape(label)}</div>'

    stats = "".join([
        stat("received total", summary["total"]),
        stat("received via backlog", summary["backlog_count"]),
        stat("received via realtime", summary["realtime_count"]),
        stat("validated (passed)", summary["validated_count"]),
        stat("harvested", summary["harvested_count"]),
        stat("registry integrity checked", summary["registry_checked_count"]),
        stat("all good end-to-end", summary["all_good_count"]),
    ])

    pie = _pie_chart_html([
        ("All good", summary["all_good_count"], "#2e7d32"),
        ("Issues found", summary["issues_count"], "#c62828"),
        ("In progress", summary["in_progress_count"], "#9e9e9e"),
    ])

    return (
        '<div style="display:flex;gap:40px;flex-wrap:wrap;margin:12px 0 20px;">'
        f'<div>{stats}</div>'
        f'<div>{pie}</div>'
        '</div>'
    )


def _pagination_links_html(query_params, page, has_more):
    """Next/previous links that preserve the current filters, just changing
    `page`. No total-page-count shown -- with pagination applied per
    database (see _build_product_tracking_query), an exact global total
    isn't something a single query can give cheaply, so this only offers
    "there are more" / "go back", not "page 4 of 9"."""
    def link_for(target_page, label):
        params = {k: _single_query_param(query_params, k) for k in PRODUCT_TRACKING_FILTERABLE_COLUMNS}
        params["page"] = str(target_page)
        # URL-encode the values for the query string itself (not
        # html.escape, which is for HTML text/attributes, not URLs) --
        # then html.escape the assembled query string once, since it's
        # about to be embedded in an href="..." attribute.
        qs = "&".join(f"{k}={urllib.parse.quote(v, safe='')}" for k, v in params.items() if v)
        return f'<a href="?{html.escape(qs)}">{label}</a>'

    parts = []
    if page > 1:
        parts.append(link_for(page - 1, "&laquo; Previous"))
    parts.append(f"Page {page}")
    if has_more:
        parts.append(link_for(page + 1, "Next &raquo;"))
    return '<div style="margin-top:12px;">' + " &nbsp;|&nbsp; ".join(parts) + '</div>'


def _products_html_response(headers, query_params, products, summary):
    def cell(value):
        return html.escape(str(value)) if value is not None else ""

    filter_fields = list(PRODUCT_TRACKING_FILTERABLE_COLUMNS.keys())
    form_inputs = "".join(
        f'<input type="text" name="{f}" placeholder="{f}" '
        f'value="{cell(_single_query_param(query_params, f))}"> '
        for f in filter_fields
    )
    header_row = "".join(f"<th>{cell(col)}</th>" for col in PRODUCT_TRACKING_COLUMNS)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{cell(p.get(col))}</td>" for col in PRODUCT_TRACKING_COLUMNS) + "</tr>"
        for p in products
    )

    page = _current_page(query_params)
    # A combined result at least as large as one database's page suggests
    # there may be more; not exact (see _pagination_links_html's docstring),
    # but good enough to show/hide "Next".
    has_more = len(products) >= PRODUCT_TRACKING_PAGE_SIZE

    body = (
        "<html><body>"
        "<h3>PDS Nucleus Product Tracking</h3>"
        f"{_summary_panel_html(summary)}"
        f'<form method="get">{form_inputs}<button type="submit">Search</button></form>'
        f"<p>{len(products)} result(s) on this page (up to {PRODUCT_TRACKING_PAGE_SIZE} per database per page)</p>"
        f'<table border="1" cellpadding="4"><tr>{header_row}</tr>{body_rows}</table>'
        f"{_pagination_links_html(query_params, page, has_more)}"
        "</body></html>"
    )
    headers['Content-Type'] = ['text/html']
    return {
        'statusCode': 200,
        'multiValueHeaders': headers,
        'body': body,
        'isBase64Encoded': False,
    }


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
        alg = headers.get('alg')

        if token_type == 'oidc-data':
            if alg not in ALLOWED_ALGORITHMS_OIDC_DATA:
                raise ValueError(f"Unexpected algorithm for oidc-data: {alg}. Expected one of {ALLOWED_ALGORITHMS_OIDC_DATA}")
            url = 'https://public-keys.auth.elb.' + AWS_REGION + '.amazonaws.com/' + kid
            req = requests.get(url)
            pub_key = req.text
            allowed_algorithms = ALLOWED_ALGORITHMS_OIDC_DATA

        elif token_type == 'oidc-accesstoken':
            if alg not in ALLOWED_ALGORITHMS_ACCESS_TOKEN:
                raise ValueError(f"Unexpected algorithm for oidc-accesstoken: {alg}. Expected one of {ALLOWED_ALGORITHMS_ACCESS_TOKEN}")
            pub_key = get_json_webkey_with_kid(kid)
            allowed_algorithms = ALLOWED_ALGORITHMS_ACCESS_TOKEN
        else:
            raise ValueError(f"Unknown token_type: {token_type}")

        # Verify the token and get the payload
        payload = jwt.decode(
            encoded_jwt,
            pub_key,
            algorithms=allowed_algorithms,
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
