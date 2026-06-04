#!/usr/bin/env python3
"""
batch_zhTW_fix.py — Run zhTW_mechanical_fix.py across all zhTW SRT files in a folder.

Finds every zhTW_*.srt (excluding already-revised files) and applies mechanical fixes
(Rules 1, 2, 6: IELTS→雅思, 您→你, _revised suffix). Prints a summary per file.

Usage:
    python3 scripts/batch_zhTW_fix.py "output/IE Intermediate 2.6/Listening Int"
    python3 scripts/batch_zhTW_fix.py output/                         # all subfolders
    python3 scripts/batch_zhTW_fix.py output/ --dry-run               # preview only
    python3 scripts/batch_zhTW_fix.py output/ --skip-existing         # skip if _revised.srt exists
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
FIX_SCRIPT = SCRIPT_DIR / "zhTW_mechanical_fix.py"


def find_srt_files(root: Path) -> list[Path]:
    """Return all zhTW_*.srt files under root, excluding *_revised.srt."""
    return sorted(
        p for p in root.rglob("zhTW_*.srt")
        if not p.stem.endswith("_revised")
    )


def revised_path(srt: Path) -> Path:
    return srt.parent / f"{srt.stem}_revised{srt.suffix}"


def main():
    parser = argparse.ArgumentParser(
        description="Batch-apply zhTW mechanical fixes to all zhTW SRT files in a folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/batch_zhTW_fix.py "output/IE Intermediate 2.6/Listening Int"
  python3 scripts/batch_zhTW_fix.py output/ --dry-run
  python3 scripts/batch_zhTW_fix.py output/ --skip-existing
""",
    )
    parser.add_argument("folder", help="Folder to search for zhTW_*.srt files (searched recursively)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files where _revised.srt already exists")
    args = parser.parse_args()

    root = Path(args.folder)
    if not root.exists():
        print(f"Error: folder not found: {root}", file=sys.stderr)
        sys.exit(1)

    files = find_srt_files(root)
    if not files:
        print(f"No zhTW_*.srt files found under: {root}")
        sys.exit(0)

    if args.skip_existing:
        skipped = [f for f in files if revised_path(f).exists()]
        files = [f for f in files if not revised_path(f).exists()]
        if skipped:
            print(f"Skipping {len(skipped)} already-revised file(s).")

    print(f"Found {len(files)} file(s) to process.\n")

    total_ielts = 0
    total_nin = 0
    total_blocks = 0
    errors = []

    for i, srt in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {srt.relative_to(root.parent) if root.parent != root else srt.name}")
        cmd = [sys.executable, str(FIX_SCRIPT), str(srt)]
        if args.dry_run:
            cmd.append("--dry-run")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            errors.append(srt)
            continue

        output = result.stdout.strip()
        # Parse summary lines for aggregate totals
        for line in output.splitlines():
            if "IELTS → 雅思" in line:
                try:
                    total_ielts += int(line.split(":")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass
            elif "您 → 你" in line:
                try:
                    total_nin += int(line.split(":")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass
            elif "Blocks changed" in line:
                try:
                    total_blocks += int(line.split(":")[1].strip())
                except (IndexError, ValueError):
                    pass
            # Print per-file stats (indented)
            if any(x in line for x in ["Rule 1", "Rule 2", "Blocks changed", "Saved →", "dry-run"]):
                print(f"  {line.strip()}")

        print()

    # Aggregate summary
    print("=" * 50)
    print("Batch complete")
    print(f"  Files processed:        {len(files) - len(errors)}")
    if errors:
        print(f"  Files with errors:      {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    print(f"  Total IELTS → 雅思:     {total_ielts}")
    print(f"  Total 您 → 你:           {total_nin}")
    print(f"  Total blocks changed:   {total_blocks}")

    if not args.dry_run:
        print(f"\nNext step: open the _revised.srt files in Claude Code for a naturalness pass (Rule 3).")


if __name__ == "__main__":
    main()
