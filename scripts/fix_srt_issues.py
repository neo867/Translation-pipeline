#!/usr/bin/env python3
from __future__ import annotations
"""
fix_srt_issues.py — Auto-fix QA issues in zhTW revised SRT files.

Runs qa_srt.py internally, then applies fixes in two phases:

  Phase 1 — Deterministic (no API):
    • simplified_char     → substitute using Simplified→Traditional map
    • leading_comma       → strip leading ，or 、from block text
    • duplicate_phrase    → remove second occurrence of repeated phrase
    • trailing_fragment   → strip trailing space + dangling English fragment
    • vocab_violation     → substitute preferred zhTW vocab (詞彙→字彙, 同義詞→同義字, 瞭解→了解, 堂課→單元)
    • slash_artifact      → pick first option in word1/word2 pairs (skips known IELTS terms)

  Phase 2 — API-assisted (for cross_block_split only):
    • Sends the block AFTER the split (block N+1, which starts with English)
      to /review/batch together with the original source block for correction.

Overwrites the _revised.srt in place.

Usage:
    python3 scripts/fix_srt_issues.py "output/IE Intermediate 2.6/Listening Int/zhTW/final/"
    python3 scripts/fix_srt_issues.py "output/.../zhTW_L10S2_revised.srt"
    python3 scripts/fix_srt_issues.py "output/.../zhTW/final/" --dry-run
"""

import argparse
import csv
import io
import re
import sys
import time
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE_DIR = PROJECT_ROOT / "IE Intermediate 2.6" / "Reading Int"

API_BASE = "https://translate.flowb.ai"
API_KEY = "tw-localizer-dev-a1b2c3d4e5f6"
REVIEW_TIMEOUT = 120

CONTEXT = (
    "Course subtitles from an English-language IELTS reading lesson for Taiwanese students. "
    "Target is Traditional Chinese (繁體中文). "
    "Preserve technical IELTS terms, English example words shown as answers, and all punctuation. "
    "Fix any untranslated English phrases at the start of the block."
)

# ── Simplified → Traditional map ─────────────────────────────────────────────
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
_LEADING_COMMA_RE = re.compile(r'^[，、]+')
_TRAILING_FRAG_RE = re.compile(r'[ 　][a-zA-Z]{1,3}$')
_DUPE_PHRASE_RE = re.compile(r'([一-鿿，、。！？]{3,})([\s，、。！？]*)(\1)')

# ── Vocab violation substitution map ─────────────────────────────────────────
VOCAB_MAP: dict[str, str] = {
    '詞彙': '字彙',
    '同義詞': '同義字',
    '瞭解': '了解',
    '堂課': '單元',
}
_VOCAB_RE = re.compile('|'.join(re.escape(k) for k in VOCAB_MAP))

# Slash artifacts: IELTS terms to preserve as-is
_SLASH_KEEP = {'True/False', 'Yes/No', 'True/False/Not Given', 'Yes/No/Not Given'}
_SLASH_RE = re.compile(r'[A-Za-z一-鿿][A-Za-z一-鿿]*/[A-Za-z一-鿿][A-Za-z一-鿿]*')


# ── SRT helpers ───────────────────────────────────────────────────────────────

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
        text = ' '.join(l.strip() for l in parts[2:] if l.strip())
        blocks.append({'index': idx, 'timestamp': parts[1].strip(), 'text': text})
    return blocks


def write_srt(blocks: list[dict], path: Path) -> None:
    parts = []
    for b in blocks:
        parts.append(f"{b['index']}\n{b['timestamp']}\n{b['text']}")
    path.write_text('\n\n'.join(parts) + '\n', encoding='utf-8')


# ── Source SRT lookup ─────────────────────────────────────────────────────────

def find_source_srt(revised_path: Path) -> Path | None:
    """Extract lesson code from zhTW_L10S2_revised.srt → L10S2.srt in SOURCE_DIR."""
    m = re.match(r'zhTW_([A-Za-z0-9]+)_revised', revised_path.stem)
    if not m:
        return None
    lesson = m.group(1)
    candidate = SOURCE_DIR / f'{lesson}.srt'
    return candidate if candidate.exists() else None


# ── Phase 1: Deterministic fixes ─────────────────────────────────────────────

