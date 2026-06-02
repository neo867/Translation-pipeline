# Translation Pipeline v5 — Architecture

Internal architecture notes for `translate.py` + `review.py`. For user-facing request/response shapes, see `API_v5.md`.

---

## High-level

```
                         /translate                         /review
                              │                                │
                              ▼                                ▼
                     cache lookup (context-aware)      review_cache lookup
                              │                                │
                   miss │                                │ miss
                              ▼                                ▼
                    ┌──────────────────────┐     ┌──────────────────────┐
                    │ S1 merged meta+trans │     │ S1 metadata-only     │
                    │ (one Qwen JSON call) │     │ (cache → fresh extr) │
                    └──────────────────────┘     └──────────────────────┘
                              │                                │
                              ▼                                ▼
                        initial = merged           initial = candidate (user-supplied)
                              │                                │
                              └───────────────┬────────────────┘
                                              ▼
                                   run_model_path(rt, …)
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
              S2 regex sieve (initial)                       S3 LLM sieve (initial)
              [hits, catastrophic]                           [bullets]
                      │                                               │
                      └──────┬────────────────────────────────────────┘
                             ▼
              bullets = [HIGH] deterministic + [LOW] llm/soft
                             │
                             ▼ (only if has_any_issue)
                      S4 self-revise — Qwen retry chain → Sonnet fallback
                             │
                             ▼
                      regression gate (_revise_regressed)
                        ├─ regress → revert to initial
                        └─ accept → final = revised
                             │
                             ▼
                  cache.put (writes per-stage timings to sqlite columns)
```

One Qwen call per stage. Stage 2 (regex) is CPU only. Stages 1/3/4 each pick a card independently via the load balancer.

---

## Stage-by-stage

### S1 — merged metadata + translate (`/translate` only)

**File:** `translate.py::_merge_meta_and_translate`

Single Qwen call, one JSON output:

```json
{"metadata": {...}, "translation": "..."}
```

- System prompt: translator that "first extracts literal metadata, then translates"
- User prompt: kinship hints (per source lang: vi/th/zh/ko) + metadata schema + source text
- **Validator:** `_validate_merged` — parses JSON, rejects if no `translation` key or empty string. Retry chain fires until a valid shape is returned.
- **`json_expected=True`** — the catastrophic detector skips `prompt_leak_json` / `prompt_leak_prefix` patterns for this stage (legitimate JSON output).
- **Timeout:** `max(5, min(45, 5 + len(source)//40))` seconds per Qwen attempt.
- **Fallback:** if merged fails after all retries, `detected_metadata = {}` and stage 1 runs separately inside `run_model_path`.

For `/review`: no merged call — stage 1 is `_detect_metadata` (metadata only), with the same retry+validator+Sonnet pattern. Candidate translation is already supplied by the caller.

### S2 — regex sieve

**File:** `translate.py::LangPairRuntime.regex_scan`

Pure-CPU deterministic scan. Produces:

```python
{
  "hits": [ {wrong, correct, type}, ... ],
  "catastrophic": [ {type, msg}, ... ],
  "cn_hits": [...],         # cn_tw pair only
  "cn_only_hits": [...],
  "ko_hits": [...],         # formality_konglish pair only
  "has_issue": bool
}
```

**Catastrophic subtypes** (`_scan_catastrophic`, source-aware):

| Type | Trigger |
|------|---------|
| `placeholder_leak` | Output contains `{{PH0}}`-style internal cache marker |
| `placeholder_mismatch` | `{0}`/`%s`/`%(x)s` tokens differ between source and output |
| `brace_content_mismatch` | `{{...}}` double-braced content differs verbatim |
| `untranslated` | Output equals source (len>10) |
| `length_ramble` | Output is >4× source length and >200 chars |
| `length_truncated` | Output is <20% of source length (source >30 chars) |

Never mutates output — detection only.

### S3 — LLM sieve

**File:** `translate.py::_run_llm_sieve`

Calls the same model with a language-specific prompt (`sieves/<pair>.txt` → `sieves/<target>.txt` → generated default). Returns `OK` or bullet list of issues.

