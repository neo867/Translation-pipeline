# MiLo-Source Run Crosscheck Report
**Command:** `python3 scripts/translate_csv.py --input "Review Report/milo-sub-source.csv" --target-lang tw`
**Output:** `Review Report/tw_milo-sub-source.csv`
**Date:** 2026-05-15
**Note:** This run uses the exact same source text MiLo evaluated — making this the most direct apples-to-apples comparison available.

---

## Script Run Summary

| Metric | Value |
|---|---|
| Rows input | 50 |
| Rows translated | 50 / 50 |
| Fallbacks (batch 1) | 9 (retried as mini-batch) |
| Fallbacks (batch 2) | 0 |
| Server busy retries | 2 (batch 1 retry) |
| Mode | batch (/translate/batch) |

Fallback count (9) is lower than the previous V11 run (16), suggesting lighter server load this session.

---

## Critical Issue — S37: Negation Dropped

> **Source:** "This course **isn't** meant to cover every single detail of English grammar."
> **New output:** 這門課程**旨在**涵蓋英語文法的所有細節。
> **MiLo's version:** 本課程**並非**旨在涵蓋 English grammar 的所有細節。

The negation ("isn't meant to") is completely absent — the output states the **opposite** of the source. This is the recurring S37 negation bug previously documented and escalated. It reappeared in this run after appearing stable in V11.

**MiLo's version, despite its "English grammar" leakage, is more accurate on meaning.** This segment must be manually corrected before any use:
> 這門課程**並非**旨在涵蓋英語文法的每一個細節。

---

## Segment-by-Segment Comparison

