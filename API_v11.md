# Translation API — v11

The Translation API is a public HTTP service for high-quality machine translation and translation review across **15 languages** and **210 N×N language pairs**. Every supported source language can translate into every other supported language; no en-pivot.

| Field | Value |
|---|---|
| **Base URL** | `https://translate.flowb.ai` |
| **Auth** | `X-API-Key: <your-key>` header on every POST. GETs are public. |
| **Transport** | HTTPS only. HTTP is 301-redirected. |
| **Encoding** | `Content-Type: application/json; charset=utf-8`. UTF-8 in, UTF-8 out. |
| **Idempotent caching** | Identical request bodies hit a content-hashed cache and skip the model. Bypass with `"no_cache": true`. |
| **Streaming** | Not supported. All endpoints are request/response. |

Everything in this document is current. The companion `GET /help` endpoint returns a machine-readable version of this reference.

---

## 1. 60-second smoke test

```bash
# Sanity check — no auth needed.
curl -s https://translate.flowb.ai/ \
  | jq '{name, version, pairs: (.available_pairs | length)}'
# → {"name":"Translation API","version":"...","pairs":210}

# One translation.
curl -s -X POST https://translate.flowb.ai/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{"text":"Hello, how are you?","source_lang":"en","target_lang":"vi"}' \
  | jq
```

```json
{
  "translation": "Xin chào, bạn khỏe không?",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "confidence_breakdown": { "meaning": "high", "style": "high", "purity": "high" },
  "elapsed_s": 5.74,
  "cached": false,
  "source_lang": "en",
  "target_lang": "vi"
}
```

Expected timing: **5–15 s** on a cache miss, **~50 ms** on a cache hit.

---

## 2. Languages

15 languages × 15 languages = **210 directional pairs**. Every code below is valid as both `source_lang` and `target_lang`, and every (source, target) combination is supported.

| Code | Language | Script | Notes |
|---|---|---|---|
| `en` | English | Latin | The lingua franca; default source. |
| `vi` | Vietnamese | Latin (with diacritics) | Standard Northern register. |
| `zhTW` | Taiwanese Mandarin | Traditional Han | Taiwan locale, Traditional characters. |
| `zhCN` | Simplified Chinese | Simplified Han | Mainland China locale. |
| `ko` | Korean | Hangul | Standard Korean. |
| `ja` | Japanese | Kanji + Hiragana/Katakana | Standard Japanese. |
| `th` | Thai | Thai | Polite particles `ค่ะ`/`ครับ` resolved via `speaker.gender`. |
| `id` | Indonesian | Latin | Bahasa Indonesia. |
| `esES` | Castilian Spanish | Latin | Spain — `tú` register. |
| `esLA` | Neutral Latin American Spanish | Latin | Region-neutral LATAM. |
| `esAR` | Argentine Rioplatense Spanish | Latin | `vos`/`voseo` forms in longer text. |
| `pt` | European Portuguese | Latin | Portugal — `tu` + EU vocabulary (`ficheiro`, `ecrã`, `telemóvel`). |
| `ptBR` | Brazilian Portuguese | Latin | `você` + BR vocabulary (`arquivo`, `tela`, `celular`). |
| `hi` | Hindi (Modern Standard) | Devanagari | `आप` polite register by default. |
| `ur` | Urdu (Modern Standard) | Perso-Arabic Nastaliq | `آپ` polite register by default. |

### Variant families
When a language has multiple regional variants, **always pick the variant code** that matches your audience — the model treats them as different targets, not synonyms.

| Family | Variants |
|---|---|
| Chinese | `zhCN`, `zhTW` |
| Spanish | `esES`, `esLA`, `esAR` |
| Portuguese | `pt`, `ptBR` |
| Hindustani | `hi`, `ur` |

Variant-pair example translations of `"Hello, how are you?"`:

| Pair | Output |
|---|---|
| `en → esES` | `Hola, ¿cómo estás?` (`tú` assumed) |
| `en → esAR` | `Hola, ¿cómo estás?` — `vos`/`tenés` forms appear in longer text |
| `en → pt` | `Olá, como estás?` (`tu`) |
| `en → ptBR` | `Olá, como você está?` (`você`) |
| `en → hi` | `नमस्ते, आप कैसे हैं?` |
| `en → ur` | `سلام، آپ کیسے ہیں؟` |

