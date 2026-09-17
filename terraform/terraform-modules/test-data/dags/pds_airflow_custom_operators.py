"""
PDS Airflow Custom Operators

Reusable synchronous ECS operators for PDS Node workflows.

These operators run with deferrable=False so the container logs are streamed
into the Airflow task log by the built-in ECS log fetcher. After the task
finishes they re-read the same CloudWatch stream to extract structured
results, which are published as XComs for a downstream summary task.

Results are passed via XCom rather than shared EFS because these operators
execute inside the MWAA worker, which does not mount the EFS volume used by
the ECS containers.
"""

import time
from typing import Any, Dict, List

from airflow.exceptions import AirflowFailException
from airflow.providers.amazon.aws.hooks.logs import AwsLogsHook
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

from pds_log_parsers import parse_harvest_messages, parse_validate_messages


class CloudWatchReadingEcsOperator(EcsRunTaskOperator):
    """Base class adding a helper to re-read this task's CloudWatch log stream."""

    def _read_log_messages(self, max_attempts=3, retry_delay=2) -> List[str]:
        """Return every log message this ECS task wrote, oldest first.

        Retries before giving up, both on a CloudWatch API error (e.g.
        GetLogEvents throttling) and on an empty first page -- CloudWatch can
        return zero events on the very first read right after a task stops,
        before its logs are fully queryable, which looks identical to a
        genuinely empty stream. Raises after exhausting retries rather than
        returning an empty list: silently treating "couldn't confirm the
        result" as "nothing to report" let a transient read failure report a
        false success for Harvest_Data, which -- since it runs with
        retries=0 by design -- skipped the whole-DAG restart that exists for
        exactly this kind of failure.
        """
        if not (self.awslogs_group and self.awslogs_stream_prefix and self.arn):
            return []

        # ECS awslogs streams are named "<prefix>/<task-id>", where task-id is
        # the final segment of the task ARN. Building it any other way (e.g.
        # from earlier ARN segments) yields a name containing ':' which
        # CloudWatch rejects with InvalidParameterException.
        task_id = self.arn.rsplit("/", 1)[-1]
        log_stream = f"{self.awslogs_stream_prefix}/{task_id}"
        logs_client = AwsLogsHook(aws_conn_id=self.aws_conn_id, region_name=self.awslogs_region).conn

        last_error = None
        for attempt in range(max_attempts):
            try:
                messages: List[str] = []
                next_token = None
                first_page = True
                while True:
                    kwargs = {
                        "logGroupName": self.awslogs_group,
                        "logStreamName": log_stream,
                        "startFromHead": True,
                    }
                    if next_token:
                        kwargs["nextToken"] = next_token

                    response = logs_client.get_log_events(**kwargs)
                    events = response.get("events", [])
                    if first_page and not events and attempt < max_attempts - 1:
                        raise RuntimeError("empty first page")
                    first_page = False
                    messages.extend(event["message"] for event in events)

                    token = response.get("nextForwardToken")
                    if not events or token == next_token:
                        break
                    next_token = token

                self.log.info("Read %d log lines from %s", len(messages), log_stream)
                return messages
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    self.log.warning(
                        "Could not read CloudWatch stream %s (attempt %d/%d): %s; retrying in %ds",
                        log_stream, attempt + 1, max_attempts, exc, retry_delay,
                    )
                    time.sleep(retry_delay)

        raise RuntimeError(f"Could not read CloudWatch stream {log_stream} after {max_attempts} attempts") from last_error


class ValidateEcsRunTaskOperator(CloudWatchReadingEcsOperator):
    """ECS operator for the validate task with exit-code-aware error handling.

    The validate tool exits 1 when it ran successfully but found real data
    problems (e.g. a missing referenced file) - a deterministic result that
    retrying will not change. Any other non-zero exit (task crashed, never
    started, OOM, etc.) is a genuine infra failure worth retrying. We
    distinguish the two so only infra failures consume the task's retries.

    On success it publishes these XComs:
        validate_passed   list of {"lidvid", "file"}
        validate_failed   list of {"lidvid", "file"}
        validate_skipped  list of {"lidvid", "file"}
        validate_summary  dict of counts reported by validate itself
    """

    CONTAINER_NAME = "pds-validate"

    def execute(self, context: Any) -> str | None:
        try:
            result = super().execute(context)
        except Exception as exc:
            if self._exit_code() == 1:
                raise AirflowFailException(
                    f"{exc} (validate exited 1 - data validation failure, not retrying)"
                ) from exc
            raise

        self._publish_results(context)
        return result

    def _exit_code(self):
        """Best-effort lookup of the validate container's exit code."""
        if not self.arn:
            return None
        try:
            response = self.hook.get_conn().describe_tasks(
                cluster=self.cluster, tasks=[self.arn]
            )
            return next(
                (
                    container.get("exitCode")
                    for container in response["tasks"][0].get("containers", [])
                    if container.get("name") == self.CONTAINER_NAME
                ),
                None,
            )
        except Exception:
            # If we cannot determine the exit code, fall back to retrying.
            return None

    def _publish_results(self, context: Any) -> None:
        parsed = parse_validate_messages(self._read_log_messages())

        task_instance = context["ti"]
        task_instance.xcom_push(key="validate_passed", value=parsed["passed"])
        task_instance.xcom_push(key="validate_failed", value=parsed["failed"])
        task_instance.xcom_push(key="validate_skipped", value=parsed["skipped"])
        task_instance.xcom_push(key="validate_summary", value=parsed["summary"])

        self.log.info(
            "Validate results: %d passed, %d failed, %d skipped",
            len(parsed["passed"]),
            len(parsed["failed"]),
            len(parsed["skipped"]),
        )


class HarvestEcsRunTaskOperator(CloudWatchReadingEcsOperator):
    """ECS operator for the harvest task that checks for failed files.

    The harvest tool always exits 0 even when files fail to parse, so we read
    the [SUMMARY] line and fail the task when it reports failed files.

    Publishes the parsed summary as the "harvest_summary" XCom.
    """

    def execute(self, context: Any) -> str | None:
        result = super().execute(context)

        summary = parse_harvest_messages(self._read_log_messages())
        context["ti"].xcom_push(key="harvest_summary", value=summary)
        self.log.info("Harvest summary: %s", summary or "not reported")

        failed_count = self._failed_count(summary)
        if failed_count:
            raise AirflowFailException(
                f"Harvest completed with {failed_count} failed files "
                "(files missing from EFS indicate an upstream copy failure)"
            )

        return result

    @staticmethod
    def _failed_count(summary: Dict[str, int]) -> int:
        """Read the failed-file count from a parsed harvest summary."""
        for key, value in summary.items():
            if "fail" in key:
                return value
        return 0
