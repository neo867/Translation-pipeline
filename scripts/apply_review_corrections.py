#!/usr/bin/env python3
"""
apply_review_corrections.py — Apply API review corrections to translated SRT files.

Reads a review CSV (from review_srt.py / batch_review.py), applies any non-empty
`corrected` text to the corresponding translated SRT, and writes a _revised.srt to
the sibling final/ folder.

Usage:
    python3 scripts/apply_review_corrections.py \
        "output/IE Intermediate 2.6/Listening Int/Bahasa/drafts/review_id_L1S1.csv"

    # Multiple files:
    python3 scripts/apply_review_corrections.py \
        "output/.../review_id_L1S1.csv" \
        "output/.../review_id_L2S1.csv"
"""

import argparse
import csv
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent


def parse_srt(text: str) -> list[dict]:
    blocks = []
    for raw in re.split(r"\n\n+", text.strip()):
        parts = raw.strip().splitlines()
        if len(parts) < 3:
            continue
        try:
            index = int(parts[0].strip())
        except ValueError:
            continue
        blocks.append({
            "index": index,
            "timestamp": parts[1].strip(),
            "lines": parts[2:],
        })
    return blocks


def write_srt(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        parts.append(f"{b['index']}\n{b['timestamp']}\n" + "\n".join(b["lines"]))
    return "\n\n".join(parts) + "\n"


def apply_corrections(review_path: Path) -> None:
    # Load corrections: {block_number: corrected_text}
    corrections: dict[int, str] = {}
    with open(review_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            corrected = row.get("corrected", "").strip()
            if corrected:
                try:
                    corrections[int(row["block"])] = corrected
                except (KeyError, ValueError):
                    pass

    if not corrections:
        print(f"  No corrections found — skipping {review_path.name}")
        return

    # Derive translated SRT path from review CSV name: review_id_L1S1.csv -> id_L1S1.srt
    stem = review_path.stem  # e.g. review_id_L1S1
    if stem.startswith("review_"):
        srt_name = stem[len("review_"):] + ".srt"
    else:
        print(f"  [error] unexpected review filename format: {review_path.name}", file=sys.stderr)
        sys.exit(1)

    srt_path = review_path.parent / srt_name
    if not srt_path.exists():
        print(f"  [error] translated SRT not found: {srt_path}", file=sys.stderr)
        sys.exit(1)

    blocks = parse_srt(srt_path.read_text(encoding="utf-8-sig"))

    # Apply corrections
    applied = 0
    for block in blocks:
        if block["index"] in corrections:
            block["lines"] = [corrections[block["index"]]]
            applied += 1

    # Output to sibling final/ folder
    final_dir = review_path.parent.parent / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    out_name = srt_path.stem + "_revised.srt"
    out_path = final_dir / out_name

    out_path.write_text(write_srt(blocks), encoding="utf-8")
    print(f"  {review_path.name}: {applied}/{len(corrections)} corrections applied → {out_path.resolve().relative_to(PROJECT_ROOT.resolve())}")


def main():
    parser = argparse.ArgumentParser(
        description="Apply review corrections to translated SRT files.",
    )
    parser.add_argument("reviews", nargs="+", help="Review CSV file(s) to process")
    args = parser.parse_args()

    for raw in args.reviews:
        path = Path(raw)
        if not path.exists():
            path = PROJECT_ROOT / raw
        if not path.exists():
            print(f"[error] file not found: {raw}", file=sys.stderr)
            sys.exit(1)
        print(f"Processing {path.name}...")
        apply_corrections(path)

    print("\nDone.")


if __name__ == "__main__":
    main()
