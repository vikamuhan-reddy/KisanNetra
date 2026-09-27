# KisanNetra — Master Project Reference

**Purpose of this file.** One source of truth for generating any content about this project:
pitch decks, video scripts, the SIH presentation, posters, social posts, reports, Q&A prep.
Everything here is taken from the code, the artifacts it produced, or checks re-run on
2026-09-22. If a fact is not in this file, verify it before publishing it.

**Rules for anything generated from this file**
1. Never present a CPU figure as a Qualcomm, Hexagon or NPU measurement. Qualcomm integration is a **future phase**.
2. Never present a simulated sensor value as a field measurement.
3. Never claim an IP rating, a field-accuracy result, or a fertiliser prescription.
4. Quote accuracy with its interval and sample size where space allows.
5. Say "advisory" for disease and pest findings; the only automatic action is the irrigation valve.

---

## 1. Identity

| Field | Value |
|---|---|
| Project name | KisanNetra |
| Event | Smart India Hackathon 2026 |
| Problem statement | 26180, Qualcomm Inc., category **Hardware** |
| Theme | Agriculture, FoodTech & Rural Development |
| Crop and place | Rice (paddy), Thanjavur, Cauvery delta, Tamil Nadu |
| Team name / ID / institute | Digital Disruptors / SIH178 / Saveetha Engineering College |
| Repository | https://github.com/vikamuhan-reddy/KisanNetra |
| Judge website | https://claude.ai/artifact/LJesDxdNKpFj1Ts32RqQxN (public link) |
| GitHub Pages (if enabled) | https://vikamuhan-reddy.github.io/KisanNetra/website/ |
| Live Wokwi project | _TODO — save on wokwi.com and paste the link_ |

---

## 2. Pitches, ready to use

**One line.**
An edge-AI pole that watches one paddy field, diagnoses disease, pests, nutrient and water
problems on the device with no internet, and admits when it is not sure.

**Fifteen seconds.**
KisanNetra is a fixed solar pole for a paddy field. It photographs the crop and reads the soil
and air, and decides on the device — no network needed — whether to irrigate or to inspect for
disease or pests. Every recommendation names the measurement behind it, and when the evidence is
weak the node says so instead of guessing.

**Sixty seconds.**
A camera sees symptoms, not causes. A yellowing paddy leaf looks identical whether the cause is
nitrogen deficiency or water stress, and no bigger model fixes that, because the answer is not in
the pixels — it is in the soil moisture history. So KisanNetra pairs two small vision models
(disease 87.7%, pest damage 95.0% on held-out images) with a soil and weather sensor tier, joined
by explainable rules that run on the device. Three rules make it trustworthy: the camera alone can
never raise a high-risk alert, an unclear photo is re-taken rather than guessed at, and a failed
sensor reads UNKNOWN, never zero. It is built for a Qualcomm QCS6490, with the low-power sensor
tier already running as ESP32 firmware and the AI tier powered off until there is something worth
looking at — which is what makes a 10–20 W solar panel enough.

**Three-minute demo arc** (use with the website or the live pages)
1. Frame it: a fixed pole, one field zone, no network needed.
2. Show a correct prediction on a held-out image, with its confidence.
3. Blur the frame: the sharpness score collapses from 2073 to 9.6 and the image never reaches the model.
4. Show the corroboration ceiling: confident Tungro still will not escalate to HIGH, because no sensor here sees leafhoppers.
5. Fail a sensor: no value is substituted, confidence drops, it asks for a manual check.
6. Close on the Wokwi simulation: cut the network and the decisions keep coming.

---

## 3. The problem

- The problem statement asks for a field-deployable AI assistant detecting disease, pests, nutrient deficiency and irrigation need early, running **on-device** and working **without continuous cloud access**.
- Smallholder plots in the Cauvery delta have unreliable connectivity; a design that needs a live link for a critical decision has already failed the brief.
- A farmer will not stand in flooded paddy photographing leaves, so the sensing has to be unattended.
- Scope decision: one crop, deeply, rather than many crops shallowly.

---

## 4. The solution in one diagram

```
  camera ──► disease model (5 classes) ──┐
         └─► pest model    (3 classes) ──┼──► rule-based fusion ──► advisory + its reasons
  soil / air / tank sensors ─────────────┘        │
                                                  └──► or ABSTAIN (blur, low confidence,
                                                       failed sensor) → re-image next cycle
```

**Three design rules to repeat in any content**

