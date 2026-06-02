#!/usr/bin/env python3
from __future__ import annotations
"""
translate_xliff.py — Translate an XLIFF file via the Translation API V11 (Pipeline V10).

Translates every <trans-unit> whose <target state="needs-review-translation">.
Updates target text and promotes state to "final". Units already at state="final"
are left untouched unless --force is passed.

Resume-safe: saves progress to a .progress.json sidecar next to the input file.
Re-run the same command to continue from where it left off.
Use --rerun to clear progress and restart from scratch.

Usage:
    python3 translate_xliff.py account_zh-TW.xliff --target zhTW
    python3 translate_xliff.py account_zh-TW.xliff --target zhTW --context "Prep learning platform UI"
    python3 translate_xliff.py account_zh-TW.xliff --target zhTW --content-type ui_button
    python3 translate_xliff.py account_zh-TW.xliff --target zhTW --force
    python3 translate_xliff.py account_zh-TW.xliff --target zhTW --rerun
    python3 translate_xliff.py account_zh-TW.xliff --target zhTW --output translated.xliff

Output overwrites the input file by default. Pass --output to write elsewhere.
"""

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

API_BASE = "https://translate.flowb.ai"
API_KEY = "tw-localizer-dev-a1b2c3d4e5f6"
BATCH_SIZE = 5
DEFAULT_TIMEOUT = 180
XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"

ET.register_namespace("", XLIFF_NS)

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _tag(name: str) -> str:
    return f"{{{XLIFF_NS}}}{name}"


def _source_text(unit: ET.Element) -> str:
    el = unit.find(_tag("source"))
    return "".join(el.itertext()).strip() if el is not None else ""


def _target_el(unit: ET.Element) -> Optional[ET.Element]:
    return unit.find(_tag("target"))


def _needs_translation(unit: ET.Element, force: bool) -> bool:
    src = _source_text(unit)
    if not src:
        return False
    target = _target_el(unit)
    if target is None:
        return True
    if force:
        return True
    return target.get("state", "") == "needs-review-translation"


# ---------------------------------------------------------------------------
# API layer  (mirrors translate_srt.py exactly)
# ---------------------------------------------------------------------------

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


def _translate_single(
    text: str,
    target_lang: str,
    context: Optional[str],
    teaching_lang: Optional[str],
    content_type: str,
    domain: str,
    intent: str,
    vocab_mode: str,
    timeout: int,
    max_retries: int = 10,
) -> str:
    payload: dict = {
        "text": text,
        "source_lang": "en",
        "target_lang": target_lang,
        "content_type": content_type,
        "domain": domain,
        "intent": intent,
        "vocab_mode": vocab_mode,
        "no_cache": True,
    }
    if teaching_lang:
        payload["teaching_lang"] = teaching_lang
    if context:
        payload["context"] = context

    for attempt in range(max_retries):
        result = _post_with_retry("/translate", payload, timeout, 1)
        if "error" in result:
            print(f"  [warn] API error: {result['error']}", file=sys.stderr)
            return ""
        if result.get("source_model") == "FALLBACK_ORIGINAL":
            wait = min(15 * (attempt + 1), 60)
            print(f"  [warn] pipeline crash — waiting {wait}s ({attempt + 1}/{max_retries})", file=sys.stderr)
            time.sleep(wait)
            continue
        return result.get("translation", "")
    return ""


