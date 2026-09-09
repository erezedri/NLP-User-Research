"""
scraper.py — Apify-based review scraper for Trustpilot (and extensible to others).

Lessons learned from DoktorABC session:
- Trustpilot 403-blocks all direct HTTP on every subdomain — Apify is mandatory.
- Two actors serve different needs:
    * automation-lab~trustpilot : general reviews, supports language + star filter as strings.
    * blackfalcondata (UB7ZX4EVAFQk7z1bA) : superior for star-filtered pulls; accepts int star list.
- Run object is a Pydantic model — use dot notation (run.default_dataset_id), NOT dict access.
- Memory tiers: 1024 MB ≤1k reviews | 2048 MB ≤15k | 4096 MB for more.
- wait_duration takes a timedelta, not seconds or a plain int.
"""

import logging
import os
from datetime import timedelta
from typing import Any

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Actor IDs
# ---------------------------------------------------------------------------
ACTOR_GENERAL = "automation-lab~trustpilot"
ACTOR_STAR_FILTERED = "UB7ZX4EVAFQk7z1bA"  # blackfalcondata/trustpilot-reviews-scraper


def _memory_mbytes(max_results: int) -> int:
    """Return appropriate Apify memory tier for the requested volume."""
    if max_results <= 1_000:
        return 1_024
    if max_results <= 15_000:
        return 2_048
    return 4_096


def _get_client() -> ApifyClient:
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "APIFY_API_KEY is not set. Add it to your .env file."
        )
    return ApifyClient(api_key)


def scrape_general(
    company_domain: str,
    max_results: int = 150,
    languages: list[str] | None = None,
    sort: str = "recency",
) -> list[dict[str, Any]]:
    """
    Scrape general reviews via automation-lab~trustpilot.

    Args:
        company_domain: e.g. "doktorabc.com"
        max_results: how many reviews to fetch
        languages: e.g. ["en"] — omit for all languages
        sort: "recency" or "relevance"

    Returns:
        List of raw review dicts from Apify dataset.
    """
    client = _get_client()
    run_input: dict[str, Any] = {
        "companyUrls": [company_domain],
        "maxReviewsPerCompany": max_results,
        "sort": sort,
        "includeCompanyInfo": False,
    }
    if languages:
        run_input["languages"] = languages

    logger.info(
        "Scraping up to %d reviews for %s via automation-lab actor ...",
        max_results,
        company_domain,
    )
    try:
        run = client.actor(ACTOR_GENERAL).call(
            run_input=run_input,
            memory_mbytes=_memory_mbytes(max_results),
            wait_duration=timedelta(minutes=10),
        )
        items = list(client.dataset(run.default_dataset_id).iterate_items())
        logger.info("Fetched %d reviews (general).", len(items))
        return items
    except Exception as exc:
        logger.error("scrape_general failed for %s: %s", company_domain, exc)
        raise


def scrape_by_stars(
    company_domain: str,
    stars: list[int],
    max_results: int = 150,
    sort: str = "recency",
) -> list[dict[str, Any]]:
    """
    Scrape star-filtered reviews via blackfalcondata actor.

    Args:
        company_domain: e.g. "doktorabc.com"
        stars: list of star ratings to include, e.g. [1] or [4, 5]
        max_results: how many reviews to fetch
        sort: "recency" or "relevance"

    Returns:
        List of raw review dicts from Apify dataset.

    Note:
        blackfalcondata accepts stars as integers (not strings).
        automation-lab~trustpilot requires stars as strings — handled in scrape_general.
    """
    client = _get_client()
    run_input: dict[str, Any] = {
        "companyDomain": company_domain,
        "maxResults": max_results,
        "stars": stars,          # integers here — blackfalcondata requirement
        "sort": sort,
        "includeCompanyInfo": False,
    }

    logger.info(
        "Scraping up to %d reviews for %s (stars=%s) via blackfalcondata actor ...",
        max_results,
        company_domain,
        stars,
    )
    try:
        run = client.actor(ACTOR_STAR_FILTERED).call(
            run_input=run_input,
            memory_mbytes=_memory_mbytes(max_results),
            wait_duration=timedelta(hours=3),
        )
        items = list(client.dataset(run.default_dataset_id).iterate_items())
        logger.info("Fetched %d reviews (star-filtered).", len(items))
        return items
    except Exception as exc:
        logger.error("scrape_by_stars failed for %s: %s", company_domain, exc)
        raise


def extract_text(raw_item: dict[str, Any]) -> str:
    """Pull review text from a raw Apify item, trying common field names."""
    for field in ("text", "body", "reviewBody", "content", "review"):
        value = raw_item.get(field)
        if value and isinstance(value, str) and len(value.strip()) > 5:
            return value.strip()
    return ""
