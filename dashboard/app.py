"""KisanNetra camera -> AI inference dashboard (local demo).

Two real models, one per dashboard tab (never run together):
  - disease: project/ai/kisannetra_fp32.onnx            + classes.json
  - pest:    project/ai/pest/kisannetra_pest_fp32.onnx  + pest_classes.json

Blur gate, preprocessing (RGB, 224x224, ImageNet normalisation, NCHW) and
softmax come from project/ai/inference_server.py; both models were trained
with the identical transform (step3_train.py / pest_step3_train.py), so the
same preprocessing serves both. The pest alert threshold comes from
project/ai/pest/pest_fusion_rule.py. Nothing here re-implements them.

Run:  .venv/Scripts/python -m uvicorn app:app --port 8000   (from dashboard/)
"""
import json
import sys
import time
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
AI_DIR = ROOT / "project" / "ai"
PEST_DIR = AI_DIR / "pest"
FRONTEND = Path(__file__).resolve().parent / "frontend"

ALLOWED_EXT = {".jpg", ".jpeg", ".png"}
MAX_BYTES = 15 * 1024 * 1024  # phone photos are a few MB; reject anything absurd

sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(PEST_DIR))

# ── Disease model, loaded by the existing module ────────────────────────────
# inference_server checks the model file, loads classes.json, opens the ONNX
# session and refuses to start if class count != model outputs.
LOAD_ERROR = None
ks = None
try:
    import inference_server as ks  # noqa: E402
except Exception as exc:  # surfaced verbatim in /api/health and the UI
    LOAD_ERROR = f"{type(exc).__name__}: {exc}"

# ── Pest model, same checks as inference_server applies to disease ──────────
PEST_MODEL = PEST_DIR / "kisannetra_pest_fp32.onnx"
PEST_ERROR = None
PEST_SESSION = PEST_CLASSES = None
PEST_THRESHOLD, PEST_NEGATIVE = 0.80, "No Pest Damage"
try:
    import onnxruntime as ort
    from pest_fusion_rule import ALERT_CONFIDENCE_THRESHOLD as PEST_THRESHOLD  # noqa: E402
    from pest_fusion_rule import NEGATIVE_CLASS as PEST_NEGATIVE  # noqa: E402

    if not PEST_MODEL.exists():
        raise FileNotFoundError(f"Pest model not found: {PEST_MODEL}")
    PEST_CLASSES = json.loads((PEST_DIR / "pest_classes.json").read_text(encoding="utf-8"))
    PEST_SESSION = ort.InferenceSession(str(PEST_MODEL), providers=["CPUExecutionProvider"])
    n_out = PEST_SESSION.get_outputs()[0].shape[-1]
    if len(PEST_CLASSES) != n_out:
        raise RuntimeError(f"pest_classes.json has {len(PEST_CLASSES)} entries but the "
                           f"model emits {n_out} logits. Refusing to serve mislabelled predictions.")
except Exception as exc:
    PEST_ERROR = f"{type(exc).__name__}: {exc}"
    PEST_SESSION = None


def _io(session) -> dict:
    inp, out = session.get_inputs()[0], session.get_outputs()[0]
    return {"input_name": inp.name, "input_shape": inp.shape,
            "output_shape": out.shape, "providers": session.get_providers()}


def _classify(session, classes, tensor) -> dict:
    t0 = time.perf_counter()
    logits = session.run(None, {session.get_inputs()[0].name: tensor})[0][0]
    ms = (time.perf_counter() - t0) * 1000.0
    probs = ks.softmax(logits)
    ranked = sorted(zip(classes, probs.tolist()), key=lambda kv: kv[1], reverse=True)
    return {
        "prediction": ranked[0][0],
        "confidence": ranked[0][1],
        "top_predictions": [{"class": c, "confidence": p} for c, p in ranked[:3]],
        "model_time_ms": round(ms, 2),
    }