### Listing languages programmatically
```bash
curl -s https://translate.flowb.ai/languages | jq '.languages | keys'
```

---

## 3. Authentication

Every POST requires:

```
X-API-Key: <your-key>
```

Public GETs (`/`, `/health`, `/languages`, `/help`) do **not** require auth. All other endpoints — `/info`, `/models/status`, `/cache/stats`, `/review/cache/stats`, `/tm/*`, and every POST — return `401 invalid or missing X-API-Key` without a valid key.

```bash
export TRANSLATOR_API_KEY="..."  # provided to you out-of-band
```

---

## 4. Endpoint matrix

| Endpoint | Use when | Cap |
|---|---|---|
| `POST /translate` | One source text → one target language. | 2 000 source chars |
| `POST /translate/batch` | Many source texts → **the same** target language. | 50 texts/req, 2 000 chars each |
| `POST /translate/multi` | **One** source text → many target languages. | 15 targets/req, 2 000 chars |
| `POST /review` | Score one (source, translation) pair. | 2 000 src / 4 000 translation |
| `POST /review/batch` | Score many pairs against the **same** language pair. | 50 pairs/req |

> **There is no `/review/multi`.** Review always operates on a single (source, target) language pair per call. To review the same source against translations into many target languages, fan out one `/review/batch` call per target.

For an N × M job (N texts × M targets), loop **N calls of `/translate/multi`** (cheaper — one inflight slot per text), or **M calls of `/translate/batch`** if M is small and N is large.

### Public GET endpoints (no auth)

| Endpoint | Returns |
|---|---|
| `GET /` | Service identity + the full list of supported pairs. |
| `GET /health` | `{"status":"ok"}` — liveness probe. |
| `GET /languages` | Full language metadata, variant families, all 210 pairs. |
| `GET /help` | Self-documenting endpoint reference (machine-readable mirror of this doc). |

### Authenticated GET endpoints

| Endpoint | Returns |
|---|---|
| `GET /info` | Pipeline + dictionary stats. |
| `GET /models/status` | Currently warm models. |
| `GET /cache/stats` | Translation cache hit/miss stats. |
| `GET /review/cache/stats` | Review cache stats. |

---

## 5. `POST /translate` — single text

### Minimum request
```json
{
  "text": "Hello, how are you?",
  "source_lang": "en",
  "target_lang": "vi"
}
```

### Full request schema
| Field | Type | Default | Notes |
|---|---|---|---|
| `text` | string (1–2000) | — | Source text. Required. |
| `source_lang` | string | `en` | Any of the 15 codes. |
| `target_lang` | string | `vi` | Any of the 15 codes. |
| `context` | string (≤1000) | — | One-paragraph hint about where this string is used. Strongly recommended whenever the text is short or ambiguous. |
| `teaching_lang` | string | — | Activates language-learning mode. Set this to the language the **learner is studying** (usually `"English"`). |
| `vocab_mode` | `"preserve"` \| `"bilingual"` | `"preserve"` when `teaching_lang` is set | `"preserve"` keeps `teaching_lang` words in their original script. `"bilingual"` produces `word (translation)`. |
| `intent` | `"literal"` \| `"pedagogical"` \| `"transcreation_marketing"` \| `"transcreation_ux"` \| `"legal"` | `"literal"` | Sets the rewrite policy. See § 7. |
| `tone` | `"warm"` \| `"professional"` \| `"urgent"` \| `"casual"` | — | Style hint. Most useful with `transcreation_*` intents. |
| `content_type` | see § 7 | auto-detected | Tightens stylistic conventions (line length, punctuation, register). |
| `domain` | `"education"` \| `"legal"` \| `"tech"` \| `"medical"` \| `"finance"` \| `"marketing"` \| `"general"` | — | Routes domain-specific glossary + filters anchor sources. |
| `loanword_tolerance` | `"low"` \| `"medium"` \| `"high"` | per-language default | `"low"` forces nativization, `"high"` accepts loanwords liberally. |
| `speaker` | object | — | `{gender, role, age_band}`. See § 7. |
| `preserve_list` | string[] | — | Brand names / technical terms that must never translate. |
| `prev_segment` | string (≤500) | — | Previous subtitle line, for cross-segment continuity. |
| `next_segment` | string (≤500) | — | Next subtitle line. |
| `max_chars` | int (1–5000) | — | Hard cap on output length; pipeline retries with a re-prompt if the first draft exceeds it. |
| `workspace_id` | string | — | Tenant scoping for glossaries/anchors. |
| `use_session_anchors` | bool | `true` | Inject recent same-pair translations as style reference. |
| `use_cross_lang_anchors` | bool | `true` | Inject parallel translations of the same source from other targets. |
| `use_glossary` | bool | `true` | Inject domain glossary as STRICT rules in the first stage. |
| `no_cache` | bool | `false` | Skip cache read **and** write. |
| `verbose` | bool | `false` | Include `audit` block with stage timings + intermediate outputs. |

