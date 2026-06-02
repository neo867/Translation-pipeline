# Subtitle Translation — Why It's Failing and How to Fix It
## V9 Engine · Root Cause Analysis

---

## The Scale of the Problem

Subtitles are the worst-performing content type in both Thai and Traditional Chinese reviews.

| Language | Accuracy Pass | Naturalness Pass |
|---|---|---|
| Thai (TH) | 38% | 24% |
| TW (by density of reviewer flags) | Lowest of three content types | Lowest of three content types |

Three in four Thai subtitle segments fail naturalness. The TW reviewer flagged problems in the majority of segments reviewed. This is not a marginal quality issue — subtitle translation is substantially broken in its current form.

The failures fall into two root-cause categories: **pipeline design problems** and **prompt quality problems**. Pipeline problems produce structurally incoherent output regardless of how good the prompt is. Prompt problems produce grammatically coherent but unnatural or incorrect output. Both must be fixed; fixing only one will not be enough.

---

## Pipeline Problem: Segments Translated Without Sentence Context

### What is happening

Subtitle files are broken into short, time-coded segments. The current pipeline sends each segment to the model individually, in isolation. When a source sentence spans more than one segment — which is common — each fragment is translated as if it were a complete, standalone utterance.

The result is syntactically broken output. A fragment like *"—so that you can"* translated alone produces a dangling clause. *"master the fundamentals"* translated alone produces a decontextualised noun phrase. Placed back in sequence, these fragments read as disconnected noise, not natural speech.

### Evidence

**Traditional Chinese — quantified impact:**
Separate evaluation of 50 TW subtitle segments found approximately **15/50 segments (30%) directly affected** by split-sentence errors. This is the largest single contributor to the accuracy gap.

Clearest confirmed example (S44/S45):
- S44 source: *"You'll notice that our approach here at Prep is a little different"*
- S45 source: *"from traditional grammar classes."*
- S45 output: `來自傳統語法課程。` — model read "from" as the start of a new sentence and translated it as *"originates from traditional grammar classes"*
- Correct translation: `與傳統語法課程略有不同` — *"a little different from traditional grammar classes"*

The model had no signal that S45 grammatically completes S44. Additional affected segment groups identified by the TW reviewer: 5–6, 9–12, 15–21, 24–26, 43–49.

Segment 51 (*"Think of it as actively exploring the language with a little guidance from me"*) scored 40/60 — *"the translation makes no sense"* — a sentence that requires the context of preceding segments to be interpretable.

**Thai:**
- "DISCONNECTED" flag explicitly recorded by the reviewer on segments 4, 6, 9, 11, 18, and 45.
- Segment 7: reviewer writes *"Too much effort required to understand. Easier to backtranslate and understand it in English."*
- Segment 10: output is completely unintelligible — reviewer notes *"How did this happen? This is probably not from any AI."* This segment is flagged as likely a data-handling or encoding failure, not a translation failure, and requires a separate investigation.

### Why this happens

The pipeline was designed to translate one segment per API call. There is no mechanism for the model to know what came before or after the segment it is processing. Every segment is a blank-slate context.

### The fix

**Implement a sliding context window of 3–5 segments per API call.** Each call should pass:
- The 1–2 segments immediately preceding the target segment (as context, not to be translated).
- The target segment (clearly marked as the translation target).
- The 1–2 segments immediately following (as context, not to be translated).

The model must be instructed to treat the target segment as part of a continuous spoken utterance and to produce a translation that reads naturally within that larger sentence. This is a **pipeline design change** — it requires restructuring how segments are batched before the API call, not just changing the prompt.

---

## Prompt Problem 1: Untranslated English Terms

### What is happening

Grammar and course-structure terms are left in English in the target-language output, even when well-established target-language equivalents exist.

### Evidence

**Traditional Chinese:** "basic grammar course," "grammar point," "nouns," "verbs," "adjectives," "adverbs," "pronouns," "prepositions," "sentences," "rules" — all left in English across multiple segments.

