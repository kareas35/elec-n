/*
 * 4 Kanallı Röle Kartı - Arduino Uno demo yazılımı
 * ------------------------------------------------
 * Bağlantı (J1):
 *   J1-1  +5V   -> Arduino 5V     (4 röle aynı anda enerjiliyse harici 5V/2A önerilir)
 *   J1-2  GND   -> Arduino GND
 *   J1-3  IN1   -> D4
 *   J1-4  IN2   -> D5
 *   J1-5  IN3   -> D6
 *   J1-6  IN4   -> D7
 *
 * ULN2003A girişi HIGH olduğunda ilgili röle enerjilenir (aktif-YÜKSEK).
 * Röle kontakları COM/NO/NC için J3..J6 vidalı terminallerini kullanın.
 * Şebeke gerilimi ile çalıştıracaksanız kartı koruyun ve ölçümleri dikkatli yapın.
 */

const byte RELAY_PINS[4] = {4, 5, 6, 7};
const byte RELAY_ON  = HIGH;
const byte RELAY_OFF = LOW;

void setRelay(byte channel, bool on) {
  if (channel >= 4) return;
  digitalWrite(RELAY_PINS[channel], on ? RELAY_ON : RELAY_OFF);
}

void allOff() {
  for (byte i = 0; i < 4; i++) setRelay(i, false);
}

void allOn() {
  for (byte i = 0; i < 4; i++) setRelay(i, true);
}

void printState(const char* label) {
  Serial.print(label);
  Serial.print(" -> ");
  for (byte i = 0; i < 4; i++) {
    Serial.print(digitalRead(RELAY_PINS[i]) == RELAY_ON ? '1' : '0');
  }
  Serial.println();
}

void setup() {
  Serial.begin(9600);
  for (byte i = 0; i < 4; i++) pinMode(RELAY_PINS[i], OUTPUT);
  allOff();                       // açılışta tüm röleler kapalı
  printState("Baslangic");
}

void loop() {
  // Sıralı tekil açma: her kanal 0.5 s
  for (byte i = 0; i < 4; i++) {
    setRelay(i, true);
    printState("Tekil");
    delay(500);
    setRelay(i, false);
  }

  // Hepsi açık, sonra kapalı
  allOn();
  printState("TumuAcik");
  delay(500);
  allOff();
  printState("TumuKapali");
  delay(1000);

  // Kovalamaca (chase): 8 x 0.25 s
  for (byte step = 0; step < 8; step++) {
    allOff();
    setRelay(step % 4, true);
    if (step >= 4) setRelay((step + 2) % 4, true);
    printState("Kovalamaca");
    delay(250);
  }

  allOff();
  printState("Bekleme");
  delay(2000);
}
