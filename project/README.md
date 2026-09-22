# KisanNetra — Edge-AI Field Sentinel for Paddy

**SIH 2026 · Problem Statement 26180 · Qualcomm Inc · Category: Hardware**
**Theme:** Agriculture, FoodTech & Rural Development · **Scope:** rice (paddy), Thanjavur, Tamil Nadu

A fixed, pole-mounted, solar-powered sentinel that watches one paddy zone and, **with no
network**, detects crop disease and pest damage from a camera, checks the finding against
soil and weather sensors, and tells the farmer what to do — or honestly says it is not sure.

---

## The idea in one line

> **A camera sees symptoms, not causes.**

Brown Spot, early Blast and nutrient stress can look alike in a single RGB frame. No bigger
model fixes that, because the information is not in the pixels — it is in the humidity
history, the root-zone moisture, the soil chemistry. So KisanNetra keeps vision and sensors
as **separate components joined by an explainable rule-based fusion layer**:

```
  camera ──► disease model (5 classes) ──┐
         └─► pest model    (3 classes) ──┼──► fusion rules ──► advisory + the reason for it
  soil / air / tank sensors ─────────────┘        │
                                                   └──► or ABSTAIN (blurry frame, low confidence,
                                                        failed sensor) and re-image next cycle
```

Three rules make it trustworthy:

1. **Visual confidence alone never reaches HIGH risk.** HIGH needs sensor corroboration
   (e.g. Blast needs humidity ≥ 85 % and 24–32 °C). Tungro and Dead Heart are **capped at
   MEDIUM by design** — their insect vectors are invisible to every sensor on this node.
2. **An inconclusive frame is a deferred capture, not a missed detection.** Blurry frames
   are rejected before inference; low-confidence pest calls are re-imaged. This is cheap
   only because the node is fixed and photographs the same plants every cycle.
3. **A missing sensor is UNKNOWN, never zero.** A dropped NPK wire must not become "0 mg/kg
   nitrogen → buy fertiliser". Dependent advice is withheld and a manual check is requested.

---

## Current status — read before making any claim

| Validation level | Status | What we may claim |
|---|---|---|
| **A — software on laptop** | ✅ done | Models, fusion, abstain logic, fault handling, firmware simulation |
| **B — Qualcomm QCS6490 via AI Hub** | 🔜 future integration — procedure in [edge/QUALCOMM_AIHUB_GUIDE.md](edge/QUALCOMM_AIHUB_GUIDE.md) | Nothing yet. When integrated: latency, memory, NPU layer share on QCS6490 |
| **C — physical board in a field** | 🔜 future integration (next round) | Nothing |

**Every figure below is software-only validation on a desktop CPU/GPU.** No number here is
a Qualcomm, Hexagon or NPU number. All sensor values are from a mock generator.

---

## Results

### Disease model — MobileNetV3-Small, 5 classes
`Bacterial Blight · Blast · Brown Spot · Healthy · Tungro`

| Metric | Value |
|---|---|
| Test accuracy (n = 1,000; 90 % field images) | **87.70 %** — 95 % Wilson CI [85.52, 89.59] |
| Macro-F1 | 0.863 |
| Expected calibration error | 0.037 |
| Field-image accuracy (n = 901) | 88.79 % |

### Pest model — MobileNetV3-Small, 3 classes
`Dead Heart · Hispa · No Pest Damage`

| Metric | Value |
|---|---|
| Test accuracy (n = 717, all field) | **94.98 %** — 95 % Wilson CI [93.13, 96.35] |
| Macro-F1 | 0.952 |
| False pest alerts on healthy leaves | **8.4 % → 3.0 %** at confidence threshold T = 0.80 (chosen from a sweep; 90.3 % pest recall, 11 % re-imaged) |

### Robustness and speed
| Check | Result |
|---|---|
| Blur | 86.8 % → **69.0 %** — the only material weakness; handled by the blur prefilter (sharp frame VoL 2073 → classified; blurred 9.6 → `ABSTAIN_BLUR`) |
| Low brightness / high contrast / 10° rotation | −1.5 / 0 / 0 pp |
| FP32 ONNX size | 5.8 MB each |
| Inference, desktop CPU | 2.5 ms median, 5.1 ms p95 (224×224) — **not** a Qualcomm number |

