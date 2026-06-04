#!/usr/bin/env python3
from __future__ import annotations

"""
review_csv.py — Review CSV translations via Translation API V11 (Pipeline V10).

Scores translations against the Qwen 3.6-35B model.
Appends review columns: score, verdict, corrected, issues.

Usage:
    python3 scripts/review_csv.py --input "Review Report/tw_milo-sub-source.csv" --target-lang tw
"""

import argparse
import csv
import sys
import time
import json
from pathlib import Path
import requests

API_BASE = "https://translate.flowb.ai"
API_KEY = "tw-localizer-dev-a1b2c3d4e5f6"
DEFAULT_TIMEOUT = 240
BATCH_SIZE = 50  # Review batch size max is 50

TARGET_LANG_MAP = {
    "tw": "zhTW", "tw2": "zhTW", "cn": "zhCN", "cn2": "zhCN",
    "id": "id", "jp": "ja", "kr": "ko", "kr2": "ko",
    "th": "th", "vi": "vi", "pt": "pt", "es": "esES",
    "mx": "esMX", "fr": "fr", "de": "de", "it": "it", "ru": "ru",
}

PRESETS = [
    {
        "name": "answer_explanation",
        "columns": ["id", "explain_eng"],
        "source_col": "explain_eng",
        "target_col_template": "explain_{lang_key}",
        "content_type": "subtitle",
        "context": "IELTS answer explanation for language learners. Contains English teaching keywords in {{double braces}} that must be preserved verbatim. Logical connectors like ⇒, =, and answer labels like TRUE/FALSE/NOT GIVEN must be kept.",
    },
    {
        "name": "course_subtitle",
        "columns": ["lesson", "segment", "timestamp", "source"],
        "source_col": "source",
        "target_col_template": "target_{lang_key}",
        "content_type": "subtitle",
        "context": "Course subtitles from an English-language lesson video for language learners. Output target language ONLY — do NOT use bilingual gloss format. English course names and grammar terminology must stay in Latin script. Preserve all negations and sentence meaning precisely. Preserve any {{double braces}} content verbatim. Keep translations natural and concise for video subtitles.",
    },
    {
        "name": "ui",
        "columns": ["key", "english content"],
        "source_col": "english content",
        "target_col_template": "{lang_key} content",
        "content_type": "ui_button",
        "context": "UI text for educational platform. Keep translation concise, suitable for buttons, headings, form labels, and notices. Preserve any {{double braces}} content verbatim.",
    },
]

def detect_preset(fieldnames: list[str]) -> dict | None:
    for p in PRESETS:
        if all(col in fieldnames for col in p["columns"]):
            return p
    return None

def _post_with_retry(endpoint: str, payload: dict, timeout: int, max_retries: int) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{API_BASE}{endpoint}",
                headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 503:
                wait = 10 + attempt * 5
                print(f"  Server busy, waiting {wait}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
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

def review_batch_chunk(
    pairs: list[dict], target_lang: str, content_type: str, context: str
) -> list[dict]:
    payload = {
        "items": pairs,
        "source_lang": "en",
        "target_lang": target_lang,
        "content_type": content_type,
        "context": context,
        "strictness": "objective",
    }
    result = _post_with_retry("/review/batch", payload, DEFAULT_TIMEOUT, 10)
    return result.get("results", [])

def main():
    parser = argparse.ArgumentParser(description="Review translated CSV files via API v11.")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument("--target-lang", required=True, choices=list(TARGET_LANG_MAP.keys()), help="Target language")
    parser.add_argument("--target-col", help="Column name containing translations (default: auto from preset)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    preset = detect_preset(fieldnames)
    if not preset:
        print(f"Error: Could not auto-detect preset from columns: {fieldnames}")
        sys.exit(1)
    
    api_target_lang = TARGET_LANG_MAP[args.target_lang]
    source_col = preset["source_col"]
    target_col = args.target_col if args.target_col else preset["target_col_template"].format(lang_key=args.target_lang)

    if source_col not in fieldnames or target_col not in fieldnames:
        print(f"Error: Required columns '{source_col}' and '{target_col}' not found.")
        sys.exit(1)

    # Add review columns
    review_cols = ["review_score", "review_verdict", "review_corrected", "review_issues"]
    for col in review_cols:
        if col not in fieldnames:
            fieldnames.append(col)

    output_path = input_path.parent / f"reviewed_{input_path.name}"
    print(f"Reviewing {len(rows)} rows -> {output_path}")

    chunks = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    done = 0

    for chunk in chunks:
        pairs = []
        for r in chunk:
            pairs.append({"source": r.get(source_col, ""), "translation": r.get(target_col, "")})
        
        print(f"[{done + 1}–{done + len(chunk)}/{len(rows)}] scoring batch...")
        try:
            results = review_batch_chunk(
                pairs, api_target_lang, preset["content_type"], preset["context"]
            )
        except Exception as e:
            print(f"  [ERROR] {e}")
            results = [{}] * len(chunk)

        for row, res in zip(chunk, results):
            row["review_score"] = res.get("score", "")
            row["review_verdict"] = res.get("verdict", "")
            row["review_corrected"] = res.get("corrected", "") or ""
            
            issues = res.get("issues", [])
            if issues:
                row["review_issues"] = "; ".join([f"[{i.get('severity')}] {i.get('category')}: {i.get('message')}" for i in issues])
            else:
                row["review_issues"] = ""

        done += len(chunk)
        
        # Save progress
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        if done < len(rows):
            time.sleep(2)

    print(f"Done! Reviewed file saved to {output_path}")

if __name__ == "__main__":
    main()
