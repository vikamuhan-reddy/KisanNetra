"""
Step 5 — Export to ONNX (FP32 deployment model)
SOFTWARE-ONLY VALIDATION. No Qualcomm/Hexagon/NPU hardware involved.

── INT8 Quantization Research Note ──────────────────────────────────────────
Post-training INT8 quantization with onnxruntime collapsed accuracy on every
scheme tried (FP32 reference: 87.70%):

  Attempt 1 — PyTorch dynamic:             ~25% (conv layers not quantized)
  Attempt 2 — ORT static QDQ QInt8:        22.7%
  Attempt 3 — ORT static QOperator QUInt8: 36.3%
  Attempt 4 — ORT static selective QDQ:    33.0%
  Attempt 5 — ORT quantize_dynamic:        24.7%

ROOT CAUSE: NOT YET ISOLATED. (An earlier note blamed HardSwish "producing
negative values for x < -3" — that is wrong: HardSwish(x) = x*relu6(x+3)/6 is
exactly 0 for x <= -3 and is negative only on (-3, 0), minimum -0.375 at x = -1.5.)
MobileNetV3 is known to be hard to post-training-quantize. Suspected factors:
  - depthwise convs with very different per-channel weight ranges, quantized
    per-tensor
  - squeeze-excite blocks (HardSigmoid gates that multiply activations)
  - HardSwish's small negative lobe losing resolution under per-tensor ranges
  - calibration set size / representativeness
The pest model (separate weights) collapsed the same way (34.6%), so this is a
property of architecture + PTQ recipe, not one bad checkpoint.

RESOLUTION: FP32 ONNX is the deployment model (87.70% accuracy, 5.82 MB).
Next steps, in order: Qualcomm AI Hub quantize job (edge/QUALCOMM_AIHUB_GUIDE.md);
per-channel weights with SE/HardSwish kept in higher precision; QAT; or a
ReLU-based backbone (MobileNetV2 / EfficientNet-Lite0). Whether Qualcomm's
toolchain avoids the collapse is UNTESTED until the AI Hub run.
─────────────────────────────────────────────────────────────────────────────
"""
import os
import sys
import io
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import torch
import torch.nn as nn
from torchvision import models, transforms, datasets
from torch.utils.data import DataLoader
from pathlib import Path
import onnx
import onnxruntime as ort

MODEL_PATH      = "best_model.pth"
ONNX_FP32_PATH  = "kisannetra_fp32.onnx"
DATA_DIR        = Path("dataset_split")
NUM_CLASSES     = 5

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def load_model():
    model = models.mobilenet_v3_small(weights=None)
    num_ftrs = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(num_ftrs, NUM_CLASSES)
    model.load_state_dict(torch.load("best_model.pth", map_location="cpu"))
    model.eval()
    return model

def export_onnx(model):
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy_input,
            ONNX_FP32_PATH,
            dynamo=False,
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}}
        )
    onnx_model = onnx.load(ONNX_FP32_PATH)
    onnx.checker.check_model(onnx_model)
    size_fp32 = os.path.getsize(ONNX_FP32_PATH) / (1024 * 1024)
    print(f"FP32 ONNX model exported and validated. Size: {size_fp32:.2f} MB")
    return size_fp32

def evaluate_onnx(model_path, label="FP32"):
    dataset = datasets.ImageFolder(DATA_DIR / 'test', transform)
    loader  = DataLoader(dataset, batch_size=64, shuffle=False)
    sess    = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name

    correct = total = 0
    for inputs, labels in loader:
        out   = sess.run(None, {in_name: inputs.numpy()})[0]
        preds = np.argmax(out, axis=1)
        correct += (preds == labels.numpy()).sum()
        total   += len(labels)

    acc = correct / total
    print(f"[{label}] ONNX Test Accuracy: {acc*100:.2f}%  ({correct}/{total})")
    return acc

if __name__ == '__main__':
    print("=" * 56)
    print("   STEP 5: EXPORT -- SOFTWARE-ONLY VALIDATION")
    print("   (No Qualcomm/Hexagon/NPU hardware is used)")
    print("=" * 56)

    model = load_model()

    print("\n--- Exporting FP32 ONNX (deployment model) ---")
    size_fp32 = export_onnx(model)

    print("\n--- Accuracy: FP32 ONNX ---")
    acc_fp32 = evaluate_onnx(ONNX_FP32_PATH, "FP32")

    print()
    print("=" * 56)
    print("  DEPLOYMENT MODEL: kisannetra_fp32.onnx")
    print(f"  Size:     {size_fp32:.2f} MB")
    print(f"  Accuracy: {acc_fp32*100:.2f}% (test set, 1000 images)")
    print()
    print("  INT8 STATUS: NOT DEPLOYED")
    print("  onnxruntime post-training INT8 collapses on MobileNetV3:")
    print("  5 attempts, accuracy 22-36% (near chance). Root cause")
    print("  not isolated (depthwise/SE/HardSwish ranges suspected).")
    print("  Next: Qualcomm AI Hub quantize job, per-channel + mixed")
    print("  precision, QAT, or a ReLU backbone. See docstring.")
    print("=" * 56)
    print("  SOFTWARE-ONLY VALIDATION. No Qualcomm NPU profiling.")
    print("=" * 56)
