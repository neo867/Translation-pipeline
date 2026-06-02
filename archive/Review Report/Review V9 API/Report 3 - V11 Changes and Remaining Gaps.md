# V11 API — What Changed and What's Still Missing
## Cross-check against V9 Review and Escalation Issues

---

## Overview

V11 introduces a significant set of new parameters and endpoints that were absent in V9. Many of the issues identified in the TH/TW review and the manager escalation are now addressable through the API — but not all of them. Some are resolved cleanly, some require correct usage by our pipeline, and some are not addressed at all.

This report maps each known issue to its V11 status, flags gaps, and identifies what still requires action from the API team or from our pipeline.

---

## Status Summary

| Issue | Source | V11 Status |
|---|---|---|
| Split-sentence subtitle errors | Escalation P0, Review | Partially addressed — new parameter exists but scope is narrower than requested |
| Grammar meta-terms stuck in English (`teaching_lang` conflict) | Escalation P1 | Partially addressed — `vocab_mode` added but the specific fix requested is not there |
| Negation dropping (non-deterministic) | Escalation P1 | **Not addressed** |
| ค่ะ/ครับ applied incorrectly | Review (TH Critical) | Partially addressed — `speaker` parameter controls gender selection |
| Register and cultural mismatches (TH) | Review (TH High) | Mechanism added — depends on glossary population |
| โปรโมชัน house spelling | Review (TH High) | Mechanism added — depends on glossary population |
| Translationese | Review (Both High) | Partially addressed — `intent` parameter helps |
| Untranslated English terms | Review (Both High) | Reframed as a feature via `vocab_mode` |
| Mai Yamok spacing | Review (TH Medium) | **Not visible as addressed** |
| Passive voice in Thai | Review (TH Medium) | **Not explicitly addressed** |
| Dual-language artefacts | Review (TH Medium) | Detection improved; prevention unconfirmed |
| English punctuation in Thai output | Review (TH Medium) | Partially addressed via `content_type` |
| Corrupted output / Segment 10 | Review + Escalation | Detection improved; root cause fix unknown |
| TW word collocation errors (活動 vs 優惠) | Review (TW) | Addressable via workspace glossary — not confirmed |
| TW mistranslation (申請 vs 應用) | Review (TW) | Addressable via workspace glossary — not confirmed |

---

## What Changed in V11 — and Why It Matters

### 1. `prev_segment` and `next_segment` — context for subtitle translation

V11 adds two new fields on `/translate` specifically for subtitles: `prev_segment` (≤500 chars) and `next_segment` (≤500 chars). The API docs describe these as: *"Cross-segment context for `content_type: "subtitle"`. Pass the previous and next subtitle lines so the pipeline can resolve pronouns, continue a clause, or maintain register across cuts."*

**What this addresses:** The split-sentence problem. The S44/S45 example from the escalation — where "from traditional grammar classes" was mistranslated because the model didn't know S45 completed S44 — should be resolvable by passing S44 as `prev_segment` when translating S45.

**Where it falls short:** The escalation asked for `preceding_text` as a *grammatical input* the pipeline resolves against — not a context hint. The V11 parameter names suggest it is a context field. It is not yet confirmed whether the pipeline treats `prev_segment` as a hard grammatical dependency or as advisory background. This needs to be tested with the S44/S45 case directly.

Additionally, the escalation recommended a **3–5 segment window**. V11 provides only 1 segment before and 1 segment after. For sentences that span 3 or more segments, this may still be insufficient.

**What our pipeline needs to do:** Update the subtitle translation loop to pass the preceding and following segment on every call. This is a required usage change — the parameter exists but does nothing unless we pass it.

---

### 2. `speaker` — polite particle and register control (Thai)

V11 adds a `speaker` object: `{gender, role, age_band}`. The language table explicitly notes: *"Polite particles `ค่ะ`/`ครับ` resolved via `speaker.gender`."* Without `speaker`, the pipeline defaults to gender-neutral or default-male form.

