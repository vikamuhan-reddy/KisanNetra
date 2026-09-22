# KisanNetra — The Project, End to End

**SIH 2026 · Problem Statement 26180 · Qualcomm-sponsored · Hardware category**
Theme: Agriculture, FoodTech & Rural Development

A complete walkthrough: what the system is, why it was built this way, how every piece
works, what it actually achieves, and what it deliberately does not claim.

---

## Table of contents

1. [The problem](#1-the-problem)
2. [What the product is](#2-what-the-product-is)
3. [The central idea](#3-the-central-idea)
4. [How the design got here](#4-how-the-design-got-here)
5. [Hardware architecture](#5-hardware-architecture)
6. [The four problems, and how each is answered](#6-the-four-problems-and-how-each-is-answered)
7. [The AI pipeline, step by step](#7-the-ai-pipeline-step-by-step)
8. [What the models achieve](#8-what-the-models-achieve)
9.  [The fusion layer](#9-the-fusion-layer)
10. [The abstain doctrine](#10-the-abstain-doctrine)
11. [The honesty discipline](#11-the-honesty-discipline)
12. [The MCU simulation](#12-the-mcu-simulation)
13. [Repository map](#13-repository-map)
14. [How to run everything](#14-how-to-run-everything)
15. [Current state](#15-current-state)
16. [How to present it](#16-how-to-present-it)

---

## 1. The problem

PS 26180 asks for a field-deployable system that detects **crop disease, pests, nutrient
deficiency, and irrigation need** early, using **on-device edge AI**, working **without
continuous cloud access**.

That last clause is the whole problem. A smallholder plot in the Cauvery delta does not
have reliable connectivity, and a farmer will not carry a laptop into standing water to
photograph leaves. Any design that needs a live network link for a critical decision has
already failed the brief.

**Scope chosen:** rice (paddy), Thanjavur, Tamil Nadu.

---

## 2. What the product is

**A fixed, pole-mounted, solar-powered field sentinel.** Installed once at the start of
a season and left alone. It watches one zone of one field. Nobody visits it, nobody
holds a phone to a leaf, nobody presses anything.

It does not move. There are no wheels, no tracks, no legs, no navigation. Coverage is
extended by installing more nodes, not by moving one — which is also what makes the unit
economics work.

```
                    ┌─ camera + sun hood, aimed 35° down at the canopy
                    │
       ┌────────────┴─────────────┐
       │  sealed electronics bay  │ ← ESP32 (always on) + QCS6490 (off by default)
       └────────────┬─────────────┘
                    │              ← 10–20 W tilted solar panel, LiFePO4 cell
                    │  mast
   ═════════════════╪═══════════════════  ground line
                    ├── surface moisture probe   ~100 mm
                    │
                    └── root-zone moisture probe ~300 mm
```

The two probe depths are not decoration. One reports what the surface did after
irrigation or rain; the other reports what the root zone actually holds. A single probe
confuses *"I watered the top"* with *"the plant can drink"* — and that is exactly the
distinction the whole fusion engine depends on.

---

## 3. The central idea

Most crop-disease projects are a classifier with a camera. This one is built on a
sharper observation:

> **A camera sees symptoms, not causes.**

Rice leaf discoloration is genuinely ambiguous. Brown Spot, early Blast, and nitrogen
deficiency produce visually similar lesions. A model at 60% confidence on Blast might
be seeing early fungal signs — or it might be seeing nutrient stress. Acting on that
call puts a farmer on a fungicide they may not need, which costs money and does nothing.

**No larger vision model fixes this**, because the information required to separate the
causes is not in the frame. A three-day soil-moisture trend is.

So the architecture is deliberately **not** a single jointly-trained image+sensor
network. It is separate per-modality components joined by an **explainable rule-based
fusion layer**:

```
   camera ──► vision model ──┐
                             ├──► rule-based fusion ──► advisory + the reason for it
   soil/air sensors ─────────┘
```

Two consequences follow, and both are deliberate:

- **No paired dataset is needed.** No image+sensor corpus exists for Thanjavur paddy, and
  the project refuses to fabricate one.
- **Every recommendation can be explained back to a measurement.** A farmer-facing
  recommendation that cannot be explained should not be shown.

---

## 4. How the design got here

The repository preserves its own wrong turns rather than retconning them. This is worth
knowing because a judge may read the older documents.

| Phase | What changed | Why |
|---|---|---|
| **Crop: cotton → rice** | `docs/` is written around cotton; `ai/` is built for rice | A rice dataset (Paddy Doctor + a Mendeley lab set) offered a clean, provable separation between lab and field imagery — which is what makes the lab-vs-field gap measurable rather than asserted |
| **Compute: phone → two-tier station** | A Snapdragon phone was recommended, then withdrawn | *"A phone is not autonomous hardware."* It must be placed and retrieved by a person, is not weather-sealed, cannot survive a season, and cannot trigger its own captures |
| **Form: brief mobile-robot detour** | A walking platform was designed, then removed | Ended by written specification. The product is a fixed sentinel |
| **Pest: deferred → built** | DR-007 deferred pest detection; it was later built | The two pest classes turned out to be sitting inside the dataset already downloaded for the disease model — no new data, no new licensing question |

The cotton documents were **left untouched rather than silently rewritten**, and the
demo script carries a prepared answer for *"why cotton?"*. That is the honest handling.

---

## 5. Hardware architecture

### Two tiers, because one tier cannot work

| Tier | Power | Role | Part |
|---|---|---|---|
| **Sentinel** | Always on, milliwatts | Reads soil and air sensors every 15 min, keeps a rolling window, decides when a capture is warranted, switches the compute rail | ESP32-class MCU + LoRa |
| **Compute** | **Off by default** | Wakes on the sentinel's trigger, captures, runs inference, fuses, transmits, powers down | Qualcomm QCS6490 (RB3 Gen 2 class) |

### Why the SoC is off by default

This is the number that decides the architecture:

| Configuration | Daily energy | Implied hardware |
|---|---|---|
| SoC always on (6 W assumed) | **144 Wh/day** | 60–80 W panel, 300 Wh battery, guyed mast |
| SoC duty-cycled, 4 × ~85 s sessions | **~0.8 Wh/day** *(est.)* | 10–20 W panel, 40–50 Wh LiFePO4 |

An always-on application SoC costs several times more in panel and battery than the
compute itself. **Autonomy is not a feature bolted on — it is what makes the bill of
materials possible.**

### The elegant part

The sentinel's wake triggers are the *same* stress conditions the fusion engine reasons
about — soil moisture crossing a stress threshold, a drying trend steepening, scheduled
dawn and mid-morning captures for comparable illumination. **Power optimisation and
diagnostic logic turn out to be the same rule set.** That is why this is a design rather
than a hack.

### Why two processors at all

A Qualcomm Linux SoC exposes I²C, SPI, UART, PCIe, USB and MIPI — but **no user analog
input**. Capacitive soil moisture probes are analog. An ESP32 reads them natively. The
sensor tier is required regardless of which compute node is chosen, so the design starts
from that rather than bolting on an ADC.

It also maps onto the scaling requirement in the PS itself: one shared compute node per
cooperative plus inexpensive sensor nodes per plot. **The hardware topology is the
business model.**

---

## 6. The four problems, and how each is answered

| Problem | Method | Status |
|---|---|---|
| **Disease** | Trained vision classifier, 5 classes | ✅ Built, validated |
| **Pest** | Second independent vision classifier, 3 classes | ✅ Built, validated |
| **Nutrient deficiency** | Rule-based on soil chemistry | ✅ Built, tested |
| **Irrigation** | Rule-based on moisture, tank, rain, flow | ✅ Built, tested |

Each problem has **detection** (present risk from current values) and **early warning**
(trend / rate-of-change toward a threshold). A plain threshold alert is never labelled an
"AI prediction" — that term is reserved for an actual trend calculation.

---

## 7. The AI pipeline, step by step

Two parallel pipelines with identical discipline. The pest pipeline was built second,
deliberately mirroring the disease pipeline rather than extending it.

### Why two models instead of one 8-class model

Pest damage (insect feeding scars, dead tillers) and fungal/bacterial lesions are
different visual tasks. Keeping them separate also means the pest model can be added,
retrained or replaced without touching a validated disease model.

### Step 1 — Data inventory

**Disease.** Two sources, deliberately different in character:
- A Mendeley rice-disease set — **lab** conditions, controlled lighting
- **Paddy Doctor** — real Tamil Nadu **field** imagery

Keeping these separable is the entire basis of the lab-vs-field claim.

**Pest.** Two classes already present in the *same* Paddy Doctor download:

| Class | Raw | Duplicates removed | Usable |
|---|---|---|---|
| Hispa | 1,594 | 5 | 1,589 |
| Dead Heart | 1,442 | 13 | 1,429 |
| No Pest Damage | 1,764 | 15 | 1,749 |

> **A design decision worth defending:** `No Pest Damage` was added as a third class. A
> Hispa-vs-Dead-Heart-only model has no way to say *"nothing here"* — it would label every
> healthy leaf as one of the two pests. It draws from the same `normal` folder the disease
> model's `Healthy` class uses, so it adds no new data source.

### Step 2 — Clean and split

- MD5 deduplication across the whole corpus
- 70/15/15 split **per class, per source**, so no image can appear in two splits
- Source provenance is baked into every filename (`lab_0001.jpg` / `field_0001.jpg`),
  which is what makes the lab-vs-field metric computable later
- Deterministic (`random.seed(42)`) — the split is fully reproducible

### Step 3 — Training

MobileNetV3-Small, ImageNet weights, two phases:

1. **Frozen backbone**, one warm-up epoch — trains only the new classifier head
2. **Full fine-tune**, 4 epochs at lr 1e-4 — best-validation checkpoint is kept

The class order is decided by `ImageFolder`'s alphabetical sort and is **persisted to
`classes.json` beside the weights**, so no downstream file ever has to guess it. This is
not incidental — see §11.

### Step 4 — Evaluation

Overall accuracy, **95% Wilson confidence interval**, macro F1, per-class precision and
recall, confusion matrix, and the lab-vs-field split.

### Step 5 — Export

FP32 ONNX (~5.8 MB) is the deployment artifact. INT8 was attempted on both models and
failed on both — see §8.

### Step 6 — Rule engine

Nutrient, irrigation and disease-fusion logic. No training involved. See §9.

### Step 7/8 — Verification

- **Independent reproduction**: loads the exported ONNX and the class list from JSON, with
  preprocessing re-implemented from PIL+numpy rather than reusing the training transforms,
  so a bug in that shared pipeline cannot hide by being on both sides of the check
- **Integration test**: 10 end-to-end checks, including the blur prefilter
- **Validation suite**: Wilson + bootstrap intervals, calibration error, perturbation
  robustness, rule-engine scenarios, and a regression lock on class ordering

---

## 8. What the models achieve

### Disease classifier — 5 classes

`Bacterial Blight · Blast · Brown Spot · Healthy · Tungro`

| Metric | Value |
|---|---|
| Test accuracy (n=1,000) | **87.70%** |
| 95% Wilson CI | [85.52%, 89.59%] |
| Bootstrap 95% CI | [85.60%, 89.65%] |
| Macro F1 | 0.8627 |
| Expected Calibration Error | 0.0369 |
| Lab-condition accuracy (n=99, 4 classes) | 77.78% |
| **Field-condition accuracy** (n=901, 5 classes) | **88.79%** |
| Lab-minus-field gap | −11.01 pp *(not a like-for-like comparison — see below)* |

**Read the lab-vs-field numbers with care.** The two subsets are not comparable as they
stand: the lab test set is small (99 images) and has **no Healthy class**, while the field
set includes Healthy, the model's easiest class (~95% recall). The raw gap therefore mixes
a real condition effect with a class-mix effect, and **we do not claim from it that the
model is "field-specialised"**. What it does show is that the headline 87.7% is dominated by
field images (90% of the test set), which is the condition the device will actually see.
A fair comparison — per-class accuracy on the four classes both sources share — is the next
evaluation step.

**Leakage check.** Deduplication was exact-MD5 only. A perceptual-hash scan of the test
split against the training split found about 5% near-duplicates (disease 46/901 field
test images, highest in Brown Spot at 13%; pest 41/717, highest in Hispa at 11%). The
headline figures are therefore slightly optimistic; re-reporting with those images
removed is queued.

### Pest classifier — 3 classes

`Dead Heart · Hispa · No Pest Damage`

| Metric | Value |
|---|---|
| Test accuracy (n=717) | **94.98%** (681/717) |
| 95% Wilson CI | [93.13%, 96.35%] |
| Macro F1 | 0.9519 |
| Recall — Dead Heart | 98.60% |
| Recall — Hispa | 95.40% |
| Recall — No Pest Damage | 91.63% |

Confusion is almost entirely Hispa ↔ No Pest Damage — expected, since early hispa
scarring is visually subtle. All imagery is field-condition, so **this model reports no
lab-vs-field gap**, and says so rather than leaving the absence unexplained.

### Robustness (n=400, clean baseline measured on the same sample)

| Perturbation | Accuracy | 95% CI | Drop |
|---|---|---|---|
| *clean baseline* | 86.75% | [83.08%, 89.73%] | — |
| **blur** | **69.00%** | [64.30%, 73.33%] | **−17.75 pp** |
| low brightness | 85.25% | [81.44%, 88.39%] | −1.50 pp |
| high contrast | 86.75% | [83.08%, 89.73%] | 0.00 pp |
| rotation 10° | 86.75% | [83.08%, 89.73%] | 0.00 pp |

**Blur is the only material weakness**, and the system has a hardware-level answer for it
(§10). An earlier version of this table reported near-chance brightness and contrast
figures; that was a bug in the test harness, not the model, and the withdrawn numbers are
retained alongside the corrected ones in the validation report.

### Speed

**2.5 ms median** per inference, p95 5.1 ms, on desktop CPU (FP32 ONNX, 224×224).

### INT8 quantization — failed twice, reported both times

| Model | FP32 | INT8 | Artifact |
|---|---|---|---|
| Disease | 87.70% | ~22% | `kisannetra_int8.BROKEN_22pct.onnx` |
| Pest | 94.98% | 34.59% | `kisannetra_pest_int8.BROKEN_35pct.onnx` |

**Root cause: not yet isolated — and we corrected our own earlier explanation.** Five
onnxruntime post-training schemes were tried on the disease model, all landing between 22%
and 36%. An earlier version of this document blamed HardSwish "producing negative values
for x < −3". That was wrong: HardSwish(x) = x·ReLU6(x+3)/6 is exactly 0 for x ≤ −3 and
is negative only on (−3, 0), with a minimum of −0.375. MobileNetV3 is known to be hard to
post-training-quantize; the suspected factors are depthwise convolutions quantized
per-tensor, squeeze-excite gating, HardSwish's small negative lobe losing resolution, and
calibration coverage.

**What we can say with evidence:** the pest model reproduced the collapse independently,
on separately trained weights. Found twice on two models, it is a property of
*MobileNetV3 + this post-training recipe*, not one bad checkpoint.

**Next steps, in order (future integration):** Qualcomm AI Hub's own quantizer
([`edge/QUALCOMM_AIHUB_GUIDE.md`](edge/QUALCOMM_AIHUB_GUIDE.md)); per-channel weights with
SE/HardSwish layers kept in higher precision; quantization-aware training; or a ReLU-based
backbone (MobileNetV2 / EfficientNet-Lite0). Whether Qualcomm's toolchain avoids the
collapse is **untested** until that run.

Both broken files are named `BROKEN` on disk so they cannot be mistaken for deployables.

---

## 9. The fusion layer

`ai/step6_rule_engine.py` and `ai/pest/pest_fusion_rule.py`. No training — this is
explicit, auditable logic.

### The governing principle

> **Visual confidence alone can never reach HIGH risk.**

A confident camera prediction reaches MEDIUM: *"investigate, do not treat yet."* HIGH
additionally requires **environmental corroboration** from the sensor layer.

| Condition | Corroborator | Ceiling |
|---|---|---|
| Bacterial Blight | Humidity ≥ 80% **and** temp 25–35 °C | HIGH |
| Blast | Humidity ≥ 85% **and** temp 24–32 °C | HIGH |
| Brown Spot | Low nitrogen **or** low root moisture (tracks nutrient/water stress, not humidity) | HIGH |
| **Tungro** | **None** | **MEDIUM** |
| **Hispa** | Soil nitrogen above `N_HIGH` — lush foliage favours leaf-pest pressure | HIGH |
| **Dead Heart** | **None** | **MEDIUM** |

**The two MEDIUM caps are the most defensible thing in the system.** Tungro is
insect-vectored; Dead Heart is caused by yellow stem borer. **No sensor on this node
observes leafhopper or stem-borer pressure.** So HIGH is unreachable for both —
*by design, documented, and tested* — rather than by accident. The node states in its own
output why it is capped.

### Combining the two channels

Disease and pest remain **two independent verdicts**. Nothing is averaged into a combined
score — they answer different questions about the same image, and a blended number could
not be explained to a farmer or a judge.

The disagreement case is handled explicitly: *"Disease: Healthy, Pest: Hispa"* is **not**
a contradiction. The disease model has no pest class and cannot represent feeding damage.
The pest channel is authoritative on pest questions. When both channels fire, the farmer
gets **one** advisory naming both — because they make one trip to the field.

### Nutrient and irrigation rules

Thresholds tuned for Thanjavur paddy: pH 5.5–7.0, EC > 2.0 dS/m for salinity, N 30–60
mg/kg, P > 12, K > 25, surface moisture 22%, root-zone 16%, tank critical at 20%.

**N, P and K are proxies, and the advisories say so.** Low-cost RS485 NPK probes estimate
these from conductivity; they are not ion-selective measurements. So an out-of-range
N/P/K reading produces a **LOW-confidence "possible shortage — soil test recommended"**
flag, never a fertiliser prescription (no "apply urea", no "apply MOP"). This is rule 4 of
§11 applied to our own sensor, not just to missing ones.

Ordering matters: **supply outranks crop stress.** If the tank is below critical,
irrigation is *blocked* mid-cycle regardless of how thirsty the crop is — a pump run dry
destroys itself in minutes.

---

## 10. The abstain doctrine

The system's most distinctive behaviour is **declining to answer**.

> *An inconclusive frame is a deferred capture, not a missed detection.*

This is only true because the node is a **fixed** sentinel photographing the same plants
on a cycle. The next frame is seconds away. That single architectural fact is what makes
abstaining cheap — and it is why the sentinel form factor and the abstain policy are the
same decision.

### Gate 1 — Blur prefilter (hardware level)

Every incoming frame gets a **variance-of-Laplacian** score, computed on the raw
greyscale image *before* normalization. Below threshold, the server returns
`ABSTAIN_BLUR` and **the image never reaches the classifier at all.**

Measured live on a real frame: sharp **2073.4** → classified. The same frame after heavy
Gaussian blur: **9.6** → rejected. Threshold 100.0.

### Gate 2 — Confidence threshold (pest channel, T = 0.80)

Chosen from a sweep, not by feel. The question that matters to a farmer is not "what is
the accuracy" but "how often does a healthy leaf raise a false pest alert":

| Threshold | False alerts on healthy | Pest recall | Inconclusive |
|---|---|---|---|
| 0.00 (raw) | **8.37%** | 96.92% | 0% |
| 0.70 | 5.32% | 93.39% | 6.6% |
| **0.80** | **3.04%** | **90.31%** | **11.2%** |
| 0.90 | 0.76% | 83.70% | 18.8% |

The raw model raises a false alert on roughly **one healthy leaf in twelve** — too high
to trust, and false alerts are what erode a farmer's confidence in a system. T=0.80 cuts
that 2.75× for 6.6 points of recall. T=0.90 was rejected: 13 points of recall is too much
to pay once false alerts are already at 3%.

### Gate 3 — Sensor fault handling

A failed or absent sensor is **never** replaced with a zero or a guess:

```python
def _reading(sensor, key, status_key=None):
    """A reading, or None. Never a substituted value.

    A missing value is a fault to be reported, not a number to reason
    with — 0 mg/kg nitrogen reads as a severe deficiency and generates a
    fertiliser prescription from an absent wire.
    """
```

The dependent rule reports `UNKNOWN` with **MANUAL CHECK RECOMMENDED**, and confidence on
every dependent decision drops.

---

## 11. The honesty discipline

The project's stated identity is that it is more careful about evidence than its peers.
That claim is only worth making if it is enforced in code, and it is.

### The absolute rules

1. Never present a simulated number as measured.
2. Never call software INT8 results "Qualcomm accelerated", "Hexagon", or "NPU" — they are
   **software-only validation**.
3. Never replace a missing or failed sensor value with zero or a guess.
4. Never invent a fertiliser prescription that no defined agronomic rule supports.
5. Never claim an IP rating that has not been tested — say "designed for outdoor
   environmental protection".

### These are enforced, not just asserted

- `_reading()` returns `None`, and every nutrient branch handles it explicitly
- Broken INT8 models carry `BROKEN` **in the filename**
- Tungro and Dead Heart are structurally incapable of reaching HIGH
- Class order is loaded from `classes.json`, never hardcoded
- Two tests exist specifically to prove a faulted probe and an absent reading cannot
  escalate an alert

### The project audited itself and published the results

`ai/FLAWS.md` records a 15-finding audit of the project's own work, including four
CRITICAL bugs. **14 of 15 are now closed.** The most serious:

> **Class labels were swapped at inference.** A hardcoded `CLASSES` list had Healthy and
> Tungro transposed relative to `ImageFolder`'s alphabetical sort. Every healthy plant was
> reported as **Tungro** — an incurable insect-vectored virus whose response is to destroy
> infected plants — and every actual Tungro infection was reported as **Healthy**.
>
> This is the worst available failure direction: the model was right and the label was
> wrong, so nothing in the confidence score signalled a problem. The fix was to delete
> every hardcoded list and load the order from an artifact written at training time.

A second audit later found the perturbation harness bug described in §8 — which was
*manufacturing a fake weakness (brightness) while concealing a real one (blur)*.

**Showing a judge a mistake you caught yourself is stronger than showing no mistakes.**

---

## 12. The MCU simulation

`iot/wokwi/` — runnable ESP32 firmware for the always-on sentinel tier, wired up in
[Wokwi](https://wokwi.com). Two variants that behave identically (all ten agronomic
constants verified equal):

| Variant | Sensors | Networking |
|---|---|---|
| **Arduino C++** | 6 channels | none — modelled |
| **MicroPython** | **12 channels** | **live MQTT** |

**This firmware does not run a CNN and does not pretend to.** Vision confidence is an
*input* — from a potentiometer or pushed over serial — exactly as it is on the real
board, where the QCS6490 returns a result over UART. That is the honest representation,
and it is the interface a judge will ask about.

The Python reference engine, the MicroPython firmware and the C++ firmware are three
expressions of one decision policy. If they drift, the demo starts disagreeing with the
documentation.

---

## 13. Repository map

```
smart-farming-edge-ai/
├── ai/                          THE EXECUTED AI CORE (rice)
│   ├── step2…step8              the pipeline, in order
│   ├── model_validation_suite.py  Wilson, bootstrap, ECE, perturbation, regression lock
│   ├── ood_eval.py              out-of-distribution harness — written, not yet run
│   ├── inference_server.py      serving + blur prefilter, localhost:8787
│   ├── sensor_contract.py       mock generator: drift, noise, fault injection
│   ├── dashboard.html           operator view
│   ├── sentinel_panel.html      judge-facing panel (generated from a live run)
│   ├── best_model.pth / *.onnx / classes.json
│   ├── pest/                    the complete second pipeline, mirroring the first
│   ├── PS-26180-MASTER.md       the frozen specification
│   ├── FLAWS.md / FIXES.md      the self-audit and its remediation plan
│   └── VALIDATION_REPORT_DETAILED.md
│
├── iot/                         cotton-lineage engine + ESP32 firmware
│   ├── contracts.py             typed SensorWindow / VisionDifferential
│   ├── fusion/engine.py         decision-level fusion reference implementation
│   └── wokwi/                   runnable MCU simulation, both variants
│
├── hardware/cad/                parametric OpenSCAD — station + printable enclosure
├── docs/                        12 design documents + decision_log.md (DR-001…DR-012)
├── viz/                         digital twin, fusion explorer
├── demo/                        the "one leaf, two field histories" demonstration
├── tests/                       23 tests locking the fusion engine
├── REPO_ANALYSIS.md             full technical audit of this repository
└── PROJECT_EXPLAINED.md         this document
```

> **Note on two lineages.** `docs/`, `iot/`, `viz/`, `demo/` and `tests/` are written
> around **cotton**; `ai/` is built for **rice**. This is documented and deliberate — the
> cotton material was preserved rather than rewritten when the crop pivoted. `REPO_ANALYSIS.md`
> covers the consequences.

---

## 14. How to run everything

All commands from the repository root. Interpreter: `ai/.venv/Scripts/python.exe`
(or any Python 3.12 with `requirements.txt` installed).

### See the results without running anything

Open [`ai/sentinel_panel.html`](ai/sentinel_panel.html) in a browser. Fully
self-contained — real model output from a live run, embedded images, no server needed.

### Run live inference

```bash
python ai/inference_server.py          # serves kisannetra_fp32.onnx on :8787
# then open ai/dashboard.html and submit an image
```

### Reproduce the disease model from scratch

```bash
python ai/step2_clean_split.py     # inventory + leakage-free split
python ai/step3_train.py           # ~6 min on CUDA
python ai/step4_evaluate.py        # accuracy, Wilson CI, lab-vs-field gap
python ai/step5_export.py          # ONNX FP32 + the INT8 research note
```

### Reproduce the pest model

```bash
python ai/pest/pest_step2_clean_split.py
python ai/pest/pest_step3_train.py --timing-only   # time one epoch first
python ai/pest/pest_step3_train.py --epochs 4      # ~3 min on CUDA
python ai/pest/pest_step4_evaluate.py
python ai/pest/pest_step5_export.py
python ai/pest/pest_verify_independent.py          # nonzero exit on failure
python ai/pest/pest_threshold_analysis.py          # the T=0.80 sweep
```

### Run every check

```bash
python ai/model_validation_suite.py    # full validation protocol
python ai/step8_integration_test.py    # 10/10 integration checks
python -m pytest tests/test_fusion.py  # 23 tests
python ai/pest/test_pest_fusion.py     # 18 tests
```

### Run the MCU simulation

Wokwi is driven by hand — see [`iot/wokwi/README.md`](iot/wokwi/README.md). Create a new
ESP32 project at wokwi.com and paste in `diagram.json` + `sketch.ino` (Arduino) or
`diagram.json` + `main.py` (MicroPython).

---

## 15. Current state

### Built and verified

- ✅ Disease classifier — trained, evaluated with intervals, exported, independently reproduced
- ✅ Pest classifier — the same, independently
- ✅ Rule engine — nutrient, irrigation, disease fusion, trend layer
- ✅ Pest fusion rule with a documented threshold — 18/18 tests
- ✅ Blur prefilter with live abstain
- ✅ Validation suite — Wilson, bootstrap, ECE, perturbation, regression lock
- ✅ Sensor contract with drift, noise and fault injection
- ✅ ESP32 firmware, both variants
- ✅ CAD: full station + printable enclosure
- ✅ 51 automated checks passing across four suites (23 + 18 + 10 checks)

### Explicitly not done

| | Why |
|---|---|
| **Qualcomm integration — future phase** | Every figure is software-only validation on desktop CPU. Compiling and profiling on Qualcomm QCS6490 (via AI Hub, then on an RB3 Gen 2 class board) is planned as the next integration phase; the procedure is in `edge/QUALCOMM_AIHUB_GUIDE.md`. No NPU profiling has been performed. |
| **INT8 not deployed** | Fails on this architecture. FP32 ships. |
| **No real sensor readings** | The hardware is designed and modelled, not built. Every sensor value is from a mock generator. |
| **No OOD test yet** | **The largest remaining validation gap.** All accuracy figures come from held-out splits of the same source distribution. `ood_eval.py` is written and ready; 20–30 real field photographs have not been collected. |
| **No IP rating claimed** | Designed for outdoor environmental protection. Nothing sealing-tested. |
| **Pest not yet on the dashboard** | The fusion rule is decided and tested; only rendering remains. |

---

## 16. How to present it

### The ninety-second arc

1. **Frame it first.** *"This is a fixed, pole-mounted sentinel node. It is not a robot and
   it does not move. Everything you are about to see is decided on-device, with no network."*
2. **Show a correct classification.** Real held-out image, real confidence.
3. **Show it abstaining.** Blur a frame — the blur score collapses from 2073 to 9.6 and the
   image never reaches the model. *This is the moment that separates a demo from a device.*
4. **Show the corroboration ceiling.** A confident Tungro prediction that still will not
   escalate to HIGH, because no sensor on this node observes leafhopper pressure.
5. **Show a sensor failing.** No value is substituted. Confidence drops. It asks for a
   manual check rather than guessing.

### The three questions to have answers ready for

**"Is this running on Qualcomm hardware?"**
Not yet — Qualcomm integration is our next phase. Everything here is software-only validation on
CPU. The software is built for the QCS6490 target: the models are 5.8 MB FP32 ONNX, and the
compile-and-profile procedure on Qualcomm AI Hub is written up in `edge/QUALCOMM_AIHUB_GUIDE.md`.
We will not present a CPU number as an NPU number.

**"How do I know your numbers are real?"**
Every headline figure carries a 95% Wilson interval. The models are independently
reproduced by a script that loads the exported ONNX and its class list from JSON, with
preprocessing re-implemented separately so a shared bug cannot hide. And we corrected one
of our own findings mid-validation and kept both numbers visible.

**"What is your biggest weakness?"**
Out-of-distribution performance on genuinely new photographs. All our accuracy comes from
held-out splits of the same distribution. The harness is written; the photos are not
collected. We would rather say that before you ask.

### What not to claim

Do not say "Qualcomm accelerated", "Hexagon", or "NPU" about any number in this repository.
Do not present any sensor value as measured. Do not claim an IP rating. Do not describe the
node as autonomous in the sense of *moving* — it is autonomous in the sense of *unattended*.

---

*Every figure in this document was produced by executing code in this repository. The
supporting audit is in [`REPO_ANALYSIS.md`](REPO_ANALYSIS.md); the validation detail is in
[`ai/VALIDATION_REPORT_DETAILED.md`](ai/VALIDATION_REPORT_DETAILED.md); the frozen
specification is [`ai/PS-26180-MASTER.md`](ai/PS-26180-MASTER.md).*
