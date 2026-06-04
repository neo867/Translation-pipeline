# zhTW Reviewer Correction Examples

Curated before/after pairs from native TW speaker reviews of L1S1, L2S1, and L2S2.
Use this file alongside `zhTW_review_rules.md` during the Claude Code naturalness pass.

**Source files:** zhTW_L1S1_aligned.xlsx · zhTW_L2S1_clean.xlsx · zhTW_L2S2.xlsx
**Reviewer scores:** Accuracy avg 92–98/100 · Naturalness avg 77–89/100
(High accuracy but lower naturalness = correct meaning, awkward phrasing — this is the main issue to fix.)

---

## Category 1 — Register: 您 → 你 (instructor-to-student)

Rule 2. Applies throughout. Highest-frequency correction across all three files.

| Before | After |
|--------|-------|
| 我將會是您這門課程的講師 | 我將會是這門課程的講師 |
| 培養您的 IELTS 聽力技巧 | 培養你的雅思聽力技巧 |
| 幫助您在考試中取得高分 | 幫助你在考試中取得高分 |
| 讓您能夠更有效地學習 | 讓你能夠更有效地學習 |

---

## Category 2 — Terminology: 雅思 / 講者 / 同義改寫

| Before | After | Rule |
|--------|-------|------|
| IELTS 中級聽力課程 | 中級雅思聽力課程 | Rule 1 |
| IELTS 考試 | 雅思考試 | Rule 1 |
| 講者的口音 | 說話者的口音 | Rule 3 — `講者` is HK usage; TW uses `說話者` |
| 改述技巧 | 同義改寫技巧 | Rule 3 — `同義改寫` is the standard TW IELTS term for paraphrasing |
| 換句話說的能力 | 同義改寫的能力 | Rule 3 |

---

## Category 3 — Formality: 聆聽 → 聽

`聆聽` is too literary for spoken/subtitle context. Use `聽` throughout.

| Before | After |
|--------|-------|
| 聆聽意義 | 聽意思 |
| 聆聽能力 | 聽力能力 / 聽的能力 |
| 聆聽技巧 | 聽力技巧 |

---

## Category 4 — Word choice: colloquial substitutions

| Before | After | Note |
|--------|-------|------|
| 表達相同的意思 | 表達一樣的意思 | `一樣` more colloquial than `相同` |
| 與其匆忙地做許多測驗 | 與其倉促地做很多回聽力測驗 | `倉促` more idiomatic; add specificity |
| 記住三個轉述層次 | 記住三種同義改寫 | Domain-specific TW IELTS term |
| 徹底練習 | 扎實練習 | `扎實` = solid/thorough practice in TW usage |
| 然而 | 不過 | Spoken register — `不過` is more natural |
| 因此 | 所以 | Spoken register |
| 獲得高分 | 拿到高分 | `拿到` is more colloquial |

---

## Category 5 — Syntax and sentence flow

| Before | After | Note |
|--------|-------|------|
| 考生每段錄音只會聽到一次 | 每段錄音，考生只會聽到一次 | Topic-comment word order; comma after topic |
| 於螢幕上輸入答案 | 直接於螢幕上輸入答案 | `直接` adds natural emphasis that was implied in English |
| 這是一門關於雅思聽力的課程 | 這是一門雅思聽力課程 | Simplify `關於…的` noun stacks |

---

## Category 6 — Punctuation

Rule 7 (mechanical) and Rule 8 (naturalness pass).

| Before | After | Note |
|--------|-------|------|
| 『關鍵字』 | 「關鍵字」 | Rule 7 — 『』→「」(auto-fixed by script) |
| 題目，博物館位於河邊。 | 題目：博物館位於河邊。 | Rule 8 — colon introduces example/definition |
| 例如，這個詞。 | 例如：這個詞。 | Rule 8 |

---

## Category 7 — Subject/pronoun handling

| Before | After | Note |
|--------|-------|------|
| 它們是不同的表達方式 | 它是一種不同的表達方式 | IELTS/雅思 as a test = singular `它` |
| 我們大家一起來練習 | 我們來練習 | Drop redundant `大家` when `我們` already covers it |

---

## Reviewer score benchmarks

| File | Avg Accuracy | Avg Naturalness | Correction Rate |
|------|-------------|-----------------|-----------------|
| L1S1 | 97.5/100 | 77.3/100 | 74.7% |
| L2S1 | 91.4/100 | 89.2/100 | 47.9% |
| L2S2 | 92.6/100 | 84.9/100 | 83.0% |

**Target:** Naturalness ≥ 90/100. The main gap in L1S1 was register (您) and vocabulary (聆聽, 講者). L2S2's gap was primarily word choice and paraphrasing terminology.
