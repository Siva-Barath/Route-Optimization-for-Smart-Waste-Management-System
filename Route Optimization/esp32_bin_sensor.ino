#include <WiFi.h>
#include <HTTPClient.h>

// ── WIFI ──────────────────────────────────────────────────────────────────────
const char* ssid     = "SIVA BARATH WIFI";
const char* password = "enterpassword";

// ── SERVER (must be on SAME network as ESP32) ─────────────────────────────────
// Run `ipconfig` on your PC and use the IP shown under the hotspot adapter
const char* server_url = "http://10.186.73.48:5000/api/bin_status";

// ── BIN CONFIG ────────────────────────────────────────────────────────────────
const String BIN_ID = "B1";

// ── SENSOR PINS ───────────────────────────────────────────────────────────────
#define TRIG1 5
#define ECHO1 18
#define TRIG2 17
#define ECHO2 16

// ── STATE ─────────────────────────────────────────────────────────────────────
long          duration;
float         d1, d2;
unsigned long blockStart = 0;
bool          blocked    = false;
String        lastStatus = "EMPTY";

// ── Distance ──────────────────────────────────────────────────────────────────
float getDistance(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  duration = pulseIn(echo, HIGH, 30000); // 30ms timeout
  if (duration == 0) return 999;         // no echo = out of range
  return duration * 0.034 / 2;
}

// ── Send with retry ───────────────────────────────────────────────────────────
void sendBinStatus(String status) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi not connected, skipping send");
    return;
  }

  String payload = "{\"bin_id\":\"" + BIN_ID + "\",\"status\":\"" + status + "\"}";
  Serial.print("📡 Sending: ");
  Serial.println(payload);

  for (int attempt = 1; attempt <= 3; attempt++) {
    HTTPClient http;
    http.begin(server_url);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000); // 5 second timeout

    int code = http.POST(payload);
    Serial.print("📨 Response (attempt ");
    Serial.print(attempt);
    Serial.print("): ");
    Serial.println(code);

    if (code == 200) {
      Serial.println("✅ Server acknowledged: " + status);
      http.end();
      return;
    } else if (code < 0) {
      Serial.print("❌ Connection error: ");
      Serial.println(http.errorToString(code));
    } else {
      Serial.print("⚠️ HTTP error: ");
      Serial.println(code);
    }

    http.end();
    if (attempt < 3) delay(1000); // wait 1s before retry
  }

  Serial.println("🔴 Failed to send after 3 attempts");
}

// ── WiFi reconnect ────────────────────────────────────────────────────────────
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.println("🔄 Reconnecting WiFi...");
  WiFi.disconnect();
  WiFi.begin(ssid, password);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi Reconnected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n❌ WiFi reconnect failed");
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  pinMode(TRIG1, OUTPUT); pinMode(ECHO1, INPUT);
  pinMode(TRIG2, OUTPUT); pinMode(ECHO2, INPUT);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi Connected!");
  Serial.println("ESP32 IP:   " + WiFi.localIP().toString());
  Serial.println("Server URL: " + String(server_url));
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  ensureWiFi();

  d1 = getDistance(TRIG1, ECHO1);
  d2 = getDistance(TRIG2, ECHO2);

  Serial.print("S1: "); Serial.print(d1);
  Serial.print(" cm | S2: "); Serial.println(d2);

  String currentStatus = "EMPTY";

  if (d1 < 5 && d2 < 5) {
    if (!blocked) { blockStart = millis(); blocked = true; }
    if (millis() - blockStart > 3000) {
      Serial.println("🚨 BIN FULL 🚨");
      currentStatus = "FULL";
    }
  } else {
    blocked = false;
    Serial.println("Bin OK");
  }

  if (currentStatus != lastStatus) {
    sendBinStatus(currentStatus);
    lastStatus = currentStatus;
  }

  delay(1000);
}
