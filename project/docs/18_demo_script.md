# Demo runbook — running Wokwi, and explaining it to a judge

Two things this covers: how to drive the simulation without fumbling, and what
to say while you drive it. The second matters more. A judge has seen twenty
sensor dashboards today; what they have not seen is a node that says *why*.

**Companion documents**
- [`iot/wokwi/README.md`](../iot/wokwi/README.md) — setup and architecture
- [`iot/wokwi/COMPONENTS.md`](../iot/wokwi/COMPONENTS.md) — every part on the canvas
- [`23_sensing_reference.md`](23_sensing_reference.md) — the physics behind each sensor

---

## Part 1 — Working Wokwi

> [!WARNING]
> **PIVOT RECONCILIATION FOR JUDGES**
> Early project docs state **Cotton** and **Qualcomm QCS6490**. The executed AI build (in `ai/`) is **Rice (Paddy)** running on **Standard CPU (Edge-class)**.
> 
> **Why we pivoted:**
> 1. **Crop (Cotton → Rice):** We found Paddy Doctor — real Tamil Nadu field imagery — plus a separate lab-condition rice set, so lab and field images can be scored separately. (The raw lab-vs-field numbers are not yet a like-for-like comparison: the lab test set has no Healthy class. We do not present the gap as a headline.)
> 2. **Hardware (QCS6490 target, CPU validation so far):** FP32 ONNX is validated on CPU. onnxruntime post-training INT8 collapsed to 22–36% on both models; the root cause is not yet isolated (MobileNetV3's depthwise/squeeze-excite/HardSwish layers are the suspects). QCS6490 profiling runs through Qualcomm AI Hub's hosted devices — see `edge/QUALCOMM_AIHUB_GUIDE.md`. We will not present a CPU number as a Qualcomm number.

### What it is

Wokwi is a browser-based simulator for microcontrollers. It runs the real
MicroPython interpreter compiled for ESP32, executes our actual firmware, and
emulates the peripherals — the ADCs, the I²C bus, the 1-Wire bus, the
ultrasonic time-of-flight timing. **Nothing is mocked inside the firmware.** The
code that runs here is the code that would run on the board.

What it does *not* do is model the sensors' physics. A potentiometer supplies
the voltage a probe would supply; it does not drift, age or decalibrate. Say
this out loud before a judge asks it.

### Setting it up

1. [wokwi.com](https://wokwi.com) → **New Project** → **ESP32** → **MicroPython**
2. Open the **`diagram.json`** tab → select all → paste our `diagram.json`
3. Open the **`main.py`** tab → select all → paste our `main.py`
4. Press **▶**

**Both files, every time.** The diagram holds the components, their positions
and every wire; the firmware holds the behaviour. Pasting only `main.py` leaves
the board physically unchanged, which looks like nothing happened.

No libraries to install. The SSD1306 and LCD drivers are embedded in the
firmware precisely so there is nothing to forget.

### The two panes

| Pane | Where | What it is for |
|---|---|---|
| **Diagram** | top | The board. Click and drag things here. |
| **Serial monitor** | below — drag the divider up if collapsed | The node's reasoning, in words |

Top-right of the diagram: a **timer**, a **speed percentage**, and ▶ / ■ / ⏸.

### Driving it

| Part | How |
|---|---|
| **Potentiometer** | Click and drag the knob, or click it and use the arrow keys |
| **DHT22, HC-SR04, photoresistor** | Click the part — a small panel opens with its value |
| **Buttons** | Click and hold |

### What you should see, and when

| Time | What happens |
|---|---|
| ~0 s | Banner, then the 12-channel sensing stack with the reason each channel exists |
| ~1 s | `[i2c] devices found: ['0x27', '0x3c']` — both displays answer |
| ~1 s | Splash on both screens |
| **~2 s** | **First decision.** Displays go live, serial prints the decision block |
| ~3 s | `first decision made locally - now raising the optional cloud link` |
| ~3–11 s | WiFi, then MQTT — or a clean timeout, which changes nothing |

**The order is the argument.** The node decides before it has a network. If it
never gets one, the serial says so and everything carries on.

### Three displays, one page description

The same content goes to three places, rendered from one function so they
cannot disagree with each other:

- **OLED 128×64** — what a real field node carries
- **LCD 20×4**, below the circuit — a demo aid, four times the character size
- **Serial monitor** — a 16-column ASCII box, the same width as the glass

Pages rotate every 3.2 seconds: DECISION, SOIL+AIR, CHEMISTRY, RISK BANDS,
SUPPLY.

### When something looks wrong

| Symptom | Cause |
|---|---|
| Board looks unchanged after an update | `diagram.json` was not re-pasted |
| Stuck on the splash screen, or both screens blank | The loop stopped. The serial monitor prints a full traceback naming the line |
| Displays blank but the LCD backlight is on | The firmware died between initialising the panels and drawing them — read the traceback |
| `no I2C device` | SDA/SCL wiring — should be GPIO 21 / 22 |
| `DS18B20 not found` | The 4.7 kΩ pull-up is missing. 1-Wire idles high |
| WiFi times out | Expected and harmless. It is half the point of the demo |

---

## Part 2 — The demo, in about ninety seconds

Say the framing sentence first, before touching anything:

> *"This is the always-on microcontroller from a fixed, pole-mounted sentinel
> node. It is not a robot and it does not move. Everything you are about to see
> is decided on this chip, with no network."*

| # | Do | Say |
|---|---|---|
| 1 | Let it run one cycle | *"Five pages. Decision, soil and air, chemistry, risk bands, supply. The green LED is the edge heartbeat — watch it later."* |
| 2 | Turn **pot 2** (second from left) down below 20 % | *"Root-zone moisture. The valve opens — but look at the screen: it lists why. Moisture, the drying trend, air temperature, and no rain."* |
| 3 | Click the **HC-SR04**, set distance past 43 cm | *"Tank below 15 %. The valve shuts mid-cycle. A pump run dry destroys itself in minutes, so supply outranks crop stress."* |
| 4 | Restore the tank, press **RAIN** | *"Now it says delay. The weather is already supplying the water."* |
| 5 | Press **NET** | *"Cloud down. Records queue locally. Every decision continues, and the heartbeat never stops. Press again — the queue replays."* |
| 6 | Press **FAULT** once | *"The probe froze. It is still reporting a plausible number. We catch it because a live capacitive probe in soil always jitters — when the jitter stops, the probe died. The node names the part to service."* |
| 7 | Press **FAULT** again | *"Now it reports FAILED. No value is substituted, confidence drops, and it asks for a manual check rather than guessing."* |
| 8 | Raise **DHT22** humidity past 80 %, then turn **pot 5** up | *"Vision confidence from the camera. Only now does it raise a disease advisory — and it recommends inspection, never a chemical."* |

**Steps 5 to 7 are the demo.** Everything before them is a sensor dashboard;
those three are the difference between a dashboard and a field device.

### The single best moment

Before step 8, set **pot 5 to maximum with normal humidity**. Nothing happens.

> *"The camera is at 100 % confidence and the node will not act. Disease risk is
> confidence × 55, and the alert threshold is 60. Arithmetically the camera
> cannot raise an alarm alone — it needs environmental corroboration. That is
> not a tuning accident, it is the architecture: a camera sees symptoms, not
> causes."*

| Environment | Vision confidence needed |
|---|---|
| Humidity > 80 % **and** 26–34 °C | 0.48 |
| Humidity > 80 % only | 0.70 |
| Temperature in band only | 0.88 |
| Neither | **impossible** |

*(Verified against the running firmware, not derived on paper.)*

---

## Part 3 — Answering the judge

### "What is actually novel here?"

Not any single sensor, and say so first. **Every individual use case in this
system scores 1–2 out of 5 on novelty. The composite scores 4.**

The novelty is corroborated diagnosis. Rice leaf discoloration (like Brown Spot or early Blast) is genuinely
ambiguous from an image alone — a single RGB frame does not contain the information needed to separate fungal vectors from nutrient lockouts. A
three-day soil-moisture and humidity trend does. If environmental corroboration is missing, the vision model's risk score is suppressed. 
**The vision model emits a ranked differential and is fused with sensors, never acting alone.**

The economic claim follows from that: the value is not in detecting disease. It
is in stopping the farmer from buying the wrong chemical input based on a false positive.

### "Is this running on Qualcomm hardware?"

Be quick and exact:

"Not yet — Qualcomm integration is our planned next phase. Everything you see is FP32 on a laptop CPU (87.70%, 5.8 MB per model). The system is designed around the QCS6490: the models are small ONNX files, the sensor tier is separate because the QCS6490 has no analog input, and the compile-and-profile procedure on Qualcomm AI Hub is already written up in `edge/QUALCOMM_AIHUB_GUIDE.md`. We won't show a latency number until it has run on Qualcomm silicon."

On INT8: "onnxruntime post-training INT8 collapsed to 22–36% on both models. We haven't isolated the cause yet — MobileNetV3's depthwise, squeeze-excite and HardSwish layers are the suspects — so we ship FP32 and flag both broken files as `BROKEN`. In the Qualcomm integration phase we try Qualcomm's own quantizer first, then quantization-aware training or a ReLU backbone."

**Do not** say HardSwish produces negative values below −3 (it is exactly 0 there), and do not say Qualcomm's toolchain "handles it natively" — that is untested.

### "Why two processors?"

Power. An always-on application SoC draws roughly 6 W, which is **144 Wh/day** —
a 60–80 W panel and a 300 Wh battery, at a cost no smallholder will pay.
Duty-cycled behind an always-on MCU the budget is about **0.8 Wh/day**, and a
10 W panel covers the worst monsoon week with margin.

The architecture is not a preference. It is what makes the product exist at all.

### "How do I know the numbers are real?"

You do not, and we have not claimed they are. Every figure in this simulation is
a **simulated demonstration value**. Agronomic thresholds are general cotton
starting points on medium-textured soil, not calibrated field constants.

The nitrogen indication is derived from electrical conductivity, exactly as the
cheap "NPK sensors" sold for low-cost agriculture actually work — they do not
perform ion-selective measurement. It is labelled a proxy in the telemetry and
it never produces a fertilizer prescription.

### "What is the biggest risk?"

Out-of-distribution vision. Public plant-disease datasets are largely laboratory
photographs — a single leaf, plain background, even lighting. A model trained on
those and shown a real Indian field will be confidently wrong.

That is why we trained on real Tamil Nadu field imagery (Paddy Doctor) rather than lab photos: 90% of our test set is field images, and the model scores **88.79%** on them (n=901). We don't claim more than that — the lab subset (77.78%, n=99) has no Healthy class, so the two numbers aren't a like-for-like comparison. We also measured train/test leakage ourselves: about 5% near-duplicates, which we're removing and re-reporting.

The remaining gap is our camera geometry: the pole camera looks down at the canopy, while the training images are close-up leaves. `ai/ood_eval.py` is written for exactly that test; the photos from the real mounting angle are the next thing we collect.

### "Why Rice (Paddy) in Thanjavur instead of Cotton?"

Our early docs say Cotton, but we pivoted to Rice for data reasons. Paddy Doctor gives us over 10,000 labelled field images collected in Tamil Nadu — the same region and varieties (ADT45, Ponni) as our target deployment in the Cauvery delta — and it already contains two pest-damage classes, which let us build the pest model without a new data source. Thanjavur is Tamil Nadu's rice bowl, so the crop, the data and the farmer are all in the same place.

### Questions to refuse cleanly

- **"Can it spray automatically?"** No. It is advisory. The valve is the only
  controlled action, and it is gated on a verified water supply.
- **"Is it waterproof?"** It is designed for outdoor environmental protection.
  No IP rating has been tested, so none is claimed.
- **"How much water does it save?"** We do not have a measured figure. Anything
  we showed you would be a simulated demonstration value.

Saying "we have not measured that" is a stronger answer than a number you cannot
defend. It is also the answer a judge remembers.

---

## Part 4 — Updated Q&A (post-validation additions)

*These entries were added after the second-round validation study (2026-09-05).*
*They are good pitch material, not defensive clean-up.*

---

### "How do you handle a blurry image?"

We abstain rather than guess. The inference server computes a **variance-of-Laplacian
score** on every incoming frame before it reaches the classifier. A sharp image has
high-frequency edges and a high variance; a blurry image does not.

If the score is below the threshold, the server returns `ABSTAIN_BLUR` — "frame
discarded, recapture next cycle" — and nothing is fed to the ONNX model at all.
The dashboard shows a distinct "Recapture" state rather than a disease label.

This is the same "abstain rather than guess" design as the T=0.80 disease confidence
threshold. The architecture statement is: *an inconclusive frame is a deferred
capture, not a missed detection.* The sentinel captures on a cycle; the next frame
is seconds away. Feeding a blurry frame to the classifier produces a confident
wrong answer, which is worse than no answer.

**Demo step** (after the disease panel):

| # | Do | Say |
|---|---|---|
| 1 | Submit a blurred image (open a sharp image in Paint, apply heavy blur, save) | *"Motion blur. The sentinel will not classify this."* |
| 2 | Point to the dashboard "Recapture" state | *"ABSTAIN_BLUR. The blur score is below the threshold — the frame is discarded. Next cycle will try again."* |
| 3 | Submit the original unblurred version | *"Now it classifies. The blur gate passed."* |

---

### "How confident are you in your robustness numbers?"

We corrected one of our own findings during validation — and kept both numbers.

Early results showed 20–26% accuracy under brightness/contrast perturbation, close
to chance level. We investigated and found the bug was in the test harness, not the
model: perturbations were applied to an already-normalized tensor (range ~[-2.05,
+2.64]) whose values were then clamped to [0,1] — producing near-solid grey images,
not realistic lighting variation.

We re-ran the test correctly (raw pixels → perturbation → normalize, in that order)
on a larger sample (400 images vs. 64) and added Wilson confidence intervals. The
corrected brightness result is 80.50% [76.58%, 83.95%] — well above baseline risk.

The old numbers are preserved in the validation report with an explicit "WITHDRAWN"
label alongside the corrected ones. We did not silently replace them. That is the
right way to handle a correction: a silently fixed number invites the question "what
else was quietly changed," while a visible correction with both values shown is
auditable.

**The finding that survives:** blur, at 69.00% [64.30%, 73.33%] against the 86.75%
baseline. That is the actual remaining image-quality risk — and we address it with
the blur prefilter above.

---

### "What is the T=0.80 threshold? How did you choose it?"

The disease pipeline has a confidence gate: if the vision model's top prediction is
below 0.80, the system notes "inconclusive — monitoring" rather than raising an
alert. This is not a tuning accident.

The reasoning: *a camera sees symptoms, not causes.* Rice leaf discoloration is
genuinely ambiguous — Brown Spot, early Blast, and nitrogen deficiency produce
visually similar lesions. A model at 60% confidence on Blast might be seeing early
fungal signs, or it might be seeing nutrient stress. Acting on a 60% call puts
a farmer on a fungicide they may not need.

The threshold was chosen so that:
- The sensor fusion layer (humidity, temperature, soil NPK) gets to speak before
  the disease alert escalates.
- A confident camera prediction (≥ 0.80) combined with corroborating environmental
  data reaches HIGH risk.
- A confident prediction *without* corroboration reaches MEDIUM — "investigate, do
  not treat yet."
- Below 0.80, the node monitors and waits for the next cycle.

This is an explainable, documented engineering trade-off, not a black-box threshold.

---

### "What is your biggest remaining validation gap?"

Out-of-distribution (OOD) performance on real-world photos.

All our quantitative accuracy numbers come from `dataset_split/test` — images that
come from the same source distribution as training data. A model can score well on a
held-out split from its own distribution while failing on genuinely new images.

We have written `ai/ood_eval.py` for exactly this test, and the methodology is ready.
The step we have not yet completed is the photo collection itself: 20–30 photos across
the 5 classes, taken with different phones and lighting than the dataset.

We say this upfront because it is the honest answer. Every other validation item has
been tightened; this is the one that remains. A judge who asks about generalization
should hear this before they ask.

---

### Updated "Questions to refuse cleanly" additions

- **"Are your perturbation numbers from before or after the correction?"**
  After. The withdrawn numbers are in the report; ask to see it.
- **"Why is blur your remaining risk rather than brightness?"**
  Brightness variation is within the model's tolerance at corrected measurement.
  Blur is a qualitatively different failure mode — you cannot normalize past
  information that was never captured. That is why we gate at the hardware level
  with the blur prefilter, not just at the model level.
