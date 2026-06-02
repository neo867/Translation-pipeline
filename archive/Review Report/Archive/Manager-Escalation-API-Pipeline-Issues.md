# Manager Escalation — Translation Pipeline Issues
**Date:** 2026-05-12
**Raised by:** Neo (prep-ea)
**Test file:** `Test Case/Testing Output/English/tw_sub-50-eng.csv` (50 segments, Lesson 1 Basic Grammar intro)
**Translation output:** `Review Report/tw_tw_sub-50-eng_short-term-fix.csv`
**Reference:** TW-Sub-Follow-Up-Investigation.md, TW-MiLo-Evaluation-Report.md

---

## TL;DR

- **Where we are:** After MiLo's evaluation (accuracy ~69, naturalness ~73), I applied client-side fixes that lifted accuracy to ~73–75. That is as far as client-side changes can take us.
- **What's blocking the target:** Three issues in the translation API itself prevent us from reaching the accuracy ≥ 80 / naturalness ≥ 78 target. None of them can be fixed in our code.
- **What I'm raising with you:** Three API-side changes that I believe need to be escalated, in priority order, along with my recommendation on whether to keep running the short-term client-side fix in the meantime.

---

## What I'm Raising

Three changes are needed on the API side. I am flagging them to you so you have the full picture and can decide how to take them forward. Listed in the order I recommend prioritising them (highest impact first):

| # | Change | Why it matters | Suggested priority |
|---|---|---|---|
| 1 | Add a `preceding_text` parameter so the model can resolve sentences split across subtitle segments | Largest single source of errors (~15/50 segments affected) | **P0 — blocks accuracy target** |
| 2 | Add a way to translate grammar meta-terms (nouns, verbs, adjectives) even when `teaching_lang=English` is set | 5–7/50 segments, consistent error, visible to learners | **P1** |
| 3 | Enforce negation preservation in the revision stage (currently non-deterministic) | Low frequency (1/50) but high severity — meaning is reversed | **P1** |

**My recommendation:** Keep the short-term client-side fix running in production until these three changes ship. It gets us from ~69 to ~73–75 accuracy — short of the target but a meaningful improvement, and it does not regress anything. Happy to discuss whether you'd like me to plan the next evaluation cycle against current numbers or wait until the API changes land.

---

## Three Blockers

### Blocker 1 — Sentences split across subtitle segments are mistranslated (P0)

**Impact:** ~15/50 segments. Largest single contributor to the accuracy gap.

**Example (clearest case, S44/S45):**
- S44 source: *"You'll notice that our approach here at Prep is a little different"*
- S45 source: *"from traditional grammar classes."*
- S45 output: `來自傳統語法課程。` ("originates from traditional grammar classes")
- Correct: `與傳統語法課程略有不同` ("a little different from traditional grammar classes")

The model translates S45 in isolation, sees a sentence starting with "from", and picks the wrong meaning. It has no signal that S45 grammatically completes S44.

**Why we can't fix this client-side:** Both `/translate/batch` and `/translate` treat each item as self-contained. The existing `context` field carries background metadata (content type, domain) — it does not feed grammatical parsing of the text. I confirmed this by injecting the preceding segment into the context string: the model still parses the current segment as a standalone sentence.

**What would need to change on the API side:** A new `preceding_text` parameter on `/translate` (and ideally `/translate/batch`) that the pipeline treats as the directly preceding utterance the model must grammatically resolve against — not background context. With this, our client would pass S44's text when translating S45 and the "different from" construction would resolve correctly.

---

### Blocker 2 — Grammar vocabulary stuck in English (P1)

**Impact:** 5–7/50 segments. Consistent error, easy for learners to spot.

**Symptom:** Words like *nouns*, *verbs*, *adjectives*, *grammar rules*, *basic sentences*, *course* are left in English in the Chinese output, when they should be translated (名詞, 動詞, 形容詞, etc.).

