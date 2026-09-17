"""Unit tests for pds_registry_client."""

import socket
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from pds_registry_client import (
    check_registry_status,
    registry_url_for,
    verify_products_against_registry,
)


URL_PREFIX = "https://pds.mcp.nasa.gov/api/search/1/products/"
LIDVID = "urn:nasa:pds:lro-l-lroc-2-edr:lrolrc_0001_data:wac.m101390758ce"


class CheckRegistryStatusTest(unittest.TestCase):
    @patch("pds_registry_client.urllib.request.urlopen")
    def test_returns_confirmed_on_200(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        self.assertEqual(check_registry_status(LIDVID, URL_PREFIX), "confirmed")

    @patch("pds_registry_client.urllib.request.urlopen")
    def test_returns_not_found_on_404(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=URL_PREFIX, code=404, msg="Not Found", hdrs=None, fp=None
        )

        self.assertEqual(check_registry_status(LIDVID, URL_PREFIX), "not_found")

    @patch("pds_registry_client.urllib.request.urlopen")
    def test_returns_unknown_on_server_error(self, mock_urlopen):
        # A 5xx says nothing about whether the registry has the product --
        # it must never be counted as a confirmed absence.
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=URL_PREFIX, code=500, msg="Internal Server Error", hdrs=None, fp=None
        )

        self.assertEqual(check_registry_status(LIDVID, URL_PREFIX), "unknown")

    @patch("pds_registry_client.urllib.request.urlopen")
    def test_returns_unknown_on_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout()

        self.assertEqual(check_registry_status(LIDVID, URL_PREFIX), "unknown")

    @patch("pds_registry_client.urllib.request.urlopen")
    def test_returns_unknown_on_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("no route to host")

        self.assertEqual(check_registry_status(LIDVID, URL_PREFIX), "unknown")

    @patch("pds_registry_client.urllib.request.urlopen")
    def test_url_encodes_the_lidvid(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        check_registry_status(LIDVID, URL_PREFIX)

        called_url = mock_urlopen.call_args[0][0]
        self.assertTrue(called_url.startswith(URL_PREFIX))
        self.assertNotIn(":", called_url[len(URL_PREFIX):])


class RegistryUrlForTest(unittest.TestCase):
    def test_builds_url_without_a_live_call(self):
        url = registry_url_for(LIDVID, URL_PREFIX)
        self.assertTrue(url.startswith(URL_PREFIX))


class VerifyProductsAgainstRegistryTest(unittest.TestCase):
    def test_empty_products_short_circuits(self):
        self.assertEqual(verify_products_against_registry([], URL_PREFIX), {})

    @patch("pds_registry_client.check_registry_status")
    def test_maps_each_product_name_to_its_status(self, mock_check):
        mock_check.return_value = "confirmed"
        products = [{"name": "a.xml", "lidvid": "urn:a::1.0"}]

        result = verify_products_against_registry(products, URL_PREFIX)

        self.assertEqual(result, {"a.xml": "confirmed"})

    @patch("pds_registry_client.check_registry_status")
    def test_a_failing_lookup_becomes_unknown_not_an_exception(self, mock_check):
        mock_check.side_effect = Exception("boom")
        products = [{"name": "a.xml", "lidvid": "urn:a::1.0"}]

        result = verify_products_against_registry(products, URL_PREFIX)

        self.assertEqual(result, {"a.xml": "unknown"})

    def test_skips_products_with_no_lidvid(self):
        products = [{"name": "a.xml", "lidvid": None}]

        result = verify_products_against_registry(products, URL_PREFIX)

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
