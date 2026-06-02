# V9 Translation Engine — Review Report

## What Went Well

### Traditional Chinese (TW)
- **UI strings are strong.** The majority of TW UI items score 90/90 on both accuracy and naturalness. Simple transactional terms (checkout, payment, phone, address, apply, total price) translate consistently well.
- **Explanation texts are mostly accurate.** A large cluster of items score 89–95 on accuracy with 80–90 naturalness. Factual, logical strings (keyword identification, "the passage states…", option elimination) perform best.
- **Isolated subtitle segments are accurate.** When a segment forms a complete, standalone thought, TW subtitle quality is good (e.g., segs 2, 13, 23, 27–28, 40–41, 52 all score 90/90 or close).

### Thai (TH)
- **UI accuracy is the highest of the three content types at 62% pass rate.** Most labels and field names are correctly understood.
- **Some explanation items are solid.** Items that deal with grammar terminology and test-taking instructions (identify keywords, eliminate option X) translate well where the phrasing is formulaic.

---

## What Did Not Go Well

### Overall (Both Languages)
| Issue | Severity | Languages Affected |
|---|---|---|
| Translationese — English sentence structure preserved | High | TW + TH |
| Split-sentence translation producing incoherent output | Critical | TW + TH |
| Untranslated English terms with target-language equivalents | High | TW + TH |
| Corrupted / unintelligible output (specific segments) | Critical | TH |

### Thai-Specific
| Issue | Severity |
|---|---|
| ค่ะ/ครับ applied to UI strings, fragments, and mid-list items | Critical — most frequent error class |
| โปรโมชั่น (spoken) used instead of โพรโมชัน (Royal Society house spelling) | High — appears in 8+ UI items |
| Register and cultural mismatches (ปฐมนิเทศ, ศิษย์, มัน, ชอปปิง) | High |
| Mai Yamok spacing violations | Medium |
| Passive voice constructions inappropriate for Thai | Medium |
| Dual-language artefacts (Thai + English side by side in output) | Medium |
| Incorrect punctuation imported from English (colons, em-dashes) | Medium |

### Score Summary (TH — 150 items)
| Content Type | Accuracy Pass | Naturalness Pass |
|---|---|---|
| Explanations | 46% | 34% |
| **Subtitles** | **38%** | **24%** |
| UI | 62% | 30% |
| **All content** | **49%** | **29%** |

Naturalness is the bigger problem: **7 in 10 translations fail naturalness across all content types.** The engine produces output that conveys meaning but rarely reads the way a native speaker would write or speak.

---

## Subtitle Translation — Problems and How to Fix Them

Subtitles are the worst-performing content type in both languages, with the lowest scores and the highest density of reviewer flags. The problems fall into two categories: **pipeline design failures** and **prompt quality failures**.

### Problem 1 — Segment-level translation without sentence context (Pipeline)

This is the primary failure mode. Subtitle files are broken into short time-coded segments, and the model receives each segment in isolation. When the source sentence spans two or more segments, each fragment is translated as if it were a standalone utterance. The result is syntactically incoherent output that reads as word fragments, not sentences.

**Evidence:**
- TW: segments 5–6, 9–12, 15–21, 24–26, 43–49 all show split-sentence failures; reviewer repeatedly recommends merging 2–4 segments and re-translating as a unit
- TH: "DISCONNECTED" flag appears on segments 4, 6, 9, 11, 18, 45; reviewer states segment 7 is "easier to backtranslate and understand in English"
- TH segment 10: output is completely unintelligible — reviewer notes "This is probably not from any AI" — flagged as a data-handling or pipeline corruption issue requiring separate investigation

**Fix:** Implement a **sliding context window of 3–5 segments** passed to the model on every call, with the target segment explicitly marked. The model must treat the segment as part of a continuous spoken utterance, not a standalone sentence. This is a **pipeline design change**, not a prompt change — it requires re-architecting how segments are batched before the API call.

---

### Problem 2 — Untranslated English terms (Prompt)

Subject-domain terms are left in English even when well-established target-language equivalents exist. The model defaults to keeping the source term when uncertain rather than finding the correct translation.

**Evidence:**
- TW: "basic grammar course," "grammar point," "nouns," "verbs," "adjectives," "adverbs," "pronouns," "prepositions," "sentences," "rules" all left in English
- TH: "basic grammar course," "foundational," "parts of speech" (partially), common words left untranslated in segments 37 and 49

