"""
classifier.py — Keyword-based review classification and tagging.

Classification:
    "Good Experience" vs "Bad Experience"
    Determined by star rating when available; falls back to sentiment keywords.

Tagging (Good):
    Fast Delivery | Responsive Support | Ease of Use | Product Effectiveness | General Positive

Tagging (Bad):
    Takes Too Long | Website Issue | Payment Issue | Customer Service | Product Quality

Tag priority order matters: first match wins.
Bad tags are checked in priority order so "Takes Too Long" doesn't get swallowed by
"Customer Service" (both may mention waiting for a reply).
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

Classification = Literal["Good Experience", "Bad Experience"]

# ---------------------------------------------------------------------------
# Keyword lists — extend per company/domain as needed
# ---------------------------------------------------------------------------

_GOOD_KEYWORDS: dict[str, list[str]] = {
    "Fast Delivery": [
        "fast", "quick", "delivery", "arrived", "received", "on time",
        "quickly", "prompt", "speedy", "rapid", "shipped", "dispatch",
        "express", "next day", "same day",
    ],
    "Responsive Support": [
        "support", "help", "helpful", "agent", "team", "customer service",
        "responsive", "quick response", "kind", "friendly", "polite",
        "assisted", "resolved", "answered",
    ],
    "Ease of Use": [
        "easy", "simple", "straightforward", "user-friendly", "convenient",
        "hassle-free", "smooth", "effortless", "intuitive", "seamless",
    ],
    "Product Effectiveness": [
        "effective", "works", "worked", "helped", "relief", "improved",
        "better", "good quality", "genuine", "authentic", "real", "potent",
    ],
}

_BAD_KEYWORDS: dict[str, list[str]] = {
    "Takes Too Long": [
        "too long", "waiting", "still waiting", "haven't received",
        "not arrived", "ages", "weeks", "days and days", "delayed",
        "never arrived", "taking forever", "slow process", "no update",
        "where is my", "missing order",
    ],
    "Website Issue": [
        "website", "site", "app", "basket", "system", "login", "bug",
        "error", "broken", "slow", "crash", "link", "page", "button",
        "checkout", "interface", "ui", "ux", "glitch", "loading",
    ],
    "Payment Issue": [
        "payment", "pay", "charge", "fee", "refund", "invoice", "billing",
        "cost", "expensive", "paypal", "credit", "debit", "money", "price",
        "charged", "subscription", "overcharged", "double charged",
    ],
    "Customer Service": [
        "support", "service", "help", "response", "reply", "contact",
        "chat", "email", "whatsapp", "agent", "staff", "team", "answer",
        "rude", "ignore", "nobody", "helpdesk", "unresponsive", "ghosted",
    ],
    # "Product Quality" is the fallback — no keyword list needed
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(text: str, star_rating: int | None = None) -> Classification:
    """
    Return "Good Experience" or "Bad Experience".

    Star rating takes precedence when present:
        4–5 stars → Good
        1–2 stars → Bad
        3 stars   → keyword fallback
    """
    if star_rating is not None:
        if star_rating >= 4:
            return "Good Experience"
        if star_rating <= 2:
            return "Bad Experience"

    # Keyword sentiment fallback
    lowered = text.lower()
    negative_signals = [
        "terrible", "awful", "horrible", "scam", "fraud", "worst",
        "disgusting", "never again", "do not", "don't buy", "waste",
        "disappointed", "useless", "broken", "fake", "not delivered",
        "no refund", "impossible", "zero stars",
    ]
    if any(w in lowered for w in negative_signals):
        return "Bad Experience"
    return "Good Experience"


def tag_good(text: str) -> str:
    """Return the most relevant Good tag for a positive review."""
    lowered = text.lower()
    for tag, keywords in _GOOD_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return tag
    return "General Positive"


def tag_bad(text: str) -> str:
    """
    Return the most relevant Bad tag for a negative review.
    Priority order: Takes Too Long → Website Issue → Payment Issue →
                    Customer Service → Product Quality (fallback).
    """
    lowered = text.lower()
    for tag, keywords in _BAD_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return tag
    return "Product Quality"


def tag(text: str, classification: Classification) -> str:
    """Dispatch to the correct tagger based on classification."""
    if classification == "Good Experience":
        return tag_good(text)
    return tag_bad(text)
