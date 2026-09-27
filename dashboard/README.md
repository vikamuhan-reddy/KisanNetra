# KisanNetra — Camera → AI Inference Dashboard (Disease + Pest)

A local web page that proves the camera → AI step of KisanNetra works. It has **two tabs**:

- **Disease Detection** — runs only the real disease model
- **Pest Detection** — runs only the real pest-damage model

Each tab has its own image upload and its own result, and calls its own endpoint, so a disease
result and a pest result are never shown together or confused. Switching tabs keeps each tab's
image and result.

```
PHONE / CAMERA IMAGE → IMAGE INPUT → KISANNETRA DISEASE (or PEST) MODEL → CLASSIFICATION → CONFIDENCE + TOP PREDICTIONS
```

**Scope (for the SIH progress demo):** disease and pest-damage classification from one image only. No sensors,
no fusion/decision engine, no Raspberry Pi, no live camera stream — those come later.

## What it runs

| | |
|---|---|
| Disease model | `project/ai/kisannetra_fp32.onnx` + `classes.json` → Bacterial Blight, Blast, Brown Spot, Healthy, Tungro. Output `[batch,5]` |
| Pest model | `project/ai/pest/kisannetra_pest_fp32.onnx` + `pest_classes.json` → Dead Heart, Hispa, No Pest Damage. Output `[batch,3]` |
| INT8 files | **not** used (both are broken, see `FLAWS.md`) |
| Pipeline | Helpers reused unchanged from `project/ai/inference_server.py`: blur gate → RGB → resize 224×224 → ImageNet mean/std → NCHW `[1,3,224,224]` → ONNX Runtime (CPU) → softmax. Both models were trained with this identical transform |
| Pest alert threshold | 0.80, imported from `project/ai/pest/pest_fusion_rule.py`. A pest call below it is labelled *INCONCLUSIVE — the field node would re-image* |
| Separation | Each tab runs only its own model; the two are never run together or averaged |

Nothing is hard-coded or faked. If the model can't load or an image can't be read, the page
shows the real error. A blurry photo (sharpness score < 100) is **rejected before either
model runs** and shown as "too blurry", never as a disease or pest.

## 1. Install (once)

Needs **Python 3.12** (`inference_server.py` imports `cgi`, which Python 3.13+ removed).
From the `dashboard/` folder:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## 2. Start the backend (this also serves the frontend)

```powershell
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

In **Git Bash** use forward slashes (bash eats backslashes):

```bash
.venv/Scripts/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Don't re-run the `venv` step while the server is running — Windows locks `python.exe` and it
fails with "Permission denied".

On start it loads the model, checks `classes.json` matches the model's 5 outputs, and runs one
real sample image from `samples/disease/` as a self-check.

## 3. Frontend

Nothing to start — the same process serves it.

## 4. Open

**http://127.0.0.1:8000**

The **AI MODEL STATUS** card should show **READY**. If it shows **ERROR**, the message under it
is the real reason (e.g. missing model file).

## 5. Upload an image

Pick the **Disease Detection** or **Pest Detection** tab, then click **Choose Leaf Image** (or drag a photo onto the box). JPG, JPEG or PNG. Test images are in
`samples/disease/<class>/`.

## 6. Run inference

Click **RUN DISEASE INFERENCE** (or **RUN PEST INFERENCE**). The result shows the predicted class,
confidence bar, top predictions, model time (~2 ms on a desktop CPU once warm; the first run after
startup is slower), total time (decode + blur check + model), file name and sharpness. In the Pest
tab, a pest call below 0.80 is labelled INCONCLUSIVE.
Test images: `samples/disease/<class>/` and `samples/pest/<class>/`.

## Demo from a phone

Start the server with `--host 0.0.0.0` instead of `127.0.0.1`, put the phone on the same Wi-Fi,
and open `http://<laptop-IP>:8000` on the phone. Windows may ask to allow Python through the
firewall. The upload button then offers the phone camera.

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{"status": "ready", "classes_loaded": true, "disease": {"status": "ready", "model": "kisannetra_fp32.onnx", "classes": [...], "input_shape": [...]}, "pest": {...}, "startup_check": {...}}` (HTTP 503 if either model is not ready; each model reports its own `error`) |
| POST | `/api/infer/disease` | multipart field `image` → `{"success": true, "task": "disease", "abstained": false, "prediction": "Blast", "confidence": 0.97, "top_predictions": [{"class": ..., "confidence": ...}], "model_time_ms": 2.1, "model": "kisannetra_fp32.onnx", "inference_time_ms": 45.3, "blur_score": 631.3}` |
| POST | `/api/infer/pest` | same shape for the pest model, plus `"alert_threshold": 0.8, "below_threshold": false, "no_damage": false` |

Errors return `{"success": false, "error": "..."}` with HTTP 400 (bad type/empty), 413 (> 15 MB),
404 (unknown task), 422 (unreadable image) or 503 (model not ready).

## Test

```powershell
.venv\Scripts\python -m pytest -q
```

Checks both models and their classes load, each endpoint runs only its own model on a real sample
(only its own classes come back), and bad requests return an error instead of a prediction.

## Limits to state in the demo

**Measured on the bundled samples (2026-09-27):** pest model 15/15 correct on `samples/pest/`;
disease model 20/25 on `samples/disease/`. But each model only knows its own classes:

- **Pest model on diseased leaves:** raised a confident pest call (≥ 0.80) on **13 of 20** diseased
  samples (e.g. Blast → Dead Heart 95 %). It was trained on Dead Heart, Hispa and *healthy* leaves only
  and has never seen disease lesions. Its measured 3.04 % false-alert rate is on healthy leaves only.
- **Disease model on pest-damaged leaves:** always names one of its 5 diseases (no pest class).
- That's why the tabs are separate: test disease photos in the Disease tab and pest photos in the Pest
  tab. Each result states its model's scope on screen. In the full system these calls are corroborated
  by sensors before any HIGH alert.
- **Pest model and wide top-down photos:** a 400×531 top-down photo of a Hispa-infested clump was read
  as No Pest Damage (89 %); crops of the damaged leaves read Hispa at 80–95 %. The damage is too small
  after resizing to 224×224. Use close, side-on photos like `samples/pest/`.

- Accuracy is 87.70 % on 1,000 held-out images (mostly close-up field leaf photos). Photos
  taken differently (whole plants, far away, other crops) are outside what it was trained on,
  and it will still pick one of its 5 classes.
- Runs on a laptop CPU, not yet on the Qualcomm target.
- Advisory only.
