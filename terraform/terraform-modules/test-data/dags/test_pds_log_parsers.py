"""Unit tests for pds_log_parsers, using real PDS validate/harvest log lines."""

import unittest

from pds_log_parsers import (
    batch_number_from_config_dir,
    build_manifest_key,
    common_directory,
    format_human_report,
    harvested_count,
    parse_harvest_messages,
    parse_validate_messages,
    relative_path,
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

    def test_ignores_log4j_method_and_line_number_metadata(self):
        # harvest logs "<method>:<line>" before the marker. A generic
        # "word: number" rule turns those into bogus counts such as
        # {"printsummary": 298}.
        messages = [
            "05:00:01 [main] INFO  g.n.p.h.HarvestSummary printSummary:298 "
            "[SUMMARY] Loaded files: 0, Skipped files: 166, Failed files: 0",
            "05:00:01 [main] INFO  g.n.p.h.ConfigReader readConfigFile:191 "
            "[SUMMARY] Total files: 166",
        ]
        summary = parse_harvest_messages(messages)

        self.assertEqual(
            summary,
            {
                "loaded_files": 0,
                "skipped_files": 166,
                "failed_files": 0,
                "total_files": 166,
            },
        )

    def test_missing_summary_line_yields_empty_dict(self):
        self.assertEqual(parse_harvest_messages(["nothing here"]), {})


class HarvestedCountTest(unittest.TestCase):
    def test_prefers_loaded_over_processed(self):
        # harvest counts a skipped file as processed, so "processed" would
        # overstate how many products were actually registered.
        summary = {"processed_files": 166, "loaded_files": 0, "skipped_files": 166}
        self.assertEqual(harvested_count(summary), 0)

    def test_falls_back_to_processed(self):
        self.assertEqual(harvested_count({"processed_files": 166}), 166)

    def test_unknown_when_nothing_reported(self):
        self.assertIsNone(harvested_count({}))


BATCH = "2026-09-10-03-36-5624f194624d624c54931fdb1fe693019c"


def _product(name, **overrides):
    product = {
        "batch_number": BATCH,
        "dag_run_id": f"batch__{BATCH}",
        "name": name,
        "s3_url": f"s3://bucket/lroc/2009184/{name}",
        "lidvid": None,
        "validate_status": "passed",
        "harvest_status": "loaded",
    }
    product.update(overrides)
    return product


def _summary(**overrides):
    summary = {
        "batch_number": BATCH,
        "dag_run_id": f"batch__{BATCH}",
        "status": "SUCCESS",
        "timing": {"start_time": "2026-09-13T04:46:53", "end_time": "2026-09-13T04:58:16"},
        "counts": {
            "received": 2,
            "validated": 2,
            "validation_failed": 0,
            "validation_skipped": 0,
            "harvested": 2,
            "harvest_skipped": 0,
        },
        "data_integrity": {
            "status": "COMPLETE",
            "not_validated": [],
            "unexpected_products": [],
        },
        "s3_prefix": "s3://bucket/lroc/2009184",
        "harvest_extra_args": "-a archived --overwrite",
    }
    summary.update(overrides)
    return summary


class BatchNumberFromConfigDirTest(unittest.TestCase):
    def test_takes_the_last_segment(self):
        self.assertEqual(
            batch_number_from_config_dir(
                f"s3://pds-nucleus-config/dag-data/PDS_IMG/{BATCH}"),
            BATCH,
        )

    def test_ignores_a_trailing_slash(self):
        self.assertEqual(
            batch_number_from_config_dir(
                f"s3://pds-nucleus-config/dag-data/PDS_IMG/{BATCH}/"),
            BATCH,
        )

    def test_works_on_the_efs_form_too(self):
        self.assertEqual(
            batch_number_from_config_dir(f"/mnt/data/dag-data/PDS_IMG/{BATCH}"),
            BATCH,
        )

    def test_empty_when_there_is_no_config_dir(self):
        self.assertEqual(batch_number_from_config_dir(""), "")


class FormatHumanReportTest(unittest.TestCase):
    def test_shows_the_batch_number_and_the_airflow_run_separately(self):
        # One names the work, the other names the attempt at it. A re-run
        # keeps the batch number and gets a new run id.
        report = format_human_report(
            _summary(batch_number=BATCH, dag_run_id="manual__2026-09-13T07:06:45"), [])

        self.assertIn("Batch number", report)
        self.assertIn(BATCH, report)
        self.assertIn("Airflow run", report)
        self.assertIn("manual__2026-09-13T07:06:45", report)

    def test_says_unknown_when_the_run_carried_no_batch_number(self):
        report = format_human_report(_summary(batch_number=""), [])

        self.assertIn("(unknown)", report)

    def test_healthy_batch_says_none_need_attention(self):
        products = [
            _product("a.xml", lidvid="urn:a::1.0"),
            _product("b.xml", lidvid="urn:b::1.0"),
        ]
        report = format_human_report(_summary(), products)

        self.assertIn("PRODUCTS NEEDING ATTENTION (0)", report)
        self.assertIn("none", report)
        self.assertIn("ALL PRODUCTS (2)", report)
        self.assertIn("urn:a::1.0", report)

    def test_lists_only_non_passing_products_as_issues(self):
        products = [
            _product("a.xml", lidvid="urn:a::1.0"),
            _product("b.xml", lidvid="urn:b::1.0", validate_status="failed"),
            _product("c.xml", validate_status="not_validated"),
        ]
        report = format_human_report(_summary(status="WARNING"), products)
        attention = report.split("PRODUCTS NEEDING ATTENTION (2)")[1].split("ALL PRODUCTS")[0]

        self.assertIn("b.xml", attention)
        self.assertIn("c.xml", attention)
        self.assertNotIn("a.xml", attention)

    def test_shows_s3_location_once_in_header(self):
        summary = _summary()
        summary["s3_prefix"] = "s3://bucket/lroc/2009184"

        report = format_human_report(summary, [])

        self.assertIn("s3://bucket/lroc/2009184", report)

    def test_lists_subdirectory_paths_not_bare_names(self):
        # Two products with the same file name in different subdirectories
        # must remain distinguishable in the report.
        products = [
            _product("a.xml", s3_url="s3://bucket/lroc/2009184/le/a.xml",
                     validate_status="failed"),
            _product("a.xml", s3_url="s3://bucket/lroc/2009184/re/a.xml",
                     validate_status="failed"),
        ]
        report = format_human_report(_summary(status="WARNING"), products)

        self.assertIn("le/a.xml", report)
        self.assertIn("re/a.xml", report)

    def test_shortens_product_urls_against_the_printed_prefix(self):
        # The prefix is already a heading, so repeating it on every line
        # would push the status columns off the side for no gain.
        products = [_product("a.xml")]
        report = format_human_report(_summary(), products)
        product_lines = report.split("ALL PRODUCTS")[1]

        self.assertIn("a.xml", product_lines)
        self.assertNotIn("s3://bucket/lroc/2009184/a.xml", product_lines)
        self.assertIn("s3://bucket/lroc/2009184", report)

    def test_falls_back_to_the_full_url_when_there_is_no_common_prefix(self):
        products = [_product("a.xml", s3_url="s3://other/elsewhere/a.xml")]
        report = format_human_report(_summary(), products)

        self.assertIn("s3://other/elsewhere/a.xml", report)

    def test_reports_the_harvest_flags_the_run_used(self):
        report = format_human_report(
            _summary(harvest_extra_args="-a archived --overwrite"), [])

        self.assertIn("-a archived --overwrite", report)

    def test_says_none_when_no_harvest_flags_were_passed(self):
        report = format_human_report(_summary(harvest_extra_args=""), [])

        self.assertIn("(none)", report)

    def test_separates_what_validate_said_from_what_harvest_did(self):
        # A product can pass validation and still not be in the registry.
        # The report must not let one bare "passed" stand for both.
        products = [
            _product("a.xml", validate_status="passed",
                     harvest_status="already_registered")
        ]
        report = format_human_report(_summary(status="WARNING"), products)

        self.assertIn("VALIDATE", report)
        self.assertIn("HARVEST", report)
        self.assertIn("passed", report)
        self.assertIn("already_registered", report)

    def test_spells_out_each_failure_reason(self):
        summary = _summary(status="FAILED")
        summary["data_integrity"]["status"] = "INCOMPLETE"
        summary["data_integrity"]["failures"] = [
            "validate published no results, so nothing was verified",
            "harvest failed on 3 file(s)",
        ]

        report = format_human_report(summary, [])

        self.assertIn("FAILED   validate published no results", report)
        self.assertIn("FAILED   harvest failed on 3 file(s)", report)

    def test_shows_warnings_separately_from_failures(self):
        summary = _summary(status="WARNING")
        summary["data_integrity"]["warnings"] = [
            "harvest skipped all 166 product(s) as already registered"
        ]

        report = format_human_report(summary, [])

        self.assertIn("WARNING  harvest skipped all 166", report)
        self.assertNotIn("FAILED", report)

    def test_clean_batch_reports_neither_failures_nor_warnings(self):
        report = format_human_report(_summary(), [])

        self.assertNotIn("FAILED", report)
        self.assertNotIn("WARNING", report)

    def test_unreported_harvest_count_is_not_shown_as_zero(self):
        # None must not render as "0", which would read as "harvested none"
        # when the truth is that harvest did not report a count at all.
        summary = _summary()
        summary["counts"]["harvested"] = None
        report = format_human_report(summary, [])

        self.assertIn("not reported", report)


class CommonDirectoryTest(unittest.TestCase):
    def test_returns_shared_directory(self):
        paths = [
            "s3://bucket/lroc/2009184/M101266738LE_hst.xml",
            "s3://bucket/lroc/2009184/M101266738RE_hst.xml",
        ]
        self.assertEqual(common_directory(paths), "s3://bucket/lroc/2009184")

    def test_truncates_to_shared_parent_when_directories_differ(self):
        paths = [
            "s3://bucket/lroc/2009184/a.xml",
            "s3://bucket/lroc/2009185/b.xml",
        ]
        self.assertEqual(common_directory(paths), "s3://bucket/lroc")

    def test_never_splits_inside_a_directory_name(self):
        # "2009184" and "2009185" share the characters "200918", but that is
        # not a real directory, so it must not become the prefix.
        paths = ["/data/2009184/a.xml", "/data/2009185/b.xml"]
        self.assertEqual(common_directory(paths), "/data")

    def test_empty_when_nothing_shared(self):
        self.assertEqual(common_directory(["/a/x.xml", "/b/y.xml"]), "")

    def test_empty_for_no_paths(self):
        self.assertEqual(common_directory([]), "")


class RelativePathTest(unittest.TestCase):
    def test_strips_the_shared_prefix(self):
        self.assertEqual(
            relative_path("s3://b/lroc/2009184/a.xml", "s3://b/lroc/2009184"),
            "a.xml",
        )

    def test_keeps_the_subdirectory_below_the_prefix(self):
        self.assertEqual(relative_path("s3://b/lroc/le/a.xml", "s3://b/lroc"), "le/a.xml")

    def test_keeps_full_path_when_there_is_no_shared_prefix(self):
        self.assertEqual(relative_path("s3://b/lroc/a.xml", ""), "s3://b/lroc/a.xml")

    def test_does_not_strip_a_partial_segment_match(self):
        # "s3://b/lroc2" is not a parent directory of "s3://b/lroc/a.xml".
        self.assertEqual(
            relative_path("s3://b/lroc/a.xml", "s3://b/lroc2"), "s3://b/lroc/a.xml"
        )

    def test_round_trips_back_to_the_original_url(self):
        prefix = "s3://b/lroc/2009184"
        url = "s3://b/lroc/2009184/le/a.xml"

        self.assertEqual(f"{prefix}/{relative_path(url, prefix)}", url)


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