def _translate_batch_chunk(
    texts: list[str],
    target_lang: str,
    context: Optional[str],
    teaching_lang: Optional[str],
    content_type: str,
    domain: str,
    intent: str,
    vocab_mode: str,
    verbose: bool,
    timeout: int,
    max_retries: int = 10,
) -> tuple[list[str], bool]:
    def _make_payload(batch_texts: list[str]) -> dict:
        p: dict = {
            "texts": batch_texts,
            "source_lang": "en",
            "target_lang": target_lang,
            "content_type": content_type,
            "domain": domain,
            "intent": intent,
            "vocab_mode": vocab_mode,
            "no_cache": True,
        }
        if teaching_lang:
            p["teaching_lang"] = teaching_lang
        if context:
            p["context"] = context
        if verbose:
            p["verbose"] = True
        return p

    def _is_fallback(item: dict, src: str) -> bool:
        return (
            "error" in item
            or "FALLBACK_ORIGINAL" in str(item.get("warnings", []))
            or item.get("translation", "") == src
        )

    result = _post_with_retry("/translate/batch", _make_payload(texts), timeout, max_retries)
    items = result.get("results", [])
    while len(items) < len(texts):
        items.append({})

    fallback_indices = [i for i, item in enumerate(items) if _is_fallback(item, texts[i])]
    had_fallbacks = bool(fallback_indices)

    if fallback_indices:
        print(f"  [warn] {len(fallback_indices)} fallback(s) — retrying mini-batch in 15s", file=sys.stderr)
        time.sleep(15)
        retry_texts = [texts[i] for i in fallback_indices]
        retry_result = _post_with_retry("/translate/batch", _make_payload(retry_texts), timeout, max_retries)
        retry_items = retry_result.get("results", [])
        while len(retry_items) < len(retry_texts):
            retry_items.append({})

        for list_pos, original_idx in enumerate(fallback_indices):
            retry_item = retry_items[list_pos]
            if not _is_fallback(retry_item, texts[original_idx]):
                items[original_idx] = retry_item
            else:
                print(f"  [warn] mini-batch retry failed — falling back to single", file=sys.stderr)
                tr = _translate_single(
                    texts[original_idx], target_lang, context, teaching_lang,
                    content_type, domain, intent, vocab_mode, timeout, max_retries,
                )
                items[original_idx] = {"translation": tr}

    return [item.get("translation", "") for item in items], had_fallbacks


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_xliff(
    input_path: Path,
    target_lang: str,
    context: Optional[str] = None,
    teaching_lang: Optional[str] = None,
    content_type: str = "ui_heading",
    domain: str = "education",
    intent: str = "transcreation_ux",
    vocab_mode: str = "preserve",
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    rerun: bool = False,
    force: bool = False,
    output_path: Optional[Path] = None,
) -> int:
    if output_path is None:
        output_path = input_path

    progress_path = input_path.parent / f".{input_path.stem}.{target_lang}.progress.json"

    if rerun and progress_path.exists():
        progress_path.unlink()
        print("--rerun: cleared progress.")

    progress: dict[str, str] = {}
    if progress_path.exists():
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except Exception:
            progress = {}

    print(f"Parsing {input_path.name}...")
    tree = ET.parse(input_path)
    root = tree.getroot()

    all_units = root.findall(f".//{_tag('trans-unit')}")
    print(f"  {len(all_units)} trans-unit elements found.")

    # Determine what needs translating and what's pending (not yet in progress)
    translatable: list[tuple[str, str]] = []  # (unit_id, source_text)
    for unit in all_units:
        uid = unit.get("id", "")
        src = _source_text(unit)
        if src and _needs_translation(unit, force):
            translatable.append((uid, src))

    id_to_src = dict(translatable)
    pending = [(uid, src) for uid, src in translatable if not progress.get(uid, "")]

    total = len(translatable)
    done_count = total - len(pending)
    print(f"  {total} unit(s) to translate — {done_count} already done, {len(pending)} pending.")

    if not pending:
        print("  Nothing new to translate. Applying saved progress to file...")

    failed_count = 0

    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start : start + BATCH_SIZE]
        chunk_ids = [uid for uid, _ in chunk]
        chunk_texts = [src for _, src in chunk]

        chunk_start = done_count + start + 1
        chunk_end = done_count + start + len(chunk)
        print(f"  [{chunk_start}–{chunk_end}/{total}] batch of {len(chunk)}...")

        try:
            translations, had_fallbacks = _translate_batch_chunk(
                chunk_texts, target_lang, context, teaching_lang,
                content_type, domain, intent, vocab_mode, verbose, timeout,
            )
        except Exception as e:
            print(f"  [batch FAILED] {e}", file=sys.stderr)
            translations = [""] * len(chunk)
            had_fallbacks = False

        for uid, src, tr in zip(chunk_ids, chunk_texts, translations):
            if tr and tr != src:
                progress[uid] = tr
            else:
                progress[uid] = ""
                failed_count += 1
                print(f"  [FAILED] id={uid}: {src[:70]}", file=sys.stderr)

        progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

        if start + BATCH_SIZE < len(pending):
            sleep_time = 15 if had_fallbacks else 3
            time.sleep(sleep_time)

    # Apply translations back into the XML tree
    applied = 0
    for unit in all_units:
        uid = unit.get("id", "")
        if uid not in id_to_src:
            continue  # not a translatable unit

        tr = progress.get(uid, "")
        if not tr:
            continue  # failed or not translated yet

        target = _target_el(unit)
        if target is None:
            # Insert a new <target> element right after <source>
            src_el = unit.find(_tag("source"))
            if src_el is not None:
                idx = list(unit).index(src_el)
                target = ET.SubElement(unit, _tag("target"))
                unit.remove(target)
                unit.insert(idx + 1, target)

        # ET automatically escapes < > & in text, which is correct for XLIFF inline tags
        target.text = tr
        target.set("state", "final")
        target.attrib.pop("state-qualifier", None)  # remove TM match qualifier
        applied += 1

    # Pretty-print and write (Python 3.9+ has ET.indent; fall back to unindented)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass

    tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    print(f"  {applied} unit(s) updated -> {output_path}")

    if failed_count == 0 and progress_path.exists():
        progress_path.unlink()
        print("  Progress file cleaned up.")
    elif failed_count:
        print(f"  {failed_count} unit(s) failed — re-run the same command to retry them.")

    return failed_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate XLIFF files — API V11 / Pipeline V10 (Qwen, S5, L2).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported targets: en, zhTW, zhCN, ko, vi, id, th, ja, pt, ptBR, esES, esLA, esAR, hi, ur

