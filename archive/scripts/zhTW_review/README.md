# zhTW Subtitle Review — Start to Finish

Two-step process: a script handles all mechanical fixes first, then Claude Code does a naturalness pass.

---

## Files in this folder

| File | Purpose |
|------|---------|
| `zhTW_review_rules.md` | Source of truth for all review rules |
| `zhTW_mechanical_fix.py` | Applies Rules 1, 2, 6, 7 to a single SRT file |
| `batch_zhTW_fix.py` | Runs the mechanical fix across a whole folder |
| `review/review_examples.md` | Curated before/after pairs from native TW speaker reviews |
| `review/*.xlsx` | Raw reviewer feedback files (L1S1, L2S1, L2S2) |

---

## Step 1 — Translate (existing pipeline)

Run as normal. Output lands in `output/` mirroring the source folder structure:

```
output/IE Intermediate 2.6/Listening Int/zhTW_L1S1.srt
```

---

## Step 2 — Mechanical fix (script)

Applies deterministically:
- **Rule 1:** IELTS → 雅思 (keeps "IELTS Academic" / "IELTS General Training" as-is)
- **Rule 2:** 您 → 你 (instructor-to-student register)
- **Rule 6:** Saves output as `<name>_revised.srt` in the same folder
- **Rule 7:** 『』→ 「」(TW-standard quotation marks)

**Single file:**
```bash
python3 scripts/zhTW_review/zhTW_mechanical_fix.py "output/IE Intermediate 2.6/Listening Int/zhTW_L1S1.srt"
```

**Dry-run first (recommended):**
```bash
python3 scripts/zhTW_review/zhTW_mechanical_fix.py "output/.../zhTW_L1S1.srt" --dry-run
```

**Whole folder (batch):**
```bash
python3 scripts/zhTW_review/batch_zhTW_fix.py "output/IE Intermediate 2.6/Listening Int"
```

**Whole output folder, skip already-revised:**
```bash
python3 scripts/zhTW_review/batch_zhTW_fix.py output/ --skip-existing
```

Output: `zhTW_L1S1_revised.srt` saved next to the original.

---

## Step 3 — Naturalness pass (Claude Code)

Open the `_revised.srt` file in Claude Code and say:

> "Apply Rules 3 and 8 from `scripts/zhTW_review/zhTW_review_rules.md` to this file — rewrite any stiff or overly literal phrasing to sound natural in spoken Taiwanese Mandarin. Use `scripts/zhTW_review/review/review_examples.md` as a reference for concrete correction patterns. Edit the file directly."

Claude Code will rewrite awkward constructions in-place. Review the diff before saving.

Rules 4 and 5 (keep technical English terms and accent names) are reminders for the naturalness pass — Claude Code will not touch those.

---

## Summary

```
translate_srt.py  →  batch_zhTW_fix.py        →  Claude Code naturalness pass
(Step 1: translate)   (Step 2: mechanical)        (Step 3: phrasing judgment)
                      Rules 1,2,6,7 auto-fixed    Rules 3,8 + review_examples.md
```

**Quality target:** Naturalness ≥ 90/100 (per TW reviewer scoring baseline). Accuracy is generally high; naturalness is the main gap.
