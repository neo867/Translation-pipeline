# Translation Pipeline — 7-Pair Single-Model Architecture, Sieves, Cache, Build Guide

Complete specification for the multi-language-pair translation system. All 7 deployed pairs use a single Qwen call per request through `qwen3.5:35b-a3b-q3km` on port 13101.

## Deployed pairs

| Pair | Tokenizer | Sieve | Dict | Glossary | LLM Sieve Prompt |
|------|-----------|-------|------|----------|-----------------|
| en-zhTW | jieba | cn_tw | dicts/en-zhTW.json | glossaries/en-zhTW.txt | sieves/en-zhTW.txt |
| en-zhCN | jieba | tw_cn | dicts/en-zhCN.json | glossaries/en-zhCN.txt | sieves/en-zhCN.txt |
| en-ko | kiwi | formality_konglish | dicts/en-ko.json | glossaries/en-ko.txt | sieves/en-ko.txt |
| en-vi | none | tone_diacritics | dicts/en-vi.json | glossaries/en-vi.txt | sieves/en-vi.txt |
| en-id | none | formality_malay | dicts/en-id.json | glossaries/en-id.txt | sieves/en-id.txt |
| en-th | none | register_script | dicts/en-th.json | glossaries/en-th.txt | sieves/en-th.txt |
| en-ja | none | formality_keigo | dicts/en-ja.json | glossaries/en-ja.txt | sieves/en-ja.txt |

## Capabilities

| Capability | Where it lives | Effect |
|-----------|---------------|--------|
| **`context` parameter** on `/translate` and `/review` | `api_server.py`, `translate._with_context`, `review._build_review_sys_prompt` | Caller-supplied free-text guidance appended to the model's system prompt (translator, self-revise, reviewer, Sonnet rescue). Cache bypassed when present. |
| **Double-brace preservation** | `LangPairRuntime.regex_scan` strips `{{...}}` before sieve scan; sys/sieve prompts instruct the model to preserve double-brace content verbatim | `{{content}}` is kept as-is; sieves never flag it. Single braces `{name}`, `{0}` are cache Tier 2 placeholder templating only. |
| **Source-aware stage 2** | `LangPairRuntime._scan_catastrophic` | Detects placeholder mismatch (`{0}` mutated to `{placeholder0}`), untranslated output, length ramble (>4x) and truncation (<0.2x). Bullets prefixed `CRITICAL:` so the stage-4 self-revise pass treats them seriously. |
| **Sonnet safety net** | `bench_stage5.needs_rescue`, `bench_stage5.sonnet_rescue` | Last-resort safety net. Fires only on catastrophic signals: empty output, upstream ERROR, placeholder leak, output identical to source, length ramble or truncation. Sonnet returns the original verbatim when nothing is actually wrong. |
| **Sonnet safety net in `/review`** | `review.review` (end of pipeline) | Same catastrophic detector + Sonnet rescue applied to the reviewer-produced `corrected` text. Replaces `corrected` when Sonnet rewrites it. Adds a `rescue` block to the audit. |
| **Load balancer** | `load_balancer.py`; used by `translate.translate` and `review._call_primary` | Both slots point to the same model on port 13101. Includes per-card in-flight tracking, active health probe (30s TTL), and circuit breaker (3 fails -> 60s open). Discovery cached 60s. |
| **Concurrency cap** | `api_server._acquire_inflight` | Bounded in-flight count per endpoint group (default 4 each for translate/review). HTTP 503 + `Retry-After` past the cap. |
| **Single model** | `models.json` | All 7 pairs: m1 == m2 == `qwen3.5:35b-a3b-q3km` on port 13101. Single Qwen call per request. |
| **Language learning** | `translate._with_context` | `teaching_lang` + `vocab_mode` parameters. Auto-detection from context keywords. Bilingual vocab format: `word (translation)`. |
| **Bench tooling** | `bench.py`, `bench_review.py`, `bench_stage5.py`, `bench_stage6.py` | `bench` runs the full per-pair translate path on cached test sentences. `bench_review` exercises `/review` end-to-end. Stage 5/6 run as separate scripts. |

---

## 1. Architecture overview

```
                   Source text + (source_lang, target_lang) [+ optional context]
                   [+ optional teaching_lang, vocab_mode]
                        |
                        v
          +-------------------------------+
          |  nginx :3102 (passthrough)    |
          |  nginx :3101 (Bearer + TLS)   |  <- ollama proxy for other apps
          +-------------+-----------------+
                        v
          +-------------------------------+
          |  FastAPI :13102 (api_server)  |
          |  + auth, rate limiter,        |
          |    pair validation,           |
          |    placeholder leak guard     |
          +-------------+-----------------+
                        | translate(text, src, tgt, context=..., teaching_lang=..., vocab_mode=...)
                        v
          +-------------------------------+
          |  Concurrency cap (in-flight)  |  <- 503 + Retry-After if cap reached
          +-------------+-----------------+
                        v
          +-------------------------------+
          |  load_balancer.pick_card      |  <- both slots point to same model/port
          |  (single port per request)    |    circuit breaker on failures
          +-------------+-----------------+
                        v
          +-------------------------------+
          |  SQLite cache lookup          |  (skipped when context is set)
          +----+-------------------+------+
               | hit               | miss
   return cached + restore         v
   placeholders                    v
                    +----------------------------+
                    |  Stage 1-4: SINGLE Qwen    |
                    |  call -> sieve -> revise   |
                    |  * Stage 1: translate      |
                    |  * Stage 2: regex sieve    |
                    |    + generic sieve         |
                    |    + catastrophic checks   |
                    |  * Stage 3: LLM sieve      |
                    |  * Stage 4: self-revise w/ |
                    |    CRITICAL bullets if any |
                    +-------------+--------------+
                                  v
                    +----------------------------+
                    |  Stage 5: catastrophic     |
                    |  detect + Sonnet rescue    |  <- /review (in API path);
                    |  (Sonnet may self-veto)    |    /translate via bench only
                    +-------------+--------------+
                                  v
                    SQLite cache.put() (skipped if context set)
                                  v
                    placeholder-leak guard
                                  v
                    ship result (+ audit)
```

