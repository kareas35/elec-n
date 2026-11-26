# Wokwi laboratuvari — Arduino 4 kanalli role

Bu klasor, Elektronik Akademi'nin KiCad tabanli role karti icin Wokwi uzerindeki **ogretici esdegeridir**.
Gercek PCB, ULN2003A veya PCB izolasyonunun Wokwi'de birebir dogrulamasini yapmaz.

## Nasil calistirilir?
1. https://wokwi.com/projects/new/arduino-uno adresini acin.
2. `sketch.ino` icerigini ayni isimli sekmeye kopyalayin.
3. `diagram.json` icerigini diagram sekmesine kopyalayin.
4. Simulasyonu baslatin. D4, D5, D6, D7 pinleri dort role modulunun IN girislerine baglidir.
5. LED'ler ilgili role COM-NO kontagi kapandiginda yanar.

- Arduino yazilimi orijinal `.ino` kaynaginin ayni icerigidir.
- Wokwi'nin sanal role modullerinde `transistor: pnp` ayari kullanilmistir:
  **HIGH = etkin / COM-NO kapali** (Wokwi simulasyon mantigi).
- Devre yalnizca sanal, dusuk gerilimli bir ogretim ornegidir.
- Gercek 4 role bobinini Arduino 5V pininden beslemeyin; harici uygun
  5V kaynak kullanin, GND'yi ortaklayin; ayri kaynaklarin 5V cikislarini
  dogrudan birlestirmeyin.
- Gercek kartin 230V/PCB guvenligi dogrulanmadi; sebeke gerilimi baglamayin.

Test durumu: JSON temel baglanti kontrollerinden gecmistir. Tarayici uzerinde
Wokwi calistirma testi bu dosya paketinden otomatik yapilamaz; elle dogrulanmalidir.