### Response
```json
{
  "translation": "Xin chào, bạn khỏe không?",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "confidence_breakdown": {
    "meaning": "high",
    "style": "high",
    "purity": "high"
  },
  "elapsed_s": 5.74,
  "cached": false,
  "source_lang": "en",
  "target_lang": "vi"
}
```

When `cached: true`, an extra `cache` object appears:
```json
"cached": true,
"cache": {
  "hit_count": 2,
  "first_cached_at": 1777019063.59,
  "last_hit_at":     1778804918.19,
  "original_source": "Welcome back!",
  "normalization":   "tier1",
  "placeholders_restored": 0,
  "context_match":   "exact"
}
```

When `verbose: true`, an `audit` object is added with stage timings, sieve hits, and intermediate candidates (useful for benchmarking and debugging).

### Worked example — pedagogical content with token preservation
```bash
curl -s -X POST https://translate.flowb.ai/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "text": "The {{Past Perfect}} tense describes an action completed before another past action.",
    "source_lang": "en",
    "target_lang": "zhTW",
    "teaching_lang": "English",
    "content_type": "subtitle",
    "domain": "education",
    "intent": "pedagogical",
    "context": "Subtitle from an English grammar lesson video."
  }'
```
```json
{
  "translation": "Past Perfect 時態描述的是在另一個過去動作之前已經完成的動作。",
  "source_model": "Qwen-35B-NT",
  "confidence": "medium",
  "confidence_breakdown": { "meaning": "high", "style": "medium", "purity": "medium" },
  "elapsed_s": 1.85,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zhTW"
}
```
Note that `{{Past Perfect}}` survives end-to-end and the braces are stripped from the delivered output.

### Worked example — UI button transcreation
```bash
curl -s -X POST https://translate.flowb.ai/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "text": "Get Started",
    "source_lang": "en",
    "target_lang": "ja",
    "content_type": "ui_button",
    "intent": "transcreation_ux",
    "max_chars": 12
  }'
```
```json
{
  "translation": "はじめましょう",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "confidence_breakdown": { "meaning": "high", "style": "high", "purity": "high" },
  "elapsed_s": 1.56,
  "cached": false,
  "source_lang": "en",
  "target_lang": "ja"
}
```

### Worked example — speaker-aware Thai dialogue
```bash
curl -s -X POST https://translate.flowb.ai/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "text": "Welcome back!",
    "source_lang": "en",
    "target_lang": "th",
    "content_type": "subtitle",
    "speaker": {"gender": "female", "role": "teacher", "age_band": "adult"}
  }'
```
```json
{
  "translation": "ยินดีต้อนรับกลับค่ะ",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 2.10,
  "cached": false,
  "source_lang": "en",
  "target_lang": "th"
}
```
The `ค่ะ` polite particle is selected because `speaker.gender = "female"`. Without `speaker`, the pipeline picks a gender-neutral or default-male form.

