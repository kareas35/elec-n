# Elektronik Akademi V3.8 – Çalışma Durumu

Tarih: 18 Kasım 2026
Branch: elektronik-akademi-v3.8
Son commit: d48b9b9

## Tamamlananlar
- 442 riskli benzersiz görsel URL'si belirlendi.
- 18 görsel Wayback üzerinden kurtarıldı.
- SHA256 ve dosya imzaları doğrulandı.
- 027, 049, 069, 129 HTML sayfaları güncellendi.
- records.json değiştirilmedi.
- Kurtarma manifesti ve temel envanterler GitHub'a gönderildi.

## Kalan işler
- 424 riskli görsel URL'si.
- e5, e6, e7, e8, e12, e13, e14, e15 GIF dosyaları.
- Diğer eksik teknik ve dekoratif görseller.

## Son araştırma
- Yedi Blogger yayınının 2023 Wayback snapshot'ları bulundu.
- e7 ve e8 için Wayback görsel yanıtı HTTP 404.
- Google Blogger proxy yanıtı HTTP 403.
- Diğer Blogger snapshot sorgularında timeout ve HTTP 429 alındı.

## Mevcut karar
- Wayback sorguları geçici olarak durduruldu.
- Yeni indirme veya otomatik tekrar deneme yapılmayacak.
- Mevcut dosyalar ve manifest korunacak.

## Devam planı
1. Git ve manifest bütünlüğünü kontrol et.
2. HTTP 429 için merkezi durdurma mekanizması oluştur.
3. Retry-After ve kaldığı yerden devam desteği ekle.
4. Önce düşük hacimli kontrollü testler yap.
5. Kurtarılan görselleri doğrulayıp HTML'ye bağla.

## Güvenlik
- git reset --hard kullanma.
- Codespace'i silme.
- Takip edilmeyen analiz/yedek dosyalarını silme.
- PR #12 index.html branch'ine merge edildi.
- Son envanter commit'i henüz ayrı branch üzerinde.
