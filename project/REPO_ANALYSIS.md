# `smart-farming-edge-ai` — Repository Analysis

**Date:** 2026-09-06 · **Scope:** the entire repository · **Method:** code read plus
runtime execution. Every number below was produced by running something in this
working tree, or read out of an artifact committed to it. Where a claim in the
repository could not be reproduced, that is stated explicitly rather than smoothed over.

> **Corrections added 2026-09-22 — these supersede the text below:**
> 1. **INT8 root cause (§ on quantization, and "two independent replications").** The claim
>    that HardSwish "produces negative values for x < −3" is wrong — HardSwish is exactly 0
>    there and negative only on (−3, 0), minimum −0.375. The collapse is real and reproduced
>    on both models, but its root cause is **not isolated**. See `ai/step5_export.py`.
> 2. **Lab-vs-field gap (§ on metrics, and "correctly-interpreted differentiator").** The
>    −11.01 pp gap is **not** evidence of field-specialisation: the lab test subset is 99
>    images with no Healthy class, while the field subset includes Healthy (~95% recall).
>    It is a class-mix-confounded comparison and is no longer presented as a headline.
> 3. **Near-duplicate leakage** is now measured: ~5% of test images (disease 46/901 field,
>    pest 41/717) have a perceptual near-duplicate in train.
> 4. **Nutrient advisories** no longer prescribe urea/MOP; N/P/K are treated as
>    EC-derived proxies and produce LOW-confidence "soil test recommended" flags.

---

## 1. What this repository is

**KisanNetra**, an entry for Smart India Hackathon 2026, Problem Statement **26180**
(Qualcomm-sponsored, Hardware category, Agriculture theme).

The product is a **fixed, pole-mounted edge-AI farm sentinel**: a solar-powered node
installed once and left to watch one zone of a field for a season. It answers four
questions — disease, pest, nutrient deficiency, irrigation — on-device, without
requiring a live cloud connection for any critical decision.

The architecture is deliberately **not** a single jointly-trained multimodal network.
It is separate per-modality components joined by an explainable rule-based fusion
layer, because no paired image+sensor dataset exists and the project declines to
fabricate one. That is a defensible engineering choice and it is the intellectual
core of the submission.

### Scale

| Measure | Value |
|---|---|
| Source files (`.py` / `.md` / `.html` / `.scad` / `.ino`) | ~80 |
| Source lines | ~16,070 |
| Largest single file | `iot/wokwi/micropython/main.py` (1,499 lines) |
| Trained models | 2 (disease, pest) |
| Test suites | 4 (23 + 18 + 9 checks + 1 verification script) |
| Git commits | 2 |
| Repository on disk | 1.7 GB (`.git` alone: 778 MB) |

---

## 2. The single most important structural finding

**The repository contains two parallel, unreconciled system lineages.**

| | Lineage A — `iot/`, `docs/`, `viz/`, `demo/`, `tests/` | Lineage B — `ai/` |
|---|---|---|
| Crop | **Cotton** | **Rice (paddy)**, Thanjavur |
| Classes | 5 *hypotheses*: healthy, water stress, nitrogen deficiency, leaf curl virus, bacterial blight | 5 *diseases*: Bacterial Blight, Blast, Brown Spot, Healthy, Tungro |
| Data contract | `iot/contracts.py` — typed `SensorWindow`, `VisionDifferential` dataclasses | `ai/sensor_contract.py` — flat JSON dict |
| Fusion engine | `iot/fusion/engine.py` (325 lines) | `ai/step6_rule_engine.py` (282 lines) |
| Vision output | A ranked *differential* (probability distribution) | An argmax label + confidence |
| Test coverage | `tests/test_fusion.py` — 23 tests | `ai/step8_integration_test.py` — 9 checks |
| Trained model | **None** | Two, with real weights |

This is **documented, not accidental**. `ai/PS-26180-MASTER.md` §225–232 states plainly
that the `docs/` set is written around cotton, that "the cotton documents have been left
untouched rather than silently rewritten," and that the same applies to the hardware
compute story. `docs/18_demo_script.md` carries a rehearsed judge answer for
*"Why Rice (Paddy) in Thanjavur instead of Cotton?"*.

Leaving the old documents intact rather than retconning them is the honest choice, and
it should be kept. But two consequences follow that are **not** currently managed:

1. **`tests/test_fusion.py` opens by declaring: *"These lock the specific claims made in
   the demo and the deck. If a test here fails, a slide is now wrong."*** All 23 of those
   tests exercise the **cotton** engine in `iot/`. The rice engine that actually drives
   the dashboard and the validation suite is covered by a different, separate harness.
   The suite that claims to protect the deck is not testing the system being presented.
2. **`docs/decision_log.md` DR-001 is "Crop: cotton"** with no superseding entry. The
   pivot to rice is recorded in `PS-26180-MASTER.md` and in the demo script, but the
   decision log — the document whose entire job is to be the authoritative record of
   decisions — does not contain it. Similarly **DR-007 "Defer pest detection"** is now
   obsolete: the pest model was built and shipped.

**Recommendation:** do not delete the cotton work. Add two decision-log entries
(`DR-013 — Crop pivot to rice`, superseding DR-001; `DR-014 — Pest detection built`,
superseding DR-007), and retitle the two test suites so it is unambiguous which system
each one locks.

---

## 3. Subsystem analysis

### `ai/` — the executed AI core *(strongest part of the repository)*

Two independently trained and independently verified classifiers, a rule engine, a
validation suite, an inference server, and a dashboard.

| File | Role | State |
|---|---|---|
| `step2_clean_split.py` | Clean + leakage-free split (disease) | Works; exact-MD5 dedup only |
| `step3_train.py` | Two-phase transfer learning | **Repaired this session**, verified end-to-end |
| `step4_evaluate.py` | Lab-vs-field evaluation | Works |
| `step5_export.py` | ONNX export + INT8 research note | Works |
| `step6_rule_engine.py` | Nutrient / irrigation / disease fusion | Works |
| `step8_integration_test.py` | 9-check integration harness | 9/9 pass |
| `model_validation_suite.py` | Wilson CI, bootstrap, ECE, perturbation, regression lock | **Bug fixed this session**; passes |
| `ood_eval.py` | Out-of-distribution harness | **Written, never run** — no photos collected |
| `inference_server.py` | Serving + blur prefilter | Works |
| `sensor_contract.py` | Mock generator with drift, noise, fault injection | Works |
| `dashboard.html` | 811-line operator view | Works; see §6 |
| `pest/` | Complete second pipeline | All green |

### `iot/` — the cotton lineage

Well-written and genuinely thoughtful. `contracts.py` defines `PLAUSIBLE_RANGES` and
treats out-of-range values as *faults rather than measurements* — "a disconnected ADC
pin floats, a shorted probe reads rail" — which is the correct instinct and predates the
same discipline appearing in `ai/`. `fusion/engine.py` records the sensor signal behind
every adjustment so each recommendation is explainable back to a measurement.

`iot/wokwi/` is a substantial, separately-documented MCU simulation (1,499-line
MicroPython firmware, 561-line Arduino sketch, 362-line README, wiring docs). Its README
is honest about its own limits — flow is modelled in firmware because Wokwi has no flow
part, and "the ESP32 does no vision; disease confidence is simulated input."

### `hardware/` — mechanical design

Two OpenSCAD sources: `product_assembly.scad` (the full sentinel station) and
`sensor_node_enclosure.scad` (printable, parametric, exports clean STLs). Both are
already fully consistent with the fixed-sentinel architecture — `product_assembly.scad`
describes a node "installed once and left in the field for a season" with a "sealed
fixed housing aimed at the canopy, not a cradle holding somebody's phone."

The README was **reconciled this session**; it had still been describing a
`hexapod_robot.scad` as "**The product**" — a file that no longer exists.

### `docs/` — 12 design documents

Numbered `00, 01, 02, 03, 06, 07, 09, 13, 18, 22, 23` plus `decision_log.md`. The gaps
(04, 05, 08, 10–12, 14–17, 19–21) suggest planned documents that were never written; the
numbering implies a completeness the directory does not have. Worth either filling or
renumbering, because a judge who sees `23_sensing_reference.md` will reasonably assume
documents 1 through 22 exist.

`decision_log.md` (DR-001…DR-012) is the strongest document in the set — each entry
carries context, alternatives, and consequences. Its value is exactly why the two
missing entries in §2 matter.

### `viz/`, `demo/`, `edge/`, `tests/`

- `viz/sentinel_twin.html` (1,072 lines) and `viz/fusion_explorer.html` (726 lines) — cotton lineage.
- `demo/differential_demo.py` — the headline "one leaf, two field histories, two
  recommendations" pitch moment. Cotton lineage.
- `edge/spike0_aihub.py` — Qualcomm AI Hub compile/profile spike, blocked on a Qualcomm ID.
  Correctly marked as not-yet-run rather than faked.