### Worked example — preserving brand/technical terms
```bash
curl -s -X POST https://translate.flowb.ai/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "text": "Deploy your TensorFlow model with kubectl in one command.",
    "source_lang": "en",
    "target_lang": "ko",
    "domain": "tech",
    "preserve_list": ["TensorFlow", "kubectl"]
  }'
```
The two listed tokens stay in Latin script regardless of context. Equivalent to wrapping them as `{{TensorFlow}}` and `{{kubectl}}` inline.

---

## 6. `POST /translate/batch` — many texts, one target

For up to **50 texts** sharing the same `source_lang`, `target_lang`, and any optional context/teaching settings.

### Request
```bash
curl -s -X POST https://translate.flowb.ai/translate/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "texts": [
      "Welcome back!",
      "Sign in to continue",
      "Your account has been updated."
    ],
    "source_lang": "en",
    "target_lang": "hi",
    "content_type": "ui_body",
    "intent": "transcreation_ux"
  }'
```

### Response
```json
{
  "results": [
    {
      "translation": "वापस आने के लिए स्वागत है!",
      "source_model": "Qwen-35B-NT",
      "confidence": "low",
      "confidence_breakdown": { "meaning": "high", "style": "low", "purity": "high" },
      "elapsed_s": 4.64,
      "cached": false,
      "source_lang": "en",
      "target_lang": "hi"
    },
    {
      "translation": "जारी रखने के लिए साइन इन करें",
      "source_model": "Qwen-35B-NT",
      "confidence": "low",
      "confidence_breakdown": { "meaning": "high", "style": "low", "purity": "high" },
      "elapsed_s": 7.14,
      "cached": false,
      "source_lang": "en",
      "target_lang": "hi"
    },
    {
      "translation": "आपका खाता अपडेट हो गया है।",
      "source_model": "Qwen-35B-NT",
      "confidence": "high",
      "confidence_breakdown": { "meaning": "high", "style": "high", "purity": "high" },
      "elapsed_s": 3.04,
      "cached": false,
      "source_lang": "en",
      "target_lang": "hi"
    }
  ]
}
```

`results[i]` corresponds to `texts[i]` in order. A per-item failure surfaces as `{"error": "...", "source_lang": "en", "target_lang": "hi"}` at the matching index — the whole request still returns 200.

All `/translate` options (`context`, `teaching_lang`, `intent`, `content_type`, `domain`, `speaker`, `preserve_list`, `tone`, `loanword_tolerance`, `max_chars`, `no_cache`, `verbose`) apply to **every** text in the batch. They are batch-shared, not per-text.

---

## 7. `POST /translate/multi` — one text, many targets

For **one source text** translated into multiple target languages in parallel under a single inflight slot. Up to **15 unique target codes**.

### Request
```bash
curl -s -X POST https://translate.flowb.ai/translate/multi \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "text": "Welcome back!",
    "source_lang": "en",
    "target_langs": ["vi", "th", "zhTW", "ja", "ko"],
    "content_type": "ui_heading"
  }'
```

### Response
```json
{
  "source_lang": "en",
  "results": {
    "vi":   { "translation": "Chào mừng bạn trở lại!",  "confidence": "high", "elapsed_s": 16.96, "cached": true,  "source_lang": "en", "target_lang": "vi"  },
    "th":   { "translation": "ยินดีต้อนรับกลับค่ะ",         "confidence": "high", "elapsed_s": 11.43, "cached": true,  "source_lang": "en", "target_lang": "th"  },
    "zhTW": { "translation": "歡迎回來！",                  "confidence": "high", "elapsed_s": 17.10, "cached": true,  "source_lang": "en", "target_lang": "zhTW" },
    "ja":   { "translation": "おかえりなさい！",               "confidence": "high", "elapsed_s": 2.29,  "cached": false, "source_lang": "en", "target_lang": "ja"  },
    "ko":   { "translation": "다시 오신 것을 환영합니다!",      "confidence": "high", "elapsed_s": 2.72,  "cached": false, "source_lang": "en", "target_lang": "ko"  }
  },
  "chain_anchor_langs": ["vi", "th"]
}
```

