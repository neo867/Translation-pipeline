#!/usr/bin/env python3 -u
from __future__ import annotations
"""
batch_review.py — Queue and run reviews for all translated SRT files.

Discovers translated SRTs in output/, pairs each with its source, and reviews
them via /review/batch. Skips files that already have a review CSV.

Usage:
    python3 scripts/batch_review.py
    python3 scripts/batch_review.py --target zhTW
    python3 scripts/batch_review.py --folder "IE Intermediate 2.6/Listening Int"
    python3 scripts/batch_review.py --force
    python3 scripts/batch_review.py --dry-run
    python3 scripts/batch_review.py --strictness linguist
"""

import argparse
import csv
import sys
import time
from pathlib import Path

# Re-use helpers from review_srt.py
sys.path.insert(0, str(Path(__file__).parent))
from review_srt import (
    parse_srt,
    review_batch_chunk,
    TARGET_LANG_MAP,
    CONTEXT_DEFAULT,
    BATCH_SIZE,
)

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# Longest prefixes first so "zhTW" matches before a hypothetical "zh"
KNOWN_LANGS = sorted(TARGET_LANG_MAP.keys(), key=len, reverse=True)


def detect_lang(filename: str) -> tuple[str, str] | None:
    """Return (lang_code, source_filename) if filename starts with a known lang prefix."""
    for lang in KNOWN_LANGS:
        prefix = f"{lang}_"
        if filename.startswith(prefix):
            return lang, filename[len(prefix):]
    return None


def discover_queue(target_filter: str | None, folder_filter: str | None) -> list[dict]:
    """Walk output/ and build a list of review jobs."""
    queue = []
    for translated_path in sorted(OUTPUT_DIR.rglob("*.srt")):
        detected = detect_lang(translated_path.name)
        if not detected:
            continue
        lang, source_name = detected

        if target_filter and lang != target_filter:
            continue

        # Reconstruct source path (mirror output/ structure back to project root)
        rel_dir = translated_path.parent.relative_to(OUTPUT_DIR)
        source_path = PROJECT_ROOT / rel_dir / source_name

        if folder_filter:
            norm = str(rel_dir).replace("\\", "/")
            if folder_filter.rstrip("/") not in norm:
                continue

        # If exact mirror path doesn't exist, walk up the tree to find the source file
        if not source_path.exists():
            parts = rel_dir.parts
            found = None
            for i in range(len(parts) - 1, 0, -1):
                candidate = PROJECT_ROOT / Path(*parts[:i]) / source_name
                if candidate.exists():
                    found = candidate
                    break
            if found:
                source_path = found
            else:
                continue  # translated file exists but source was moved/renamed

        review_path = translated_path.parent / f"review_{lang}_{source_path.stem}.csv"

        queue.append({
            "source": source_path,
            "translated": translated_path,
            "lang": lang,
            "review_out": review_path,
            "done": review_path.exists(),
        })

    return queue


def review_file(source_path: Path, translated_path: Path, lang: str,
                output_path: Path, context: str, strictness: str) -> dict:
    """Review one source+translation pair; save CSV; return summary stats."""
    source_blocks = parse_srt(source_path.read_text(encoding="utf-8-sig"))
    translated_blocks = parse_srt(translated_path.read_text(encoding="utf-8-sig"))

    common = sorted(set(source_blocks) & set(translated_blocks))
    source_only = set(source_blocks) - set(translated_blocks)
    translated_only = set(translated_blocks) - set(source_blocks)
    if source_only:
        print(f"  [warn] {len(source_only)} source block(s) not in translation — skipped")
    if translated_only:
        print(f"  [warn] {len(translated_only)} translation block(s) not in source — skipped")

    pairs = [
        {
            "block_index": i,
            "timestamp": source_blocks[i]["timestamp"],
            "source": source_blocks[i]["text"],
            "translation": translated_blocks[i]["text"],
        }
        for i in common
        if source_blocks[i]["text"] and translated_blocks[i]["text"]
    ]
    total = len(pairs)

    # Resume support
    existing: dict[int, dict] = {}
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    existing[int(row["block"])] = row
                except (KeyError, ValueError):
                    pass
        if existing:
            print(f"  Resuming: {len(existing)}/{total} already scored.")

    pending = [p for p in pairs if p["block_index"] not in existing]
    if not pending:
        print("  All blocks already reviewed — skipping.")
        return _summarise(existing)

    fieldnames = ["block", "timestamp", "source", "translation", "score", "verdict", "corrected", "issues"]
    results_map: dict[int, dict] = dict(existing)

    done = 0
    skipped = total - len(pending)
    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start: start + BATCH_SIZE]
        api_pairs = [{"source": p["source"], "translation": p["translation"]} for p in chunk]
        lo, hi = skipped + done + 1, skipped + done + len(chunk)
        print(f"  [{lo}–{hi}/{total}] scoring...")

        try:
            results = review_batch_chunk(api_pairs, TARGET_LANG_MAP[lang], context, strictness)
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

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results_map[i] for i in sorted(results_map))

        if done < len(pending):
            time.sleep(2)

    return _summarise(results_map)


