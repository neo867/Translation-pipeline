#!/usr/bin/env python3 -u
from __future__ import annotations
"""
translate_srt.py — Translate an SRT subtitle file via the Translation API V11 (Pipeline V10).

Supports S5 deterministic selector, L2 fixes, 3-pattern preservation,
Qwen 3.6-35B model, and 210 language pairs (15 languages, N×N routing).

Resume-safe: saves progress after each batch chunk. Re-run the same command to continue
from where it left off. Use --rerun to clear progress and start fresh.

Usage:
    python3 translate_srt.py --target zhTW --context "IELTS course"
    python3 translate_srt.py video.srt --target zhTW --target ko
    python3 translate_srt.py --folder input/ --target zhTW --batch 5
    python3 translate_srt.py --folder input/EN\ Reading\ Inter\ 2.6/ --target zhTW,ko,ja
    python3 translate_srt.py --target zhTW --teaching-lang English --domain education
    python3 translate_srt.py --target zhTW --vocab-mode bilingual --verbose
    python3 translate_srt.py --target zhTW --rerun

Output goes to output/ mirroring input folder structure: output/<subfolder>/<LANG>_original.srt
Progress is saved to output/<subfolder>/.<LANG>_original.progress.json (deleted on clean finish).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, List

import requests

API_BASE = "https://translate.flowb.ai"
API_KEY = "tw-localizer-dev-a1b2c3d4e5f6"
BATCH_API_SIZE = 5

# Default timeout increased for Pipeline v10 (S5 + L2 add latency)
DEFAULT_TIMEOUT = 180

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"


def parse_srt(text: str):
    """Parse SRT into list of blocks: {index, timestamp, lines[]}"""
    blocks = []
    raw_blocks = re.split(r"\n\n+", text.strip())
    for raw in raw_blocks:
        parts = raw.strip().splitlines()
        if len(parts) < 3:
            continue
        try:
            index = int(parts[0].strip())
        except ValueError:
            continue
        timestamp = parts[1].strip()
        lines = parts[2:]
        blocks.append({"index": index, "timestamp": timestamp, "lines": lines})
    return blocks


def write_srt(blocks: list) -> str:
    parts = []
    for block in blocks:
        lines = "\n".join(block["lines"])
        parts.append(f"{block['index']}\n{block['timestamp']}\n{lines}")
    return "\n\n".join(parts) + "\n"


def _post_with_retry(endpoint: str, payload: dict, timeout: int, max_retries: int) -> dict:
    """POST to API with 503 retry and timeout backoff. Returns parsed JSON."""
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


def translate_single(
    text: str,
    target_lang: str,
    context: Optional[str] = None,
    teaching_lang: Optional[str] = "English",
    content_type: str = "subtitle",
    domain: str = "education",
    intent: str = "pedagogical",
    vocab_mode: str = "preserve",
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 10,
) -> str:
    """Translate a single text with FALLBACK_ORIGINAL retry."""
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
            print(
                f"  [warn] pipeline crash (backend 503) — waiting {wait}s before retry "
                f"({attempt + 1}/{max_retries})",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue
        return result.get("translation", "")
    return ""


def translate_batch_chunk(
    texts: List[str],
    target_lang: str,
    context: Optional[str] = None,
    teaching_lang: Optional[str] = "English",
    content_type: str = "subtitle",
    domain: str = "education",
    intent: str = "pedagogical",
    vocab_mode: str = "preserve",
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 10,
) -> tuple[list[str], bool]:
    """Send one batch, retry fallbacks as mini-batch, then fall back to single on failure."""

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

    def _is_fallback(item: dict, source_text: str) -> bool:
        translation = item.get("translation", "")
        warnings = item.get("warnings", [])
        return (
            "error" in item
            or "FALLBACK_ORIGINAL" in str(warnings)
            or translation == source_text
        )

    result = _post_with_retry("/translate/batch", _make_payload(texts), timeout, max_retries)
    items = result.get("results", [])
    while len(items) < len(texts):
        items.append({})

    if verbose:
        for r in items:
            if "audit" in r:
                audit = r["audit"]
                st = audit.get("stage_timings", {})
                s5 = st.get("s5_decision", "n/a")
                s5_reason = st.get("s5_reason", "")
                l2 = st.get("l2_fixes", [])
                conf = r.get("confidence", "n/a")
                overrode = st.get("s5_overrode_final", False)
                had_rev = st.get("had_revision", False)
                info_parts = [f"S5={s5}"]
                if overrode:
                    info_parts.append("S5-OVERRODE")
                if had_rev:
                    info_parts.append("revised")
                if l2:
                    info_parts.append(f"L2={','.join(l2)}")
                info_parts.append(f"conf={conf}")
                print(f"    [{' | '.join(info_parts)}] {s5_reason}")

    fallback_indices = [i for i, item in enumerate(items) if _is_fallback(item, texts[i])]
    had_fallbacks = bool(fallback_indices)

    if fallback_indices:
        print(
            f"  [warn] {len(fallback_indices)} item(s) fallback — waiting 15s then retrying as mini-batch",
            file=sys.stderr,
        )
        time.sleep(15)
        retry_texts = [texts[i] for i in fallback_indices]
        retry_result = _post_with_retry(
            "/translate/batch", _make_payload(retry_texts), timeout, max_retries
        )
        retry_items = retry_result.get("results", [])
        while len(retry_items) < len(retry_texts):
            retry_items.append({})

        for list_pos, original_idx in enumerate(fallback_indices):
            retry_item = retry_items[list_pos]
            if not _is_fallback(retry_item, texts[original_idx]):
                items[original_idx] = retry_item
            else:
                print(
                    f"  [warn] mini-batch retry failed — falling back to single",
                    file=sys.stderr,
                )
                translation = translate_single(
                    texts[original_idx],
                    target_lang=target_lang,
                    context=context,
                    teaching_lang=teaching_lang,
                    content_type=content_type,
                    domain=domain,
                    intent=intent,
                    vocab_mode=vocab_mode,
                    timeout=timeout,
                    max_retries=max_retries,
                )
                items[original_idx] = {"translation": translation}

    translations = [item.get("translation", "") for item in items]
    return translations, had_fallbacks


def translate_blocks(
    blocks: list,
    target_lang: str,
    context: Optional[str] = None,
    teaching_lang: Optional[str] = "English",
    content_type: str = "subtitle",
    domain: str = "education",
    intent: str = "pedagogical",
    vocab_mode: str = "preserve",
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    progress_path: Optional[Path] = None,
) -> tuple[list, int]:
    """Translate all subtitle text, preserving structure.

    Returns (translated_blocks, failed_count).
    Saves progress after each chunk so interrupted runs can resume.
    """
    items = []
    for bi, block in enumerate(blocks):
        for li, line in enumerate(block["lines"]):
            stripped = line.strip()
            if stripped:
                items.append((bi, li, stripped))

    # Load existing progress — keys are "bi_li" strings in JSON, tuples in memory
    translations: dict[tuple[int, int], str] = {}
    if progress_path and progress_path.exists():
        try:
            saved = json.loads(progress_path.read_text(encoding="utf-8"))
            for k, v in saved.items():
                bi_s, li_s = k.split("_", 1)
                translations[(int(bi_s), int(li_s))] = v
        except Exception:
            translations = {}

    # Pending = not yet translated or previously failed (empty string)
    pending = [(bi, li, t) for bi, li, t in items if not translations.get((bi, li), "")]
    total = len(items)
    done_count = total - len(pending)

    if done_count:
        print(f"  Resuming: {done_count} already done, {len(pending)} remaining.")
    if not pending:
        print("  All lines already translated.")

    failed_count = 0

    for start in range(0, len(pending), BATCH_API_SIZE):
        chunk = pending[start: start + BATCH_API_SIZE]
        texts = [t for _, _, t in chunk]
        chunk_start = done_count + start + 1
        chunk_end = done_count + start + len(chunk)
        print(f"  [{chunk_start}–{chunk_end}/{total}] sending batch of {len(chunk)}...")

        had_fallbacks = False
        try:
            translated, had_fallbacks = translate_batch_chunk(
                texts, target_lang,
                context=context,
                teaching_lang=teaching_lang,
                content_type=content_type,
                domain=domain,
                intent=intent,
                vocab_mode=vocab_mode,
                verbose=verbose,
                timeout=timeout,
            )
        except Exception as e:
            print(f"  [batch FAILED] {e}", file=sys.stderr)
            translated = [""] * len(chunk)

        for (bi, li, src), tr in zip(chunk, translated):
            if tr and tr != src:
                translations[(bi, li)] = tr
            else:
                translations[(bi, li)] = ""
                failed_count += 1
                print(f"  [FAILED] block {bi} line {li}: {src[:60]}", file=sys.stderr)

        # Save progress after every chunk
        if progress_path:
            progress_data = {f"{bi}_{li}": v for (bi, li), v in translations.items()}
            progress_path.write_text(
                json.dumps(progress_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        if start + BATCH_API_SIZE < len(pending):
            inter_sleep = 15 if had_fallbacks else 3
            if had_fallbacks:
                print(f"  [cooldown] fallbacks — waiting {inter_sleep}s before next batch")
            time.sleep(inter_sleep)

    # Reconstruct blocks with translations (fall back to original line if failed)
    result = []
    for bi, block in enumerate(blocks):
        new_lines = []
        for li, line in enumerate(block["lines"]):
            if line.strip():
                tr = translations.get((bi, li), "")
                new_lines.append(tr if tr else line)
            else:
                new_lines.append(line)
        result.append({**block, "lines": new_lines})
    return result, failed_count


def process_file(
    input_path: Path,
    targets: List[str],
    context: Optional[str] = None,
    teaching_lang: Optional[str] = "English",
    content_type: str = "subtitle",
    domain: str = "education",
    intent: str = "pedagogical",
    vocab_mode: str = "preserve",
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    rerun: bool = False,
    output_dir: Optional[Path] = None,
):
    """Translate a single file to all target languages."""
    print(f"Parsing {input_path.name}...")
    text = input_path.read_text(encoding="utf-8-sig")
    blocks = parse_srt(text)
    print(f"  {len(blocks)} subtitle blocks found.")

    for target in targets:
        if output_dir is not None:
            out_dir = output_dir
        else:
            try:
                rel_parent = input_path.resolve().relative_to(PROJECT_ROOT.resolve()).parent
            except ValueError:
                rel_parent = Path(".")
            out_dir = OUTPUT_DIR / rel_parent
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{target}_{input_path.name}"
        progress_path = out_dir / f".{target}_{input_path.stem}.progress.json"

        if rerun and progress_path.exists():
            progress_path.unlink()
            print(f"  --rerun: cleared progress for {target}.")

        print(f"Translating to {target}...")
        translated_blocks, failed_count = translate_blocks(
            blocks, target, context,
            teaching_lang=teaching_lang,
            content_type=content_type,
            domain=domain,
            intent=intent,
            vocab_mode=vocab_mode,
            verbose=verbose,
            timeout=timeout,
            progress_path=progress_path,
        )
        print(f"Writing {output_path}...")
        output_path.write_text(write_srt(translated_blocks), encoding="utf-8")

        # Clean up progress file on clean finish
        if failed_count == 0 and progress_path.exists():
            progress_path.unlink()

        print(f"Done. -> {output_path}")
        if failed_count:
            print(f"  {failed_count} line(s) failed — re-run the same command to retry them.")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Translate SRT subtitle files — API V11 / Pipeline V10 (Qwen 3.6, S5 selector, L2 fixes).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported languages (15, N×N = 210 pairs):
  en, zhTW, zhCN, ko, vi, id, th, ja, pt, esES, esMX, fr, de, it, ru

Examples:
  python3 translate_srt.py --target zhTW --context "IELTS course"
  python3 translate_srt.py --input file1.srt --input file2.srt --target zhTW --context "IELTS course"
  python3 translate_srt.py --target zhTW --teaching-lang English --verbose
  python3 translate_srt.py --folder input/ --target zhTW,ko,ja --batch 5
  python3 translate_srt.py --target zhTW --vocab-mode bilingual
  python3 translate_srt.py --target zhTW --rerun
""",
    )
    parser.add_argument("input", nargs="?", help="Input .srt file (default: first .srt in input/)")
    parser.add_argument("--input", "-i", dest="inputs", action="append", metavar="FILE",
                        help="Input .srt file (repeatable for multiple files)")
    parser.add_argument("--folder", "-f", help="Folder containing .srt files (processes all .srt files)")
    parser.add_argument("--target", "-t", action="append", required=True,
                        help="Target language code(s): zhTW, zhCN, ko, vi, id, th, ja, pt, esES, esMX, fr, de, it, ru (comma-separated or repeated)")
    parser.add_argument("--context", "-c", help="Domain context (e.g., 'IELTS course', 'Movie subtitles')")
    parser.add_argument("--batch", "-b", type=int, default=0, help="Process N files at a time (0=all at once)")
    parser.add_argument("--rerun", action="store_true",
                        help="Clear saved progress and retranslate from scratch")

    # --- API v11 / Pipeline v10 pedagogical params ---
    parser.add_argument("--teaching-lang", default="English",
                        help="Teaching language for Pattern 2 preservation (default: English). "
                             "Keeps English vocab in Latin script. Set to empty string to disable.")
    parser.add_argument("--content-type", default="subtitle",
                        help="Content type hint (default: subtitle). Options: subtitle, ui_button, ui_heading, legal, cta")
    parser.add_argument("--domain", default="education",
                        help="Content domain (default: education). Options: education, legal, tech, medical, finance, marketing")
    parser.add_argument("--intent", default="pedagogical",
                        help="Translation intent (default: pedagogical). Options: pedagogical, literal, transcreation_marketing, transcreation_ux, legal")
    parser.add_argument("--vocab-mode", default="preserve",
                        help="Vocab mode (default: preserve). "
                             "'preserve' = English stays in Latin only; "
                             "'bilingual' = English_word (target_translation)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Include audit info (S5 selector decisions, L2 fixes, confidence)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--output-dir", "-o", help="Custom output directory (overrides default output/ mirroring)")

    args = parser.parse_args()

    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    context = args.context
    if not context:
        print("\n" + "="*50)
        print("CONTEXT REMINDER")
        print("="*50)
        context_input = input("Enter context (or press Enter to skip): ").strip()
        if context_input:
            context = context_input
            print(f"Using context: {context}")
        else:
            print("No context set - using default translation")
        print("="*50 + "\n")

    teaching_lang = args.teaching_lang if args.teaching_lang else None

    targets = []
    for t in args.target:
        targets.extend([x.strip() for x in t.split(",")])
    targets = [t.strip() for t in targets if t.strip()]
    if not targets:
        print("Error: at least one target language required", file=sys.stderr)
        sys.exit(1)

    print(f"Pipeline: API V11 / Pipeline V10 (Qwen 3.6)")
    print(f"  teaching_lang={teaching_lang or 'off'}, content_type={args.content_type}, "
          f"domain={args.domain}, intent={args.intent}, vocab_mode={args.vocab_mode}")
    if args.verbose:
        print(f"  verbose=ON (audit logging enabled)")
    if args.rerun:
        print(f"  --rerun: will clear saved progress before translating")
    print()

    output_dir = Path(args.output_dir) if args.output_dir else None

    translate_kwargs = dict(
        teaching_lang=teaching_lang,
        content_type=args.content_type,
        domain=args.domain,
        intent=args.intent,
        vocab_mode=args.vocab_mode,
        verbose=args.verbose,
        timeout=args.timeout,
        rerun=args.rerun,
        output_dir=output_dir,
    )

    if args.folder:
        folder_path = Path(args.folder)
        if not folder_path.exists():
            folder_path = INPUT_DIR / folder_path

        if not folder_path.exists():
            print(f"Error: folder not found: {folder_path}", file=sys.stderr)
            sys.exit(1)

        srt_files = sorted(folder_path.glob("*.srt"))
        if not srt_files:
            print(f"Error: no .srt files in {folder_path}", file=sys.stderr)
            sys.exit(1)

        total_files = len(srt_files)
        batch_size = args.batch if args.batch > 0 else total_files

        print(f"Found {total_files} .srt files in {folder_path}")
        print(f"Processing in batches of {batch_size}...")
        print(f"Targets: {', '.join(targets)}\n")

        for i in range(0, total_files, batch_size):
            batch_files = srt_files[i:i + batch_size]
            print(f"=== Batch {i // batch_size + 1}: files {i+1}-{min(i+batch_size, total_files)} ===")
            for f in batch_files:
                process_file(f, targets, context, **translate_kwargs)
            if i + batch_size < total_files:
                print(f"--- Batch complete, pausing before next batch ---")
                time.sleep(2)

        print(f"\nAll done! {total_files} files processed.")

    elif args.inputs:
        if len(args.inputs) > 20:
            print(f"Error: queue limit is 20 files, got {len(args.inputs)}. Split into multiple runs.", file=sys.stderr)
            sys.exit(1)

        input_paths = []
        for raw in args.inputs:
            p = Path(raw)
            if not p.exists():
                p = INPUT_DIR / raw
            if not p.exists():
                print(f"Error: file not found: {raw}", file=sys.stderr)
                sys.exit(1)
            input_paths.append(p)

        total_files = len(input_paths)
        print(f"Queue: {total_files} file(s)\n")
        for i, p in enumerate(input_paths, 1):
            print(f"=== [{i}/{total_files}] {p.name} ===")
            process_file(p, targets, context, **translate_kwargs)

        print(f"All done! {total_files} file(s) processed.")

    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            input_path = INPUT_DIR / args.input
        if not input_path.exists():
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        process_file(input_path, targets, context, **translate_kwargs)

    else:
        srt_files = sorted(INPUT_DIR.glob("*.srt"))
        if not srt_files:
            print(f"Error: no .srt files found in {INPUT_DIR}", file=sys.stderr)
            sys.exit(1)
        process_file(srt_files[0], targets, context, **translate_kwargs)


if __name__ == "__main__":
    main()
