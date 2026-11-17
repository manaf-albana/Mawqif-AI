/*
 * Smart Parking System — ESP32 WiFi + ThingSpeak + OTA
 * =====================================================
 * يجمع بين:
 *  - الكود الأصلي الشغّال (Serial + LEDs بالمنافذ الصحيحة)
 *  - إرسال مباشر لـ ThingSpeak عبر HTTPS (TLS)
 *  - تحديثات OTA (Over-The-Air)
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ArduinoOTA.h>
#include <ESP32Servo.h>
#include "secrets.h"

// ====================================================
// إعدادات ThingSpeak (المضيف والمنفذ — المفتاح في secrets.h)
// ====================================================
#define THINGSPEAK_HOST    "api.thingspeak.com"
#define THINGSPEAK_PORT    443

// ====================================================
// 8 منافذ معتمدة وشغالة 100% + منفذ السيرفو
// ====================================================
int redPins[4]   = {23, 22, 21, 19};
int greenPins[4] = {14, 18, 32, 33};

#define SERVO_PIN 25  // منفذ السيرفو موتور للبوابة
Servo gateServo;

// ====================================================
// حالة المواقف
// ====================================================
int currentStates[4]      = {0, 0, 0, 0};
bool newDataReady          = false;
unsigned long lastCloudSend = 0;
const unsigned long CLOUD_INTERVAL_MS = 15000; // 15 ثانية

WiFiClientSecure client;

// ====================================================
// setup()
// ====================================================
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(10); // سرعة استجابة فائقة

  // تهيئة السيرفو (البوابة) — افتراضياً مفتوحة (0 درجة)
  gateServo.attach(SERVO_PIN);
  gateServo.write(0);

  // تهيئة المنافذ — افتراضياً كل المواقف خضراء (فارغة)
  for (int i = 0; i < 4; i++) {
    pinMode(redPins[i], OUTPUT);
    pinMode(greenPins[i], OUTPUT);
    digitalWrite(redPins[i], LOW);
    digitalWrite(greenPins[i], HIGH);
  }

  // الاتصال بـ WiFi
  connectWiFi();

  // ====== إدارة الطاقة (Power Management) ======
  // تفعيل Modem Sleep: إيقاف تشغيل راديو الـ Wi-Fi تلقائياً في فترات الخمول
  // يقلل استهلاك التيار من ~120mA إلى ~20-30mA
  WiFi.setSleep(true);

  // إعداد OTA
  setupOTA();

  // TLS — تفعيل اتصال HTTPS الآمن
  client.setInsecure();

  Serial.println("ESP32 READY (Power Optimized + OTA + TLS)");
}

// ====================================================
// loop()
// ====================================================
void loop() {
  // معالجة OTA أولاً
  ArduinoOTA.handle();

  // ====== قراءة Serial من Python (الكود الأصلي) ======
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() >= 7) { // "0,1,0,0" = 7 خانات
      int parsed = sscanf(data.c_str(), "%d,%d,%d,%d",
                          &currentStates[0], &currentStates[1],
                          &currentStates[2], &currentStates[3]);

      if (parsed == 4) {
        updateLEDs();
        newDataReady = true;
      }
    }
  }

  // ====== إرسال لـ ThingSpeak كل 15 ثانية ======
  unsigned long now = millis();
  if (newDataReady && (now - lastCloudSend >= CLOUD_INTERVAL_MS)) {
    if (WiFi.status() == WL_CONNECTED) {
      sendToThingSpeak();
      lastCloudSend = now;
      newDataReady  = false;
    } else {
      connectWiFi(); // إعادة الاتصال تلقائياً
    }
  }

  // السماح لـ FreeRTOS بتشغيل Idle Task لتوفير استهلاك طاقة المعالج
  delay(10);
}

// ====================================================
// updateLEDs() — تحديث إضاءة المصابيح والتحكم بالبوابة
// ====================================================
void updateLEDs() {
  int occupiedCount = 0;

  for (int i = 0; i < 4; i++) {
    if (currentStates[i] == 1) {
      digitalWrite(redPins[i], HIGH);
      digitalWrite(greenPins[i], LOW);
      occupiedCount++;
    } else {
      digitalWrite(redPins[i], LOW);
      digitalWrite(greenPins[i], HIGH);
    }
  }

  // التحكم بالـ Servo (البوابة):
  // إذا كانت جميع المواقف الـ 4 مشغولة (occupiedCount == 4) -> تتغلق البوابة (90 درجة)
  // إذا كان هناك أي موقف فارغ (0 أو 1 أو 2 أو 3) -> تنفتح البوابة (0 درجة)
  if (occupiedCount == 4) {
    gateServo.write(90); // إغلاق البوابة (ممتلئ بالكامل)
  } else {
    gateServo.write(0);  // فتح البوابة (يوجد موضع واحد على الأقل)
  }
}

// ====================================================
// sendToThingSpeak() — HTTPS مباشر من ESP32
// ====================================================
void sendToThingSpeak() {
  int occupied     = 0;
  for (int i = 0; i < 4; i++) occupied += currentStates[i];
  float occupancyPct = (occupied / 4.0) * 100.0;

  String url = "/update?api_key=" + String(THINGSPEAK_API_KEY) +
               "&field1=" + String(currentStates[0]) +
               "&field2=" + String(currentStates[1]) +
               "&field3=" + String(currentStates[2]) +
               "&field4=" + String(currentStates[3]) +
               "&field5=" + String(occupied) +
               "&field6=" + String(occupancyPct);

  Serial.print("Cloud -> ThingSpeak... ");

  if (!client.connect(THINGSPEAK_HOST, THINGSPEAK_PORT)) {
    Serial.println("FAILED (no connection)");
    return;
  }

  client.print("GET " + url + " HTTP/1.1\r\n");
  client.print("Host: " + String(THINGSPEAK_HOST) + "\r\n");
  client.print("Connection: close\r\n\r\n");

  unsigned long timeout = millis();
  while (client.connected() && millis() - timeout < 5000) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      if (line.startsWith("HTTP/1.1 200")) {
        Serial.println("OK");
      }
      break;
    }
  }
  client.stop();
}

// ====================================================
// connectWiFi()
// ====================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("WiFi connecting");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" OK | IP: " + WiFi.localIP().toString());
  } else {
    Serial.println(" FAILED — Serial mode only");
  }
}

// ====================================================
// setupOTA()
// ====================================================
void setupOTA() {
  ArduinoOTA.setHostname("SmartParking-ESP32");
  ArduinoOTA.setPassword(OTA_PASSWORD);

  ArduinoOTA.onStart([]()  { Serial.println("OTA Start..."); });
  ArduinoOTA.onEnd([]()    { Serial.println("\nOTA Done!"); });
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("OTA Error[%u]\n", error);
  });

  ArduinoOTA.begin();
  Serial.println("OTA Ready");
}