The pipeline code is pair-agnostic — pair-specific behavior lives in `LangPairRuntime` instances and `models.json`. Every system prompt is composed via `_with_context(base, context)`, augmented with language-learning prompts when `teaching_lang` or `vocab_mode` is detected. Every regex sieve scan runs the pair-specific sieve plus the generic sieve (`_scan_generic`). Each request routes through the load balancer (both slots point to the same model). `/review` passes its corrected text through a Sonnet safety net before returning.

## 2. LangPairRuntime class

`LangPairRuntime` (defined in `translate.py`) is the central abstraction for per-pair configuration. One instance is lazily created per pair on first request and cached in `_runtimes` for the process lifetime.

### Construction

```python
rt = LangPairRuntime(pair="en-zhTW", cfg=model_manager.get_pair_config("en-zhTW"))
```

`cfg` comes from `models.json` (see section 3). On construction, the runtime:

1. **Loads the dictionary** from `cfg["dict"]` (e.g. `dicts/en-zhTW.json`). This is the sieve's vocabulary database.
2. **Loads the glossary** from `cfg["glossary"]` (e.g. `glossaries/en-zhTW.txt`). This is injected into the system prompt.
3. **Initializes the tokenizer** based on `cfg["tokenizer"]`:
   - `"jieba"` — Chinese word segmenter. TW-biased vocab: paired-TW terms registered at freq 10,000; paired-CN at 2,000. Jieba prefers TW tokenization when ambiguous.
   - `"kiwi"` — Korean morphological analyzer via kiwipiepy. Returns morpheme forms.
   - `"none"` or omitted — whitespace split fallback. Used by en-vi, en-id, en-th, en-ja.
4. **Initializes the sieve** based on `cfg["sieve"]`:
   - `"cn_tw"` — Mainland vs. Taiwan Chinese vocabulary detection.
   - `"tw_cn"` — Taiwan vocabulary in Mainland Chinese output detection.
   - `"formality_konglish"` — Konglish blacklist + formality register checks for Korean.
   - `"tone_diacritics"` — Vietnamese diacritics + loanword + kinship/classifier checks.
   - `"formality_malay"` — Jakarta slang + loanword checks for Indonesian.
   - `"register_script"` — Thai romanization + script mix detection.
   - `"formality_keigo"` — Japanese katakana-to-kanji preference + keigo checks.
5. **Builds all prompts** (system, self-revise template, judge template) with the pair's `source_name` and `target_name` and pair-specific `extra_rules` injected.

### Key methods

| Method | Purpose |
|--------|---------|
| `tokenize(text)` | Segment text using the pair's tokenizer, returns `set[str]` |
| `regex_scan(text, source=...)` | Run pair-specific sieve + generic sieve, returns structured hit dict |
| `build_revise_bullets(scan)` | Format sieve hits as human-readable bullet list for the self-revise prompt |
| `format_issues(scan)` | Compact one-line issue summary for the judge prompt |

### Runtime registry

Runtimes are stored in `_runtimes: dict[str, LangPairRuntime]` behind a lock. `get_runtime(pair)` creates on demand. Since all pairs share the same model, runtimes hold only config, dicts, and tokenizers — no model loading state.

## 3. Model configuration (`models.json`)

All pair-specific model and resource config lives in a single JSON file. All 7 pairs point to the same model on the same port:

```json
{
  "en-zhTW": {
    "m1": {
      "name": "qwen3.5:35b-a3b-q3km",
      "gpu": 1,
      "port": 13101,
      "label": "Qwen-35B-NT"
    },
    "m2": {
      "name": "qwen3.5:35b-a3b-q3km",
      "gpu": 1,
      "port": 13101,
      "label": "Qwen-35B-NT"
    },
    "tokenizer": "jieba",
    "sieve": "cn_tw",
    "dict": "dicts/en-zhTW.json",
    "glossary": "glossaries/en-zhTW.txt",
    "llm_sieve": "sieves/en-zhTW.txt",
    "source_name": "English",
    "target_name": "Taiwanese Mandarin (Traditional Chinese, Taiwan usage)"
  },
  "en-zhCN": {
    "m1": { "name": "qwen3.5:35b-a3b-q3km", "gpu": 1, "port": 13101, "label": "Qwen-35B-NT" },
    "m2": { "name": "qwen3.5:35b-a3b-q3km", "gpu": 1, "port": 13101, "label": "Qwen-35B-NT" },
    "tokenizer": "jieba",
    "sieve": "tw_cn",
    "dict": "dicts/en-zhCN.json",
    "glossary": "glossaries/en-zhCN.txt",
    "llm_sieve": "sieves/en-zhCN.txt",
    "source_name": "English",
    "target_name": "Simplified Chinese (Mainland China usage)"
  }
}
```

All pairs follow the same pattern: `m1` and `m2` both point to `qwen3.5:35b-a3b-q3km` on port 13101. The load balancer still exists but both slots resolve to the same endpoint.