- `results[code]` shape is identical to `/translate`. Cached results carry a `cache` sub-object.
- A per-target failure appears as `{"error": "...", "target_lang": "..."}` in the results map — the whole request still returns 200.
- `chain_anchor_langs` lists the target languages whose translations were used as cross-language anchors for the others. Disable with `"use_cross_lang_anchors": false`.

### Errors (returns 400)
- Unknown language code in `target_langs`.
- Unsupported pair `source_lang-target_lang`.
- Duplicate target codes.
- 0 targets or > 15 targets.

---

## 8. `POST /review` — score one translation

Score an existing (source, translation) pair against the same quality pipeline used to gate `/translate` outputs.

### Request
```bash
curl -s -X POST https://translate.flowb.ai/review \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "source":      "Hello, how are you?",
    "translation": "Hola, ¿cómo estás?",
    "source_lang": "en",
    "target_lang": "esES"
  }'
```

### Response
```json
{
  "verdict": "ok",
  "score": 100,
  "issues": [],
  "summary": {
    "issue_counts_by_category": {},
    "most_severe_category": null,
    "total_issues": 0
  },
  "relevant_categories": ["length", "register", "terminology"],
  "corrected": null,
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "confidence_breakdown": { "meaning": "high", "style": "high", "purity": "high" },
  "elapsed_s": 1.33,
  "cached": false,
  "source_lang": "en",
  "target_lang": "esES"
}
```

| Field | Notes |
|---|---|
| `verdict` | `"ok"` / `"warning"` / `"reject"`. |
| `score` | 0-100 quality score. ≥ 90 ≈ shippable, 70–89 ≈ usable with caveats, < 70 ≈ rework. |
| `issues` | Array of `{category, severity, message, span?}` items. Empty when `verdict = "ok"`. |
| `summary.issue_counts_by_category` | Count by category for quick filtering. |
| `relevant_categories` | Categories the reviewer considered for this `content_type`. |
| `corrected` | Suggested fix when `verdict ≠ "ok"`; `null` otherwise. |

### Optional request fields
| Field | Type | Default | Notes |
|---|---|---|---|
| `context` | string (≤1000) | — | Same as `/translate`. Helps the reviewer judge stylistic fit. |
| `strictness` | `"objective"` \| `"linguist"` \| `"permissive"` | `"objective"` | `"objective"` flags only outright errors. `"linguist"` also flags unnatural phrasing. `"permissive"` flags only severe errors. |
| `content_type` | see § 9 | auto-detected | Tightens which rules apply. |
| `loanword_tolerance` | `"low"` \| `"medium"` \| `"high"` | per-language default | Same semantics as `/translate`. |
| `no_cache` | bool | `false` | Skip review cache. |
| `verbose` | bool | `false` | Add audit detail. |

### Worked example — strict legal review
```bash
curl -s -X POST https://translate.flowb.ai/review \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "source":      "The Customer shall indemnify and hold harmless the Provider.",
    "translation": "El Cliente exime al Proveedor de cualquier responsabilidad.",
    "source_lang": "en",
    "target_lang": "esES",
    "content_type": "legal",
    "strictness":   "linguist"
  }'
```

---

## 9. `POST /review/batch` — score many pairs

Score up to **50 pairs** that share the same `source_lang` and `target_lang`. There is **no `/review/multi`** — to review the same source against translations into many target languages, fan out one `/review/batch` call per target.

### Request
```bash
curl -s -X POST https://translate.flowb.ai/review/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TRANSLATOR_API_KEY" \
  -d '{
    "items": [
      {"source": "Hello",     "translation": "Xin chào"},
      {"source": "Thank you", "translation": "Cảm ơn"}
    ],
    "source_lang": "en",
    "target_lang": "vi"
  }'
```

