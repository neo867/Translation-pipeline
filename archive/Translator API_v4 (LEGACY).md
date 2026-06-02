# Translation API — Documentation

HTTP API for translating and reviewing text across language pairs. Supports `en-zhTW`, `en-zhCN`, `en-ko`, `en-vi`, `en-id`, `en-th`, `en-ja`.

**Endpoints**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/translate` | Translate one text |
| `POST` | `/translate/batch` | Translate up to 50 texts |
| `POST` | `/review` | Review a (source, candidate translation) pair |
| `POST` | `/review/batch` | Review up to 50 pairs |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/cards` | Per-card load + health (auth) |
| `GET`  | `/cache/stats` | Translate cache statistics (auth) |
| `GET`  | `/review/cache/stats` | Review cache statistics (auth) |

**Capabilities at a glance**

- Seven language pairs, all using the same model — no model swap needed between pairs.
- Optional `context` parameter on every translate/review call — domain guidance respected throughout the pipeline.
- Language-learning mode: `teaching_lang` and `vocab_mode` parameters for vocabulary preservation in educational content.
- Double-brace preservation: anything inside `{{...}}` is kept verbatim and ignored by sieves.
- Source-aware quality checks: placeholder mismatch, untranslated output, and length ramble are flagged catastrophically and self-revised before returning.
- `/review` includes a safety net that rewrites the corrected text if it's broken (placeholder leak, untranslated, length ramble); harmless cases are passed through verbatim.
- Bounded in-flight concurrency with HTTP 503 + `Retry-After` for back-pressure.

## Base URL

```
http://203.171.30.194:3102
```

Nginx passthrough, plain HTTP (no TLS). Default binding is `0.0.0.0:13102` on the host. Override with `TRANSLATOR_HOST` / `TRANSLATOR_PORT` env vars.

## Authentication

Header `X-API-Key: <key>`. Keys loaded (in priority order) from:
1. Environment variable `API_KEYS` (comma-separated)
2. File `/home/csaptu/translator/api_keys.txt` (one per line, `#` for comments)

Current dev key: `tw-localizer-dev-a1b2c3d4e5f6`

Missing or invalid key returns `401` — checked BEFORE rate limiting, so anonymous abuse doesn't consume quota.

## Rate limits

Sliding-window, in-process. Three tiers, all must pass:

| Bucket | Default | Env override |
|--------|---------|--------------|
| Global (whole server) | `120/minute` | `RATE_LIMIT_GLOBAL` |
| Per-API-key | `600/minute` | `RATE_LIMIT_KEY` |
| Per-IP (fallback if no valid key) | `30/minute` | `RATE_LIMIT_IP` |

Format: `<count>/<second|minute|hour|day>`.

On exceed: `HTTP 429` with body `{"detail": "rate limit exceeded (key: 600/60s)"}`.

## Language pairs

All seven pairs are deployed and use the same model (`qwen3.5:35b-a3b-q3km`, labeled `Qwen-35B-NT`). Switching between pairs is instant — no model swap required.

| Pair key | `target_lang` | Source | Target | Sieve | Tokenizer |
|----------|---------------|--------|--------|-------|-----------|
| `en-zhTW` | `zhTW` or `zh-TW` | English | Taiwanese Mandarin | `cn_tw` | jieba |
| `en-zhCN` | `zhCN` or `zh-CN` | English | Simplified Chinese | `tw_cn` | jieba |
| `en-ko` | `ko` | English | Korean | `formality_konglish` | kiwi |
| `en-vi` | `vi` | English | Vietnamese | `tone_diacritics` | none |
| `en-id` | `id` | English | Indonesian | `formality_malay` | none |
| `en-th` | `th` | English | Thai | `register_script` | none |
| `en-ja` | `ja` | English | Japanese | `formality_keigo` | none |

Each request specifies `source_lang` and `target_lang` parameters. If omitted, both default to `en` and `zh-TW` respectively.

