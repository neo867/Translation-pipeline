# V9 vs V11 Cross-Check Report
**Date:** 2026-05-15
**Files:** `v9-scoring-tw-sub.csv` (human-scored baseline) × `tw-v11-sub-source.csv` (v11 output)
**Scope:** Lesson 1, Segments 1–53 (51 rows, TW subtitle)

---

## Overall Verdict

**V11 is a partial improvement but not publishable as-is.**

Naturalness improved in roughly half the segments. Several terminology issues flagged in v9 were addressed. However, v11 introduced a critical meaning reversal in Seg 37, produced an incomplete dangling clause in Seg 39, and regressed on untranslated terms in Segs 4 and 14. Structural split-sentence problems were not addressed at all.

---

## 1. Clear Improvements

| Seg | v9 Issue | v9 Translation | v11 Translation |
|-----|----------|----------------|-----------------|
| 3 | "Not readable" (naturalness 45) | 這裡是我們將建立您真正需要的非常基礎的地方 | 這裡就是我們將為您奠定真正所需基礎的地方 |
| 7 | Stiff phrasing | 在這支最一開始的影片中 | 在這第一支影片中 |
| 25 | "basic sentences" untranslated | …basic sentences | …基本句子 |
| 31 | "grammar point" untranslated | …grammar point 的三個關鍵面向 | …文法點的三個關鍵面向 |
| 34 | Grammar terms untranslated | adjectives、adverbs、pronouns、prepositions | 形容詞和副詞、代名詞、介系詞 |
| 41 | Stiff (80/60) | 專注於品質，而非數量 | **重質不重量** |
| 51 | "Makes no sense" (40/60) | 請將這視為…並會得到我的一些引導 | 把它視為在少許指導下主動探索語言的過程 |
| 53 | "rules" untranslated | 一堆 rules 對您進行填鴨式教學 | 一堆規則，然後單方面地講授 |

---

## 2. Critical Regression — Segment 37 (Must Fix)

| | Text |
|---|---|
| **Source** | "This course **isn't** meant to cover every single detail of English grammar." |
| **v9** | 本課程**並非**旨在涵蓋 English grammar 的所有細節。 ✓ |
| **v11** | 這門課程**旨在**涵蓋英語文法的所有細節。 ✗ |

The negation (`isn't meant to`) is completely dropped. V11 states the course IS designed to cover all details — the exact opposite of the instructor's meaning. **Mandatory correction before publication.**

---

## 3. Other Regressions

| Seg | v9 | v11 | Problem |
|-----|----|-----|---------|
| 4 | 征服並掌握**英語** | 征服並掌握 **English** | Regression — v9 had 英語; v11 leaves "English" untranslated |
| 14 | Basic Grammar 課程是 Prep **基礎系列**的重要組成部分 | Basic Grammar 課程是 Prep's **foundational series** 的重要組成部分 | More untranslated than v9; v9 had 基礎系列 |
| 39 | Stiff but complete thought | 在發音和詞彙方面，在你能有效處理它們之前。 | Dangling clause — no main verb, sentence communicates nothing |
| 46 | 賦予您力量 | 賦能您 | 賦能 is simplified Chinese corporate-speak, unnatural in TW register |

---

## 4. Unchanged Issues (v9 flagged, v11 did not fix)

| Seg | v9 Reviewer Note | Status in v11 |
|-----|-----------------|---------------|
| 1 | "big welcome" not translated | Only punctuation changed (！→，); "big welcome" still not conveyed |
| 9 | "Excessive and should be deleted" | Still present; only "course" fixed to 課程 |
| 29 | "Heavy translationese" (naturalness 73) | Identical to v9 — no change |
| 33 | "nouns/verbs should be translated" | nouns、verbs still in English |
| 44/45 | Split-sentence structural problem | Still unresolved |
| 47/48 | Split-sentence → mistranslation | Slightly better wording but still a dangling fragment |

---

## 5. Minimum Required Fixes Before Publication

1. **Seg 37** — Restore negation: "這門課程並非旨在涵蓋英語文法的每一個細節。"
2. **Seg 39** — Full rewrite needed; current translation is an incomplete clause
3. **Seg 4** — 英語 should replace "English"
4. **Seg 14** — "foundational series" should be translated (基礎系列)
5. **Seg 33** — nouns → 名詞, verbs → 動詞

---

## Segment Score Comparison (v9 human scores vs v11 estimated)

| Seg | v9 Accuracy | v9 Naturalness | v11 Change |
|-----|------------|---------------|-----------|
| 3 | 70 | 45 | Improved — more readable |
| 4 | 90 | 70 | Regressed — 英語 → English |
| 14 | 80 | 83 | Regressed — more untranslated text |
| 25 | 50 | 80 | Improved — basic sentences translated |
| 31 | 80 | 60 | Improved — grammar point translated |
| 37 | 70 | 60 | **Critical regression — meaning reversed** |
| 41 | 80 | 80 | Improved — idiomatic 重質不重量 |
| 51 | 40 | 60 | Improved — now readable |