**Field reference**

| Field | Meaning |
|-------|---------|
| `m1` / `m2` | Both point to the same model — legacy dual-model fields kept for compatibility |
| `m1.name` | Ollama model identifier (`qwen3.5:35b-a3b-q3km` for all pairs) |
| `m1.gpu` | GPU index (1 for all pairs) |
| `m1.port` | Ollama instance port (13101 for all pairs) |
| `m1.label` | Human-readable name used in `source_model` responses |
| `tokenizer` | Which tokenizer: `jieba`, `kiwi`, or `none` |
| `sieve` | Which sieve strategy (see section 6) |
| `dict` | Path (relative to project root) to the pair's dictionary JSON |
| `glossary` | Path to the pair's prompt glossary text file |
| `llm_sieve` | Path to the pair's LLM sieve prompt file |
| `source_name` | Human name of source language (for prompts) |
| `target_name` | Human name of target language (for prompts) |

## 4. Model manager

`model_manager.py` handles model configuration lookup and Ollama model loading. Since all 7 pairs use the same model on the same port, there is no model swapping — the model stays loaded permanently.

### State

- `_current_pair` — the pair whose models are currently loaded (or `None` on cold start).
- `_loaded` — dict mapping `"m1"` / `"m2"` to the currently loaded model name string.
- `_lock` — threading lock serializing any load operations.

### `ensure_models_loaded(pair)` flow

Called at the top of every `translate()` and `review()` call:

1. Look up pair config from `models.json`.
2. Compare `_loaded["m1"]` with `cfg["m1"]["name"]`.
3. Since all pairs share the same model, this is always a match after the first request. Return immediately.
4. On cold start only: send a minimal chat request with `keep_alive: "30m"` to warm the model into GPU memory.

### Timing

- Cold load (first request after reboot): ~30-60s for the 35B model.
- All subsequent requests: <1ms (dict lookup, model already loaded).
- No pair-switching delay — all pairs share the same model.

## 5. Stage-by-stage pipeline

### Stage 0 — Context-aware cache lookup (SQLite-backed)

The cache is fully context-aware — translations with `context`, `teaching_lang`, and `vocab_mode` are cached (not bypassed). The cache key includes the full parameter bundle.

**Lookup flow:**
1. **Exact match** — hash(text + pair + context + teaching_lang + vocab_mode) against `key_hash`. Sub-ms.
2. **Known mapping** — if context is set, check `context_mappings` table for a previously verified equivalent context hash. If found and score ≥ 95%, look up the mapped entry. Sub-ms.
3. **LLM similarity** (cache miss with context) — fetch all cached entries for the same text (via `text_hash` index), pre-filter by word-cosine similarity (top 3 candidates), then compare each with both Qwen and Sonnet. Both must score ≥ 95%. Mappings stored bidirectionally so repeat comparisons are instant.

`teaching_lang` and `vocab_mode` require exact match in the candidate filter — only free-text `context` uses LLM similarity.

**New columns:** `context_text`, `text_hash` (context-free hash for candidate search), `ctx_text_hash` (context string hash for mapping), `teaching_lang`, `vocab_mode`.

**New table:** `context_mappings(new_ctx_hash, old_ctx_hash, score, created_at)` — stores bidirectional LLM-verified context equivalences.

Before running any pipeline work:

1. **Tier 1 normalization** of incoming source text:
   - Strip leading/trailing whitespace
   - Collapse internal whitespace to single spaces
   - Strip trailing sentence-end punctuation (`. ! ?`)
   - Lowercase only if the input "looks like a sentence" — heuristic: >=4 words, or len>15 chars and contains lowercase. Short ALL-CAPS buttons stay distinct.
2. **Tier 2 placeholder templating** — replace common placeholder patterns with canonical `{{PH0}}`, `{{PH1}}`, ... markers:
   - `{name}`, `{0}` (single curly-brace — cache templating only)
   - `%s`, `%d`, `%i`, `%f` (printf-style)
   - `%(key)s` (Python percent-formatting)
   - `${name}`, `$name` (shell/template style)
3. **Build key**: `sha256(source_lang + 0x1f + target_lang + 0x1f + template_form)`. The language pair is part of the hash, so "Hello" cached for zh-TW won't collide with "Hello" cached for ko.
4. SQLite `SELECT * FROM translations WHERE key_hash = ?`

On HIT:
- Load cached `template_translation` (has `{{PHn}}` markers)
- Re-substitute markers with THIS request's placeholder values
- Count-check: if cached template has N markers but request has M placeholders (M!=N), treat as MISS
- Return cached with `cached: true` + metadata

On MISS: call `model_manager.ensure_models_loaded(pair)`, then continue to Stage 1.

### Stages 1-4 — Single Qwen call, sieve, self-revise

A single model call drives the entire pipeline:

1. **Translate (Stage 1)**: call `qwen3.5:35b-a3b-q3km` with the pair-specific system prompt + source text. The system prompt is composed via `_with_context(rt.sys_prompt, context)` — the caller's optional `context` is appended verbatim. When `teaching_lang` or `vocab_mode` is set (or language-learning keywords are auto-detected from context), the prompt is augmented with bilingual vocabulary instructions producing `word (translation)` format. The base prompt includes the double-brace preservation rule: "Any text inside double curly braces {{like this}} MUST be kept verbatim."

