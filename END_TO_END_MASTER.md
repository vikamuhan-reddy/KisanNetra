# KisanNetra — End-to-End Master (Sensor → Data → AI → Fusion → Edge Cases)

**What this file is for.** It is the source script for a video (and any explainer) that walks
through the whole system in the order data actually moves:

```
HARDWARE  →  HOW EACH PART MEASURES  →  RAW SIGNAL  →  JSON  →  AI MODELS  →  MULTIMODAL FUSION  →  EDGE CASE  →  ADVISORY / VALVE
```

Every threshold, field name, JSON shape and rule below is taken from the code. File references
are given so each claim can be checked. Companion file: [`PROJECT_MASTER.md`](PROJECT_MASTER.md)
(the numbers, the pitch and the Q&A).

### Rules for anything generated from this file (read before making the video)

1. **Nothing is a field measurement.** Sensor values are simulated (mock generator + Wokwi). On screen, label sensor numbers "simulated".
2. **Qualcomm is the target, not yet the test bench.** Models run on a laptop CPU today. Never show a latency as a Qualcomm/NPU number.
3. **Disease and pest findings are advisory.** The only automatic action is the irrigation valve.
4. **N/P/K are EC-derived proxies.** Never show a fertiliser prescription; show "soil test recommended".
5. Accuracy is always quoted with its test size: disease **87.70 % (n = 1,000)**, pest **94.98 % (n = 717)**.

---

## PART 0 — The whole system in one frame

```
                  ┌───────────────────────── SOLAR POLE (one paddy zone) ─────────────────────────┐
                  │                                                                              │
  FIELD           │   SENTINEL TIER  (ESP32, always on, milliwatts)                              │
  ─────           │   every 15 min: read all sensors → validate → history → risk → decide        │
  soil probes ───►│        │                                    │                                │
  air sensor  ───►│        │ "something worth looking at?"      └──► VALVE (relay)  ◄── only     │
  rain, light ───►│        ▼  (wake trigger)                         automatic action            │
  tank, flow  ───►│   COMPUTE TIER  (Qualcomm QCS6490, OFF by default)                           │
  AWD tube    ───►│   boot → camera frame → blur gate → disease model + pest model               │
                  │        → fusion with sensor window → advisory → transmit → power off         │
  camera      ───►│                                                                              │
                  │   OUTPUT: OLED on the pole · LoRa/MQTT to phone/cloud (optional)             │
                  └──────────────────────────────────────────────────────────────────────────────┘
```

**The idea in one sentence (voice-over):** *A camera sees symptoms, not causes — so every
picture is judged together with what the soil and air say, and when the evidence is weak the
node says so instead of guessing.*

---

## PART 1 — Hardware, component by component

Each card is one video shot: **what it is → where it sits → how it physically measures → what
signal comes out → which JSON field it becomes → which decision needs it.**

### 1.1 Physical layout (for the 3D / render shot)

| Element | Placement |
|---|---|
| Pole / mast | Fixed, one per field zone |
| Camera | Sealed, with sun hood, aimed **35° down** at the canopy |
| Electronics bay | Sealed box on the pole: ESP32 sentinel + QCS6490 compute + power electronics |
| Solar panel | **10–20 W**, tilted |
| Battery | **LiFePO4, 40–50 Wh** |
| Soil probes | Two depths: **100 mm (surface)** and **300 mm (root zone)**; pH, EC, soil temp at root zone |
| AWD tube | Perforated tube pushed into the paddy soil; measures how far standing water has drawn down |
| Tank | Irrigation water tank with ultrasonic level sensor on top, flow meter on the outlet, solenoid valve |

### 1.2 The two brains

| | **Sentinel** | **Compute** |
|---|---|---|
| Part | ESP32-class MCU + LoRa | Qualcomm **QCS6490** (RB3 Gen 2 class) — *target* |
| Power | Always on, ~mW (deep sleep 0.5 mW, est.) | **Off by default**, ~6 W when on (est.) |
| Job | Read every sensor, validate, keep history, compute risks, decide, drive the valve, decide *when to wake the camera* | Capture image, blur gate, run both AI models, fuse, send result back, power down |
| Why it exists | QCS6490 has **no analog input**; soil probes are analog. The ESP32 reads them natively | Runs the vision models on the device (NPU on target) |
| Link between them | UART on the real board; MQTT topic `…/vision` in the simulation | |

**Energy shot:** always-on AI = ~144 Wh/day (60–80 W panel). Duty-cycled, 4 sessions × 85 s =
**~0.8 Wh/day** (10–20 W panel). *Estimate, not measured.* Source: `project/docs/22_power_autonomy.md`.

### 1.3 Sensor cards

> Format of each card: **Part · Interface / pin (Wokwi) · Physics · Raw → value · JSON field · Used by**

---