| Rule | What it means | Why it matters |
|---|---|---|
| Corroboration ceiling | Visual confidence alone reaches MEDIUM, never HIGH | A camera sees symptoms, not causes |
| Abstain | An unclear frame is a deferred capture, not a missed detection | The pole re-photographs the same plants every cycle, so waiting is cheap |
| No guessing | A failed sensor is UNKNOWN, never 0 | "0 mg/kg nitrogen" from a cut wire would generate a fertiliser recommendation |

---

## 5. Hardware architecture

| Tier | Power | Role | Part |
|---|---|---|---|
| Sentinel | Always on, milliwatts | Reads sensors every 15 min, keeps history, decides when a photo is warranted, switches the compute rail | ESP32 + LoRa |
| Compute | **Off by default** | Wakes, captures, blur gate, both models, fusion, advisory, transmit, power down | Qualcomm QCS6490 (RB3 Gen 2 class) — target |

**Energy, the number that decides the design** (estimate, not measured)

| Configuration | Energy per day | Implied hardware |
|---|---|---|
| AI processor always on (~6 W) | ~144 Wh | 60–80 W panel, ~300 Wh battery, guyed mast |
| Duty-cycled, 4 sessions × ~85 s | **~0.8 Wh** | 10–20 W panel, 40–50 Wh LiFePO4 |

**Why two processors:** the QCS6490 exposes no user analog input, and capacitive soil probes are
analog. The ESP32 reads them natively. The wake triggers are the same stress conditions the fusion
rules reason about, so power management and diagnostics are one rule set.

**Physical layout:** camera with sun hood aimed 35° down at the canopy; sealed electronics bay;
tilted solar panel; soil probes at ~100 mm (surface) and ~300 mm (root zone) with pH, EC and soil
temperature at the root zone. Two depths separate "the surface got wet" from "the roots can drink".

---

## 6. Data

| Dataset | Role | Images used | Conditions |
|---|---|---|---|
| Paddy Doctor (Kaggle competition; Petchiammal et al., CODS-COMAD 2023) | Disease + pest models | 5,981 disease-model, 4,767 pest-model (after de-duplication) | Field, Tamil Nadu; 10 varieties, ADT45 is 67% of the dataset |
| Lab rice-leaf set (`archive (3)`) | Lab-condition subset of the disease model | 626 | Studio, single leaf — _TODO: source link_ |

- **Class mapping:** `bacterial_leaf_blight`, `blast`, `brown_spot`, `tungro`, `normal` → Bacterial Blight, Blast, Brown Spot, Tungro, Healthy. `dead_heart`, `hispa`, `normal` → pest model.
- **Not used yet:** bacterial leaf streak, bacterial panicle blight, downy mildew (Paddy Doctor); leaf scald (lab set, no field counterpart).
- **De-duplication:** exact MD5; 53 duplicates removed (disease), 33 (pest).
- **Splits:** 70/15/15 per class *and* per source, seed 42.

| | Train | Val | Test |
|---|---|---|---|
| Disease | 4,621 | 986 | 1,000 (901 field + 99 lab) |
| Pest | 3,336 | 714 | 717 (all field) |

- **No paired image + sensor dataset exists** for Thanjavur paddy, so none was fabricated. Vision and sensors stay separate, joined by rules.
- Image splits are not in the repository; two scripts rebuild them from the raw datasets.

---

## 7. Models and training

| | Disease | Pest damage |
|---|---|---|
| Classes | Bacterial Blight, Blast, Brown Spot, Healthy, Tungro | Dead Heart, Hispa, No Pest Damage |
| Architecture | MobileNetV3-Small, ImageNet-1k pretrained | same |
| Input | 224×224 RGB, ImageNet normalisation | same |
| Augmentation | horizontal flip, rotation ±15°, colour jitter 0.2 | same |
| Schedule | 1 epoch head-only (Adam 1e-3) → 4 epochs full fine-tune (Adam 1e-4), batch 64, cross-entropy, best-validation checkpoint | same |
| Train time | ~6 min on an RTX 5060 laptop GPU | ~3 min |
| Deployed artifact | FP32 ONNX, opset 17, 5.8 MB | FP32 ONNX, 5.8 MB |
| Class order | written to `classes.json` at training time, never hard-coded | `pest_classes.json` |

**Why two models rather than one 8-class model:** fungal or bacterial lesions and insect feeding
damage are different visual tasks, and keeping them separate means the pest model can be retrained
without touching a validated disease model. The two verdicts are never averaged.

