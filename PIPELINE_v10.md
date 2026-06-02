# Translation Pipeline v10 — S5 Deterministic Selector + L2 Fixes + 3-Pattern Preservation

> Delta from v9. v9 was S4-loop consolidation. v10 adds S5 post-S4 selector, L2 deterministic fix layer, and tightens the 3-pattern preservation contract end-to-end.
> Date: 2026-04-23. Model: Qwen 3.6-35B-A3B-Q3_K_XL on 2×GPU load-balanced.

---

## 1. New Effective Flow

```
S1 (merged meta+translate)
  ↓
S2a regex sieve on S1
  ↓
L2 deterministic fixes        ← NEW (Phase 3.6)
  ↓
S3 LLM sieve (if warranted)
  ↓
S4 revise loop (iters 1..3, regression gate per iter)
  ↓
S5 deterministic selector     ← NEW (Phase 3.1)
  ↓
Auto-fixes (trailing punct, id mood)
  ↓
Braces strip (final_text)
  ↓
Response
```

v9 had no S5 and no L2. S4's regression gate was the only safety net; on subtitle+teaching content that gate let regressions through because sieve hits don't fully correlate with Opus judgment. v10 adds a rule-based deterministic selector that compares candidates by weighted error count after the S4 loop.

---

## 2. S5 — Deterministic Best-of Selector

Purely rule-based (zero LLM). Runs after the S4 loop if ≥1 S4 iteration produced text.

**Inputs:** S1 text + scan, list of S4 iter outputs + scans, content_type, teaching_lang, target_lang, preserve_verbatim set, source_text.

### Tier 1 — Hard disqualifiers (eliminate candidate)
- empty output
- placeholder leak (`PH[0-9]+` markers)
- preserve_verbatim token dropped (teaching_lang mode only; strip braces from both text + tokens before comparison)
- target-script ratio below threshold (CJK ≥60%, Thai/Hangul ≥50%)
- length ratio outside 0.3–3.0× source chars

### Tier 2 — Weighted error count per candidate
```
weight = 10·critical + 3·high + 1·low
```
(catastrophic counted as critical)

### Tier 3 — Pick lowest weight. On tie: prefer S1 (conservative).

### Tier 4 — S1-disqualified fallback
If S1 fails Tier 1 but an S4 iter survives → pick the S4 iter with lowest weight. If ALL disqualified → return S1 as last-resort.

### Output
Override `final` if S5 chose a different candidate than pre-S5 `final`. Record telemetry:
- `s5_decision`: `s1` | `s4_iter1` | `s4_iter2` | `s4_iter3`
- `s5_reason`: human text (`s1_fewer_or_equal_errors` / `s4_fewer_errors:s1=W,s4=W` / `fallback_all_disqualified` / `s1_disqualified,picked_X:w=W`)
- `s5_scores`: per-candidate negated weight
- `s5_disqualified`: list of `(candidate, [reasons])`
- `s5_overrode_final`: bool (did S5 flip what S4 would have delivered?)

**Empirical** (Phase 3 bench, 8,025 rows):

| Content | S1 picks | S4 picks | S5-overrode-S4 |
|---|---|---|---|
| general | 84% | 16% | 159 |
| subtitle | 98% | 2% | 88 |
| ui_button | 97% | 3% | 90 |

---

## 3. L2 — Deterministic Fix Layer

Runs AFTER S2a scan, BEFORE the S4 gate. Zero LLM calls. Applies known-good deterministic patches so (a) S4 may skip entirely when L2 resolves critical issues, or (b) S4 sees cleaner input.

### Fixes
1. Whitespace: `strip()` + collapse doubles — safe for all content
2. Subtitle trailing period: strip terminal `.` when source has none — **Latin targets only** (CJK/Thai expect sentence-end punct even on fragments)
3. Indonesian imperative → infinitive for `is_continuation=True` — id only
4. zh variant correction (zhTW ← simplified glyph; zhCN ← traditional glyph) — conservative context-independent swap list only

### Preserves raw S1
The pre-L2 S1 output is captured in `initial_raw_s1` and reported in `audit.stage_timings.initial_translation`. L2-modified initial is what S4 + S5 see. If L2 fired, `audit.stage_timings.initial_after_l2` has the modified text; `l2_fixes` has the list of fix tags.

---

## 4. 3-Pattern Preservation Contract

### Pattern 1 — `{{double-braced}}` tokens in source
Caller can wrap tokens in `{{...}}`. Pipeline contract:
- Content inside braces MUST survive unchanged at every stage (S1 → S5).
- Braces are internal markers — stripped at delivery via `re.sub(r"\{\{([^{}]+)\}\}", r"\1", final_text)`.
- S1 prompt: "MUST keep verbatim, braces included."
- S4 revise prompt: "copy character-for-character."
- S5 Tier-1 disqualifier checks (after stripping braces from both sides) that each preserve token's content is present in the candidate.
- Judge prompt: do NOT penalize missing braces in S4/S5 — that's correct post-strip. Score on content survival.

