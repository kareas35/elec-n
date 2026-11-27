"""4 kanal optokuplörlü Arduino röle sürücüsü - V2 (kullanıcı pin haritası).

Tek kaynaklı tanım: şema (gen_sch.py) ve PCB (gen_pcb.py) bu dosyadan üretilir.

KULLANICI TARAFINDAN ONAYLANAN PIN HARİTASI:

  J1 - Yeni 5 pinli kontrol soketi
      1 = GND    -> Arduino GND
      2 = IN1    -> Arduino D4
      3 = IN2    -> Arduino D5
      4 = IN3    -> Arduino D6
      5 = IN4    -> Arduino D7

  J2 - Tek röle besleme girişi
      Pin 1 = Harici +5 V DC
      Pin 2 = GND

Eski 6 pinli sürümde +5V header'daydı ve Arduino/röle 5V'ları karışıyordu.
V2'de header'da hiç 5V yoktur; Arduino yalnızca USB'den beslenir.
+5V yalnızca J2'den gelir ve PC817 optokuplörleriyle GND_A / GND_B ayrıdır.

Kanal k (1..4):
  Arduino D(k+3) -> Rled(1k) -> PC817 LED anot(1); katot(2) -> GND_A
  PC817 pin4 -> +5V_B ; pin3 -> BC547 taban + Rpd(4k7) -> GND_B
  BC547 kollektör -> COL(k) -> röle bobin pin2 ; bobin pin1 -> +5V_B
  Flyback 1N4148: katot=+5V_B, anot=COL(k)
  Röle COM/NO -> yük terminali J(k+2)
"""

CHANNELS = 4

TERMINAL = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"


def build_components():
    comps = []

    # --- J1: 5 pinli KONTROL soketi (GND ilk pin, 5V YOK) ---
    comps.append((
        "J1", "Connector_Generic:Conn_01x05", "J1 KONTROL 5P (GND,IN1-IN4)",
        "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
        {"1": "GND_A", "2": "D4", "3": "D5", "4": "D6", "5": "D7"},
    ))

    # --- J2: TEK röle besleme girişi (harici +5V DC / GND) ---
    comps.append((
        "J2", "Connector_Generic:Conn_01x02", "J2 ROLE BESLEME +5V DC",
        TERMINAL, {"1": "+5V_B", "2": "GND_B"},
    ))
    comps.append((
        "C1", "Device:C", "100u",
        "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
        {"1": "+5V_B", "2": "GND_B"},
    ))
    comps.append((
        "C2", "Device:C", "100n",
        "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
        {"1": "+5V_B", "2": "GND_B"},
    ))

    for k in range(1, CHANNELS + 1):
        comps.append((
            f"Rled{k}", "Device:R", "1k",
            "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
            {"1": f"D{k + 3}", "2": f"LD{k}"},
        ))
        comps.append((
            f"U{k}", "Isolator:PC817", "PC817",
            "Package_DIP:DIP-4_W7.62mm",
            {"1": f"LD{k}", "2": "GND_A", "3": f"B{k}", "4": "+5V_B"},
        ))
        comps.append((
            f"Rpd{k}", "Device:R", "4k7",
            "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
            {"1": f"B{k}", "2": "GND_B"},
        ))
        comps.append((
            f"Q{k}", "Transistor_BJT:Q_NPN_CBE", "BC547",
            "Package_TO_SOT_THT:TO-92_Inline",
            {"1": f"COL{k}", "2": f"B{k}", "3": "GND_B"},
        ))
        comps.append((
            f"D{k}", "Device:D", "1N4148",
            "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
            {"1": "+5V_B", "2": f"COL{k}"},
        ))
        comps.append((
            f"K{k}", "Relay:SANYOU_SRD_Form_C", "SRD-05VDC-SL-C",
            "Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C",
            {"1": "+5V_B", "2": f"COL{k}", "3": f"NO{k}", "4": f"COM{k}", "5": f"NC{k}"},
        ))
        comps.append((
            f"J{k + 2}", "Connector_Generic:Conn_01x02", f"Yuk {k} (COM/NO)",
            TERMINAL, {"1": f"COM{k}", "2": f"NO{k}"},
        ))
    return comps


NC_NETS = {f"NC{k}" for k in range(1, CHANNELS + 1)}
ZONE_NETS = {"GND_A", "GND_B", "+5V_B"}

# Şemaya basılan uyarı notları: (x, y, metin)
SCH_NOTES = [
    (30, 20, "J1 (5 PIN): 1=GND->Arduino GND | 2=IN1->D4 | 3=IN2->D5 | 4=IN3->D6 | 5=IN4->D7"),
    (30, 27, "J2 (ROLE BESLEME): PIN 1 = HARICI +5V DC, PIN 2 = GND"),
    (30, 34, "HEADER'DA 5V YOKTUR. ARDUINO SADECE USB'DEN BESLENIR."),
    (30, 250, "SOL: KONTROL / GND_A      SAG: IZOLE ROLE TARAFI / +5V_B + GND_B"),
]