---

## 8. Results — quote these exactly

### Disease model (n = 1,000 held-out images)

| Metric | Value |
|---|---|
| Accuracy | **87.70%**, 95% Wilson CI [85.52, 89.59]; bootstrap CI [85.60, 89.65] |
| Macro-F1 | 0.8627 |
| Expected calibration error | 0.0369 |
| Field-image accuracy | 88.79% (n = 901) |
| Lab-image accuracy | 77.78% (n = 99, no Healthy class — **not** a like-for-like comparison) |

Per-class recall: Healthy 95.4% (251/263) · Tungro 91.2% (165/181) · Blast 88.7% (258/291) ·
Bacterial Blight 85.8% (91/106) · **Brown Spot 70.4% (112/159)** — mostly confused with Blast (22 images).

### Pest-damage model (n = 717, all field)

| Metric | Value |
|---|---|
| Accuracy | **94.98%**, 95% Wilson CI [93.13, 96.35] |
| Macro-F1 | 0.9519 |
| Recall | Dead Heart 98.6% · Hispa 95.4% · No Pest Damage 91.6% |

### Alert threshold, chosen by measurement (pest channel)

| Threshold | False alerts on healthy leaves | Pest recall | Re-imaged |
|---|---|---|---|
| none | 8.37% | 96.9% | 0% |
| 0.70 | 5.32% | 93.4% | 6.6% |
| **0.80 (chosen)** | **3.04%** | **90.3%** | **11.2%** |
| 0.90 | 0.76% | 83.7% | 18.8% |

One healthy leaf in twelve raised a false alert without a threshold; 0.80 cuts that 2.75× for 6.6
points of recall.

### Robustness (n = 400, same images perturbed)

| Condition | Accuracy | Change |
|---|---|---|
| Clean baseline | 86.75% | — |
| Low brightness | 85.25% | −1.50 pp |
| High contrast | 86.75% | 0 |
| Rotation 10° | 86.75% | 0 |
| **Blur** | **69.00%** | **−17.75 pp** |

Blur is the only material weakness, and the blur gate sits in front of the model because of it.

### Speed and size

2.5 ms median inference, p95 5.1 ms, FP32 ONNX at 224×224 on a **desktop CPU**. 5.8 MB per model.
**Not a Qualcomm number.**

### INT8 quantization — reported as a failure