**Language code normalization**: Both hyphenated (`zh-TW`, `zh-CN`) and compact (`zhTW`, `zhCN`) formats are accepted and automatically normalized. The response always returns the compact form.

An unsupported pair returns `HTTP 400` with the list of available pairs.

## Cache

Persistent SQLite cache with Tier 1 + Tier 2 normalization applied before key lookup. Cache keys incorporate `source_lang` and `target_lang`, so the same English text cached for zh-TW does NOT collide with the same text cached for ko.

- **Tier 1**: collapse whitespace, strip trailing sentence punctuation (`. ! ?`), smart-lowercase (only sentence-shaped inputs; preserves case of short UI labels like `Save` vs `SAVE`)
- **Tier 2**: replace placeholder patterns (`{name}`, `%s`, `%d`, `%(key)s`, `${name}`, `$name`) with internal markers, cache the TEMPLATE, re-substitute placeholder values on hit

Cache survives server restart. Stored at `/home/csaptu/translator/translations.sqlite`.

**Context-aware caching**: All translations are cached, including those with context, teaching_lang, or vocab_mode. The cache key includes the full parameter bundle.

On cache miss with a context, the server runs a 3-tier matching pipeline:
1. **Exact match** — hash lookup on the full key (text + pair + context + tl + vm). Sub-ms.
2. **Known mappings** — check the  table for a previously verified equivalent context. Sub-ms.
3. **LLM similarity** — fetch all cached contexts for the same text (any context), pre-filter by word-cosine similarity (top 3), then compare each with both Qwen and Sonnet. Both must score ≥95% to match. Mappings are stored bidirectionally so future lookups skip the LLM calls.

 and  require exact match — only the free-text  uses LLM similarity. The response includes  (, , or ), and for similarity matches: , ,  (word-cosine), and  (which cached context was matched).

## Double-brace preservation

Anything inside double curly braces — e.g. `{{exorbitant}}`, `{{user_name}}`, `{{do_not_translate}}` — is preserved verbatim across all pipeline stages. This is always-on and works in addition to context. Do not nest braces.

**Important distinction**: `{{content}}` (double braces) = preserved verbatim, never translated. Single-brace tokens like `{name}`, `{0}`, `%s` are cache Tier 2 placeholder templating only — they are NOT "don't translate" markers.

**Unclosed brace warning**: When input has unmatched `{{` without `}}`, the response includes a warning:

```json
{"code": "unclosed_double_brace", "message": "Input has 1 '{{' but 0 '}}'. Use matching double braces {{like this}} to protect content from translation."}
```

## Language-learning mode

For educational content (ESL, vocabulary lessons, language teaching), the API provides dedicated parameters that control how vocabulary words are handled in translation.

### Parameters

Available on `/translate` and `/translate/batch`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `teaching_lang` | string | Language being taught (e.g., `"English"`, `"Mandarin"`). Activates language-learning mode. |
| `vocab_mode` | string | `"preserve"` \| `"bilingual"` \| `null`. How to handle vocabulary words. |

**`vocab_mode` values**:
- `"preserve"` — keep vocabulary words in the teaching language, untranslated.
- `"bilingual"` — output vocabulary as `word (translation)`, e.g., `ecology (sinh thái)`.
- `null` (or omitted) — auto-detect; defaults to `"bilingual"` when learning mode is detected.

**Auto-detection**: language-learning mode can also be detected automatically from context keywords such as `dạy tiếng`, `vocabulary`, `ESL`, `language lesson`, etc. When auto-detected, behavior defaults to bilingual vocab mode.

**Cache behavior**: `teaching_lang` and `vocab_mode` are included in the cache key (exact match required). Only the free-text `context` uses LLM similarity matching.

### Example

```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Today we will learn the word ecology.",
    "source_lang": "en",
    "target_lang": "vi",
    "teaching_lang": "English",
    "vocab_mode": "bilingual"
  }'
```

Response:
```json
{
  "translation": "Hôm nay chúng ta sẽ học từ ecology (sinh thái).",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.52,
  "cached": false,
  "source_lang": "en",
  "target_lang": "vi"
}
```

