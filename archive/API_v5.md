# Translation API v5 — Reference

HTTP API for translating and reviewing text across 56 language pairs. Pipeline is a unified 4-stage architecture shared by `/translate` and `/review`, backed by a Qwen retry chain with Sonnet fallback and a stage-level regression gate.

---

## What's new vs v4

- **4 stages, not 5.** Legacy stage 5 (metadata-retry) is gone. Pipeline is now **s1 merged metadata+translate → s2 regex sieve → s3 LLM sieve → s4 self-revise (with regression gate)**.
- **`/translate` and `/review` share one codebase.** `/review` calls `translate.run_model_path(initial_translation=candidate)`, reusing stages 2-4 and all the same prompts and gates.
- **Qwen retry chain + Sonnet fallback** on every LLM stage: `qwen_1 → qwen_2 → qwen_3 → sonnet_fallback`. Each attempt is post-filtered for catastrophic output (prompt leak, repetition loop, think-tag leak).
- **`metadata_mode` request parameter removed.** No more split path — merged is the only path.
- **Rate limits bumped** to 600/min (global + per-key).
- **sqlite logging extended** with per-stage timings and source tags (see `audit` field).

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/translate` | Translate one text |
| `POST` | `/translate/batch` | Translate up to 50 texts |
| `POST` | `/review` | Review a (source, candidate) pair |
| `POST` | `/review/batch` | Review up to 50 pairs |
| `GET`  | `/health` | Liveness (no auth) |
| `GET`  | `/info` | Pair configs + judge info (auth) |
| `GET`  | `/cards` | Per-card load + health (auth) |
| `GET`  | `/cache/stats` | Translation cache stats (auth) |
| `GET`  | `/review/cache/stats` | Review cache stats (auth) |
| `GET`  | `/models/status` | Currently loaded models (auth) |

---

## Base URL & auth

```
http://203.171.30.194:3102
```

Plain HTTP via nginx passthrough; FastAPI bound internally to `0.0.0.0:13102`.

Header `X-API-Key: <key>`. Dev key: `tw-localizer-dev-a1b2c3d4e5f6`. Missing/invalid → `401` (checked before rate limit).

---

## Rate limits

| Tier | Limit | Header returned on 429 |
|------|-------|------------------------|
| Global | 600 / minute (all callers combined) | `detail: global rate limit exceeded` |
| Per-key | 600 / minute | `detail: rate limit exceeded (key: ...)` |
| Per-IP (no key) | 30 / minute | `detail: rate limit exceeded (ip: ...)` |

Concurrency caps (HTTP 503 on overflow): translate=4, review=4. Response includes `Retry-After: 5`.

---

## Supported language pairs (56 total)

Seven core languages plus English, all directions:

```
en  zhTW  zhCN  ko  vi  id  th  ja
```

| From \ To | en | zhTW | zhCN | ko | vi | id | th | ja |
|-----------|----|------|------|----|----|----|----|----|
| **en**   | —  | ✓    | ✓    | ✓  | ✓  | ✓  | ✓  | ✓  |
| **zhTW** | ✓  | —    | ✓    | ✓  | ✓  | ✓  | ✓  | ✓  |
| **zhCN** | ✓  | ✓    | —    | ✓  | ✓  | ✓  | ✓  | ✓  |
| **ko**   | ✓  | ✓    | ✓    | —  | ✓  | ✓  | ✓  | ✓  |
| **vi**   | ✓  | ✓    | ✓    | ✓  | —  | ✓  | ✓  | ✓  |
| **id**   | ✓  | ✓    | ✓    | ✓  | ✓  | —  | ✓  | ✓  |
| **th**   | ✓  | ✓    | ✓    | ✓  | ✓  | ✓  | —  | ✓  |
| **ja**   | ✓  | ✓    | ✓    | ✓  | ✓  | ✓  | ✓  | —  |

`8 × 7 = 56` pairs. Codes accept either `zhTW` or `zh-TW` (normalized server-side).

---

## POST /translate

Translate one source string.

### Request

```jsonc
{
  "text": "Hello, world!",             // required, 1-2000 chars
  "source_lang": "en",                 // default: "en"
  "target_lang": "zhTW",               // default: "zhTW"
  "context": "Mobile-app UI string",   // optional, ≤1000 chars
  "teaching_lang": "English",          // optional — activates language-learning mode
  "vocab_mode": "bilingual",           // optional: "preserve" | "bilingual" | null
  "no_cache": false,                   // default: false
  "verbose": false                     // default: false — true includes full audit
}
```

### Response

```jsonc
{
  "translation": "你好,世界!",
  "source_model": "qwen3.5:27b-dense",
  "confidence": "high",                // "high" | "low"
  "elapsed_s": 1.23,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zhTW",

  // present only if verbose=true
  "audit": {
    "model": "qwen3.5:27b-dense",
    "sieve_hits": [ ... ],
    "sieve_catastrophic": [ ... ],
    "llm_sieve_issues": [ "..." ],
    "had_revision": false,
    "metadata_detected": { ... },
    "stage_timings": { ... }           // see PIPELINE_v5.md
  },

  // present only if pipeline produced soft warnings
  "warnings": [ { "code": "...", "message": "..." } ]
}
```

### Notes

- Cache is context-aware: same `(source_text, pair, context, teaching_lang, vocab_mode)` → exact key hit. Contexts of the same source may also match via a Qwen+Sonnet similarity pass (≥0.95, both) — sets `cache.context_match` to `"exact"` / `"context_mapped"` / `"similarity"`.
- `{{double-braced content}}` is preserved verbatim through the entire pipeline (prompt + sieve + regression gate).
- `no_cache=true` skips both the cache lookup and cache write.

---

## POST /translate/batch

```jsonc
{
  "texts": ["...", "...", ...],    // required, 1-50 items
  "source_lang": "en",
  "target_lang": "zhTW",
  "context": "...",                // shared across all items
  "teaching_lang": "English",
  "vocab_mode": "bilingual",
  "no_cache": false,
  "verbose": false
}
```

### Response

```jsonc
{ "results": [ { ...same shape as /translate... }, ... ] }
```

Items are translated sequentially; per-item errors do not abort the batch:

```jsonc
{ "error": "timeout: ...", "text": "original source" }
```

---

## POST /review

Check a user-supplied translation. Internally runs the same pipeline as `/translate` **with stage 1 skipped** (candidate becomes the stage-1 output), then runs s2 regex → s3 LLM sieve → s4 self-revise.

### Request

```jsonc
{
  "source": "Hello, world!",             // required, 1-2000
  "translation": "你好世界",              // required, 1-4000
  "source_lang": "en",
  "target_lang": "zhTW",
  "context": "Mobile-app UI string",     // optional
  "teaching_lang": "English",            // optional
  "vocab_mode": "bilingual",             // optional
  "no_cache": false,
  "verbose": false
}
```

### Response

```jsonc
{
  "verdict": "minor_issues",           // "ok" | "minor_issues" | "needs_revision"
  "score": 85,                         // 30-100
  "issues": [
    {
      "type": "vocab",                 // vocab|style|mistranslation|placeholder_missing|placeholder_extra|register
      "span": "信息",
      "suggest": "資訊",
      "reason": "Mainland vocabulary; Taiwan uses the suggested term.",
      "severity": "high"               // "low"|"medium"|"high"
    }
  ],
  "corrected": "你好,世界!",           // non-null iff s4 produced a different text that passed the regression gate
  "source_model": "qwen3.5:27b-dense",
  "confidence": "high",
  "elapsed_s": 1.87,
  "cached": false,
  "source_lang": "en",
  "target_lang": "zhTW",
  "audit": { ... }                     // verbose=true only
}
```

### Verdict logic

| Condition | Verdict | `corrected` |
|-----------|---------|-------------|
| s4 produced revised text ≠ candidate AND regression gate passed | `needs_revision` | revised text |
| Any high-severity issue (incl. simplified-char in zhTW, placeholder mismatch) | `needs_revision` | `null` |
| Any other issue | `minor_issues` | `null` |
| No issues | `ok` | `null` |

### Score formula

`score = 100 − Σ weight(severity)` where `{low:3, medium:10, high:25}`, clamped to `[30,100]` and bucketed by verdict (`ok` ≥ 85, `minor_issues` 70-89, `needs_revision` 30-69).

### Deterministic cross-checks (independent of LLM)

Always run, regardless of stage outputs:

- **placeholder mismatch**: any `{0}`, `%s`, `%(name)s`, `${var}`, or `{{braced}}` token in source must appear in candidate with the same count (severity: high).
- **simplified-char check** (zhTW only): any Simplified Chinese char in candidate → high.

---

## POST /review/batch

```jsonc
{
  "items": [{"source":"...","translation":"..."}, ...],  // 1-50
  "source_lang": "en",
  "target_lang": "zhTW",
  "context": "...",
  "no_cache": false,
  "verbose": false
}
```

Per-item errors:

```jsonc
{ "error": "...", "source": "...", "translation": "..." }
```

---

## GET /cards

Auth-gated diagnostic:

```jsonc
{
  "api_inflight": {"translate": 1, "review": 0},
  "api_caps":     {"translate": 4, "review": 4},
  "cards": [
    {"port": 3101, "model": "...", "loaded": true, "inflight": 1,
     "circuit_open": false, "consecutive_failures": 0, ...},
    {"port": 3102, ...}
  ]
}
```

---

## GET /cache/stats, GET /review/cache/stats

```jsonc
{
  "total_unique": 12034,
  "total_requests": 45210,
  "cache_hits_saved": 33176,
  "entries_reused": 5804,
  "context_mappings": 120,
  "by_confidence": {"high": 11800, "low": 234},
  "by_source_model": {"qwen3.5:27b-dense": 11950, ...},
  "by_language_pair": [{"source_lang":"en","target_lang":"zhTW","count":3200}, ...]
}
```

Both endpoints accept optional query params `?source_lang=&target_lang=` to scope stats to one pair.

---

## Error responses

| Status | When |
|--------|------|
| 400 | `Unsupported language pair: <pair>. Available: [...]` |
| 401 | Missing or invalid `X-API-Key` |
| 429 | Rate limit exceeded (global / key / IP) |
| 500 | Pipeline crash (pipeline normally returns a safe fallback dict; 500 only on HTTP-layer failure or placeholder leak reaching exit) |
| 503 | Concurrency cap reached (`Retry-After: 5`) |

### Soft warnings (200 response, `warnings[]` field)

| Code | Meaning |
|------|---------|
| `unclosed_double_brace` | Input has mismatched `{{` vs `}}` counts |
| `cache_leak_recovered` | Cached entry contained leaked `{{PH0}}`; invalidated |
| `pipeline_leak_detected` | Fresh pipeline output leaked; retried |
| `placeholder_leak_fallback` | Retry also leaked; returned original source |
| `pipeline_exception` | Internal crash caught; returned source verbatim |
| `corrected_leak_dropped` | Review s4 produced leak; `corrected` nulled |
| `corrected_catastrophic_dropped` | Review s4 output looked broken (prompt leak, repetition loop, etc); `corrected` nulled |
| `api_corrected_leak_stripped` | API layer detected leak in `corrected`; stripped |

---

## Language codes & normalization

| Input | Normalized |
|-------|------------|
| `en`, `EN` | `en` |
| `zh-TW`, `zhTW`, `zh-tw` | `zhTW` |
| `zh-CN`, `zhCN`, `zh-cn` | `zhCN` |
| `ko`, `vi`, `id`, `th`, `ja` | unchanged |

Normalization: split on `-`; if second part is 2 chars, uppercase → `{first}{UPPER}`.

---

## See also

- `PIPELINE_v5.md` — internal stage-by-stage architecture, retry chain, regression gates, catastrophic detector, sieve init filters, sqlite schema.
- `LANGUAGES.md` — per-language sieve behavior and glossary notes.