### Response
```json
{
  "results": [
    {
      "verdict": "ok", "score": 100, "issues": [],
      "summary": {"issue_counts_by_category": {}, "most_severe_category": null, "total_issues": 0},
      "relevant_categories": ["length", "register", "terminology"],
      "corrected": null,
      "source_model": "Qwen-35B-NT", "confidence": "high",
      "elapsed_s": 0.33, "cached": false,
      "source_lang": "en", "target_lang": "vi"
    },
    {
      "verdict": "ok", "score": 100, "issues": [],
      "summary": {"issue_counts_by_category": {}, "most_severe_category": null, "total_issues": 0},
      "relevant_categories": ["length", "register", "terminology"],
      "corrected": null,
      "source_model": "Qwen-35B-NT", "confidence": "high",
      "elapsed_s": 0.33, "cached": false,
      "source_lang": "en", "target_lang": "vi"
    }
  ]
}
```

`results[i]` corresponds to `items[i]`. Per-item failures surface as `{"error": "...", "source_lang": "...", "target_lang": "..."}` at the matching index.

---

## 10. Parameter guide — when to use what

This section is the *opinionated* guide to the optional fields. The Pydantic schemas in §§ 5/8 are the authoritative reference; this section is the **pick-the-right-knob** companion.

### `context`
A one-paragraph free-text hint about where the string is used and who reads it. **Always pass this for short strings** — without it, "Submit" can mean a button label, a verb, or an adjective, and the model will guess.

Good `context` examples:
- `"Confirmation toast shown after the user saves a draft."`
- `"Heading at the top of an exam-result screen for high-school students."`
- `"Push notification body for a flash-sale promotion in the mobile app."`

### `teaching_lang` + `vocab_mode` (language-learning mode)
Pass `teaching_lang` only when translating learning content **for a learner studying that language**. The most common setup is "translate Vietnamese subtitles for an English-language lesson":

```json
{
  "text": "The {{Past Perfect}} tense describes an action that was completed before another past action.",
  "source_lang": "en", "target_lang": "vi",
  "teaching_lang": "English",
  "content_type": "subtitle",
  "domain": "education",
  "intent": "pedagogical"
}
```

| `vocab_mode` | Output style | Use when |
|---|---|---|
| `"preserve"` (default when `teaching_lang` is set) | `Past Perfect` stays in Latin script in the target. | The learner is meant to recognise the English term verbatim. |
| `"bilingual"` | `Past Perfect (Quá khứ Hoàn thành)` | The learner is new and needs the gloss. |

If you want a specific token preserved without enabling full pedagogical mode, wrap it in `{{double braces}}` instead — it's the simpler tool.

### `intent`
Controls how aggressively the pipeline rewrites for fluency vs. fidelity.

| `intent` | Behaviour | Typical content |
|---|---|---|
| `"literal"` (default) | Faithful, no creative liberties. | API responses, technical text, raw user content. |
| `"pedagogical"` | Faithful + ELT-aware glossing rules. | Lesson subtitles, grammar explanations. |
| `"transcreation_ux"` | Rewrite for natural in-product UX. | UI buttons, headings, microcopy, error messages. |
| `"transcreation_marketing"` | Rewrite for emotional impact. | Ad copy, CTAs, hero headings, taglines. |
| `"legal"` | Maximum fidelity, terminology-locked. | Contracts, ToS, legal notices. Pair with `content_type: "legal"`. |

### `tone`
Style overlay. Most useful with `transcreation_*`.

| `tone` | Effect |
|---|---|
| `"warm"` | Friendly, second-person, conversational. |
| `"professional"` | Polished, neutral register. |
| `"urgent"` | Imperative, short, action-forward. |
| `"casual"` | Slangy, contractions, low formality. |

### `content_type`
Tells the pipeline what kind of artefact this is — affects line length, punctuation style, casing, and which review categories matter. **Auto-detected from the text** if omitted, but auto-detect is heuristic — always set it for `subtitle`, `ui_*`, `legal`, and `cta` if you know it.

