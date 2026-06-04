#!/usr/bin/env python3
"""Phase 1: Apply mechanical substitutions to all *_revised.srt files."""

import os
import glob
import re

FINAL_DIR = "/Users/prep-ea/Documents/Translation Pipeline/output/IE Intermediate 2.6/Listening Int/zhTW/final"

SUBSTITUTIONS = [
    ("詞彙", "字彙"),
    ("堂課", "單元"),
    ("播客", "Podcast"),
    ("發言者", "說話者"),
    ("惠靈頓", "威靈頓"),
    ("部分匹配", "部分符合"),
    ("同義詞", "同義字"),
    ("文法變化", "詞性變化"),
    ("瞭解", "了解"),
]

files = sorted(glob.glob(os.path.join(FINAL_DIR, "*_revised.srt")))
print(f"Found {len(files)} *_revised.srt files.\n")

total_changes = 0

for filepath in files:
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    updated = original
    file_changes = []

    for old, new in SUBSTITUTIONS:
        count = updated.count(old)
        if count > 0:
            updated = updated.replace(old, new)
            file_changes.append(f"  '{old}' → '{new}': {count} occurrence(s)")
            total_changes += count

    if file_changes:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"[CHANGED] {filename}")
        for change in file_changes:
            print(change)
    else:
        print(f"[no change] {filename}")

print(f"\nDone. Total substitutions made: {total_changes}")
