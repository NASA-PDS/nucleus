"""
PDS Log Parsers

Helpers for extracting product identifiers and counts from the CloudWatch
logs emitted by the PDS validate and harvest ECS tasks.

These functions are pure (they take a list of log message strings) so they
can be unit tested without any AWS calls.
"""

import re
from typing import Dict, List


# validate emits lines like:
#   PASS: file:/mnt/data/.../M101266738LE_hst.xml (urn:nasa:pds:bundle:collection:product::2.0)
_VALIDATE_RESULT_RE = re.compile(
    r"(?<!\S)(?P<status>PASS|FAIL|SKIP):\s+file:(?P<path>\S+?)\s+\((?P<lidvid>urn:[^)\s]+)\)"
)

# validate summary block:
#       166        product(s) passed
# The literal "product(s)" keeps this from matching the running progress
# lines, which read "N product validation(s) completed".
_VALIDATE_SUMMARY_RE = re.compile(
    r"(?<!\S)(?P<count>\d+)\s+product\(s\)\s+(?P<status>passed|failed|skipped|total)\s*$"
)


def parse_validate_messages(messages: List[str]) -> Dict:
    """Extract per-product validate results and the summary counts.

    Args:
        messages: raw CloudWatch log message strings from the validate task.

    Returns:
        Dict with keys:
            passed / failed / skipped -> list of {"lidvid", "file"}
            summary -> {"passed", "failed", "skipped", "total"} ints, or {}
    """
    results = {"passed": [], "failed": [], "skipped": []}
    summary = {}

    bucket_for_status = {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}

    for msg in messages:
        match = _VALIDATE_RESULT_RE.search(msg)
        if match:
            bucket = bucket_for_status[match.group("status")]
            results[bucket].append(
                {"lidvid": match.group("lidvid"), "file": match.group("path")}
            )
            continue

        summary_match = _VALIDATE_SUMMARY_RE.search(msg)
        if summary_match:
            summary[summary_match.group("status")] = int(summary_match.group("count"))

    results["summary"] = summary
    return results


_HARVEST_SUMMARY_MARKER = "[SUMMARY]"

# Only count labels we recognise. harvest's log4j pattern prints
# "<method>:<line>" (e.g. "printSummary:298") before the [SUMMARY] marker,
# and a generic "word: number" rule captures those as bogus counts.
_HARVEST_SUMMARY_FIELD_RE = re.compile(
    r"(?P<label>total|processed|loaded|skipped|failed|succeeded|registered)"
    r"\s+(?P<noun>files|products|records)\s*:\s*(?P<count>\d+)",
    re.IGNORECASE,
)


def parse_harvest_messages(messages: List[str]) -> Dict:
    """Extract harvest counts from the [SUMMARY] line.

    Args:
        messages: raw CloudWatch log message strings from the harvest task.

    Returns:
        Dict of "<label>_<noun>" keys to integer counts, e.g.
        {"loaded_files": 166, "failed_files": 0}. Empty if no [SUMMARY]
        line was present.
    """
    summary = {}
    for msg in messages:
        marker = msg.find(_HARVEST_SUMMARY_MARKER)
        if marker == -1:
            continue

        # Parse only what follows the marker, so the logger's own
        # "method:line" prefix cannot be read as a count.
        body = msg[marker + len(_HARVEST_SUMMARY_MARKER) :]
        for match in _HARVEST_SUMMARY_FIELD_RE.finditer(body):
            key = f"{match.group('label').lower()}_{match.group('noun').lower()}"
            summary[key] = int(match.group("count"))
    return summary


def harvested_count(summary: Dict[str, int]):
    """Pick the count of products harvest actually registered.

    Prefers explicit "loaded" over "processed", because harvest counts a
    skipped file as processed. Returns None when harvest reported nothing,
    so callers can distinguish "zero" from "unknown".
    """
    for key in ("loaded_files", "registered_files", "succeeded_files", "processed_files"):
        if key in summary:
            return summary[key]
    return None


def build_manifest_key(path_or_url: str) -> str:
    """Normalise an S3 URL or EFS path down to its file name.

    The manifest holds S3 URLs while validate logs EFS paths, so comparing
    them directly never matches. Reducing both to the base file name gives a
    stable join key.
    """
    return path_or_url.rstrip("/").rsplit("/", 1)[-1]