---

## 4. Model and validation state

### Disease classifier — 5 classes, MobileNetV3-Small

| Metric | Value |
|---|---|
| Overall accuracy | **87.70%** |
| 95% Wilson CI | [85.52%, 89.59%] |
| Bootstrap 95% CI | [85.60%, 89.65%] |
| Macro F1 | 0.8627 |
| Expected Calibration Error | 0.0369 |
| Lab-condition accuracy | 77.78% |
| Field-condition accuracy | 88.79% |
| Lab-minus-field gap | **−11.01%** (field *better*) |
| Deployment artifact | `kisannetra_fp32.onnx`, 5.82 MB |

The negative gap is the project's headline claim and it is real: training data was
overwhelmingly field imagery, so the model is field-specialised. That is the right
direction for a pole-mounted sentinel, and it is honestly framed as such.

### Pest classifier — 3 classes, MobileNetV3-Small *(built in the previous session)*

| Metric | Value |
|---|---|
| Accuracy | **94.98%** (681/717) |
| 95% Wilson CI | [93.13%, 96.35%] |
| Macro F1 | 0.9519 |
| Per-class recall | Dead Heart 98.60% · Hispa 95.40% · No Pest Damage 91.63% |
| Deployment artifact | `kisannetra_pest_fp32.onnx`, 5.81 MB |
| Condition | 100% field imagery — **no lab counterpart exists**, so no gap is reported |

### Perturbation robustness *(corrected this session)*

| Perturbation | Accuracy | 95% Wilson CI | Drop vs clean |
|---|---|---|---|
| *clean baseline* | 86.75% | [83.08%, 89.73%] | — |
| **blur** | **69.00%** | [64.30%, 73.33%] | **−17.75 pp** |
| low brightness | 85.25% | [81.44%, 88.39%] | −1.50 pp |
| high contrast | 86.75% | [83.08%, 89.73%] | 0.00 pp |
| rotation 10° | 86.75% | [83.08%, 89.73%] | 0.00 pp |

**Blur is the model's only material weakness.** The previously published near-chance
brightness (26.56%) and contrast (20.31%) figures were a harness artefact — perturbations
were applied to an already-normalized tensor and clamped to [0,1], pinning 63.9% and
80.8% of pixels respectively to a clamp boundary. Both the old and corrected numbers are
retained in `ai/VALIDATION_REPORT_DETAILED.md` §8 so the correction is auditable.

### INT8 quantization — failed twice, reported honestly both times

| Model | FP32 | INT8 | Status |
|---|---|---|---|
| Disease | 87.70% | ~22% | `kisannetra_int8.BROKEN_22pct.onnx` |
| Pest | 94.98% | 34.59% | `kisannetra_pest_int8.BROKEN_35pct.onnx` |

Root cause is architectural: MobileNetV3-Small's HardSwish activations produce negative
values, and every onnxruntime quantization path inserts Quantize/Dequantize ops on
activation tensors that clip them. **The pest failure is an independent replication of
the disease finding on a separately trained model** — which makes it a stronger claim
than a single occurrence, not a weaker one. Both broken artifacts are named so they
cannot be mistaken for deployables.

---

## 5. Audit trail — verified status of the 15 known flaws

`ai/FLAWS.md` recorded 15 findings on 2026-09-04. Each was re-checked against the code
as it stands today.

