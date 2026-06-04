#!/usr/bin/env python3
"""
id_mechanical_fix.py — Apply deterministic Bahasa Indonesia review rules before a naturalness pass.

Applies:
  Rule 1: Keep IELTS skill names in English (menyimak/mendengarkan → Listening, etc.)
  Rule 2: grup musik → Band (IELTS band score — never music band)
  Rule 3: melatih → berlatih (self-practice is intransitive)
  Rule 4: Word-level substitutions (see WORD_SUBS below)
  Rule 5: Slash artifact removal (X/Y alternatives → pick one)
  Rule 6: Output saved as id_<name>_revised.srt

Usage:
    python3 scripts/id_mechanical_fix.py output/id_L1S1.srt
    python3 scripts/id_mechanical_fix.py output/id_L1S1.srt --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

# Rule 1 — IELTS skill name patterns (whole-phrase, context-sensitive)
# Replace Indonesian skill names only when used as IELTS skill labels.
# Pattern: word boundary + Indonesian term + optional " IELTS" or "tes" context
_SKILL_SUBS: list[tuple[re.Pattern, str, str]] = [
    # menyimak / mendengarkan → Listening (as IELTS skill label)
    (re.compile(r'\btes\s+menyimak\b',     re.IGNORECASE), 'tes Listening',    'menyimak→Listening'),
    (re.compile(r'\btes\s+mendengarkan\b', re.IGNORECASE), 'tes Listening',    'mendengarkan→Listening'),
    (re.compile(r'\bkursus\s+menyimak\b',  re.IGNORECASE), 'kursus Listening', 'menyimak→Listening'),
    (re.compile(r'\bkemampuan\s+menyimak\b', re.IGNORECASE), 'kemampuan Listening', 'menyimak→Listening'),
    (re.compile(r'\bskor\s+mendengarkan\b', re.IGNORECASE), 'skor Listening',  'mendengarkan→Listening'),
    # Reading / Writing / Speaking
    (re.compile(r'\btes\s+membaca\b',      re.IGNORECASE), 'tes Reading',      'membaca→Reading'),
    (re.compile(r'\btes\s+menulis\b',      re.IGNORECASE), 'tes Writing',      'menulis→Writing'),
    (re.compile(r'\btes\s+berbicara\b',    re.IGNORECASE), 'tes Speaking',     'berbicara→Speaking'),
]

# Rule 2-4 — Word-level substitutions (ordered: longer/specific first)
WORD_SUBS: list[tuple[str, str]] = [
    # Critical machine-translation errors
    ("grup musik",        "Band"),          # IELTS band score
    # Practice verb
    ("melatih",           "berlatih"),
    # Terminology
    ("tingkatan",         "tingkat"),
    ("persis sama",       "sama persis"),
    ("bad cuaca",         "cuaca buruk"),
    ("football",          "sepak bola"),
    ("synonyms",          "sinonim"),
    # Preposition consistency
    ("untuk kursus kami", "di kursus ini"),
]

# Rule 5 — Slash artifact patterns (explicit known pairs)
SLASH_FIXES: list[tuple[str, str]] = [
    ("global/mendunia",       "global"),
    ("jumlah/total",          "total"),
    ("perjanjian/kesepakatan","kesepakatan"),
]


def apply_skill_subs(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for pattern, replacement, label in _SKILL_SUBS:
        new_text, n = pattern.subn(replacement, text)
        if n:
            counts[label] = counts.get(label, 0) + n
            text = new_text
    return text, counts


def apply_word_subs(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for src, dst in WORD_SUBS:
        n = text.count(src)
        if n:
            text = text.replace(src, dst)
            counts[src] = n
    return text, counts


def apply_slash_fixes(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for src, dst in SLASH_FIXES:
        n = text.count(src)
        if n:
            text = text.replace(src, dst)
            counts[src] = n
    return text, counts


def parse_srt(content: str) -> list[dict]:
    blocks = []
    for raw in re.split(r'\n\n+', content.strip()):
        parts = raw.strip().splitlines()
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0].strip())
        except ValueError:
            continue
        blocks.append({
            'index': idx,
            'timestamp': parts[1].strip(),
            'text_lines': parts[2:],
            'raw': raw.strip(),
        })
    return blocks


def blocks_to_srt(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        text = '\n'.join(b['text_lines'])
        parts.append(f"{b['index']}\n{b['timestamp']}\n{text}")
    return '\n\n'.join(parts) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description='Apply deterministic Bahasa Indonesia fixes before a naturalness pass.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/id_mechanical_fix.py output/id_L1S1.srt
  python3 scripts/id_mechanical_fix.py output/id_L1S1.srt --dry-run
""",
    )
    parser.add_argument('input', help='Translated Bahasa .srt file to fix')
    parser.add_argument('--output', '-o', help='Output path (default: <stem>_revised.srt)')
    parser.add_argument('--dry-run', action='store_true', help='Print changes without writing')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'Error: file not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else \
        input_path.parent / f"{input_path.stem}_revised{input_path.suffix}"

    content = input_path.read_text(encoding='utf-8-sig')
    blocks = parse_srt(content)

    total_skill: dict[str, int] = {}
    total_word: dict[str, int] = {}
    total_slash: dict[str, int] = {}
    changed_blocks = []

    for block in blocks:
        original_lines = list(block['text_lines'])
        new_lines = []
        for line in block['text_lines']:
            line, s = apply_skill_subs(line)
            line, w = apply_word_subs(line)
            line, sl = apply_slash_fixes(line)
            new_lines.append(line)
            for k, v in s.items():
                total_skill[k] = total_skill.get(k, 0) + v
            for k, v in w.items():
                total_word[k] = total_word.get(k, 0) + v
            for k, v in sl.items():
                total_slash[k] = total_slash.get(k, 0) + v
        if new_lines != original_lines:
            changed_blocks.append({'index': block['index'], 'before': original_lines, 'after': new_lines})
        block['text_lines'] = new_lines

    print(f'\nFile: {input_path.name}')
    for label, cnt in total_skill.items():
        print(f'  Rule 1 — {label}: {cnt}')
    for src, cnt in total_word.items():
        dst = next(d for s, d in WORD_SUBS if s == src)
        print(f'  Rule 2-4 — {src} → {dst}: {cnt}')
    for src, cnt in total_slash.items():
        dst = next(d for s, d in SLASH_FIXES if s == src)
        print(f'  Rule 5 — {src} → {dst}: {cnt}')
    print(f'  Blocks changed: {len(changed_blocks)}')

    if changed_blocks:
        print('\nChanged blocks:')
        for cb in changed_blocks:
            print(f"\n  [{cb['index']}]")
            print(f"    Before: {' / '.join(cb['before'])}")
            print(f"    After:  {' / '.join(cb['after'])}")

    if args.dry_run:
        print('\n[dry-run] No file written.')
        return

    output_path.write_text(blocks_to_srt(blocks), encoding='utf-8')
    print(f'\nSaved → {output_path}')
    print('Next step: naturalness pass, then qa_srt.py.')


if __name__ == '__main__':
    main()