With `"vocab_mode": "preserve"`:
```json
{
  "translation": "Hôm nay chúng ta sẽ học từ ecology.",
  ...
}
```

## Endpoints

### `GET /`
Metadata. No auth.

```json
{
  "name": "Translation API",
  "version": "4.0",
  "available_pairs": ["en-zhTW", "en-zhCN", "en-ko", "en-vi", "en-id", "en-th", "en-ja"],
  "endpoints": {
    "POST /translate": "single text — body: {text, source_lang?, target_lang?, context?, teaching_lang?, vocab_mode?, verbose?}",
    "POST /translate/batch": "batch — body: {texts[], source_lang?, target_lang?, context?, teaching_lang?, vocab_mode?, verbose?}",
    "POST /review": "check a translation — body: {source, translation, source_lang?, target_lang?, context?, verbose?}",
    "POST /review/batch": "batch review — body: {items:[{source,translation}], source_lang?, target_lang?, context?, verbose?}",
    "GET /health": "liveness",
    "GET /info": "pipeline + dict stats",
    "GET /models/status": "currently loaded models",
    "GET /cache/stats": "translation cache stats",
    "GET /review/cache/stats": "review cache stats"
  },
  "auth": "Header: X-API-Key"
}
```

### `GET /health`
Liveness. No auth. Returns `{"status": "ok"}`.

### `GET /models/status`
Currently loaded models. Auth required.

```json
{
  "current_pair": "en-zhTW",
  "loaded_models": {
    "m1": "qwen3.5:35b-a3b-q3km",
    "m2": "qwen3.5:35b-a3b-q3km"
  },
  "available_pairs": ["en-zhTW", "en-zhCN", "en-ko", "en-vi", "en-id", "en-th", "en-ja"]
}
```

All pairs use the same model for both m1 and m2. When no models are loaded yet (cold start), `current_pair` is `null` and `loaded_models` is empty. Sending a translation request triggers the load automatically.

### `GET /info`
Pipeline + model config for all pairs. Auth required.

```json
{
  "available_pairs": ["en-zhTW", "en-zhCN", "en-ko", "en-vi", "en-id", "en-th", "en-ja"],
  "pairs": {
    "en-zhTW": {
      "model": "Qwen-35B-NT",
      "tokenizer": "jieba",
      "sieve": "cn_tw"
    },
    "en-zhCN": {
      "model": "Qwen-35B-NT",
      "tokenizer": "jieba",
      "sieve": "tw_cn"
    },
    "en-ko": {
      "model": "Qwen-35B-NT",
      "tokenizer": "kiwi",
      "sieve": "formality_konglish"
    },
    "en-vi": {
      "model": "Qwen-35B-NT",
      "tokenizer": "none",
      "sieve": "tone_diacritics"
    },
    "en-id": {
      "model": "Qwen-35B-NT",
      "tokenizer": "none",
      "sieve": "formality_malay"
    },
    "en-th": {
      "model": "Qwen-35B-NT",
      "tokenizer": "none",
      "sieve": "register_script"
    },
    "en-ja": {
      "model": "Qwen-35B-NT",
      "tokenizer": "none",
      "sieve": "formality_keigo"
    }
  }
}
```

### `GET /cache/stats`
Auth required. Optional query parameters `source_lang` and `target_lang` to filter stats to a single pair. If both are omitted, returns aggregate stats plus a `by_language_pair` breakdown.

**Unfiltered response**
```json
{
  "total_unique": 150,
  "total_requests": 430,
  "cache_hits_saved": 280,
  "entries_reused": 85,
  "by_confidence": {"high": 145, "low": 5},
  "by_source_model": {"Qwen-35B-NT": 148, "Qwen-35B-NT+FALLBACK_ORIGINAL": 2},
  "by_language_pair": [
    {"source_lang": "en", "target_lang": "zhTW", "count": 110},
    {"source_lang": "en", "target_lang": "ko", "count": 40}
  ]
}
```

