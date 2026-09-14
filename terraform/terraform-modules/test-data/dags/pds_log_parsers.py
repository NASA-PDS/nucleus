"""
PDS Log Parsers and Report Formatting

Helpers for extracting product identifiers and counts from the CloudWatch
logs emitted by the PDS validate and harvest ECS tasks, and for rendering
the reconciled result as a human-readable report.

These functions are pure (they take plain data structures) so they can be
unit tested without any AWS calls.
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


def batch_number_from_config_dir(config_dir: str) -> str:
    """Recover the batch name from the config directory a run was given.

    The trigger builds this directory as .../dag-data/<node>/<batch>, so its
    last segment is the batch name. Only a fallback: a run triggered with an
    explicit batch_number should use that. It exists because a DAG triggered
    by hand from the Airflow UI has no batch_number in its conf, and a run
    with no batch name at all cannot be tied to the batch it processed.
    """
    if not config_dir:
        return ""
    return config_dir.rstrip("/").rsplit("/", 1)[-1]


def format_human_report(summary: Dict, products: List[Dict]) -> str:
    """Render the batch summary as plain text for the Airflow UI XCom tab.

    This goes to XCom rather than the task log on purpose: MWAA stores task
    logs in CloudWatch, so printing this would duplicate into CloudWatch
    everything the JSON event already carries. XCom lives in the Airflow
    metadata database and is shown in the UI only.
    """
    counts = summary["counts"]
    integrity = summary["data_integrity"]

    def row(label, value):
        return f"  {label:<22}{value}"

    lines = [
        "PDS BATCH SUMMARY",
        "=" * 60,
        # The batch name the pipeline works in terms of, and the Airflow run
        # that processed it. Two different identifiers: one names the work,
        # the other names the attempt, and a batch can be re-run.
        row("Batch number", summary.get("batch_number") or "(unknown)"),
        row("Airflow run", summary["dag_run_id"]),
        row("Status", summary["status"]),
        row("Started", summary["timing"]["start_time"] or "unknown"),
        row("Ended", summary["timing"]["end_time"]),
        # Printed once. Every product path below is relative to this, so a
        # reader can reconstruct the full S3 URL without it being repeated
        # on all N lines.
        row("S3 location", summary.get("s3_prefix") or "(mixed)"),
        # Which harvest flags this run used. Whether a re-run updated the
        # registry or skipped every product turns on this line.
        row("Harvest args", summary.get("harvest_extra_args") or "(none)"),
        "",
        "COUNTS",
        "-" * 60,
        row("Received", counts["received"]),
        row("Validated", counts["validated"]),
        row("Validation failed", counts["validation_failed"]),
        row("Validation skipped", counts["validation_skipped"]),
        row(
            "Harvested",
            counts["harvested"] if counts["harvested"] is not None else "not reported",
        ),
        row("Harvest skipped", counts["harvest_skipped"]),
        row("Registry checked", counts.get("registry_checked", 0)),
        row("Registry confirmed", counts.get("registry_confirmed", 0)),
        row("Registry mismatch", counts.get("registry_harvest_mismatch", 0)),
        "",
        "DATA INTEGRITY",
        "-" * 60,
        row("Result", integrity["status"]),
        row("Not validated", len(integrity["not_validated"])),
        row("Unexpected products", len(integrity["unexpected_products"])),
    ]

    # The reasons behind the status, exactly as the summary task classified
    # them. Deriving them a second time here would let the report and the
    # DAG's pass/fail decision drift apart.
    for failure in integrity.get("failures", []):
        lines.append(f"  FAILED   {failure}")
    for warning in integrity.get("warnings", []):
        lines.append(f"  WARNING  {warning}")

    # Three columns, each headed, because "passed" alone does not say what
    # passed. Validation checking a product out, harvest loading it, and the
    # live registry actually holding it are three different facts.
    header = f"  {'VALIDATE':<14}{'HARVEST':<20}{'REGISTRY':<14}PRODUCT"

    # Products carry their full S3 URL so an entry means something on its
    # own. The report already prints the shared prefix as a heading, so it
    # shows only the part below it rather than repeating the prefix on
    # every line.
    prefix = summary.get("s3_prefix") or ""

    def product_line(product):
        location = product.get("s3_url") or product["name"]
        location = relative_path(location, prefix)
        validate_status = product.get("validate_status", product.get("status", ""))
        harvest_status = product.get("harvest_status", "")
        registry_status = product.get("registry_status", "")
        return (
            f"  {validate_status:<14}{harvest_status:<20}{registry_status:<14}{location}  "
            f"{product['lidvid'] or ''}"
        ).rstrip()

    def needs_attention(product):
        if product.get("validate_status", product.get("status")) != "passed":
            return True
        # The actionable case this feature exists to surface: harvest
        # claims the product is loaded/registered, but the live registry
        # doesn't confirm it -- worth a look even though validation passed.
        harvest_status = product.get("harvest_status")
        registry_status = product.get("registry_status")
        if harvest_status in ("loaded", "already_registered") and registry_status not in (
            "confirmed",
            "not_checked",
            None,
        ):
            return True
        return False

    issues = [product for product in products if needs_attention(product)]
    lines += ["", f"PRODUCTS NEEDING ATTENTION ({len(issues)})", "-" * 60]
    if issues:
        lines += [header] + [product_line(product) for product in issues]
    else:
        lines.append("  none")

    lines += ["", f"ALL PRODUCTS ({len(products)})", "-" * 60]
    if products:
        lines += [header] + [product_line(product) for product in products]
    return "\n".join(lines)


def common_directory(paths: List[str]) -> str:
    """Return the directory prefix shared by every path.

    Lets a report store one prefix plus bare file names instead of repeating
    the full location for every product. Returns "" when the paths share no
    directory, in which case callers should keep the full paths.
    """
    directories = [path.rsplit("/", 1)[0] for path in paths if "/" in path]
    if not directories or len(directories) != len(paths):
        return ""

    first = directories[0]
    if all(directory == first for directory in directories):
        return first

    # Compare segment by segment so the prefix always ends on a path
    # boundary, never in the middle of a directory name.
    segments = first.split("/")
    for directory in directories[1:]:
        other = directory.split("/")
        keep = 0
        while keep < len(segments) and keep < len(other) and segments[keep] == other[keep]:
            keep += 1
        segments = segments[:keep]
        if not segments:
            return ""
    return "/".join(segments)


def relative_path(path_or_url: str, prefix: str) -> str:
    """Return the part of a path below a shared prefix.

    Storing the prefix once plus this remainder keeps a report lossless:
    the original location is prefix + "/" + remainder. A bare file name
    would not be, because products in different subdirectories all reduce
    to the same name.
    """
    if prefix and path_or_url.startswith(prefix + "/"):
        return path_or_url[len(prefix) + 1 :]
    return path_or_url


def build_manifest_key(path_or_url: str) -> str:
    """Normalise an S3 URL or EFS path down to its file name.

    The manifest holds S3 URLs while validate logs EFS paths, so comparing
    them directly never matches. Reducing both to the base file name gives a
    stable join key.
    """
    return path_or_url.rstrip("/").rsplit("/", 1)[-1]
