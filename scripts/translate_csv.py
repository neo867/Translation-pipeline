#!/usr/bin/env python3
from __future__ import annotations

"""
translate_csv.py — Translate CSV column via Translation API V11 (Pipeline V10).

Supports multiple input file types:
1. Answer explanations (id, explain_eng, explain_tw)
2. Course subtitles (lesson, segment, timestamp, source, target_tw)
3. UI text (key, english content, tw content)

Supports target languages: tw/tw2 (zhTW), id, jp (ja), kr/kr2 (ko), th, vi.
Add more *2 variants by duplicating a key in TARGET_LANG_MAP (same API lang, new column).

Resume-safe: skips rows where target column already has a valid translation.

Usage:
    # First run — translates all rows, creates output file
    python3 translate_csv.py --input <path> --target-lang <lang>

    # Rerun — clears the target column and retranslates everything from scratch
    python3 translate_csv.py --input <path> --target-lang <lang> --rerun

    # Rerun writing back to the same file (in-place refresh)
    python3 translate_csv.py --input <path> --target-lang <lang> --rerun --output <same-path>

    # Force batch mode for subtitle content (faster but no cross-segment context)
    python3 translate_csv.py --input <path> --target-lang <lang> --batch

Examples:
    python3 translate_csv.py --input "Test Case/Testing Output/English/explain_eng.csv" --target-lang tw
    python3 translate_csv.py --input "Test Case/Testing Output/English/sub-50-eng.csv" --target-lang tw
    python3 translate_csv.py --input "Test Case/Testing Output/English/sub-50-eng.csv" --target-lang th
    python3 translate_csv.py --input "Test Case/Testing Output/English/ui_eng.csv" --target-lang tw --rerun

---
NOTES — lessons learned from past translation runs
---

1. Bilingual gloss leaking (course_subtitle)
   Symptom: output contained "word（翻譯）" style glosses even with vocab_mode=preserve.
   Cause:   pipeline auto-detection sometimes ignored vocab_mode and produced bilingual output.
   Fix:     context string now explicitly says "Output target language ONLY — do NOT use
            bilingual gloss format". Always keep this line in any subtitle/pedagogical context.

2. Negation dropped (course_subtitle)
   Symptom: "This course isn't meant to cover X" → "本課程旨在涵蓋 X" (meaning reversed).
   Cause:   pipeline dropped the negation during revision stage. Non-deterministic — occurs in
            roughly 2 of 3 runs with no parameter change. Context-string instruction reduces
            but does not fully eliminate this. Requires a pipeline-side validation fix.
   Fix:     context string says "Preserve all negations and sentence meaning precisely".
            If negation is still dropped after retranslation, flag for manual correction.

3. Grammar meta-term vs teaching token distinction (course_subtitle)
   Symptom: grammar terms (nouns, verbs) left in English even though target equivalents exist.
   Cause:   teaching_lang=English causes a blanket English-preservation rule in the pipeline.
            The rule is correct for teaching tokens (e.g. {{Past Perfect}}) but wrong for
            grammar meta-terms. Context string partially overrides this but is inconsistent.
   Fix:     context string explicitly lists grammar meta-terms that MUST be translated.
            Course names and method names (Basic Grammar, Guided Discovery) stay in Latin
            script. Long-term fix requires a translate_terms API parameter (escalated).

4. FALLBACK_ORIGINAL — pipeline crash / backend 503
   Symptom: translated column contains the original English source text unchanged.
            API response has source_model="FALLBACK_ORIGINAL" and a pipeline_exception warning.
   Cause:   the Qwen backend returned 503 for all attempts; pipeline gave up and echoed source.
   Fix:     translate_single retries with increasing wait (15s, 30s, 45s… up to 60s).
            translate_batch_chunk collects all fallback items, waits 15s, then retries as a
            mini-batch. Only items that fail the mini-batch retry fall back to single.
            If rows still show [FAILED] after a run, just re-run — resume logic retries them.

5. Large batch timeouts
   Symptom: items past position ~14 in a batch come back as FALLBACK_ORIGINAL.
   Cause:   the batch endpoint processes items sequentially; 50-item batches can exceed the
            server's pipeline timeout for some languages.
   Fix:     BATCH_SIZE reduced to 25. Adjust lower if timeouts recur.

6. Split-sentence fragment errors (course_subtitle)
   Symptom: subtitle segments that grammatically continue the previous segment are mistranslated
            as standalone sentences (e.g. "from traditional grammar classes." → wrong meaning).
   Cause:   /translate/batch treats every item independently — no cross-item context.
   Fix:     course_subtitle uses single translate (/translate) by default. Each segment is
            translated with prev_segment and next_segment so the model can resolve sentence
            boundaries. Use --batch to override back to batch mode if speed matters more.

7. Thai register errors (course_subtitle, th target)
   Symptom: ค่ะ on sentence fragments; มัน used as "it"; overly formal/literary vocabulary.
   Cause:   no register brief in the prompt; model makes arbitrary register choices.
   Fix:     CONTEXT_ADDITIONS["course_subtitle"]["th"] injects Thai-specific register rules.
            speaker parameter set for Thai subtitle calls (female teacher, adult).
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import requests

API_BASE = "https://translate.flowb.ai"
API_KEY = "tw-localizer-dev-a1b2c3d4e5f6"
DEFAULT_TIMEOUT = 240  # seconds per request

# Target language mapping (user key → API target_lang)
TARGET_LANG_MAP = {
    "tw": "zhTW",
    "tw2": "zhTW",
    "cn": "zhCN",
    "cn2": "zhCN",
    "id": "id",
    "jp": "ja",
    "kr": "ko",
    "kr2": "ko",
    "th": "th",
    "vi": "vi",
    "pt": "pt",
    "es": "esES",
    "mx": "esMX",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "ru": "ru",
}

# File type presets — auto-detected by checking that all base columns are present in the CSV.
PRESETS = [
    {
        "name": "answer_explanation",
        "columns": ["id", "explain_eng", "explain_tw"],
        "unique_key": "id",
        "source_col": "explain_eng",
        "target_col_template": "explain_{lang_key}",
        "content_type": "subtitle",
        "intent": "pedagogical",
        "teaching_lang": "English",
        "context": (
            "IELTS answer explanation for language learners. "
            "Contains English teaching keywords in {{double braces}} that must be preserved verbatim. "
            "Logical connectors like ⇒, =, and answer labels like TRUE/FALSE/NOT GIVEN must be kept."
        ),
    },
    {
        "name": "course_subtitle",
        "columns": ["lesson", "segment", "timestamp", "source"],
        "unique_key": ("lesson", "segment"),
        "source_col": "source",
        "target_col_template": "target_{lang_key}",
        "content_type": "subtitle",
        "intent": "pedagogical",
        "teaching_lang": "English",
        "context": (
            "Course subtitles from an English-language lesson video for language learners. "
            "Output target language ONLY — do NOT use bilingual gloss format "
            "(e.g. word (翻譯) or word（翻譯）). "
            "Translate all grammar meta-terms into the target language "
            "(e.g. nouns=名詞, verbs=動詞, adjectives=形容詞, adverbs=副詞, pronouns=代名詞, "
            "prepositions=介系詞, grammar rules=文法規則, sentence structure=句型結構, "
            "parts of speech=詞性). "
            "Course names and method names (Basic Grammar, Basic Vocabulary, Guided Discovery) "
            "stay in Latin script. "
            "Preserve all negations and sentence meaning precisely. "
            "Preserve any {{double braces}} content verbatim. "
            "Keep translations natural and concise for video subtitles."
        ),
    },
    {
        "name": "ui",
        "columns": ["key", "english content", "tw content"],
        "unique_key": "key",
        "source_col": "english content",
        "target_col_template": "{lang_key} content",
        "content_type": "ui_button",
        "intent": "transcreation_ux",
        "teaching_lang": None,  # UI strings are not English-teaching content
        "context": (
            "UI text for an online educational platform. "
            "Keep translation concise and natural, suitable for buttons, headings, "
            "form labels, and notices. "
            "Preserve any {{double braces}} content verbatim."
        ),
    },
]

BATCH_SIZE = 25  # items per /translate/batch request

# speaker defaults per language for subtitle/explanation content.
# Controls polite particle selection (ค่ะ/ครับ for Thai) and register.
SPEAKER_DEFAULTS = {
    "th": {"gender": "female", "role": "teacher", "age_band": "adult"},
}

# Additional context injected per preset + language — used to add language-specific
# register and cultural rules without bloating the shared context string.
CONTEXT_ADDITIONS = {
    "course_subtitle": {
        "th": (
            " Thai register: "
            "ค่ะ at sentence-end only — never on fragments or mid-sentence segments. "
            "Prohibited: มัน (not 'it'), ศิษย์, กอร์ส, ท่าน, ชอปปิง. "
            "Use นักเรียน/ผู้เรียน for 'student'. "
            "Localise discourse markers to natural Thai classroom equivalents, not literal. "
            "Active voice only. Restructure for Thai topic-comment order."
        ),
    },
}


def _post_with_retry(endpoint: str, payload: dict, timeout: int, max_retries: int) -> dict:
    """POST to API with 503 retry and timeout backoff. Returns parsed JSON."""
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{API_BASE}{endpoint}",
                headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 503:
                try:
                    detail = resp.json().get("detail", "")
                    retry_after = int(detail.split("Retry after ")[-1].rstrip("s. "))
                except Exception:
                    retry_after = 10
                wait = retry_after + 2
                print(f"  Server busy, waiting {wait}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
            wait_time = min(2 ** attempt * 10, 60)
            print(f"  Timeout, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            print(f"  Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                raise
    return {}


def translate_single(
    text: str,
    target_lang: str = "zhTW",
    teaching_lang: str | None = "English",
    content_type: str = "subtitle",
    domain: str = "education",
    intent: str = "pedagogical",
    vocab_mode: str = "preserve",
    context: str = "",
    prev_segment: str = "",
    next_segment: str = "",
    speaker: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 10,
) -> str:
    """Translate a single text using API v11."""
    payload: dict = {
        "text": text,
        "source_lang": "en",
        "target_lang": target_lang,
        "content_type": content_type,
        "domain": domain,
        "intent": intent,
        "vocab_mode": vocab_mode,
        "context": context,
        "no_cache": True,
    }
    if teaching_lang:
        payload["teaching_lang"] = teaching_lang
    if prev_segment:
        payload["prev_segment"] = prev_segment
    if next_segment:
        payload["next_segment"] = next_segment
    if speaker:
        payload["speaker"] = speaker

    for attempt in range(max_retries):
        result = _post_with_retry("/translate", payload, timeout, 1)
        if "error" in result:
            print(f"  [warn] API error: {result['error']}", file=sys.stderr)
            return ""
        if result.get("source_model") == "FALLBACK_ORIGINAL":
            wait = min(15 * (attempt + 1), 60)
            print(
                f"  [warn] pipeline crash (backend 503) — waiting {wait}s before retry "
                f"({attempt + 1}/{max_retries})",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue
        return result.get("translation", "")
    return ""


def translate_batch_chunk(
    texts: list[str],
    target_lang: str = "zhTW",
    teaching_lang: str | None = "English",
    content_type: str = "subtitle",
    domain: str = "education",
    intent: str = "pedagogical",
    vocab_mode: str = "preserve",
    context: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 10,
) -> tuple[list[str], bool]:
    """Translate up to BATCH_SIZE texts in one /translate/batch call.

    Note: batch mode does not support per-item prev_segment/next_segment.
    For subtitle content, use single translate mode (the default) instead.
    """
    assert len(texts) <= BATCH_SIZE

    def _make_payload(batch_texts: list[str]) -> dict:
        p: dict = {
            "texts": batch_texts,
            "source_lang": "en",
            "target_lang": target_lang,
            "content_type": content_type,
            "domain": domain,
            "intent": intent,
            "vocab_mode": vocab_mode,
            "context": context,
            "no_cache": True,
        }
        if teaching_lang:
            p["teaching_lang"] = teaching_lang
        return p

    def _is_fallback(item: dict, source_text: str) -> bool:
        translation = item.get("translation", "")
        warnings = item.get("warnings", [])
        return (
            "error" in item
            or "FALLBACK_ORIGINAL" in str(warnings)
            or translation == source_text
        )

    result = _post_with_retry("/translate/batch", _make_payload(texts), timeout, max_retries)
    items = result.get("results", [])
    while len(items) < len(texts):
        items.append({})

    fallback_indices = [i for i, item in enumerate(items) if _is_fallback(item, texts[i])]
    had_fallbacks = bool(fallback_indices)

    if fallback_indices:
        print(
            f"  [warn] {len(fallback_indices)} item(s) fallback — waiting 15s then retrying as mini-batch",
            file=sys.stderr,
        )
        time.sleep(15)
        retry_texts = [texts[i] for i in fallback_indices]
        retry_result = _post_with_retry(
            "/translate/batch", _make_payload(retry_texts), timeout, max_retries
        )
        retry_items = retry_result.get("results", [])
        while len(retry_items) < len(retry_texts):
            retry_items.append({})

        for list_pos, original_idx in enumerate(fallback_indices):
            retry_item = retry_items[list_pos]
            if not _is_fallback(retry_item, texts[original_idx]):
                items[original_idx] = retry_item
            else:
                print(
                    f"  [warn] mini-batch retry failed for item {original_idx} — retrying single",
                    file=sys.stderr,
                )
                translation = translate_single(
                    texts[original_idx],
                    target_lang=target_lang,
                    teaching_lang=teaching_lang,
                    content_type=content_type,
                    domain=domain,
                    intent=intent,
                    vocab_mode=vocab_mode,
                    context=context,
                    timeout=timeout,
                    max_retries=max_retries,
                )
                items[original_idx] = {"translation": translation}

    translations = [item.get("translation", "") for item in items]
    return translations, had_fallbacks


def load_existing(path: Path, unique_key) -> dict:
    """Return {unique_key: row_data} from existing output file."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        existing = {}
        for row in reader:
            if isinstance(unique_key, tuple):
                key = "_".join(row[k] for k in unique_key)
            else:
                key = row[unique_key]
            existing[key] = row
        return existing


