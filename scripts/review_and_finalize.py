#!/usr/bin/env python3
"""
review_and_finalize.py — Review translated SRT files and apply corrections in one pass.

Combines step 2 (batch_review) and step 4 (apply corrections) without a human review step.
API-suggested corrections are applied directly to produce _revised.srt files.
Skips files whose _revised.srt already exists in final/ unless --force is used.

For zhTW: automatically applies mechanical fixes (IELTS→雅思, 您→你, 『』→「」) to the
draft before review, and uses an enriched context covering naturalness rules.

Usage:
    python3 scripts/review_and_finalize.py --target zhTW
    python3 scripts/review_and_finalize.py --target zhTW --folder "IE Intermediate 2.6/Listening Int"
    python3 scripts/review_and_finalize.py --target id --folder "IE Intermediate 2.6/Listening Int"
    python3 scripts/review_and_finalize.py --dry-run
    python3 scripts/review_and_finalize.py --force
"""

import argparse
import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
sys.path.insert(0, str(SCRIPT_DIR))

from batch_review import discover_queue, review_file
from apply_review_corrections import parse_srt, write_srt
from review_srt import CONTEXT_DEFAULT, TARGET_LANG_MAP
from zhTW_mechanical_fix import apply_rule1_ielts, apply_rule2_nin, apply_rule7_quotes

ZHTW_CONTEXT = (
    "Course subtitles from an English-language IELTS lesson video for Taiwanese learners. "
    "Rules: (1) IELTS → 雅思 except in formal tier names like 'IELTS Academic' or 'IELTS General Training'. "
    "(2) Instructor addresses students using 你, not 您. "
    "(3) Natural spoken Taiwanese Mandarin — avoid stiff sentence endings (ending with 的 that feel abrupt, "
    "overly formal 然而/因此 — prefer 不過/所以 in speech). "
    "Rewrite overly literal constructions: 在…之前 chains, 關於…的… double-noun stacks, 進行… → direct verb. "
    "Prefer colloquial word choices: 拿到 over 獲得 for scores, 扎實 over 徹底 for practice, "
    "聽 over 聆聽, 說話者 over 講者, 同義改寫 for paraphrasing. "
    "(4) Keep English grammar terms, accent names (British/American/Australian English), "
    "and score bands (Band 6, B1/B2, CEFR) in English. "
    "Preserve all negations precisely. "
    "(5) Flag broken English words — a translation that ends with a lone English letter or partial word "
    "(e.g. '一個 s') is a broken hyphenated term split across blocks; the corrected field should "
    "absorb or drop the fragment so the block reads cleanly on its own. "
    "(6) Flag lines that begin with a punctuation mark (，、。) — these are continuation commas or "
    "periods that leaked to the wrong block; remove the leading punctuation in the corrected field."
)


import re as _re
_LEADING_PUNCT = _re.compile(r'^[，、。]+')
_TRAILING_LONE_LETTER = _re.compile(r'\s+[a-z]$')


def pre_fix_zhTW(srt_path: Path) -> int:
    """Apply deterministic zhTW fixes to a draft SRT in place.

    Rules applied:
      1. IELTS → 雅思
      2. 您 → 你
      7. 『』→ 「」
      8. Strip leading punctuation (，、。) from line start
      9. Strip lone trailing English letter (broken hyphenated word fragment)

    Modifies the file directly so the review API scores the already-fixed text.
    Returns total number of replacements made.
    """
    from zhTW_mechanical_fix import parse_srt as mf_parse, blocks_to_srt

    content = srt_path.read_text(encoding="utf-8-sig")
    blocks = mf_parse(content)
    total = 0
    for block in blocks:
        new_lines = []
        for line in block["text_lines"]:
            line, n1 = apply_rule1_ielts(line)
            line, n2 = apply_rule2_nin(line)
            line, n3 = apply_rule7_quotes(line)
            # Rule 8: remove leading punctuation
            stripped = _LEADING_PUNCT.sub('', line)
            n8 = 1 if stripped != line else 0
            line = stripped
            # Rule 9: remove lone trailing English letter (broken word fragment)
            stripped = _TRAILING_LONE_LETTER.sub('', line).rstrip()
            n9 = 1 if stripped != line else 0
            line = stripped
            total += n1 + n2 + n3 + n8 + n9
            new_lines.append(line)
        block["text_lines"] = new_lines
    srt_path.write_text(blocks_to_srt(blocks), encoding="utf-8")
    return total


