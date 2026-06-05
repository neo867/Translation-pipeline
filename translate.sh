#!/usr/bin/env bash
# Run the SRT translation pipeline. See translate_commands.md for full reference.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LANGS=()
FOLDER=""
EXTRA_ARGS=()

usage() {
  cat <<EOF
Usage: ./translate.sh <folder> --target <lang> [options]

Arguments:
  <folder>              Skill folder path, e.g. "IE Intermediate 2.6/Listening Int"
  --target <lang>       Language code (repeatable). e.g. --target zhTW --target id
  --skip-translate      Use existing drafts, skip translation step
  --skip-review         Skip review+finalize, run QA+fix only (implies --skip-translate)
  --force               Re-process already-finalized files
  --rerun               Force re-translate from scratch
  --strictness <level>  Review strictness: default | linguist

Language codes:
  zhTW  Traditional Chinese    id    Indonesian
  zhCN  Simplified Chinese     vi    Vietnamese
  ko    Korean                 th    Thai
  ja    Japanese               pt    Portuguese

Examples:
  ./translate.sh "IE Intermediate 2.6/Listening Int" --target zhTW
  ./translate.sh "IE Intermediate 2.6/Listening Int" --target zhTW --target id
  ./translate.sh "IE Intermediate 2.6/Listening Int" --target zhTW --skip-translate
  ./translate.sh "IE Intermediate 2.6/Listening Int" --target zhTW --force
  ./translate.sh "IE Intermediate 2.6/Listening Int" --target zhTW --strictness linguist
EOF
  exit 1
}

# Parse args
if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then usage; fi
FOLDER="$1"; shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      LANGS+=("$2"); shift 2 ;;
    --skip-translate|--skip-review|--force|--rerun)
      EXTRA_ARGS+=("$1"); shift ;;
    --strictness)
      EXTRA_ARGS+=("--strictness" "$2"); shift 2 ;;
    -h|--help)
      usage ;;
    *)
      echo "Unknown argument: $1"; usage ;;
  esac
done

if [[ ${#LANGS[@]} -eq 0 ]]; then
  echo "Error: at least one --target is required."
  usage
fi

TARGET_ARGS=()
for lang in "${LANGS[@]}"; do
  TARGET_ARGS+=("--target" "$lang")
done

echo "▶ Folder:  $FOLDER"
echo "▶ Targets: ${LANGS[*]}"
[[ ${#EXTRA_ARGS[@]} -gt 0 ]] && echo "▶ Flags:   ${EXTRA_ARGS[*]}"
echo ""

python3 scripts/run_pipeline.py "$FOLDER" "${TARGET_ARGS[@]}" "${EXTRA_ARGS[@]}"
