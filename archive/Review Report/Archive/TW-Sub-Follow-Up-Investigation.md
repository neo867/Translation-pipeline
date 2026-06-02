# TW Subtitle Follow-Up Investigation
**Date:** 2026-05-11  
**Input file:** `Test Case/Testing Output/English/tw_sub-50-eng.csv`  
**Reference:** TW-MiLo-Evaluation-Report.md (MiLo human review)

---

## Purpose

After receiving MiLo's evaluation, the subtitle pipeline was re-run on the same 50-segment source file to check whether the identified problems carried over into new output. This document records what was fixed, what remains broken, and the two outstanding root causes that need resolution.

---

## What Changed

### Fixed

| Issue from MiLo review | New output |
|---|---|
| Grammar meta-terms left in English (nouns, verbs, adjectives…) | **Resolved.** S33–35 now correctly render 名詞, 動詞, 形容詞, 副詞, 代名詞, 介詞 |
| Negation dropped ("isn't meant to cover") | **Resolved.** S37 correctly preserves 並非 |
| General translationese tone | **Partially improved** in several segments |

---

## What Is Still Broken

### Problem 1 — Split-sentence fragments (15 segments affected)

**Root cause:** Segments are still being translated one at a time. English sentences frequently span 2–4 subtitle segments; when each segment is translated without knowledge of its neighbours, the output is either a dangling fragment or a semantically wrong standalone sentence.

**Critical examples:**

| Segment(s) | Source | Translation | Issue |
|---|---|---|---|
| S5 | `…I truly believe that getting to know` | `…而我真心相信，認識` | Ends on a bare verb — no continuation |
| S9 | `we'll be taking in this course.` | `我們將在這個 course 中進行學習。` | Should be joined to S8; reads as a new sentence |
| S25/S26 | `…creating your own basic sentences` / `that are grammatically correct.` | `…建立自己的 basic sentences。` / `在文法上是正確的。` | S26 is a relative clause orphaned from S25 |
| S38/S39 | `…really require a strong foundation` / `in pronunciation and vocabulary before you can tackle them effectively.` | `有些領域相當複雜，確實需要扎實的基礎。` / `在發音和詞彙方面，在你能夠有效處理它們之前。` | S39 is a prepositional phrase with no head sentence |
| **S44/S45** | `…our approach here at Prep is a little different` / `from traditional grammar classes.` | `我們在 Prep 的方法略有不同` / `來自傳統的語法課程。` | **Exact example flagged by MiLo.** "different from" split across segments; translator sees only "from traditional grammar classes." and renders it as 來自 (originates from) instead of 與傳統語法課程不同 |

The S44/S45 case is the clearest diagnostic: if cross-segment context were working, S45 would have S44 as context and would never produce `來自`. The fact that it still does strongly suggests the batch endpoint is not passing segment context in a way that bridges sentence boundaries.

**Total affected:** S3, S5, S9, S15, S17–S19, S20–S22, S25–S26, S27–S28, S38–S39, S44–S45, S47–S48 — 15 of 50 segments.

---

### Problem 2 — English meta-terms still not translated in some segments

Grammar meta-terms were fixed in S33–35 but remain in English elsewhere in the same file:

| Segment | Term left in English | Expected TW |
|---|---|---|
| S9 | `course` | 課程 |
| S21 | `sentences` | 句子 / 句型 |
| S25 | `basic sentences` | 基本句子 |
| S31 | `grammar` | 文法 |
| S49 | `grammar rules` | 文法規則 |

`Guided Discovery` (S50) is a named method/course and is acceptable to keep in English.

The inconsistency (translated in S33–35, not in S9/S21/S25/S31/S49) suggests the pipeline is making context-dependent decisions rather than following a blanket rule. The current `course_subtitle` context string does not explicitly instruct the translator to render grammar meta-terms in the target language.

---

## Two Actions Required

### Action 1 — Add explicit grammar meta-term rule to context string

**File:** `translate_csv.py`  
**Location:** `PRESETS` → `course_subtitle` → `"context"` field  
**Change:** Append the sentence:

> `"Translate all grammar meta-terms into the target language (nouns=名詞, verbs=動詞, adjectives=形容詞, adverbs=副詞, pronouns=代名詞, prepositions=介系詞, grammar rules=文法規則, sentence structure=句型結構, parts of speech=詞性). Course names (Basic Grammar, Basic Vocabulary, Guided Discovery) stay in Latin script."`

This is a one-line change. It closes the inconsistency without touching the pipeline architecture.

---

### Action 2 — Investigate and fix batch cross-segment context

**Observation:** The `/translate/batch` endpoint is being used with cross-segment context enabled, yet S44/S45 still produces a sentence-boundary error identical to the one MiLo flagged in the single-translate version. This means one of the following is true:

| Hypothesis | How to verify |
|---|---|
| A. The batch endpoint receives all texts but treats each item independently (no context window across items) | Log the raw API request and check if "context" in the payload is meaningful to the model, or if it's ignored for per-item translation |
| B. The 15-item gap between S44 and the start of the chunk means they land in different batches | Check chunk boundaries — if chunk 1 ends at S25 and chunk 2 starts at S26, S44/S45 are both in chunk 2 and should share context. Verify the batch payload for that chunk |
| C. The cross-segment context only applies within the model's attention window, which is too short for 25 segments | Reduce `BATCH_SIZE` to 10–15 and re-test |
| D. The pipeline processes batch items sequentially but resets context between items | Would require a server-side fix or a different endpoint |

**Recommended test:** Re-run just the 4 known split-sentence pairs (S8/S9, S44/S45, S25/S26, S38/S39) with `--no-batch` mode and compare. If `--no-batch` produces the same errors, the problem is purely the missing segment context. If `--no-batch` is actually better for some pairs, the batch endpoint is degrading quality for adjacent segments.

---

## Re-evaluation Target

Once both actions are applied, re-run the same 50 segments and score against the thresholds proposed in the evaluation report:

| Metric | Current | Target |
|---|---|---|
| Accuracy avg | ~69 (MiLo) | ≥ 80 |
| Naturalness avg | ~73 (MiLo) | ≥ 78 |
| Segments with accuracy < 70 | 11 / 50 | ≤ 3 / 50 |
| Split-sentence fragment errors | 15 / 50 | ≤ 3 / 50 |
