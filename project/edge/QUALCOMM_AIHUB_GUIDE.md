# Qualcomm AI Hub — Run KisanNetra on Real Snapdragon Silicon

**Goal:** turn "Qualcomm is our migration target" into a measured number on a slide:

> *Disease model on Qualcomm QCS6490 (via AI Hub): **X ms** per inference, **Y %** of layers on the Hexagon NPU, **Z MB** peak memory, on-device predictions match CPU on **N/N** test images.*

**Status:** future integration phase — not yet run. Until it is, every figure in this repository is a
software-only CPU measurement and must never be presented as a Qualcomm number.
**Time budget when run:** ~1.5–2 h (mostly waiting in the AI Hub queue).

---

## What you will produce

| Output | Where | Used for |
|---|---|---|
| Latency, peak memory, compute-unit split (NPU/GPU/CPU) | `benchmarks/qualcomm_aihub_disease.json`, `..._pest.json` | Slide + README |
| Profile job URL (link on AI Hub) | printed + saved in the JSON | Proof for judges |
| On-device vs CPU agreement on real test images | same JSON | Shows the compiled model is still *correct*, not just fast |
| *(optional)* INT8 accuracy via AI Hub quantization | `..._int8.json` | Answers "why is INT8 broken?" |

---

## Step 1 — Account and token (10 min)

1. Go to **https://aihub.qualcomm.com** → *Sign up* with a Qualcomm ID (free).
2. Sign in → **Settings** → copy your **API token**.
3. Do not commit the token anywhere. The next step stores it in `~/.qai_hub/client.ini`.

## Step 2 — Install (5 min)

Run from `smart-farming-edge-ai/`, using the project venv (it already has `onnx`, `onnxruntime`, `numpy`, `Pillow`):

```bash
ai/.venv/Scripts/python.exe -m pip install qai-hub
ai/.venv/Scripts/qai-hub.exe configure --api_token <YOUR_TOKEN>
```

## Step 3 — Pick the device (5 min)

```bash
ai/.venv/Scripts/qai-hub.exe list-devices
```

Choose the first one that appears in the list:

1. `QCS6490 (Proxy)` — the SoC of our stated target board (RB3 Gen 2). **Preferred.**
2. `RB3 Gen 2 (Proxy)`
3. Any other `QCS` / `Snapdragon` device — then say its exact name on the slide.

Copy the name **exactly**, including the `(Proxy)` suffix.

## Step 4 — Save the script (2 min)

Save the following as `edge/aihub_run.py`:

```python
"""Compile, profile and verify KisanNetra models on Qualcomm AI Hub.

Usage (from smart-farming-edge-ai/):
    ai/.venv/Scripts/python.exe edge/aihub_run.py --device "QCS6490 (Proxy)"
    ai/.venv/Scripts/python.exe edge/aihub_run.py --device "QCS6490 (Proxy)" --int8
"""
import argparse, json, random
from collections import Counter
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx.tools.update_model_dims import update_inputs_outputs_dims
from PIL import Image
import qai_hub as hub

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks"
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

MODELS = {  # name: (onnx, classes.json, split root)
    "disease": ("ai/kisannetra_fp32.onnx", "ai/classes.json", "ai/dataset_split"),
    "pest": ("ai/pest/kisannetra_pest_fp32.onnx", "ai/pest/pest_classes.json", "ai/pest/pest_dataset_split"),
}


def preprocess(path):
    # Identical to ai/inference_server.py:preprocess
    img = Image.open(path).convert("RGB").resize((224, 224), Image.BILINEAR)
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - MEAN) / STD
    return arr.transpose(2, 0, 1)[np.newaxis].astype(np.float32)


def sample(split_dir, classes, per_class, seed=0):
    rng = random.Random(seed)
    picks = []
    for label, cls in enumerate(classes):
        files = sorted((split_dir / cls).glob("*.jpg"))
        picks += [(f, label) for f in rng.sample(files, min(per_class, len(files)))]
    return picks


def static_copy(onnx_path, n_classes):
    # AI Hub compile/quantize need fixed shapes; our export has a dynamic batch dim.
    m = onnx.load(onnx_path)
    m = update_inputs_outputs_dims(m, {"input": [1, 3, 224, 224]}, {"output": [1, n_classes]})
    dst = OUT / f"{Path(onnx_path).stem}_static.onnx"
    onnx.save(m, dst)
    return dst


def summarize_profile(profile):
    ex = profile.get("execution_summary", {})
    units = Counter(l.get("compute_unit", "?") for l in profile.get("execution_detail", []))
    total = sum(units.values()) or 1
    return {
        "latency_ms": ex.get("estimated_inference_time", 0) / 1000,
        "peak_memory_mb": (ex.get("estimated_inference_peak_memory") or 0) / 1e6,
        "layers_by_unit": dict(units),
        "npu_layer_pct": round(100 * units.get("NPU", 0) / total, 1),
    }


def run(name, device, per_class, int8):
    onnx_path, classes_path, split = (ROOT / p for p in MODELS[name])
    classes = json.loads(classes_path.read_text())
    model = str(static_copy(onnx_path, len(classes)))
    tag = f"{name}_int8" if int8 else name

    if int8:
        calib = [preprocess(f) for f, _ in sample(split / "train", classes, 20, seed=1)]
        qjob = hub.submit_quantize_job(
            model=model, calibration_data={"input": calib},
            weights_dtype=hub.QuantizeDtype.INT8, activations_dtype=hub.QuantizeDtype.INT8)
        model = qjob.get_target_model()
        print(f"[{tag}] quantize job: {qjob.url}")

    cjob = hub.submit_compile_job(model=model, device=device, options="--target_runtime tflite")
    target = cjob.get_target_model()
    print(f"[{tag}] compile job: {cjob.url}")

    pjob = hub.submit_profile_job(model=target, device=device)
    profile = pjob.download_profile()
    print(f"[{tag}] profile job: {pjob.url}")

    # Correctness: same images on-device and on local CPU ONNX Runtime.
    picks = sample(split / "test", classes, per_class)
    inputs = [preprocess(f) for f, _ in picks]
    ijob = hub.submit_inference_job(model=target, device=device, inputs={"input": inputs})
    dev_out = next(iter(ijob.download_output_data().values()))
    sess = ort.InferenceSession(str(onnx_path))
    cpu_pred = [int(sess.run(None, {"input": x})[0].argmax()) for x in inputs]
    dev_pred = [int(np.asarray(o).argmax()) for o in dev_out]
    labels = [l for _, l in picks]

    result = {
        "model": name, "precision": "INT8 (AI Hub quantize)" if int8 else "FP32",
        "device": device.name, "runtime": "tflite",
        **summarize_profile(profile),
        "n_images": len(picks),
        "device_accuracy": float(np.mean([p == l for p, l in zip(dev_pred, labels)])),
        "cpu_fp32_accuracy_same_images": float(np.mean([p == l for p, l in zip(cpu_pred, labels)])),
        "device_matches_cpu_top1": int(sum(d == c for d, c in zip(dev_pred, cpu_pred))),
        "jobs": {"compile": cjob.url, "profile": pjob.url, "inference": ijob.url},
        "note": "Measured on a Qualcomm AI Hub hosted device, not on our own board.",
    }
    (OUT / f"qualcomm_aihub_{tag}.json").write_text(json.dumps(result, indent=2))
    (OUT / f"qualcomm_aihub_{tag}_profile_raw.json").write_text(json.dumps(profile, indent=2, default=str))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="QCS6490 (Proxy)")
    ap.add_argument("--models", nargs="+", default=["disease", "pest"])
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--int8", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    dev = hub.Device(a.device)
    for m in a.models:
        run(m, dev, a.per_class, a.int8)
```

