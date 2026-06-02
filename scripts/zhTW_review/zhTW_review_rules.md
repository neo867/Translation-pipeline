# TW Subtitle Translation Review Rules

Rules derived from reviewer feedback on zhTW_L1S1 (IE Intermediate 2.6 Listening Int). Apply to all future zhTW subtitle files.

---

## 1. IELTS → 雅思

Taiwanese audiences use 雅思 (the Chinese transliteration) rather than the English acronym IELTS. Replace IELTS throughout with 雅思 unless the term is part of a formal test tier name that must stay in English (e.g. "IELTS Academic" — judge contextually).

---

## 2. 您 → 你 (teacher-student register)

In classroom/course settings, the instructor addresses students using 你, not 您. Using 您 implies the student outranks the speaker; in TW educational culture, respect flows from student to teacher. Replace 您 with 你 throughout when the instructor is speaking to students.

**Exception:** Keep 您 if a student or third-party character is addressing the instructor/examiner in a dialogue or example scenario.

---

## 3. Fix awkward phrasing, sentences, and word endings

Beyond explicit feedback corrections, actively rewrite any translation that sounds unnatural in spoken Taiwanese Mandarin. Common patterns to watch for:

**Sentence endings:**

- Avoid stiff or overly written endings. Prefer natural spoken-language closings.
- `是不是…呢？` is fine; `…不是嗎？` can feel foreign/translated.
- `好嗎？` is acceptable for rhetorical tags.
- Avoid ending with 的 when it creates an abrupt or unresolved feel.

**Overly literal constructions:**

- `在…之前` chains that become clunky — restructure for flow.
- `關於…的…` double-noun stacks — simplify where possible.
- `進行…` (perform/conduct) is often more natural as a direct verb: `做`, `參加`, `完成`.
- `應用…方法` → `使用這個方法` or `用這個方式` (more colloquial).

**Word choice — general:**

- `徹底` (thorough) → `扎實` when describing practice or study habits.
- `掌握` is fine for "master/grasp a skill"; avoid overusing it in adjacent sentences — vary with `學好`, `熟悉`.
- `強調` is fine; avoid `著重強調` (redundant).
- `獲得` and `取得` are interchangeable for scores; `拿到` is more colloquial and natural.
- `目標是 X 分` is natural; `以 X 分為目標` is acceptable but slightly stiffer.
- `培養` is fine for skills; `提升` is more natural for improvement in TW spoken context.
- `相同` → `一樣` in conversational/spoken context (`一樣` is more colloquial in TW Mandarin).
- `匆忙` → `倉促` is more idiomatic when paired with study/test contexts.

**Word choice — formal vs. colloquial substitutions (from reviewer feedback):**

- `聆聽` → `聽` — `聆聽` is too literary for subtitle/spoken context; use `聽` throughout.
- `講者` → `說話者` — `說話者` is the standard term in TW IELTS material; `講者` reads as HK usage.
- `改述` / `換句話說` → `同義改寫` — This is the correct TW IELTS term for "paraphrasing."
- `閱讀` is fine; avoid `閱覽` which is overly formal.
- `記筆記` is natural; `做筆記` is also acceptable; avoid `筆記紀錄`.

**Connector words:**

- `然而` (however) is slightly formal — `不過` is more natural in spoken TW Mandarin.
- `因此` is fine in writing but `所以` flows better in speech.
- `而是` is correct for contrast; don't replace with `但是` unless restructuring the sentence.
- `反而` means "contrary to expectation / turned out to be" — do NOT use it to translate "instead." Use `而是` or `改為` instead.

**Pronoun and subject handling:**

- TW Mandarin often drops subjects — don't force them in if the context is clear.
- `我們` (we/our) for course context is fine; don't switch to `大家` unless addressing a group explicitly.
- Check that `它` vs `它們` matches the actual subject. IELTS/雅思 as a test = singular `它`; don't default to `它們`.

**Syntax and sentence flow:**

- Restructure topic-comment sentences for natural spoken word order: `考生每段錄音只會聽到一次` → `每段錄音，考生只會聽到一次`.
- Add clarifying words when dropping them causes ambiguity: `直接於螢幕上輸入答案` not `於螢幕上輸入答案`.
- Avoid long noun stacks before verbs — break them into two shorter clauses.

**Repeated characters:**

- Avoid accidental `一一` or other doubled characters from adjacent measure words — restructure the phrase (e.g. `這一一般類別` → `這個大類別`).

---

## 7. Quotation marks — use 「」not 『』

In TW subtitles, use `「」` for all quotation marks. The double-corner style `『』` is standard in Mainland/HK usage but uncommon in Taiwan. The mechanical fix script applies this automatically.

**Exception:** `『』` is acceptable if it nests inside `「」` for a quote-within-a-quote, but this is rare in subtitle content.

---

## 8. Punctuation — use colons for clarification

When a subtitle introduces an example or definition, use `：` (colon) not `。` or `,` to introduce it:

- ❌ `題目，博物館位於河邊。` → ✓ `題目：博物館位於河邊。`
- ❌ `例如，這個詞的意思。` → ✓ `例如：這個詞的意思。`

This matches standard TW educational writing conventions.

---

## 4. Technical English terms — keep in English

Terms like *keyword identification*, *prediction based on vocabulary groups*, *grammatical clues*, *note-taking key information*, *signposting language*, *CEFR*, *Band 6*, *B1/B2* should be kept in English/alphanumeric form. Naturalness scores of 0 on these blocks are expected and acceptable.

---

## 5. English accent names — keep in English

*British English*, *American English*, *Australian English* are kept as-is. This is standard in TW IELTS materials.

---

## 6. Revised file naming

Append `_revised` suffix to the SRT filename (e.g. `zhTW_L1S1_revised.srt`).

---

## Workflow (apply to every file)

1. Run `zhTW_mechanical_fix.py` — applies Rules 1, 2, 7 automatically (IELTS→雅思, 您→你, 『』→「」).
2. Open the `_revised.srt` for a naturalness pass — apply Rules 3, 8 and the vocabulary substitutions above.
3. Reference `review/review_examples.md` for concrete before/after examples from native TW reviewer feedback.
4. Read every subtitle block aloud mentally — if it sounds stiff or translated, rewrite it.
5. Technical English terms (Rule 4) and accent names (Rule 5) must not be touched.
6. File is already saved as `<original-name>_revised.srt` by the script.