**Filtered response** (`?source_lang=en&target_lang=ko`)
```json
{
  "total_unique": 40,
  "total_requests": 95,
  "cache_hits_saved": 55,
  "entries_reused": 20,
  "by_confidence": {"high": 38, "low": 2},
  "by_source_model": {"Qwen-35B-NT": 40}
}
```

### `POST /translate`
Single translation. Auth + rate limit required.

**Request**
```json
{
  "text": "The student takes the metro to elementary school.",
  "source_lang": "en",
  "target_lang": "zh-TW",
  "context": null,
  "teaching_lang": null,
  "vocab_mode": null,
  "verbose": false
}
```
- `text` — 1 to 2000 chars (required)
- `source_lang` — source language code (default `"en"`)
- `target_lang` — target language code (default `"zh-TW"`)
- `context` — optional, max 1000 chars. Free-text guidance appended to the system prompt and respected by every model call in the pipeline (initial translate, self-revise). Context is included in the cache key; similar contexts are matched via LLM comparison.
- `teaching_lang` — optional. Language being taught (e.g., `"English"`). Activates language-learning mode. **Cache is bypassed when set.**
- `vocab_mode` — optional. `"preserve"` | `"bilingual"` | `null`. Controls vocabulary handling in learning mode. **Cache is bypassed when set.**
- `no_cache` — force bypass cache and run full pipeline (default `false`)
- `verbose` — include audit object (default `false`)

**Response — fresh translation (cache miss)**
```json
{
  "translation": "學生搭捷運去國小。",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.34,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zh-TW"
}
```

**Response — cache hit**
```json
{
  "translation": "學生搭捷運去國小。",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.34,
  "cached": true,
  "source_lang": "en",
  "target_lang": "zh-TW",
  "cache": {
    "hit_count": 3,
    "first_cached_at": 1776223019.47,
    "last_hit_at": 1776224110.02,
    "original_source": "The student takes the metro to elementary school.",
    "normalization": "tier1",
    "placeholders_restored": 0
  }
}
```

**Response — cache hit with placeholder restoration (Tier 2)**
```json
{
  "translation": "歡迎，{user}！",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.27,
  "cached": true,
  "source_lang": "en",
  "target_lang": "zh-TW",
  "cache": {
    "hit_count": 2,
    "first_cached_at": 1776223020.11,
    "last_hit_at": 1776224111.05,
    "original_source": "Welcome, {name}!",
    "normalization": "tier1+tier2_placeholders",
    "placeholders_restored": 1
  }
}
```

**Response fields**
| Field | Type | Meaning |
|-------|------|---------|
| `translation` | string | Target language output, with caller's placeholders substituted back in if Tier 2 applied |
| `source_model` | enum | Model label that produced the final text (always `Qwen-35B-NT`, or `Qwen-35B-NT+FALLBACK_ORIGINAL` after placeholder-leak fallback) |
| `confidence` | enum | `high` (clean) \| `low` (residual issues, fallback applied, or pipeline error) |
| `elapsed_s` | float | Pipeline time of the ORIGINAL run (not the current cache fetch). For cache hits, fetching itself is sub-ms |
| `cached` | bool | True if served from SQLite cache, False if pipeline ran |
| `source_lang` | string | Echo of source language code |
| `target_lang` | string | Echo of target language code |
| `cache` | object | **Only if `cached=true`.** See breakdown below |
| `audit` | object | **Only if `verbose=true`.** Sanitized audit object |
| `warnings` | array | **Only if issues arose.** Recovery actions taken (e.g. cache leak invalidated, unclosed double brace) |

**`cache` object fields (cache-hit responses only)**
| Field | Meaning |
|-------|---------|
| `hit_count` | Total requests that matched this entry (including this one) |
| `first_cached_at` | Unix timestamp of first cache write |
| `last_hit_at` | Unix timestamp of this request |
| `original_source` | The EXACT source text of the first call that produced this cached translation |
| `normalization` | `none` \| `tier1` \| `tier1+tier2_placeholders` — which normalizations collapsed the request into this entry |
| `placeholders_restored` | Count of placeholders the current request had that were re-substituted from the cached template |