## Step 5 — Run FP32 (30–45 min, mostly waiting in the AI Hub queue)

```bash
ai/.venv/Scripts/python.exe edge/aihub_run.py --device "QCS6490 (Proxy)"
```

While it waits, open the printed **profile job URL** in the browser. The AI Hub web page shows the
per-layer compute-unit breakdown. **Screenshot it** for the slide.

**Check before trusting the number:** `device_matches_cpu_top1` should be close to `n_images`
(e.g. 49/50). If it is far off, the compiled model is not equivalent. Do not present the latency.

## Step 6 — (Optional) INT8 via AI Hub

```bash
ai/.venv/Scripts/python.exe edge/aihub_run.py --device "QCS6490 (Proxy)" --int8
```

This uses **Qualcomm's own quantizer** with 100 calibration images from the train split. That is the
correct path, instead of the onnxruntime quantizer that collapsed to 22–35%.

| Outcome | What to say |
|---|---|
| `device_accuracy` within ~2–3 pp of `cpu_fp32_accuracy_same_images` | *"INT8 recovered with Qualcomm's quantizer: A% vs B% FP32, C ms."* Strong result. |
| Still collapsed | *"INT8 still fails on MobileNetV3; next step is quantization-aware training or a ReLU-based backbone (EfficientNet-Lite0)."* Present FP32 numbers only. |

Note: 10 images per class is a sanity check, not an accuracy claim. Quote it as "N/N agreement on
a 50-image spot check", not as model accuracy.

---

## Step 7 — Put it on the slide and in the README

**Slide table:**

| Model | Precision | Device | Latency | NPU layers | Peak mem | On-device = CPU |
|---|---|---|---|---|---|---|
| Disease (5-class) | FP32 | QCS6490 (AI Hub) | __ ms | __ % | __ MB | __/50 |
| Pest (3-class) | FP32 | QCS6490 (AI Hub) | __ ms | __ % | __ MB | __/30 |
| Disease | INT8 (AI Hub) | QCS6490 (AI Hub) | __ ms | __ % | __ MB | __/50 |

**True wording (use this):**
- "Measured on Qualcomm QCS6490 via Qualcomm AI Hub hosted devices."
- "X % of layers executed on the Hexagon NPU" (only if the profile shows it).

**False wording (never use this):**
- "Running on our Qualcomm board" (we have no board).
- "NPU-accelerated" if the profile shows mostly CPU/GPU.
- Any number from the desktop CPU run presented as a Qualcomm number.

Then update the README "Validation level B" row from ⏳ to ✅ with the date and the profile URL.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Device not found` | The name must match `list-devices` exactly, including `(Proxy)`. |
| Compile fails on shapes | The script already makes a static-shape copy; check that `benchmarks/*_static.onnx` exists. |
| Compile fails on an op | Try `options="--target_runtime qnn_context_binary"` or `"--target_runtime onnx"` in `submit_compile_job`. |
| Job stuck "queued" > 20 min | Normal at busy times. Keep working on slides; do not resubmit duplicates. |
| Profile shows mostly CPU | FP32 often cannot run fully on the NPU. Report it honestly; that is why Step 6 (INT8) exists. |
| A key is missing in `execution_summary` | Open `*_profile_raw.json` and read the real key names, or fill the slide from the web page. |
| `submit_quantize_job` errors | Skip Step 6. The FP32 numbers alone are the main win. |
| Nothing works | Keep the status as "future integration" everywhere; never substitute a CPU number. |

API reference if a call signature has changed: https://app.aihub.qualcomm.com/docs/