**What this addresses:** The ค่ะ/ครับ gender-selection problem. Setting `speaker: {gender: "female", role: "teacher", age_band: "adult"}` will produce the correct polite particle for a female teacher speaker.

**Where it falls short:** The deeper V9 issue was ค่ะ appearing on sentence *fragments* — mid-sentence subtitle segments that are not complete utterances. This error should be partially resolved by passing `prev_segment`/`next_segment` (the model can then tell the segment is not sentence-final). But whether the pipeline specifically suppresses ค่ะ on non-final fragments is unconfirmed. Needs testing.

The ค่ะ problem in UI strings (where it should never appear at all) is likely resolved by using `content_type: "ui_button"`, `"ui_body"`, etc. — these content types enforce neutral imperative register. Again, this only works if our pipeline sets `content_type` correctly on every UI call.

---

### 3. `teaching_lang` + `vocab_mode` — grammar term handling

V11 adds `vocab_mode: "preserve" | "bilingual"` alongside `teaching_lang`.

- `"preserve"` (default when `teaching_lang` is set): keeps teaching-language words in their original script.
- `"bilingual"`: outputs `word (translation)` — e.g. `Past Perfect (Quá khứ Hoàn thành)`.

**What this addresses:** The escalation flagged that `teaching_lang=English` blanket-preserves all English tokens, including grammar meta-terms (nouns, verbs, adjectives) that should be translated. The `vocab_mode` system makes this behaviour an explicit, configurable choice rather than a hidden side-effect.

**Where it falls short:** The escalation specifically asked for a `translate_terms` allow-list or `teaching_lang_mode` flag so grammar meta-terms can be translated while teaching tokens are preserved. V11 does not have this. `vocab_mode` is a binary switch — either everything stays in English (`"preserve"`) or everything gets glossed (`"bilingual"`). There is still no way to say "translate 'noun' → 名詞 but keep 'Past Perfect' in English."

The `{{double-braces}}` pattern (`{{Past Perfect}}`) is the closest workaround — wrapping teaching tokens inline so the model knows to preserve them. This would require our content pipeline to pre-process source subtitles and wrap every teaching token before sending to the API.

---

### 4. `intent` — translation rewrite policy

V11 adds an `intent` parameter with five modes. The most relevant for our use cases:

- `"pedagogical"`: *"Faithful + ELT-aware glossing rules"* — designed for lesson subtitles and grammar explanations.
- `"transcreation_ux"`: *"Rewrite for natural in-product UX"* — designed for UI strings.
- `"literal"` (default): faithful, no creative liberties.

**What this addresses:** The translationese problem. `"pedagogical"` should produce more naturally restructured output than `"literal"`. `"transcreation_ux"` should produce natural UI copy rather than word-for-word translation.

**Where it falls short:** Whether the internal prompts behind `"pedagogical"` explicitly address Thai topic-comment sentence order, passive-to-active conversion, and discourse marker localisation is not visible from the API docs. The parameter provides the right lever; the depth of language-specific tuning behind it is unconfirmed. This needs to be validated against the TW and TH translationese segments from the V9 review.

---

### 5. `content_type` — stylistic conventions per content type

V11 formalises content type as a first-class parameter with specific conventions enforced per type:

| Content type | Key conventions |
|---|---|
| `"subtitle"` | One screen-line per segment; no terminal full stop unless source has one; speaker-aware; designed for use with `prev_segment`/`next_segment` |
| `"ui_button"` | Verb-first; no terminal punctuation; strict `max_chars` |
| `"ui_heading"` | No terminal punctuation |
| `"ui_body"` | Sentence case; terminal punctuation allowed |

**What this addresses:** UI punctuation artefacts (colons, em-dashes imported from English), incorrect capitalisation, and register inconsistencies between UI string types. Setting `content_type` correctly should eliminate most UI-level formatting errors from the V9 review.

