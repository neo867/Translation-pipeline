# Translation Review Summary — Thai (TH) & Traditional Chinese (TW)
## V9 Engine · Review Findings

---

## Overview

Three content types were reviewed across both languages: **UI strings**, **Explanations**, and **Subtitles**. Each item was rated on two independent dimensions — accuracy and naturalness — on a 0–100 scale.

| Rating band | Score range |
|---|---|
| Satisfactory | 70–100 |
| Poor | 50–69 |
| Unacceptable | 0–49 |

---

## Thai (TH) — Score Dashboard

150 items reviewed (50 per content type).

| Content Type | Accuracy Pass | Accuracy Fail | Naturalness Pass | Naturalness Fail |
|---|---|---|---|---|
| Explanations | 46% | 54% | 34% | 66% |
| Subtitles | 38% | 62% | 24% | 76% |
| UI strings | 62% | 38% | 30% | 70% |
| **All content** | **49%** | **51%** | **29%** | **71%** |

**Headline:** Half of all Thai translations fail on accuracy. Seven in ten fail on naturalness. Naturalness is the more urgent problem — the engine often conveys the correct meaning but rarely reads the way a Thai speaker would naturally write or speak.

---

## Traditional Chinese (TW) — Score Overview

50 UI strings, 53 subtitle segments, and 50 explanation texts reviewed.

| Content Type | General finding |
|---|---|
| UI strings | Strong. Majority score 90/90 on accuracy and naturalness. |
| Explanations | Mostly accurate. Large cluster at 89–95 accuracy, 80–90 naturalness. |
| Subtitles | Most problematic. Significant number of low naturalness scores, several accuracy failures. |

No full pass/fail dashboard was compiled for TW, but the pattern is clear: UI and explanations perform well; subtitles underperform consistently.

### TW Subtitle Scores — Baseline and Target

A separate evaluation of 50 subtitle segments (Lesson 1, Basic Grammar intro) by MiLo established the following reference numbers:

| Metric | MiLo baseline | After client-side fixes | Target |
|---|---|---|---|
| Accuracy avg | ~69 | ~73–75 | ≥ 80 |
| Naturalness avg | ~73 | ~75–76 | ≥ 78 |
| Split-sentence errors | ~15 / 50 segments | ~8–10 / 50 | ≤ 3 / 50 |
| Grammar term errors | 5–7 / 50 segments | 5–7 / 50 (unchanged) | 0 / 50 |

Client-side fixes (switching to single-translate mode with the preceding segment appended to the context field) improved accuracy by ~4–6 points but cannot close the remaining gap. The accuracy and naturalness targets are not reachable without API-level changes. See Report 2 for detail.

---

## What Went Well

### Traditional Chinese
- Simple transactional UI terms (checkout, payment, address, apply, total price) translate at 90/90 consistently.
- Explanation strings with clear logical structure (keyword identification, "the passage states…", option elimination) score 89–95 accuracy.
- Subtitle segments that form a complete, standalone thought translate well (segs 2, 13, 23, 27–28, 40–41, 52).

### Thai
- UI accuracy is the highest of the three content types at 62% pass — most field labels and button labels are correctly understood.
- Formulaic explanation items (grammar terminology, test-taking instructions) perform well where phrasing is predictable.

---

## What Did Not Go Well

### Issues Common to Both Languages

| Issue | Severity |
|---|---|
| Translationese — English sentence structure preserved in output | High |
| Split-sentence translation producing incoherent subtitle output | Critical |
| English domain terms left untranslated when target-language equivalents exist | High |
| Corrupted or unintelligible output in specific segments | Critical (TH) |

### Thai-Specific Issues