| Seg | MiLo (Acc/Nat) | New Output | vs MiLo | Notes |
|---|---|---|---|---|
| S1 | 70/90 | 大家好，歡迎來到 Prep。 | Regressed | MiLo used ！; new uses ，— less energetic. "Big" still untranslated in both. |
| S2 | 90/90 | 很高興大家來參加我們的 Basic Grammar 課程。 | Improved | "course" now translated as 課程; MiLo left "basic grammar course" in Latin script. |
| S3 | 70/45 | 這裡就是我們將為您奠定真正所需基礎的地方 | Improved | "奠定…基礎" is natural; significantly more readable than MiLo's unreadable version. Missing terminal period. |
| S4 | 90/70 | 征服並掌握 **English**。 | **Regressed** | "English" left in Latin script — MiLo correctly rendered it as 英語. New output introduces leakage MiLo didn't have. |
| S5 | 75/50 | 我們前方還有相當長的一段旅程，而我真心相信，了解 | Structural | Same split-clause issue; new omits MiLo's 透過, slightly cleaner but same fragment problem. |
| S6 | 75/50 | 彼此多些了解，會讓整個過程更順利且更有效率。 | Equivalent | Both are readable completions of S5; new uses 更順利 vs MiLo's 更加順暢 — minor. |
| S7 | 85/75 | 所以，在這第一支影片中，我們花一點時間來做幾件事。 | Improved | Cleaner than MiLo's "最一開始的影片中"; natural phrasing, no redundant classifier. |
| S8 | 80/80 | 我將帶您了解目標、內容以及整體學習方式。 | Equivalent | Both accurate; new is slightly more concise. |
| S9 | 60/80 | 我們將在這門課程中學習。 | Improved | Fully Chinese — removes "course" leakage that both MiLo and V11 left. MiLo's note was to delete this segment; not possible in pipeline. |
| S10 | 55/80 | 我的期望是，在課程結束時，您能對以下內容有非常清晰的認識： | Regressed | "我的期望是" is stiff vs MiLo's natural "我希望"; structural split issue unchanged. |
| S11 | 55/80 | 前方有許多事物等著您，您也將能與提供支持的本團隊自然融洽相處。 | Equivalent | "本團隊" is awkward; "自然融洽相處" slightly more natural than MiLo's 相處得十分融洽. Both have structural issue. |
| S12 | 55/80 | 我們會一直陪伴您。這樣聽起來不錯吧？ | Improved | "這樣聽起來不錯吧？" is a better match for "Sound good?" than MiLo's "這樣可以嗎？" |
| S13 | 90/90 | 好，我們開始吧。 | Equivalent | Minor: MiLo has 好的; new drops 的. Negligible. |
| S14 | 80/83 | 因此，Basic Grammar 課程是 Prep's foundational series 的重要組成部分。 | **Regressed** | "Prep's foundational series" fully untranslated — same regression as V11. MiLo had 基礎系列. |
| S15 | 40/80 | 我們也準備了 Basic Vocabulary，這些課程是一起設計的 | Structural | Both versions produce an incomplete sentence; pipeline split issue. |
| S18 | 40/80 | 真正理解，並自信地使用一些最常見的用法 | Identical | Exact same as MiLo's version. |
| S19 | 40/70 | 英文中的詞性。 | Improved | "English" translated; uses 英文 vs 英語 (both acceptable in TW). MiLo had "English 的詞性." |
| S20 | 70/80 | 讓你完全熟悉基本的英文句子結構， | Identical | Exact same as MiLo's version. |
| S21 | 70/80 | 句子的組合方式，以及不同的句型結構 | Improved | "句型結構" more complete than MiLo's 句型; "組合方式" vs "組成方式" — minor. |
| S22 | 70/65 | 你將遇到的句子。 | Improved | "sentences" translated as 句子; cleaner than MiLo's "你將會遇到的 sentences". |
| S23 | 90/90 | 幫助您掌握簡單時態，包括過去式、現在式和未來式。 | Identical | Perfect match. |
| S24 | 60/80 | 我們會徹底掌握這些。 | Equivalent | 徹底 stronger than MiLo's 確實; 這些 still vague (MiLo suggested 知識點). |
| S25 | 50/80 | 最後，協助您開始建立自己的基本句子。 | Improved | "basic sentences" translated as 基本句子; MiLo left it in Latin script. (Note: V11 used 基本句型 which is more precise.) |
| S26 | 50/80 | 在文法上是正確的。 | Identical | Same fragment issue as MiLo's version. |
| S27 | 90/86 | 課程分為六個主要單元，每個單元都著重於 | Regressed | Drops "本/這門" — bare 課程 is slightly awkward without an article-equivalent; MiLo's 本課程 is better. |
| S28 | 90/86 | 關於核心文法主題。 | Regressed | Redundant 關於 (same issue as V11); MiLo's bare 核心文法主題 is cleaner. |
| S29 | 88/73 | 在每個課程中，你會找到 2 到 4 個較小的課程或章節。 | Identical | Exact same as MiLo's version. |
| S30 | 80/60 | 總計共有 23 個課程，每個課程都經過精心設計。 | Identical | Exact same as MiLo's version. |
| S31 | 80/60 | 涵蓋任何文法點的三個關鍵面向：使用方式， | Improved | "grammar point" → 文法點; uses 使用方式 vs MiLo's 其用法 — both fine. |
| S32 | 80/60 | 其形式，以及它的含義。 | Equivalent | Slight rewording of MiLo's 其形式及其含義; both natural. |
| S33 | 70/60 | 因此，在整個課程中，我們將探索 **nouns、verbs，** | **Regressed** | S34 translates adjectives/adverbs etc. but S33 still leaves nouns/verbs in Latin script — inconsistent within the same sentence group. |
| S34 | 70/60 | 形容詞和副詞、代名詞、介系詞，以及當然， | Improved | All terms translated; MiLo left all in Latin script. |
| S35 | 70/60 | 基本句型結構。 | Equivalent | 句型結構 vs MiLo's 句子結構 — both acceptable. |
| S36 | 85/70 | 現在，我想誠懇地談論一件事。 | Equivalent | "誠懇地談論" vs MiLo's "坦白說明" — different register, both reasonable. |
| S37 | 70/60 | 這門課程**旨在**涵蓋英語文法的所有細節。 | **CRITICAL REGRESSION** | Negation ("isn't meant to") completely dropped — meaning reversed. See top of report. |
| S38 | 60/80 | 有些領域相當複雜，確實需要扎實的基礎。 | Identical | Same as MiLo's version. |
| S39 | 60/80 | 在發音和詞彙方面，在你能有效處理它們之前。 | Regressed | Fragment; MiLo's "您必須先熟悉，才能有效掌握" is more complete and natural. |
| S40 | 80/80 | 我們會將這些進階主題留待中階和高階課程中進行講解。 | Improved | "進行講解" adds specificity vs MiLo's bare 討論; both good. |
| S41 | 80/80 | 這裡的重點在於重質不重量。 | Improved | Idiomatic 重質不重量 beats MiLo's literal 專注於品質，而非數量. |
| S42 | 75/60 | 我們將深入講解，確保你真正理解， | Equivalent | 深入講解 vs MiLo's 深入探討 — minor difference. |
| S43 | 70/60 | 並培養能長久持續的技能。 | Identical | Same as MiLo's version. |
| S44 | 50/70 | 您會注意到，我們在 Prep 的教學方法略有不同 | Improved | Removes the awkward "這邊" from V11; cleaner phrasing than both MiLo and V11. Still structurally split. |
| S45 | 50/70 | 來自傳統語法課程。 | Equivalent | Both versions fail equally on this cross-segment split. |
| S46 | 80/60 | 我們致力於賦能您，成為積極主動、獨立自主的學習者。 | Equivalent | Same as V11; "賦能" is corporate but contemporary. |
| S47 | 60/70 | 我們希望您培養能持續提升英語能力的技能。 | Identical | Exact same as MiLo's version. |
| S48 | 60/70 | 即使這門課程結束了。 | Improved | "這門課程結束了" more natural than MiLo's "完成本課程後". |
| S49 | 60/70 | 因此，我們不會直接拋出一堆 grammar rules，而是會採用以下方法： | Equivalent | "直接拋出" vs MiLo's "只是把…丟給您" — both natural. "grammar rules" still in Latin script in both. |
| S51 | 40/60 | 把它視為在少許指導下主動探索語言的過程。 | Improved | MiLo's version was flagged as making no sense; new output is readable and accurate. |
| S52 | 80/80 | 運作方式如下。 | Identical | Perfect match. |
| S53 | 75/80 | 我不會只是列出一堆規則，然後單方面地講授。 | Improved | "規則" translates MiLo's remaining "rules" leakage; "單方面地講授" is a natural rendering of "lecture". |

