"""
PDS Airflow Custom Operators

Reusable ECS operators for PDS Node workflows with enhanced logging and error handling.
"""

import os
import json
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
            # Task failed; try to fetch and log CloudWatch logs before re-raising
            self._fetch_and_log_cloudwatch_logs()
            raise
        
        # Task succeeded; also fetch logs for visibility
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
            # Build log stream name from task ARN
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
    
    The `validate` tool exits 1 when it ran successfully but found real
    data problems (e.g. missing referenced file) — a deterministic result
    that retrying will not change. Any other non-zero exit (task crashed,
    never started, OOM, etc.) is a genuine infra failure worth retrying.
    We distinguish the two so only infra failures consume the task's retries.
    """
    
    def execute(self, context):
        try:
            # This will run the parent execute(), which also fetches the logs
            result = super().execute(context)
            self._write_validation_marker_to_efs(context)
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
                    pass  # if we can't determine exit code, fall back to retrying

            if exit_code == 1:
                raise AirflowFailException(
                    f"{e} (validate exited 1 — data validation failure, not retrying)"
                ) from e
            raise
    
    def _write_validation_marker_to_efs(self, context):
        """Write validation completion marker to EFS."""
        try:
            dag_run = context["dag_run"]
            efs_config_dir = dag_run.conf.get("efs_config_dir", "")
            if not efs_config_dir:
                self.log.warning("No efs_config_dir in dag_run.conf, skipping validation marker")
                return
            
            marker_file = os.path.join(efs_config_dir, "validation_completed.txt")
            Path(efs_config_dir).mkdir(parents=True, exist_ok=True)
            with open(marker_file, 'w') as f:
                f.write(f"Validation completed at {datetime.utcnow().isoformat()}\n")
            
            self.log.info(f"Wrote validation marker to {marker_file}")
        except Exception as e:
            self.log.warning(f"Could not write validation marker to EFS: {e}")


class HarvestEcsRunTaskOperator(EcsRunTaskOperatorWithMaxLogs):
    """ECS operator for Harvest task that checks for failed files in summary.
    
    The harvest tool always exits 0 even when files fail to parse. This operator
    parses CloudWatch logs to detect the [SUMMARY] line with failed file count
    and fails the task if any files failed.
    """
    
    def execute(self, context: Any) -> str | None:
        """Execute task synchronously, fetch logs, and check for failed files."""
        # This will run the parent execute(), which also fetches the logs
        result = super().execute(context)
        
        # Task succeeded (exit 0), but check if harvest had failed files
        self._check_harvest_summary()
        
        # Write harvest completion marker to EFS for summary task
        self._write_harvest_marker_to_efs(context)
        
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
                            # Extract failed file count
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
    
    def _write_harvest_marker_to_efs(self, context):
        """Write harvest completion marker to EFS."""
        try:
            dag_run = context["dag_run"]
            efs_config_dir = dag_run.conf.get("efs_config_dir", "")
            if not efs_config_dir:
                self.log.warning("No efs_config_dir in dag_run.conf, skipping harvest marker")
                return
            
            marker_file = os.path.join(efs_config_dir, "harvest_completed.txt")
            Path(efs_config_dir).mkdir(parents=True, exist_ok=True)
            with open(marker_file, 'w') as f:
                f.write(f"Harvest completed at {datetime.utcnow().isoformat()}\n")
            
            self.log.info(f"Wrote harvest marker to {marker_file}")
        except Exception as e:
            self.log.warning(f"Could not write harvest marker to EFS: {e}")