**`audit` object (verbose=true only)**

The audit object exposes a sanitized summary — pipeline internals are not exposed:

```json
{
  "model": "Qwen-35B-NT",
  "sieve_hits": [...],
  "sieve_catastrophic": [...],
  "llm_sieve_issues": [...],
  "had_revision": true,
  "elapsed_model": 5.22
}
```

### `POST /translate/batch`
Batch (max 50). Auth + rate limit required. The `source_lang`, `target_lang`, `context`, `teaching_lang`, and `vocab_mode` apply to all items in the batch.

**Request**
```json
{
  "texts": ["Hello.", "Save your progress.", "Settings"],
  "source_lang": "en",
  "target_lang": "ko",
  "context": null,
  "teaching_lang": null,
  "vocab_mode": null,
  "verbose": false
}
```

**Response**
```json
{
  "results": [
    { "translation": "안녕하세요.", "source_model": "Qwen-35B-NT", "confidence": "high", "elapsed_s": 0.5, "cached": false, "source_lang": "en", "target_lang": "ko" },
    { "translation": "진행 상황을 저장하세요.", "source_model": "Qwen-35B-NT", "confidence": "high", "elapsed_s": 0.4, "cached": false, "source_lang": "en", "target_lang": "ko" },
    { "translation": "설정", "source_model": "Qwen-35B-NT", "confidence": "high", "elapsed_s": 0.3, "cached": false, "source_lang": "en", "target_lang": "ko" }
  ]
}
```

On per-item failure: `{"error": "...", "text": "<input>"}` at the corresponding index.

### `POST /review`
Quality-check a user-supplied translation. Auth + rate limit required.

**Request**
```json
{
  "source": "The elementary school students take the metro.",
  "translation": "小學生搭地鐵。",
  "source_lang": "en",
  "target_lang": "zh-TW",
  "context": null,
  "verbose": false
}
```
- `source` — source text, 1 to 2000 chars
- `translation` — candidate translation, 1 to 4000 chars
- `source_lang` — source language code (default `"en"`)
- `target_lang` — target language code (default `"zh-TW"`)
- `context` — optional, max 1000 chars. Same semantics as `/translate`'s `context` — appended to the reviewer's system prompt. Use this to tell the reviewer about domain conventions or what *not* to flag (e.g., quoted English vocabulary in language-learning content). Context is included in the cache key; similar contexts are matched via LLM comparison.
- `no_cache` — force bypass cache and run full pipeline (default `false`)
- `verbose` — include audit object (default `false`)

**Response — clean (verdict: ok)**
```json
{
  "verdict": "ok",
  "score": 100,
  "issues": [],
  "corrected": null,
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 5.21,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zh-TW"
}
```

**Response — needs revision**
```json
{
  "verdict": "needs_revision",
  "score": 30,
  "issues": [
    {"type": "vocab", "span": "小學", "suggest": "國小", "reason": "Mainland vocabulary; Taiwan uses the suggested term.", "severity": "high"},
    {"type": "vocab", "span": "地鐵", "suggest": "捷運", "reason": "Mainland vocabulary; Taiwan uses the suggested term.", "severity": "high"}
  ],
  "corrected": "國小學生搭捷運。",
  "source_model": "Qwen-35B-NT",
  "confidence": "medium",
  "elapsed_s": 1.56,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zh-TW"
}
```

