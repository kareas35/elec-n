"""gorsel/index.html için gerekli dosyaları sayfanın kendi alt klasörüne kopyalar.

Uygulama içi tarayıcı üst klasöre (..) erişime izin vermediği için
şema/PCB/3B çıktıları ve canlı simülasyon buraya kopyalanır.
Kaynak dosyalar değiştiğinde bu betiği yeniden çalıştır.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VARLIKLAR = os.path.join(HERE, "varliklar")

KAYNAKLAR = [
    (os.path.join(ROOT, "kicad", "cikti", "sema.png"), "sema.png"),
    (os.path.join(ROOT, "kicad", "cikti", "pcb.png"), "pcb.png"),
    (os.path.join(ROOT, "kicad", "cikti", "3d_ust.png"), "3d_ust.png"),
    (os.path.join(ROOT, "kicad", "cikti", "3d_izometrik.png"), "3d_izometrik.png"),
    (os.path.join(ROOT, "sim", "simulasyon.html"), "simulasyon.html"),
]


def main():
    os.makedirs(VARLIKLAR, exist_ok=True)
    for src, name in KAYNAKLAR:
        if not os.path.isfile(src):
            raise SystemExit("Kaynak dosya yok: " + src)
        dst = os.path.join(VARLIKLAR, name)
        shutil.copyfile(src, dst)
        print("kopyalandı:", os.path.relpath(dst, ROOT))
    print("görsel özeti hazır:", os.path.join(HERE, "index.html"))


if __name__ == "__main__":
    main()
