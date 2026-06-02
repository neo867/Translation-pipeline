# TW Translation Evaluation Report — MiLo
**Reviewer:** Human reviewer (MiLo)  
**Date:** 2026-05-11  
**Scoring guide:** Translation Quality Review — Scorer's Guide  
**Sample size:** 150 rows (50 per content type)

---

## Executive Summary

| Content Type | Avg Accuracy | Avg Naturalness | Status |
|---|---|---|---|
| UI Strings (`tw_ui_eng`) | **88.8** | **88.2** | Near production-ready |
| Subtitles (`tw_sub_eng`) | **69.3** | **72.7** | Needs significant rework |
| Explanations (`tw_explanation_eng`) | **85.6** | **82.0** | Acceptable, targeted fixes needed |

UI strings are strong. Subtitles have systemic problems rooted in how segments are fed to the translator. Explanations are mostly solid with isolated readability issues.

---

## Sheet 1: UI Strings (`tw_ui_eng`)

### Score Distribution

| Band | Accuracy | Naturalness |
|---|---|---|
| 90–100 | 45 / 50 (90%) | 44 / 50 (88%) |
| 80–89 | 3 / 50 (6%) | 2 / 50 (4%) |
| 70–79 | 1 / 50 (2%) | 3 / 50 (6%) |
| 60–69 | 1 / 50 (2%) | 1 / 50 (2%) |
| < 60 | 0 | 0 |

### Flagged Items

| Key | Issue | Reviewer Suggestion |
|---|---|---|
| `coupon_apply_not_successfully` | "application" mistranslated as 申請 (to apply for) instead of 套用/使用 | 優惠券應用已失敗 |
| `unavailable` | 無法使用 is too generic; context-dependent | Context-specific wording needed |
| `discount_conflict_with_current_coupon` | 活動 (event) is wrong word class for a promotion conflict message | Replace 活動 with 優惠 |
| `coupon_conflict_with_current_discount` | Same 活動 collocation error | Replace 活動 with 優惠 |
| `no_promo_yet` | "available" not translated — 無促銷代碼 misses the sense of "none available" | 無可用促銷代碼 |
| `empty_discount` | 活動 vs 計劃 mismatch with source "programs" | 促銷計劃 aligns better |

### Assessment
UI is the strongest content type. The 活動/優惠 word-choice error is a repeating collocation problem that needs a glossary entry. One semantic mistranslation (`coupon_apply_not_successfully`) requires correction before production.

---

## Sheet 2: Subtitles (`tw_sub_eng`)

### Score Distribution

| Band | Accuracy | Naturalness |
|---|---|---|
| 90–100 | 6 / 50 (12%) | 4 / 50 (8%) |
| 80–89 | 12 / 50 (24%) | 21 / 50 (42%) |
| 70–79 | 14 / 50 (28%) | 10 / 50 (20%) |
| 60–69 | 7 / 50 (14%) | 12 / 50 (24%) |
| < 60 | **11 / 50 (22%)** | 3 / 50 (6%) |

### Root Cause: Split-Sentence Problem

The single largest quality driver is that the translator receives subtitle segments one at a time without cross-segment context. English sentences frequently span 2–4 segments. Translating each segment in isolation produces:

- Fragments that are syntactically incomplete in Chinese
- Repeated partial clauses when segments overlap
- Misaligned meaning because the full sentence intent is not visible

**Examples:**

| Segments | English | Translation Issue |
|---|---|---|
| 11–13 | "My hope is that by the end of the session, you'll have a really clear picture of what lies ahead, and you'll feel comfortable with the team that's here to support you every step of the way." | Split into 3 rows → each partial translation scores 55; combined would score 85+ |
| 5–6 | "We've got quite a journey ahead of us, and I truly believe that getting to know each other a bit better will make this whole process smoother…" | Partial clause in seg 6 repeats "getting to know" from seg 5 |
| 43–44 | "You'll notice that our approach here at Prep is a little different from traditional grammar classes." | Seg 44 translated as 來自傳統的語法課程 — reads as "from traditional grammar classes" (standalone phrase, not a sentence) |

### Secondary Issues

**Grammar terms kept in English when they should be translated**  
Items like `nouns`, `verbs`, `adjectives`, `adverbs`, `pronouns`, `prepositions`, `grammar point`, `grammar rules` were left untranslated in subtitle lines where the Chinese learner needs the Chinese equivalent. These are descriptive labels, not English teaching tokens — they should be rendered as 名詞, 動詞, 形容詞, 副詞, 代名詞, 介系詞, 文法要點, 文法規則.

> **Note:** The preservation rule (English teaching words stay in English) applies to *target vocabulary being taught to the student*, not to meta-language describing grammar. "Practice the word 'horse'" → 'horse' stays. "We'll explore nouns and verbs" → should be translated.

**Translationese / AI tone**  
Multiple segments scored 60 on naturalness despite acceptable accuracy. Patterns:
- Literal calque of English structure (我們致力於賦予您力量 for "We're all about empowering you")
- Over-literal idioms (征服英語 for "conquer the language" — should be 攻克英語)
- Awkward pronoun use in Chinese: 那些, 它 where Chinese would repeat the noun

