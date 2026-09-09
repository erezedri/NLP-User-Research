"""
run_pipeline.py — CLI entry point for the NLP Review Intelligence pipeline.

Usage:
    python run_pipeline.py --company doktorabc.com --name "DoktorABC" \
        --output "C:/path/to/Reviews.xlsx" --good 168 --bad 168

Steps executed:
    1. Scrape general reviews (automation-lab actor)
    2. Scrape 1-star reviews (blackfalcondata actor) if bad quota unmet
    3. Classify each review: Good / Bad
    4. Tag each review by category
    5. Balance to equal Good/Bad counts
    6. Write styled Excel
    7. Launch Dash dashboard

Secrets required in .env:
    APIFY_API_KEY=apify_api_...
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

from pipelines.nlp_reviews import classifier, excel_builder, scraper, dashboard


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NLP Review Intelligence Pipeline")
    p.add_argument("--company", required=True, help="Company domain, e.g. doktorabc.com")
    p.add_argument("--name", required=True, help="Display name, e.g. DoktorABC")
    p.add_argument("--output", required=True, help="Output .xlsx path")
    p.add_argument("--good", type=int, default=150, help="Target Good Experience count")
    p.add_argument("--bad", type=int, default=150, help="Target Bad Experience count")
    p.add_argument("--port", type=int, default=8050, help="Dash server port")
    p.add_argument("--no-dashboard", action="store_true", help="Skip dashboard launch")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    total_target = args.good + args.bad

    # ── Step 1: Scrape general reviews ───────────────────────────────────────
    logger.info("Step 1/5 — Scraping general reviews ...")
    raw_general = scraper.scrape_general(
        company_domain=args.company,
        max_results=total_target,
        languages=["en"],
    )

    # ── Step 2: Scrape additional 1-star reviews if needed ───────────────────
    logger.info("Step 2/5 — Scraping 1-star reviews for bad coverage ...")
    raw_bad = scraper.scrape_by_stars(
        company_domain=args.company,
        stars=[1],
        max_results=args.bad,
    )

    # ── Step 3 & 4: Classify + Tag ───────────────────────────────────────────
    logger.info("Step 3/5 — Classifying and tagging reviews ...")
    all_raw = raw_general + raw_bad
    processed: list[dict] = []
    seen_texts: set[str] = set()

    for item in all_raw:
        text = scraper.extract_text(item)
        if not text or text in seen_texts:
            continue
        seen_texts.add(text)
        star_rating = item.get("stars") or item.get("rating") or item.get("starRating")
        try:
            star_rating = int(star_rating) if star_rating is not None else None
        except (ValueError, TypeError):
            star_rating = None

        classification = classifier.classify(text, star_rating)
        tag = classifier.tag(text, classification)
        processed.append({
            "text": text,
            "classification": classification,
            "tag": tag,
            "persona": "Patient",
        })

    logger.info(
        "Processed %d unique reviews before balancing.", len(processed)
    )

    # ── Step 5: Write Excel ───────────────────────────────────────────────────
    logger.info("Step 4/5 — Writing Excel to %s ...", output_path)
    excel_builder.write_excel(
        rows=processed,
        output_path=output_path,
        balance=True,
    )

    # ── Step 6: Launch dashboard ──────────────────────────────────────────────
    if not args.no_dashboard:
        logger.info("Step 5/5 — Launching dashboard on port %d ...", args.port)
        dashboard.run_dashboard(
            excel_path=output_path,
            company_name=args.name,
            port=args.port,
        )
    else:
        logger.info("Dashboard skipped (--no-dashboard).")
        logger.info("Done. Output: %s", output_path)


if __name__ == "__main__":
    main()