def fix_simplified_chars(text: str) -> tuple[str, int]:
    count = 0
    def sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        return SIMP_TO_TRAD[m.group()]
    return _SIMP_RE.sub(sub, text), count


def fix_leading_comma(text: str) -> tuple[str, bool]:
    new = _LEADING_COMMA_RE.sub('', text).lstrip()
    return new, new != text


def fix_duplicate_phrase(text: str) -> tuple[str, int]:
    count = 0
    def sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        return m.group(1) + m.group(2)  # keep first occurrence + separator
    new = _DUPE_PHRASE_RE.sub(sub, text)
    return new, count


def fix_trailing_fragment(text: str) -> tuple[str, bool]:
    new = _TRAILING_FRAG_RE.sub('', text).rstrip()
    return new, new != text


def fix_vocab_violations(text: str) -> tuple[str, int]:
    count = 0
    def sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        return VOCAB_MAP[m.group()]
    return _VOCAB_RE.sub(sub, text), count


def fix_slash_artifact(text: str) -> tuple[str, bool]:
    def sub(m: re.Match) -> str:
        matched = m.group()
        if matched in _SLASH_KEEP:
            return matched
        return matched.split('/')[0]
    new = _SLASH_RE.sub(sub, text)
    return new, new != text


def apply_deterministic_fixes(blocks: list[dict]) -> tuple[list[dict], dict[int, list[str]]]:
    """Apply all phase-1 fixes. Returns updated blocks and a change log."""
    log: dict[int, list[str]] = {}
    for b in blocks:
        original = b['text']
        changes = []

        text, n = fix_simplified_chars(b['text'])
        if n:
            changes.append(f'simplified_char ({n})')
            b['text'] = text

        text, changed = fix_leading_comma(b['text'])
        if changed:
            changes.append('leading_comma')
            b['text'] = text

        text, n = fix_duplicate_phrase(b['text'])
        if n:
            changes.append(f'duplicate_phrase ({n})')
            b['text'] = text

        text, changed = fix_trailing_fragment(b['text'])
        if changed:
            changes.append('trailing_fragment')
            b['text'] = text

        text, n = fix_vocab_violations(b['text'])
        if n:
            changes.append(f'vocab_violation ({n})')
            b['text'] = text

        text, changed = fix_slash_artifact(b['text'])
        if changed:
            changes.append('slash_artifact')
            b['text'] = text

        if changes:
            log[b['index']] = changes
    return blocks, log


# ── Phase 2: API-assisted fix for cross-block splits ─────────────────────────

