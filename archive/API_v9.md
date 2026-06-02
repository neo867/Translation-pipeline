# Translation API v9 — Complete Reference

> Delta from v8. v9 aligns with Pipeline v10 (S5 selector + L2 fixes + 3-pattern preservation + Qwen 3.6 swap).
> Generated from source: `api_server.py`, `translate.py`, `review.py`, `cache.py`.
> Date: 2026-04-23. 210 language pairs, 15 languages, N×N routing. Model: Qwen 3.6-35B-A3B-Q3_K_XL.

---

## 1. What Changed Since v8

### Runtime model
- **Qwen 3.5 → 3.6.** Benched 280-sentence apple-to-apple comparison shows 3.6 wins 18%, 3.5 wins 8%, 74% tie (same system prompt, same params). Biggest 3.6 gains: en-zhCN +9.5 acc, en-pt +5.2, en-esES +6.5. Load-balanced across 2×GPU via Python proxy on port 13100.

### Parameters
- **`vocab_mode` default changed** from `"bilingual"` to `"preserve"` when `teaching_lang` is set. Previous default produced `English_word (target_translation)` bilingual output; new default keeps English tokens in Latin script (matches S4 revise prompt + user's Pattern 2). Callers wanting bilingual output MUST now pass `vocab_mode="bilingual"` explicitly.
- No other param default changes. All v8 params continue to work.

### Response audit
New fields in `audit.stage_timings`:
| Field | Type | Description |
|---|---|---|
| `s5_decision` | str | Which candidate the S5 selector picked: `"s1"`, `"s4_iter1"`, `"s4_iter2"`, `"s4_iter3"`. `"s1"` + `no_s4_iterations` when S4 didn't fire. |
| `s5_reason` | str | Human-readable reason (e.g. `"s1_fewer_or_equal_errors"`, `"s4_fewer_errors:s1=15,s4=3"`, `"fallback_all_disqualified"`). |
| `s5_scores` | object | Per-candidate negated weight (higher = better). |
| `s5_disqualified` | array | `[[candidate_name, [reason_strings]], ...]` — Tier-1 rejections with cause. |
| `s5_overrode_final` | bool | `true` when S5 reverted an S4-accepted candidate back to S1. Counts S5 rescues. |
| `s5_margin`, `s5_margin_key` | int, str | Reserved for future per-content-type threshold tuning. |
| `l2_fixes` | array | List of L2 deterministic fix tags applied: `l2_whitespace_strip`, `l2_whitespace_collapse`, `l2_subtitle_trailing_period`, `l2_id_mood_fix`, `l2_s2t:X→Y`, `l2_t2s:X→Y`. Empty array when L2 didn't fire. |
| `s4_output_accepted` | str | Text output from the last-accepted S4 iteration (pre-S5). Empty string when S4 skipped. Used by bench scoring for true 3-way (S1/S4/S5) analysis. |
| `initial_after_l2` | str\|null | L2-modified initial (null when L2 didn't fire). |

All v8 audit fields remain.

### Preservation contract (tightened in v9)
Three patterns the pipeline must respect — **apples-to-apples with the bench Opus judge**:

**Pattern 1 — `{{double-braced}}` source tokens.** Content inside braces MUST survive at every stage. Braces are internal markers stripped at final delivery. S5 Tier-1 disqualifier checks this.

**Pattern 2 — Unbraced English teaching tokens** (when `teaching_lang=English`). Quoted/example English MUST stay in Latin script (no translation, no bilingual gloss unless `vocab_mode="bilingual"` passed). Enforced via S1 + S3 + S4 prompts; no programmatic S5 check.

**Pattern 3 — Delivered output.** Braces stripped. Content preserved. English tokens in Latin. User-facing text has NO `{{...}}`.

Both `bench_score.py` and `bench_score_neo.py` Opus judge prompts explicitly describe these 3 patterns (v9-aligned).

---

## 2. Quick Usage Guide

*How to pick the right param set for your call context. For the full param reference, see § 3.*

### Minimum required
```json
POST /translate
{ "text": "...", "source_lang": "en", "target_lang": "zhTW" }
```
Everything else is optional. Pipeline auto-detects `content_type`, `intent`, `teaching_lang`, `loanword_tolerance`, `vocab_mode` from text signals. Good for "just translate this" use cases.

### For **pedagogical / language-learning content** (subtitles, lesson material)
Always pass these explicitly — auto-detection isn't perfect:
```json
{
  "text": "...",
  "source_lang": "en", "target_lang": "zhTW",
  "teaching_lang": "English",         // tells pipeline English tokens must survive
  "content_type": "subtitle",         // or "ui_button", "ui_heading"
  "domain": "education",              // unlocks education glossary + pedagogical intent
  "intent": "pedagogical",            // consistent revise rules
  "context": "Subtitle from an English-language lesson video for language learners."
}
```
- **`teaching_lang=English`** activates Pattern 2 preservation (English vocab stays in Latin script). Default `vocab_mode` = `"preserve"` (no target-lang gloss).
- If you need `word (translation)` bilingual output, pass `"vocab_mode": "bilingual"` explicitly.
- For source text containing `{{double braced}}` tokens (Pattern 1), no extra param needed — pipeline preserves content + strips braces from delivered output.

### For **benchmarking / eval runs**
```json
{
  "text": "...", "source_lang": "en", "target_lang": "zhTW",
  "no_cache": true,      // skip cache, always fresh translation
  "verbose": true,       // include full audit (stage_timings, s5_decision, etc.)
  ...plus all pedagogical params above
}
```
The `audit.stage_timings` object in the response includes everything the bench scorer needs (`s4_output_accepted` = S4-intermediate; `translation` = S5-delivered; `s5_decision` + `s5_overrode_final` for selector analysis).

### For **legal / marketing / UI microcopy**
Keep `content_type` explicit (`legal` | `cta` | `ui_button` | `ui_heading`). Pass `intent` (`legal` | `transcreation_marketing` | `transcreation_ux`) for strictness-appropriate revise behavior. Legal: `"strictness": "linguist"` for maximum fidelity checks.

### Speaker-aware subtitle
When dialogue gender matters (Thai/Japanese/Korean particles):
```json
"speaker": { "gender": "female", "role": "teacher", "age_band": "adult" }
```

### Preserve-verbatim brand names / technical terms
```json
"preserve_list": ["FlowTasks", "TensorFlow", "kubectl"]
```
These never translate, regardless of context. Pipeline wraps them in `{{...}}` internally and strips braces at delivery.

### What's auto-detected vs what to pass
| Param | Auto-detected? | When to override |
|---|---|---|
| `content_type` | Yes (from length, punctuation, timestamp patterns) | Always for pedagogical (auto picks `subtitle` reliably but fails on mixed). |
| `intent` | Yes | Override for marketing/legal — auto defaults to `literal`. |
| `teaching_lang` | Yes (from text signals) | Override when text is ambiguous (short sentences). |
| `vocab_mode` | Defaults to `preserve` when teaching_lang set | Pass `bilingual` for side-by-side output. |
| `loanword_tolerance` | Per-lang default | Override for strict nativization (`low`) or permissive (`high`). |
| `domain` | Not auto-detected | Pass `"education"`, `"legal"`, `"tech"`, `"medical"`, `"finance"`, `"marketing"` for glossary routing. |

### Response fields to read
- `translation` — delivered text (braces stripped, S5-selected)
- `confidence` — `high` / `medium` / `low`
- `audit.stage_timings.s5_decision` — which candidate was delivered
- `audit.stage_timings.s5_overrode_final` — true when S5 reverted an S4 decision
- `audit.stage_timings.had_revision` — true when S4 fired
- `warnings` — non-empty only when something degraded (FALLBACK_ORIGINAL, placeholder leak, etc.)

### Model selection (new Phase 4)
No caller-facing change. The production path `nginx:3101 → LB:13100 → ollama` uses `DEFAULT_MODEL` env var (currently `qwen3.6:35b-a3b-q3kxl`). External clients hitting `:3101` can pass empty `model` field or omit it — LB substitutes the default. Translator internal path (`:13102`) uses `models.json` explicit model name (for model_manager pre-warming).

### Cache semantics
- Default: reads cache first, writes on miss.
- `no_cache: true`: skips both read AND write (true fresh pipeline run).
- Cache key = `hash(source_lang, target_lang, source_text, context, teaching_lang, vocab_mode)`. Different `context` strings = different cache entries.

---

## 3. Endpoints (unchanged from v8)

See v8 for full list. No endpoint signature changes.

---

## 4. Parameter Reference Table (only changes shown)

### `POST /translate` — `TranslateSingleReq`

| Param | Type | Default | Notes |
|---|---|---|---|
| `vocab_mode` | `"preserve" \| "bilingual" \| null` | `null` (resolves to `"preserve"` when `teaching_lang` set; was `"bilingual"` in v8) | Pattern 2 control. |

All other params: **unchanged from v8**. See `API_v8.md` for the full table.

---

## 5. Response Shape (delta from v8)

```json
{
  "translation": "...",          // S5 delivered, braces stripped
  "source_model": "Qwen-35B-NT",
  "confidence": "high",
  "elapsed_s": 1.42,
  "cached": false,
  "audit": {
    "stage_timings": {
      "initial_translation": "...",    // raw pre-L2 S1 (honest S1)
      "initial_after_l2": null,        // NEW v9
      "s4_output_accepted": "",        // NEW v9
      "s5_decision": "s1",             // NEW v9
      "s5_reason": "s1_fewer_or_equal_errors",  // NEW v9
      "s5_scores": {"s1": 0},          // NEW v9
      "s5_disqualified": [],           // NEW v9
      "s5_overrode_final": false,      // NEW v9
      "s5_margin": 0,                  // NEW v9
      "s5_margin_key": "subtitle+teaching+zhTW",  // NEW v9
      "l2_fixes": [],                  // NEW v9
      "s1_merged": 1.105,
      "s3_llm_sieve": 0.305,
      "s4_revise": 0.0,
      "had_revision": false,
      "revert_reason": "",
      // ... all v8 fields retained
    }
  }
}
```

---

## 6. Infrastructure Topology (v9)

```
Client
  ↓
nginx (public :3101 /v1/*, :3102 /translate) — TLS + API key
  ↓
translator API :13102 (FastAPI, single process, async)
  ↓
Python LB :13100 — /home/csaptu/gpu_proxy/proxy.py
  ├── routes least-loaded healthy backend that has the requested model
  ├── merges /api/tags across backends
  ├── circuit breaker (3 fails → 60s open)
  └── discovery TTL 60s
  ↓
ollama backends:
  :13101 (GPU 1, systemd ollama-gpu1.service) — qwen3.6:35b-a3b-q3kxl
  :13104 (GPU 0, systemd ollama-gpu0.service) — qwen3.6:35b-a3b-q3kxl
```

GGUFs on disk (rollback):
- `/opt/ollama-gguf/Qwen3.5-35B-A3B-Q3_K_M.gguf` + Modelfile in `~/models/qwen35-35b-a3b/`
- `/home/csaptu/models/qwen36-35b-a3b/Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf` + Modelfile
- `/home/csaptu/models/qwen35-27b-gguf/Qwen_Qwen3.5-27B-Q4_K_M.gguf` + Modelfile

To roll back to 3.5:
```bash
# Re-register on both GPU ollamas
cd /home/csaptu/models/qwen35-35b-a3b && OLLAMA_HOST=127.0.0.1:13101 ollama create qwen3.5:35b-a3b-q3km -f Modelfile
cd /home/csaptu/models/qwen35-35b-a3b && OLLAMA_HOST=127.0.0.1:13104 ollama create qwen3.5:35b-a3b-q3km -f Modelfile
# Swap models.json
sed -i 's/qwen3.6:35b-a3b-q3kxl/qwen3.5:35b-a3b-q3km/g' /home/csaptu/translator/models.json
# Restart API
systemctl restart translator || kill+relaunch api_server.py
```

---

## 7. Schema Migration (Phase 4)

`translations` table new columns (nullable, backwards-compat):
- `s4_intermediate` TEXT
- `s5_picked` TEXT (`'s1'` | `'s4'`)
- `s5_accuracy` INTEGER
- `s5_naturalness` INTEGER

Old rows without these columns return NULL — scorer handles gracefully.

---

## 8. Bench Methodology Alignment

See `bench-method.md` v6. Key v9 updates:
- § "Preservation Patterns" — authoritative 3-pattern spec (judge + pipeline must agree).
- § "Required Per-Language Report Table" — S1/S4/S5/HUMAN × acc+nat columns.
- § "Step 5 — S5 Deterministic Selector" — tier logic + telemetry fields.
- Type 2 bench expanded to 4-candidate scoring (S1/S4/S5/HUMAN), two deltas (Δ S4-S1, Δ S5-S1).

---

## 9. Breaking Changes / Migration

| v8 behavior | v9 behavior | Migration |
|---|---|---|
| `teaching_lang=X` without `vocab_mode` → bilingual output `X_word (tgt)` | → preserve-only (X stays in Latin) | If you relied on bilingual output, now pass `vocab_mode="bilingual"` explicitly |
| `s4_accuracy` column = Opus score of delivered (S5) | `s4_accuracy` = Opus score of S4-intermediate; `s5_accuracy` = Opus score of delivered | For historical rows, `s4_accuracy` still reflects delivered-at-scoring-time. For new benches, read `s5_accuracy` for delivered, `s4_accuracy` for S4-intermediate |
| Delivered text from qwen3.5 | Delivered text from qwen3.6 | Slightly different phrasing; overall +1-2 pt quality on non-en targets |

---

*v9 generated 2026-04-23. See PIPELINE_v10.md for internal pipeline detail.*