### Known limitations (we say these before you ask)
- **Qualcomm integration is future work.** The software is built for the QCS6490 target; compiling and
  profiling on Qualcomm silicon (AI Hub, then an RB3 Gen 2 class board) is the next integration phase.
- **INT8 does not work yet.** onnxruntime post-training INT8 collapsed to 22–36 % on both
  models; root cause not isolated (MobileNetV3 depthwise / squeeze-excite / HardSwish
  ranges suspected). Broken files are named `*.BROKEN_*.onnx`. FP32 ships. Next: Qualcomm's
  own quantizer on AI Hub, then QAT or a ReLU backbone.
- **Out-of-distribution not tested.** Training images are close-up leaves; the sentinel camera
  looks down at the canopy. `ai/ood_eval.py` is ready; real mounting-angle photos are not
  yet collected. This is the largest open validation gap.
- **~5 % near-duplicate leakage measured** between train and test (deduplication was exact-MD5
  only). Headline accuracies are slightly optimistic; re-reporting without them is queued.
- **Lab vs field is not like-for-like:** the lab test subset (99 images, 77.8 %) has no
  Healthy class, so we do not draw a "field-specialised" conclusion from it.
- **N/P/K are proxies.** Low-cost NPK probes estimate them from conductivity, so the system
  flags *possible* shortages with LOW confidence and recommends a soil test — it never
  prescribes fertiliser.
- **Pest coverage is two damage types** (Hispa, stem-borer Dead Heart). Brown planthopper and
  leaf folder are phase 2.

---

## Hardware architecture

```
                    ┌─ camera + sun hood, 35° down at the canopy
       ┌────────────┴─────────────┐
       │  sealed electronics bay  │  ESP32 sentinel (always on, mW) + QCS6490 (OFF by default)
       └────────────┬─────────────┘  10–20 W solar, LiFePO4
   ═════════════════╪═════════════  ground
                    ├── moisture probe  ~100 mm (surface)
                    └── moisture probe  ~300 mm (root zone) + pH / EC / soil temp
```

| Tier | Role | Part |
|---|---|---|
| **Sentinel** | Reads sensors every 15 min, keeps a rolling window, decides when a capture is worth it, switches the compute rail | ESP32 + LoRa |
| **Compute** | Wakes on trigger, captures, runs both models + fusion, transmits, powers down | Qualcomm QCS6490 (RB3 Gen 2 class) — target |

**Why duty-cycled:** an always-on SoC at ~6 W needs ~144 Wh/day (60–80 W panel, guyed mast);
four ~85 s sessions need ~0.8 Wh/day *(estimate)*. The wake triggers are the same stress
conditions the fusion rules reason about. **Why two processors:** the QCS6490 has no user
analog input; capacitive moisture probes are analog; the ESP32 reads them natively.

---

## Quickstart

All commands from this folder. Interpreter: `ai/.venv/Scripts/python.exe` (Python 3.12).

```bash
# See results without running anything
#   open ai/sentinel_panel.html in a browser (self-contained, real model output)

# Live inference + dashboard
python ai/inference_server.py            # serves kisannetra_fp32.onnx on :8787
#   then open ai/dashboard.html and drop in a leaf image

# Every check
python ai/step8_integration_test.py      # 10/10 end-to-end checks
python ai/pest/test_pest_fusion.py       # 18 pest fusion tests
python ai/model_validation_suite.py      # Wilson/bootstrap CIs, ECE, perturbation, rule scenarios
python -m pytest tests/ -q               # 23 fusion-engine tests (pytest is in requirements.txt)

# Qualcomm integration (future phase; needs a free Qualcomm AI Hub ID)
#   follow edge/QUALCOMM_AIHUB_GUIDE.md

# ESP32 sentinel firmware
#   paste iot/wokwi/micropython/{diagram.json,main.py} into a new ESP32 project at wokwi.com
```

