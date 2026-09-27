# KisanNetra — Arduino Sensor Setup (Bench Prototype)

Wiring, test sketch and expected serial output for each sensor validated on the
**Arduino UNO**. Status as of 2026-09-27; see [`PROGRESS_REPORT.md`](../../../PROGRESS_REPORT.md).

**Reading the output on the laptop:** every sketch prints at **115200 baud**. With the UNO on
`COM12`, run [`kisan_serial_test.py`](kisan_serial_test.py) (`pip install pyserial` first; change
`PORT` if your board enumerates on a different COM port). Each line prints as
`Arduino → <line>`.

> These are **bench readings from real sensors**, but uncalibrated beyond what is stated per
> sensor. The DHT11 and 3-pin LDR are prototype parts; the target design specifies SHT31 and
> BH1750 (see `project/docs/23_sensing_reference.md`).

## 1. Capacitive Soil Moisture Sensor #1

**Sensor:** Capacitive Soil Moisture Sensor v1.2

### Connections

```text
Sensor          Arduino UNO
────────────────────────────
VCC      →      5V
GND      →      GND
AO       →      A0
DO       →      Not connected
```

### Arduino code

```cpp
const int SOIL_PIN = A0;

const int DRY_ADC = 1011;
const int WET_ADC = 265;

float rawToMoisture(int raw) {
  float moisture =
    ((float)(DRY_ADC - raw) / (DRY_ADC - WET_ADC)) * 100.0;

  if (moisture < 0) moisture = 0;
  if (moisture > 100) moisture = 100;

  return moisture;
}

void setup() {
  Serial.begin(115200);

  Serial.println("KISANNETRA_SOIL_MOISTURE");
  Serial.println("STATUS: READY");
}

void loop() {
  int raw = analogRead(SOIL_PIN);
  float moisture = rawToMoisture(raw);

  Serial.print("RAW_ADC=");
  Serial.println(raw);

  Serial.print("MOISTURE_PERCENT=");
  Serial.println(moisture, 1);

  Serial.println("---");

  delay(1000);
}
```

### Expected output

```text
RAW_ADC=1007
MOISTURE_PERCENT=0.5
```

Dry:

```text
MOISTURE_PERCENT ≈ 0–1%
```

Wet:

```text
MOISTURE_PERCENT ≈ 94–95%
```

### Final KisanNetra value

```text
surface_moisture = moisture %
```

**Status: ✅ Tested**

---

## 2. DHT11

### Connections

```text
DHT11           Arduino UNO
────────────────────────────
VCC      →      5V
GND      →      GND
DATA     →      D2
```

### Arduino code

```cpp
#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);

  dht.begin();

  Serial.println("KISANNETRA_DHT11");
  Serial.println("STATUS: READY");
}

void loop() {
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT11_ERROR=READ_FAILED");
  } else {
    Serial.print("TEMPERATURE_C=");
    Serial.println(temperature, 1);

    Serial.print("HUMIDITY_PERCENT=");
    Serial.println(humidity, 1);
  }

  Serial.println("---");

  delay(2000);
}
```

### Expected output

```text
TEMPERATURE_C=32.0
HUMIDITY_PERCENT=64.2
```

### Final KisanNetra values

```text
air_temperature = temperature
humidity        = humidity
```

**Status: ✅ Tested**

---

## 3. LDR Module

The available part is the **3-pin LDR module**, so for the current demo we use its digital output.

### Connections

```text
LDR Module      Arduino UNO
────────────────────────────
VCC      →      5V
GND      →      GND
DO       →      D3
```

⚠️ Use **D3**, not D2, because D2 is already used by the DHT11.

**You do NOT need the external 10kΩ resistor for this module's digital-output test.**

### Arduino code

```cpp
const int LDR_PIN = 3;

void setup() {
  Serial.begin(115200);

  pinMode(LDR_PIN, INPUT);

  Serial.println("KISANNETRA_LDR");
  Serial.println("STATUS: READY");
}

void loop() {
  int state = digitalRead(LDR_PIN);

  if (state == LOW) {
    Serial.println("LIGHT_STATUS=BRIGHT");
  } else {
    Serial.println("LIGHT_STATUS=DARK");
  }

  delay(500);
}
```

If your module behaves opposite to this, simply swap `BRIGHT` and `DARK` in the code.

### Expected output

```text
LIGHT_STATUS=BRIGHT
```

or

```text
LIGHT_STATUS=DARK
```

### Final KisanNetra value

For **this current test**:

```text
light_status = BRIGHT / DARK
```

Later, if you want actual calibrated:

```text
light_lux = XXXX lux
```

the hardware/readout method must change (e.g. a BH1750 digital lux sensor).

**Status: ✅ Basic test**

---

## 4. HC-SR04 Ultrasonic Sensor

Purpose: eventually measure **irrigation tank water level**.

### Connections

```text
HC-SR04         Arduino UNO
────────────────────────────
VCC      →      5V
GND      →      GND
TRIG     →      D7
ECHO     →      D8
```

### Arduino code

```cpp
const int TRIG_PIN = 7;
const int ECHO_PIN = 8;

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  digitalWrite(TRIG_PIN, LOW);

  delay(1000);

  Serial.println("KISANNETRA_HC_SR04");
  Serial.println("STATUS: READY");
}

void loop() {

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {

    Serial.println("DISTANCE_STATUS=NO_ECHO");

  } else {

    float distance_cm = duration * 0.0343 / 2.0;

    Serial.print("DISTANCE_CM=");
    Serial.println(distance_cm, 1);
  }

  delay(500);
}
```

### Expected output

For example:

```text
DISTANCE_CM=10.4
DISTANCE_CM=10.3
DISTANCE_CM=10.5
```

Move an object farther away:

```text
DISTANCE_CM=20.2
DISTANCE_CM=20.4
```

### Final KisanNetra value

For now:

```text
distance_cm
```

Later:

```text
distance_cm
      ↓
tank geometry
      ↓
tank_level %
```

This is **not yet a tank percentage** — tank geometry is not calibrated.

**Status: 🔜 Sensor test / tank calibration later**

---

## 5. Capacitive Soil Moisture Sensor #2

Postponed until it can be placed properly in the root zone.

When we do it:

### Connections

```text
Sensor #2       Arduino UNO
────────────────────────────
VCC      →      5V
GND      →      GND
AO       →      A1
DO       →      Not connected
```

### Final purpose

```text
Sensor #1 → surface_moisture
Sensor #2 → root_moisture
```

Not calibrated yet.

**Status: ⏸️ Later**

---

## 6. Combined pin layout (planned)

Each sensor above was tested with its own sketch. A single combined sketch has not been written yet; when it is, it keeps this layout:

```text
SOIL #1 AO       → A0
SOIL #2 AO       → A1       (later)

DHT11 DATA       → D2

LDR DO           → D3

HC-SR04 TRIG     → D7
HC-SR04 ECHO     → D8

All VCC           → 5V
All GND           → GND
```

This is the pin layout for the combined Arduino sensor prototype.
