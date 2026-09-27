# KisanNetra — Edge-AI Field Sentinel for Paddy

**Smart India Hackathon 2026 · Problem Statement 26180 · Qualcomm Inc. · Category: Hardware**
**Theme:** Agriculture, FoodTech & Rural Development · **Scope:** rice (paddy), Thanjavur, Tamil Nadu

| | |
|---|---|
| **Team name** | Digital Disruptors |
| **Team ID** | SIH178 |
| **Institute** | Saveetha Engineering College |
| **Current stage** | Hardware validation + AI inference — see [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md) |

A fixed, solar-powered pole for a paddy field that photographs the crop, reads the soil and air,
and decides **on the device, with no network** whether there is disease, pest damage, a nutrient
problem or a need to irrigate — and says so honestly when the evidence is too weak to decide.

---

## Start here

| If you want to… | Open |
|---|---|
| **See the whole project in 5 minutes** | [`website/index.html`](website/index.html) — works offline, in any browser |
| See real model predictions on held-out images | [`website/results.html`](website/results.html) |
| Watch the guided system demo (drought, disease, rain, offline, sensor failure) | [`website/twin.html`](website/twin.html) |
| Try the sensor-fusion idea yourself | [`website/fusion.html`](website/fusion.html) |
| See the ESP32 firmware simulation (Wokwi): circuit, 15 tested scenarios, how to run it | [`website/wokwi.html`](website/wokwi.html) |
| Read the full technical walkthrough | [`project/PROJECT_EXPLAINED.md`](project/PROJECT_EXPLAINED.md) |
| Get every verified fact in one place (for slides, scripts, Q&A prep) | [`PROJECT_MASTER.md`](PROJECT_MASTER.md) |
| **See the latest progress (hardware bench tests + AI dashboard)** | [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md) |
| Run the real disease and pest models on your own leaf photo | [`dashboard/`](dashboard/README.md) — local web dashboard |
| Wire and test the sensors on an Arduino UNO | [`project/hardware/arduino/SENSOR_SETUP.md`](project/hardware/arduino/SENSOR_SETUP.md) |
| Follow the data end to end (sensor → JSON → AI → fusion → edge cases) | [`END_TO_END_MASTER.md`](END_TO_END_MASTER.md) |
| Run the code | [How to run](#how-to-run) below |

---

## Results at a glance

All figures are software-only validation on held-out test images (laptop CPU, FP32 ONNX).

| | Disease model | Pest-damage model |
|---|---|---|
| Classes | Bacterial Blight, Blast, Brown Spot, Healthy, Tungro | Dead Heart, Hispa, No pest damage |
| Test accuracy | **87.70%** (n = 1,000), 95% CI [85.52, 89.59] | **94.98%** (n = 717), 95% CI [93.13, 96.35] |
| Macro-F1 | 0.863 | 0.952 |
| Model | MobileNetV3-Small, 5.8 MB FP32 ONNX | MobileNetV3-Small, 5.8 MB FP32 ONNX |

- False pest alerts on healthy leaves fall from **8.4% to 3.0%** with the chosen confidence threshold (0.80).
- Blurry frames are rejected before inference and re-captured (the model's one real weakness is blur).
- **51 automated checks pass** (23 fusion-engine, 18 pest-fusion, 10 end-to-end integration).
- **Qualcomm QCS6490 integration is the next phase** — see [`project/edge/QUALCOMM_AIHUB_GUIDE.md`](project/edge/QUALCOMM_AIHUB_GUIDE.md). No figure here is a Qualcomm NPU measurement.

---

## Data

| Dataset | Used for | Images used | Conditions | Source |
|---|---|---|---|---|
| **Paddy Doctor** (Petchiammal et al., CODS-COMAD 2023) | Disease model (4 classes + Healthy) and pest model (Dead Heart, Hispa, No pest damage) | 5,981 disease-model + 4,767 pest-model images after de-duplication | **Field**: real paddy plots in Tamil Nadu; 10 varieties, ADT45 is 67% of the dataset | [Kaggle: paddy-disease-classification](https://www.kaggle.com/competitions/paddy-disease-classification) |
| **Lab rice-leaf set** (`archive (3)`) | Disease model, lab-condition subset | 626 (Bacterial Blight, Blast, Brown Spot, Tungro) | **Lab**: single leaf, studio background | _TODO: source link_ |

**Class mapping.** Paddy Doctor `bacterial_leaf_blight`, `blast`, `brown_spot`, `tungro`, `normal` → Bacterial Blight,
Blast, Brown Spot, Tungro, Healthy. `dead_heart`, `hispa`, `normal` → the pest model. Not used yet: Paddy Doctor
`bacterial_leaf_streak`, `bacterial_panicle_blight`, `downy_mildew`, and the lab set's `leaf_scald` (no field counterpart).

**Splits.** Exact duplicates removed by MD5 (53 disease, 33 pest), then a 70 / 15 / 15 split **per class and per source**
(fixed seed 42), so no image appears in two splits and lab and field images can be scored separately.

| | Train | Validation | Test |
|---|---|---|---|
| Disease model | 4,621 | 986 | 1,000 (901 field + 99 lab) |
| Pest model | 3,336 | 714 | 717 (all field) |

Image splits are not stored in the repository; `ai/step2_clean_split.py` and `ai/pest/pest_step2_clean_split.py` rebuild them
from the raw datasets. Split reports: `ai/split_report.json`, `ai/pest/pest_split_report.json`.

**No image + sensor dataset exists** for Thanjavur paddy, so none was fabricated: vision and sensors are separate
components joined by explainable rules, and every sensor value in this submission is simulated.

---

## Models, training and evaluation

| | Disease model | Pest-damage model |
|---|---|---|
| Architecture | MobileNetV3-Small, ImageNet-1k pretrained | same |
| Input | 224×224 RGB, ImageNet normalisation | same |
| Augmentation (train only) | horizontal flip, rotation ±15°, colour jitter 0.2 | same |
| Training | 1 epoch head-only (Adam, lr 1e-3), then 4 epochs full fine-tune (Adam, lr 1e-4); batch 64; cross-entropy; best validation checkpoint kept | same |
| Hardware / time | NVIDIA RTX 5060 laptop GPU, ~6 min | ~3 min |
| Deployment artifact | FP32 ONNX (opset 17), 5.8 MB | FP32 ONNX, 5.8 MB |
| Class order | saved to `classes.json` at training time; never hard-coded | `pest_classes.json` |

**Evaluation** (`ai/step4_evaluate.py`, `ai/model_validation_suite.py`): accuracy with 95% Wilson and bootstrap
intervals, macro-F1, per-class recall, confusion matrix, expected calibration error (0.037), accuracy under blur,
brightness, contrast and rotation, and an independent reproduction that reloads the exported ONNX file with
separately written preprocessing. Pest alert threshold chosen from a sweep (`ai/pest/pest_threshold_analysis.py`).

**Inference safeguards:** a variance-of-Laplacian blur gate (threshold 100) rejects frames before the model; visual
confidence alone never produces a HIGH risk; a missing sensor is reported as UNKNOWN, never as zero.

---

## ML roadmap

| Priority | Next step | Why |
|---|---|---|
| 1 | Qualcomm integration: compile and profile on QCS6490 via AI Hub; INT8 with Qualcomm's quantizer or quantization-aware training | Edge latency and NPU numbers; recover the INT8 accuracy lost with onnxruntime |
| 2 | Collect 20–30 canopy-angle photos from the pole's mounting position and run `ai/ood_eval.py` | Training images are close-up leaves; the deployed camera is not |
| 3 | Remove the ~5% near-duplicate test images (perceptual hash) and re-report; add a variety-held-out test | Remove optimism from the headline numbers; two-thirds of Paddy Doctor is a single variety (ADT45) |
| 4 | Class weighting or focal loss, plus more Brown Spot data | Brown Spot recall is 70%, the weakest class, most often confused with Blast |
| 5 | Confidence-threshold sweep for the disease model, as done for pests | Let the disease channel abstain on unfamiliar leaves |
| 6 | Add bacterial leaf streak, downy mildew and panicle blight from Paddy Doctor | Diseases the current 5-class model would misclassify |
| 7 | Brown planthopper and leaf folder detection (insect imagery; likely an object detector) | The most damaging Tamil Nadu pests are not yet covered |
| 8 | Nutrient-deficiency leaf imagery; yield-risk model from Tamil Nadu district crop data | Complete the problem statement's nutrient and analytics goals |

---

## What is in this folder

```
KisanNetra_SIH_Submission/
├── README.md                 this file
├── website/                  judge-facing site (open index.html; no server needed): overview,
│                             results, digital twin, fusion explorer, Wokwi simulation
├── samples/                  5 held-out test images per class, for trying the dashboard
│   ├── disease/              Bacterial Blight, Blast, Brown Spot, Healthy, Tungro
│   └── pest/                 Dead Heart, Hispa, No Pest Damage
└── project/                  complete source code
    ├── README.md             project README (architecture, results, limitations)
    ├── PROJECT_EXPLAINED.md  end-to-end technical walkthrough
    ├── ai/                   disease pipeline: data split → train → evaluate → export,
    │   │                     rule engine, inference server, dashboard, validation suite
    │   └── pest/             pest-damage pipeline, mirroring the disease one
    ├── iot/                  sensor-fusion engine, field simulator, ESP32 firmware (Wokwi)
    ├── edge/                 Qualcomm integration (future phase): AI Hub guide and script
    ├── hardware/cad/         OpenSCAD models of the sentinel station and sensor enclosure
    ├── viz/                  digital twin and fusion explorer pages
    ├── demo/                 "one leaf, two field histories" demonstration
    ├── tests/                fusion-engine tests
    └── docs/                 design documents, demo script, decision log
```

---

## How to run

Requires Python 3.10+ (developed on 3.12). Runs on **Windows, Linux and macOS** — the code contains
no platform-specific calls. Verified on Windows 11 and on Ubuntu 24.04 (Python 3.12.3), where the
models produce identical predictions. All commands run from the `project/` folder.

```bash
cd project

# Linux / macOS
python3 -m venv .venv && source .venv/bin/activate

# Windows
python -m venv .venv && .venv\Scripts\activate

pip install -r requirements.txt
```

On Debian/Ubuntu, `python3 -m venv` first needs `sudo apt install python3-venv`. PyTorch is only
required for retraining; running the models, the rules, the tests and the demo needs just
`onnxruntime`, `numpy`, `Pillow` and `pytest`.

**Run the checks** (use `python3` on Linux/macOS if `python` is not on your PATH)

```bash
python -m pytest tests/ -q               # 23 fusion-engine tests
python ai/pest/test_pest_fusion.py       # 18 pest-fusion tests
python -m demo.differential_demo         # sensors overturning an ambiguous camera reading
python iot/wokwi/micropython/test_firmware.py iot/wokwi/micropython/main.py   # 15 field scenarios
```

**Live disease prediction with the dashboard**

```bash
python ai/inference_server.py            # serves the ONNX model on http://localhost:8787
```

Then open `project/ai/dashboard.html` in a browser and drop in any image from `samples/disease/`.
Without the server running, the dashboard shows "Model offline" and never invents a prediction.

**ESP32 sensor-tier firmware:** paste `project/iot/wokwi/micropython/diagram.json` and `main.py`
into a new ESP32 project at [wokwi.com](https://wokwi.com). See `project/iot/wokwi/README.md`.

**Retraining** needs the public datasets, which are not included (they are several GB):
[Paddy Doctor](https://www.kaggle.com/competitions/paddy-disease-classification) and a lab rice-disease
image set. Place them in a folder, set `KISANNETRA_DATA` to that folder, then run
`ai/step2_clean_split.py` → `step3_train.py` → `step4_evaluate.py` → `step5_export.py`
(and the `ai/pest/pest_step*.py` equivalents). The end-to-end integration test
(`ai/step8_integration_test.py`) also expects these rebuilt splits.

---

## Stated limitations

- **Qualcomm integration is a future phase.** Everything is validated on CPU; QCS6490 profiling via
  Qualcomm AI Hub, then an RB3 Gen 2 class board, comes next.
- **No physical board yet.** Sensor values are simulated (with drift, noise and fault injection); the
  hardware is designed in CAD and simulated as ESP32 firmware.
- **Camera angle not yet tested.** Training images are close-up leaves; the pole camera looks down at
  the canopy. The evaluation script (`ai/ood_eval.py`) is ready; mounting-angle photos are not yet collected.
- **About 5% near-duplicate images** between training and test splits were measured, so headline
  accuracy is slightly optimistic.
- **N/P/K are estimates** from a low-cost conductivity-based probe, so the system recommends a soil
  test and never prescribes fertiliser.
- **INT8 is not deployed:** onnxruntime post-training quantization collapsed accuracy (22–36%); FP32
  ships. Files marked `BROKEN` in `project/ai/` are kept as evidence, not for use.

---

*Datasets are public and credited to their authors. Paddy Doctor field images were collected in Tamil Nadu.*