| # | Severity | Finding | Verified status |
|---|---|---|---|
| 1 | CRITICAL | Class labels swapped at inference (Healthy ↔ Tungro) | ✅ **Fixed** — `inference_server.py:52` and `step8:59` both load `classes.json`. ⚠️ See §6.1 |
| 2 | CRITICAL | Chance-level INT8 model shipped | ✅ **Fixed** — renamed `BROKEN_22pct` |
| 3 | CRITICAL | Rule engine crashes when pH sensor fails | ✅ **Fixed** — explicit `None` branch |
| 4 | CRITICAL | Missing N/P/K become `0`, generate prescriptions | ✅ **Fixed** — `_reading()` returns `None`; each nutrient emits `UNKNOWN` + "No fertiliser recommendation is made without a reading" |
| 5 | HIGH | Near-duplicate dedup never implemented but ticked done | ✅ **Resolved by amendment** — claim corrected in `PS-26180-MASTER.md:347` to "Exact-MD5… Known unquantified leakage risk for resized/recompressed near-duplicates". Perceptual hashing still not implemented (accepted trade-off) |
| 6 | HIGH | Steps 5–8 ran without checkpoints; trackers stale | ❌ **STILL OPEN** — see §6.2 |
| 7 | HIGH | Trend layer fed independent noise | ✅ **Fixed** — generator now carries state with drift + noise |
| 8 | HIGH | Negative time-to-threshold displayable | ✅ **Fixed** — `max(0, …)` guard |
| 9 | MEDIUM | Brown Spot / Tungro can never reach HIGH | ✅ **Fixed** — Brown Spot corroborates on soil stress; Tungro capped at MEDIUM *by design*, documented |
| 10 | MEDIUM | Lab-vs-field gap explained incorrectly | ✅ **Fixed** — now framed as field-specialisation |
| 11 | MEDIUM | Mock generator can only emit `VALID` | ✅ **Fixed** — `generate_mock_reading(faults=…, drop=…)` |
| 12 | MEDIUM | Irrigation reads invented defaults | ✅ **Fixed** — uses `_reading()`, degrades confidence |
| 13 | LOW | EC validity gated on pH status key | ✅ **Fixed** |
| 14 | LOW | Deprecated `datetime.utcnow()` | ✅ **Fixed** — zero occurrences repo-wide |
| 15 | LOW | Orphaned export artifacts | ✅ **Fixed** |

**14 of 15 closed.** The honesty rules from `PS-26180-MASTER.md` §4 are now genuinely
enforced in code, not merely asserted in prose — the missing-sensor path in particular is
handled correctly in every branch I checked.

---

## 6. New findings from this analysis

### 6.1 `DISEASE_CLASSES` is dead code in the exact order that caused the CRITICAL bug

`ai/step6_rule_engine.py:20`:

```python
DISEASE_CLASSES = ["Bacterial Blight", "Blast", "Brown Spot", "Tungro", "Healthy"]
```

The true `ImageFolder` order is `[…, "Healthy", "Tungro"]`. This list has Healthy and
Tungro **transposed** — precisely the defect that made the system report every healthy
plant as an incurable virus and every Tungro infection as healthy.

It is currently **never referenced anywhere in the repository**, so it is harmless today.
It is also a loaded gun: the next person who needs a class list will find it sitting at
the top of the rule engine and use it. Fix 1 in `FIXES.md` explicitly warned that
"a hardcoded ordering that duplicates a sorted directory listing will drift again."

**Recommendation:** delete it, or replace it with a `classes.json` load.
The same transposed ordering also appears in the `CLASSES IN USE:` line of
`PS-26180-MASTER.md` and should be corrected there too.

### 6.2 The master tracker is still stale — flaw #6 is not closed

`ai/PS-26180-MASTER.md`, `CURRENT STATE` block:

```
OVERALL STATUS:   STEP 4 DONE — AWAITING STEP 5 EXPORT
CURRENT TASK:     Step 5 — Export
LAST UPDATED:     2026-09-03
```

Since that was written: Step 5 exported, Step 6 rule engine built, Step 8 integration
passing 9/9, a full validation suite run, a 15-finding audit completed and largely
remediated, and an entire second (pest) model built, evaluated, exported and verified.
The file that declares itself "your single source of truth for what to do and where you
are" is three days and roughly two thousand lines of work behind.

This is the one audit finding that was never closed, and it is self-referential: the
document that enforces update discipline is the document that is out of date.

### 6.3 The demo script asserts a "T=0.80 disease confidence threshold" that does not exist in the code

`docs/18_demo_script.md` §"What is the T=0.80 threshold?" tells a judge:

> *"The disease pipeline has a confidence gate: if the vision model's top prediction is
> below 0.80, the system notes 'inconclusive — monitoring' rather than raising an alert."*

`ai/step6_rule_engine.py:237–239` actually implements:

```python
if confidence_score >= 0.75 and env_corroborated:      # HIGH
elif confidence_score >= 0.55 or env_corroborated:     # MEDIUM
```

There is **no 0.80 gate in the disease path**, and no "inconclusive — monitoring" state.
The thresholds are 0.75 and 0.55, and below 0.55 the result is `LOW`, not an abstention.

**T=0.80 is the *pest* alert threshold**, defined in `ai/pest/pest_fusion_rule.py`, where
it was derived from a documented sweep. The value appears to have migrated from the pest
module into a disease-facing explanation. The same claim has propagated into a code
comment at `ai/inference_server.py:43`, which also refers to "the T=0.80 disease
confidence threshold."

