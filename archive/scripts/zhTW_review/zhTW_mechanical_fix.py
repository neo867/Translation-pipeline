#!/usr/bin/env python3
"""
zhTW_mechanical_fix.py — Apply deterministic zhTW review rules before a Claude Code naturalness pass.

Applies:
  Rule 1: IELTS → 雅思 (except inside formal tier names like "IELTS Academic")
  Rule 2: 您 → 你 (instructor-to-student direction; not in quoted dialogue)
  Rule 4: Keep technical English terms as-is (no change needed — this is a no-op guard)
  Rule 5: Keep accent names as-is (same)
  Rule 6: Output saved as <name>_revised.srt
  Rule 7: 『』→ 「」(TW-standard quotation marks)

Usage:
    python3 scripts/zhTW_mechanical_fix.py output/zhTW_L1S1.srt
    python3 scripts/zhTW_mechanical_fix.py output/zhTW_L1S1.srt --output output/zhTW_L1S1_revised.srt
    python3 scripts/zhTW_mechanical_fix.py output/zhTW_L1S1.srt --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

# Formal IELTS tier names that should keep "IELTS" in English
IELTS_KEEP_PATTERNS = re.compile(
    r"IELTS\s+(Academic|General\s+Training|General Training|Indicator)",
    re.IGNORECASE,
)

# Matches standalone IELTS not followed by a formal tier name
IELTS_STANDALONE = re.compile(r"\bIELTS\b(?!\s+(?:Academic|General))")


def apply_rule1_ielts(text: str) -> tuple[str, int]:
    """Replace standalone IELTS with 雅思; preserve IELTS Academic / General Training."""
    count = 0

    def replace(m: re.Match) -> str:
        nonlocal count
        # Double-check it's not part of a kept pattern
        start = m.start()
        surrounding = text[max(0, start - 1): start + 30]
        if IELTS_KEEP_PATTERNS.search(surrounding):
            return m.group(0)
        count += 1
        return "雅思"

    result = IELTS_STANDALONE.sub(replace, text)
    return result, count


def apply_rule2_nin(text: str) -> tuple[str, int]:
    """Replace 您 with 你 throughout (instructor-to-student context)."""
    count = text.count("您")
    return text.replace("您", "你"), count


def apply_rule7_quotes(text: str) -> tuple[str, int]:
    """Replace 『』with 「」(TW-standard quotation marks)."""
    count = text.count("『") + text.count("』")
    text = text.replace("『", "「").replace("』", "」")
    return text, count


def parse_srt(content: str) -> list[dict]:
    """Parse SRT into list of {index, timestamp, text_lines, raw}."""
    blocks = []
    for raw in re.split(r"\n\n+", content.strip()):
        parts = raw.strip().splitlines()
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0].strip())
        except ValueError:
            continue
        timestamp = parts[1].strip()
        text_lines = parts[2:]
        blocks.append({
            "index": idx,
            "timestamp": timestamp,
            "text_lines": text_lines,
            "raw": raw.strip(),
        })
    return blocks


def blocks_to_srt(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        text = "\n".join(b["text_lines"])
        parts.append(f"{b['index']}\n{b['timestamp']}\n{text}")
    return "\n\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Apply deterministic zhTW fixes (Rules 1, 2, 6) before a naturalness pass.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/zhTW_mechanical_fix.py output/zhTW_L1S1.srt
  python3 scripts/zhTW_mechanical_fix.py output/zhTW_L1S1.srt --dry-run
""",
    )
    parser.add_argument("input", help="Translated zhTW .srt file to fix")
    parser.add_argument("--output", "-o", help="Output path (default: <input-stem>_revised.srt)")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_revised{input_path.suffix}"

    content = input_path.read_text(encoding="utf-8-sig")
    blocks = parse_srt(content)

    total_ielts = 0
    total_nin = 0
    total_quotes = 0
    changed_blocks = []

    for block in blocks:
        original_lines = list(block["text_lines"])
        new_lines = []
        for line in block["text_lines"]:
            line, n1 = apply_rule1_ielts(line)
            line, n2 = apply_rule2_nin(line)
            line, n3 = apply_rule7_quotes(line)
            new_lines.append(line)
            total_ielts += n1
            total_nin += n2
            total_quotes += n3
        if new_lines != original_lines:
            changed_blocks.append({
                "index": block["index"],
                "before": original_lines,
                "after": new_lines,
            })
        block["text_lines"] = new_lines

    # Report
    print(f"\nFile: {input_path.name}")
    print(f"  Rule 1 — IELTS → 雅思:  {total_ielts} replacement(s)")
    print(f"  Rule 2 — 您 → 你:        {total_nin} replacement(s)")
    print(f"  Rule 7 — 『』→ 「」:     {total_quotes} replacement(s)")
    print(f"  Blocks changed: {len(changed_blocks)}")

    if changed_blocks:
        print("\nChanged blocks:")
        for cb in changed_blocks:
            print(f"\n  [{cb['index']}]")
            print(f"    Before: {' / '.join(cb['before'])}")
            print(f"    After:  {' / '.join(cb['after'])}")

    if args.dry_run:
        print("\n[dry-run] No file written.")
        return

    output_srt = blocks_to_srt(blocks)
    output_path.write_text(output_srt, encoding="utf-8")
    print(f"\nSaved → {output_path}")
    print("Next step: open in Claude Code for a naturalness pass (Rule 3).")


if __name__ == "__main__":
    main()