**What our pipeline needs to do:** Ensure `content_type` is explicitly set on every call. If omitted, it is auto-detected heuristically — for short strings this will be unreliable.

---

### 6. `domain` + `use_glossary` + `workspace_id` — glossary injection

V11 adds `domain: "education" | "legal" | "tech" | ...` and `workspace_id` for tenant-scoped glossaries. `use_glossary` defaults to `true` and injects the domain glossary as strict rules in the first translation stage.

**What this addresses:** The mechanism for injecting house terminology, correct Thai spellings (โพรโมชัน), and prohibited vocabulary (มัน, ศิษย์, กอร์ส) now exists at the API level.

**What still needs to happen:** The glossaries must actually be populated. The API provides the pipe; someone needs to have put the correct Thai house spellings, prohibited terms, and cultural adaptation rules into the workspace glossary. This is an operational task. It is not confirmed that this work has been done.

---

### 7. `/review` and `/review/batch` — quality gating

V11 adds full review endpoints: `POST /review` and `POST /review/batch` (up to 50 pairs). Each response includes:
- `verdict`: `"ok"` / `"warning"` / `"reject"`
- `score`: 0–100
- `issues`: array with category, severity, and message per issue
- `corrected`: suggested fix when `verdict ≠ "ok"`

**What this addresses:** The V9 recommendation for a second-pass naturalness evaluation. The review endpoint can be wired into our subtitle pipeline as a post-translation quality gate: auto-publish if `score ≥ 90`, route to human review (with `corrected` as a starting point) if score is below threshold.

**What our pipeline needs to do:** This endpoint exists but is not yet integrated. Using `strictness: "linguist"` (flags unnatural phrasing, not just outright errors) is recommended for subtitle and explanation content where naturalness is the priority metric.

---

### 8. `confidence_breakdown` — structured quality signal

Every translation response now includes `confidence_breakdown: {meaning, style, purity}`:

- `meaning`: semantic fidelity
- `style`: register / fluency / convention fit
- `purity`: freedom from leakage and artefacts

**What this addresses:** Dual-language artefacts (Thai + English side by side) and corrupted output would score low on `purity`. This signal can be used to route suspicious outputs for human review without waiting for a full `/review` call.

**What our pipeline needs to do:** Read `confidence_breakdown` on every response and apply routing logic — e.g. if `purity` is `"low"`, flag for inspection before writing to file.

---

## What Is Still Missing

These issues are **not addressed in V11**, or are addressed only in theory (the mechanism exists but the fix depends on operational work that has not been confirmed).

### Not addressed in V11