Retraining from scratch: `ai/step2_clean_split.py` → `step3_train.py` → `step4_evaluate.py` →
`step5_export.py` (and the `ai/pest/pest_step*.py` mirror). The image splits are **not stored in git**:
download [Paddy Doctor](https://www.kaggle.com/competitions/paddy-disease-classification) and the lab rice-disease set
(`archive (3)`), put both next to this repository folder (or set `KISANNETRA_DATA` to their folder),
then run the two `*step2_clean_split.py` scripts to rebuild `ai/dataset_split/` and `ai/pest/pest_dataset_split/`.

---

## Repository map

| Path | Contents |
|---|---|
| [`ai/`](ai/) | **Rice AI core:** pipeline `step2`–`step8`, rule engine, inference server, dashboard, validation suite, models |
| [`ai/pest/`](ai/pest/) | Second, independent pest pipeline mirroring the disease one, plus pest fusion rule and threshold sweep |
| [`ai/sentinel_panel.html`](ai/sentinel_panel.html) | Judge-facing results panel generated from a live run |
| [`edge/`](edge/) | Qualcomm integration (future phase): AI Hub guide and scripts |
| [`iot/wokwi/`](iot/wokwi/) | ESP32 sentinel firmware — Arduino C++ and MicroPython (live MQTT) |
| [`iot/fusion/`](iot/fusion/), [`demo/`](demo/), [`tests/`](tests/) | Differential-fusion reference engine and its "one leaf, two field histories" demo *(cotton-lineage, see below)* |
| [`hardware/cad/`](hardware/cad/) | Parametric OpenSCAD: full sentinel station + printable sensor enclosure |
| [`docs/`](docs/) | Design documents and decision log (DR-001 … DR-012) |
| [`PROJECT_EXPLAINED.md`](PROJECT_EXPLAINED.md) | **Full end-to-end walkthrough — start here after this README** |
| [`ai/FLAWS.md`](ai/FLAWS.md) | Our own 15-finding audit of our work, including the Healthy↔Tungro label swap we caught |

**Two lineages, stated openly.** The project began on cotton and pivoted to rice when Paddy
Doctor (10,000+ labelled Tamil Nadu field images, ADT45/Ponni varieties) gave us field data
from the exact target region. `ai/` is the executed rice system. `docs/`, `iot/fusion`,
`demo/` and `tests/` were written for cotton and are kept unchanged as the design record; the
fusion *principles* carried over, the class lists did not.

---

## Documentation index

| Document | Purpose |
|---|---|
| [PROJECT_EXPLAINED.md](PROJECT_EXPLAINED.md) | The whole project, end to end |
| [ai/VALIDATION_REPORT_DETAILED.md](ai/VALIDATION_REPORT_DETAILED.md) | Full validation results |
| [edge/QUALCOMM_AIHUB_GUIDE.md](edge/QUALCOMM_AIHUB_GUIDE.md) | Running both models on a Qualcomm QCS6490 via AI Hub |
| [docs/18_demo_script.md](docs/18_demo_script.md) | Demo flow and prepared answers for judges |
| [docs/07_hardware_decision.md](docs/07_hardware_decision.md) | Platform choice and rejected alternatives |
| [docs/22_power_autonomy.md](docs/22_power_autonomy.md) | Energy budget, solar and battery sizing |
| [docs/23_sensing_reference.md](docs/23_sensing_reference.md) | Every sensor: principle, placement, what breaks without it |
| [docs/13_failure_modes.md](docs/13_failure_modes.md) | Hostile-reviewer cases and tested behaviour |
| [docs/decision_log.md](docs/decision_log.md) | Every significant choice and when to revisit it |

---

## What we will not claim

"Qualcomm-accelerated", "Hexagon" or "NPU" for any number not produced on AI Hub · any
simulated sensor value as measured · an IP rating (design intent only: outdoor environmental
protection) · a fertiliser prescription from an NPK proxy · "autonomous" in the sense of
*moving* — the node is autonomous in the sense of *unattended*.