def _summarise(results_map: dict) -> dict:
    rows = [r for r in results_map.values() if str(r.get("score", "")).isdigit()]
    if not rows:
        return {"avg": None, "ok": 0, "warning": 0, "reject": 0, "total": 0}
    scores = [int(r["score"]) for r in rows]
    verdicts = [r.get("verdict", "") for r in rows]
    return {
        "avg": sum(scores) / len(scores),
        "ok": verdicts.count("ok"),
        "warning": verdicts.count("warning"),
        "reject": verdicts.count("reject"),
        "total": len(scores),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Review all translated SRT files in output/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/batch_review.py
  python3 scripts/batch_review.py --target zhTW
  python3 scripts/batch_review.py --folder "IE Intermediate 2.6/Listening Int"
  python3 scripts/batch_review.py --dry-run
  python3 scripts/batch_review.py --force --strictness linguist
""",
    )
    parser.add_argument("--target", "-t", choices=list(TARGET_LANG_MAP.keys()),
                        help="Only review files for this language (e.g. zhTW)")
    parser.add_argument("--folder", "-f", help="Only review files under this subfolder of output/")
    parser.add_argument("--force", action="store_true", help="Re-review even if review CSV already exists")
    parser.add_argument("--dry-run", action="store_true", help="Print queue without running reviews")
    parser.add_argument("--strictness", default="objective",
                        choices=["objective", "linguist", "permissive"],
                        help="Review strictness (default: objective)")
    parser.add_argument("--context", default=CONTEXT_DEFAULT, help="Domain context for reviewer")
    args = parser.parse_args()

    queue = discover_queue(args.target, args.folder)

    if not queue:
        print("No translated SRT files found matching your filters.")
        sys.exit(0)

    pending = [j for j in queue if not j["done"] or args.force]
    already_done = len(queue) - len(pending)

    print(f"Queue: {len(queue)} file(s) — {len(pending)} to review, {already_done} already done")
    print()

    for j in queue:
        status = "DONE" if j["done"] and not args.force else "QUEUE"
        rel = j["translated"].relative_to(OUTPUT_DIR)
        print(f"  [{status}] {rel}")
    print()

    if args.dry_run:
        print("Dry run — exiting.")
        return

    if not pending:
        print("Nothing to do.")
        return

    summaries = []
    for idx, job in enumerate(pending, 1):
        rel = job["translated"].relative_to(OUTPUT_DIR)
        print(f"[{idx}/{len(pending)}] {rel}")
        stats = review_file(
            job["source"], job["translated"], job["lang"],
            job["review_out"], args.context, args.strictness,
        )
        if stats["avg"] is not None:
            print(f"  Score: {stats['avg']:.1f} | ok={stats['ok']} warn={stats['warning']} reject={stats['reject']}")
            print(f"  Saved: {job['review_out'].relative_to(PROJECT_ROOT)}")
        summaries.append({"file": str(rel), **stats})
        print()

    # Final summary table
    scored = [s for s in summaries if s["avg"] is not None]
    if scored:
        print("=" * 60)
        print(f"{'File':<40} {'Avg':>5}  {'ok':>4}  {'warn':>4}  {'rej':>4}")
        print("-" * 60)
        for s in scored:
            name = s["file"][-40:] if len(s["file"]) > 40 else s["file"]
            print(f"{name:<40} {s['avg']:>5.1f}  {s['ok']:>4}  {s['warning']:>4}  {s['reject']:>4}")
        overall_scores = [s["avg"] for s in scored]
        print("-" * 60)
        print(f"{'TOTAL':<40} {sum(overall_scores)/len(overall_scores):>5.1f}")
        print("=" * 60)


if __name__ == "__main__":
    main()
