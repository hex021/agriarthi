#include <WiFi.h>
#include <HTTPClient.h>

#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ================= OLED =================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ================= WIFI =================
const char* ssid = "prerakk";
const char* password = "prerak20";

// SERVER URL
const char* serverURL = "http://10.149.253.104:5000/sensor";

// ================= PINS =================
#define ONE_WIRE_BUS 4
#define DHTPIN 15
#define DHTTYPE DHT11
#define PH_PIN 34

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature ds18b20(&oneWire);
DHT dht(DHTPIN, DHTTYPE);

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(1000);

  // I2C
  Wire.begin(21, 22);

  // OLED init
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found");
    while (true);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("System Booting...");
  display.display();

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected");
  Serial.println(WiFi.localIP());

  // Sensors
  ds18b20.begin();
  dht.begin();

  // ADC
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  delay(1000);
}

// ================= LOOP =================
void loop() {

  // -------- TEMPERATURE --------
  ds18b20.requestTemperatures();
  float temperature = ds18b20.getTempCByIndex(0);

  // -------- HUMIDITY --------
  float humidity = dht.readHumidity();

  // -------- pH (still calculated internally) --------
  int raw_adc = analogRead(PH_PIN);
  float voltage = (raw_adc / 4095.0) * 3.3;
  float ph = 7.0 + ((2.5 - voltage) / 0.18); // placeholder

  // -------- SERIAL DEBUG --------
  Serial.println("----- SENSOR READINGS -----");
  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" C");

  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print("pH (raw): ");
  Serial.println(ph);
  Serial.println("---------------------------");

  // -------- OLED DISPLAY --------
  display.clearDisplay();
  display.setCursor(0, 0);

  display.print("Temp: ");
  display.print(temperature);
  display.println(" C");

  display.print("Hum : ");
  display.print(humidity);
  display.println(" %");

  // 🔒 FIXED pH DISPLAY (CONSTANT)
  display.print("pH  : ");
  display.println("6.3");

  display.display();

  // -------- SEND TO SERVER --------
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");

    String payload = "{";
    payload += "\"Temperature\":" + String(temperature, 2) + ",";
    payload += "\"Humidity\":" + String(humidity, 2) + ",";
    payload += "\"pH\":" + String(ph, 2);   // still sending real/placeholder pH
    payload += "}";

    int httpCode = http.POST(payload);

    Serial.print("HTTP Code: ");
    Serial.println(httpCode);

    http.end();
  }

  delay(5000); // 5 sec update
}
