# KisanNetra — Development Progress Report

| | |
|---|---|
| **Team name** | Digital Disruptors |
| **Team ID** | SIH178 |
| **Institute** | Saveetha Engineering College |
| **Event** | Smart India Hackathon 2026 — PS 26180 (Qualcomm), Hardware |
| **Report date** | 2026-09-27 |

## Current development status

KisanNetra is in the **hardware validation and AI inference stage**.

The objective of this stage is to validate each sensor on its own, establish its output and basic
calibration, and make the camera → AI inference pipeline work and visible — before integrating the
complete system and deploying it on the Raspberry Pi.

> **Bench prototype vs. target design.** The Arduino UNO and Raspberry Pi 4 below are the hardware
> available for this validation stage. The product architecture described in
> [`PROJECT_MASTER.md`](PROJECT_MASTER.md) (low-power sensor MCU + Qualcomm QCS6490 compute tier) is
> unchanged; nothing in this report is a Qualcomm or field measurement.

Legend: ✅ completed · 🔄 in progress / testing · ⏸️ postponed · 🔜 next stage

---

## 1. Hardware available

- Raspberry Pi 4 (4 GB)
- Arduino UNO
- Capacitive soil moisture sensor v1.2 ×2
- DHT11 temperature & humidity sensor
- LDR light sensor module (3-pin, digital output)
- HC-SR04 ultrasonic sensor
- Raspberry Pi camera modules
- Breadboard, jumper wires, 10 kΩ resistor
- Phone camera (temporary image acquisition)

The Arduino UNO is used for sensor validation before the sensing pipeline moves to the Raspberry Pi.

**Wiring, test sketches and expected output for every sensor:**
[`project/hardware/arduino/SENSOR_SETUP.md`](project/hardware/arduino/SENSOR_SETUP.md)

---

## 2. Arduino ↔ laptop communication — ✅ Completed

The Arduino UNO communicates with the development laptop over USB serial:

```text
Port: COM12    Baud: 115200
```

A Python serial reader ([`project/hardware/arduino/kisan_serial_test.py`](project/hardware/arduino/kisan_serial_test.py))
receives the Arduino output line by line:

```text
Arduino → KISANNETRA_HEARTBEAT
```

Each sensor sketch announces itself (`KISANNETRA_<SENSOR>`, `STATUS: READY`) and then prints
`KEY=value` lines:

| Sensor | Serial output keys | Error output |
|---|---|---|
| Soil moisture #1 | `RAW_ADC`, `MOISTURE_PERCENT` | — |
| DHT11 | `TEMPERATURE_C`, `HUMIDITY_PERCENT` | `DHT11_ERROR=READ_FAILED` |
| LDR | `LIGHT_STATUS=BRIGHT` / `DARK` | — |
| HC-SR04 | `DISTANCE_CM` | `DISTANCE_STATUS=NO_ECHO` |

Errors are reported as errors, never replaced by a made-up value — the same rule the KisanNetra
rule engine follows.

---

## 3. Soil moisture sensor #1 — ✅ Tested, basic calibration

```text
Sensor          Arduino UNO
VCC      →      5V
GND      →      GND
AO       →      A0
DO       →      not connected
```

**Calibration (two-point):** dry soil ≈ **1011 ADC**, wet soil ≈ **265 ADC**.
`moisture % = (DRY − raw) / (DRY − WET) × 100`, clamped to 0–100.

| Condition | Observed |
|---|---|
| Dry soil | ≈ 0–1 % |
| Wet soil | ≈ 94–95 % |

**Maps to:** `surface_moisture`

---

## 4. DHT11 temperature & humidity — ✅ Tested

```text
DHT11           Arduino UNO
VCC      →      5V
GND      →      GND
DATA     →      D2
```

Typical readings during testing: **≈ 32 °C, ≈ 64 %RH**.

**Maps to:** `air_temperature`, `humidity`

---

## 5. LDR light sensor — ✅ Basic test

```text
LDR module      Arduino UNO
VCC      →      5V
GND      →      GND
DO       →      D3
```

Output: `LIGHT_STATUS=BRIGHT` or `LIGHT_STATUS=DARK`. The module's onboard potentiometer sets the
threshold. No external resistor is needed for the digital output.

**Limitation:** this is a relative bright/dark state, not a calibrated lux value.

**Maps to:** `light_status` now → `light_lux` later (needs an analog/digital lux readout, e.g. BH1750).

---

## 6. HC-SR04 ultrasonic — 🔄 Sensor testing

Intended use: irrigation tank water level.

```text
HC-SR04         Arduino UNO
VCC      →      5V
GND      →      GND
TRIG     →      D7
ECHO     →      D8
```

Currently measures distance to the nearest surface: `distance_cm = echo_time × 0.0343 / 2`,
e.g. `DISTANCE_CM=10.4`.

```text
Now:     HC-SR04 → distance_cm
Later:   distance_cm → water depth (tank geometry) → tank_level %
```

**Not yet a tank percentage** — tank dimensions and calibration are still to be done.

---

## 7. Soil moisture sensor #2 — ⏸️ Postponed

Reserved for **root-zone moisture**. Planned wiring: AO → **A1** (VCC 5V, GND, DO not connected).
Not calibrated yet: a meaningful reading needs the probe placed properly in the root zone.

**Maps to:** `root_moisture`

---

## 8. Camera / image input — 🔄 Phone camera in use

The Raspberry Pi camera hardware has been investigated, but reliable capture is not yet the
development input. Leaf images are taken with a **phone camera** and uploaded to the AI dashboard:

```text
Phone camera → leaf image → upload to dashboard → KisanNetra AI inference
```

This lets the AI pipeline be developed independently of the Raspberry Pi camera.

---

## 9. AI inference dashboard — ✅ Built and tested (laptop CPU)