2. **Regex sieve (Stage 2)**: `rt.regex_scan(text, source=source_text)`. Runs two layers:
   - **Pair-specific sieve** — the sieve implementation matching `cfg["sieve"]` (see section 6).
   - **Generic sieve** (`_scan_generic`) — runs for ALL pairs (see section 7).
   - **Catastrophic checks** (`_scan_catastrophic`): placeholder leak, placeholder mismatch (`{0}` mutated), output identical to source (untranslated), output >4x source length (ramble), output <0.2x (truncated). All catastrophic hits force `has_issue=True`.
   - **Brace stripping**: `re.sub(r'\{\{[^{}]+\}\}', ' ', text)` removes double-brace blocks before pattern-matching so preserved content is not flagged.

3. **LLM sieve (Stage 3)**: pair-specific `sieves/<pair>.txt` prompt asks the model to list issues. Per-pair prompts include the rule: *"Any text inside double curly braces `{{like this}}` is intentionally preserved verbatim — do NOT flag braced content as untranslated, missing diacritics, wrong script, placeholder leak, or any other issue."*

4. **Self-revise (Stage 4, conditional)**: if any sieve found an issue, call the same model again with bulleted issues. Catastrophic bullets are prefixed `CRITICAL:` so the model treats them with priority.

The path returns: initial translation, revised translation (if any), final translation, and the sieve scan of the final output.

### Stage 5 — Catastrophic-output rescue (Sonnet)

A safety net applied on the translator's final output (in `/review`, applied to the reviewer-produced `corrected` text):

1. **`needs_rescue(translation, source, rt)`** — high-precision string/regex checks only. Returns `(True, [reasons])` when ANY of these fires:
   - empty translation
   - upstream `ERROR: ...` from translate
   - placeholder leak (internal `{{PHn}}` marker survived to output)
   - output identical to source (untranslated; double-brace-protected content stripped before compare)
   - length ramble: output > 4x source length AND > 200 chars
   - length truncation: output < 20% of source length AND source > 30 chars

2. **Sonnet rescue** — when `needs_rescue` returns `True`, send `{source, broken translation, reasons, per-pair extra_rules, optional caller context}` to Sonnet. The prompt instructs Sonnet to **self-veto**: if the translation is already good, output the original VERBATIM; only rewrite if there's a real, concrete error. The rewrite replaces the original whenever Sonnet returns text different from the input. When applied, a `corrected_rescued` warning is emitted and `audit.rescue` records `{needs_rescue, reasons[], sonnet_rewrite, applied}`.

**What stage 5 does NOT do**:
- No CPU n-gram quality score, no perplexity, no antipattern density check. These were retired.
- No "translation is mediocre" detection. That's the LLM reviewer's job (Qwen reviewer in `/review`).

**Where stage 5 runs**:
- `/translate` API path: NOT in the live API; runs in the offline bench (`bench_stage5.score_model_stage5`).
- `/review` API path: YES, at the end of `review.review` on the reviewer's `corrected` text. Adds a `rescue` block to `audit`.

### Stage 6 — Opus quality scoring (offline only)

Background scoring of cached translations against an Opus-driven rubric (`bench_stage6.STAGE6_PROMPT`: vocab/grammar/register/meaning each /20, naturalness/cultural each /10). Detached subprocess; never gates the API response. The authoritative offline quality measure.

### Stage 7 — Cache write

Store result with Tier 1+2 key + templated translation. The `source_lang` and `target_lang` are stored as columns for stats filtering. **Skipped when caller supplies `context`.**

### Stage 8 — Placeholder-leak guard (3 defense layers)

1. **Cache restoration layer** — if placeholder count mismatch, cache hit rejected, pipeline runs fresh.
2. **Pipeline exit layer** — if final translation contains `{{PHn}}`, attempt retry without cache. If retry also leaks, fall back to original source text + confidence=low + source marked `+FALLBACK_ORIGINAL`.
3. **API exit layer** — response scanned; if marker slips through, HTTP 500 rather than serve the leak.

## 6. Per-pair sieve strategies

All sieves are implemented in `translate.py`. Each pair's sieve runs as the pair-specific layer of Stage 2, followed by the generic sieve (`_scan_generic`, section 7).

### `cn_tw` — Mainland vs. Taiwan Chinese (en-zhTW)

Detects Mainland Chinese vocabulary in a translation that should be Taiwan Mandarin.

**Dict contents** (en-zhTW.json): 7507 paired_pairs, 6734 cn_only, 1808 tw_only, 10656 homonyms, 5000 frequency_top_5000.

**Vocabulary categories**:
| Category | Purpose | Runtime filter |
|----------|---------|----------------|
| `paired_pairs` | CN term present AND TW counterpart NOT present -> `cn_hit` | All entries active |
| `cn_only` | CN-only term present -> `cn_only_hit` (blacklist) | Only `g0v_moedict_csld` source |
| `tw_only` | TW-only term present -> `tw_only_hit` (positive signal) | All entries active |
| `homonyms` | Ambiguous word present -> `homonym_hit` | Only `g0v_moedict_csld` source |

**Cross-filter**: any word in `tw_only` or as a paired-TW term is removed from `cn_only` and `homonyms` active sets at init time.

**Tokenizer**: jieba with TW-biased frequencies. TW terms registered at 10,000 freq, CN terms at 2,000. This makes jieba prefer the TW segmentation when a character sequence could be tokenized as either a TW or CN word.

### `tw_cn` — Taiwan vocabulary in Mainland Chinese output (en-zhCN)

Detects Taiwan-specific vocabulary in translations that should be Simplified Chinese for Mainland China.

**Dict contents** (en-zhCN.json): 7452 paired_pairs, 4191 trad_chars_to_avoid, 77178 preferred_terms, 1901 tw_blacklist, 10656 homonyms.

