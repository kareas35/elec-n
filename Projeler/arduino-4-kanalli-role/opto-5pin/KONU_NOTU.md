# Konu başlığı (sohbet için kullanılacak)

**4 Röle Arduino — V2 5 Pinli (J1 GND/D4-D7, J2 +5V DC)**

Yeni bir sohbet açtığında bu başlığı yazman yeterli. Bu klasördeki tüm çıktılar o sohbette referans alınabilir.

## Konu özeti

Arduino uyumlu, optokuplör izolasyonlu 4 röleli sürücü devresi. Eski 6 pinli sürümde header'da +5V vardı ve Arduino 5V ile röle 5V'u karışıyordu. Bu sürümde:

- **J1 — 5 pinli kontrol soketi:** 1=GND→Arduino GND, 2=IN1→D4, 3=IN2→D5, 4=IN3→D6, 5=IN4→D7. Header'da **5V yok**.
- **J2 — tek röle besleme girişi:** Pin 1=harici +5V DC, Pin 2=GND. Bu 5V yalnızca röle bobinlerini besler; Arduino USB'den beslenir.
- Her kanal: PC817 + BC547 + 4k7 + 1N4148 + SRD-05VDC-SL-C. `GND_A` / `GND_B` ayrı; PCB'de X=64.5–67.0 mm bakırsız bariyer.
- Mantık: Arduino HIGH → röle çekilir → COM-NO kapanır.

## Ana dosyalar

| Dosya | İçerik |
|---|---|
| `README.md` | Tam açıklama, pin tablosu, yeniden üretim komutları |
| `kicad/relay_4ch_5pin.kicad_sch` / `.kicad_pcb` | Şema ve PCB (ERC/DRC = 0) |
| `kicad/design.py`, `gen_sch.py`, `gen_pcb.py` | Tek kaynaklı üretim betikleri |
| `kicad/cikti/` | Şema/PCB/3B çıktılar, BOM |
| `sim/sketch.ino` | Arduino kodu (PIN = D4,D5,D6,D7) |
| `sim/diagram.json`, `wokwi.toml` | Wokwi projesi |
| `sim/simulasyon.html` | Tarayıcıda çalışan canlı simülasyon |
| `gorsel/index.html` | Tüm çıktıların görsel özeti (içindeki canlı simülasyon çalışır) |
| `gorsel/varliklar/` | Galerinin kullandığı görsel + simülasyon kopyaları (`hazirla.py` ile yenilenir) |
| `gorsel/simulasyon.gif` | Çalışan simülasyon kaydı |

## Not

Wokwi'de optokuplör olmadığı için simülasyonda GND'ler ortak gösterilir; gerçek PCB'de izolidir.
