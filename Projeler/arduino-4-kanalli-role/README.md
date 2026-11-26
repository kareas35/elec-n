# 4 Kanallı Arduino Röle Kartı

Arduino Uno ile kontrol edilen, ULN2003A sürücülü, 5 V bobinli 4 kanallı röle kartı.
Şema, PCB, 3B görünüm, Gerber/drill, firmware, sayısal simülasyon ve SimulIDE
projesi bu klasörde birlikte bulunur.

> **Güvenlik — yalnızca düşük gerilimli eğitim:**
> Bu PCB'nin 230 V şebeke güvenliği doğrulanmamıştır.
> Şebeke gerilimi bağlamayın. Kontak yolları 0,5 mm'dir;
> güvenli akım kapasitesi henüz doğrulanmamıştır.
> Röleleri Arduino 5 V pininden beslemeyin.
> Harici, regüle 5 V DC kaynak kullanın.
> J2-1: +5 V, J2-2: GND.
> Arduino ve röle kartının GND bağlantısı ortak olmalıdır.
> J1-1 ve J2-1 aynı +5 V hattındadır.
> Harici besleme kullanırken J1-1'i Arduino 5 V pinine
> BAĞLAMAYIN. Mevcut PCB yanlış bağlantıyı engellemez.

## Donanım özeti

| Öğe | Değer / bağlantı |
|---|---|
| Besleme | 5 V DC. 4 röle aynı anda açıksa harici 5 V / 2 A önerilir. |
| Sürücü | ULN2003A (SOIC-16), entegre flyback diyotları |
| Röle | 4 × SRD-05VDC-SL-C, SPDT, bobin 5 V |
| Kontak çıkışı | Her kanal için COM / NO / NC vidalı terminal |
| Giriş | IN1..IN4, aktif-YÜKSEK, 10 kΩ pull-down |
| Kart boyutu | 140 × 95 mm |

### J1 — Arduino giriş soketi

| J1 pini | Sinyal | Arduino Uno |
|---:|---|---|
| 1 | +5V | Harici beslemede bağlama |
| 2 | GND | GND |
| 3 | IN1 | D4 |
| 4 | IN2 | D5 |
| 5 | IN3 | D6 |
| 6 | IN4 | D7 |

J2 isteğe bağlı harici 5 V girişidir: pin 1 +5V, pin 2 GND. J2 kullanılıyorsa
J1'in 5 V pini bağlanmaz; GND ortak kalır.

### J3..J6 — röle çıkış terminalleri

| Terminal pini | Kontak |
|---:|---|
| 1 | COM |
| 2 | NO (enerjiliyken kapalı) |
| 3 | NC (enerjisizken kapalı) |

Kart üzerindeki D1..D4 LED'leri ULN çıkışlarını, yani kanalın aktif olduğunu
gösterir. SimulIDE ekranındaki LED'ler ise röle kontaklarının kapandığını
göstermek için NO çıkışına eklenmiş ayrı 330 Ω + LED yükleridir.

## Yazılım davranışı

`Arduino_4_Relay/firmware/Arduino_4_Relay/Arduino_4_Relay.ino`:

1. Açılışta 4 kanal da kapatılır.
2. Kanal 1→4 sırayla 0,5 s açılır.
3. Tüm kanallar 0,5 s açık, 1 s kapalı kalır.
4. 8 adımlı kovalamaca dizisi (0,25 s/adım) çalışır.
5. 2 s bekleme sonrası döngü tekrar eder.

Derlenen çıktı: `Arduino_4_Relay.ino.hex` (2432 bayt flash, 252 bayt RAM).

## Dosyalar

```
Arduino_4_Relay/
├─ Arduino_4_Relay.kicad_sch        Şematik
├─ Arduino_4_Relay.kicad_pcb        PCB
├─ netlist.net                      Doğrulanmış KiCad netlist'i
├─ erc.rpt / drc.rpt                0 hata / 0 uyarı raporları
├─ firmware/
│  ├─ Arduino_4_Relay/Arduino_4_Relay.ino
│  └─ Arduino_4_Relay.ino.hex       SimulIDE'ye yüklenen firmware
├─ simulation/
│  ├─ transient.csv / transient.png / animation.gif
│  ├─ relay4_arduino.cir            ngspice uyumlu devre dosyası
│  └─ simulide/
│     ├─ Arduino_4_Relay.sim1       Arduino kodu yüklü proje
│     └─ Arduino_4_Relay.ino.hex
├─ docs/
│  ├─ Arduino_4_Relay_schematic.pdf / .svg
│  ├─ Arduino_4_Relay_pcb_layers.svg
│  ├─ pcb_3d.png
│  ├─ bom.csv
│  └─ simulide_running.png         Simülasyon çalışırken ekran görüntüsü
└─ gerber/                          Gerber + Excellon drill dosyaları
```

## Yeniden üretim

Tüm komutlar proje kökünde (`Varsayılan Proje`) çalıştırılır.

```powershell
# Şema, netlist, ERC, PCB ve DRC
python scripts\build_all.py
python scripts\validate_netlist.py

# PDF/SVG/BOM/Gerber/drill/3B render
python scripts\export_docs.py

# Arduino firmware derleme
& "C:\Program Files\Arduino CLI\arduino-cli.exe" compile `
  --fqbn arduino:avr:uno --output-dir Arduino_4_Relay\firmware `
  Arduino_4_Relay\firmware\Arduino_4_Relay

# Geçici rejim simülasyonu (scipy + matplotlib gerekir)
python scripts\simulate.py

# SimulIDE projesini HEX ile yenile
python scripts\simulide.py
```

`build_all.py`, PCB adımı için KiCad'in kendi Python'unu
(`C:\Program Files\KiCad\10.0\bin\python.exe`) kullanır; diğer adımlar normal
Python ile çalışır.

Gerekli yazılımlar: KiCad 10.0.8, Arduino CLI 1.6.0 (`arduino:avr:uno` çekirdeği),
SimulIDE 1.1.0 ve Python 3 (`numpy`, `scipy`, `matplotlib`, `Pillow`).

## SimulIDE'de çalıştırma

1. `Arduino_4_Relay\simulation\simulide\Arduino_4_Relay.sim1` dosyasını açın.
   Klasör adındaki Türkçe karakter nedeniyle sorun olursa, klasöre ASCII bir
   sürücü harfi atayın: `subst S: " ... \Arduino_4_Relay\simulation\simulide"`
   ve `S:\Arduino_4_Relay.sim1` dosyasını açın.
2. Üst araç çubuğundaki **Off** düğmesine basın; simülasyon başlar ve HEX
   dosyası otomatik olarak yeniden yüklenir.
3. Arduino kodu D4..D7'yi sırayla değiştirdikçe ULN çıkışları, röle bobinleri
   ve NO kontaklarına bağlı LED'ler yanar. `docs\simulide_running.png` tüm
   kanalların açık olduğu andan alınmıştır.

Son doğrulama: netlist geçerli, ERC 0/0, DRC 0/0, firmware derlendi, transient
simülasyonu ve SimulIDE çalışması tamamlandı.
