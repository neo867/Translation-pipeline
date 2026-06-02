# Translation Pipeline — Command Reference

## Setup

All commands are run from the project root:
```
/Users/prep-ea/Documents/Translation Pipeline/
```

Scripts: `scripts/translate_csv.py`, `scripts/translate_srt.py`, `scripts/review_srt.py`

---

## Language Codes

| Code | Language |
|------|----------|
| `tw` | Traditional Chinese |
| `th` | Thai |
| `cn` | Simplified Chinese |
| `kr` | Korean |
| `jp` | Japanese |
| `id` | Indonesian |
| `vi` | Vietnamese |

---

## Input Files (Test Cases)

| Content type | File |
|---|---|
| Course subtitles | `Test Case/Testing Output/English/sub-50-eng.csv` |
| Answer explanations | `Test Case/Testing Output/English/explain_eng.csv` |
| UI strings | `Test Case/Testing Output/English/ui_eng.csv` |

---

## Basic Commands — Single Language

The script auto-detects content type from the CSV columns. Run from the project root.

### Course subtitles
```bash
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw
```

### Answer explanations
```bash
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/explain_eng.csv" \
  --target-lang tw
```

### UI strings
```bash
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/ui_eng.csv" \
  --target-lang tw \
  --preset ui
```

> **Note:** UI files require `--preset ui` because auto-detection expects a `tw content` column that may not be present in the source file.

Replace `tw` with any language code from the table above.

---

## Output Files

Outputs are written to the **same folder as the input file**, prefixed with the language code:

| Input | Output |
|---|---|
| `sub-50-eng.csv` | `tw_sub-50-eng.csv` |
| `explain_eng.csv` | `tw_explain_eng.csv` |
| `ui_eng.csv` | `tw_ui_eng.csv` |

---

## Named Output — A/B Testing and Versioning

Use `--output` to save to a specific filename (in the same folder as the input):

```bash
# Save as (v11-track1) tw_sub-50-eng.csv
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw \
  --output "(v11-track1) tw_sub-50-eng.csv"
```

Use different names to compare versions side by side:
```bash
# Version A
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw \
  --output "(v11-A) tw_sub-50-eng.csv"

# Version B (after a change)
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw \
  --output "(v11-B) tw_sub-50-eng.csv"
```

To test a second language variant (e.g. `tw2`), use a separate output name:
```bash
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw \
  --output "(v11-track1) tw2_sub-50-eng.csv"
```

---

## Resume Behaviour

The script is **resume-safe** by default. If a run is interrupted, re-running the same command will skip rows that already have a translation and continue from where it left off.

To force a full re-run from scratch (overwrite existing translations):
```bash
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw \
  --rerun
```

---

## Batch Mode

By default, subtitles use **single-translate mode** (one API call per segment, with `prev_segment`/`next_segment` context). All other content types use batch mode.

To override subtitles to batch mode (faster, but loses cross-segment context):
```bash
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang tw \
  --batch
```

---

## All Languages at Once — Batch Runner

`scripts/batch_translate.py` runs `translate_csv.py` for every language in sequence.

```bash
# All 7 languages, subtitles
python3 scripts/batch_translate.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv"

# All 7 languages, explanations
python3 scripts/batch_translate.py \
  --input "Test Case/Testing Output/English/explain_eng.csv"

# All 7 languages, UI
python3 scripts/batch_translate.py \
  --input "Test Case/Testing Output/English/ui_eng.csv"
```

Default languages: `tw cn kr id jp th vi`

To run a subset:
```bash
python3 scripts/batch_translate.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --langs tw th
```

---

## Running a Full Test for a New Language Pair

Example: first time running Thai subtitles.

```bash
# Step 1 — run the translation
python3 scripts/translate_csv.py \
  --input "Test Case/Testing Output/English/sub-50-eng.csv" \
  --target-lang th \
  --output "(v11-track1) th_sub-50-eng.csv"

# Step 2 — open the output file and review
# Test Case/Testing Output/English/(v11-track1) th_sub-50-eng.csv
```

Check:
- Are any cells blank? (API error — re-run to resume)
- Do any cells contain `FALLBACK_ORIGINAL:` prefix? (backend 503 — re-run)
- Subtitle: is cross-segment continuity better than V9?
- Thai: are ค่ะ/ครับ appearing mid-sentence or on fragments?
- Thai: are prohibited words present (มัน, ศิษย์, กอร์ส)?
- TW: is S37 negation preserved ("並非旨在" not "旨在")?

---

## Known Issues (as of V11 Track 1)

| Segment | Issue | Status |
|---|---|---|
| S45 (TW subtitles) | Still reads as sentence-start ("來自…") — split-sentence not resolved by `prev_segment` | Requires API `preceding_text` parameter fix (escalated P0) |
| S37 (TW subtitles) | Non-deterministic negation drop — "isn't meant to" becomes "IS meant to" in ~2/3 runs | Requires API validation-stage fix (escalated P1) |
| S18/S19 (TW subtitles) | "nouns/verbs" left in English — `teaching_lang=English` blanket-preserves grammar meta-terms | Requires API `translate_terms` allow-list (escalated P1) |
| Thai ค่ะ on fragments | `speaker` param added; not yet tested — TH run required to confirm fix | Run TH subtitles to verify |
| Thai มัน / ศิษย์ | Prohibited vocabulary list added to context; not yet tested | Run TH subtitles to verify |