def _infer(img_bytes: bytes, task: str) -> dict:
    """Blur gate, preprocess, then run ONLY the requested model ("disease" or "pest").

    The two models are deliberately never run together here: each tab of the
    dashboard answers one question, so a pest call can't be read as a disease
    call or vice versa.
    """
    t0 = time.perf_counter()
    blur = ks.compute_vol(img_bytes)
    out = {"success": True, "task": task, "blur_score": round(blur, 1),
           "blur_threshold": ks.BLUR_THRESHOLD}

    if blur < ks.BLUR_THRESHOLD:
        # Rejected before the model runs. Not a disease, not a pest.
        out.update(abstained=True, prediction=None, confidence=None, top_predictions=[],
                   message=f"Blur score {blur:.1f} is below threshold {ks.BLUR_THRESHOLD}. "
                           "Frame discarded — not fed to the model.")
    else:
        tensor = ks.preprocess(img_bytes)
        if task == "disease":
            out.update(_classify(ks.SESSION, ks.CLASSES, tensor), model=ks.MODEL_PATH.name)
        else:
            r = _classify(PEST_SESSION, PEST_CLASSES, tensor)
            out.update(
                r,
                model=PEST_MODEL.name,
                alert_threshold=PEST_THRESHOLD,
                no_damage=r["prediction"] == PEST_NEGATIVE,
                # pest_fusion_rule: below threshold the node reports INCONCLUSIVE
                below_threshold=(r["prediction"] != PEST_NEGATIVE
                                 and r["confidence"] < PEST_THRESHOLD),
            )
        out["abstained"] = False

    out["inference_time_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
    return out


# ── Startup validation on a real sample image (no invented input) ───────────
STARTUP_CHECK = None
if ks is not None:
    STARTUP_CHECK = {}
    for task in ("disease", "pest"):
        if task == "pest" and PEST_SESSION is None:
            continue
        sample = next(iter(sorted((ROOT / "samples" / task).glob("*/*.jpg"))), None)
        if sample is None:
            STARTUP_CHECK[task] = {"ran": False, "note": f"no sample image in samples/{task}/"}
            continue
        try:
            res = _infer(sample.read_bytes(), task)
            STARTUP_CHECK[task] = {"ran": True, "image": f"{sample.parent.name}/{sample.name}",
                                   "prediction": res["prediction"],
                                   "inference_time_ms": res["inference_time_ms"]}
        except Exception as exc:
            if task == "disease":
                LOAD_ERROR = f"Startup inference failed: {type(exc).__name__}: {exc}"
            else:
                PEST_ERROR, PEST_SESSION = f"Startup inference failed: {type(exc).__name__}: {exc}", None

app = FastAPI(title="KisanNetra Inference Dashboard")


@app.get("/api/health")
def health():
    disease_ok = ks is not None and not LOAD_ERROR
    pest_ok = PEST_SESSION is not None
    body = {
        "status": "ready" if disease_ok and pest_ok else "error",
        "framework": "ONNX Runtime",
        "device": "CPU",
        "disease": ({"status": "ready", "model": ks.MODEL_PATH.name,
                     "classes": ks.CLASSES, **_io(ks.SESSION)} if disease_ok else
                    {"status": "error", "model": "kisannetra_fp32.onnx", "error": LOAD_ERROR}),
        "pest": ({"status": "ready", "model": PEST_MODEL.name, "classes": PEST_CLASSES,
                  "alert_threshold": PEST_THRESHOLD, **_io(PEST_SESSION)} if pest_ok else
                 {"status": "error", "model": PEST_MODEL.name, "error": PEST_ERROR}),
        "classes_loaded": disease_ok and pest_ok,
        "startup_check": STARTUP_CHECK,
    }
    return body if body["status"] == "ready" else JSONResponse(status_code=503, content=body)


@app.post("/api/infer/{task}")
async def infer(task: str, image: UploadFile = File(...)):
    def fail(status, msg):
        return JSONResponse(status_code=status, content={"success": False, "error": msg})

    if task not in ("disease", "pest"):
        return fail(404, f"Unknown task '{task}'. Use /api/infer/disease or /api/infer/pest.")
    # The disease module supplies the shared blur gate and preprocessing too.
    if ks is None or LOAD_ERROR:
        return fail(503, f"Disease model / inference pipeline not ready: {LOAD_ERROR}")
    if task == "pest" and PEST_SESSION is None:
        return fail(503, f"Pest model not ready: {PEST_ERROR}")

    ext = Path(image.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        return fail(400, f"Unsupported file type '{ext or 'none'}'. Use JPG, JPEG or PNG.")

    data = await image.read()
    if not data:
        return fail(400, "The uploaded file is empty.")
    if len(data) > MAX_BYTES:
        return fail(413, f"Image is {len(data) / 1e6:.1f} MB; limit is {MAX_BYTES // 1024 // 1024} MB.")

    try:
        result = _infer(data, task)
    except Exception as exc:
        return fail(422, f"Could not run inference on this file: {type(exc).__name__}: {exc}")

    result["input_filename"] = image.filename
    return result


# Frontend is served by the same process: one command, one URL.
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
