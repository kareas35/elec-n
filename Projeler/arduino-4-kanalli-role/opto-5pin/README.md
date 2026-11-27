# 4 Röleli Arduino Devresi — V2 / 5 Pinli (kullanıcı pin haritası)

Klasör: `C:\SalonAsistan\yatirim_takip\devre_4role_5pin_duzeltilmis`

## Pin haritası (onaylanan düzen)

**J1 — Yeni 5 pinli kontrol soketi**

| Pin | İsim | Bağlantı |
|---|---|---|
| 1 | GND | Arduino GND |
| 2 | IN1 | Arduino **D4** |
| 3 | IN2 | Arduino **D5** |
| 4 | IN3 | Arduino **D6** |
| 5 | IN4 | Arduino **D7** |

**J2 — Tek röle besleme girişi**

| Pin | Bağlantı |
|---|---|
| 1 | Harici **+5 V DC** |
| 2 | GND |

J1'de **5V yoktur**. Arduino yalnızca USB'den beslenir. J2'den gelen +5V yalnızca röle bobinlerini besler; Arduino'ya verilmez. Eski 6 pinli sürümde +5V header'daydı ve iki 5V birbirine karışıyordu; bu sürümde o pin kaldırıldı.

## Devre özeti (her kanal)

- Arduino `D4–D7` → **1 kΩ** → PC817 giriş LED'i (pin 1) → pin 2 → `GND_A`
- PC817 çıkışı: pin 4 → `+5V_B`, pin 3 → `B{k}` → **4k7** → `GND_B`
- `B{k}` → **BC547** tabanı; kollektör → röle bobini → `+5V_B`
- Bobin üzerinde **1N4148** flyback diyot
- Röle kontağı **COM / NO** → yük terminali `J{k+2}` (J3–J6)
- Filtre: J2 `+5V_B` için **100 µF + 100 nF**
- Mantık: Arduino `HIGH` → röle çekilir → COM-NO kapanır
- PC817 optokuplörleri sayesinde `GND_A` (Arduino) ve `GND_B` (röle) ayrıdır; PCB'de **X = 64.5–67.0 mm** bakırsız bariyer vardır.

> Wokwi'de optokuplör bileşeni olmadığı için simülasyonda GND'ler ortak gösterilmiştir. Gerçek PCB'de ayrıdır.

## Dosyalar

| Yol | İçerik |
|---|---|
| `kicad/relay_4ch_5pin.kicad_pro` | KiCad 10 projesi |
| `kicad/relay_4ch_5pin.kicad_sch` | Şema (J1 5 pin, J2 tek besleme) |
| `kicad/relay_4ch_5pin.kicad_pcb` | 2 katman PCB, izolasyon bariyerli |
| `kicad/design.py`, `gen_sch.py`, `gen_pcb.py` | Tek kaynaklı üretim betikleri |
| `kicad/cikti/sema.png`, `.svg`, `.pdf` | Şema çıktıları |
| `kicad/cikti/pcb.png`, `.svg` | PCB görünümü |
| `kicad/cikti/3d_ust.png`, `3d_izometrik.png` | 3B render'lar |
| `kicad/cikti/bom.csv` | Malzeme listesi |
| `sim/sketch.ino` | Arduino kodu (D4–D7) |
| `sim/diagram.json`, `wokwi.toml` | Wokwi simülasyon projesi |
| `sim/simulasyon.html` | İnternetsiz, tarayıcıda çalışan canlı simülasyon |
| `sim/build_sim.py` | `sketch.ino` → HTML içine gömer |
| `gorsel/index.html` | Tüm çıktıların görsel özet sayfası |
| `gorsel/varliklar/` | Galerinin kullandığı şema/PCB/3B/simülasyon kopyaları |
| `gorsel/hazirla.py` | Kaynak dosyaları `gorsel/varliklar/` içine kopyalar |
| `gorsel/simulasyon.gif` | Çalışan simülasyonun kaydı |

## Simülasyonu çalıştırma

1. **Tarayıcı (internetsiz):** `sim\simulasyon.html` dosyasına çift tıkla. `sketch.ino` içine gömülü olduğu için aynı kod çalışır. Hız etiketine tıklayarak 1/2/4/8x arasında geçiş yapılır.
2. **Wokwi:** `https://wokwi.com` → *New Arduino Uno Project* → `diagram.json` ve `sketch.ino` içeriklerini yapıştır → *Start simulation*.
3. **Görsel özet:** `gorsel\index.html` dosyasını aç.

## Arduino seri komutları

| Komut | Etki |
|---|---|
| `a` | 4 röleyi aç |
| `k` | 4 röleyi kapat |
| `1`–`4` | İlgili röleyi aç/kapat (toggle) |
| `s` | Durumları yazdır |

Otomatik demo: 4 açık (1.5 s) → 4 kapalı (0.9 s) → sırayla R1…R4 (0.6 s açık / 0.3 s kapalı) → tekrar.

## Doğrulama sonuçları

- **ERC:** 0 hata, 0 uyarı
- **DRC:** 0 ihlal
- **Router:** 32 bağlantı / 32 başarılı
- **Arduino CLI:** `arduino:avr:uno` derlemesi başarılı (3310 B flash, 224 B RAM)
- **Wokwi:** `diagram.json` geçerli, 18 parça / 32 bağlantı
- **Simülasyon:** `simulasyon.gif` ve `gorsel/sim_durum_*.png` kayıtları

## Yeniden üretim

```powershell
cd C:\SalonAsistan\yatirim_takip\devre_4role_5pin_duzeltilmis
python kicad\gen_sch.py
& 'C:\Program Files\KiCad\10.0\bin\python.exe' kicad\gen_pcb.py
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' sch erc --severity-all -o kicad\erc.json --format json kicad\relay_4ch_5pin.kicad_sch
& 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe' pcb drc --severity-all -o kicad\drc.json --format json kicad\relay_4ch_5pin.kicad_pcb
python sim\build_sim.py
python sim\animasyon.py
python gorsel\hazirla.py
```

> `gorsel\index.html` dosyası şema/PCB/3B görselleri ile canlı simülasyonu kendi `varliklar\` alt klasöründen okur; dosyalar değiştiğinde `python gorsel\hazirla.py` komutunu çalıştır.