def finalize(review_path: Path, translated_path: Path) -> int:
    """Apply corrections from review CSV to translated SRT; write _revised.srt to final/.

    Always writes the final SRT — blocks without a correction keep the original translation.
    Returns the number of corrections applied.
    """
    corrections: dict[int, str] = {}
    with open(review_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            corrected = row.get("corrected", "").strip()
            if corrected:
                try:
                    corrections[int(row["block"])] = corrected
                except (KeyError, ValueError):
                    pass

    blocks = parse_srt(translated_path.read_text(encoding="utf-8-sig"))
    for block in blocks:
        if block["index"] in corrections:
            block["lines"] = [corrections[block["index"]]]

    final_dir = review_path.parent.parent / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    out_path = final_dir / (translated_path.stem + "_revised.srt")
    out_path.write_text(write_srt(blocks), encoding="utf-8")
    return len(corrections)


def main():
    parser = argparse.ArgumentParser(
        description="Review translated SRTs and apply corrections in one pass.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/review_and_finalize.py --target zhTW
  python3 scripts/review_and_finalize.py --target zhTW --folder "IE Intermediate 2.6/Listening Int"
  python3 scripts/review_and_finalize.py --target id --folder "IE Intermediate 2.6/Listening Int"
  python3 scripts/review_and_finalize.py --dry-run
  python3 scripts/review_and_finalize.py --force --strictness linguist
""",
    )
    parser.add_argument("--target", "-t", choices=list(TARGET_LANG_MAP.keys()),
                        help="Language code to process (e.g. zhTW, id, ja, ko)")
    parser.add_argument("--folder", "-f", help="Subfolder filter under output/ (e.g. 'IE Intermediate 2.6/Listening Int')")
    parser.add_argument("--force", action="store_true",
                        help="Re-review and re-finalize even if _revised.srt already exists")
    parser.add_argument("--skip-review", action="store_true",
                        help="Skip API review — apply pre-fix to drafts and re-generate finals from existing CSVs only (no API calls)")
    parser.add_argument("--dry-run", action="store_true", help="Print queue without running")
    parser.add_argument("--strictness", default="objective",
                        choices=["objective", "linguist", "permissive"],
                        help="Review strictness (default: objective)")
    parser.add_argument("--context", default=None,
                        help="Domain context for reviewer (default: zhTW-specific rules for zhTW, generic otherwise)")
    args = parser.parse_args()

    queue = discover_queue(args.target, args.folder)

    if not queue:
        print("No translated SRT files found matching your filters.")
        sys.exit(0)

    # Tag each job with its expected final output path
    for job in queue:
        job["final_out"] = (
            job["review_out"].parent.parent / "final" /
            (job["translated"].stem + "_revised.srt")
        )
        job["finalized"] = job["final_out"].exists()

    pending = [j for j in queue if not j["finalized"] or args.force]
    already_done = len(queue) - len(pending)

    print(f"Queue: {len(queue)} file(s) — {len(pending)} to process, {already_done} already finalized")
    print()

    for j in queue:
        status = "DONE" if j["finalized"] and not args.force else "QUEUE"
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

        # Pre-fix: apply deterministic zhTW rules before review
        # Runs when: zhTW, and either no review CSV yet OR --skip-review (re-fix without re-reviewing)
        if job["lang"] == "zhTW" and (not job["review_out"].exists() or args.skip_review):
            fixes = pre_fix_zhTW(job["translated"])
            if fixes:
                print(f"  Pre-fix: {fixes} mechanical replacement(s) applied (IELTS→雅思, 您→你, quotes)")

        if args.skip_review:
            if not job["review_out"].exists():
                print(f"  [skip-review] No review CSV found — skipping {rel}")
                print()
                continue
            print(f"  [skip-review] Using existing review CSV")
        else:
            # Resolve context: zhTW gets enriched rules; others get generic default
            context = args.context or (ZHTW_CONTEXT if job["lang"] == "zhTW" else CONTEXT_DEFAULT)

            # Step 2: review (resumes from existing CSV if present)
            stats = review_file(
                job["source"], job["translated"], job["lang"],
                job["review_out"], context, args.strictness,
            )
            if stats["avg"] is not None:
                print(f"  Score: {stats['avg']:.1f} | ok={stats['ok']} warn={stats['warning']} reject={stats['reject']}")
                print(f"  Review: {job['review_out'].relative_to(PROJECT_ROOT)}")

        # Step 4: apply corrections → _revised.srt
        applied = finalize(job["review_out"], job["translated"])
        print(f"  Applied {applied} correction(s) → {job['final_out'].relative_to(PROJECT_ROOT)}")
        print()

        if not args.skip_review and stats["avg"] is not None:
            summaries.append({"file": str(rel), **stats})

    # Summary table
    scored = [s for s in summaries if s["avg"] is not None]
    if scored:
        print("=" * 60)
        print(f"{'File':<40} {'Avg':>5}  {'ok':>4}  {'warn':>4}  {'rej':>4}")
        print("-" * 60)
        for s in scored:
            name = s["file"][-40:] if len(s["file"]) > 40 else s["file"]
            print(f"{name:<40} {s['avg']:>5.1f}  {s['ok']:>4}  {s['warning']:>4}  {s['reject']:>4}")
        overall = [s["avg"] for s in scored]
        print("-" * 60)
        print(f"{'TOTAL':<40} {sum(overall)/len(overall):>5.1f}")
        print("=" * 60)

    print(f"\nDone. {len(pending)} file(s) reviewed and finalized.")


if __name__ == "__main__":
    main()
