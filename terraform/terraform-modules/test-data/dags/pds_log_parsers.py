"""
PDS Log Parsers

Helper functions for parsing CloudWatch logs from PDS ECS tasks.
"""

import re
from typing import List


def extract_manifest_products(efs_config_dir: str) -> List[str]:
    """Read manifest file and extract S3 URLs.
    
    Args:
        efs_config_dir: Path to EFS config directory containing harvest_manifest.txt
        
    Returns:
        List of S3 URLs from the manifest file
    """
    manifest_path = f"{efs_config_dir}/harvest_manifest.txt"
    try:
        with open(manifest_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading manifest: {e}")
        return []


def parse_validate_logs(logs_client, log_group: str, log_stream: str) -> List[str]:
    """Extract validated product LIDVIDs from validate logs.
    
    Args:
        logs_client: AWS CloudWatch Logs client
        log_group: CloudWatch log group name
        log_stream: CloudWatch log stream name
        
    Returns:
        List of validated product LIDVIDs
    """
    validated_products = []
    try:
        logs_resp = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            startFromHead=True,
        )
        events = logs_resp.get("events", [])
        for event in events:
            msg = event["message"]
            if "Product_Observational" in msg or "Product_Bundle" in msg:
                match = re.search(r'urn:nasa:pds:[\w\-\.]+:[\w\-\.]+:[\w\-\.]+:[\w\-\.]+', msg)
                if match:
                    validated_products.append(match.group(0))
    except Exception as e:
        print(f"Error parsing validate logs: {e}")
    return validated_products


def parse_harvest_logs(logs_client, log_group: str, log_stream: str) -> List[str]:
    """Extract harvested product S3 URLs from harvest logs.
    
    Args:
        logs_client: AWS CloudWatch Logs client
        log_group: CloudWatch log group name
        log_stream: CloudWatch log stream name
        
    Returns:
        List of harvested product S3 URLs
    """
    harvested_products = []
    try:
        logs_resp = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            startFromHead=True,
        )
        events = logs_resp.get("events", [])
        for event in events:
            msg = event["message"]
            if "Processing" in msg and ".xml" in msg:
                match = re.search(r's3://[\w\-\.]+/[\w\-\./]+\.xml', msg)
                if match:
                    harvested_products.append(match.group(0))
    except Exception as e:
        print(f"Error parsing harvest logs: {e}")
    return harvested_products
