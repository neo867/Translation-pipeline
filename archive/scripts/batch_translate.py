#!/usr/bin/env python3
"""
batch_translate.py – Automate translation of explanation, subtitle, and UI CSV files

This script scans the "Test Case/Testing Output/English" directory for English CSV files
and runs ``translate_csv.py`` for each target language, saving outputs to "Test Case/Testing Output".

Supported target languages: tw, cn, kr, id, jp, th, vi, pt, es, mx, fr, de, it, ru.
Presets are inferred from the filename.
"""

import subprocess
import sys
import argparse
from pathlib import Path
from tqdm import tqdm

# Import TARGET_LANG_MAP from translate_csv to avoid duplication
from translate_csv import TARGET_LANG_MAP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DEFAULT_BASE_SEARCH = BASE_DIR.parent / "Test Case"

# Default target languages (common set)
DEFAULT_TARGET_LANGS = ["tw", "cn", "kr", "id", "jp", "th", "vi"]

# Map filename patterns to the preset argument for translate_csv.py
PRESET_MAP = {
    "explain": "explanation",
    "sub-": "subtitle",
    "ui": "ui",
}

TRANSLATE_SCRIPT = BASE_DIR / "translate_csv.py"

# ---------------------------------------------------------------------------
def infer_preset(csv_path: Path) -> str:
    """Return the appropriate preset based on the filename."""
    name = csv_path.name.lower()
    for pattern, preset in PRESET_MAP.items():
        if pattern in name:
            return preset
    # Default to auto-detect if no pattern matches
    return "auto"

# ---------------------------------------------------------------------------
def run_translation(input_csv: Path, target_lang: str, preset: str, output_dir: Path) -> int:
    """Execute translate_csv.py for a single language/preset."""
    output_path = output_dir / f"{target_lang}_{input_csv.name}"
    
    cmd = [
        sys.executable,
        str(TRANSLATE_SCRIPT),
        "--input", str(input_csv),
        "--target-lang", target_lang,
        "--output", str(output_path),
    ]
    if preset != "auto":
        cmd.extend(["--preset", preset])
    
    print(f"\n=== Translating {input_csv.name} -> {target_lang} (preset={preset}) ===")
    try:
        result = subprocess.run(cmd, cwd=BASE_DIR.parent)
        return result.returncode
    except Exception as e:
        print(f"[ERROR] Failed to run translation: {e}", file=sys.stderr)
        return 1

# ---------------------------------------------------------------------------
def select_directory() -> Path:
    """Interactively select a directory from DEFAULT_BASE_SEARCH."""
    if not DEFAULT_BASE_SEARCH.exists():
        print(f"Warning: {DEFAULT_BASE_SEARCH} not found. Please enter a path manually.")
        path_str = input("Enter path to folder containing CSVs: ").strip()
        return Path(path_str).resolve()

    subdirs = [d for d in DEFAULT_BASE_SEARCH.iterdir() if d.is_dir() and not d.name.startswith(".")]
    subdirs.sort()

    print("\nSelect a folder to translate:")
    for i, d in enumerate(subdirs):
        print(f"  {i+1}. {d.name}")
    print(f"  {len(subdirs)+1}. [Enter Custom Path]")

    choice = input(f"\nPick a number (1-{len(subdirs)+1}): ").strip()
    if not choice:
        return subdirs[0] # Default to first one if empty
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(subdirs):
            return subdirs[idx]
        else:
            path_str = input("Enter custom path: ").strip()
            return Path(path_str).resolve()
    except ValueError:
        return Path(choice).resolve()

# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Batch translate CSV files using translate_csv.py")
    parser.add_argument("--dir", help="Path to folder containing CSVs (skips interactive selection)")
    parser.add_argument("--langs", help="Comma-separated list of target language codes (e.g., kr,id,jp).")
    args = parser.parse_args()

    # 1. Determine Input Directory
    if args.dir:
        input_dir = Path(args.dir).resolve()
    else:
        input_dir = select_directory()

    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory.")
        sys.exit(1)

    # 2. Determine Output Directory (Same as input or a sibling 'Translated' folder)
    # For now, let's put it in an 'Output' folder inside the input dir, or just the input dir itself.
    output_dir = input_dir
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # 3. Determine Languages
    if args.langs:
        target_langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    else:
        print("\nAvailable languages: tw, cn, kr, id, jp, th, vi, pt, es, mx, fr, de, it, ru")
        user_input = input("Enter language codes (comma-separated) or press Enter for defaults (tw,cn,kr,id,jp,th,vi): ")
        if user_input.strip():
            target_langs = [l.strip() for l in user_input.split(",") if l.strip()]
        else:
            target_langs = DEFAULT_TARGET_LANGS

    # Verify script exists
    if not TRANSLATE_SCRIPT.is_file():
        print(f"Error: {TRANSLATE_SCRIPT} not found.", file=sys.stderr)
        sys.exit(1)

    # 4. Discover CSV files
    csv_files = sorted(list(input_dir.glob("*.csv")))
    # Filter out files that already have a language prefix (to avoid re-translating translations)
    # We'll skip files starting with any of our target lang codes followed by an underscore
    lang_prefixes = tuple(f"{l}_" for l in list(TARGET_LANG_MAP.keys()))
    
    # Also skip files if they already look like a translation output (optional, but safer)
    files_to_process = [f for f in csv_files if not f.name.startswith(lang_prefixes)]
    
    if not files_to_process:
        print(f"No suitable CSV files found in {input_dir}")
        sys.exit(0)

    print(f"Found {len(files_to_process)} files to process.")

    # 5. Process each file
    for csv_file in files_to_process:
        preset = infer_preset(csv_file)
        for lang in tqdm(target_langs, desc=f"Overall progress for {csv_file.name}"):
            rc = run_translation(csv_file, lang, preset, output_dir)
            if rc != 0:
                print(f"[WARN] Failed: {csv_file.name} -> {lang} (Exit code {rc})")

    print("\nBatch translation completed.")

if __name__ == "__main__":
    main()
