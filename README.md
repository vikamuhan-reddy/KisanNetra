# KisanNetra — Edge-AI Field Sentinel for Paddy

**Smart India Hackathon 2026 · Problem Statement 26180 · Qualcomm Inc. · Category: Hardware**
**Theme:** Agriculture, FoodTech & Rural Development · **Scope:** rice (paddy), Thanjavur, Tamil Nadu

| | |
|---|---|
| **Team name** | _TODO_ |
| **Team ID** | _TODO_ |
| **Institute** | _TODO_ |

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
| Read the full technical walkthrough | [`project/PROJECT_EXPLAINED.md`](project/PROJECT_EXPLAINED.md) |
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

## What is in this folder

```
KisanNetra_SIH_Submission/
├── README.md                 this file
├── website/                  judge-facing site (open index.html; no internet or server needed)
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

Requires Python 3.10+ (developed on 3.12). All commands run from the `project/` folder.

```bash
cd project
python -m venv .venv
.venv/Scripts/activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

**Run the checks**

```bash
python -m pytest tests/ -q               # 23 fusion-engine tests
python ai/pest/test_pest_fusion.py       # 18 pest-fusion tests
python -m demo.differential_demo         # sensors overturning an ambiguous camera reading
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