- **Timeout:** `max(3, min(25, 3 + (src+tr)//50))` seconds.
- Retry chain: qwen_1 → qwen_2 → qwen_3 → sonnet_fallback.
- Returns `[]` when response is `OK` or whitespace.
- Per-pair sieve prompts for ko/ja/id/vi were rewritten Thai-style: "flag only objective errors"; stylistic nits become advisory `[LOW]` bullets at s4.

### S4 — self-revise

**File:** `translate.py::run_model_path` (stage 4 block)

Only runs if `scan_initial.has_issue OR llm_issues` is non-empty.

- Prompt template (`revise_prompt_tpl`): teaches `[HIGH]` vs `[LOW]` discipline.
  - **[HIGH]** = objective error (wrong script, missing diacritic, placeholder leak, char-variant mismatch). Apply the fix.
  - **[LOW]** = stylistic suggestion or LLM judgment. Apply ONLY if you agree the current wording is clearly wrong. Otherwise keep the prior text.
- **Timeout:** `max(3, min(30, 3 + (src+initial)//50))` seconds.
- Retry chain: qwen_1 → qwen_2 → qwen_3 → sonnet_fallback.
- Output runs through the regression gate (`_revise_regressed`) before acceptance.

---

## LLM retry chain (`_stage_call_with_retries`)

Shared by s1 merged, s1 metadata-only (`/review`), s3 LLM sieve, s4 revise.

```
attempt 1 — qwen_1 (load balancer picks card)
  │ fail (timeout/empty/catastrophic/validator)
  ▼
attempt 2 — qwen_2 (load balancer picks card again)
  │ fail
  ▼
attempt 3 — qwen_3 (load balancer picks card again)
  │ fail
  ▼
attempt 4 — sonnet_fallback (claude-sonnet-4-6)
  │ fail
  ▼
return {text: "", source_tag: "all_failed"}
```

Each attempt independently post-filtered:

1. Empty output → `error: empty_output`
2. `_looks_catastrophic(text, json_expected)` → `error: <pattern_name>`
3. Optional `validator(text)` → stage-specific rejection

Returns `{text, source_tag, port, attempts[], final_model}`.

### Catastrophic detector `_looks_catastrophic`

Cheap structural post-filter, not semantic. Patterns:

| Reason | Regex | Notes |
|--------|-------|-------|
| `prompt_leak_json` | `^\s*\{.*"(translation\|metadata\|output)"\s*:` | Bypassed when `json_expected=True` |
| `prompt_leak_prefix` | `^\s*(Translation\|Output\|Assistant\|Metadata\|Source\|Target)\s*:` | Bypassed when `json_expected=True` |
| `prompt_leak_fence` | ```` ``` ```` | Always applied |
| `think_tag_leak` | `<\s*think\s*>` | Always applied |
| `repetition_loop` | `(\S{3,})(?:\s*\1){3,}` | Catches token-run degeneracies |

### `json_expected` flag

Set to `True` only for the s1 merged call (which legitimately returns JSON). All other stages use the default where JSON-looking output is treated as prompt leakage.

### Validators

Stage-specific shape checks, applied AFTER `_looks_catastrophic` passes:

| Stage | Validator | Rejects when |
|-------|-----------|--------------|
| s1 merged | `_validate_merged` | Can't parse a JSON with a non-empty `translation` key |
| s1 meta-only (`/review`) | (lenient JSON scan) | — |
| s3, s4 | (none) | — |

---

## Bullet tagging `build_revise_bullets`

S4 sees a stitched bullet list prefixed with confidence tags:

```
- [HIGH] You used '信息' (Mainland) — in Taiwan, use '資訊'
- [HIGH] CRITICAL: Output is 4.1× the source length.
- [LOW] '피드백' may be a Konglish loan — consider '의견' if unnatural here
- [LOW] Formality feels slightly off for this context.
```

### Tag rules

| Source | Tag |
|--------|-----|
| `cn_hits`, `cn_only_hits` (paired dictionary swaps, high-precision) | `[HIGH]` |
| `ko_hits` (konglish) | `[LOW]` |
| `hits[].type` ∈ `{diacritics, romanization, trad_char_in_cn, script_mix, placeholder_leak, untranslated, length_ramble}` | `[HIGH]` |
| All other `hits[]` (register, slang, style, etc.) | `[LOW]` |
| `catastrophic[]` | `[HIGH]` |
| `llm_sieve_issues[]` | `[LOW]` |

The revise prompt explicitly teaches the model to treat `[LOW]` as advisory and default to keeping prior text unless a change clearly improves it.

---

## Regression gate `_revise_regressed`

**File:** `translate.py::_revise_regressed`

Runs on every s4 output. Returns `(should_revert, reason)`. If `True`, `final = initial` and `revised` is nulled out.

| Check | Trigger | Condition |
|-------|---------|-----------|
| `empty_revision` | Revised text is empty | — |
| `low_only_minor_drift` | **NEW in v5.** All bullets are `[LOW]` AND change is minor. | CJK/Thai: `SequenceMatcher` ratio ≥ 0.80 AND `abs(len_delta) ≤ 6`. Latin (ko/vi/id): ≤3 words changed via aligned diff (min 3 words total). |
| `contamination_increased` | Target-script contamination grew | `r_score > i_score + 0.05 AND r_score > 0.10` |
| `braced_tokens_dropped` | Revised lost a `{{...}}` token the initial had | any loss |
| `length_delta_excessive` | Revised dramatically expanded or truncated | `abs(r_len − i_len) / i_len > 0.40` (i_len ≥ 10) |
| `latin_contamination_increased` | CJK/Thai target gained Latin letters | `r_latin > i_latin + 3 AND r_latin > i_latin × 1.5` |
| `foreign_script_inserted_th` | Thai target: Arabic/Cyrillic/Hebrew letter appeared | any new foreign char |
| `thai_combining_marks_orphaned` | Thai combining marks without preceding base consonant | `r_orphans > i_orphans` |
| `critical_hits_increased` | Revised introduced a new critical hit | `r_crit > i_crit` on set `{calque, trad_char_in_cn, placeholder_mismatch, brace_content_mismatch, length_ramble, length_truncated, untranslated, katakana_overuse}` |

Contamination score = fraction of non-whitespace chars outside the allowed Unicode ranges for the target, excluding `{{braced}}` and `preserve_verbatim` words. Allowed ranges:

| Target | Ranges |
|--------|--------|
| en, id, vi | Latin + Latin Extended + Latin Extended Additional (`0041-007A`, `00C0-024F`, `1E00-1EFF`) |
| zhCN, zhTW | CJK unified (`4E00-9FFF`) + CJK punct + FW forms |
| ja | CJK + hiragana + katakana (`3040-30FF`) |
| ko | Hangul (`AC00-D7AF`) + Jamo + CJK (hanja occasionally legit) |
| th | Thai (`0E00-0E7F`) + Latin (loanwords) |

---

## `/review` reuses `/translate`'s pipeline

Unified codebase. `review.py::review` does:

1. `model_manager.ensure_models_loaded(pair)` + `_tp.get_runtime(pair)`.
2. `review_cache.get(...)` — separate cache keyed on (source, candidate, pair).
3. **Stage 1 (metadata only):**
   - `cache.get_cached_metadata(source, source_lang)` — reuses `/translate`'s metadata cache.
   - On miss: `_tp._detect_metadata(...)` via the retry chain (qwen→qwen→qwen→sonnet).
4. Build `effective_context` = caller context + `_build_metadata_context(meta, target_lang)`.
5. **Stages 2-4:** `_tp.run_model_path(rt, source, ..., initial_translation=target_text, pre_s1_port=0, preserve_verbatim=…)`. Because `initial_translation` is set, stage 1 inside `run_model_path` is skipped.
6. Convert scan output to `issues[]` with `_sieve_to_issues`, merge with LLM sieve bullets + `_placeholder_mismatch` + `_simplified_char_check`.
7. Derive verdict from (revised≠candidate, high-severity hits).
8. Safety: drop `corrected` if it contains a placeholder leak or is catastrophic.
9. `review_cache.put(...)`.

Same prompts, same retry chain, same regression gate, same catastrophic detector.

---

## Sieve per-language init filters

To suppress over-fires observed across bench/prod traffic, dictionary entries are filtered at runtime load:

### Korean (`_init_ko_sieve`)

`_konglish_blacklist` is built from `dicts/ko/<>.json::konglish_blacklist` with three filters:

1. **`_KO_ACCEPTED_LOANWORDS` safelist** (dropped even if the dictionary flags them):
   ```
   AI, ai, 에이아이, 피드백, 프린터, 프리랜서, 팀리더, 팀 리더, 밴드,
   컴퓨터, 이메일, 메일, 소프트웨어, 하드웨어, 파일, 다운로드, 업로드,
   로그인, 로그아웃, 패스워드, 비밀번호, 쇼핑몰, 카페, 호텔, 비디오,
   오디오, 클릭, 앱, 버튼, 메뉴, 서버, 데이터, 웹사이트, 블로그,
   이모지, 이모티콘, 텍스트, 코드, 링크
   ```
   These are in widespread modern use; over-nativizing hurts quality.
2. **Noop entries dropped** where `konglish == native` (no real suggestion).
3. **Single-char entries dropped** (e.g. `탭`, `풀`, `벅`) — they over-fire on common Hangul syllables in unrelated words.

### Japanese (`_init_ja_sieve`)

`_ja_katakana_blacklist`: drop single-char entries (`カ`, `コ`). Katakana is unspaced — 1-char keys fire inside longer compounds (`カメラ`, `コーヒー`). A full-run regex `(?<!katakana)key(?!katakana)` is also applied at scan time.

### Vietnamese (`_init_vi_sieve`)

- `_vi_diacritics`: drop entries where `len(wrong) < 2` (single vowels `u`/`o`/`y`/`A` fire on any standalone vowel).
- `_vi_southern`: require `len(south) >= 3` AND `freq ∈ {"very_common","common"}`. Short words like `ba` match many unrelated Vietnamese words.

### Indonesian (`_init_id_sieve`)

- `_id_slang`: require `len(slang) >= 2`.
- `_id_malay`: require both sides present and `len(malay) >= 3`.

### Thai (`_init_th_sieve`)

- Romanization: only flag words of `len >= 4` (skips English acronyms).
- ASCII ratio: flag only if `>50%` (was 30%, over-flagged).
- Royal language in casual: **disabled** (false-positive rate too high for single-sentence scoring).
- Classifier check: narrowed window from 20 chars to 8 chars and requires adjacency.
- Gender particle mixing: **disabled** (text may legitimately quote a speaker of the opposite gender).

### English (`_init_en_sieve`)

- `_en_translationese`, `_en_prepositions`, `_en_misspellings`, `_en_uncountable_plurals`, `_en_article_rules`: drop entries where `wrong == correct`.
- `_en_uncountable_set`: require alpha-only, `len >= 3`.

### Generic (`_init_generic_sieve`)

- `_freq_top_words`: words ranked in top-1000 for target skip loanword blacklist (prevent flagging common words).
- `_calque_blacklist`, `_diacritics_blacklist`, `_register_tags`: null/equality guards.

---

## sqlite logging schema

Table `translations` (see `cache.py::init`):

| Column | Type | Source | Purpose |
|--------|------|--------|---------|
| `key_hash` | TEXT PK | sha256(lang+text+context bundle) | Exact cache lookup |
| `source_lang`, `target_lang` | TEXT | request | Filter stats by pair |
| `source_text`, `template_source` | TEXT | request | Original + placeholder-templated form |
| `translation`, `template_translation` | TEXT | pipeline output | Final + placeholder-templated form |
| `context_text` | TEXT | request | For similarity lookups |
| `text_hash` | TEXT | sha256(lang+template) | Context-independent lookup |
| `ctx_text_hash` | TEXT | sha256(context) | Mapping-table join |
| `teaching_lang`, `vocab_mode` | TEXT | request | Language-learning mode keys |
| `source_model`, `confidence` | TEXT | audit | e.g. `qwen3.5:27b-dense`, `high`/`low` |
| `elapsed_s` | REAL | total wall | End-to-end pipeline duration |
| `audit_json` | TEXT | full audit | Complete stage details |
| `metadata_json` | TEXT | detected meta | Reusable metadata cache |
| `metadata_hash` | TEXT | sha256(meta) | Dedupe |
| `s1_elapsed_s` | REAL | `audit.stage_timings.s1_merged` | **NEW v5** — s1 wall time |
| `s3_elapsed_s` | REAL | `audit.stage_timings.s3_llm_sieve` | **NEW v5** |
| `s4_elapsed_s` | REAL | `audit.stage_timings.s4_revise` | **NEW v5** (0 if no revision) |
| `s1_source` | TEXT | `audit.stage_timings.s1_merged_source` | **NEW v5** — `qwen_1`/`qwen_2`/`qwen_3`/`sonnet_fallback`/`all_failed` |
| `s3_source` | TEXT | — | **NEW v5** — same tag values |
| `s4_source` | TEXT | — | **NEW v5** — same tag values (`skipped` when no revise needed) |
| `had_revision` | INTEGER | — | **NEW v5** — 1 if s4 output accepted |
| `merged_used` | INTEGER | — | **NEW v5** — 1 if s1 merged call returned usable output |
| `revert_reason` | TEXT | regression gate | **NEW v5** — non-null when s4 was reverted |
| `created_at`, `last_hit_at`, `hit_count` | REAL/INT | — | Cache analytics |

Table `context_mappings` (context similarity matches): `(new_ctx_hash, old_ctx_hash, score, created_at)`.

All inserts use `ON CONFLICT(key_hash) DO UPDATE` — same text+pair+context bundle refreshes all stage fields on re-run.

### Example analytics queries

```sql
-- qwen_1 first-try success rate per pair
SELECT source_lang||'-'||target_lang AS pair,
       SUM(s1_source='qwen_1')*100.0/COUNT(*) AS pct_q1, COUNT(*) AS n
