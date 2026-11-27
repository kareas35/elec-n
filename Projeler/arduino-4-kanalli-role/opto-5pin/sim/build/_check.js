async function __test(){
const PIN = [4, 5, 6, 7];
const AD = ["R1", "R2", "R3", "R4"];
let state = [0, 0, 0, 0];

async function setup() {
  ser.begin(9600);
  for (let i = 0; i < 4; i++) pinMode(PIN[i], OUTPUT);
  await allOff();
  ser.println(("Hazir. J1: GND,D4,D5,D6,D7 | J2: +5V DC/GND | Komut: a k 1-4 s"));
}

async function loop() {
  ser.println((">> DEMO: 4 role ACIK"));
  await allOn();
  await bekle(1500);

  ser.println((">> DEMO: 4 role KAPALI"));
  await allOff();
  await bekle(900);

  for (let k = 1; k <= 4; k++) {
    ser.print((">> DEMO: sira "));
    ser.println(k);
    await setRelay(k, 1);
    await bekle(600);
    await setRelay(k, 0);
    await bekle(300);
  }

  while (ser.available() > 0) {
    let c = ser.read();
    await komut(c);
  }
}

async function setRelay(k, on) {
  if (k < 1 || k > 4) return;
  digitalWrite(PIN[k - 1], on ? HIGH : LOW);
  state[k - 1] = on;
  ser.print(("  "));
  ser.print(AD[k - 1]);
  ser.println(on ? (" ACIK") : (" KAPALI"));
}

async function allOn() {
  for (let k = 1; k <= 4; k++) await setRelay(k, 1);
}

async function allOff() {
  for (let k = 1; k <= 4; k++) await setRelay(k, 0);
}

async function bekle(ms) {
  let t0 = millis();
  while (millis() - t0 < ms) await delay(10);
}

async function komut(c) {
  if (c == 'a') {
    ser.println((">> KOMUT: hepsi acik"));
    await allOn();
  } else if (c == 'k') {
    ser.println((">> KOMUT: hepsi kapali"));
    await allOff();
  } else if (c >= '1' && c <= '4') {
    let k = c - '0';
    ser.print((">> KOMUT: R"));
    ser.println(k);
    await setRelay(k, state[k - 1] ? 0 : 1);
  } else if (c == 's') {
    ser.print((">> DURUM:"));
    for (let k = 1; k <= 4; k++) {
      ser.print((" R"));
      ser.print(k);
      ser.print(state[k - 1] ? ("=1") : ("=0"));
    }
    ser.println((""));
  }
}
}