**Root cause:** `teaching_lang=English` activates a preservation rule that keeps all unbraced English tokens in Latin script. That rule is correct for *teaching tokens* (e.g. `'horse'`, `"freedom"` — the actual vocabulary being taught) and course names (Basic Grammar). It is wrong for *grammar meta-terms* (the general vocabulary used to talk about grammar). The current API cannot distinguish the two.

I tried adding an explicit instruction to the context string telling the model to translate grammar meta-terms. The result was inconsistent — the structural API parameter overrides the context instruction. This cannot be fixed from our side.

**What would need to change on the API side:** Either
- a `translate_terms` allow-list parameter naming terms that should always be translated even when `teaching_lang` is set, **or**
- a `teaching_lang_mode` flag with a stricter/looser setting so we can opt out of the blanket English-preservation behaviour.

---

### Blocker 3 — Negations dropped non-deterministically (P1)

**Impact:** Low frequency (1/50 in the test file) but highest severity per occurrence: the meaning is reversed.

**Example (S37):**
- Source: *"This course isn't meant to cover every single detail of English grammar."*
- Output: `本課程旨在涵蓋英語文法的所有細節。` ("This course IS meant to cover…")
- Correct: `本課程並非旨在涵蓋英語文法的所有細節。` ("This course is NOT meant to cover…")

**Behaviour:** Non-deterministic. The negation was preserved in one run and dropped in two others with no input or parameter change. The instruction `"Preserve all negations and sentence meaning precisely."` is in the context string but is honoured inconsistently. This points to the revision stage of the pipeline dropping negations under load.

**What would need to change on the API side:** A deterministic negation-preservation check in the validation/revision stage — comparable to the existing placeholder-leak disqualifier that the pipeline already runs. If the source contains a negation marker (*isn't, doesn't, not, never, no*) and the candidate translation does not contain a corresponding negation (*並非, 不是, 沒有*…), the candidate should be rejected and retried.

---

## Impact on Targets

| Metric | MiLo baseline | Target | Current (after client-side fixes) | Reachable without API changes? |
|---|---|---|---|---|
| Accuracy avg | ~69 | ≥ 80 | ~73–75 | **No** |
| Naturalness avg | ~73 | ≥ 78 | ~75–76 | **No** |
| Split-sentence fragment errors | 15 / 50 | ≤ 3 / 50 | ~8–10 / 50 | **No — needs Blocker 1** |
| Grammar term errors | 5+ / 50 | 0 / 50 | 5–7 / 50 | **No — needs Blocker 2** |

Blockers 1 and 2 are on the critical path to the accuracy and naturalness targets. Blocker 3 is a quality/safety fix that does not move the averages much but should not ship as-is.

---

## Appendix — Client-Side Fixes Already Applied

These are in production via `short term fix/translate_csv.py`. They are the reason current numbers are 73–75 instead of MiLo's 69. They do not resolve the three blockers above.

| Fix | Change | Result |
|---|---|---|
| 1 — Grammar meta-term rule | Added instruction to context string telling the model to translate grammar terms but keep course names in Latin script. | Partial. Works in some runs, reverts in others. Context string cannot override the structural `teaching_lang` rule. |
| 2 — Batch cross-context (rejected) | Tried prepending each batch item with the preceding segment via a `[ctx:]` marker. | Failed. Context field hit a 422 size limit; model echoed the prefix verbatim at batch sizes ≥ 25; fallback path leaked the wrapper. |
| 3 — Single-translate cross-context (current short-term fix) | Switched `course_subtitle` to `/translate` single mode and appended the preceding source segment to the context string. | Improved continuity on several segments (e.g. S39). Does not resolve split-sentence cases like S44/S45 because context is metadata, not a grammatical input. |

Differences from the original pipeline:

| | Original | Short-term fix |
|---|---|---|
| Subtitle mode | Batch by default | Single translate by default |
| Cross-segment context | None | Preceding source segment appended to context per call |
| Grammar meta-term rule | Not in context | Added (partial effect only) |
| Output location | Same folder as input | `short term fix/` folder |