### Pattern 2 — Unbraced English teaching tokens (pedagogical)
When `teaching_lang=English` is set (or pedagogical context detected):
- English vocab, quoted tokens (`'horse'`, `"freedom"`), grammar terms MUST stay in English (Latin script).
- Do NOT translate. Do NOT wrap with target-language gloss (unless `vocab_mode="bilingual"` is explicitly passed).
- **Default `vocab_mode` = `preserve`** (Phase 4 — was `bilingual` pre-Phase-4, which contradicted S4's preserve-only revise prompt).
- S3 LLM sieve has `*** PEDAGOGICAL CONTEXT ***` block telling it not to flag English teaching tokens as errors.
- Judge prompt: score 100 accuracy when English kept; penalize when translated.

### Pattern 3 — Delivered output
- Braces stripped (Pattern 1 content survives without braces).
- English teaching tokens in Latin script (Pattern 2).
- User-facing text NEVER contains `{{...}}` markers.

---

## 5. Audit / DB Changes (v10)

### New `stage_timings` fields
| Field | Value |
|---|---|
| `s5_decision` | `s1` / `s4_iter1` / ... |
| `s5_reason` | human explanation |
| `s5_scores` | `{candidate: negated_weight}` |
| `s5_disqualified` | `[(candidate, [reasons])]` |
| `s5_overrode_final` | bool |
| `s5_margin`, `s5_margin_key` | future per-lang threshold tuning |
| `l2_fixes` | list of applied L2 tags |
| `s4_output_accepted` | S4 intermediate text (used for 3-way scoring) |
| `initial_after_l2` | L2-modified initial (NULL when no L2 fix fired) |

### New `translations` table columns (Phase 4)
| Column | Type | Contents |
|---|---|---|
| `s4_intermediate` | TEXT | S4 loop output pre-S5 |
| `s5_picked` | TEXT | `'s1'` \| `'s4'` — coarse signal (fine-grained in `audit_json`) |
| `s5_accuracy` | INTEGER | Opus score of S5 delivered (bench scorer writes) |
| `s5_naturalness` | INTEGER | Opus score of S5 delivered (bench scorer writes) |

### Scorer 3-way output (Phase 4)
Both `bench_score.py` and `bench_score_neo.py` now send 4 candidates to Opus (S1 / S4 / S5 / HUMAN when available) and write:
- `s1_accuracy`, `s1_naturalness` (raw S1)
- `s4_accuracy`, `s4_naturalness` (S4-intermediate — NOT delivered)
- `s5_accuracy`, `s5_naturalness` (S5 delivered)
- `human_accuracy`, `human_naturalness`
- `neo_verdict` derived from S5 vs HUMAN

Pre-Phase-4 data has `s4_accuracy` column conflated with delivered — flag when reading old rows.

---

## 6. Model / Serving Topology

```
External → nginx :3101/3102 → translator :13102 → Python LB :13100
                                                       ├─→ ollama :13101 (GPU 1) — qwen3.6:35b-a3b-q3kxl
                                                       └─→ ollama :13104 (GPU 0) — qwen3.6:35b-a3b-q3kxl
```

- LB (`/home/csaptu/gpu_proxy/proxy.py`) routes per-request to least-loaded healthy backend that has the requested model.
- `_per_stage_call` in translate.py hardcodes `http://127.0.0.1:13100/api/chat` (hits the LB).
- Circuit breaker: 3 consec failures → backend marked unhealthy for 60s.
- Model swap: Qwen 3.5 → 3.6 (Phase 4). Smoke comparison: 3.6 wins 18%, 3.5 wins 8%, tie 74% over 280 apples-to-apples sentences.

---

## 7. File / Function Map (v10)

| File | Changed in v10 |
|---|---|
| `translate.py` | `s5_select_best`, `s5_disqualify_reasons`, `s5_score_candidate`, `_apply_l2_fixes`, `build_param_context` (vocab_mode preserve default + expanded 3-pattern prompt), `_with_context` (same), `_build_iteration_prompt` (pc dict threading from Phase 2) |
| `cache.py` | schema migration adds `s4_intermediate`, `s5_picked`, `s5_accuracy`, `s5_naturalness`; `put()` extracts `s4_output_accepted` + `s5_decision` from audit |
| `bench_score.py` | JUDGE_SYSTEM: 3-pattern rules, 3-way (S1/S4/S5) scoring |
| `bench_score_neo.py` | JUDGE_SYS: 3-pattern rules, 4-way (S1/S4/S5/HUMAN) scoring |
| `bench-method.md` | new § "Preservation Patterns", new § "Step 5 — S5 Deterministic Selector", new § "Required Per-Language Report Table", Type 2 section expanded |

---

## 8. Behavior Invariants (v10)

1. S5 never delivers a candidate with more critical+high errors than the S1 baseline (Tier 4 fallback guarantees floor).
2. L2 never modifies `s1_translation` column (raw pre-L2 S1 preserved for honest reporting).
3. Final delivered text has zero `{{...}}` markers (stripped at line 4645).
4. `vocab_mode=preserve` is the default for `teaching_lang` when caller doesn't specify.
5. Both scorer prompts explicitly describe the 3 patterns — apples-to-apples with pipeline behavior.

---

## 9. Out of Scope (future)

- Pattern 2 programmatic enforcement (S5 can't verify unbraced English preservation without metadata annotation).
- Per-content-type calibrated S5 thresholds from bench data (scaffolding: `S5_LANG_OVERRIDE` dict).
- Opus model upgrade (judge is claude-opus-4-7).