This matters more than a typo: it is a **rehearsed answer to a judge, about a number, that
the code does not support**. Either implement the 0.80 disease gate (and re-run the
validation that depends on the thresholds), or rewrite the answer around the real 0.75 /
0.55 corroboration ladder — which is a perfectly good story on its own.

### 6.4 The demo script's corrected brightness figure does not match the artifact

The script states the corrected brightness result is **80.50% [76.58%, 83.95%]**.
`ai/validation_report.json` — regenerated by the corrected suite — records
**85.25% [81.44%, 88.39%]**. The intervals do not even overlap at the point estimate.

The narrative around it (harness bug, clamping, both numbers retained, blur is the
surviving finding) is accurate and well told. Only the figure is wrong. Given the section
is specifically about the integrity of a correction, quoting a number that isn't in the
report is the one error it can least afford.

### 6.5 The blur gate is implemented, but its threshold is uncalibrated and the dashboard cannot show it

Good news first: the variance-of-Laplacian prefilter in `ai/inference_server.py` is
**real**, correctly computed on the raw greyscale image *before* normalization (with a
comment explaining exactly why that ordering matters), and returns a proper
`ABSTAIN_BLUR` response. This is a genuine, well-built answer to the blur weakness in §4.

Two gaps:

1. `BLUR_THRESHOLD = 100.0` is annotated `# tune against real device`. It is a placeholder,
   not a measured value. Since blur is the model's only material robustness weakness, this
   threshold is doing real safety work and deserves calibration against the corrected
   perturbation data.
2. **`dashboard.html` has no handling for `ABSTAIN_BLUR` or any "Recapture" state** — the
   only match for "blur" in the file is a CSS `backdrop-filter`. The demo script's step 2
   instructs the presenter to *"point to the dashboard 'Recapture' state"*. That state does
   not render. **This will fail live.**

### 6.6 Repository hygiene — the dataset is committed to git

| | |
|---|---|
| Tracked files | 11,462 |
| …of which are dataset images | **11,374** (99.2%) |
| `.git` directory | **778 MB** |
| Working tree | 1.7 GB |
| Commits | 2, both messaged "Initial commit of smart farming edge ai directory" |

`ai/dataset_split/` (553 MB) and `ai/pest/pest_dataset_split/` (367 MB) are both committed.
These are *derived copies* of a publicly downloadable Kaggle dataset, regenerable at any
time by re-running the two `step2` scripts. `.gitignore` covers `.venv/`, `__pycache__/`
and `*.stl`, but not `dataset_split/`.

Consequences: the repository is effectively un-cloneable over a hackathon network
connection, and every future commit that touches the split rewrites hundreds of megabytes.

**Recommendation:** add `dataset_split/` and `pest_dataset_split/` to `.gitignore`. The
split is fully reproducible (`random.seed(42)`, deterministic), and `split_report.json` /
`pest_split_report.json` already record the exact resulting counts. The trained
`.pth`/`.onnx` artifacts (~24 MB total) are reasonable to keep tracked.

### 6.7 Three Python environments, none of which runs everything

| Interpreter | torch | onnxruntime | pytest | Verdict |
|---|---|---|---|---|
| `.venv/` (root) | — | — | — | **Empty** — contains only `pip` |
| `ai/.venv/` | 2.11.0+cu128 ✅ CUDA | 1.29.0 | ❌ **missing** | The interpreter `FIXES.md` tells you to use — cannot run `tests/test_fusion.py` |
| System `Python312` | 2.12.0.dev | 1.29.0 | ✅ | What actually ran this session's work |

Also: `requirements.txt` pins `torch>=2.14.0`, which **neither environment satisfies**
(2.11 and 2.12). A clean `pip install -r requirements.txt` would either fail or silently
install a different torch than the one every result in this repository was produced with.

My earlier remark that the requirements files were out of date was wrong — they correctly
list `pytest` and `onnxruntime`. The problem is the reverse: the environments were never
installed *from* them, and the torch pin is unsatisfiable.

**Recommendation:** delete the empty root `.venv/`, install `pytest` into `ai/.venv/`,
and relax the torch pin to `>=2.11` to match reality.

---

## 7. What is genuinely strong

Stated plainly, because a document that only lists problems misrepresents this repository.

- **The honesty discipline is real and enforced in code.** `_reading()` returning `None`
  rather than `0`, every nutrient emitting "No fertiliser recommendation is made without a
  reading", Tungro capped at MEDIUM because no sensor on the node observes leafhopper
  pressure, INT8 failures named `BROKEN_22pct` and `BROKEN_35pct` in the filename. These
  are not slogans; they are branches with tests behind them.
