# API Review Cross-Check Report
**Date:** 2026-05-15
**File:** `reviewed_tw-v11-sub-source.csv`
**Script:** `scripts/review_csv.py` (API v11, endpoint `/review/batch`)
**Scope:** Lesson 1, Segments 1–53 (51 rows, TW subtitle)

---

## Overall Verdict

The review pipeline ran successfully and produced scores and verdicts for all 51 segments. However, **four structural issues** were found between the CSV output and the API spec, and **one critical false negative** (Seg 37 meaning reversal) was missed entirely by the reviewer model.

---

## Issue 1 — `review_issues` Message Field is Always `None` (High)

Every issue in the file renders as `[severity] category: None`, for example:

```
[medium] terminology: None
[high] style: None
[high] meaning_drift: None
```

**Root cause:** The script correctly does `i.get('message')`, which returns Python `None` when the field is absent or null — rendered as the string `"None"` in the f-string. The API is returning `null` for the `message` field on every issue object across all 60+ issues. This is either:

- An API-side bug where `message` is populated as `null` (spec violation — `message` is defined as a required field in §8)
- A silent field rename (e.g. `"text"`, `"description"`, `"detail"`) — inspect a raw response to confirm

**Practical consequence:** The `review_issues` column is entirely useless. Category and severity are present, but zero diagnostic text is available. It is impossible to know *what* is wrong, only that something is wrong in a category.

**Fix:** Log one raw `res` dict from the API response to inspect actual key names, then update `i.get('message')` in `review_csv.py:175` to match.

---

## Issue 2 — Verdict Vocabulary Mismatch with API Spec (Medium)

API_v11.md §8 defines three valid verdict values:

| Spec value | Appears in CSV |
|---|---|
| `"ok"` | Yes ✓ |
| `"warning"` | Never appears |
| `"reject"` | Never appears |
| `"minor_issues"` *(not in spec)* | Yes — 35 rows |
| `"needs_revision"` *(not in spec)* | Yes — 8 rows |

The API is emitting an undocumented three-tier enum. Neither `"warning"` nor `"reject"` appear in the output. Any downstream code branching on `verdict == "warning"` or `verdict == "reject"` will silently never trigger.

**Action required:** Update API_v11.md §8 to document the actual verdict enum values, or correct the API to emit the spec values.

---

## Issue 3 — Critical False Negative: Seg 37 Meaning Reversal Undetected (Critical)

| | |
|---|---|
| **Source** | "This course **isn't** meant to cover every single detail of English grammar." |
| **Translation** | "這門課程**旨在**涵蓋英語文法的所有細節。" |
| **API score** | **70 / `minor_issues`** |
| **API issues** | `[medium] terminology: None` ×2 — no `meaning_drift` flagged |

The negation (`isn't meant to`) was dropped and inverted. The translation states the course IS designed to cover everything — the exact opposite of the source. The API gave this a score of 70 and flagged only terminology concerns.

**Why the model missed it:**

1. **No per-segment context in batch mode** — `/review/batch` shares one `context` string across all items; there is no `prev_segment`/`next_segment` per item. Without neighbouring segments, the Chinese text reads as a coherent standalone statement.
2. **LLM reviewers underweight negation** — negations are low-token-salience but high-semantic-weight. The model evaluated the Chinese on its own terms (fluent, grammatical) without detecting the inversion against the source.
3. **`strictness: "objective"`** — flags only outright errors, but the model failed to classify this as one.

**This segment requires mandatory human correction. Do not rely on the API score for Seg 37.**

---

## Issue 4 — Corrections Are Superficial (Medium)

Segs 5, 6, 8, and 11 have `review_corrected` values that only swap one character: `了解` → `瞭解`.

`了解` and `瞭解` are variant characters — both valid Traditional Chinese, both meaning "understand." `瞭解` is the MoE-preferred prescriptive form. While technically correct, these corrections:

- Do not address the `[high] terminology` or `[high] style` issues that were flagged
- Leave split-sentence structural problems completely untouched
- Seg 6 has three issues including `[high] terminology` and scores 32, yet the correction changes one character

**Do not auto-apply these corrections.** They are orthographic preferences, not fixes for the flagged quality issues.

---

## Issue 5 — `needs_revision` with Empty `review_corrected` (Medium — Spec Violation)

Per API_v11.md §8: *"`corrected`: Suggested fix when `verdict ≠ "ok"`; `null` otherwise."*

**Seg 4** (score 35, verdict `needs_revision`) has empty `review_corrected`. Multiple `minor_issues` segments also have no correction. The API appears to only provide `corrected` when score drops below ~50 or a `[high]` issue is present — not consistently for all non-`"ok"` verdicts as the spec requires.

The script handles this correctly (`res.get("corrected", "") or ""`); the issue is on the API side.

---

## Issue 6 — Score Calibration Weights Issue Count Over Semantic Severity (High)

| Seg | Actual problem | Score | Verdict |
|-----|---------------|-------|---------|
| 37 | Negation dropped — **meaning reversed** | **70** | minor_issues |
| 6 | `了解` → `瞭解` character variant + `[low] style` | **32** | needs_revision |
| 4 | "English" left untranslated (should be 英語) | 35 | needs_revision |
| 14 | "Prep's foundational series" entirely untranslated | 30 | needs_revision |

Seg 37, the worst error in the file, scores 38 points higher than Seg 6 which has no meaning error at all. The model is weighting **issue count over semantic severity** — a `[medium]` issue on three counts scores lower than a `[high]` meaning reversal that goes undetected.

**Known limitation:** This calibration is unreliable for subtitle QA where meaning preservation is the highest priority. Use the API scores as a triage filter only; do not treat a score ≥ 70 as "meaning-safe."

---

## Summary Table

| # | Issue | Severity | Fix owner |
|---|-------|----------|-----------|
| 1 | All `message` fields null — `review_issues` column useless | High | API team / inspect field name |
| 2 | Verdict enum undocumented (`minor_issues` / `needs_revision`) | Medium | Update API_v11.md or fix API |
| 3 | Seg 37 meaning reversal scored 70 / `minor_issues` — false negative | **Critical** | Human review mandatory |
| 4 | Corrections only swap 了解 → 瞭解, ignore flagged high-severity issues | Medium | Do not auto-apply |
| 5 | `needs_revision` segs with empty `corrected` — spec violation | Medium | API team |
| 6 | Scoring weights issue count over semantic severity | High | Model calibration — document as known limitation |

---

## Segments Requiring Human Review (Cannot Rely on API Score)

| Seg | API Score | API Verdict | Actual Problem |
|-----|-----------|-------------|----------------|
| 37 | 70 | minor_issues | Meaning reversed — negation dropped |
| 39 | 77 | minor_issues | Dangling clause — incomplete sentence |
| 4 | 35 | needs_revision | "English" untranslated; correction not provided |
| 14 | 30 | needs_revision | "foundational series" untranslated (regression from v9) |
