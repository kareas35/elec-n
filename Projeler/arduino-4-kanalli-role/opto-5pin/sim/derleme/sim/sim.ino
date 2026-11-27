/*
  4 kanalli röle sürücüsü - V2 (kullanıcı pin haritası)
  -----------------------------------------------------
  J1 (5 pin): 1=GND -> Arduino GND
              2=IN1 -> Arduino D4
              3=IN2 -> Arduino D5
              4=IN3 -> Arduino D6
              5=IN4 -> Arduino D7
              (header'da 5V YOK - Arduino USB'den beslenir)

  J2 (2 pin): 1=Harici +5V DC, 2=GND  -> SADECE röle beslemesi

  HIGH = röle çekilir (COM-NO kapanır). Seri komutlar: a, k, 1-4, s
*/

const int PIN[4] = {4, 5, 6, 7};
const char* AD[4] = {"R1", "R2", "R3", "R4"};
int state[4] = {0, 0, 0, 0};

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 4; i++) pinMode(PIN[i], OUTPUT);
  allOff();
  Serial.println(F("Hazir. J1: GND,D4,D5,D6,D7 | J2: +5V DC/GND | Komut: a k 1-4 s"));
}

void loop() {
  Serial.println(F(">> DEMO: 4 role ACIK"));
  allOn();
  bekle(1500);

  Serial.println(F(">> DEMO: 4 role KAPALI"));
  allOff();
  bekle(900);

  for (int k = 1; k <= 4; k++) {
    Serial.print(F(">> DEMO: sira "));
    Serial.println(k);
    setRelay(k, 1);
    bekle(600);
    setRelay(k, 0);
    bekle(300);
  }

  while (Serial.available() > 0) {
    int c = Serial.read();
    komut(c);
  }
}

void setRelay(int k, int on) {
  if (k < 1 || k > 4) return;
  digitalWrite(PIN[k - 1], on ? HIGH : LOW);
  state[k - 1] = on;
  Serial.print(F("  "));
  Serial.print(AD[k - 1]);
  Serial.println(on ? F(" ACIK") : F(" KAPALI"));
}

void allOn() {
  for (int k = 1; k <= 4; k++) setRelay(k, 1);
}

void allOff() {
  for (int k = 1; k <= 4; k++) setRelay(k, 0);
}

void bekle(int ms) {
  int t0 = millis();
  while (millis() - t0 < ms) delay(10);
}

void komut(int c) {
  if (c == 'a') {
    Serial.println(F(">> KOMUT: hepsi acik"));
    allOn();
  } else if (c == 'k') {
    Serial.println(F(">> KOMUT: hepsi kapali"));
    allOff();
  } else if (c >= '1' && c <= '4') {
    int k = c - '0';
    Serial.print(F(">> KOMUT: R"));
    Serial.println(k);
    setRelay(k, state[k - 1] ? 0 : 1);
  } else if (c == 's') {
    Serial.print(F(">> DURUM:"));
    for (int k = 1; k <= 4; k++) {
      Serial.print(F(" R"));
      Serial.print(k);
      Serial.print(state[k - 1] ? F("=1") : F("=0"));
    }
    Serial.println(F(""));
  }
}