| `content_type` | Stylistic conventions enforced |
|---|---|
| `"general"` | No special rules. |
| `"subtitle"` | One screen-line per segment, no terminal full stop unless source has one, speaker-aware. Use with `prev_segment` / `next_segment` for cross-line continuity. |
| `"ui_button"` | Verb-first, ≤ ~3 words / `max_chars` honoured strictly, no terminal punctuation. |
| `"ui_heading"` | Title case (where the language has one), no terminal punctuation. |
| `"ui_body"` | Sentence case, terminal punctuation allowed. |
| `"notification"` | Push-notification style: short, verb-first, sentence-case. |
| `"cta"` | Call-to-action, action verb, no period. Pair with `intent: "transcreation_marketing"`. |
| `"legal"` | Maximum fidelity, term-locked. Pair with `intent: "legal"`. |
| `"error_message"` | User-facing error: blame-free, no jargon. |
| `"tooltip"` | Sentence case, ≤ ~12 words, no period. |

### `domain`
Routes domain-specific glossaries and filters which session/cross-lang anchors get injected. Pass when you have a clear domain — `"education"`, `"legal"`, `"tech"`, `"medical"`, `"finance"`, `"marketing"`, or `"general"`.

### `speaker`
Only relevant for languages with grammatical gender, polite particles, or honorifics — primarily **Thai, Japanese, Korean**, and to a lesser extent **Spanish/Hindi/Urdu**. Object shape:

```json
"speaker": {
  "gender":   "male" | "female" | "nonspecified",
  "role":     "teacher" | "student" | "narrator" | "customer_service" | "host",
  "age_band": "child" | "teen" | "adult" | "elder"
}
```

All three sub-fields are optional; pass what you know.

### `preserve_list` and the `{{double-braces}}` pattern
Two ways to keep tokens out of translation:

1. **Inline `{{...}}` in the source text** — the easiest. Anything inside braces is preserved end-to-end and the braces are stripped at delivery. Use for one-off terms inside a longer string.
2. **`preserve_list: ["FlowTasks", "kubectl"]`** — for tokens that recur unmarked across many strings. Equivalent to wrapping each occurrence in `{{...}}` automatically.

If you use both, they compose: inline `{{...}}` and `preserve_list` are merged.

### `prev_segment` / `next_segment`
Cross-segment context for `content_type: "subtitle"`. Pass the previous and next subtitle lines so the pipeline can resolve pronouns, continue a clause, or maintain register across cuts.

```json
{
  "text":          "But she didn't.",
  "prev_segment": "I thought Anna would call.",
  "next_segment": "I waited all evening.",
  "source_lang":  "en", "target_lang": "ja",
  "content_type": "subtitle"
}
```

### `max_chars`
Hard cap on output length. The pipeline retries with a re-prompt if the first draft exceeds it. Critical for `ui_button` and `notification` content.

### `loanword_tolerance`
Controls how aggressively the pipeline nativises foreign words.

| Level | Behaviour |
|---|---|
| `"low"` | Aggressively nativise — even common loans get translated. |
| `"medium"` (per-language default) | Accept established loanwords, translate the rest. |
| `"high"` | Accept most loanwords as-is. Best for tech/UI content where users recognise English terms. |

### `use_session_anchors` / `use_cross_lang_anchors` / `use_glossary`
All default `true`. Disable individually for benchmarking or when you want a clean-room translation that ignores prior context.

### `no_cache` and `verbose`
- `no_cache: true` — skips both cache read and write. Use for benchmarks or when you've changed something the cache key doesn't include.
- `verbose: true` — adds an `audit` block with stage timings and intermediate candidates. Use during development; turn off in production.

---

## 11. Response shape (full)

```json
{
  "translation": "...",                  // Final delivered output
  "source_model": "Qwen-35B-NT",
  "confidence": "high",                  // worst of the three breakdown axes
  "confidence_breakdown": {
    "meaning": "high",                   // semantic fidelity
    "style":   "high",                   // register / fluency / convention fit
    "purity":  "high"                    // freedom from leakage / artefacts
  },
  "elapsed_s": 1.42,
  "cached": false,
  "source_lang": "en",
  "target_lang": "vi",

  // Present only when cached: true
  "cache": {
    "hit_count": 2,
    "first_cached_at": 1777019063.59,
    "last_hit_at":     1778804918.19,
    "original_source": "Welcome back!",
    "normalization":   "tier1",
    "placeholders_restored": 0,
    "context_match":   "exact"
  },

  // Present only when verbose: true
  "audit": {
    "stage_timings": { "...": "..." },
    "had_revision":  false,
    "warnings":      []
  }
}
```