Examples:
  python3 translate_xliff.py account_zh-TW.xliff --target zhTW
  python3 translate_xliff.py account_zh-TW.xliff --target zhTW --context "Prep learning platform UI"
  python3 translate_xliff.py account_zh-TW.xliff --target zhTW --content-type ui_button
  python3 translate_xliff.py account_zh-TW.xliff --target zhTW --force
  python3 translate_xliff.py account_zh-TW.xliff --target zhTW --rerun
  python3 translate_xliff.py account_zh-TW.xliff --target zhTW --output out/account_zh-TW.xliff
""",
    )
    parser.add_argument("input", help="Input .xliff file path")
    parser.add_argument("--target", "-t", required=True, help="Target language code (e.g. zhTW)")
    parser.add_argument("--context", "-c",
                        help="Context hint for the API (e.g. 'Prep learning platform UI')")
    parser.add_argument("--output", "-o",
                        help="Output file path (default: overwrite input file)")
    parser.add_argument("--force", action="store_true",
                        help="Retranslate all units, including those already at state=final")
    parser.add_argument("--rerun", action="store_true",
                        help="Clear saved progress and restart from scratch")
    parser.add_argument("--content-type", default="ui_heading",
                        help="API content_type hint: ui_button, ui_heading, subtitle, legal, cta "
                             "(default: ui_heading)")
    parser.add_argument("--domain", default="education",
                        help="API domain: education, tech, marketing, legal, general "
                             "(default: education)")
    parser.add_argument("--intent", default="transcreation_ux",
                        help="API intent: literal, pedagogical, transcreation_marketing, "
                             "transcreation_ux, legal (default: transcreation_ux)")
    parser.add_argument("--vocab-mode", default="preserve",
                        help="preserve = English stays Latin-only; bilingual = word (翻譯) "
                             "(default: preserve)")
    parser.add_argument("--teaching-lang", default="",
                        help="Activates language-learning mode (e.g. English). "
                             "Usually off for UI strings.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print API audit info (S5 decisions, L2 fixes, confidence)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT})")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        # Try relative to project root
        alt = PROJECT_ROOT / args.input
        if alt.exists():
            input_path = alt
        else:
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)

    output_path = Path(args.output) if args.output else None
    teaching_lang = args.teaching_lang.strip() or None

    print(f"Pipeline: API V11 / Pipeline V10")
    print(f"  target={args.target}, content_type={args.content_type}, "
          f"domain={args.domain}, intent={args.intent}, vocab_mode={args.vocab_mode}")
    if teaching_lang:
        print(f"  teaching_lang={teaching_lang}")
    if args.verbose:
        print("  verbose=ON")
    print()

    failed = process_xliff(
        input_path=input_path,
        target_lang=args.target,
        context=args.context,
        teaching_lang=teaching_lang,
        content_type=args.content_type,
        domain=args.domain,
        intent=args.intent,
        vocab_mode=args.vocab_mode,
        verbose=args.verbose,
        timeout=args.timeout,
        rerun=args.rerun,
        force=args.force,
        output_path=output_path,
    )

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