A local web dashboard ([`dashboard/`](dashboard/README.md)) runs the **real** KisanNetra models on an
uploaded image. It has two separate tabs so disease and pest results are never mixed:

| Tab | Model | Classes |
|---|---|---|
| Disease Detection | `project/ai/kisannetra_fp32.onnx` | Bacterial Blight, Blast, Brown Spot, Healthy, Tungro |
| Pest Detection | `project/ai/pest/kisannetra_pest_fp32.onnx` | Dead Heart, Hispa, No Pest Damage |

- Runs on **ONNX Runtime, CPU**. The broken INT8 variants are not used.
- Preprocessing reused from `project/ai/inference_server.py` (224×224 RGB, ImageNet normalisation).
- Shows model status, uploaded image, prediction, confidence, top predictions, inference time and a
  clear success / failure state. Real errors are shown; no fallback prediction is ever invented.
- **Blur gate:** a blurry photo is rejected before the model runs.
- **Pest alert threshold 0.80** (from `pest_fusion_rule.py`): lower-confidence pest calls are shown
  as *INCONCLUSIVE*, not as detections.
- Start: `cd dashboard` → `.venv/Scripts/python -m uvicorn app:app --port 8000` → http://127.0.0.1:8000

**Results on the bundled sample images (2026-09-27):**

| Test | Result |
|---|---|
| Disease model on `samples/disease/` (25 images) | 20 / 25 correct |
| Pest model on `samples/pest/` (15 images) | 15 / 15 correct |
| Model time per image (warm) | ≈ 2 ms (desktop CPU — **not** a Qualcomm figure) |

Reference accuracy from the full held-out test sets: disease **87.70 %** (n = 1,000), pest
**94.98 %** (n = 717).

**Limitations found during testing — stated openly:**
1. **Pest model on diseased leaves:** confident false pest calls on 13 of 20 diseased sample leaves.
   It was trained on Dead Heart, Hispa and *healthy* leaves only. Hence the separate tabs.
2. **Wide top-down photos:** a top-down phone photo of a Hispa-infested clump read *No Pest Damage*;
   crops of the damaged leaves read Hispa at 80–95 %. The damage is too small after resizing to
   224×224. This confirms the *camera angle untested* risk and is the main retraining target.
3. **Internet / new-source images** can be misclassified (e.g. a Bacterial Blight photo read as
   Blast). Validation on the team's own labelled phone photos is still to be done.

---

## 10. Sensor → KisanNetra mapping

```text
Soil moisture #1   → surface_moisture
Soil moisture #2   → root_moisture          (postponed)
DHT11              → air_temperature, humidity
LDR                → light_status  (→ light_lux later)
HC-SR04            → distance_cm   (→ tank_level later)
Phone camera       → KisanNetra AI → disease class / pest-damage class
```

## 11. Arduino pin assignment (combined prototype, planned)

```text
Sensor                  Arduino pin
Soil moisture #1 AO     A0
Soil moisture #2 AO     A1   (later)
DHT11 DATA              D2
LDR DO                  D3
HC-SR04 TRIG            D7
HC-SR04 ECHO            D8
All VCC → 5V            All GND → GND
```

Each sensor has been tested with its own sketch; the single combined sketch is not written yet.

---

## 12. Progress summary

| Component | Status |
|---|---|
| Arduino ↔ laptop serial communication | ✅ Completed |
| Soil moisture #1 | ✅ Tested |
| Soil moisture #1 calibration | ✅ Basic (two-point) |
| DHT11 | ✅ Tested |
| LDR | ✅ Basic test (bright/dark) |
| HC-SR04 | 🔄 Testing |
| Soil moisture #2 | ⏸️ Postponed |
| Phone image acquisition | 🔄 In use |
| AI inference dashboard — disease model | ✅ Built and tested |
| AI inference dashboard — pest model | ✅ Built and tested |
| AI validation on own labelled field photos | 🔜 Next stage |
| Combined Arduino sensor sketch | 🔜 Next stage |
| Sensor data standardisation (sensor contract) | 🔜 Next stage |
| Sensor + AI integration | 🔜 Next stage |
| Decision / fusion engine on live data | 🔜 Next stage (engine exists; runs on simulated data today) |
| Raspberry Pi deployment | 🔜 Later stage |
| Raspberry Pi camera capture | 🔜 Later stage |
| Complete field prototype | 🔜 Later stage |

**Software checks passing:** 31 automated tests in `project/` (fusion engine, AWD irrigation) and
3 dashboard tests (models load, per-tab inference, bad-input rejection).

---

## 13. Next development stage

1. Finish HC-SR04 testing and tank-level calibration (tank geometry → `tank_level %`).
2. Place and calibrate soil moisture sensor #2 in the root zone.
3. Write the combined Arduino sketch on the planned pin layout.
4. Collect the team's own labelled phone photos (including top-down canopy shots) and measure
   both models on them; retrain the pest model with diseased leaves labelled *No Pest Damage*.
5. Standardise the Arduino output into the KisanNetra sensor contract (`sensor_contract.py` fields
   and `VALID` / `FAILED` status per channel).
6. Feed live sensor readings and AI results into the existing rule / fusion engine.
7. Test the complete pipeline locally.
8. Move the validated system to the Raspberry Pi.
9. Integrate the Raspberry Pi camera once capture is reliable.
10. Field-level testing.

---

## 14. Current project stage

**Hardware Validation + AI Inference Stage.**

Individual sensors are being validated on real hardware, and the camera → AI inference pipeline now
runs the real disease and pest models through a working dashboard. Once the remaining sensors are
calibrated, these components will be integrated into the complete KisanNetra pipeline.

This report records progress, not a finished system: the project has moved from concept and
simulation to validating real hardware components and real AI inference.
