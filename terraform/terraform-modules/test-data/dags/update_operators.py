#!/usr/bin/env python3
"""Update pds_airflow_custom_operators.py to parse logs and save to EFS."""

import os

content = '''"""
PDS Airflow Custom Operators

Reusable ECS operators for PDS Node workflows with enhanced logging and error handling.
"""

import os
import json
import re
from pathlib import Path

from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.providers.amazon.aws.hooks.logs import AwsLogsHook
from airflow.exceptions import AirflowFailException
from typing import Any
from datetime import datetime


class EcsRunTaskOperatorWithMaxLogs(EcsRunTaskOperator):
    """Base class: fetch max available CloudWatch logs after task execution."""
    
    def execute(self, context: Any) -> str | None:
        """Execute task synchronously and fetch CloudWatch logs."""
        try:
            result = super().execute(context)
        except Exception:
            self._fetch_and_log_cloudwatch_logs()
            raise
        
        self._fetch_and_log_cloudwatch_logs()
        return result

    def _fetch_and_log_cloudwatch_logs(self):
        """Fetch and log all available CloudWatch logs."""
        if not self.awslogs_group or not self.awslogs_stream_prefix:
            return
        try:
            logs_client = AwsLogsHook(
                aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region
            ).conn
            if self.arn:
                task_id = self.arn.rsplit("/", 1)[-1]
                log_stream = f"{self.awslogs_stream_prefix}/{self.arn.split('/')[-3]}/{task_id}"
                try:
                    logs_resp = logs_client.get_log_events(
                        logGroupName=self.awslogs_group,
                        logStreamName=log_stream,
                        startFromHead=True,
                    )
                    events = logs_resp.get("events", [])
                    if events:
                        self.log.info(f"--- CloudWatch logs ({len(events)} lines) ---")
                        for event in events:
                            self.log.info(event["message"])
                except logs_client.exceptions.ResourceNotFoundException:
                    self.log.warning(f"Log stream not found: {log_stream}")
        except Exception as e:
            self.log.warning(f"Could not fetch CloudWatch logs: {e}")


class ValidateEcsRunTaskOperator(EcsRunTaskOperatorWithMaxLogs):
    """ECS operator for Validate task with exit code-aware error handling.
    
    The validate tool exits 1 when it ran successfully but found real
    data problems (e.g. missing referenced file) — a deterministic result
    that retrying will not change. Any other non-zero exit (task crashed,
    never started, OOM, etc.) is a genuine infra failure worth retrying.
    We distinguish the two so only infra failures consume the task's retries.
    
    Also parses logs and saves validated product count to EFS.
    """
    
    def execute(self, context):
        try:
            result = super().execute(context)
            self._write_validation_results_to_efs(context)
            return result
        except Exception as e:
            exit_code = None
            if self.arn:
                try:
                    resp = self.hook.get_conn().describe_tasks(
                        cluster=self.cluster, tasks=[self.arn]
                    )
                    exit_code = next(
                        (
                            c.get("exitCode")
                            for c in resp["tasks"][0].get("containers", [])
                            if c.get("name") == "pds-validate"
                        ),
                        None,
                    )
                except Exception:
                    pass

            if exit_code == 1:
                raise AirflowFailException(
                    f"{e} (validate exited 1 — data validation failure, not retrying)"
                ) from e
            raise
    
    def _write_validation_results_to_efs(self, context):
        """Parse logs and write validation results to EFS."""
        try:
            dag_run = context["dag_run"]
            efs_config_dir = dag_run.conf.get("efs_config_dir", "")
            if not efs_config_dir:
                self.log.warning("No efs_config_dir in dag_run.conf")
                return
            
            validated_count = self._parse_validation_logs()
            
            results_file = os.path.join(efs_config_dir, "validation_results.txt")
            Path(efs_config_dir).mkdir(parents=True, exist_ok=True)
            with open(results_file, 'w') as f:
                f.write(f"validated_count={validated_count}\\n")
                f.write(f"completed_at={datetime.utcnow().isoformat()}\\n")
            
            self.log.info(f"Validation results saved: {validated_count} products")
        except Exception as e:
            self.log.warning(f"Could not write validation results: {e}")
    
    def _parse_validation_logs(self) -> int:
        """Parse CloudWatch logs to count validated products."""
        validated_count = 0
        try:
            if not self.awslogs_group or not self.awslogs_stream_prefix:
                return 0
            
            logs_client = AwsLogsHook(
                aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region
            ).conn
            
            if self.arn:
                task_id = self.arn.rsplit("/", 1)[-1]
                log_stream = f"{self.awslogs_stream_prefix}/{self.arn.split('/')[-3]}/{task_id}"
                try:
                    logs_resp = logs_client.get_log_events(
                        logGroupName=self.awslogs_group,
                        logStreamName=log_stream,
                        startFromHead=True,
                    )
                    events = logs_resp.get("events", [])
                    for event in events:
                        msg = event["message"]
                        if "Product_Observational" in msg or "Product_Bundle" in msg:
                            validated_count += 1
                except logs_client.exceptions.ResourceNotFoundException:
                    self.log.warning(f"Log stream not found: {log_stream}")
        except Exception as e:
            self.log.warning(f"Could not parse validation logs: {e}")
        
        return validated_count


class HarvestEcsRunTaskOperator(EcsRunTaskOperatorWithMaxLogs):
    """ECS operator for Harvest task that checks for failed files in summary.
    
    The harvest tool always exits 0 even when files fail to parse. This operator
    parses CloudWatch logs to detect the [SUMMARY] line with failed file count
    and fails the task if any files failed.
    
    Also parses logs and saves harvested product count to EFS.
    """
    
    def execute(self, context: Any) -> str | None:
        """Execute task synchronously, fetch logs, and check for failed files."""
        result = super().execute(context)
        
        self._check_harvest_summary()
        self._write_harvest_results_to_efs(context)
        
        return result

    def _check_harvest_summary(self):
        """Parse CloudWatch logs and fail if any files failed to harvest."""
        if not self.awslogs_group or not self.awslogs_stream_prefix:
            return
        try:
            logs_client = AwsLogsHook(
                aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region
            ).conn
            if self.arn:
                task_id = self.arn.rsplit("/", 1)[-1]
                log_stream = f"{self.awslogs_stream_prefix}/{self.arn.split('/')[-3]}/{task_id}"
                try:
                    logs_resp = logs_client.get_log_events(
                        logGroupName=self.awslogs_group,
                        logStreamName=log_stream,
                        startFromHead=True,
                    )
                    events = logs_resp.get("events", [])
                    for event in events:
                        msg = event["message"]
                        if "[SUMMARY]" in msg and "Failed files:" in msg:
                            parts = msg.split("Failed files:")
                            if len(parts) > 1:
                                try:
                                    failed_count = int(parts[1].strip().split()[0])
                                    if failed_count > 0:
                                        raise AirflowFailException(
                                            f"Harvest completed with {failed_count} failed files (missing from EFS)"
                                        )
                                except (ValueError, IndexError):
                                    pass
                except logs_client.exceptions.ResourceNotFoundException:
                    self.log.warning(f"Log stream not found: {log_stream}")
        except AirflowFailException:
            raise
        except Exception as e:
            self.log.warning(f"Could not check harvest summary: {e}")
    
    def _write_harvest_results_to_efs(self, context):
        """Parse logs and write harvest results to EFS."""
        try:
            dag_run = context["dag_run"]
            efs_config_dir = dag_run.conf.get("efs_config_dir", "")
            if not efs_config_dir:
                self.log.warning("No efs_config_dir in dag_run.conf")
                return
            
            harvested_count = self._parse_harvest_logs()
            
            results_file = os.path.join(efs_config_dir, "harvest_results.txt")
            Path(efs_config_dir).mkdir(parents=True, exist_ok=True)
            with open(results_file, 'w') as f:
                f.write(f"harvested_count={harvested_count}\\n")
                f.write(f"completed_at={datetime.utcnow().isoformat()}\\n")
            
            self.log.info(f"Harvest results saved: {harvested_count} products")
        except Exception as e:
            self.log.warning(f"Could not write harvest results: {e}")
    
    def _parse_harvest_logs(self) -> int:
        """Parse CloudWatch logs to count harvested products."""
        harvested_count = 0
        try:
            if not self.awslogs_group or not self.awslogs_stream_prefix:
                return 0
            
            logs_client = AwsLogsHook(
                aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region
            ).conn
            
            if self.arn:
                task_id = self.arn.rsplit("/", 1)[-1]
                log_stream = f"{self.awslogs_stream_prefix}/{self.arn.split('/')[-3]}/{task_id}"
                try:
                    logs_resp = logs_client.get_log_events(
                        logGroupName=self.awslogs_group,
                        logStreamName=log_stream,
                        startFromHead=True,
                    )
                    events = logs_resp.get("events", [])
                    for event in events:
                        msg = event["message"]
                        if "Processing" in msg and ".xml" in msg:
                            harvested_count += 1
                except logs_client.exceptions.ResourceNotFoundException:
                    self.log.warning(f"Log stream not found: {log_stream}")
        except Exception as e:
            self.log.warning(f"Could not parse harvest logs: {e}")
        
        return harvested_count
'''

target_file = "terraform/terraform-modules/test-data/dags/pds_airflow_custom_operators.py"
with open(target_file, 'w') as f:
    f.write(content)

print(f"Updated {target_file}")