**One source-text gap noted**  
Segment 17 (`00:01:11,640`): The reviewer noted there appear to be missing words in the source text between "designed" and "truly understand" — this is a source integrity issue, not a translation error.

---

## Sheet 3: Explanations (`tw_explanation_eng`)

### Score Distribution

| Band | Accuracy | Naturalness |
|---|---|---|
| 90–100 | 29 / 50 (58%) | 12 / 50 (24%) |
| 80–89 | 13 / 50 (26%) | 29 / 50 (58%) |
| 70–79 | 5 / 50 (10%) | 5 / 50 (10%) |
| 60–69 | 3 / 50 (6%) | 3 / 50 (6%) |
| < 60 | 0 | 1 / 50 (2%) |

### Flagged Items

| ID | Issue | Reviewer Suggestion |
|---|---|---|
| 2 | Misread list structure: "several smaller ones, ponds and a stream" — translated as if ponds/stream are examples of "smaller ones" | 幾個較小的景點，幾口池塘和一條… |
| 3 | Literal translation throughout; heavy translationese | Full rewrite needed |
| 4 | 不易閱讀 (not readable) | Restructure sentence |
| 5 | Poor readability; naturalness 40 | 我認為，這是以您的 visitors 為重點 is awkward |
| 6 | Heavy translationese feel despite good accuracy (86) | Rewrite for fluency |
| 17 | "simply" left in English mid-sentence | 只是/根本 |
| 18 | "sunlight" not translated | 陽光 |
| 23 | "object" not translated | 受詞 |
| 39 | Completion object missing: "must complete" → "must complete the program" | Add 該課程 |

### {{Bracket}} Preservation — Handled Correctly
The reviewer confirmed that the preservation rule for `{{...}}` tokens is being applied correctly in this sheet. Teaching-target words in brackets are kept in English as intended.

### Pronoun-as-noun issue
The reviewer flagged multiple cases where Chinese pronoun 它 / 它們 / 這裡 was used where Chinese convention prefers repeating the noun. This is a stylistic pattern worth adding to the style guide.

---

## Recurring Issues Summary

| Issue | Severity | Affected Sheets |
|---|---|---|
| Split-sentence subtitle translation | Critical | Subtitles |
| Grammar meta-terms not translated (nouns, verbs…) | High | Subtitles, Explanations |
| 活動 / 優惠 word choice confusion | Medium | UI |
| Translationese / AI tone | Medium | Subtitles, Explanations |
| Chinese pronoun overuse (should repeat noun) | Low–Medium | Explanations |
| Specific mistranslation (`coupon_apply_not_successfully`) | Medium | UI |
| Source text gap in subtitle segment 17 | Needs investigation | Subtitles (source) |

---

## Next Steps

### Immediate (before next batch)

1. **Fix subtitle pipeline context window**  
   The translator must receive 2–3 surrounding segments as read-only context when translating each segment. This alone should recover 15–20 accuracy points on average. Consider a "sentence-boundary grouping" pre-processing step that detects sentence-final punctuation and routes complete sentences as a unit.

2. **Correct the 8 flagged UI items**  
   Priority: `coupon_apply_not_successfully` (semantic error). The `活動 → 優惠` collocation fixes can be batch-replaced across the full UI string set.

3. **Verify source text integrity for subtitle segment 17**  
   Reviewer noted missing words between "designed" and "truly understand." Confirm whether this is a source export truncation or a real gap in the script.

### Short-term (style guide and tooling)

4. **Add grammar meta-term glossary**  
   Create a TW-specific glossary entry: noun=名詞, verb=動詞, adjective=形容詞, adverb=副詞, pronoun=代名詞, preposition=介系詞, grammar point=文法要點, sentence structure=句型結構. These are translatable and should not be protected by the preservation rule.

5. **Add collocation rules for promotion-related terms**  
   活動 = event/campaign (suitable for marketing)  
   優惠 = discount/offer (suitable for transactional UI)  
   Distinction should be in the prompt or style guide used by the translator.

6. **Chinese-style guide note on pronoun vs. noun repetition**  
   Add a standing instruction: avoid 它/它們/這裡 as stand-ins when the referent noun is short — repeat the noun instead.

### Medium-term (quality process)

7. **Separate QA tier for subtitles**  
   Subtitles score ~20 points lower on average than other content types. Consider a dedicated post-edit pass for subtitle content until the pipeline context-window fix is validated.

8. **Re-evaluate the 50-row subtitle sample post-fix**  
   Once the context-window change is deployed, re-run the same 50 segments through the updated pipeline and re-score. Target: accuracy avg ≥ 80, naturalness avg ≥ 80.

9. **Establish pass/fail thresholds for production**  
   Based on this evaluation, proposed minimum acceptable scores:  
   - UI strings: Accuracy ≥ 85, Naturalness ≥ 80  
   - Subtitles: Accuracy ≥ 80, Naturalness ≥ 78  
   - Explanations: Accuracy ≥ 85, Naturalness ≥ 80  
   Any item below threshold triggers a mandatory post-edit flag in the pipeline.