**Tokenizer**: jieba. Uses tw_blacklist to flag Taiwan vocabulary. paired_pairs provide TW-to-CN mapping for correction suggestions.

### `formality_konglish` — Korean quality sieve (en-ko)

Detects two classes of issues:

**Dict contents** (en-ko.json): 725 konglish_blacklist, 379 formality_pairs, 10000 frequency_top_10000, 63 particle_patterns, 29 honorific_words.

1. **Konglish blacklist**: non-standard English loanwords transliterated into Korean when a natural Korean equivalent exists. Detection is **substring-based** (not token-based) because Konglish terms may not segment cleanly at morpheme boundaries.

2. **Formality pairs**: checks for register mismatches. The sieve is detection-only; the self-revise prompt tells the model about register expectations.

**Tokenizer**: kiwi (kiwipiepy), a Korean morphological analyzer. Returns morpheme forms via `t.form`.

**Self-revise bullets** format:
```
- You used '프로그레스' (non-standard Konglish) — use '진행 상황' instead
```

### `tone_diacritics` — Vietnamese diacritics and tone sieve (en-vi)

Detects missing or incorrect diacritical marks, inappropriate loanwords, and kinship/classifier issues.

**Dict contents** (en-vi.json): 5105 diacritics_blacklist, 438 loanword_blacklist, 68 kinship_pronouns, 78 classifier_rules, 475 northern_southern_pairs.

1. **Diacritics blacklist**: WORD-BOUNDARY matching (not substring). Self-mapping entries (where wrong==correct) are filtered at load time to prevent false positives.
2. **Loanword blacklist**: word-boundary matching. Flags unnecessary foreign loanwords when Vietnamese equivalents exist.
3. **Kinship pronouns**: checks for appropriate Vietnamese pronoun usage (anh/chi/em/con/bac).
4. **Classifiers**: validates Vietnamese classifier usage (cai, con, chiec, etc.).

**Tokenizer**: none (whitespace split). Vietnamese is a whitespace-delimited language.

### `formality_malay` — Indonesian formality sieve (en-id)

Detects Jakarta slang and inappropriate register for formal Indonesian.

**Dict contents** (en-id.json): 858 loanword_blacklist, 97 slang_blacklist, 316 malay_indonesian_pairs, 224 verb_prefix_rules, 10000 frequency_top_10000.

1. **Slang detection**: Jakarta slang set intersection (not substring).
2. **Loanword blacklist**: word-boundary matching. Flags unnecessary foreign loanwords.

**Tokenizer**: none (whitespace split).

### `register_script` — Thai script and register sieve (en-th)

Detects romanized Thai, script mixing, and register issues.

**Dict contents** (en-th.json): 942 romanization_blacklist, 855 noun_classifiers, 227 royal_common_pairs, 521 loanword_blacklist, 10000 frequency_top_10000.

1. **Romanization blacklist**: `\b` word boundaries. Flags romanized Thai words that should be in Thai script.
2. **ASCII ratio check**: if >0.3 of the output is ASCII characters, flags `script_mix` — indicates the translation contains too much non-Thai-script content.

**Tokenizer**: none (whitespace split).

### `formality_keigo` — Japanese formality sieve (en-ja)

Detects excessive katakana usage and keigo (honorific) register issues.

**Dict contents** (en-ja.json): 835 katakana_blacklist, 215 keigo_pairs, 11763 jmdict_entries, 4998 frequency_top_5000, 327 honorific_prefixes.

1. **Katakana blacklist**: **substring match**. Flags katakana loanwords when kanji/native Japanese equivalents are preferred.

**Tokenizer**: none (whitespace split).

## 7. Generic sieve (`_scan_generic`)

Runs for ALL pairs after the pair-specific sieve. Implemented in `translate.py` as `_scan_generic()`.

| Check | Matching method | Details |
|-------|----------------|---------|
| Loanword blacklist | WORD-BOUNDARY (not substring) | Skips top-1000 frequency words to avoid false positives |
| Diacritics blacklist | Word-boundary | Self-mapping entries filtered at load time |
| Romanization blacklist | `\b` word boundaries | Flags romanized target-language words |
| Slang detection | Substring | Flags informal/slang terms |
| Register tags | Tag match | `formal_archaic`, `literary`, `archaic`, `vulgar` |
| Traditional chars in zhCN | Character check | Flags traditional Chinese characters in Simplified Chinese context |
| Katakana-to-kanji (JA) | Substring | Prefers kanji over katakana where applicable |
| Royal/honorific in casual | Context check | Flags royal/honorific vocabulary in casual register context |
| Collocation misses | Threshold | Flag if >=3 expected collocations are broken |

## 8. Per-pair prompts

### System prompt structure

All pairs share the same template:

```
You are a professional translator. Translate {source_name} into {target_name}.

Rules:
{extra_rules}
- Preserve the original meaning exactly.
- Any text inside double curly braces {{like this}} MUST be kept verbatim.

{glossary_text}

Output ONLY the translation. No commentary, no explanation.
```

### Per-pair `extra_rules`

**cn_tw** (en-zhTW):
```
- Use standard written Chinese, NOT Hokkien/台語. Formal written register.
```

**tw_cn** (en-zhCN):
```
- Use Simplified Chinese (简体中文). Do NOT use Taiwan-specific vocabulary.
```

**formality_konglish** (en-ko):
```
- 해요체 default. Prefer native Korean over Konglish. Correct particles.
```

