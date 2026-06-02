# V9 vs V11 Crosscheck Report
**File:** `tw_sub-50-eng.csv` — Lesson 1 Basic Grammar (50 segments)
**Date:** 2026-05-15

---

## Summary Verdict

V11 is a net improvement over V9. It resolves several English-leakage issues (untranslated terms left in Latin script), corrects TW-specific terminology (`介系詞`, `這門`), and produces more natural sentence flow in a number of segments. However, one structural regression was introduced in S7, and two long-standing cross-segment continuation issues (S44/S45, S38/S39) remain unresolved in both versions.

---

## Segment-by-Segment Differences

### V11 Improvements

| Seg | V9 | V11 | Why V11 Wins |
|-----|-----|-----|------|
| S1 | 大家好，歡迎來到 Prep。 | 大家好！歡迎來到 Prep。 | Exclamation matches tone of "big welcome" |
| S2 | 很高興大家來參加 Basic Grammar 課程。 | 很高興大家來參加**我們的** Basic Grammar 課程。 | "our" now reflected; more accurate |
| S3 | 這裡我們將為您**建立**真正需要的堅實基礎 | 這裡就是我們將為您**打下**真正需要的堅實基礎的地方。 | "打下基礎" is the idiomatic TW form; sentence now complete |
| S9 | 我們將在**這個** course 中**進行學習**。 | 我們將在**這門** course 中**學習**。 | "這門" is the correct classifier for courses; "進行學習" trimmed |
| S21 | 如何將 **sentences** 組合在一起，以及不同的句型 | **句子的組成方式**，以及不同的句型 | "sentences" translated; more natural Chinese |
| S25 | 最後，幫助您開始建立自己的 **basic sentences**。 | 最後，協助您開始建立自己的**基本句型**。 | "basic sentences" translated |
| S31 | 涵蓋任何 **grammar** 重點的三個關鍵面向：**使用方式，** | 涵蓋任何**文法點**的三個關鍵面向：**其用法，** | "grammar" translated; "其用法" is crisper |
| S34 | 形容詞與副詞、代名詞、**介詞**，以及當然， | 形容詞和副詞、代名詞、**介系詞**，以及當然， | "介系詞" is the correct TW standard term |
| S35 | 基本句型。 | **基本句型結構**。 | Source says "basic sentence structure" — v11 is accurate |
| S37 | 本課程並非旨在涵蓋英語文法的**所有**細節。 | 這門課程並非旨在涵蓋英語文法的**每一個**細節。 | "every single detail" → "每一個細節" is closer |
| S40 | 我們會將這些更進階的主題**留給**中階和高階課程。 | 我們會把這些進階主題**留到**中階和高階課程。 | "留到" more natural for "save for" |

---

### V9 Better Than V11

| Seg | V9 | V11 | Why V9 Wins |
|-----|-----|-----|------|
| S7 | 所以，在**這個**第一支影片裡，我們花點時間來做幾件事。 | 所以在**這支**第一支影片裡，我們花點時間來做幾件事。 | V11 is redundant — "這支" and "第一支" back-to-back |
| S14 | 因此，Basic Grammar 課程是 Prep **基礎系列**的重要組成部分。 | 因此，Basic Grammar 課程是 **Prep's foundational series** 的重要組成部分。 | V9 correctly translates "foundational series"; V11 leaves the entire phrase in English |
| S39 | 在發音和詞彙方面，**在你能夠有效處理它們之前**。 | 在發音和詞彙方面，**如果你無法有效掌握它們**。 | Source says "before you can tackle them" — V11 reframes it as a negative conditional, which is a meaning shift |

---

### Identical (No Change)

S4, S6, S10, S13, S18, S19, S20, S23, S24, S26, S28, S29, S30, S33, S36, S38, S43, S47, S48, S50

---

## Persistent Issues (Both Versions)

### 1. Split Construction: S44 / S45 — ★ Critical
**Source:**
- S44: "You'll notice that our approach here at Prep is a little different"
- S45: "from traditional grammar classes."

**Both V9 and V11:**
- S44: ...方法略有不同 / ...教學方法有一點不同
- S45: **來自傳統的語法課程。** / **來自傳統語法課程。**

**Issue:** S45 still reads as an independent clause ("originates from traditional grammar classes"), instead of completing the comparison from S44. Correct rendering should be something like S44 ending with: "…與傳統語法課程**有所不同**". This is the known API-level cross-segment continuation bug. No change from prior investigation.

---

### 2. Split Construction: S38 / S39 — ★ Notable
**Source:**
- S38: "There are some pretty complex areas that really require a strong foundation"
- S39: "in pronunciation and vocabulary before you can tackle them effectively."

**V9 S39:** 在發音和詞彙方面，在你能夠有效處理它們之前。
**V11 S39:** 在發音和詞彙方面，如果你無法有效掌握它們。

**Issue:** Neither version successfully continues from S38. V9 is closer to the source ("before you can tackle them"); V11 introduces an incorrect negative conditional. The full S38+S39 meaning is: "…需要在**發音和詞彙方面有扎實基礎**，才能有效掌握它們." — unachievable without cross-segment context at the API level.

---

### 3. Pronoun Inconsistency (您 / 你) — Minor
Both versions alternate between 您 (formal) and 你 (informal) throughout. Not a new issue; likely driven by model variation per segment. Recommend a post-processing pass to standardise to 您 for course subtitles.

---

### 4. S37 Negation — Confirmed Stable
Source: "This course **isn't** meant to cover…"
Both V9 and V11: "並**非**旨在涵蓋…" ✓

The negation is correctly preserved in both. The previously documented instability (negation randomly dropping across runs) does not appear in either of these outputs.

---

## Overall Scorecard

| Dimension | V9 | V11 |
|---|---|---|
| English leakage (untranslated terms) | Several (sentences, grammar, basic sentences…) | Mostly resolved |
| TW-specific terminology | Partial (介詞 incorrect) | Correct (介系詞) |
| Structural completeness | Some incomplete sentences (S3) | More complete |
| Accuracy regressions | None notable | S39 meaning shift; S14 English not translated |
| Structural regression | — | S7 redundant classifier |
| Cross-segment splits | Unresolved | Unresolved |
| Negation stability | Correct | Correct |

**Recommendation:** V11 is the better output to carry forward. Before use, apply the following targeted corrections:

1. **S7** — Fix "在這支第一支" → "在這第一支" or "在這支"
2. **S14** — Translate "Prep's foundational series" → "Prep 的基礎系列"
3. **S39** — Revert meaning: "在發音和詞彙方面，在你能夠有效掌握它們之前。"
4. **S44/S45** — Manual fix until API supports `preceding_text`: merge S44+S45 into one segment or manually correct S44 to end with "與傳統語法課程有所不同".
5. Pronouns: standardise 你 → 您 throughout for consistency.

---

*Report generated from direct segment comparison of (v9) tw_sub-50-eng.csv and (v11) tw_sub-50-eng.csv.*
*Cross-referenced against: TW-Sub-Follow-Up-Investigation.md, Manager-Escalation-API-Pipeline-Issues.md*