**Response fields**
| Field | Type | Meaning |
|-------|------|---------|
| `verdict` | enum | `ok` (clean, correct for target locale) \| `minor_issues` (small style/register only) \| `needs_revision` (vocab, mistranslation, or placeholder issue) |
| `score` | int 0-100 | 100 for clean, 70-89 minor, <70 needs_revision. Penalty-weighted by severity |
| `issues` | array | Structured issue list (may be empty) |
| `issues[].type` | enum | `vocab` \| `grammar` \| `register` \| `mistranslation` \| `placeholder_missing` \| `placeholder_extra` \| `style` |
| `issues[].span` | string | Offending substring in the user's translation |
| `issues[].suggest` | string | Suggested replacement |
| `issues[].reason` | string | Brief human-readable reason |
| `issues[].severity` | enum | `low` \| `medium` \| `high` |
| `corrected` | string\|null | Full revised translation, or `null` if verdict is `ok` |
| `source_model` | enum | `Qwen-35B-NT` (the reviewer) \| `sieve-only` (reviewer call failed; fell back to deterministic sieve) |
| `confidence` | enum | `high` (reviewer + sieve agree on clean) \| `medium` (reviewer flagged with concrete issues) \| `low` (reviewer flagged but no concrete fix, or call failed) |

The review pipeline runs a deterministic sieve scan on the user's translation (source-aware: also checks placeholder mismatch, untranslated output, length ramble), then a single Qwen reviewer call. The reviewer's verdict is merged with deterministic findings. Placeholder tokens (`{name}`, `%s`, etc.) are checked structurally — missing, extra, or mutated placeholders are flagged.

**Safety net**: After the reviewer produces a `corrected` text, it is checked for catastrophic problems (placeholder leak, output identical to source, length ramble or truncation). If any fires, the corrected text is rewritten — instructed to return the original verbatim when nothing's actually wrong. The rewrite replaces `corrected` only when it differs from the input. When applied, a `corrected_rescued` warning is added.

**Review cache**: keyed on `(source_lang, target_lang, template_source, target_stripped)`. Source gets Tier 1 normalization; target text is byte-exact because any target difference is semantically meaningful. Expected hit rate is 5-15%. Bypassed when `context` is set.

### `POST /review/batch`
Batch review (max 50). Auth + rate limit required. The `source_lang`, `target_lang`, and `context` apply to all items.

**Request**
```json
{
  "items": [
    {"source": "Save your progress.", "translation": "保存您的進度。"},
    {"source": "Settings", "translation": "設定"}
  ],
  "source_lang": "en",
  "target_lang": "zh-TW",
  "context": null,
  "verbose": false
}
```

**Response**
```json
{
  "results": [
    {"verdict": "needs_revision", "score": 45, "issues": [...], "corrected": "儲存您的進度。", "source_model": "Qwen-35B-NT", "confidence": "medium", "elapsed_s": 1.1, "cached": false, "source_lang": "en", "target_lang": "zh-TW"},
    {"verdict": "ok", "score": 100, "issues": [], "corrected": null, "source_model": "Qwen-35B-NT", "confidence": "high", "elapsed_s": 0.9, "cached": false, "source_lang": "en", "target_lang": "zh-TW"}
  ]
}
```

### `GET /review/cache/stats`
Auth required. Optional query parameters `source_lang` and `target_lang` to filter.

```json
{
  "total_unique": 3,
  "total_requests": 5,
  "cache_hits_saved": 2,
  "entries_reused": 1,
  "by_verdict": {"ok": 1, "needs_revision": 2},
  "by_confidence": {"high": 1, "medium": 2},
  "by_source_model": {"Qwen-35B-NT": 3}
}
```

## Confidence tiers

The enum is intentionally simple — `high` / `low` for `/translate`; `/review` adds a `medium` tier when the reviewer flagged concrete issues but the deterministic sieve was clean.

| Tier | Where | Meaning | Reliability |
|------|-------|---------|-------------|
| `high` | `/translate` | Single Qwen call produced clean output (no residual sieve issues, no LLM-sieve issues) | ~95-99% |
| `high` | `/review` | Reviewer + sieve agree the translation is clean, OR reviewer flagged with concrete issues + sieve clean | ~95-99% |
| `medium` | `/review` only | Reviewer flagged + sieve found something | ~90% |
| `low` | both | Residual issues remain after self-revise, OR reviewer call failed (sieve-only fallback), OR placeholder-leak fallback triggered. Always log + audit. | ~85% |

## Placeholder safety