**tone_diacritics** (en-vi):
```
- ALL Vietnamese must have correct diacritical marks. Correct kinship pronouns. Northern standard.
```

**formality_malay** (en-id):
```
- saya/Anda default. Prefer native Indonesian. Standard Bahasa Indonesia.
```

**register_script** (en-th):
```
- Polite register with ครับ/ค่ะ. NEVER romanized Thai. Correct classifiers.
```

**formality_keigo** (en-ja):
```
- です/ます default. Prefer kanji over katakana. Correct particles.
```

### Language learning augmentation

When `teaching_lang` or `vocab_mode` is set (or language-learning keywords are auto-detected from context), `_with_context()` augments the system prompt with instructions to produce bilingual vocabulary in `word (translation)` format. This allows the pipeline to serve as a language-learning tool without a separate code path.

### Self-revise prompt

Same template for all pairs, with `{source_name}` and `{target_name}` substituted. The bullet list is generated by `build_revise_bullets()` which formats sieve hits in pair-appropriate language.

### Judge prompt

Same template for all pairs. Referenced only by the bench's offline Opus rubric scoring (`bench_stage6`), not by the live API pipeline.

## 9. Review pipeline

The review pipeline (`review.py`) evaluates a user-supplied translation rather than generating one.

### Flow

1. **Cache lookup** — review cache keyed on `(source_lang, target_lang, normalized_source, target_stripped)`.
2. **Deterministic sieve scan** — run the pair's sieve + generic sieve on the user's translation.
3. **Structural checks** — placeholder mismatch detection (missing/extra) and simplified character detection (zh-TW only).
4. **Reviewer call** (single Qwen call via load balancer) — the model receives the source, translation, and sieve report; **system prompt augmented with caller's `context` if any**. Produces a JSON verdict (`ok` / `minor_issues` / `needs_revision`) plus a `corrected` field.
5. **Confidence assignment**:
   - `high` — reviewer + sieve both clean.
   - `medium` — reviewer flagged with concrete issues.
   - `low` — reviewer flagged but couldn't articulate a fix, or the call failed.
   - On model failure: sieve-only verdict with `low`.
6. **Sonnet safety net** — if `final.corrected` is non-null, run `bench_stage5.needs_rescue(corrected, source, rt)`. The check is catastrophic-only (placeholder leak / output identical to source / length ramble or truncation). If it fires, call `bench_stage5.sonnet_rescue(rt, source, corrected, reasons)`. Sonnet returns the original verbatim when nothing's broken; if it returns different text, replace `final.corrected` and emit a `corrected_rescued` warning. Audit gains a `rescue` block.
7. **Scoring** — penalty-weighted from issues: high=25pts, medium=10pts, low=3pts. Score = 100 - penalty, clamped by verdict tier.
8. **Cache write** — result stored for future identical (source, translation) queries. **Skipped when `context` was supplied.**

### Review-specific sieve behavior

The review system prompt is more lenient than the translate prompt. For `cn_tw`, it instructs the reviewer to only flag vocabulary that is "genuinely Mainland-specific AND uncommon in Taiwan." For `formality_konglish`, it says Konglish is wrong "only if a natural Korean equivalent is widely used."

### Simplified character check

For `cn_tw` pairs only: every character in the user's translation is checked against `simplified_chars.json`. Any simplified Chinese character is flagged as a `vocab` issue with `severity: high`, and the verdict is forced to `needs_revision`.

## 10. Brace preservation — DOUBLE braces only

The pipeline uses a double-brace convention for content that must be preserved verbatim in translations:

- **`{{content}}`** = preserved verbatim. System prompt instructs the model to keep double-brace content as-is.
- **Single `{name}`, `{0}`** = cache Tier 2 placeholder templating only. These are replaced with `{{PH0}}` etc. during cache normalization and restored on cache hit.

### Sieve stripping

Before any sieve pattern-matching, double-brace blocks are stripped from the text:
```python
re.sub(r'\{\{[^{}]+\}\}', ' ', text)
```
This prevents vocabulary-teaching content, do-not-translate markers, etc. from triggering sieve false positives.

### Catastrophic check

`_scan_catastrophic` compares `{{...}}` blocks between source and output. If a double-brace block from the source is missing or mutated in the output, a `CRITICAL:` bullet is generated.

### Unclosed double-brace warning

If the source text contains an opening `{{` without a matching `}}`, a warning is emitted in the audit. The pipeline still processes the text but flags the potential issue.

## 11. Cache schema

Both translation and review caches live in the same SQLite file: `/home/csaptu/translator/translations.sqlite` (WAL journal mode).

### `translations` table

```sql
CREATE TABLE translations (
  key_hash TEXT PRIMARY KEY,          -- sha256(source_lang + 0x1f + target_lang + 0x1f + template)
  source_lang TEXT NOT NULL DEFAULT 'en',
  target_lang TEXT NOT NULL DEFAULT 'zh-TW',
  source_text TEXT NOT NULL,           -- raw original input
  template_source TEXT NOT NULL,       -- templated+normalized form
  translation TEXT NOT NULL,           -- latest delivered translation
  template_translation TEXT,           -- translation with {{PHi}} markers
  source_model TEXT,                   -- pair-specific model label
  confidence TEXT,                     -- high | medium | low
  elapsed_s REAL,
  audit_json TEXT,                     -- full pipeline audit as JSON
  created_at REAL NOT NULL,
  last_hit_at REAL NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_translations_last_hit ON translations(last_hit_at);
CREATE INDEX idx_translations_lang ON translations(source_lang, target_lang);
```

### `reviews` table

