# MiLo Evaluation vs V11 Crosscheck Report

**Date:** 2026-05-15
**Pipeline:** V10 (S1→L2→S3→S4→S5), Model: Qwen 3.6-35B, vocab_mode=preserve
**Evaluator:** Auto-crosscheck against MiLo's human evaluation (tw_sub_eng sheet)

---

## 1. Executive Summary

V11 shows **selective improvement** over MiLo's evaluated version but does not resolve the most consequential structural issues. Of the 48 segments MiLo scored that are also present in V11 (S1–S49, excluding S51/52/53), the breakdown is:

- **Improved:** 14 segments — V11 produces a linguistically better or more natural rendering than MiLo's evaluated version
- **Unchanged / Equivalent:** 12 segments — negligible or cosmetic difference, same quality tier
- **Regressed:** 6 segments — V11 is demonstrably worse than MiLo's evaluated version
- **Structural (pipeline-level, unfixable in output):** 16 segments — the segment itself cannot be judged independently because the issue originates from cross-segment split construction

**Key takeaways:**

1. V11 has largely eliminated untranslated grammar meta-terms (nouns → 名詞, verbs → 動詞, etc.), which was MiLo's most recurring vocabulary flag. This is the clearest win.
2. The cross-segment split-sentence bug remains the dominant quality problem. Segments such as S5/S6, S10/S11/S12, S44/S45, S47/S48, S49/S50 all suffer from incomplete meaning — an API-level issue already escalated.
3. V11 regressed on S14 (added untranslated "Prep's foundational series") and several segments where vocabulary leakage was re-introduced.
4. MiLo's suggested combined translations for multi-segment runs (S10–S12, S15–S19, S29–S32, S33–S35) remain unimplemented because the pipeline does not merge segments.
5. Average MiLo baseline is **Accuracy: 69.6 / Naturalness: 73.0** (Section 2). V11 estimated improvement is modest (+3–5 accuracy points) due to vocabulary fixes, but naturalness is unlikely to have improved without segment-merging.

---

## 2. MiLo Average Scores (Baseline)

Scored segments: S1–S15, S18–S49, S51–S53 (49 rows total; S16/S17/S50 absent from MiLo sheet).

| Metric | Count | Average |
|---|---|---|
| Accuracy | 49 | **69.6** |
| Naturalness | 49 | **73.0** |

> S51, S52, S53 are included in these MiLo averages but excluded from the V11 crosscheck table below (absent from V11 output).

---

## 3. Segment-by-Segment Table

