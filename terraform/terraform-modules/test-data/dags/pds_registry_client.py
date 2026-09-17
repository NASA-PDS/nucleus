"""
PDS Registry Client

Live verification of a product against the public PDS registry search API,
independent of Nucleus's own harvest result. Stdlib urllib only -- no new
MWAA dependency -- since this only needs a single GET per product.
"""

import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MAX_WORKERS = 8


def check_registry_status(lidvid: str, url_prefix: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Query the live PDS registry search API for one product's lidvid.

    Returns "confirmed" (HTTP 200), "not_found" (HTTP 404 -- an explicit
    negative), or "unknown" (any other status, timeout, DNS/connection
    failure). "unknown" is kept distinct from "not_found" on purpose: a
    network failure or a 5xx says nothing about whether the registry has
    the product, so it must never be counted as a confirmed absence.
    """
    url = url_prefix + urllib.parse.quote(lidvid, safe="")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return "confirmed" if resp.status == 200 else "unknown"
    except urllib.error.HTTPError as e:
        return "not_found" if e.code == 404 else "unknown"
    except OSError:
        # Covers urllib.error.URLError and socket.timeout/TimeoutError too --
        # both are OSError subclasses, so listing them separately was
        # redundant. Any other network failure (DNS, connection refused,
        # etc.) lands here as well.
        return "unknown"


def registry_url_for(lidvid: str, url_prefix: str) -> str:
    """The public URL for a product, for display -- no live call needed."""
    return url_prefix + urllib.parse.quote(lidvid, safe="")


def verify_products_against_registry(
    products,
    url_prefix: str,
    max_workers: int = DEFAULT_MAX_WORKERS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
):
    """Check a bounded worker pool of registry lookups for the given products.

    `products` should already be filtered down to the ones worth checking
    (the caller decides gating -- see _products_to_verify in the DAG).
    Returns {product_name: registry_status}. A per-product exception is
    mapped to "unknown" rather than propagating, so one bad lookup can't
    fail the whole batch's verification pass.
    """
    results = {}
    if not products:
        return results

    with ThreadPoolExecutor(max_workers=min(max_workers, len(products))) as pool:
        futures = {
            pool.submit(check_registry_status, product["lidvid"], url_prefix, timeout): product["name"]
            for product in products
            if product.get("lidvid")
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = "unknown"

    return results