onnxruntime post-training INT8 collapsed to 22–36% across five schemes (disease) and 34.59% (pest).
Root cause **not isolated**; suspects are MobileNetV3's depthwise convolutions, squeeze-excite
blocks and HardSwish activation ranges under per-tensor quantization. FP32 ships; the broken files
are named `BROKEN` on disk. An earlier explanation of ours ("HardSwish produces negative values for
x < −3") was **wrong** and has been corrected: HardSwish is exactly 0 for x ≤ −3 and negative only
on (−3, 0), minimum −0.375.

---

## 9. The fusion and decision rules

### Disease fusion (`ai/step6_rule_engine.py`)

| Condition | Corroboration needed for HIGH | Ceiling |
|---|---|---|
| Bacterial Blight | humidity ≥ 80% and 25–35 °C | HIGH |
| Blast | humidity ≥ 85% and 24–32 °C | HIGH |
| Brown Spot | low nitrogen or low root moisture | HIGH |
| **Tungro** | none exists on this node | **MEDIUM** |
| Hispa (pest channel) | soil nitrogen above the high threshold | HIGH |
| **Dead Heart** | none exists on this node | **MEDIUM** |

Tungro is leafhopper-vectored and Dead Heart is caused by stem borer; no sensor on this pole
observes either insect, so HIGH is unreachable **by design, documented and tested**, and the node
states why in its own output.

### Agronomic thresholds (Thanjavur paddy; general starting points, not calibrated constants)

| Quantity | Threshold |
|---|---|
| **AWD water depth** | **re-flood at 15 cm below surface** (`AWD_REFLOOD_DEPTH_CM`); tube floor 25 cm. **Primary irrigation signal** — see note below |
| Surface moisture | irrigate below 22% — **drained stages only** |
| Root-zone moisture | urgent below 16% — **drained stages only**; firmware: stress 20%, adequate 28%, waterlogged 45% |
| Soil pH | optimal 5.5–7.0 (firmware flags outside 5.6–7.8) |
| Soil EC | salinity above 2.0 dS/m (firmware 3.0) |
| N / P / K | 30–60 / >12 / >25 mg/kg — **EC-derived proxies, soil test advised, never a prescription** |
| Tank level | irrigation blocked below 20% (firmware 15%) |
| Light | image discounted below 400 lux (firmware 120 lux) |
| Air temperature | heat stress above 38 °C |
| Blur (variance of Laplacian) | frame rejected below 100 |

**Ordering matters:** supply outranks crop stress. Below the critical tank level the valve stays
shut however thirsty the crop is — a pump run dry destroys itself in minutes.

**Why water depth, not soil moisture.** Thanjavur paddy is grown under standing water for most
of the season, so capacitive probes at 100 and 300 mm sit at saturation and carry no irrigation
signal — the 22% and 16% thresholds above would never fire. The actionable variable is how far
the water has drawn down below the surface, measured in a perforated AWD (Alternate Wetting and
Drying) tube. `evaluate_irrigation()` therefore runs on water depth whenever the tube is
reading, and falls back to the soil probes only when the tube shows the field is genuinely
drained, or when the tube has failed. See `ai/test_awd_irrigation.py` (8 tests).

> The 15 cm figure is the commonly cited AWD threshold and is **not yet verified for the
> Cauvery delta**. It is a calibration parameter, flagged as such in the source. An enquiry to
> TRRI Aduthurai is outstanding.

> **Known divergence:** the ESP32 firmware (`iot/wokwi/`) still implements the moisture-only
> policy. The Python rule engine and the firmware are two expressions of one decision policy and
> they currently disagree on irrigation. The firmware is the next thing to bring in line.

---

## 10. Abstain and failure handling

- **Blur gate:** variance of Laplacian on the raw greyscale image, before normalisation. Measured live: a sharp frame scores 2073.4 and is classified; the same frame blurred scores 9.6 and returns `ABSTAIN_BLUR` without reaching the model. A flat frame scores 0.0 and is rejected.
- **Confidence gate:** pest predictions below 0.80 are reported inconclusive and re-imaged.
- **Sensor faults:** a missing or failed reading returns `None`, never a substituted value; dependent rules report UNKNOWN with MANUAL CHECK RECOMMENDED and confidence drops. Two tests prove a faulted probe cannot escalate an alert.
- **Stuck sensors** are detected by loss of jitter: a live capacitive probe always fluctuates, so identical repeated readings mean it died while still reporting.

---

## 11. Firmware and the Wokwi simulation

- Runs the sentinel tier's real MicroPython firmware on a simulated ESP32: **23 parts, 58 wires, 12 sensor channels**.
- Inputs: two soil-moisture depths, pH, EC, vision confidence (potentiometers); DHT22 air temperature and humidity; DS18B20 soil temperature; HC-SR04 tank level; photoresistor light; RAIN, NET and FAULT buttons.
- Outputs: relay (irrigation valve), VALVE/ALERT/EDGE LEDs, buzzer, 128×64 OLED with five pages, plus a 20×4 LCD mirror for demos.
- Live MQTT to a public HiveMQ broker: `sih26180/sentinel-01/telemetry`, `/decision`, and `/vision` (subscribed — where the AI tier's result arrives, as `{"disease": 0.85, "pests": 6}`).
- **The decision happens before the radio is touched;** Wi-Fi has an 8 s timeout, retries every 30 s, and up to 50 records queue locally while offline.
- **Verified:** the firmware's decision logic passes **15 field scenarios** (healthy, dry root zone, empty tank, rain, waterlogging, salinity, pH lock-out, heat, disease with and without corroboration, failed probe, stuck probe, lost tank sensor), plus a portability check for MicroPython. Its harness already caught a real bug: a waterlogged rainy field once read "all signals normal".
- **The camera cannot alarm alone, as arithmetic:** vision risk is confidence × 55 against a threshold of 60. With humid, warm air the camera needs 0.48; with humidity alone 0.70; with temperature alone 0.88; with neither it is impossible.
- An Arduino C++ variant (6 channels, no networking) exists with identical decision logic.

---

## 12. Qualcomm edge path — future integration

| Phase | Step | What it proves |
|---|---|---|
| 1 | Compile and profile both models on QCS6490 via Qualcomm AI Hub | Latency, peak memory, share of layers on the Hexagon NPU |
| 2 | INT8 with Qualcomm's quantizer; quantization-aware training if needed | INT8 accuracy against the FP32 baseline |
| 3 | RB3 Gen 2 class board with the ESP32 tier over UART | End-to-end on-device advisory and energy per capture session |

Procedure is written up in `project/edge/QUALCOMM_AIHUB_GUIDE.md`, including a ready script.
Until it runs, **no Qualcomm figure exists** and none may be implied.

---

## 13. Validation and the honesty discipline

- **51 automated checks pass:** 23 fusion-engine tests, 18 pest-fusion tests, 10 end-to-end integration checks; plus the firmware's 15 scenarios and the full validation suite.
- **Independent reproduction:** a separate script reloads the exported ONNX and its class list, with preprocessing re-implemented from scratch, so a shared bug cannot hide on both sides.
- **Offline proof:** a test asserts the rule engine makes zero network calls.
- **Self-audit:** 15 findings recorded in `ai/FLAWS.md`, including a label swap that reported every healthy plant as Tungro and every Tungro as healthy — caught and fixed. Showing a mistake you caught yourself is stronger than showing none.
- **Corrections made before submission:** the wrong INT8 explanation; fertiliser prescriptions replaced with soil-test advisories; the lab-vs-field comparison caveated; a dashboard that invented a prediction when the model server was unreachable; a blur rejection displayed as a disease.
- **Leakage measured, not assumed:** a perceptual-hash scan found ~5% near-duplicates between train and test (disease 46/901 field images, worst Brown Spot 13%; pest 41/717, worst Hispa 11%), so the headline figures are slightly optimistic.

---

## 14. Limitations — state these before a judge asks

1. **Qualcomm integration is a future phase.** Everything is validated in software on a laptop CPU.
2. **No physical board yet.** Sensor values come from a mock generator with drift, noise and fault injection; the hardware exists as CAD and firmware simulation.
3. **Camera angle untested.** Training images are close-up leaves; the pole camera looks down at the canopy. `ai/ood_eval.py` is written; the photos are not collected.
4. **~5% near-duplicate leakage** between splits, so accuracy is slightly optimistic.
5. **N/P/K are EC-derived proxies**, so the system advises a soil test and never prescribes fertiliser.
6. **Coverage:** five diseases and two pest-damage types. Brown planthopper and leaf folder are not covered.
7. **Thresholds are general starting points,** not per-field calibrated constants.
8. **The demo MQTT broker is public and unauthenticated** — fine for a demo, wrong for a fleet.

---

## 15. Roadmap

**ML:** Qualcomm profiling and INT8 → canopy-angle OOD test → remove near-duplicates and add a
variety-held-out test → improve Brown Spot (class weighting, more data) → disease confidence
threshold → three more Paddy Doctor diseases → brown planthopper and leaf folder detection →
nutrient-deficiency imagery and district-level yield risk.

**Product:** physical node on an RB3 Gen 2 class board → one-season pilot on a cooperative's plots
through kuruvai or samba, calibrating thresholds per field → one shared compute node per
cooperative with inexpensive sensor nodes per plot. The hardware topology is the business model.

---

## 16. Judge Q&A — prepared answers

**"Is this running on Qualcomm hardware?"**
Not yet; Qualcomm integration is our next phase. Everything you see is FP32 on a laptop CPU
(87.70%, 5.8 MB per model). The system is designed around the QCS6490 — small ONNX models, a
separate sensor tier because that SoC has no analog input — and the compile-and-profile procedure
is already written up. We will not show a latency number until it has run on Qualcomm silicon.

**"How do I know your numbers are real?"**
Every headline figure carries a 95% Wilson interval. The models are independently reproduced by a
script that reloads the exported ONNX with separately written preprocessing. We also measured our
own train/test leakage and corrected one of our own findings mid-validation.

**"What is your biggest weakness?"**
Out-of-distribution performance on genuinely new photographs, especially at the pole's camera
angle. The harness is written; the photos are not collected. We would rather say that first.

**"Why rice, when your early docs say cotton?"**
We pivoted for data reasons. Paddy Doctor gives 10,000+ labelled field images from Tamil Nadu — the
same region and varieties as our target deployment — and already contains two pest-damage classes.
The old cotton documents are kept unchanged as the design record.

**"Why not one model for everything?"**
Lesions and insect damage are different visual tasks, and the two verdicts must stay separately
explainable. A blended score could not be explained to a farmer or to you.

**"What does the farmer actually get?"**
One advisory per capture cycle, naming the reasons: for example "Disease: Bacterial Blight
(MEDIUM). No pest alert." — because the farmer makes one trip to the field.

---

## 17. Soundbites

- "A camera sees symptoms, not causes."
- "An inconclusive frame is a deferred capture, not a missed detection."
- "A failed sensor reads UNKNOWN, never zero — a cut wire must not become a fertiliser bill."
- "The camera is not allowed to raise the alarm alone."
- "Power optimisation and diagnostic logic turned out to be the same rule set."
- "The hardware topology is the business model: one compute node per cooperative, cheap sensor nodes per plot."
- "We found fifteen faults in our own work and published them."

---

## 18. Asset inventory

| Asset | Path / link |
|---|---|
| Judge website (offline copy) | `website/index.html` + `results.html`, `twin.html`, `fusion.html`, `wokwi.html` |
| Sample images for demos | `samples/disease/*`, `samples/pest/*` (5 per class) |
| Models | `project/ai/kisannetra_fp32.onnx`, `project/ai/pest/kisannetra_pest_fp32.onnx` |
| Metrics files | `ai/eval_metrics.json`, `ai/validation_report.json`, `ai/pest/pest_eval_metrics.json`, `ai/pest/pest_threshold_analysis.json` |
| Full walkthrough | `project/PROJECT_EXPLAINED.md` |
| End-to-end data flow + edge cases (video script source) | `END_TO_END_MASTER.md` |
| Progress report (bench hardware + AI dashboard) | `PROGRESS_REPORT.md` |
| AI inference dashboard | `dashboard/` |
| Arduino sensor wiring and test sketches | `project/hardware/arduino/SENSOR_SETUP.md` |
| Demo script and prepared answers | `project/docs/18_demo_script.md` |
| Sensor reference (physics of each sensor) | `project/docs/23_sensing_reference.md` |
| Power budget | `project/docs/22_power_autonomy.md` |
| Decision log (DR-001…DR-012) | `project/docs/decision_log.md` |
| Self-audit | `project/ai/FLAWS.md`, `project/ai/FIXES.md` |
| Firmware | `project/iot/wokwi/micropython/` (and `arduino/`) |
| CAD | `project/hardware/cad/` |
| Qualcomm procedure | `project/edge/QUALCOMM_AIHUB_GUIDE.md` |

---

## 19. Glossary

| Term | Plain meaning |
|---|---|
| Edge AI | The model runs on the device in the field, not in a cloud server |
| NPU | The chip's AI accelerator; on the QCS6490 it is the Hexagon NPU |
| ONNX | A portable model file format, used here for deployment |
| Quantization / INT8 | Shrinking a model to 8-bit numbers for speed; ours loses accuracy, so we ship FP32 |
| Wilson interval | An honest error bar around an accuracy computed from a limited test set |
| Calibration (ECE) | Whether a "90% confident" prediction is right about 90% of the time |
| Macro-F1 | Average per-class score; unlike accuracy it does not hide a weak class |
| Recall | Of all images of a class, the share the model found |
| Variance of Laplacian | A sharpness score; low means blurred |
| EC | Electrical conductivity of soil; indicates salts, and cheap probes infer N/P/K from it |
| Root zone | The soil depth the plant actually drinks from (~300 mm here) |
| OOD | Out-of-distribution: images unlike anything in training |
| Duty cycling | Keeping a power-hungry chip switched off except in short bursts |

---

## 20. Fact register — where each number comes from

| Number | Source |
|---|---|
| 87.70%, CIs, macro-F1, ECE, per-class recall | `ai/validation_report.json`, `ai/eval_metrics.json` (suite re-run 2026-09-22) |
| 94.98% and pest recalls | `ai/pest/pest_eval_metrics.json`, reproduced by `pest_verify_independent.py` |
| Threshold sweep | `ai/pest/pest_threshold_analysis.json` |
| Robustness table | perturbation section of `ai/validation_report.json` |
| 2.5 ms / p95 5.1 ms | desktop CPU timing, FP32 ONNX |
| Dataset and split counts | `ai/split_report.json`, `ai/pest/pest_split_report.json` |
| 51 checks | `pytest tests/` (23), `ai/pest/test_pest_fusion.py` (18), `ai/step8_integration_test.py` (10) |
| 15 firmware scenarios | `iot/wokwi/micropython/test_firmware.py` |
| ~5% near-duplicates | perceptual-hash scan, 2026-09-22 |
| Blur scores 2073 / 9.6 / 0.0 | inference server runs on real and flattened frames |
| Energy 144 Wh vs ~0.8 Wh | `docs/22_power_autonomy.md` — **estimate, not measured** |