**① Soil moisture — capacitive, ×2 (100 mm and 300 mm)**
- **Part:** corrosion-resistant capacitive probe. *Not resistive* — resistive probes corrode in months and read 20–40 % wrong in fertilised/saline soil.
- **Interface:** analog → ESP32 ADC. Wokwi: GPIO **34** (surface), GPIO **35** (root zone).
- **Physics:** the probe is a capacitor with soil as the dielectric. Water εr ≈ 80, dry soil ≈ 4, air = 1 → capacitance tracks water content → oscillator frequency shifts → rectified to a voltage. Electrodes are coated and never touch soil.
- **Raw → value:** 12-bit ADC 0–4095 → `raw × 60 / 4095` = **0–60 % VWC** (firmware `hub.moisture()`).
- **JSON:** `surface_moisture`, `root_moisture` (rule engine) · `soil_surface`, `soil_root` (firmware telemetry).
- **Used by:** irrigation (drained stages), Brown Spot corroboration, water-stress vs nitrogen separation, stuck-probe detection.
- **Why two depths:** surface = *did water arrive?*; root zone = *can the plant drink?* A light shower wets the top only.

**② AWD water-depth tube — the primary paddy irrigation signal**
- **Part:** perforated AWD (Alternate Wetting and Drying) tube with a water-level sensor inside. *Level sensor part not yet selected* (a submersible pressure transducer is the documented option for level sensing).
- **Physics:** water inside the perforated tube equals the field water table.
- **Value:** `water_depth_cm`, cm relative to soil surface. **+** = standing water above surface, **−** = drawn down below. Tube floor −25 cm.
- **Used by:** `evaluate_irrigation()` — re-flood at **−15 cm** (`AWD_REFLOOD_DEPTH_CM`, calibration knob, not yet verified for the Cauvery delta).
- **Why:** under standing water, both soil probes read saturated and carry no irrigation information.

**③ Air temperature + humidity**
- **Part:** **SHT31** (I²C with CRC) for deployment; **DHT22** (single-wire) in Wokwi, GPIO **15**.
- **Physics:** temperature = band-gap (silicon junction voltage vs temperature); humidity = capacitive polymer whose permittivity changes with absorbed water vapour.
- **JSON:** `air_temperature`, `humidity` · firmware `air_temp_c`, `humidity_pct`.
- **Used by:** disease corroboration (Blight, Blast), heat-stress alert (>38 °C), water-stress urgency, and speed-of-sound correction for the tank sensor. On read failure the firmware returns `None` — never the previous value.

**④ Soil temperature**
- **Part:** **DS18B20** digital probe, 1-Wire, GPIO **14**, with 4.7 kΩ pull-up.
- **Read:** asynchronous — conversion started at end of one cycle, read at the start of the next (a 750 ms conversion must not stall the loop).
- **JSON:** `soil_temp_c`. **Used by:** context and cross-check (wet soil swings less than air).

**⑤ Soil pH**
- **Physics:** glass electrode, ion-selective, Nernst ≈ **59 mV per pH unit** at 25 °C.
- **Wokwi:** potentiometer GPIO **32**, mapped 4.0–9.0.
- **Honest note:** real glass electrodes need recalibration and don't survive burial → realistically a periodic manual reading entered into the system.
- **JSON:** `soil_ph` / `ph`. **Used by:** nutrient lock-out (optimal 5.5–7.0; firmware flags outside 5.6–7.8), zinc-risk prior (pH > 7.2).