The API guarantees the user will never see internal `{{PHn}}` markers. A three-layer guard sits between the cache/pipeline and the response:

1. **Cache restoration layer** — if placeholder count in the cached template doesn't match the current request, the cache hit is rejected and the pipeline runs fresh.
2. **Pipeline exit layer** — if the final translation contains any `{{PHn}}` marker, the response is replaced with the original source text, confidence is downgraded to `low`, and `source_model` gains a `+FALLBACK_ORIGINAL` suffix. A retry without cache is attempted first.
3. **API exit layer** — response scanned one more time; if a marker slips through, returns HTTP 500 `{"detail": "internal placeholder leak; please retry"}` rather than serving the leak.

For review responses, if the `corrected` field contains a leak, it is set to `null` and a warning is appended.

## Error codes

| Code | Cause |
|------|-------|
| `200` | Success |
| `400` | Unsupported language pair |
| `401` | Missing or invalid `X-API-Key` (returned BEFORE rate-limit check) |
| `422` | Request body validation failed (e.g., text too long, missing required fields) |
| `429` | Rate limit exceeded (global, per-key, or per-IP). Distinct from 503 — see [Concurrency](#concurrency-queueing-and-503-handling). |
| `500` | Pipeline failure OR placeholder-leak guard tripped — see `api.log` |
| `503` | In-flight concurrency cap reached. Honor the `Retry-After` header and retry with backoff. |

## Quick test

```bash
# Health
curl http://203.171.30.194:3102/health

# Translate
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, how are you?", "source_lang": "en", "target_lang": "vi"}'
```

## Examples (curl)

### English to Taiwan Mandarin (default pair)

Fresh translation:
```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Tap Settings to change your password."}'
```

Response (first call):
```json
{
  "translation": "輕觸「設定」以變更您的密碼。",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.27,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zh-TW"
}
```

Second identical call (cached):
```json
{
  "translation": "輕觸「設定」以變更您的密碼。",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.27,
  "cached": true,
  "source_lang": "en",
  "target_lang": "zh-TW",
  "cache": {
    "hit_count": 2,
    "first_cached_at": 1776224000.12,
    "last_hit_at": 1776224530.45,
    "original_source": "Tap Settings to change your password.",
    "normalization": "none",
    "placeholders_restored": 0
  }
}
```

### Translation with `context` (vocabulary teaching)

Without context — Qwen translates the vocab word, defeating the lesson:
```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Today we will learn the word '\''apple'\''.", "source_lang": "en", "target_lang": "vi"}'
```
```json
{"translation": "Hôm nay chúng ta sẽ học từ \"táo\".", ...}
```

With context — vocab word preserved:
```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Today we will learn the word '\''apple'\''.",
    "source_lang": "en", "target_lang": "vi",
    "context": "English-learning vocabulary content for Vietnamese students. Words in single quotes MUST be preserved verbatim — they are the vocabulary being taught."
  }'
```
```json
{"translation": "Hôm nay chúng ta sẽ học từ 'apple'.", ...}
```

### Translation with double-brace preservation (no context needed)

```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Today we will learn two new words: {{exorbitant}} and {{extravagant}}.", "source_lang": "en", "target_lang": "zh-TW"}'
```
```json
{"translation": "今天我們將學習兩個新詞：{{exorbitant}} 和 {{extravagant}}。", ...}
```

### Translation with language-learning mode

```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The word ecology means the study of ecosystems.",
    "source_lang": "en", "target_lang": "vi",
    "teaching_lang": "English",
    "vocab_mode": "bilingual"
  }'
```
```json
{"translation": "Từ ecology (sinh thái) có nghĩa là nghiên cứu về hệ sinh thái.", ...}
```

### English to Vietnamese

```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Tap Settings to change your password.", "source_lang": "en", "target_lang": "vi"}'
```

### English to Korean

```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Tap Settings to change your password.", "source_lang": "en", "target_lang": "ko"}'
```

Response:
```json
{
  "translation": "비밀번호를 변경하려면 설정을 탭하세요.",
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 0.45,
  "cached": false,
  "source_lang": "en",
  "target_lang": "ko"
}
```

### English to Japanese

```bash
curl -X POST http://203.171.30.194:3102/translate \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"text": "Save your progress.", "source_lang": "en", "target_lang": "ja"}'
```

### Korean review

```bash
curl -X POST http://203.171.30.194:3102/review \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"source": "Save your progress.", "translation": "프로그레스를 세이브하세요.", "source_lang": "en", "target_lang": "ko"}'
```

Response:
```json
{
  "verdict": "needs_revision",
  "score": 45,
  "issues": [
    {"type": "vocab", "span": "프로그레스", "suggest": "진행 상황", "reason": "Non-standard Konglish; prefer native Korean.", "severity": "medium"},
    {"type": "vocab", "span": "세이브", "suggest": "저장", "reason": "Non-standard Konglish; prefer native Korean.", "severity": "medium"}
  ],
  "corrected": "진행 상황을 저장하세요.",
  "source_model": "Qwen-35B-NT",
  "confidence": "medium",
  "elapsed_s": 2.1,
  "cached": false,
  "source_lang": "en",
  "target_lang": "ko"
}
```

### Batch translation (one pair per batch)

```bash
curl -X POST http://203.171.30.194:3102/translate/batch \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello.", "Settings", "Save"], "source_lang": "en", "target_lang": "ko"}'
```

### Cache stats filtered by pair

```bash
curl "http://203.171.30.194:3102/cache/stats?source_lang=en&target_lang=ko" \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6"
```

### Model status check

```bash
curl http://203.171.30.194:3102/models/status \
  -H "X-API-Key: tw-localizer-dev-a1b2c3d4e5f6"
```

## Logs

- `/home/csaptu/translator/api.log` — structured request/response log
- stdout — FastAPI + uvicorn console output

Both flow while the server runs. Rotation is not configured — use logrotate for long-lived deployments.

## Operational notes

- **Architecture**: single model (`qwen3.5:35b-a3b-q3km`) on one GPU card (port 13101). Single Qwen call per request. All 7 pairs share the same model — no model swapping between pairs.
- **Throughput**: ~15 req/min for translate, ~10 req/min for review on a single card. With cache on typical traffic, sustained >100 QPS on cache hits (sub-ms).
- **Cache file growth**: ~1 KB per entry across all pairs. 500k entries ~ 500 MB. Plan storage accordingly.
- **Cold start**: first request after startup incurs a model load delay. Preload with a dummy request if needed.
- **Restart**: `tmux kill-session -t translator && ./start.sh` — cache persists across restarts.

## Known limitations

- **No HTTPS**: plain HTTP only. The nginx passthrough at port 3102 does not add TLS.
- **In-process rate limiter**: rate limit state is not shared across processes. A single uvicorn worker is assumed.
- **Cache doesn't age out**: entries persist forever. Manual cache management via the SQLite file if needed.
- **No streaming**: all responses are complete JSON. No SSE or chunked transfer.

## Clients / SDKs

None shipped. The API is thin enough to call directly with any HTTP client. For a Python client, wrapping `requests.post` in a small function with the API key, timeout, and `source_lang`/`target_lang` is sufficient. Existing v1/v2 clients that omit the lang parameters will continue to work against en-zhTW.

### Python example

```python
import requests

BASE = "http://203.171.30.194:3102"
KEY = "tw-localizer-dev-a1b2c3d4e5f6"

def translate(text: str, target_lang: str = "zh-TW") -> dict:
    r = requests.post(
        f"{BASE}/translate",
        headers={"X-API-Key": KEY, "Content-Type": "application/json"},
        json={"text": text, "source_lang": "en", "target_lang": target_lang},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def review(source: str, translation: str, target_lang: str = "zh-TW") -> dict:
    r = requests.post(
        f"{BASE}/review",
        headers={"X-API-Key": KEY, "Content-Type": "application/json"},
        json={"source": source, "translation": translation, "source_lang": "en", "target_lang": target_lang},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()
```