---

---

## SRT Translation — translate_srt.py

### Single file
```bash
python3 scripts/translate_srt.py \
  "IE Intermediate 2.6/Listening Int/L1S1.srt" \
  --target zhTW \
  --context "IELTS course"
```

### Queue (up to 10 files)
```bash
python3 scripts/translate_srt.py \
  --input "IE Intermediate 2.6/Listening Int/L1S1.srt" \
  --input "IE Intermediate 2.6/Listening Int/L2S1.srt" \
  --input "IE Intermediate 2.6/Listening Int/L2S2.srt" \
  --target zhTW \
  --context "IELTS course"
```

Maximum 10 files per run. Split into multiple runs if you have more.

### Whole folder
```bash
python3 scripts/translate_srt.py \
  --folder "IE Intermediate 2.6/Listening Int/" \
  --target zhTW \
  --context "IELTS course"
```

### Force retranslate from scratch
```bash
python3 scripts/translate_srt.py \
  --input "IE Intermediate 2.6/Listening Int/L1S1.srt" \
  --target zhTW \
  --context "IELTS course" \
  --rerun
```

### Language codes (translate_srt.py)

| Code | Language |
|------|----------|
| `zhTW` | Traditional Chinese |
| `zhCN` | Simplified Chinese |
| `ko` | Korean |
| `ja` | Japanese |
| `th` | Thai |
| `id` | Indonesian |
| `vi` | Vietnamese |
| `pt` | Portuguese |
| `esES` | Spanish (Spain) |
| `esMX` | Spanish (Mexico) |

### Output location

Mirrors input folder structure under `output/`:

| Input | Output |
|---|---|
| `IE Intermediate 2.6/Listening Int/L1S1.srt` | `output/IE Intermediate 2.6/Listening Int/zhTW_L1S1.srt` |

### Resume behaviour

Resume-safe by default — re-run the same command to continue from where it left off. Progress is saved after every batch chunk to a hidden `.progress.json` file, which is deleted on clean finish.

---

## SRT Review Queue — batch_review.py

Review all translated SRTs in `output/` in one go.

### Review everything pending
```bash
python3 scripts/batch_review.py
```

### Filter by language
```bash
python3 scripts/batch_review.py --target zhTW
```

### Filter by folder
```bash
python3 scripts/batch_review.py --folder "IE Intermediate 2.6/Listening Int"
```

### Preview queue without running
```bash
python3 scripts/batch_review.py --dry-run
```

### Force re-review already-done files
```bash
python3 scripts/batch_review.py --force
```

### Stricter review (flags unnatural phrasing)
```bash
python3 scripts/batch_review.py --strictness linguist
```

Auto-detects translated files from `output/`, skips files that already have a review CSV, resumes mid-file if interrupted. Prints a summary table with avg score, ok/warning/reject counts per file when done.

Review CSVs are saved alongside the translated file:
`output/IE Intermediate 2.6/Listening Int/review_zhTW_L1S1.csv`

---

## SRT Review — review_srt.py

Score a translated SRT against the source using the `/review/batch` API endpoint.

### Basic usage
```bash
python3 scripts/review_srt.py \
  "IE Intermediate 2.6/Listening Int/L1S1.srt" \
  --target zhTW
```

Auto-detects the translated file from `output/`. Outputs a CSV report to the same output folder:
`output/IE Intermediate 2.6/Listening Int/review_zhTW_L1S1.csv`

### Stricter review (flags unnatural phrasing)
```bash
python3 scripts/review_srt.py \
  "IE Intermediate 2.6/Listening Int/L1S1.srt" \
  --target zhTW \
  --strictness linguist
```

### Report columns

| Column | Notes |
|---|---|
| `block` | SRT block number |
| `timestamp` | Timestamp from the SRT |
| `source` | Original English text |
| `translation` | Translated text |
| `score` | 0–100 (≥90 shippable, 70–89 usable, <70 rework) |
| `verdict` | `ok` / `warning` / `reject` |
| `corrected` | Suggested fix (when verdict ≠ ok) |
| `issues` | List of flagged issues with severity and category |

---

## Troubleshooting

**Blank output cells**
Re-run the same command — the script will resume from the last translated row. Blank cells are API timeouts or transient errors.

**`FALLBACK_ORIGINAL:` in output**
The backend returned 503. The source text was preserved as a fallback. Re-run to retry those rows.

**`422 Unprocessable Entity` in logs**
Usually a payload too large for batch mode. Switch to single mode (remove `--batch` if set) or reduce input size.

**`401 Unauthorized`**
Check that `TRANSLATE_API_KEY` is set in your environment or `.env` file.

**Output file not created**
The input file path is wrong or the column headers don't match any known preset. Check that the CSV has the expected columns:
- Subtitles: `lesson`, `segment`, `timestamp`, `source`
- Explanations: `id`, `explain_eng`
- UI: `key`, `english content`