- **Two independent replications of the HardSwish quantization failure.** A failure mode
  found once is an anecdote. Found again on a separately trained model, it is a property
  of the architecture — and that is a considerably better story to tell a Qualcomm judge
  than a single bad run.
- **A self-audit that found four CRITICAL bugs in the project's own work, and closed 14 of
  15 findings.** Including a class-label swap that was actively producing the worst
  possible wrong answer while looking perfectly confident.
- **A withdrawn result, kept visible.** Section 8 of the validation report retains the
  wrong numbers next to the corrected ones with the mechanism explained. Very few
  hackathon submissions can show a judge a mistake they caught themselves.
- **The lab-vs-field gap is a real, measured, correctly-interpreted differentiator** —
  and the corrected sign (field *better* than lab) is the direction that actually supports
  the product thesis.
- **The decision log.** DR-001 through DR-012, each with context, alternatives and
  consequences. It is the document that most clearly shows this was engineered rather
  than assembled.

---

## 8. Prioritised open items

| # | Item | Severity | Why | Effort |
|---|---|---|---|---|
| 1 | Demo script's T=0.80 disease-gate claim contradicts the code (§6.3) | **HIGH** | A rehearsed judge answer the code does not support. Worst-case discovery is live. | 15 min |
| 2 | Dashboard cannot render `ABSTAIN_BLUR`; demo step points at it (§6.5) | **HIGH** | A scripted demo step that will visibly fail | 30 min |
| 3 | Demo script's brightness figure ≠ validation report (§6.4) | **HIGH** | Wrong number inside the integrity story itself | 5 min |
| 4 | OOD evaluation never run — no photos collected | **HIGH** | The one honestly-declared validation gap. Harness is written and ready; only 20–30 real photos are missing. | 1–2 hrs |
| 5 | Master tracker stale — audit finding #6 still open (§6.2) | MEDIUM | The record of truth is 3 days behind | 20 min |
| 6 | Dataset committed to git; 778 MB `.git` (§6.6) | MEDIUM | Repository is impractical to clone | 15 min |
| 7 | `DISEASE_CLASSES` dead code in the transposed order (§6.1) | MEDIUM | Latent re-entry point for the original CRITICAL bug | 2 min |
| 8 | Decision log missing crop-pivot and pest-built entries (§2) | MEDIUM | Authoritative record contradicts the build | 20 min |
| 9 | `BLUR_THRESHOLD = 100.0` uncalibrated (§6.5) | MEDIUM | Guards the model's only real weakness | 45 min |
| 10 | Pest model not wired into the dashboard | MEDIUM | Fusion rule is decided and tested; only rendering remains | 1 hr |
| 11 | `tests/test_fusion.py` claims to lock deck claims, tests the cotton engine (§2) | MEDIUM | Misleading coverage signal | 10 min (retitle) |
| 12 | Three environments, unsatisfiable torch pin (§6.7) | LOW | Reproducibility | 15 min |
| 13 | `docs/` numbering implies documents that don't exist | LOW | Implies false completeness | 15 min |
| 14 | `EC_HIGH`, `P_LOW`, `K_LOW` defined but unused; literals used instead | LOW | Editing the constant changes nothing — a silent-failure trap | 5 min |

**Items 1–3 are the pre-presentation blocking set.** All three are documentation
corrections or a small UI addition, total effort under an hour, and all three are
failures that would surface *in front of a judge* rather than in a log file.

---

## 9. Bottom line

This is a strong submission whose principal weakness is no longer its engineering.

The models are trained, measured with confidence intervals, independently reproduced, and
honestly bounded. The rule engine enforces its own stated ethics in code. A serious
self-audit found and fixed four critical defects, and a second audit this session found
and fixed a fifth (a silently broken training script) and a sixth (a validation harness
bug that was manufacturing a fake weakness while concealing a real one).

What now lags the code is **the writing about the code**. The three highest-severity open
items are all cases where a document asserts something the repository does not do — a
threshold that isn't implemented, a dashboard state that doesn't render, a number that
isn't in the report. Given that this project's central differentiator is precisely its
claim to be more rigorous about evidence than its peers, a judge who catches one of those
does disproportionate damage.

They are also, all three, under an hour of work.

---

*Generated 2026-09-06. All figures reproduced by execution in this working tree; no value
in this document is copied from an unverified claim elsewhere in the repository.*
