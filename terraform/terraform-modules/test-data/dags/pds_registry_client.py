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

    Every "unknown" is printed with the specific status code/exception
    that caused it -- otherwise a genuine indexing-lag "not there yet"
    and a network-level failure reaching the registry at all are
    indistinguishable from the caller's side, which made a real incident
    (see NASA-PDS/nucleus issue tracker, Nov 2026) impossible to diagnose
    from the DAG logs alone.
    """
    url = url_prefix + urllib.parse.quote(lidvid, safe="")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                return "confirmed"
            print(f"registry check unknown for {lidvid}: HTTP {resp.status} (expected 200)")
            return "unknown"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "not_found"
        print(f"registry check unknown for {lidvid}: HTTP {e.code} {e.reason}")
        return "unknown"
    except OSError as e:
        # Covers urllib.error.URLError and socket.timeout/TimeoutError too --
        # both are OSError subclasses, so listing them separately was
        # redundant. Any other network failure (DNS, connection refused,
        # etc.) lands here as well.
        print(f"registry check unknown for {lidvid}: {type(e).__name__}: {e}")
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
            except Exception as e:
                # check_registry_status already catches and logs
                # HTTPError/OSError itself -- reaching here means something
                # it doesn't handle (a bug, not a network condition), so
                # it's worth printing distinctly from the expected cases.
                print(f"registry check unknown for {name}: unexpected {type(e).__name__}: {e}")
                results[name] = "unknown"

    return results