**Thai:** "basic grammar course," "foundational," common words in segments 37 and 49 left untranslated.

### Why this happens

This is not simply a missing glossary. When `teaching_lang=English` is set in the API, the pipeline activates a blanket preservation rule that keeps **all unbraced English tokens in Latin script** in the output. This rule is correct for *teaching tokens* — the actual English words being studied (e.g. `'horse'`, `"freedom"`, course names) — but it is wrong for *grammar meta-terms* (the vocabulary used to talk about grammar: "noun," "verb," "adjective"). The API currently cannot distinguish between the two categories.

Injecting an explicit instruction into the `context` string telling the model to translate grammar meta-terms was attempted and found to be inconsistent: the structural `teaching_lang` API parameter overrides context-string instructions. This cannot be fixed client-side.

### The fix

Two options, requiring an API-side change:

1. **`translate_terms` allow-list parameter** — a new parameter naming specific terms that should always be translated even when `teaching_lang` is set (e.g. `["noun", "verb", "adjective", "grammar rule"]`).
2. **`teaching_lang_mode` flag** — a stricter/looser setting allowing callers to opt out of the blanket English-preservation behaviour for meta-language vocabulary.

In the interim, the Thai reviewer notes that two EN-TH glossary sets are already compiled. For TW, grammar meta-term equivalents (名詞, 動詞, 形容詞, etc.) are well-established and can be passed via `preserve_list` with `{{double-braces}}` workaround as a partial client-side mitigation.

**Product decision note:** For a language-learning platform, there is a legitimate case for preserving English grammar terms (so learners see them in context). Whether terms like "noun" should be translated to 名詞/คำนาม or kept in English is a product call — but it must be a deliberate choice, not a side-effect of the blanket preservation rule.

---

## Prompt Problem 2: Translationese

### What is happening

The model reproduces English sentence structure in the target language rather than restructuring the sentence naturally. The output conveys the correct meaning but reads like a direct word-for-word transfer — not how a native speaker of the target language would construct the same thought.

### Evidence

**Traditional Chinese:** Segments 29, 37, 42, and 46 are explicitly flagged for *"heavy translationese tone"* and *"heavy Chinese-y tone."* Segment 42 is noted as having *"a little AI tone."*

**Thai:** Segments 15, 21, 36, and 40 are flagged for English structure. The reviewer notes *"proper Thai doesn't really use passive voice"* — yet passive constructions appear throughout. Segment 7 is described as easier to understand by backtranslating to English than by reading the Thai.

### Why this happens

The model optimises for semantic fidelity (meaning accuracy) without being instructed to restructure for the target language's natural syntax. Thai in particular is a topic-comment language with different word order, a strong preference for active voice, and discourse patterns that differ significantly from English.

### The fix

Add an **explicit restructuring instruction and negative-examples block** to the subtitle system prompt:

For all languages:
> *"Do not preserve English sentence structure. Produce output that reads as natural [target language], not as translated English."*

For Thai specifically:
> *"Thai uses topic-comment sentence order. Convert passive voice to active voice. Do not translate English discourse markers literally — adapt them to the equivalent Thai spoken expression."*

A small set of before/after negative examples in the prompt (2–3 pairs showing translationese output and the correct natural rewrite) is more effective than a general instruction alone.

---

## Prompt Problem 3: Register and Cultural Mismatches (Thai)

### What is happening

The model is not calibrated to the register appropriate for spoken educational content on an online learning platform. It produces output that is either too formal, too informal, culturally mismatched, or that uses politeness particles in inappropriate positions.

### Evidence