def _post_review(pairs: list[dict]) -> list[dict]:
    try:
        resp = requests.post(
            f'{API_BASE}/review/batch',
            headers={'X-API-Key': API_KEY, 'Content-Type': 'application/json'},
            json={
                'items': pairs,
                'source_lang': 'en',
                'target_lang': 'zhTW',
                'content_type': 'subtitle',
                'context': CONTEXT,
                'strictness': 'linguist',
            },
            timeout=REVIEW_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get('results', [])
    except Exception as e:
        print(f'  [API error] {e}', file=sys.stderr)
        return []


def detect_cross_block_splits(blocks: list[dict]) -> list[int]:
    """Return indices (in blocks list) of block N+1 that start with English continuation."""
    _trailing = re.compile(r'[ 　][a-zA-Z]{1,3}$')
    _leading_lower = re.compile(r'^[a-z]{2,}')
    splits = []
    for i in range(len(blocks) - 1):
        if _trailing.search(blocks[i]['text']) and _leading_lower.match(blocks[i + 1]['text']):
            splits.append(i + 1)
    return splits


def fix_cross_block_splits(
    blocks: list[dict],
    source_blocks: dict[int, dict],
    dry_run: bool,
) -> dict[int, str]:
    """Send cross-block-split successor blocks to the review API. Returns {block_idx: corrected}."""
    split_positions = detect_cross_block_splits(blocks)
    if not split_positions:
        return {}

    pairs = []
    for pos in split_positions:
        b = blocks[pos]
        src = source_blocks.get(b['index'], {}).get('text', '')
        pairs.append({
            '_pos': pos,
            'block_index': b['index'],
            'source': src,
            'translation': b['text'],
        })

    if dry_run:
        print(f'  [dry-run] would send {len(pairs)} block(s) to review API')
        return {}

    api_pairs = [{'source': p['source'], 'translation': p['translation']} for p in pairs]
    results = _post_review(api_pairs)

    corrections: dict[int, str] = {}
    for pair, res in zip(pairs, results):
        corrected = (res.get('corrected') or '').strip()
        if corrected and corrected != pair['translation']:
            corrections[blocks[pair['_pos']]['index']] = corrected

    return corrections


# ── QA runner (inline — avoids subprocess) ───────────────────────────────────

def _run_qa(path: Path) -> list[dict]:
    """Import and run the qa_srt logic directly."""
    # Import qa_srt from the same scripts/ directory
    import importlib.util
    spec = importlib.util.spec_from_file_location('qa_srt', SCRIPT_DIR / 'qa_srt.py')
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    return qa.audit_file(path)


# ── Main fix routine ──────────────────────────────────────────────────────────

def fix_file(path: Path, dry_run: bool) -> None:
    print(f'\n{path.name}')

    qa_issues = _run_qa(path)
    if not qa_issues:
        print('  clean — no issues found')
        return

    issue_types = {iss['type'] for iss in qa_issues}
    print(f'  {len(qa_issues)} issue(s): {", ".join(sorted(issue_types))}')

    blocks = parse_srt(path)
    block_by_idx: dict[int, dict] = {b['index']: b for b in blocks}

    # Detect cross-block split successors BEFORE phase 1 strips the trailing fragments
    has_split = any(iss['type'] == 'cross_block_split' for iss in qa_issues)
    split_successor_indices: set[int] = set()
    if has_split:
        for i in range(len(blocks) - 1):
            if _TRAILING_FRAG_RE.search(blocks[i]['text']) and \
               re.match(r'^[a-z]{2,}', blocks[i + 1]['text']):
                split_successor_indices.add(blocks[i + 1]['index'])

    # Phase 1 — deterministic
    blocks, det_log = apply_deterministic_fixes(blocks)
    for idx, changes in sorted(det_log.items()):
        print(f'  [fix] block {idx:>3}: {", ".join(changes)}')

    # Phase 2 — API for cross-block splits (fix the successor block's English start)
    if split_successor_indices:
        source_path = find_source_srt(path)
        if source_path:
            source_blocks = {b['index']: b for b in parse_srt(source_path)}
        else:
            source_blocks = {}
            print('  [warn] source SRT not found — API fix will run without source context')

        # Build pairs for API
        pairs = []
        for b in blocks:
            if b['index'] in split_successor_indices:
                src = source_blocks.get(b['index'], {}).get('text', '')
                pairs.append({'_idx': b['index'], 'source': src, 'translation': b['text']})

        if dry_run:
            print(f'  [dry-run] would send {len(pairs)} block(s) to review API for English fix')
        else:
            api_pairs = [{'source': p['source'], 'translation': p['translation']} for p in pairs]
            results = _post_review(api_pairs)
            for pair, res in zip(pairs, results):
                corrected = (res.get('corrected') or '').strip()
                if corrected and corrected != pair['translation']:
                    block_by_idx[pair['_idx']]['text'] = corrected
                    print(f'  [API] block {pair["_idx"]:>3}: corrected')
            if not results:
                print('  [API] no response — cross-block splits left for manual check')

    if dry_run:
        print('  [dry-run] file not written')
        return

    write_srt(blocks, path)
    print(f'  saved → {path.name}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Auto-fix QA issues in zhTW revised SRT files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/fix_srt_issues.py "output/IE Intermediate 2.6/Listening Int/zhTW/final/"
  python3 scripts/fix_srt_issues.py "output/.../zhTW_L10S2_revised.srt" --dry-run
""",
    )
    parser.add_argument('target', help='SRT file or directory of _revised.srt files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would change, write nothing')
    args = parser.parse_args()

    target = Path(args.target)
    if target.is_dir():
        files = sorted(target.glob('*_revised.srt'))
    elif target.is_file():
        files = [target]
    else:
        print(f'Error: {target} not found', file=sys.stderr)
        sys.exit(1)

    if not files:
        print('No _revised.srt files found.', file=sys.stderr)
        sys.exit(1)

    for f in files:
        fix_file(f, args.dry_run)
        if len(files) > 1:
            time.sleep(1)  # be gentle with the API

    print('\nDone.')


if __name__ == '__main__':
    main()
