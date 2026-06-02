# Translation Pipeline 4.0 — LLM Instruction Guide

## What This Project Does

Translates English educational content (IELTS subtitles, answer explanations, UI text) into
multiple target languages using a self-hosted Translation API (Pipeline V10, API V11).

The API runs a Qwen 3.6-35B model with a multi-stage pipeline:
S1 (translate) → L2 (deterministic fixes) → S3 (LLM sieve) → S4 (revise loop) → S5 (best-of selector).

---

## API

| Field | Value |
|---|---|
| Base URL | `https://translate.flowb.ai` |
| Auth header | `X-API-Key: tw-localizer-dev-a1b2c3d4e5f6` |
| Health check | `GET /health` → `{"status":"ok"}` |
| Single translate | `POST /translate` |
| Batch translate | `POST /translate/batch` |

Full parameter reference: `API_v11.md`. Pipeline internals: `PIPELINE_v10.md`.

### Core params for every pedagogical/educational request

```json
{
  "text": "...",
  "source_lang": "en",
  "target_lang": "zhTW",
  "teaching_lang": "English",
  "content_type": "subtitle",
  "domain": "education",
  "intent": "pedagogical",
  "vocab_mode": "preserve",
  "context": "..."
}
```

- `teaching_lang: "English"` — keeps English tokens in Latin script (Pattern 2 preservation).
  Without this, English words in the source may be translated into the target language.
- `vocab_mode: "preserve"` — default in v11; do NOT change unless bilingual gloss output is needed.
- `content_type: "subtitle"` — use for educational sentences (subtitles, answer explanations).
  Use `"ui_button"` / `"ui_heading"` for UI copy; `"legal"` for legal text.
- `context` — describe the content type and any special rules. More specific = better.

### `{{double braces}}` preservation (Pattern 1)

Any token wrapped in `{{...}}` in the source text is automatically preserved verbatim and the
braces are stripped from the final output. No extra param needed. Example:

- Source: `"The answer is {{FALSE}}."`
- Delivered: `"答案是 FALSE。"` (braces stripped, content kept)

The pipeline enforces this at every stage. The S5 selector disqualifies any candidate that drops
a braced token.

### Server busy (503)

The server caps at 4 concurrent translations. If you get a 503, wait ~10s and retry.
The `translate_csv.py` and `translate_srt.py` scripts handle this automatically.

---

## Scripts

### `translate_csv.py` — CSV column translation

Translates `explain_eng` → `explain_tw` (zhTW) for IELTS answer explanation rows.

```
Input:  Test Case/tw test output/explain_tw.csv       (id, explain_eng, explain_tw)
Output: Test Case/tw test output/explain_tw_translated.csv
```

**Resume-safe**: rows where `explain_tw` is already set and differs from `explain_eng` are
skipped on re-run. Safe to kill and restart at any time.

Run:
```bash
python3 scripts/translate_csv.py
```

**If you need to retranslate specific rows**, set their `explain_tw` value back to the
`explain_eng` value (or empty) in `explain_tw_translated.csv`, then re-run.

### `translate_srt.py` — SRT subtitle translation

Translates `.srt` files from `input/` to `output/` with a language prefix.

```bash
python3 scripts/translate_srt.py --target zhTW --teaching-lang English --domain education
python3 scripts/translate_srt.py --folder "input/EN Reading Inter 2.6/" --target zhTW,ko,ja
python3 scripts/translate_srt.py --target zhTW --vocab-mode bilingual --verbose
```

---

## File Layout

```
Translation Pipeline 4.0/
├── scripts/
│   ├── translate_csv.py      # CSV translation script (answer explanations)
│   ├── translate_srt.py      # SRT subtitle translation script
│   └── ...                   # Other utilities
├── API_v11.md                # Full API reference (params, response shape, infra)
├── PIPELINE_v10.md           # Pipeline internals (S1-S5, L2, pattern preservation)
├── input/                    # Source SRT files (EN Listening/Reading/Speaking)
├── output/                   # Translated SRT files (LANG_filename.srt)
└── Test Case/
    ├── Answer Explanations/
    │   └── explain_eng_only.csv          # Source: 50 IELTS answer explanations (en only)
    └── tw test output/
        ├── explain_tw.csv                # Input for translate_csv.py (explain_tw = placeholder)
        └── explain_tw_translated.csv     # Output with actual zhTW translations
```

---

## Checking Server Status

```bash
# Quick health check
curl -s https://translate.flowb.ai/health
# Expected: {"status":"ok"}

# Test a real translation
curl -s -X POST https://translate.flowb.ai/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","source_lang":"en","target_lang":"zhTW"}'
# 200 = working; 503 = busy (retry); 502 = translator backend down
```

If you get `502 Bad Gateway`: nginx is up but the FastAPI backend on `:13102` is down.
Someone needs to restart the `translator` service on the server.

---

## Common Mistakes to Avoid

1. **Omitting `teaching_lang`** for educational content → English vocab gets translated.
2. **Passing `vocab_mode: "bilingual"`** when you don't want `word (翻譯)` output — the default
   `"preserve"` is correct for IELTS content.
3. **Not setting `context`** — the pipeline uses context to tune style and glossary. Always
   describe what the content is.
4. **Translating rows that already have a valid translation** — check if `explain_tw != explain_eng`
   before calling the API.
5. **Not handling 503** — always retry with a delay; the server is shared and hits concurrency
   limits under load.