| Segment | Problem |
|---|---|
| Segs 17, 20, 25, 30, 33, 38, 44 | ค่ะ added mid-sentence, where a teacher would not use this particle |
| Seg 32 | มัน used as "it" — impolite in Thai educational materials. Reviewer: *"DON'T USE THIS WORD"* |
| Seg 39 | ปฐมนิเทศ used for "orientation" — in Thai culture, refers specifically to new staff/student welcome events, not course orientation |
| Seg 23 | เชี่ยวชาญ used as a verb — it is not a verb in Thai |
| Seg 46 | Reviewer: *"Too fancy, too literary for classroom"* |
| Seg 13 | Discourse marker ("all right, let's dive in") translated literally — *"sophisticated speeches never employ their linguistic functions in Thai"* |
| Seg 24 | "nail those down" → เป๊ะ — natural Gen-Z spoken Thai but *"too friendly for classroom"* |
| Seg 44 | Inconsistent pronoun: ท่าน (very formal) vs คุณ (standard polite) in adjacent segments |

### Why this happens

The model has no content-specific register brief. Without explicit instructions about who the speaker is, who the audience is, what formality level is expected, and which vocabulary is prohibited, the model makes its own choices — which are inconsistent and often wrong.

### The fix

Add a **register and brand brief** to the Thai subtitle system prompt:

```
Speaker: adult teacher, female, professional but approachable
Audience: young adult learners on an online learning platform
Formality: semi-formal — polite but conversational, not academic
ค่ะ/ครับ: use only at the end of complete sentences; never on fragments
Prohibited vocabulary: มัน (as "it"), ศิษย์, กอร์ส, ชอปปิง, ท่าน
Discourse markers: localise, do not translate literally
Cultural adaptation: "orientation" in this context means course introduction, not ปฐมนิเทศ
```

---

## Prompt Problem 4: Non-deterministic Negation Dropping (TW)

### What is happening

Source-language negations are intermittently dropped from TW subtitle output, reversing the meaning of the sentence. The error is non-deterministic — it appears in some runs and not others with no change in input or parameters.

### Evidence

**Confirmed example (TW subtitles, S37):**
- Source: *"This course isn't meant to cover every single detail of English grammar."*
- Erroneous output: `本課程旨在涵蓋英語文法的所有細節。` — *"This course IS meant to cover every single detail"* (meaning fully reversed)
- Correct: `本課程並非旨在涵蓋英語文法的所有細節。`

Tested across 3 runs with identical input: negation preserved in 1 run, dropped in 2. The instruction `"Preserve all negations and sentence meaning precisely."` was present in the context string on all runs and had no consistent effect.

**Frequency:** Low — approximately 1–2 segments per 50. The per-segment rate is low but the severity per occurrence is the highest in this report — the meaning is reversed, not just awkward.

### Why this happens

The pipeline's revision or quality-checking stage appears to non-deterministically drop negation markers under load, likely during a fluency-optimisation pass that treats contracted negations (*isn't*, *doesn't*, *won't*) as candidates for rewriting. Unlike placeholder-leak errors (which the pipeline already disqualifies deterministically), negation loss is not caught before output is returned.

### The fix

Add a **deterministic negation-preservation check** to the pipeline's validation/revision stage, comparable to the existing placeholder-leak disqualifier:

- If the source text contains a negation marker (*isn't, doesn't, not, never, no, cannot, won't*…), verify that the candidate translation contains a corresponding negation (*並非, 不是, 沒有, 從不*…).
- If the candidate fails this check, reject and retry rather than returning the output.

This is an API-side fix. Client-side instructions in the `context` string cannot reliably enforce it.

---

## Pipeline Problem 2: Corrupted Output (Thai — Segment 10)

### What is happening

Thai subtitle segment 10 produced output described by the reviewer as completely unintelligible — not a poor translation, but garbled text that is inconsistent with any AI translation failure mode. Similar corruption appears in Thai explanation items 20, 32, 33, and 45, where Thai characters appear alongside embedded English characters and tone marks are missing or incorrect.

### Why this happens

This is not a translation quality issue. The evidence points to an encoding, tokenisation, or input-handling problem upstream of the model. The corruption pattern (mixed-script characters, missing tone marks) is consistent with a character encoding error in how the source text is preprocessed or in how the model output is decoded.

### The fix

This requires a **separate infrastructure investigation** — it cannot be addressed by prompt changes.

In the interim, implement a **post-processing validation step** before subtitle output is written to file or returned to the caller:
- Check that the output contains a minimum ratio of valid Thai Unicode codepoints.
- Check for mixed-script tokens (Thai characters adjacent to embedded Latin characters mid-word).
- Check for empty or near-empty output.
- Flag any segment that fails these checks and re-queue it rather than passing corrupted output downstream.

---

## What Has Already Been Tried (TW Subtitles)

Before escalating, three client-side approaches were tested to address the context window and grammar term issues. All three have been found insufficient, and their failure explains why API-level changes are required.

| Attempt | What was done | Result |
|---|---|---|
| Grammar meta-term instruction | Added instruction to the `context` string telling the model to translate grammar terms but keep course names in Latin script | Partial — works in some runs, reverts in others. The structural `teaching_lang` parameter overrides the context instruction. |
| Batch cross-context injection | Prepended each batch item with the preceding segment using a `[ctx:]` marker | Failed. Hit a 422 size limit; at batch sizes ≥ 25 the model echoed the prefix verbatim in the output; the fallback path leaked the wrapper into production. |
| Single-translate cross-context (current short-term fix) | Switched subtitle mode from batch to single `/translate` calls; appended the preceding source segment to the `context` field per call | Partial improvement — improved continuity on some segments (e.g. S39). Does not resolve split-sentence cases like S44/S45 because the `context` field is treated as background metadata, not as a grammatical input for parsing. Lifted TW accuracy from ~69 to ~73–75 but cannot reach the ≥ 80 target. |

The short-term single-translate fix is currently running in production. It is the best achievable without API changes and should remain in place until the API-level fixes ship.

---

## Priority Action List

| Priority | Action | Category | Who fixes it | Expected Impact |
|---|---|---|---|---|
| 1 | Add `preceding_text` (or equivalent) as a grammatical input parameter — distinct from the existing `context` field — so the model can resolve sentences split across segments | API change | API team | Eliminates DISCONNECTED errors; removes ~15/50 TW error segments; closes the largest single accuracy gap |
| 2 | Add `translate_terms` allow-list or `teaching_lang_mode` flag so grammar meta-terms can be translated even when `teaching_lang` is set | API change | API team | Eliminates grammar term errors (5–7/50 segments); required to reach accuracy target |
| 3 | Add deterministic negation-preservation check to the pipeline validation stage | API change | API team | Prevents meaning-reversal errors; low frequency but highest severity per occurrence |
| 4 | Inject grammar and domain glossary into subtitle system prompt | Prompt | Our team | Reduces remaining untranslated terms once API changes land |
| 5 | Add Thai register brief and prohibited word list to subtitle system prompt | Prompt | Our team | Eliminates ค่ะ misuse, มัน, ศิษย์, and cultural mismatch errors |
| 6 | Add restructuring instruction + negative-examples block for translationese | Prompt | Our team | Reduces translationese in both TW and TH |
| 7 | Investigate and fix Segment 10 encoding/data-handling issue | Infrastructure | API team | Prevents corrupted output from reaching production |
| 8 | Add post-processing validation for corrupted output (Unicode ratio check, mixed-script check) | Pipeline | Our team | Safety net while infrastructure fix is investigated |
| 9 | Wire in a second-pass naturalness review prompt | Prompt (new stage) | Our team | Addresses the 20-point accuracy-to-naturalness gap in Thai |

---

## Bottom Line

The subtitle pipeline has two distinct classes of problem that must be addressed separately.

**The context window fix (Priority 1) is the most impactful single change** — and it is a pipeline design change, not a prompt change. A significant portion of the low scores in both languages trace back to the model receiving sentence fragments with no surrounding context and producing incoherent translations as a result. No amount of prompt tuning will fix this; the segments must be batched with their neighbours before being sent to the model.

**The prompt fixes (Priorities 2–4) address what remains after the context window is in place.** Untranslated terms, translationese, and register errors are all solvable at the prompt level once the model is receiving coherent input. For Thai, the register brief (Priority 3) should be treated as equally urgent — it eliminates the most frequently recurring error class in the Thai review.
