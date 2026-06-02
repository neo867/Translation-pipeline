#!/usr/bin/env python3
from __future__ import annotations
"""
review_srt.py — Score a translated SRT file via Translation API V11 /review/batch.

Pairs each block from the source SRT with the matching block in the translated SRT,
scores them, and writes a CSV report with: block, timestamp, source, translation,
score, verdict, corrected, issues.

Auto-detects the translated file from output/ if not specified.

Usage:
    python3 scripts/review_srt.py "IE Intermediate 2.6/Listening Int/L1S1.srt" --target zhTW
    python3 scripts/review_srt.py source.srt --translated output/zhTW_source.srt --target zhTW
    python3 scripts/review_srt.py source.srt --target zhTW --context "IELTS course" --strictness linguist
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests

API_BASE = "https://translate.flowb.ai"
API_KEY = "tw-localizer-dev-a1b2c3d4e5f6"
DEFAULT_TIMEOUT = 240
BATCH_SIZE = 50  # /review/batch max is 50

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

TARGET_LANG_MAP = {
    "zhTW": "zhTW", "zhCN": "zhCN",
    "ko": "ko", "vi": "vi", "id": "id", "th": "th", "ja": "ja",
    "pt": "pt", "esES": "esES", "esMX": "esMX",
    "fr": "fr", "de": "de", "it": "it", "ru": "ru",
}

CONTEXT_DEFAULT = (
    "Course subtitles from an English-language lesson video for language learners. "
    "English course names and grammar terminology stay in Latin script. "
    "Preserve all negations and sentence meaning precisely."
)


def parse_srt(text: str) -> dict[int, dict]:
    """Parse SRT into {block_index: {index, timestamp, text}} — text is lines joined."""
    blocks = {}
    for raw in re.split(r"\n\n+", text.strip()):
        parts = raw.strip().splitlines()
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0].strip())
        except ValueError:
            continue
        timestamp = parts[1].strip()
        text_lines = " ".join(line.strip() for line in parts[2:] if line.strip())
        blocks[idx] = {"index": idx, "timestamp": timestamp, "text": text_lines}
    return blocks


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
                try:
                    detail = resp.json().get("detail", "")
                    retry_after = int(detail.split("Retry after ")[-1].rstrip("s. "))
                except Exception:
                    retry_after = 10
                wait = retry_after + 2
                print(f"  Server busy, waiting {wait}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            if resp.status_code == 524:
                wait = 30 * (attempt + 1)
                print(f"  Gateway timeout (524), waiting {wait}s... (attempt {attempt + 1}/{max_retries})")
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


def review_batch_chunk(
    pairs: list[dict],
    target_lang: str,
    context: str,
    strictness: str,
) -> list[dict]:
    payload = {
        "items": pairs,
        "source_lang": "en",
        "target_lang": target_lang,
        "content_type": "subtitle",
        "context": context,
        "strictness": strictness,
    }
    result = _post_with_retry("/review/batch", payload, DEFAULT_TIMEOUT, 10)
    return result.get("results", [])


def find_translated_srt(source_path: Path, target: str) -> Optional[Path]:
    """Auto-detect translated SRT from output/ using same folder-mirror logic as translate_srt.py."""
    try:
        rel_parent = source_path.resolve().relative_to(PROJECT_ROOT.resolve()).parent
    except ValueError:
        rel_parent = Path(".")
    candidate = OUTPUT_DIR / rel_parent / f"{target}_{source_path.name}"
    return candidate if candidate.exists() else None


def main():
    parser = argparse.ArgumentParser(
        description="Review a translated SRT file via API V11 /review/batch.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/review_srt.py "IE Intermediate 2.6/Listening Int/L1S1.srt" --target zhTW
  python3 scripts/review_srt.py source.srt --target zhTW --strictness linguist
  python3 scripts/review_srt.py source.srt --translated output/zhTW_source.srt --target zhTW
""",
    )
    parser.add_argument("source", help="Source (English) .srt file")
    parser.add_argument(
        "--target", "-t", required=True, choices=list(TARGET_LANG_MAP.keys()),
        help="Target language code (e.g. zhTW, ko, vi)"
    )
    parser.add_argument("--translated", help="Translated .srt file (auto-detected from output/ if omitted)")
    parser.add_argument("--context", "-c", default=CONTEXT_DEFAULT, help="Domain context for the reviewer")
    parser.add_argument(
        "--strictness", default="objective",
        choices=["objective", "linguist", "permissive"],
        help="Review strictness (default: objective). 'linguist' also flags unnatural phrasing.",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        source_path = INPUT_DIR / args.source
    if not source_path.exists():
        print(f"Error: source file not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    if args.translated:
        translated_path = Path(args.translated)
    else:
        translated_path = find_translated_srt(source_path, args.target)
        if not translated_path:
            print(
                f"Error: could not find translated file for {args.target}.\n"
                f"Expected: output/.../{args.target}_{source_path.name}\n"
                f"Pass --translated <path> to specify it manually.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Auto-detected translated file: {translated_path}")

    if not translated_path.exists():
        print(f"Error: translated file not found: {translated_path}", file=sys.stderr)
        sys.exit(1)

    source_blocks = parse_srt(source_path.read_text(encoding="utf-8-sig"))
    translated_blocks = parse_srt(translated_path.read_text(encoding="utf-8-sig"))

    # Match by block index — warn if counts differ
    common_indices = sorted(set(source_blocks) & set(translated_blocks))
    source_only = set(source_blocks) - set(translated_blocks)
    translated_only = set(translated_blocks) - set(source_blocks)
    if source_only:
        print(f"  [warn] {len(source_only)} block(s) in source but not in translation — skipping")
    if translated_only:
        print(f"  [warn] {len(translated_only)} block(s) in translation but not in source — skipping")

    pairs_to_review = [
        {
            "block_index": i,
            "timestamp": source_blocks[i]["timestamp"],
            "source": source_blocks[i]["text"],
            "translation": translated_blocks[i]["text"],
        }
        for i in common_indices
        if source_blocks[i]["text"] and translated_blocks[i]["text"]
    ]
    total = len(pairs_to_review)
    print(f"Reviewing {total} pairs ({source_path.name} → {args.target})...")
    print(f"Strictness: {args.strictness}")

    # Output path mirrors input folder structure
    try:
        rel_parent = source_path.resolve().relative_to(PROJECT_ROOT.resolve()).parent
    except ValueError:
        rel_parent = Path(".")
    out_dir = OUTPUT_DIR / rel_parent
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"review_{args.target}_{source_path.stem}.csv"

    # Load existing results for resume
    existing: dict[int, dict] = {}
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    existing[int(row["block"])] = row
                except (KeyError, ValueError):
                    pass
        if existing:
            print(f"  Resuming: {len(existing)} already reviewed.")

    pending = [p for p in pairs_to_review if p["block_index"] not in existing]
    skipped = total - len(pending)
    if skipped:
        print(f"  Skipping {skipped} already reviewed, {len(pending)} remaining.")
    if not pending:
        print("All pairs already reviewed.")
        return

    fieldnames = ["block", "timestamp", "source", "translation", "score", "verdict", "corrected", "issues"]
    results_map: dict[int, dict] = dict(existing)

    done = 0
    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start: start + BATCH_SIZE]
        api_pairs = [{"source": p["source"], "translation": p["translation"]} for p in chunk]
        chunk_start = skipped + done + 1
        chunk_end = skipped + done + len(chunk)
        print(f"[{chunk_start}–{chunk_end}/{total}] scoring batch of {len(chunk)}...")

        try:
            results = review_batch_chunk(api_pairs, TARGET_LANG_MAP[args.target], args.context, args.strictness)
        except Exception as e:
            print(f"  [ERROR] {e}", file=sys.stderr)
            results = [{}] * len(chunk)

        for pair, res in zip(chunk, results):
            issues = res.get("issues", [])
            issue_str = "; ".join(
                f"[{i.get('severity')}] {i.get('category')}: {i.get('message')}"
                for i in issues
            ) if issues else ""
            results_map[pair["block_index"]] = {
                "block": pair["block_index"],
                "timestamp": pair["timestamp"],
                "source": pair["source"],
                "translation": pair["translation"],
                "score": res.get("score", ""),
                "verdict": res.get("verdict", ""),
                "corrected": res.get("corrected") or "",
                "issues": issue_str,
            }

        done += len(chunk)

        # Save progress after each chunk
        sorted_rows = [results_map[i] for i in sorted(results_map)]
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted_rows)

        if done < len(pending):
            time.sleep(2)

    # Summary
    all_results = [results_map[i] for i in sorted(results_map) if results_map[i].get("score") != ""]
    if all_results:
        scores = [int(r["score"]) for r in all_results if str(r["score"]).isdigit()]
        if scores:
            avg = sum(scores) / len(scores)
            rejected = sum(1 for r in all_results if r["verdict"] == "reject")
            warnings = sum(1 for r in all_results if r["verdict"] == "warning")
            print(f"\nAverage score: {avg:.1f}/100")
            print(f"Verdicts — ok: {len(scores) - rejected - warnings}, warning: {warnings}, reject: {rejected}")

    print(f"\nDone. Report saved to:\n  {output_path}")
    if any(str(r.get("score", "")).isdigit() and int(r["score"]) < 70 for r in all_results):
        print("  Note: some segments scored < 70 — check 'corrected' column for suggested fixes.")


if __name__ == "__main__":
    main()