| Issue | Severity | Notes |
|---|---|---|
| ค่ะ/ครับ applied to UI strings, sentence fragments, and mid-list items | Critical | Most frequent single error class across all 150 items |
| โปรโมชั่น used instead of prescribed house spelling โพรโมชัน | High | Appears in 8+ UI items; informal/spoken form used in formal written context |
| Cultural and register mismatches | High | See detail below |
| Mai Yamok (ๆ) spacing violations | Medium | Must have space before and after |
| Passive voice constructions | Medium | Thai strongly prefers active voice; passive is rare in natural Thai |
| Dual-language artefacts | Medium | Thai and English appear side by side in output (e.g. ขนมปังเก่า old bread) |
| English punctuation imported into Thai | Medium | Colons and em-dashes do not appear in natural Thai prose |

### Cultural and Register Mismatches (TH — Detail)

| Term used | Problem | Correct approach |
|---|---|---|
| ปฐมนิเทศ for "orientation" | In Thai culture this refers specifically to new staff/student welcome events — not course orientation | Use a general orientation term appropriate to e-learning context |
| ศิษย์ for "student" | Extremely formal/archaic register — inappropriate for an online learning platform's learner persona | Use นักเรียน or ผู้เรียน |
| มัน as third-person "it" | Impolite in Thai educational materials | Never use มัน in place of "it" in this context |
| ชอปปิง for course purchase | Implies recreational shopping for non-essentials — wrong register for course purchase | Use appropriate e-commerce or educational purchase language |
| กอร์ส for "course" | Not a Thai word | Use คอร์ส or หลักสูตร |
| โปรโมชั่น | Informal spoken-form loanword | Use Royal Society prescribed โพรโมชัน in all written UI |

### TW-Specific Issues

| Issue | Notes |
|---|---|
| Word collocation errors | 活動 (activity/event) used where 優惠 (discount/deal) is more natural in promotional contexts |
| Untranslated words | "available" left in English in one UI string |
| Suboptimal term choices | 訂單付款 vs preferred 訂單支付; 開立 vs preferred 開具 |
| One outright mistranslation | 申請 (to apply/apply for) used for "use a coupon" — should be 應用 |
| Non-deterministic negation dropping | Source negations ("isn't meant to", "doesn't") are dropped in the output — reversing the meaning. Affects ~1–2/50 segments but severity is critical when it occurs. |

**Negation dropping — confirmed example (TW subtitles, S37):**
- Source: *"This course isn't meant to cover every single detail of English grammar."*
- Erroneous output: `本課程旨在涵蓋英語文法的所有細節。` — *"This course IS meant to cover…"* (meaning reversed)
- Correct: `本課程並非旨在涵蓋英語文法的所有細節。`

This error is non-deterministic: the negation was preserved in 1 of 3 test runs and dropped in 2, with no input or parameter change between runs. The instruction `"Preserve all negations and sentence meaning precisely."` was present in the context string on all runs and had no consistent effect. This points to the pipeline's revision stage non-deterministically dropping negation markers under load.

---

## Key Observations

**The accuracy-to-naturalness gap is the defining characteristic of this engine's output.** Across all TH content types there is approximately a 20-point gap between accuracy pass rates and naturalness pass rates. The engine conveys the right meaning more reliably than it produces text that reads naturally. For a learning platform, naturalness is the higher-priority metric — learners who encounter clunky subtitles or awkward UI copy lose confidence in the product.

**UI is the one content type where accuracy is majority-passing for TH**, but even UI fails naturalness at scale — almost entirely because of the ค่ะ/ครับ register problem, which is a prompt-level rule gap, not a model capability gap.

**TW UI quality is substantially better than TH UI**, with most TW items scoring 90/90. The gap is explained by the absence of a TW equivalent of the ค่ะ/ครับ problem and fewer cultural register constraints.

**Corrupted output is a separate category of failure from translation quality.** Several TH items (Explanations 20, 32, 33, 45; Subtitle segment 10) show garbled text, embedded English characters in Thai, and missing tone marks. The subtitle segment 10 output was flagged by the reviewer as inconsistent with any AI translation failure mode — likely an encoding or data-handling issue that requires a separate investigation rather than a prompt fix.