```sql
CREATE TABLE reviews (
  key_hash TEXT PRIMARY KEY,           -- sha256(source_lang + 0x1f + target_lang + 0x1f + template_source + 0x1f + target_stripped)
  source_lang TEXT NOT NULL DEFAULT 'en',
  target_lang TEXT NOT NULL DEFAULT 'zh-TW',
  source_text TEXT NOT NULL,
  target_text TEXT NOT NULL,           -- user's translation (byte-exact)
  template_source TEXT NOT NULL,
  verdict TEXT NOT NULL,
  score INTEGER,
  issues_json TEXT,
  corrected TEXT,
  source_model TEXT,
  confidence TEXT,
  elapsed_s REAL,
  audit_json TEXT,
  created_at REAL NOT NULL,
  last_hit_at REAL NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_reviews_last_hit ON reviews(last_hit_at);
CREATE INDEX idx_reviews_lang ON reviews(source_lang, target_lang);
```

### Key design decisions

- **Language pair in hash**: `source_lang + 0x1f + target_lang` is prepended to the normalized template before hashing. This ensures "Hello" cached for zh-TW never collides with "Hello" cached for ko.
- **`source_lang`/`target_lang` columns**: stored explicitly for `WHERE` filtering in stats queries, even though they're already baked into the hash.
- **Review key includes target text**: unlike translations (where the target is generated), review keys include the user's candidate translation because any difference in the translation is semantically meaningful.

### Audit sanitization

Audit JSON no longer contains `initial`, `revised`, `scan_initial`, or `card_port` fields. These were removed to reduce audit size and eliminate information that is no longer relevant in the single-model architecture.

## 12. Per-pair dictionary contents

### en-zhTW (cn_tw sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `paired_pairs` | 7507 | CN term -> TW equivalent mapping |
| `cn_only` | 6734 | CN-only blacklist (g0v_moedict_csld source) |
| `tw_only` | 1808 | TW-only positive signal |
| `homonyms` | 10656 | Ambiguous CN/TW words |
| `frequency_top_5000` | 5000 | High-frequency words (jieba bias) |

### en-zhCN (tw_cn sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `paired_pairs` | 7452 | TW term -> CN equivalent mapping |
| `trad_chars_to_avoid` | 4191 | Traditional characters to flag |
| `preferred_terms` | 77178 | Mainland-preferred vocabulary |
| `tw_blacklist` | 1901 | Taiwan-specific terms to reject |
| `homonyms` | 10656 | Ambiguous TW/CN words |

### en-ko (formality_konglish sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `konglish_blacklist` | 725 | Non-standard English loanwords |
| `formality_pairs` | 379 | Register mismatch detection |
| `frequency_top_10000` | 10000 | High-frequency words |
| `particle_patterns` | 63 | Korean particle validation |
| `honorific_words` | 29 | Honorific vocabulary |

### en-vi (tone_diacritics sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `diacritics_blacklist` | 5105 | Missing/wrong diacritical marks |
| `loanword_blacklist` | 438 | Unnecessary foreign loanwords |
| `kinship_pronouns` | 68 | Vietnamese pronoun appropriateness |
| `classifier_rules` | 78 | Classifier usage validation |
| `northern_southern_pairs` | 475 | Northern vs. Southern vocabulary |

### en-id (formality_malay sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `loanword_blacklist` | 858 | Unnecessary foreign loanwords |
| `slang_blacklist` | 97 | Jakarta slang terms |
| `malay_indonesian_pairs` | 316 | Malay vs. Indonesian vocabulary |
| `verb_prefix_rules` | 224 | Indonesian verb prefix validation |
| `frequency_top_10000` | 10000 | High-frequency words |

### en-th (register_script sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `romanization_blacklist` | 942 | Romanized Thai words to reject |
| `noun_classifiers` | 855 | Thai classifier validation |
| `royal_common_pairs` | 227 | Royal vs. common vocabulary |
| `loanword_blacklist` | 521 | Unnecessary foreign loanwords |
| `frequency_top_10000` | 10000 | High-frequency words |

### en-ja (formality_keigo sieve)
| Category | Count | Purpose |
|----------|-------|---------|
| `katakana_blacklist` | 835 | Katakana words with kanji equivalents |
| `keigo_pairs` | 215 | Keigo (honorific) register pairs |
| `jmdict_entries` | 11763 | JMDict vocabulary reference |
| `frequency_top_5000` | 4998 | High-frequency words |
| `honorific_prefixes` | 327 | Honorific prefix patterns |

## 13. Per-pair tokenizers

| Tokenizer | Pairs | Library | Notes |
|-----------|-------|---------|-------|
| `jieba` | en-zhTW, en-zhCN | jieba (Python) | Chinese word segmenter. Custom vocab registered at init from dict paired/tw_only/cn_only/homonym entries. TW-biased frequencies. Returns word-level tokens. |
| `kiwi` | en-ko | kiwipiepy | Korean morphological analyzer. Returns morpheme forms via `t.form`. No custom vocab registration needed. |
| `none` | en-vi, en-id, en-th, en-ja | built-in | Whitespace split. Used for languages where whitespace segmentation is sufficient or no mature tokenizer is available. |

All tokenizers return `set[str]` from `rt.tokenize(text)`. The sieve uses set membership to check for token presence.

## 14. Directory layout