| Seg | MiLo Score (Acc/Nat) | MiLo Issue Flagged | V11 Translation | V11 vs MiLo | Notes |
|---|---|---|---|---|---|
| S1 | 70/90 | "big" untranslated | 大家好！歡迎來到 Prep。 | Unchanged | Both versions omit "big welcome"; "big" still lost. |
| S2 | 90/90 | Very good | 很高興大家來參加我們的 Basic Grammar 課程。 | Improved | V11 translates "course" as 課程, removing English leakage. |
| S3 | 70/45 | Not readable | 這裡就是我們將為您打下真正需要的堅實基礎的地方。 | Improved | V11 significantly more readable; "堅實基礎" is natural vs MiLo's convoluted "非常基礎的地方". |
| S4 | 90/70 | 征服 improper; suggest 攻克 | 征服並精通英語。 | Unchanged | V11 keeps 征服 and uses 精通 (better than 掌握) but ignores MiLo's 攻克 suggestion. |
| S5 | 75/50 | Repetition across S5/S6 | 我們前方還有相當長的一段旅程，而我真心相信，了解 | Structural | Sentence cut mid-clause; cross-segment split unfixable at output level. |
| S6 | 75/50 | Split sentence, poor readability | 彼此多些了解，會讓整個過程更順暢、更有效率。 | Structural | S6 alone reads as a fragment; grammatical subject is in S5. |
| S7 | 85/75 | Readability acceptable | 所以在這支第一支影片裡，我們花點時間來做幾件事。 | Regressed | "這支第一支" is clumsy (redundant 支); MiLo's "最一開始的影片" is more natural. |
| S8 | 80/80 | Meaning well reflected | 我將帶您了解目標、內容以及整體學習方式。 | Improved | V11 is cleaner; reads naturally without losing meaning. |
| S9 | 60/80 | Fragment; should delete or merge with S8 | 我們將在這門 course 中學習。 | Unchanged | V11 fixes 這個 → 這門 but keeps "course" in Latin script; merge not implemented. |
| S10 | 55/80 | S10/11/12 should merge | 我希望在課程結束時，您能對以下內容有非常清晰的認識： | Structural | Matches MiLo's version for this row; merging unimplemented. |
| S11 | 55/80 | Should merge with S10/S12 | 未來有許多事情等著您，您也會能自然地融入這裡提供支持的團隊。 | Regressed | "您也會能自然地融入" is grammatically awkward; "融入" (blend in) ≠ "feel comfortable with"; MiLo's version is closer. |
| S12 | 55/80 | Complete merged translation provided | 我們會一直陪伴著你，每一步都支持你。這樣聽起來不錯吧？ | Regressed | V11's "這樣聽起來不錯吧？" is a better match for "Sound good?" but the assurance clause preceding it diverges from source. |
| S13 | 90/90 | Very good | 好，我們開始吧。 | Unchanged | V11 drops 好的 → 好; negligible difference. |
| S14 | 80/83 | "Basic Grammar" should be translated | 因此，Basic Grammar 課程是 Prep's foundational series 的重要組成部分。 | **Regressed** | V11 leaves "Prep's foundational series" fully untranslated — worse than MiLo's version which only kept "Basic Grammar" in Latin script. Clear regression. |
| S15 | 40/80 | S15–S18 should merge | 我們也準備了 Basic Vocabulary，這些課程是一起設計的 | Structural | Sentence incomplete; "是一起設計的" hangs without continuation — pipeline split issue. |
| S18 | 40/80 | Missing words between "designed" and "truly" | 真正理解，並自信地使用一些最常見的用法 | Structural | Mid-sentence fragment; cannot resolve without segment merging. |
| S19 | 40/70 | "English 的詞性" leakage | 英語中的詞性。 | Improved | V11 translates to 英語中的詞性 — removes leakage flagged by MiLo. |
| S20 | 70/80 | S19/20/21 should merge | 讓你完全熟悉基本的英文句子結構， | Structural | Identical to MiLo's version; split issue unresolved. |
| S21 | 70/80 | S19/20/21 should merge | 句子的組成方式，以及不同的句型 | Structural | Identical to MiLo's version; split issue unresolved. |
| S22 | 70/65 | "sentences" leakage | 你會遇到的句子。 | Improved | V11 translates "sentences" as 句子; cleaner than MiLo's "你將會遇到的 sentences". |
| S23 | 90/90 | Very good | 幫助您掌握簡單時態，包括過去式、現在式和未來式。 | Unchanged | Identical quality; V11 matches MiLo's translation. |
| S24 | 60/80 | "those" should be 這些知識點 | 我們會徹底掌握這些。 | Unchanged | V11 uses 徹底 (stronger than MiLo's 確實) but still uses vague 這些; MiLo's suggestion not adopted. |
| S25 | 50/80 | S24/S25 should merge; "basic sentences" leakage | 最後，協助您開始建立自己的基本句型。 | Improved | V11 uses 基本句型 (no leakage); reads more naturally than MiLo's version. |
| S26 | 50/80 | S25/S26 should merge | 在文法上是正確的。 | Structural | Dangling clause; requires S25+S26 merge to resolve. |
| S27 | 90/86 | Good even though split | 這門課程分為六個主要單元，每個單元都著重於 | Improved | V11 uses 這門課程 (more natural) vs MiLo's 本課程; minor but cleaner. |
| S28 | 90/86 | Good even though split | 關於核心文法主題。 | Regressed | V11 adds redundant 關於 — creates awkward phrasing; MiLo's bare 核心文法主題 is better. |
| S29 | 88/73 | Heavy translationese | 在每個課程中，你會找到 2 到 4 個較小的課程或章節。 | Unchanged | Identical to MiLo's version; translationese flag unresolved. |
| S30 | 80/60 | S29/30/31 should merge | 總計共有 23 個課程，每個課程都經過精心設計。 | Unchanged | Identical to MiLo's version; merging not implemented. |
| S31 | 80/60 | "grammar point" leakage; merge needed | 涵蓋任何文法點的三個關鍵面向：其用法， | Improved | V11 uses 文法點 vs MiLo's "grammar point" in Latin script — direct vocabulary improvement. |
| S32 | 80/60 | S29/30/31 merge needed | 其形式，以及它所代表的意義。 | Improved | V11 rewrites as "它所代表的意義" — slightly more natural than MiLo's 其含義. |
| S33 | 70/60 | Grammar terms untranslated | 因此，在整個課程中，我們將探索名詞、動詞， | Improved | V11 translates 名詞、動詞; MiLo left nouns/verbs in Latin script. |
| S34 | 70/60 | Grammar terms untranslated; merge needed | 形容詞和副詞、代名詞、介系詞，以及當然， | Improved | V11 fully translates all terms; MiLo's version retained English. |
| S35 | 70/60 | Merge; grammar terms | 基本句型結構。 | Improved | V11 uses 句型結構 vs MiLo's 句子結構; slightly more technical-accurate. |
| S36 | 85/70 | Relatively acceptable | 現在，我想就某件事坦誠地談談。 | Unchanged | V11 and MiLo near-identical; negligible difference. |
| S37 | 70/60 | Heavy tone; "English grammar" leakage | 這門課程並非旨在涵蓋英語文法的每一個細節。 | Improved | V11 translates "English grammar" as 英語文法; removes leakage. |
| S38 | 60/80 | S37/38 should merge; meaning misaligned | 有些領域相當複雜，確實需要扎實的基礎。 | Unchanged | Identical to MiLo's version; merge not implemented. |
| S39 | 60/80 | S37/38/39 should merge | 在發音和詞彙方面，如果你無法有效掌握它們。 | Regressed | V11 rewrites as a negative conditional "如果你無法有效掌握它們" — semantically inverted from source ("before you can tackle them effectively"). |
| S40 | 80/80 | Relatively good | 我們會把這些進階主題留到中階和高階課程。 | Unchanged | V11 slightly shorter than MiLo's version; both natural and accurate. |
| S41 | 80/80 | Relatively good | 這裡的重點在於重質不重量。 | Improved | V11's 重質不重量 is a well-known Chinese idiom; vastly more natural than MiLo's literal 專注於品質，而非數量. |
| S42 | 75/60 | Slight AI tone | 我們將深入講解，確保你真正理解， | Unchanged | V11 uses 深入講解 vs MiLo's 深入探討 — marginally different, same quality tier. |
| S43 | 70/60 | S41/42 form one sentence | 並培養能長久持續的技能。 | Structural | Fragment dependent on S42; split issue persists. |
| S44 | 50/70 | S43/44 split; translation based on fragment | 你會注意到，我們在這邊 Prep 的教學方法有一點不同 | Structural | "這邊 Prep" is unnatural phrasing; cross-segment split (S44/45) is the core issue, escalated. |
| S45 | 50/70 | Split sentence | 來自傳統語法課程。 | Structural | "來自" as sentence opener is a literal calque that fails in isolation; cross-segment bug. |
| S46 | 80/60 | Heavy translationese | 我們致力於賦能您，成為積極主動、獨立自主的學習者。 | Unchanged | "賦能" is more contemporary than MiLo's "賦予您力量" but both carry translationese; similar quality. |
| S47 | 60/70 | S46/47 form one sentence | 我們希望您培養能持續提升英語能力的技能。 | Unchanged | V11 and MiLo translations are identical. |
| S48 | 60/70 | Split sentence → mistranslation | 即使這門課程結束了。 | Structural | Fragment; "即使…了" is a subordinate clause with no main clause — unfixable without S47+S48 merge. |
| S49 | 60/70 | Split sentence → mistranslation | 因此，我們不會只是丟出一堆 grammar rules，而是會採用以下方法 | Structural | "grammar rules" leakage; "採用以下方法" sets up S50 but is itself a cut sentence. |

---

## 4. Coverage Gaps

### Segments in V11 with no MiLo score

| Seg | V11 Translation | Observation |
|---|---|---|
| S16 | 為你在所有重要領域打下堅實的基礎。 | Continuation of S15; readable within split context. "重要領域" reasonable for "key areas." |
| S17 | 在這門課程中，我們的具體目標是：確保你能記住， | Natural lead-in; "具體目標" is good. Fragment continues into S18/S19. |
| S50 | 一種稱為 Guided Discovery 的方法。 | Names the method introduced in S49; "Guided Discovery" kept in Latin script by design (brand term). Acceptable. |

### Segments MiLo evaluated absent from V11

| Seg | MiLo TW | MiLo Score | Status |
|---|---|---|---|
| S51 | 請將這視為一種積極探索語言的過程，並會得到我的一些引導。 | 40/60 | Absent from V11 — likely consolidated into S49/S50 in the revised source script. |
| S52 | 運作方式如下。 | 80/80 | Absent from V11 — segmentation mismatch; content may continue beyond S50 in the full script. |
| S53 | 我不會只是列出一堆 rules 對您進行填鴨式教學。 | 75/80 | Absent from V11 — same segmentation gap; "rules" leakage flagged by MiLo. |

> S51–S53 are not regressions — they reflect a different source script boundary. Reconciliation with the production script is needed.

---

## 5. Issues Addressed by V11

| MiLo Flag | Segments | V11 Resolution |
|---|---|---|
| Untranslated grammar meta-terms (nouns, verbs, adjectives, etc.) | S33, S34, S35 | V11 translates all: 名詞、動詞、形容詞、副詞、代名詞、介系詞 |
| "grammar point" in Latin script | S31 | V11 uses 文法點 |
| "English grammar" leakage | S37 | V11 uses 英語文法 |
| "sentences" leakage | S22 | V11 uses 句子 |
| "basic sentences" leakage | S25 | V11 uses 基本句型 |
| "English 的詞性" leakage | S19 | V11 uses 英語中的詞性 |
| "basic grammar course" partially in Latin script | S2 | V11 renders as Basic Grammar 課程 (course translated) |
| Unnatural literal "quality over quantity" | S41 | V11 uses idiomatic 重質不重量 |
| S3 unreadable construction | S3 | V11 restructured to 打下…堅實基礎的地方 |

---

## 6. Issues NOT Addressed

### (a) Fixable in pipeline / post-processing

| Issue | Segments | Recommended Fix |
|---|---|---|
| "big" untranslated in "big welcome" | S1 | 大家好！熱烈歡迎來到 Prep。 |
| 征服 improper collocation | S4 | Replace with 攻克 |
| "those" vague 這些 | S24 | Replace with 這些知識點 |
| "course" leakage in S9 | S9 | 這門課 (remove Latin "course") |
| "Prep's foundational series" fully untranslated | S14 | Prep 基礎系列課程 |
| 關於 in S28 redundant | S28 | Remove 關於: just 核心文法主題 |
| "grammar rules" leakage in S49 | S49 | Replace with 文法規則 |
| S39 semantically inverted | S39 | 在發音和詞彙方面需要扎實基礎，才能有效掌握這些內容。 |
| S11 "融入" wrong meaning; "您也會能" awkward | S11 | 您將對前方的旅程有所了解，也會對這個全程陪伴您的支援團隊感到安心。 |
| S7 redundant classifier "這支第一支" | S7 | 所以在這支第一部影片裡，我們花點時間來做幾件事。 |

### (b) Requires API-level change

| Issue | Segments | Reason |
|---|---|---|
| Cross-segment sentence splits producing fragments | S5/S6, S10–S12, S15–S19, S20/S21, S25/S26, S29–S32, S33–S35, S43, S44/S45, S47/S48, S49/S50 | Pipeline processes segments individually; no cross-segment context window |
| MiLo-recommended segment merges | S10–S12, S15–S19, S29–S32, S33–S35 | Requires pre-merge before translation or post-merge with retranslation |

---

## 7. Persistent Structural Issues (API-Level, Escalated)

| Segment Group | Nature of Split | Impact on Output |
|---|---|---|
| **S44 / S45** | "is a little different / from traditional grammar classes" — prepositional phrase orphaned | S45 "來自傳統語法課程" reads as an independent clause with no verb |
| **S38 / S39** | Conditional clause split across segments | V11 S39 inverts logic to negative conditional; meaning reversed from source |
| **S5 / S6** | "getting to know / each other" — object split | Repeated 了解 across segments; MiLo flagged semantic repetition |
| **S47 / S48** | "continue improving your English / even after this course is over" | S48 is a free-standing subordinate clause with no anchor |
| **S49 / S50** | "we'll be using / a method called Guided Discovery" | S49 ends incomplete; S50 starts with method name mid-sentence |
| **S25 / S26** | "creating your own basic sentences / that are grammatically correct" — relative clause orphaned | S26 "在文法上是正確的" is headless |
| **S10 / S11 / S12** | Three-segment complex sentence | All three score 55/80 independently; MiLo provided a complete merged translation |
| **S15–S19** | Five-segment run; main clause "designed to" arrives in S18 | S15/S18/S19 are meaningless fragments without preceding context |

---

## 8. Recommended Manual Fixes (Priority Order)

| Priority | Seg | V11 Text | Fix |
|---|---|---|---|
| 1 | **S14** | …Prep's foundational series 的重要… | → …Prep 基礎系列的重要… |
| 2 | **S39** | 在發音和詞彙方面，如果你無法有效掌握它們。 | → 在發音和詞彙方面需要扎實基礎，才能有效掌握這些內容。 |
| 3 | **S11** | 您也會能自然地融入這裡提供支持的團隊。 | → 您也會對這個全程陪伴您的支援團隊感到安心。 |
| 4 | **S28** | 關於核心文法主題。 | → 核心文法主題。 |
| 5 | **S7** | 在這支第一支影片裡 | → 在這支第一部影片裡 |
| 6 | **S4** | 征服並精通英語。 | → 攻克並精通英語。 |
| 7 | **S9** | 這門 course 中學習 | → 這門課中學習 |
| 8 | **S24** | 我們會徹底掌握這些。 | → 我們會徹底掌握這些知識點。 |
| 9 | **S49** | 一堆 grammar rules | → 一堆文法規則 |
| 10 | **S1** | 大家好！歡迎來到 Prep。 | → 大家好！熱烈歡迎來到 Prep。 |

---

*Report generated 2026-05-15. Crosscheck covers 49 shared segments (S1–S49). Coverage gaps: S16/S17/S50 in V11 only; S51/S52/S53 in MiLo only. MiLo baseline: Accuracy 69.6 / Naturalness 73.0.*
*Cross-referenced against: V9-vs-V11-Crosscheck-Report.md, Manager-Escalation-API-Pipeline-Issues.md*