| Field | Read for |
|---|---|
| `translation` | The string to ship. |
| `confidence` / `confidence_breakdown` | Decide whether to auto-publish, queue for human review, or reject. |
| `elapsed_s` | SLO tracking. |
| `cached` + `cache.context_match` | Whether the output was from the cache, and whether the cache hit was on identical or normalised inputs. |
| `audit.warnings` | Non-empty only when something degraded (e.g. the model fell back to the source string). Treat any non-empty `warnings` array as a yellow flag. |

---

## 12. Caching semantics

- **Default** — read cache first, write on miss.
- **Cache key** = `hash(source_lang, target_lang, source_text, context, teaching_lang, vocab_mode)`. Different `context` strings produce different cache entries — set `context` deliberately, not opportunistically.
- **`no_cache: true`** — skips read AND write. Use for fresh runs.
- **TTL** — none by default; entries persist until manually evicted.
- **Stats** — `GET /cache/stats` (translation cache) and `GET /review/cache/stats` (review cache).

---

## 13. Errors

| Status | Meaning |
|---|---|
| `400` | Validation failure: unknown language code, unsupported pair, duplicate `target_langs`, oversize `text`, > 50 batch items, > 15 multi targets. |
| `401` | Missing or invalid `X-API-Key`. |
| `429` | Per-key rate limit hit. Back off and retry. |
| `503` | Per-endpoint concurrency cap hit (transient). Retry with jittered backoff. |
| `5xx` (other) | Internal error. Safe to retry with the same body — caching makes retries cheap. |

Error body shape:
```json
{ "detail": "human-readable explanation" }
```

---

## 14. Best-practice recipes

### Translating UI strings into 5 languages
One `/translate/multi` call per source string. Set `content_type` and `intent` once; the pipeline applies them to every target.

```json
{
  "text": "Save changes",
  "source_lang": "en",
  "target_langs": ["vi", "th", "zhTW", "ja", "ko", "esLA", "ptBR", "hi"],
  "content_type": "ui_button",
  "intent": "transcreation_ux",
  "max_chars": 14
}
```

### Translating a subtitle file
Loop over segments. For each, pass `prev_segment` and `next_segment` from the neighbouring lines and a `speaker` block when known. Use one `/translate` per line (better cache behaviour than `/translate/batch` because each segment has its own neighbours).

### Marketing copy for multiple regions
One `/translate/multi` per asset, with `intent: "transcreation_marketing"` and an explicit `tone`. Pass region-specific variants (`esES` vs `esAR`, `pt` vs `ptBR`) to get the right vocabulary and register.

### Reviewing a vendor's translation memory
`/review/batch` in chunks of 50. Use `strictness: "linguist"` for high-stakes content, `"objective"` for general acceptance testing. Sort `results` by `score` ascending to triage the worst.

### Quality-gating an in-house pipeline
After your generator produces a translation, run `/review` on it. Auto-publish if `verdict = "ok"` and `score ≥ 90`; otherwise route to human review with the `corrected` suggestion as a starting point.

---

## 15. Quick reference

```
POST /translate         body { text, source_lang, target_lang, ...options }
POST /translate/batch   body { texts[], source_lang, target_lang, ...options }
POST /translate/multi   body { text, source_lang, target_langs[], ...options }
POST /review            body { source, translation, source_lang, target_lang, ...options }
POST /review/batch      body { items[{source, translation}], source_lang, target_lang, ...options }

GET  /                  service identity + pair list (public)
GET  /health            liveness (public)
GET  /languages         language metadata (public)
GET  /help              this reference, machine-readable (public)

GET  /info              pipeline + dictionary stats (auth)
GET  /models/status     warm models (auth)
GET  /cache/stats       translation cache stats (auth)
GET  /review/cache/stats review cache stats (auth)

Auth: X-API-Key header on every POST and on /info, /models/status, /cache/stats, /review/cache/stats.
Base: https://translate.flowb.ai
```