```
/home/csaptu/translator/
├── api_server.py              # FastAPI entry point (auth, rate limit, pair validation, leak guard)
├── translate.py               # Pipeline: LangPairRuntime + translate() + all sieve implementations
├── review.py                  # Review pipeline: review()
├── cache.py                   # SQLite cache for translations (tier1+tier2, multi-pair)
├── review_cache.py            # SQLite cache for reviews (multi-pair)
├── model_manager.py           # Model config lookup + Ollama warm-up
├── load_balancer.py           # Card selection (both slots -> same port)
├── models.json                # Per-pair model + resource config (all 7 pairs)
├── simplified_chars.json      # Simplified Chinese character set (for zh-TW review)
├── api_keys.txt               # Authorized API keys
├── translations.sqlite        # Persistent cache (WAL journal, both tables)
├── start.sh                   # Launcher (tmux session)
├── bench.py                   # Translation benchmark driver
├── bench_review.py            # Review benchmark driver
├── bench_stage5.py            # Stage 5 catastrophic rescue benchmark
├── bench_stage6.py            # Stage 6 Opus quality scoring benchmark
├── dicts/
│   ├── en-zhTW.json           # CN/TW sieve dictionary
│   ├── en-zhCN.json           # TW/CN sieve dictionary
│   ├── en-ko.json             # Korean sieve dictionary
│   ├── en-vi.json             # Vietnamese sieve dictionary
│   ├── en-id.json             # Indonesian sieve dictionary
│   ├── en-th.json             # Thai sieve dictionary
│   └── en-ja.json             # Japanese sieve dictionary
├── glossaries/
│   ├── en-zhTW.txt            # TW prompt glossary
│   ├── en-zhCN.txt            # CN prompt glossary
│   ├── en-ko.txt              # Korean prompt glossary
│   ├── en-vi.txt              # Vietnamese prompt glossary
│   ├── en-id.txt              # Indonesian prompt glossary
│   ├── en-th.txt              # Thai prompt glossary
│   └── en-ja.txt              # Japanese prompt glossary
├── sieves/
│   ├── en-zhTW.txt            # TW LLM sieve prompt
│   ├── en-zhCN.txt            # CN LLM sieve prompt
│   ├── en-ko.txt              # Korean LLM sieve prompt
│   ├── en-vi.txt              # Vietnamese LLM sieve prompt
│   ├── en-id.txt              # Indonesian LLM sieve prompt
│   ├── en-th.txt              # Thai LLM sieve prompt
│   └── en-ja.txt              # Japanese LLM sieve prompt
├── API_v4.md                  # HTTP API documentation
├── PIPELINE_v4.md             # This file
└── BENCH_v4.md                # Benchmark documentation
```

## 15. Build / deploy guide

### 15a. Model preload (on reboot)

The Ollama instance must be running before starting the API:

```bash
# GPU 1 instance on :13101 (systemd-managed or manual)
sudo systemctl start ollama-gpu1
# OR manually:
# sudo OLLAMA_HOST=127.0.0.1:13101 OLLAMA_MODELS=/opt/ollama-gpu1 CUDA_VISIBLE_DEVICES=1 \
#   OLLAMA_FLASH_ATTENTION=1 nohup /usr/local/bin/ollama serve > /tmp/ollama-gpu1.log 2>&1 &
```

The model is loaded on-demand by the model manager when the first request arrives. You can optionally pre-warm:

```bash
curl -X POST http://127.0.0.1:13102/translate \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

### 15b. Launch API

```bash
cd /home/csaptu/translator
# Foreground (dev):
ANTHROPIC_API_KEY=sk-... python3 api_server.py

# Detached tmux (prod-like):
ANTHROPIC_API_KEY=sk-... ./start.sh
# tmux attach -t translator
# tmux kill-session -t translator
```

Optional overrides:
```bash
TRANSLATOR_HOST=127.0.0.1 \
TRANSLATOR_PORT=8080 \
RATE_LIMIT_GLOBAL=300/minute \
RATE_LIMIT_KEY=1000/minute \
RATE_LIMIT_IP=60/minute \
ANTHROPIC_API_KEY=sk-... python3 api_server.py
```

## 16. Known limitations

- **No HTTPS** — front with nginx/caddy for TLS.
- **In-process rate limiter** — resets on restart. For multi-instance, swap to a shared Redis/sqlite store.
- **Cache doesn't age out** — grows unbounded. Add a TTL sweep job if disk becomes a concern.
- **Konglish detection is substring-based** — may produce false positives if a blacklisted term appears as part of a longer, valid word. Monitor and tune the blacklist.
- **Vietnamese diacritics sieve false positives** — may flag valid compound words where a component matches the blacklist (e.g., "nay" in "hom nay", "ta" in "chung ta"). Word-boundary matching mitigates but does not eliminate this.
- **No streaming endpoint** — all responses are synchronous. For latency-sensitive paths, consider adding a streaming mode that skips self-revise.
- **Placeholder templating** only handles documented patterns (see section 5, Stage 0). Bare proper nouns or ALL-CAPS values in free-form text do NOT collapse — by design (too risky).

## 17. Iteration roadmap

- **Parallel GPU loading** — with 4+ GPUs, load multiple model instances simultaneously for higher throughput.
- **Per-pair benchmark suites** — extend `bench.py` to run pair-specific test sets with language-specific quality rubrics.
- **systemd services** for API + Ollama instance (survive reboot).
- **Cache TTL / size cap** — if cache grows past 500k entries, add `last_hit_at` pruner.
- **Reactive glossary expansion** — when production audits find repeat failures, add via validate-apply loop.
- **Streaming endpoint** — skip self-revise for latency-sensitive paths.
- **Vietnamese compound word awareness** — improve diacritics sieve to recognize multi-syllable words and avoid false positives on valid compounds.