**⑥ Soil EC (electrical conductivity)**
- **Physics:** AC current between two electrodes (AC so the soil doesn't electrolyse). Conductivity rises with dissolved salts.
- **Wokwi:** potentiometer GPIO **39 (VN)**, mapped 0–5 dS/m.
- **JSON:** `soil_ec` / `ec_ds_m`. **Used by:** salinity alert (>2.0 dS/m rule engine; >3.0 firmware), **osmotic stress** (plant wilts in wet soil), N/P/K proxy.

**⑦ N / P / K "sensor" — a proxy, stated as such**
- **Reality:** low-cost RS485 NPK probes measure bulk EC and apply a vendor correlation. Not ion-selective.
- **Firmware:** `npk_proxy(ec)` → `LOW` (<0.8) / `NORMAL` (<2.2) / `HIGH`. Telemetry carries `"n_note": "EC-derived proxy, not ion-selective"`.
- **JSON:** `soil_n`, `soil_p`, `soil_k` with status key `soil_npk`.
- **Used by:** Hispa corroboration (N > 60), Brown Spot corroboration (N < 30), nutrient advisories — always ending in "soil test recommended".

**⑧ Rain sensor**
- **Physics:** interleaved conductive (or capacitive) traces; a droplet bridges them. Binary.
- **Wokwi:** pushbutton GPIO **4** (toggle).
- **JSON:** `rain: true/false`. **Used by:** the very first irrigation gate — rain ⇒ HOLD.

**⑨ Light level**
- **Part:** **BH1750** digital lux sensor for deployment; LDR (photoresistor) in Wokwi, GPIO **36 (VP)**, 0–1200 lux.
- **JSON:** `light_lux` / `lux`.
- **Used by:** **image-quality gate.** A CNN given a dark frame still returns a confident answer, so the hardware tells the software "don't trust this picture". Rule engine: below 400 lux, visual confidence × 0.7. Firmware: below 120 lux, vision weight 0.35.

**⑩ Tank level**
- **Part:** **HC-SR04** ultrasonic, TRIG GPIO **26**, ECHO GPIO **27**.
- **Physics:** 40 kHz burst, time the echo. `distance = speed_of_sound × t / 2`, speed of sound corrected using the air temperature (~0.6 m/s per °C) — *one sensor improving another*. `level % = (50 − distance) / 50 × 100` (50 cm tank).
- **JSON:** `tank_level` / `tank_pct`. No echo ⇒ `None` ⇒ valve held shut.
- **Used by:** pump-safety gate (block irrigation below 20 % rule engine, 15 % firmware).

**⑪ Water flow**
- **Part:** Hall-effect turbine on the valve outlet (pulses per litre). **Modelled in firmware, not wired in Wokwi.**
- **JSON:** `flow_lpm` / `flow_l`.
- **Used by:** closes the irrigation loop — valve open but flow < 0.5 L/min ⇒ blockage alert.

**⑫ Camera — the vision channel**
- **Part:** IMX577-class sealed camera with sun hood, 35° down, on the compute tier.
- **Output:** RGB frame → blur gate → two models (Part 3).
- **In Wokwi:** no camera; vision confidence arrives from potentiometer GPIO **33** or over MQTT.

### 1.4 Outputs / actuators

| Part | Pin (Wokwi) | Meaning |
|---|---|---|
| Relay → solenoid valve | GPIO 25 | **The one automatic action.** Opens only if the decision says irrigate *and* tank ≥ 15 % |
| LED VALVE (blue) | 18 | Mirrors relay |
| LED ALERT (red) | 19 | An advisory is active |
| LED EDGE (green) | 23 | Heartbeat — **independent of network** |
| Buzzer | 2 | Chirps ~140 ms on a *new* alert only |
| OLED SSD1306 128×64 | 21 SDA / 22 SCL | 5 pages: DECISION, SOIL+AIR, CHEMISTRY, RISK BANDS, SUPPLY |
| Buttons RAIN / NET / FAULT | 4 / 5 / 13 | Scenario injection: rain, cut the cloud, cycle probe GOOD→STUCK→FAILED |

---

## PART 2 — How data is taken, cleaned and formatted

### 2.1 The timeline of one day

```
every 15 min (sentinel)          wake trigger fires                    compute session (~85 s)
─────────────────────────        ─────────────────────                 ──────────────────────────────────
read all sensors                 • scheduled: dawn + mid-morning       25 s boot
→ plausibility check             • root moisture below stress          60 s: capture → blur gate →
→ stuck check (6 identical)      • drying trend steeper than limit          disease + pest model →
→ append to rolling history      • humidity in blight window                fusion → advisory → transmit
→ risk scores                    • temperature above heat limit        power off
→ decision + valve               • farmer request (SMS/app)
→ publish (after deciding)
```
Baseline: 2 scheduled + ~2 event wakes per day. **Power management and diagnosis are the same
rule set** — the camera wakes exactly when the sensors think there is something to look at.

### 2.2 Stage 1 — Raw signal → validated value

| Step | What happens | Code |
|---|---|---|
| Read | ADC count / digital bus value | firmware `SensorHub` |
| Convert | Count → physical unit (%, pH, dS/m, lux, cm) | `moisture()`, `ph()`, `ec()`, `lux()`, `level_pct()` |
| Plausibility | Out-of-range = **fault, not data** (a floating pin reading 247 % moisture is treated as missing) | `PLAUSIBLE_RANGES` in `iot/contracts.py` |
| Stuck detection | 6 bit-identical readings in a row ⇒ `STUCK` (a live probe always jitters) | `FROZEN_RUN_LENGTH = 6` |
| Status tag | Every channel gets `VALID` / `STALE` / `FAILED` / `UNKNOWN` | `sensor_status` |
| Missing value | Stays `None`. **Never replaced by 0 or a guess** | `_reading()` in `step6_rule_engine.py` |

### 2.3 Stage 2 — The sensor reading JSON (input to the rule engine)

Shape produced by `project/ai/sensor_contract.py` (simulated):

```json
{
  "timestamp": "2026-09-27T06:15:00Z",
  "rain": false,
  "sensor_status": {
    "soil_ph": "VALID",
    "soil_ec": "VALID",
    "soil_npk": "VALID",
    "surface_moisture": "VALID",
    "root_moisture": "VALID",
    "tank_level": "VALID",
    "water_depth_cm": "VALID"
  },
  "air_temperature": 30.0,
  "humidity": 75.0,
  "soil_ph": 6.5,
  "soil_ec": 1.2,
  "soil_n": 40.0,
  "soil_p": 15.0,
  "soil_k": 30.0,
  "surface_moisture": 32.0,
  "root_moisture": 24.0,
  "tank_level": 80.0,
  "flow_lpm": 0.0,
  "light_lux": 1000.0,
  "water_depth_cm": 3.0
}
```

### 2.4 Stage 3 — Firmware telemetry JSON (MQTT, every cycle)

Topic `sih26180/sentinel-01/telemetry` — from `iot/wokwi/micropython/main.py`:

```json
{
  "seq": 412, "node": "sentinel-01", "simulated": true,
  "soil_root": 24.1, "soil_surface": 31.8, "soil_state": "OK",
  "air_temp_c": 30.0, "humidity_pct": 75.0, "soil_temp_c": 28.4,
  "tank_pct": 80, "ph": 6.5, "ec_ds_m": 1.2,
  "n_indication": "NORMAL", "n_note": "EC-derived proxy, not ion-selective",
  "lux": 1000, "rain": false, "trend_pct_per_h": -0.12, "flow_l": 0.0,
  "vision_source": "pot",
  "quality": {"soil_root": "GOOD", "air_temp": "GOOD", "humidity": "GOOD",
              "soil_temp": "GOOD", "tank": "GOOD", "ph": "GOOD", "ec": "GOOD", "light": "GOOD"}
}
```
Other topics: `…/inventory` (sensor stack, once at boot), `…/decision` (see 2.8),
`…/vision` (**subscribed** — where the AI result arrives).

### 2.5 Stage 4 — Image → tensor (camera side)

| Step | Detail |
|---|---|
| Blur score | Greyscale, resize 224×224, **variance of Laplacian** on raw 0–255 pixels. `< 100` ⇒ `ABSTAIN_BLUR`, image never reaches the model |
| Resize | 224 × 224 RGB |
| Normalise | ÷255, then ImageNet mean `[0.485, 0.456, 0.406]`, std `[0.229, 0.224, 0.225]` |
| Layout | HWC → **(1, 3, 224, 224)** float32 |
| Run | ONNX (FP32, 5.8 MB each) → logits → softmax |
| Label | Class order loaded from `classes.json` / `pest_classes.json` — never hard-coded (a hard-coded list once swapped Healthy ↔ Tungro) |

### 2.6 Stage 5 — Model output JSON

From `project/ai/inference_server.py` (disease model):

```json
{
  "class": "Blast",
  "confidence": 0.81,
  "scores": {"Bacterial Blight": 0.04, "Blast": 0.81, "Brown Spot": 0.11, "Healthy": 0.03, "Tungro": 0.01},
  "blur_score": 2073.4,
  "blur_threshold": 100.0,
  "model": "kisannetra_fp32.onnx (MobileNetV3-Small, Val 87.32%)",
  "inference": "REAL — onnxruntime CPUExecutionProvider"
}
```

Blurred frame (measured: sharp 2073.4 → blurred 9.6):

```json
{
  "class": "ABSTAIN_BLUR",
  "confidence": 0.0,
  "blur_score": 9.6,
  "blur_threshold": 100.0,
  "inference": "ABSTAINED — image too blurry, recapture next cycle"
}
```

Vision result sent back to the sentinel (simulation wire format on `…/vision`):
```json
{"disease": 0.85, "pests": 6}
```

### 2.7 Stage 6 — Rule engine output JSON

`run_rule_engine(sensor, predicted_class, visual_confidence)` in `project/ai/step6_rule_engine.py` returns:

```json
{
  "timestamp": "...",
  "nutrients":      [ { "nutrient": "N", "level": "LOW|HIGH|UNKNOWN", "message": "...", "confidence": "LOW|HIGH|NONE" } ],
  "irrigation":     { "action": "IRRIGATE|HOLD|NO_ACTION", "reason": ["..."], "confidence": "HIGH|LOW|NONE", "blocked": false, "flow_alert": null },
  "disease_fusion": { "predicted": "Blast", "visual_confidence": 0.81, "final_risk": "NONE|LOW|MEDIUM|HIGH",
                      "factors": ["..."], "image_quality": "GOOD|POOR", "adjusted_visual_confidence": 0.81 }
}
```

Pest verdict (`fuse_pest`, `project/ai/pest/pest_fusion_rule.py`) has the same shape plus `"alert": true/false`
and can be `"final_risk": "INCONCLUSIVE"`. The two verdicts are merged by `combine_verdicts()`:

```json
{
  "disease": { "...disease verdict, verbatim..." },
  "pest":    { "...pest verdict, verbatim..." },
  "channels_fired": ["pest"],
  "headline_risk": "HIGH",
  "advisory": "Pest: Hispa (HIGH). No disease alert.",
  "conflict_note": "Disease model reports Healthy while the pest model reports Hispa. ..."
}
```

### 2.8 Stage 7 — Decision JSON (MQTT, firmware)

Topic `sih26180/sentinel-01/decision`:

```json
{
  "seq": 412, "node": "sentinel-01", "advisory_only": true,
  "action": "IRRIGATE NOW", "detail": "zone water stress",
  "why": ["Moisture 17% below thresh", "Trend -0.62 %/h falling", "Air temp 34C", "Rain: none"],
  "valve_open": true,
  "risk": {"water": 81, "disease": 22, "pest": 0, "nutrient": 0, "heat": 11, "flood": 0},
  "confidence": 1.0
}
```
**The decision is made before the radio is touched.** Wi-Fi times out at 8 s, retries every 30 s,
and up to **50 records queue** locally while offline.

---

## PART 3 — The AI models

| | Disease model | Pest-damage model |
|---|---|---|
| Classes | Bacterial Blight, Blast, Brown Spot, Healthy, Tungro | Dead Heart, Hispa, No Pest Damage |
| Architecture | MobileNetV3-Small, ImageNet pretrained | same |
| Data | Paddy Doctor (Tamil Nadu field images) + lab rice-leaf set | Paddy Doctor |
| Train / val / test | 4,621 / 986 / 1,000 | 3,336 / 714 / 717 |
| Accuracy | **87.70 %** (95 % CI 85.52–89.59) | **94.98 %** (95 % CI 93.13–96.35) |
| Weakest class | Brown Spot recall 70.4 % (confused with Blast) | No Pest Damage recall 91.6 % |
| Alert gate | Blur gate (all images) | Blur gate + confidence ≥ **0.80** |
| File | `kisannetra_fp32.onnx` (5.8 MB) | `kisannetra_pest_fp32.onnx` (5.8 MB) |
| Speed | 2.5 ms median on a **desktop CPU** (not Qualcomm) | same class |

**Why two models, not one:** lesions (fungus/bacteria) and insect feeding damage are different
visual tasks. The verdicts stay separate and are **never averaged**, so each can be explained.

**Why the pest threshold is 0.80:** measured, not guessed. False alerts on healthy leaves drop
from 8.37 % to 3.04 % while pest recall only falls from 96.9 % to 90.3 %
(`pest_threshold_analysis.json`).

**Known weakness:** blur costs −17.75 pp accuracy — which is why the blur gate sits in front of the model.

---

## PART 4 — Multimodal fusion: how camera + sensors become one decision

### 4.1 Three rules to show on screen

| Rule | Meaning |
|---|---|
| **Corroboration ceiling** | The camera alone can reach MEDIUM, **never HIGH**. HIGH needs a sensor that independently supports the diagnosis |
| **Abstain** | Blurry, dark or low-confidence frame ⇒ re-image next cycle. The pole looks at the same plants again, so waiting is cheap |
| **No guessing** | A failed sensor is `UNKNOWN`, never `0`. "0 mg/kg nitrogen" from a cut wire would otherwise become a fertiliser bill |

### 4.2 Which sensor corroborates which finding

| Camera finding | Corroborating sensor evidence | Why that sensor | Max risk |
|---|---|---|---|
| Bacterial Blight | humidity ≥ 80 % **and** 25–35 °C | Bacterium spreads in warm, humid conditions | HIGH |
| Blast | humidity ≥ 85 % **and** 24–32 °C | Fungal spores need leaf wetness and mild heat | HIGH |
| Brown Spot | soil N < 30 **or** root moisture < 16 % | Brown spot follows nutrient/water stress | HIGH |
| **Tungro** | none on this node | Spread by leafhoppers — no sensor sees them | **MEDIUM** |
| Hispa (pest) | soil N > 60 mg/kg | Excess N → lush foliage → leaf-pest pressure | HIGH |
| **Dead Heart** (pest) | none on this node | Caused by stem borer — no sensor sees it | **MEDIUM** |

### 4.3 Disease scoring logic (rule engine)

```
if light < 400 lux:          confidence = confidence × 0.7      (image-quality gate)
if class == Healthy:         risk = NONE
HIGH   if confidence ≥ 0.75 AND sensor corroboration
MEDIUM if confidence ≥ 0.55 OR  sensor corroboration
LOW    otherwise              → "monitoring recommended"
then cap at max risk (Tungro / Dead Heart → MEDIUM)
```

**Pest:** below 0.80 ⇒ `INCONCLUSIVE`; corroborated ⇒ HIGH; otherwise MEDIUM + "scouting recommended".

### 4.4 Firmware version of the same idea — "the camera cannot alarm alone" as arithmetic

```
disease_risk = vision_confidence × 55 × (1.0 if lux ≥ 120 else 0.35)
             + 22 if humidity > 80   (+10 if > 70)
             + 12 if 26 < temp < 34
alert threshold = 60
```

| Environment | Camera confidence needed to alert |
|---|---|
| Humid **and** warm | 0.48 |
| Humid only | 0.70 |
| Warm only | 0.88 |
| Neither | **impossible** (max 55 < 60) |

### 4.5 Decision priority (firmware `decide()` — safety first, advice second)

```
1. Root soil probe FAILED        → MANUAL CHECK
2. Soil probe STUCK              → MANUAL CHECK
3. Tank sensor lost              → MANUAL CHECK (valve shut)
4. Flooded / waterlogged         → DELAY IRRIGATION  or  WATERLOGGING
5. High EC in moist soil         → SALINITY CHECK
6. Water stress ≥ 55             → TANK REFILL (if tank < 15 %)  else  IRRIGATE NOW
7. Disease or pest risk ≥ 60     → INSPECT ZONE (advisory, no spray prescription)
8. Nutrient risk ≥ 55            → SOIL TEST
9. Heat risk ≥ 60                → HEAT STRESS
10. otherwise                    → NO ACTION
```
**Supply outranks crop stress:** a pump run dry destroys itself in minutes; a crop recovers from a delayed irrigation.

---

## PART 5 — Edge-case catalogue (one scene per case)

Each case: **Camera says · Sensors say · Rule that fires · Output · Explanation (voice-over)**.
Input numbers are illustrative simulated values; outputs follow the code exactly.

---

### PEST CASES

#### E1 — Pest detected **and** explained by the soil → HIGH
- **Camera (pest model):** Hispa, confidence **0.91** · Disease model: Healthy 0.93
- **Sensors:** soil N **68 mg/kg** (> 60), light 1000 lux, humidity 75 %
- **Rule:** Hispa ≥ 0.80 → not inconclusive → corroborator `excess_nitrogen` satisfied → **HIGH**
- **Output:**
  ```json
  {
    "channels_fired": ["pest"],
    "headline_risk": "HIGH",
    "advisory": "Pest: Hispa (HIGH). No disease alert.",
    "pest": {"predicted": "Hispa", "visual_confidence": 0.91, "final_risk": "HIGH", "alert": true,
             "factors": ["Soil corroboration: nitrogen 68 mg/kg above 60 mg/kg - lush foliage favours leaf-pest pressure."]},
    "conflict_note": "Disease model reports Healthy while the pest model reports Hispa. This is expected for a pest-only infestation ..."
  }
  ```
  Nutrient channel adds: `N HIGH — soil test recommended before further N` and `Zn RISK (high N can lock out zinc)`.
- **Explanation:** *The camera found hispa scraping marks. The soil explains why: nitrogen is high, the leaves are lush, and lush leaves attract hispa. Two independent sources agree, so the risk is HIGH. The farmer is also told the likely root cause — excess nitrogen — and to get a soil test before adding more urea.*

#### E2 — Pest detected, **no** sensor support → MEDIUM + scout
- **Camera:** Hispa 0.88 · **Sensors:** soil N 42 (normal)
- **Rule:** corroborator exists but not met → MEDIUM
- **Output factors:** `"Visual detection without environmental corroboration - scouting recommended before treatment."`
- **Explanation:** *The picture shows damage, but nothing in the soil or air explains it. The node does not escalate — it asks the farmer to walk over and check before spending on treatment.*

#### E3 — Dead Heart (stem borer) → capped at MEDIUM by design
- **Camera:** Dead Heart 0.97 · **Sensors:** anything
- **Rule:** no corroborator on this node → `max_risk = MEDIUM`
- **Output factors:** `"Dead Heart risk capped at MEDIUM - no environmental corroborator for this pest exists on this node."`
- **Explanation:** *Dead heart is caused by the stem borer, and none of our sensors can see that insect. However confident the camera is, the node will not claim HIGH — and it says so in its own words.*

#### E4 — Pest model unsure → INCONCLUSIVE, re-image
- **Camera:** Hispa **0.72** (< 0.80)
- **Output:** `"final_risk": "INCONCLUSIVE"`, advisory `"No disease alert. Pest read inconclusive - re-imaging this zone on the next capture cycle."`
- **Explanation:** *An unclear frame is a deferred capture, not a missed detection. The pole will photograph the same plants in a few hours.*

#### E5 — Disease model says Healthy, pest model says Hispa → not a contradiction
- **Output:** `conflict_note` explains the disease model has no pest class.
- **Explanation:** *Two specialists, two questions. The disease model was never trained on insect damage, so "healthy" from it plus "hispa" from the pest model is exactly what a pest-only attack looks like.*

#### E6 — Both channels fire → one trip to the field
- **Camera:** Bacterial Blight 0.84 (humidity 86 %, 29 °C → HIGH) + Hispa 0.90 (N 65 → HIGH)
- **Output:** `"advisory": "Both channels fired. Disease: Bacterial Blight (HIGH). Pest: Hispa (HIGH). Inspect this zone for both."`
- **Explanation:** *The farmer gets one message naming both problems, because they will make one trip.*

---

### DISEASE CASES

#### E7 — Blast + humid, mild weather → HIGH
- **Camera:** Blast 0.81 · **Sensors:** humidity 88 %, temp 27 °C, light 1000
- **Rule:** 0.81 ≥ 0.75 **and** humidity ≥ 85 % and 24–32 °C → **HIGH**
- **Output factors:** `"Environmental corroboration: humidity 88% ≥ 85% and temp 27°C in (24, 32) risk range."`
- **Explanation:** *The camera sees blast lesions; the air says conditions are exactly right for the blast fungus to spread. Both agree — HIGH risk, inspect now.*

#### E8 — Blast, but dry air → MEDIUM
- **Camera:** Blast 0.81 · **Sensors:** humidity 70 %
- **Rule:** not corroborated, 0.81 ≥ 0.55 → **MEDIUM**
- **Explanation:** *Same picture, different weather. Without humid conditions the fungus is unlikely to be spreading, so the node lowers its alarm.*

#### E9 — Tungro, very confident → still MEDIUM
- **Camera:** Tungro 0.95
- **Output factors:** `"Tungro risk capped at MEDIUM — no environmental corroborator available on this node."`
- **Explanation:** *Tungro is spread by leafhoppers. We cannot see leafhoppers, so the camera alone is not allowed to claim HIGH.*

#### E10 — Brown Spot explained by stressed soil → HIGH
- **Camera:** Brown Spot 0.78 · **Sensors:** root moisture **14 %** (< 16) or soil N **25** (< 30)
- **Rule:** soil-stress corroborator → **HIGH**
- **Output factors:** `"Soil corroboration: low nitrogen or low root moisture detected."`
- **Explanation:** *Brown spot is a disease of stressed plants. The soil confirms the stress — the real fix is water or nutrients, not just a spray.*
- **Honest note:** Brown Spot is the weakest class (70.4 % recall, often confused with Blast) — the soil check matters most here.

#### E11 — Blurry frame → ABSTAIN_BLUR
- **Camera:** blur score **9.6** (< 100)
- **Output:** `"class": "ABSTAIN_BLUR"`, image never reaches the model
- **Explanation:** *Blur is the model's biggest weakness (−17.75 points). So a blurry image is thrown away and re-taken, never guessed at.*

#### E12 — Dark frame → confidence discounted
- **Camera:** Blast 0.81 · **Sensors:** light **350 lux** (< 400), humidity 88 %, 27 °C
- **Rule:** 0.81 × 0.7 = **0.567** → corroborated but < 0.75 → **MEDIUM** (would be HIGH in daylight)
- **Output:** `"image_quality": "POOR"`, `"adjusted_visual_confidence": 0.567`, factor `"Low light (350 lux) — image quality degraded. Visual confidence reduced."`
- **Firmware:** below 120 lux the reason line reads `"Frame too dark - discounted"`.
- **Explanation:** *A neural network shown a dark picture still answers confidently. The light sensor is the hardware that tells the AI "don't trust this one".*

#### E13 — Yellow leaf: water stress or nitrogen? (the core multimodal argument)
- **Camera:** chlorosis — same pixels for both causes
- **Sensors:** root-moisture **trend** over days (`moisture_trend_pct_per_day`)
- **Rule (differential fusion engine, `iot/fusion/engine.py`):** falling moisture ⇒ supports water stress; adequate *and stable* moisture ⇒ water can't explain it ⇒ nitrogen becomes the likely cause (→ soil test). Every adjustment is logged as an `Evidence` item (`signal`, `observation`, `direction`, `weight`). If the margin between hypotheses stays < 0.15 ⇒ `needs_human_review`.
- **Explanation:** *No bigger model can fix this, because the answer isn't in the picture — it's in the soil's history. Fertilising a thirsty plant wastes money and makes the stress worse.*

---

### WATER & IRRIGATION CASES (paddy, AWD)

#### E14 — Water drawn down past −15 cm → IRRIGATE (automatic valve)
- **Sensors:** `water_depth_cm` **−17**, tank 80 %, no rain, flow 6 L/min
- **Output:** `"action": "IRRIGATE"`, reason `"Water drawn down to -17.0 cm below surface (AWD re-flood threshold -15 cm) — re-flood now."`
- **Explanation:** *Paddy doesn't need to be flooded all the time. The node lets the water drop, and re-floods only at the threshold — saving water without stressing the crop.*

#### E15 — Standing water → no action
- **Sensors:** `water_depth_cm` **+3**
- **Output:** `"Standing water 3.0 cm above surface — irrigation not needed."`

#### E16 — Crop is thirsty but the tank is almost empty → BLOCKED
- **Sensors:** depth −18 cm, tank **12 %** (< 20)
- **Output:** `"action": "HOLD", "blocked": true`, `"Tank level 12% is critically low (<20.0%) — irrigation BLOCKED."` Firmware: **TANK REFILL**, `"Valve held shut - dry run kills the pump"`.
- **Explanation:** *The crop can wait a few hours. A pump that runs dry is destroyed in minutes — and then there's no irrigation at all.*

#### E17 — Raining → HOLD
- **Sensors:** `rain: true`
- **Output:** `"Active rainfall detected — irrigation not needed."` (checked first, before anything else)

#### E18 — Waterlogging (firmware)
- **Sensors:** root moisture > 45 %, rain on
- **Output:** **WATERLOGGING** — `"Root anoxia and disease pressure rise", "Irrigation suppressed"`

#### E19 — Plant looks thirsty in wet soil → SALINITY, not drought
- **Sensors:** EC **3.4 dS/m** (> 3.0), root moisture ≥ 28 %
- **Output (firmware):** **SALINITY CHECK** — `"Osmotic stress, not drought", "Irrigation would worsen salts"`
- **Explanation:** *Salt stops the roots pulling water in. Without the EC sensor this would look like a broken probe or a disease.*

#### E20 — Valve open but nothing flowing → blockage
- **Sensors:** action IRRIGATE, `flow_lpm` < 0.5 or missing
- **Output:** `"flow_alert": "Valve commanded but flow_lpm<0.5 or missing — possible blockage. VERIFY MANUALLY."`

---

### SOIL CHEMISTRY CASES

#### E21 — pH out of range → nutrient lock-out
- **Sensors:** pH 7.9 (firmware flags outside 5.6–7.8), EC 0.6
- **Output:** **SOIL TEST** — `"pH 7.9 outside 5.6-7.8", "Nutrients may be locked out", "N indication LOW (EC proxy)", "Soil test before fertiliser"`
- **Explanation:** *The nutrients may be in the soil but the plant can't take them up. Adding fertiliser wouldn't help — fixing pH would.*

#### E22 — Zinc risk (inferred, never "detected")
- **Sensors:** soil N > 60 **or** pH > 7.2
- **Output:** `"Possible zinc deficiency — high N or alkaline pH can lock out Zn in paddy. Soil test recommended."`

#### E23 — Heat stress
- **Sensors:** air temp 44 °C
- **Output (firmware):** **HEAT STRESS** — `"Above 38C threshold"`

---

### SENSOR-FAILURE & SYSTEM CASES

#### E24 — Sensor FAILED → UNKNOWN, never zero
- **Sensors:** `sensor_status.soil_npk = "FAILED"`
- **Output:** `{"nutrient": "N", "level": "UNKNOWN", "message": "Soil N unavailable — MANUAL CHECK RECOMMENDED. No fertiliser recommendation is made without a reading.", "confidence": "NONE"}`. Firmware root probe failed ⇒ **MANUAL CHECK**, `"No value substituted"`, confidence 0.35.
- **Explanation:** *If a wire is cut, the system says "I don't know" — it does not pretend the soil has zero nitrogen.*

#### E25 — Sensor STUCK (the dangerous one)
- **Sensors:** 6 identical root-moisture readings in a row
- **Output:** **MANUAL CHECK — soil probe stuck**: `"Readings unchanging", "Channel excluded", "Probe needs service"`
- **Explanation:** *A dead probe that keeps repeating its last value looks like perfectly stable soil. We catch it because a live probe always jitters.*

#### E26 — Tank sensor lost
- **Sensors:** ultrasonic, no echo → `tank = None`
- **Output:** **MANUAL CHECK — tank level unknown**, `"Valve held shut"`. Rule engine: `"Tank level sensor FAILED — irrigation BLOCKED."`

#### E27 — Water-depth tube failed → fall back, confidence LOW
- **Output:** `"Water-depth sensor FAILED — falling back to soil moisture, which is unreliable under standing water. MANUAL CHECK RECOMMENDED."`, `"confidence": "LOW"`

#### E28 — Internet down → decisions continue
- **Trigger:** NET button / no Wi-Fi
- **Output:** OLED `CLOUD:DN`, green EDGE LED keeps blinking, up to 50 records queue, replayed on reconnect.
- **Explanation:** *The decision happens on the pole before the radio is touched. No network, no problem.*

---

## PART 6 — Video storyboard (suggested, ~4–5 min)

| # | Scene | Visual | On-screen data | Voice-over (short) |
|---|---|---|---|---|
| 1 | Problem | Flooded paddy, farmer, no signal bars | — | "Disease, pests and water problems — found late, in fields with no internet." |
| 2 | The pole | 3D pole: camera 35° down, solar panel, box, probes | Labels | "One solar pole watches one field zone." |
| 3 | Two brains | Split box: ESP32 (always on) / QCS6490 (asleep) | 144 Wh vs 0.8 Wh (est.) | "The AI sleeps until the sensors find something worth looking at." |
| 4 | Sensor tour | Each sensor card (Part 1.3), one per 4–6 s | Physics icon → value → JSON field | "Each sensor covers a blind spot of another." |
| 5 | Data pipeline | Numbers flow into the JSON of 2.3 | Status tags VALID / FAILED | "Every value is checked. A missing value stays missing." |
| 6 | Camera → AI | Frame → blur score → tensor → two models | 87.70 % / 94.98 % | "Two small models: one for disease, one for pest damage." |
| 7 | Fusion | Camera verdict + sensor evidence → rule → risk | Table 4.2 | "The camera alone can never raise a HIGH alert." |
| 8 | Edge case: pest | **E1** walkthrough | JSON from E1 | "Hispa found — and the soil explains why." |
| 9 | Edge case: disease | **E7 vs E8** side by side | HIGH vs MEDIUM | "Same picture, different weather, different answer." |
| 10 | Edge case: honesty | **E3/E9** cap, **E11** blur, **E12** dark | Factor strings | "When it can't know, it says so." |
| 11 | Edge case: water | **E14 → E16** | Valve LED, tank gauge | "It irrigates — but never runs the pump dry." |
| 12 | Edge case: failure | **E24/E25** | UNKNOWN, MANUAL CHECK | "A cut wire becomes 'I don't know', not a fertiliser bill." |
| 13 | Offline | **E28**, Wokwi sim | CLOUD:DN, EDGE blinking | "Cut the network. The decisions keep coming." |
| 14 | Close | Pole at sunset, roadmap | "Qualcomm QCS6490 integration — next phase" | "Built to run on the edge, honest about what it knows." |

---

## PART 7 — Say these limits out loud (or in on-screen footnotes)

1. Sensor values are **simulated**; no physical node has been deployed.
2. Models are validated on a **laptop CPU**; Qualcomm/NPU profiling is the next phase. INT8 quantization currently fails (22–36 %), so FP32 ships.
3. Training images are close-up leaves; the pole looks down at the canopy — that angle is **untested**.
4. ~5 % near-duplicate leakage between train and test → accuracy slightly optimistic.
5. N/P/K are **EC proxies**; the system never prescribes fertiliser.
6. Thresholds (incl. AWD −15 cm) are **starting points**, not field-calibrated.
7. **Known divergence:** the ESP32 firmware still uses moisture-only irrigation; the Python rule engine uses AWD water depth. They must be brought in line.
8. The firmware's `{"disease", "pests"}` vision input is a simulation interface; mapping the pest classifier into it is not yet wired end to end.

---

## PART 8 — Source map

| Topic | File |
|---|---|
| Sensor reading contract (mock generator) | `project/ai/sensor_contract.py` |
| Plausibility, stuck detection, evidence types | `project/iot/contracts.py` |
| Differential fusion (water vs nitrogen) | `project/iot/fusion/engine.py` |
| Disease fusion, irrigation, nutrients | `project/ai/step6_rule_engine.py` |
| Pest fusion + combined advisory | `project/ai/pest/pest_fusion_rule.py` |
| Blur gate + inference JSON | `project/ai/inference_server.py` |
| Firmware (sensors, risks, decisions, MQTT) | `project/iot/wokwi/micropython/main.py` |
| Wokwi parts and pins | `project/iot/wokwi/COMPONENTS.md` |
| Sensor physics | `project/docs/23_sensing_reference.md` |
| Hardware choice | `project/docs/07_hardware_decision.md` |
| Power budget and wake triggers | `project/docs/22_power_autonomy.md` |
| Numbers, pitch, Q&A | `PROJECT_MASTER.md` |