def save_all(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def detect_preset(fieldnames: list[str]) -> dict | None:
    """Return the first preset whose required columns are all present in fieldnames."""
    for p in PRESETS:
        if all(col in fieldnames for col in p["columns"]):
            return p
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Translate CSV files for educational content.")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument(
        "--target-lang",
        required=True,
        choices=list(TARGET_LANG_MAP.keys()),
        help="Target language code",
    )
    parser.add_argument("--output", help="Output path (default: <lang>_<input>.csv next to input)")
    parser.add_argument(
        "--target-col",
        help="Column name to write translations into (default: auto from preset)",
    )
    parser.add_argument(
        "--preset",
        choices=["explanation", "subtitle", "ui"],
        help="Force a content preset (auto-detected if omitted)",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Clear the target column and retranslate all rows from scratch",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help=(
            "Force batch mode for subtitle content "
            "(faster but no cross-segment context — use only if speed matters more than quality)"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file {input_path} not found.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    preset_map = {"explanation": "answer_explanation", "subtitle": "course_subtitle", "ui": "ui"}
    if args.preset:
        preset_name = preset_map[args.preset]
        preset = next((p for p in PRESETS if p["name"] == preset_name), None)
        if not preset:
            print(f"Error: Unknown preset '{args.preset}'")
            sys.exit(1)
    else:
        preset = detect_preset(fieldnames)
        if not preset:
            print(f"Error: Could not auto-detect preset from columns: {fieldnames}")
            print("Pass --preset explicitly. Supported presets:")
            for p in PRESETS:
                print(f"  {p['name']}: requires columns {p['columns']}")
            sys.exit(1)
        print(f"Auto-detected preset: {preset['name']}")

    lang_key = args.target_lang
    api_target_lang = TARGET_LANG_MAP[lang_key]
    source_col = preset["source_col"]
    target_col = (
        args.target_col
        if args.target_col
        else preset["target_col_template"].format(lang_key=lang_key)
    )
    unique_key = preset["unique_key"]

    # Resolve per-language context addition and speaker
    context_addition = CONTEXT_ADDITIONS.get(preset["name"], {}).get(lang_key, "")
    full_context = preset["context"] + context_addition
    speaker = SPEAKER_DEFAULTS.get(lang_key) if preset["name"] != "ui" else None

    if target_col not in fieldnames:
        fieldnames.append(target_col)
        for row in rows:
            row[target_col] = ""

    output_path = Path(args.output) if args.output else input_path.parent / f"{lang_key}_{input_path.stem}.csv"

    if args.rerun:
        print(f"--rerun: clearing {target_col} for all {len(rows)} rows...")
        for row in rows:
            row[target_col] = ""
        save_all(output_path, fieldnames, rows)
    else:
        existing = load_existing(output_path, unique_key)
        for row in rows:
            row_key = (
                "_".join(row[k] for k in unique_key)
                if isinstance(unique_key, tuple)
                else row[unique_key]
            )
            saved_target = existing.get(row_key, {}).get(target_col, "")
            if saved_target and saved_target != row[source_col]:
                row[target_col] = saved_target

    pending = [
        row for row in rows
        if not row.get(target_col) or row[target_col] == row[source_col]
    ]
    skipped = len(rows) - len(pending)
    if skipped:
        print(f"Resuming: {skipped} already translated, {len(pending)} remaining.")
    if not pending:
        print("All rows already translated.")
        return

    # course_subtitle defaults to single so each segment gets prev_segment/next_segment.
    # All other presets default to batch. Pass --batch to force batch mode for subtitles.
    use_batch = args.batch or preset["name"] != "course_subtitle"

    mode = (
        "batch (/translate/batch)"
        if use_batch
        else "single (/translate, with prev_segment/next_segment)"
    )
    if speaker:
        mode += f" | speaker={speaker}"
    print(f"Translating {len(pending)} rows → {lang_key} ({api_target_lang})")
    print(f"Preset: {preset['name']}  |  intent: {preset['intent']}  |  Mode: {mode}")
    print(f"Output: {output_path}")

    translated_count = 0

    if use_batch:
        chunks = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
        done = 0
        for chunk in chunks:
            texts = [r[source_col] for r in chunk]
            print(f"[{done + 1}–{done + len(chunk)}/{len(pending)}] sending batch of {len(chunk)}...")
            had_fallbacks = False
            try:
                translations, had_fallbacks = translate_batch_chunk(
                    texts=texts,
                    target_lang=api_target_lang,
                    teaching_lang=preset["teaching_lang"],
                    content_type=preset["content_type"],
                    domain="education",
                    intent=preset["intent"],
                    context=full_context,
                )
            except Exception as e:
                print(f"  [batch FAILED] {e} — falling back to single for this chunk", file=sys.stderr)
                had_fallbacks = True
                translations = []
                for text in texts:
                    try:
                        translations.append(
                            translate_single(
                                text=text,
                                target_lang=api_target_lang,
                                teaching_lang=preset["teaching_lang"],
                                content_type=preset["content_type"],
                                intent=preset["intent"],
                                context=full_context,
                                speaker=speaker,
                            )
                        )
                    except Exception as e2:
                        print(f"  [FAILED] {e2}", file=sys.stderr)
                        translations.append("")

            for row, translation in zip(chunk, translations):
                row[target_col] = translation
                if translation and translation != row[source_col]:
                    translated_count += 1
                    print(f"  -> {translation[:80]}...")
                else:
                    print("  [FAILED]")

            done += len(chunk)
            save_all(output_path, fieldnames, rows)
            if done < len(pending):
                inter_chunk_sleep = 15 if had_fallbacks else 3
                if had_fallbacks:
                    print(f"  [cooldown] fallbacks — waiting {inter_chunk_sleep}s before next batch")
                time.sleep(inter_chunk_sleep)

    else:
        # Single translate with prev_segment/next_segment for cross-segment continuity.
        for i, row in enumerate(pending):
            row_key = (
                "_".join(row[k] for k in unique_key)
                if isinstance(unique_key, tuple)
                else row[unique_key]
            )
            print(f"[{i + 1}/{len(pending)}] {row_key}: {row[source_col][:80]}...")

            prev_source = pending[i - 1][source_col] if i > 0 else ""
            next_source = pending[i + 1][source_col] if i < len(pending) - 1 else ""

            try:
                translation = translate_single(
                    text=row[source_col],
                    target_lang=api_target_lang,
                    teaching_lang=preset["teaching_lang"],
                    content_type=preset["content_type"],
                    domain="education",
                    intent=preset["intent"],
                    context=full_context,
                    prev_segment=prev_source,
                    next_segment=next_source,
                    speaker=speaker,
                )
            except Exception as e:
                print(f"  [FAILED after all retries] {e}", file=sys.stderr)
                translation = ""

            row[target_col] = translation
            if translation and translation != row[source_col]:
                translated_count += 1
                print(f"  -> {translation[:80]}...")
            else:
                print("  [FAILED]")

            save_all(output_path, fieldnames, rows)
            if i < len(pending) - 1:
                time.sleep(3)

    print(f"\nDone. Output: {output_path}")
    print(f"Translated {translated_count}/{len(pending)} rows in this run.")
    failed = len(pending) - translated_count
    if failed:
        print(f"  {failed} row(s) failed — re-run the script to retry them.")


if __name__ == "__main__":
    main()