**Fix:** Add a **subject-domain glossary** to the subtitle system prompt covering grammar terminology, course structure vocabulary, and learning-platform terms. The TH reviewer notes two EN-TH glossary sets are already compiled and ready for injection.

---

### Problem 3 — Translationese (Prompt)

The model preserves English sentence structure rather than restructuring for the target language. In Chinese this produces a "heavy translationese tone" (flagged in TW segs 29, 37, 42, 46). In Thai this is more severe — Thai is a topic-comment language with different word order and strong preference for active voice; the English passive and discourse-marker patterns are not natural.

**Evidence:**
- TW: segments 29, 37, 42, 46 explicitly flagged for translationese
- TH: segments 15, 21, 36, 40 flagged for passive voice and English structure; reviewer notes "proper Thai doesn't really use passive voice"
- TH segment 7: "Too much effort required to understand. Easier to backtranslate and understand it in English."

**Fix:** Add an explicit **negative-examples block** to the system prompt showing English-structure output and the correct natural-language rewrite. For Thai specifically, include the instruction: "Restructure sentences to follow Thai topic-comment order; convert passive voice to active; do not translate discourse markers literally — localise them."

---

### Problem 4 — Register and cultural mismatches (Prompt — TH specific)

Subtitle content is spoken educational language. The model is not calibrated to the register appropriate for an online learning platform.

**Evidence:**
- TH: **ค่ะ** added to subtitle segments where a teacher would not use this particle mid-sentence (segs 17, 20, 25, 30, 33, 38, 44)
- TH: **มัน** used as third-person "it" — reviewer: "DON'T USE THIS WORD" — impolite in Thai educational materials
- TH: **ปฐมนิเทศ** used for "orientation" — in Thai culture this word specifically means new staff/student welcome events, not safety/course orientation
- TH: **ศิษย์** used for "student" — extremely formal term, inappropriate for Prep's learner persona
- TH: Discourse markers ("all right, let's dive in") translated literally rather than localised
- TH: "nail those down" → เป๊ะ — natural Gen-Z spoken Thai but "too friendly for a classroom"

**Fix:** Add a **brand and register brief** to the subtitle system prompt specifying: target learner persona (young adults on an online platform), formality level (semi-formal, active, encouraging), prohibited vocabulary list (มัน, ศิษย์, กอร์ส), cultural adaptation rules (discourse markers must be localised, not translated), and ค่ะ/ครับ usage rules (sentence-end only, never on fragments).

---

### Problem 5 — Corrupted output in specific segments (Pipeline/Infrastructure)

TH subtitle segment 10 produces output that is completely unintelligible — not a translation failure but a data corruption event. The reviewer states it is inconsistent with any AI translation failure mode. This issue also manifests in TH explanations items 20, 32, 33, and 45 as garbled Thai with embedded English characters and missing tone marks.

**Fix:** Investigate this as a separate infrastructure issue — likely encoding, tokenisation, or input-handling. Implement a **post-processing validation step** that checks output for: minimum character ratio of valid Thai Unicode codepoints, presence of corrupted character sequences (mixed-script tokens), and empty/near-empty output. Flag and re-queue any segment that fails validation rather than passing corrupted output downstream.

---

## Priority Action List for Subtitles

| Priority | Action | Type | Expected Impact |
|---|---|---|---|
| 1 | Sliding context window (3–5 segments) with target segment marked | Pipeline redesign | Eliminates DISCONNECTED errors — the dominant failure cause |
| 2 | Grammar and domain glossary injected into subtitle system prompt | Prompt | Eliminates untranslated English term errors |
| 3 | Register brief + prohibited word list per language | Prompt | Eliminates ค่ะ, มัน, ศิษย์ errors; calibrates tone |
| 4 | Negative-examples block for translationese | Prompt | Reduces translationese in both TW and TH |
| 5 | Post-processing validation for corrupted output | Pipeline | Prevents corrupted segments from reaching production |
| 6 | Second-pass naturalness evaluation and rewrite | Prompt (new step) | Addresses the 20-point accuracy-to-naturalness gap |

---

**Bottom line:** The V9 engine handles structured, standalone text (UI labels, formulaic explanations) reasonably well. It breaks down on subtitles primarily because the pipeline sends fragments without context, and the prompts lack the register, glossary, and structure guidance that spoken educational content requires. The highest-ROI fix is the context window change — it's a pipeline issue, not a model capability issue.
