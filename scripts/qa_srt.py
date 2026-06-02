#!/usr/bin/env python3
from __future__ import annotations
"""
qa_srt.py — Quality audit for zhTW revised SRT files.

Detects per block:
  1. Simplified Chinese characters that should be Traditional
  2. Leading comma/punctuation (，、) at block start
  3. Trailing English fragment (word drop-off at block end)
  4. Cross-block English word split (fragment in N + continuation in N+1)
  5. Duplicate consecutive phrases within a block
  6. Long untranslated English sequences in a Chinese block (25+ chars)

Does NOT detect:
  - CJK-level word splits across blocks (e.g. 幫助 → 助我們) — needs a segmenter
  - Wrong word substitutions (e.g. 煤 vs 冷) — needs semantic context

Usage:
    python3 scripts/qa_srt.py output/IE\ Intermediate\ 2.6/Listening\ Int/zhTW/final/
    python3 scripts/qa_srt.py output/.../zhTW_L10S2_revised.srt
    python3 scripts/qa_srt.py output/.../zhTW/final/ --csv qa_report.csv
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


# ── 1. Simplified → Traditional (unambiguous pairs only) ─────────────────────
SIMP_TO_TRAD: dict[str, str] = {
    '们': '們', '这': '這', '来': '來', '过': '過', '为': '為',
    '产': '產', '气': '氣', '将': '將', '发': '發', '从': '從',
    '说': '說', '进': '進', '还': '還', '给': '給', '对': '對',
    '时': '時', '话': '話', '样': '樣', '场': '場', '头': '頭',
    '实': '實', '见': '見', '长': '長', '个': '個', '节': '節',
    '动': '動', '东': '東', '关': '關', '开': '開', '类': '類',
    '应': '應', '该': '該', '务': '務', '质': '質', '浆': '漿',
    '处': '處', '际': '際', '间': '間', '后': '後', '没': '沒',
    '块': '塊', '须': '須', '问': '問', '边': '邊', '现': '現',
    '与': '與', '号': '號', '员': '員', '历': '歷', '设': '設',
    '备': '備', '确': '確', '证': '證', '识': '識', '总': '總',
    '导': '導', '载': '載', '义': '義', '带': '帶', '则': '則',
    '术': '術', '达': '達', '较': '較', '体': '體', '变': '變',
    '传': '傳', '联': '聯', '验': '驗', '试': '試', '组': '組',
    '级': '級', '态': '態', '办': '辦', '权': '權', '规': '規',
}
_SIMP_RE = re.compile('[' + ''.join(re.escape(c) for c in SIMP_TO_TRAD) + ']')

# ── 2. Leading comma ───────────────────────────────────────────────────────────
_LEADING_COMMA_RE = re.compile(r'^[，、]')

# ── 3. Trailing English fragment: space + 1–3 Latin letters at end of block ───
_TRAILING_FRAG_RE = re.compile(r'[ 　][a-zA-Z]{1,3}$')

# ── 4. Cross-block split: block N ends with fragment → block N+1 starts lowercase ─
_LEADING_LOWER_EN_RE = re.compile(r'^[a-z]{2,}')

# ── 5. Duplicate consecutive CJK phrase (3+ chars, repeated with optional punct between) ─
_DUPE_PHRASE_RE = re.compile(
    r'([一-鿿，、。！？]{3,})'
    r'[\s，、。！？]*'
    r'\1'
)

# ── 6. Long untranslated English in Chinese context (25+ consecutive Latin chars/spaces) ─
_LONG_EN_RE = re.compile(r'[a-zA-Z][a-zA-Z ]{23,}[a-zA-Z]')
_HAS_CJK_RE = re.compile(r'[一-鿿]')


# ─────────────────────────────────────────────────────────────────────────────

def parse_srt(path: Path) -> list[dict]:
    content = path.read_text(encoding='utf-8-sig')
    blocks = []
    for raw in re.split(r'\n\n+', content.strip()):
        parts = raw.strip().splitlines()
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0].strip())
        except ValueError:
            continue
        text = ' '.join(line.strip() for line in parts[2:] if line.strip())
        blocks.append({'index': idx, 'timestamp': parts[1].strip(), 'text': text})
    return blocks


def _issue(block_idx: int, issue_type: str, detail: str, text: str) -> dict:
    return {'block': block_idx, 'type': issue_type, 'detail': detail, 'text': text}


def check_block(block: dict) -> list[dict]:
    issues = []
    idx = block['index']
    text = block['text']

    # 1. Simplified chars
    found = _SIMP_RE.findall(text)
    if found:
        corrections = ', '.join(f'{c}→{SIMP_TO_TRAD[c]}' for c in dict.fromkeys(found))
        issues.append(_issue(idx, 'simplified_char', corrections, text))

    # 2. Leading comma
    if _LEADING_COMMA_RE.match(text):
        issues.append(_issue(idx, 'leading_comma', f'starts with "{text[0]}"', text))

    # 3. Trailing English fragment
    m = _TRAILING_FRAG_RE.search(text)
    if m:
        issues.append(_issue(idx, 'trailing_fragment', f'ends with "{m.group().strip()}"', text))

    # 5. Duplicate phrase
    for m in _DUPE_PHRASE_RE.finditer(text):
        issues.append(_issue(idx, 'duplicate_phrase', f'"{m.group(1)}" repeated', text))

    # 6. Long untranslated English
    if _HAS_CJK_RE.search(text):
        m = _LONG_EN_RE.search(text)
        if m:
            snippet = m.group()[:50]
            issues.append(_issue(idx, 'untranslated_english', f'"{snippet}"', text))

    return issues


def check_cross_blocks(blocks: list[dict]) -> list[dict]:
    issues = []
    for i in range(len(blocks) - 1):
        curr = blocks[i]
        nxt = blocks[i + 1]
        m_end = _TRAILING_FRAG_RE.search(curr['text'])
        m_start = _LEADING_LOWER_EN_RE.match(nxt['text'])
        if m_end and m_start:
            frag = m_end.group().strip()
            cont = nxt['text'][:20]
            issues.append(_issue(
                curr['index'],
                'cross_block_split',
                f'"{frag}" → block {nxt["index"]} starts "{cont}"',
                curr['text'],
            ))
    return issues


def audit_file(path: Path) -> list[dict]:
    blocks = parse_srt(path)
    issues: list[dict] = []
    for block in blocks:
        issues.extend(check_block(block))
    issues.extend(check_cross_blocks(blocks))
    for iss in issues:
        iss['file'] = path.name
    return sorted(issues, key=lambda x: (x['block'], x['type']))


def main() -> None:
    parser = argparse.ArgumentParser(
        description='QA audit for zhTW revised SRT files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/qa_srt.py "output/IE Intermediate 2.6/Listening Int/zhTW/final/"
  python3 scripts/qa_srt.py "output/IE Intermediate 2.6/Listening Int/zhTW/final/" --csv qa_report.csv
  python3 scripts/qa_srt.py "output/IE Intermediate 2.6/Listening Int/zhTW/final/zhTW_L10S2_revised.srt"
""",
    )
    parser.add_argument('target', help='SRT file or directory containing SRT files')
    parser.add_argument('--csv', '-o', metavar='FILE', help='Save report to CSV')
    args = parser.parse_args()

    target = Path(args.target)
    if target.is_dir():
        files = sorted(target.glob('*_revised.srt'))
        if not files:
            files = sorted(target.glob('*.srt'))
    elif target.is_file():
        files = [target]
    else:
        print(f'Error: {target} not found', file=sys.stderr)
        sys.exit(1)

    if not files:
        print('No SRT files found.', file=sys.stderr)
        sys.exit(1)

    all_issues: list[dict] = []
    clean_count = 0

    for f in files:
        file_issues = audit_file(f)
        all_issues.extend(file_issues)
        if file_issues:
            print(f'\n{f.name} — {len(file_issues)} issue(s)')
            for iss in file_issues:
                print(f'  [{iss["block"]:>3}] {iss["type"]:<22} {iss["detail"]}')
        else:
            clean_count += 1

    # Summary
    print(f'\n{"─" * 60}')
    print(f'Files: {len(files)} scanned, {clean_count} clean, {len(files) - clean_count} with issues')
    print(f'Total issues: {len(all_issues)}')
    if all_issues:
        print('\nBy type:')
        for t, c in Counter(iss['type'] for iss in all_issues).most_common():
            print(f'  {t:<22} {c}')

    if args.csv:
        csv_path = Path(args.csv)
        fieldnames = ['file', 'block', 'type', 'detail', 'text']
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_issues)
        print(f'\nReport saved → {csv_path}')


if __name__ == '__main__':
    main()
