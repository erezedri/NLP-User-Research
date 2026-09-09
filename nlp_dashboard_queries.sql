-- ══════════════════════════════════════════════════════════════════
--   NLP Review Intelligence — Dashboard SQL Queries
--   Source  : DoktorABC Reviews (scraped via Trustpilot / Apify)
--   Table   : doktorabc_reviews
--   Columns : persona  TEXT   — "Patient" (or "Doctor")
--             review   TEXT   — original review text
--             classification TEXT — "Good Experience" / "Bad Experience"
--             tag      TEXT   — category tag assigned by classifier
-- ══════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────
-- 1.  KPI SUMMARY BAR
--     Powers: Total · Good · Bad · Satisfaction % · Complaint %
-- ─────────────────────────────────────────────────────────────────
WITH base AS (
    SELECT
        classification,
        tag,
        review
    FROM doktorabc_reviews
    WHERE review  IS NOT NULL
      AND TRIM(review) <> ''
)
SELECT
    COUNT(*)                                                                        AS total_reviews,
    SUM(CASE WHEN classification = 'Good Experience' THEN 1 ELSE 0 END)            AS good_count,
    SUM(CASE WHEN classification = 'Bad Experience'  THEN 1 ELSE 0 END)            AS bad_count,
    ROUND(
        100.0 * SUM(CASE WHEN classification = 'Good Experience' THEN 1 ELSE 0 END)
        / COUNT(*), 0
    )                                                                               AS satisfaction_pct,
    ROUND(
        100.0 * SUM(CASE WHEN classification = 'Bad Experience' THEN 1 ELSE 0 END)
        / COUNT(*), 0
    )                                                                               AS complaint_pct
FROM base;


-- ─────────────────────────────────────────────────────────────────
-- 2.  GOOD EXPERIENCE — TAG DISTRIBUTION
--     Powers: Phase 1 Donut Chart + Horizontal Bar Chart
-- ─────────────────────────────────────────────────────────────────
SELECT
    tag,
    COUNT(*)                                                                        AS review_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1
    )                                                                               AS pct_of_good
FROM doktorabc_reviews
WHERE classification = 'Good Experience'
GROUP BY tag
ORDER BY review_count DESC;


-- ─────────────────────────────────────────────────────────────────
-- 3.  BAD EXPERIENCE — TAG DISTRIBUTION
--     Powers: Phase 2 Donut Chart + Horizontal Bar Chart
-- ─────────────────────────────────────────────────────────────────
SELECT
    tag,
    COUNT(*)                                                                        AS review_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1
    )                                                                               AS pct_of_bad
FROM doktorabc_reviews
WHERE classification = 'Bad Experience'
GROUP BY tag
ORDER BY review_count DESC;


-- ─────────────────────────────────────────────────────────────────
-- 4.  SAMPLE REVIEWS — GOOD (one per tag, longest text wins)
--     Powers: Phase 1 review cards
-- ─────────────────────────────────────────────────────────────────
WITH ranked AS (
    SELECT
        tag,
        review,
        ROW_NUMBER() OVER (
            PARTITION BY tag
            ORDER BY LEN(review) DESC
        ) AS rn
    FROM doktorabc_reviews
    WHERE classification = 'Good Experience'
)
SELECT
    tag,
    review
FROM ranked
WHERE rn = 1
ORDER BY tag;


-- ─────────────────────────────────────────────────────────────────
-- 5.  SAMPLE REVIEWS — BAD (one per tag, longest text wins)
--     Powers: Phase 2 complaint cards
-- ─────────────────────────────────────────────────────────────────
WITH ranked AS (
    SELECT
        tag,
        review,
        ROW_NUMBER() OVER (
            PARTITION BY tag
            ORDER BY LEN(review) DESC
        ) AS rn
    FROM doktorabc_reviews
    WHERE classification = 'Bad Experience'
)
SELECT
    tag,
    review
FROM ranked
WHERE rn = 1
ORDER BY tag;


-- ─────────────────────────────────────────────────────────────────
-- 6.  BALANCED FULL DATASET (for scrollable review table)
--     Trims the larger class so Good count = Bad count (50/50)
-- ─────────────────────────────────────────────────────────────────
WITH good_rows AS (
    SELECT
        persona,
        review,
        classification,
        tag,
        ROW_NUMBER() OVER (ORDER BY NEWID())    AS rn
    FROM doktorabc_reviews
    WHERE classification = 'Good Experience'
),
bad_rows AS (
    SELECT
        persona,
        review,
        classification,
        tag,
        ROW_NUMBER() OVER (ORDER BY NEWID())    AS rn
    FROM doktorabc_reviews
    WHERE classification = 'Bad Experience'
),
target_count AS (
    SELECT MIN(cnt) AS n
    FROM (
        SELECT COUNT(*) AS cnt FROM good_rows
        UNION ALL
        SELECT COUNT(*) AS cnt FROM bad_rows
    ) sub
)
SELECT persona, review, classification, tag
FROM good_rows
CROSS JOIN target_count
WHERE good_rows.rn <= target_count.n

UNION ALL

SELECT persona, review, classification, tag
FROM bad_rows
CROSS JOIN target_count
WHERE bad_rows.rn <= target_count.n

ORDER BY classification, tag;


-- ─────────────────────────────────────────────────────────────────
-- 7.  CROSS-TAB: classification × tag (full matrix view)
-- ─────────────────────────────────────────────────────────────────
SELECT
    classification,
    tag,
    COUNT(*)                                                AS review_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY classification), 1
    )                                                       AS pct_within_class
FROM doktorabc_reviews
GROUP BY classification, tag
ORDER BY classification, review_count DESC;
