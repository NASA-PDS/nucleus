"""Unit tests for pds_log_parsers, using real PDS validate/harvest log lines."""

import unittest

from pds_log_parsers import (
    build_manifest_key,
    parse_harvest_messages,
    parse_validate_messages,
)


VALIDATE_LOG = [
    "[2026-09-13 04:20:26,089] PDS Validate Tool Report",
    "[2026-09-13 04:20:31,259] Product Level Validation Results",
    "[2026-09-13 04:20:31,259]   PASS: file:/mnt/data/pds-img-archive-prod/lunar_reconnaissance_orbiter/"
    "pds4/lroc/lro-l-lroc-2-edr/LROLRC_0001/EXTRAS/HISTOGRAM/2009184/M101266738LE_hst.xml "
    "(urn:nasa:pds:lro-l-lroc-2-edr:lrolrc_0001_extras:histogram.m101266738le::2.0)",
    "[2026-09-13 04:20:31,259]         1 product validation(s) completed",
    "[2026-09-13 04:20:31,466]   PASS: file:/mnt/data/pds-img-archive-prod/lunar_reconnaissance_orbiter/"
    "pds4/lroc/lro-l-lroc-2-edr/LROLRC_0001/EXTRAS/HISTOGRAM/2009184/M101266738RE_hst.xml "
    "(urn:nasa:pds:lro-l-lroc-2-edr:lrolrc_0001_extras:histogram.m101266738re::2.0)",
    "[2026-09-13 04:20:44,784]   Product Validation Summary:",
    "[2026-09-13 04:20:44,784]     166        product(s) passed",
    "[2026-09-13 04:20:44,784]     0          product(s) failed",
    "[2026-09-13 04:20:44,784]     0          product(s) skipped",
    "[2026-09-13 04:20:44,784]     166        product(s) total",
]


class ParseValidateMessagesTest(unittest.TestCase):
    def test_extracts_lidvid_and_file_for_passing_products(self):
        result = parse_validate_messages(VALIDATE_LOG)

        self.assertEqual(len(result["passed"]), 2)
        self.assertEqual(
            result["passed"][0]["lidvid"],
            "urn:nasa:pds:lro-l-lroc-2-edr:lrolrc_0001_extras:histogram.m101266738le::2.0",
        )
        self.assertTrue(result["passed"][0]["file"].endswith("M101266738LE_hst.xml"))

    def test_does_not_treat_progress_lines_as_products(self):
        # "1 product validation(s) completed" must not be parsed as a summary
        # count, otherwise the totals are silently wrong.
        result = parse_validate_messages(VALIDATE_LOG)
        self.assertEqual(result["summary"]["passed"], 166)
        self.assertEqual(result["summary"]["total"], 166)

    def test_reports_zero_failures_when_none_present(self):
        result = parse_validate_messages(VALIDATE_LOG)
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["summary"]["failed"], 0)

    def test_captures_failed_and_skipped_products(self):
        messages = [
            "  FAIL: file:/mnt/data/a/bad.xml (urn:nasa:pds:b:c:bad::1.0)",
            "  SKIP: file:/mnt/data/a/other.xml (urn:nasa:pds:b:c:other::1.0)",
        ]
        result = parse_validate_messages(messages)

        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["failed"][0]["lidvid"], "urn:nasa:pds:b:c:bad::1.0")

    def test_empty_log_yields_empty_results(self):
        result = parse_validate_messages([])
        self.assertEqual(result["passed"], [])
        self.assertEqual(result["summary"], {})


class ParseHarvestMessagesTest(unittest.TestCase):
    def test_extracts_counts_from_summary_line(self):
        messages = ["[SUMMARY] Processed files: 166, Failed files: 0"]
        summary = parse_harvest_messages(messages)

        self.assertEqual(summary["processed_files"], 166)
        self.assertEqual(summary["failed_files"], 0)

    def test_detects_non_zero_failures(self):
        messages = ["[SUMMARY] Processed files: 160, Failed files: 6"]
        self.assertEqual(parse_harvest_messages(messages)["failed_files"], 6)

    def test_missing_summary_line_yields_empty_dict(self):
        self.assertEqual(parse_harvest_messages(["nothing here"]), {})


class BuildManifestKeyTest(unittest.TestCase):
    def test_s3_url_and_efs_path_for_same_product_match(self):
        s3_url = (
            "s3://pds-img-archive-prod/lunar_reconnaissance_orbiter/pds4/lroc/"
            "lro-l-lroc-2-edr/LROLRC_0001/EXTRAS/HISTOGRAM/2009184/M101266738LE_hst.xml"
        )
        efs_path = (
            "/mnt/data/pds-img-archive-prod/lunar_reconnaissance_orbiter/pds4/lroc/"
            "lro-l-lroc-2-edr/LROLRC_0001/EXTRAS/HISTOGRAM/2009184/M101266738LE_hst.xml"
        )
        self.assertEqual(build_manifest_key(s3_url), build_manifest_key(efs_path))
        self.assertEqual(build_manifest_key(s3_url), "M101266738LE_hst.xml")


if __name__ == "__main__":
    unittest.main()
