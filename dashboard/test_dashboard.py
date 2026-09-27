"""Checks the dashboard serves the REAL models: both load, their classes load,
and each tab's endpoint runs only its own model on a real sample image.

Run from dashboard/:  .venv/Scripts/python -m pytest -q
"""
import json

from fastapi.testclient import TestClient

from app import AI_DIR, PEST_DIR, ROOT, app

client = TestClient(app)
CLASSES = {
    "disease": json.loads((AI_DIR / "classes.json").read_text(encoding="utf-8")),
    "pest": json.loads((PEST_DIR / "pest_classes.json").read_text(encoding="utf-8")),
}
MODELS = {"disease": "kisannetra_fp32.onnx", "pest": "kisannetra_pest_fp32.onnx"}


def _post(task, path):
    with path.open("rb") as f:
        return client.post(f"/api/infer/{task}", files={"image": (path.name, f, "image/jpeg")})


def test_health_both_models_and_classes_loaded():
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["status"] == "ready" and h["classes_loaded"] is True
    for task in ("disease", "pest"):
        assert h[task]["model"] == MODELS[task]
        assert h[task]["classes"] == CLASSES[task]
        assert h[task]["input_shape"][1:] == [3, 224, 224]
        assert h[task]["output_shape"][-1] == len(CLASSES[task])


def test_each_task_runs_only_its_own_model():
    for task in ("disease", "pest"):
        sample = next(iter(sorted((ROOT / "samples" / task).glob("*/*.jpg"))), None)
        assert sample is not None, f"no sample image in samples/{task}/"
        r = _post(task, sample)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True and d["task"] == task and d["inference_time_ms"] > 0
        assert "disease" not in d and "pest" not in d  # no mixed verdicts
        if d["abstained"]:
            continue
        assert d["model"] == MODELS[task]
        assert d["prediction"] in CLASSES[task]
        assert 0.0 <= d["confidence"] <= 1.0
        top = d["top_predictions"]
        assert len(top) == min(3, len(CLASSES[task]))
        assert all(p["class"] in CLASSES[task] for p in top)
        assert top[0]["class"] == d["prediction"]
        assert [p["confidence"] for p in top] == sorted((p["confidence"] for p in top), reverse=True)
        assert ("alert_threshold" in d) == (task == "pest")


def test_rejects_bad_requests_without_fake_prediction():
    assert client.post("/api/infer/weather", files={"image": ("a.jpg", b"x", "image/jpeg")}).status_code == 404

    r = client.post("/api/infer/disease", files={"image": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and r.json()["success"] is False

    r = client.post("/api/infer/pest", files={"image": ("broken.jpg", b"not really a jpeg", "image/jpeg")})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False and "prediction" not in body