**1. Deterministic negation preservation (Escalation P1)**
The escalation asked for a validation-stage check that rejects translations where a source negation (*isn't, not, never*) has no corresponding negation in the output. V11 does not mention this. The non-deterministic negation dropping confirmed in TW S37 — where meaning was fully reversed in 2 of 3 runs — remains unresolved. This is the highest-severity unaddressed issue.

**2. `translate_terms` allow-list for `teaching_lang` (Escalation P1)**
The escalation asked for a way to translate grammar meta-terms (noun → 名詞) while keeping teaching tokens (Past Perfect) in English. V11's `vocab_mode` is a binary switch that does not support this distinction. The `{{double-braces}}` workaround shifts the burden to our content pipeline (pre-processing every source subtitle to wrap teaching tokens) rather than solving it at the API level.

**3. Mai Yamok (ๆ) spacing enforcement**
No mention of Thai-specific orthographic rules in V11. Whether this is enforced internally by the pipeline is unknown. Needs to be tested.

**4. Passive voice in Thai**
V11's `intent: "pedagogical"` may help, but Thai-specific active-voice preference is not explicitly documented as enforced. Needs to be tested against the V9 segments flagged for passive constructions.

**5. Segment 10 corruption root cause**
The unintelligible TH subtitle Segment 10 was flagged as likely a data-handling or encoding error rather than a translation failure. V11's `purity` score improves *detection* of corrupted output, but there is no indication the underlying encoding or tokenisation bug has been investigated or fixed. The post-processing validation step (Unicode ratio check, mixed-script check) recommended in Report 2 should still be implemented as a safety net.

### Addressed in theory — requires confirmation

**6. Workspace glossaries populated with Thai house terms**
The mechanism for house spellings and prohibited vocabulary exists (`workspace_id`, `domain` glossaries). Whether โพรโมชัน, prohibited terms (มัน, ศิษย์, ท่าน, กอร์ส, ชอปปิง), and cultural adaptation rules have actually been loaded into the workspace is not confirmed. A test call using each of these terms as source input would confirm this.

**7. `prev_segment` treated as grammatical input vs advisory context**
The escalation explicitly noted that injecting the preceding segment into the `context` field did *not* resolve split-sentence cases like S44/S45 because the model treated it as background metadata rather than a grammatical dependency. V11's `prev_segment` is a separate named field — but whether the pipeline treats it differently from `context` needs to be verified with a direct test using S44/S45.

**8. ค่ะ suppressed on sentence fragments**
`speaker.gender` controls which particle is used. Whether the pipeline suppresses ค่ะ on non-final subtitle fragments (where no particle should appear) depends on whether `prev_segment`/`next_segment` gives the model enough sentence-boundary signal. Needs to be tested.

**9. Cultural register terms in education domain glossary**
ปฐมนิเทศ (wrong term for course orientation), ศิษย์ (overly formal for "student"), and ชอปปิง (wrong register for course purchase) need to be in the domain glossary or prohibited-word list to be caught. Whether the `domain: "education"` glossary contains these Thai-specific cultural rules is not confirmed.

**10. TW word collocation and mistranslation errors**
The specific TW issues — 活動 vs 優惠 in promotional strings, 申請 vs 應用 for coupon usage — are addressable via workspace glossary. Not confirmed as fixed.

---

## What Our Pipeline Must Do to Use V11 Correctly

V11 capabilities only work if our pipeline passes the right parameters. The following changes are required regardless of any further API-team work:

| Change | Parameter | Content type | Priority |
|---|---|---|---|
| Pass `prev_segment` and `next_segment` on every subtitle call | `prev_segment`, `next_segment` | Subtitle | High |
| Set `content_type` explicitly on every call — do not rely on auto-detect | `content_type` | All | High |
| Set `speaker: {gender, role, age_band}` on subtitle and explanation calls | `speaker` | Subtitle, Explanation | High |
| Set `intent: "pedagogical"` for subtitle and explanation content | `intent` | Subtitle, Explanation | High |
| Set `intent: "transcreation_ux"` for UI string content | `intent` | UI | High |
| Set `domain: "education"` on all content calls | `domain` | All | Medium |
| Set `workspace_id` to scope to our Thai/TW glossaries | `workspace_id` | All | Medium |
| Read `confidence_breakdown.purity` and flag low-purity output | Response field | All | Medium |
| Integrate `/review` as a post-translation quality gate for subtitles | Endpoint | Subtitle | Medium |
| Wrap teaching tokens with `{{...}}` in source text before sending | Inline markup | Subtitle | Medium (workaround) |

---

## Bottom Line

V11 closes a meaningful portion of the V9 gap. The three biggest improvements are the subtitle context parameters (`prev_segment`/`next_segment`), the `speaker` object for Thai polite particles, and the `/review` endpoint for quality gating. If our pipeline is updated to use these parameters correctly, and if the workspace glossaries are populated, we should see measurable improvement in all three content types.

The two issues that remain completely unaddressed and require escalation back to the API team are:

1. **Negation dropping** — no validation-stage check exists; meaning-reversal errors will continue at low but non-zero frequency.
2. **Grammar meta-term translation under `teaching_lang`** — the `translate_terms` allow-list requested in the escalation does not exist in V11. The `{{double-braces}}` workaround shifts work to our pipeline and is fragile at scale.

Everything else is either fixed, testable, or within our control to configure.