FROM translations GROUP BY pair ORDER BY pct_q1;

-- s4 revert reasons
SELECT revert_reason, COUNT(*) AS n FROM translations
WHERE had_revision=0 AND revert_reason IS NOT NULL
GROUP BY revert_reason ORDER BY n DESC;
```

---

## Legacy removed in v5

| Removed | Why |
|---------|-----|
| Stage 5 (metadata-retry) | Merged call in s1 + retry chain makes a separate metadata-retry stage redundant. |
| `metadata_mode` request parameter | No more split path — merged is the only path. |
| `_verify_metadata` function | Belonged to removed stage 5. |
| `bench_stage5.py` | Benched the removed stage. |
| `judge_rescues.py` | Superseded by the unified retry chain + Sonnet fallback. |
| `PIPELINE_v4.md`, `BENCH_v4.md` | Replaced by `PIPELINE_v5.md`. |

If you need the old split metadata path (separate `_detect_metadata` call before a translation-only s1), restore from git history — but note that `/review` still keeps the metadata-only path for exactly that reason (the candidate is already supplied).

---

## Files of interest

| File | Role |
|------|------|
| `translate.py` | Pipeline, retry chain, sieve, regression gate |
| `review.py` | Unified reviewer that calls `run_model_path(initial_translation=...)` |
| `cache.py` | Translation cache (sqlite) + context-similarity mapping |
| `review_cache.py` | Separate review cache |
| `api_server.py` | FastAPI endpoints, auth, rate limit, concurrency gate |
| `load_balancer.py` | Per-card GPU load picker with circuit breaker |
| `model_manager.py` | On-demand Ollama model load/unload |
| `sieves/<pair>.txt`, `sieves/<target>.txt` | Per-language LLM sieve prompts |
| `dicts/<lang>/*.json` | Per-language dictionaries (loanwords, diacritics, classifiers, …) |
| `translations.sqlite` | Cache + analytics |
