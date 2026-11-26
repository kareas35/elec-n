# Arduino 4 Kanallı Röle — PCB V2 Güvenlik Planı

Durum: TASARIM / ÜRETİM ONAYI YOK
Başlangıç commit'i: 4f82e78

## Mevcut PCB bulguları
- J1-1 ve J2-1 aynı +5V netinde.
- Röle kontak yolları 0,5 mm.
- Şebeke güvenliği doğrulanmadı.
- Mevcut ERC/DRC raporları fiziksel güvenlik onayı değildir.

## V2 hedefleri
1. J1 yalnızca IN1-IN4 ve GND içerecek.
2. Röle beslemesi yalnızca J2 üzerinden sağlanacak.
3. Besleme girişinde ters polarite ve aşırı akım koruması değerlendirilecek.
4. Kontaktan geçen akım için yol genişliği hesaplanacak.
5. Kontak ve kontrol devresi arası mesafeler doğrulanacak.
6. Yeni şema ve PCB üzerinde ERC/DRC yeniden çalıştırılacak.
7. Fiziksel testler tamamlanmadan Gerber üretime gönderilmeyecek.

## Koruma kuralları
- Eski PCB, şema, ZIP ve Gerber dosyaları değiştirilmeyecek.
- V2 çalışmaları ayrı dosyalarda yürütülecek.
- 230V şebeke bağlantısı yapılmayacak.