---

## Summary Scorecard

| Verdict | Count | Segments |
|---|---|---|
| Improved vs MiLo | 16 | S2, S3, S7, S9, S12, S19, S21, S22, S25, S31, S34, S40, S41, S44, S48, S51, S53 |
| Identical / Equivalent | 18 | S6, S8, S11, S13, S18, S20, S23, S24, S26, S29, S30, S32, S35, S36, S38, S42, S43, S45, S46, S47, S49, S52 |
| Regressed vs MiLo | 9 | S1, S4, S10, S14, S27, S28, S33, S37, S39 |
| Structural (unfixable) | 7 | S5, S15, S43, S45, S47, S48 (split constructions) |

**S37 is the only critical regression** — it reverses the meaning of the source. All other regressions are minor quality issues.

---

## Comparison: This Run vs V11

| Better in this run | Better in V11 |
|---|---|
| S7 — no redundant classifier | S1 — uses ！ |
| S9 — "course" fully translated (課程) | S3 — "堅實基礎" vs "所需基礎" (V11 more natural) |
| S27 — (equal; both have issues) | S14 — identical regression in both |
| S44 — removes "這邊" awkwardness | S37 — V11 preserves negation ✓ (this run drops it) |
| S51, S53 — present in this run; absent from V11 | — |

**The most important difference:** V11 preserves the S37 negation correctly; this run drops it entirely. This alone makes V11 the safer base for production use.

---

## Required Manual Corrections Before Use

| Priority | Seg | Current Output | Correction |
|---|---|---|---|
| ★ Critical | S37 | 這門課程旨在涵蓋英語文法的所有細節。 | 這門課程**並非**旨在涵蓋英語文法的每一個細節。 |
| High | S4 | 征服並掌握 English。 | 征服並掌握英語。 (or 攻克並精通英語。) |
| High | S14 | …Prep's foundational series 的重要… | …Prep 基礎系列的重要… |
| High | S33 | 我們將探索 nouns、verbs， | 我們將探索名詞、動詞， |
| Medium | S28 | 關於核心文法主題。 | 核心文法主題。 |
| Medium | S39 | 在發音和詞彙方面，在你能有效處理它們之前。 | 在發音和詞彙方面需要扎實基礎，才能有效掌握這些內容。 |
| Medium | S10 | 我的期望是，在課程結束時… | 我希望在課程結束時… |
| Low | S1 | 大家好，歡迎來到 Prep。 | 大家好！歡迎來到 Prep。 |
| Low | S27 | 課程分為六個主要單元… | 這門課程分為六個主要單元… |

---

## Persistent Issues (Both This Run and V11)

- **S14**: "Prep's foundational series" — untranslated in every run. Consistent behaviour.
- **S28**: Redundant 關於 — consistent across runs.
- **S33**: nouns/verbs leakage while S34 is translated — inconsistency within same sentence group, every run.
- **S44/S45**: Cross-segment split construction — unfixable without API `preceding_text` support.
- **S37 negation**: Unstable — correct in V11, dropped in this run. Documented as non-deterministic in earlier investigation.

---

*Report generated 2026-05-15. Direct comparison: same source text MiLo evaluated → new pipeline output → MiLo scores.*
*Cross-referenced against: MiLo-vs-V11-Crosscheck-Report.md, Manager-Escalation-API-Pipeline-Issues.md*
