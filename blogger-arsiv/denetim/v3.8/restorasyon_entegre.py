#!/usr/bin/env python3
"""V3.8 kontrollu gorsel restorasyon entegratoru."""
import argparse
import csv
import io
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[2]
V38 = ROOT / "denetim/v3.8"
PLAN = V38 / "restorasyon-entegrasyon-plani.csv"
ORIGINAL_BASE = "http://www.deli-prof.net/wp-content/uploads/2006/01/"

# Teknik olarak on incelemesi yapilan hedefler.
APPROVED = {"e14.gif"}

class ImageReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))

def read_plan():
    with PLAN.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def save_plan(rows):
    fields = ["Original", "Publication", "Restored",
              "Status", "Integrated"]
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=fields, lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    PLAN.write_text(buffer.getvalue(), encoding="utf-8-sig")

def transform(source, original, restored):
    url = ORIGINAL_BASE + original
    local = "../../assets/restored/" + restored

    pattern = re.compile(
        r'<div><span><b>\s*<img\b[^>]*\bsrc="'
        + re.escape(url)
        + r'"[^>]*/></b></span></div>',
        re.I
    )

    if len(pattern.findall(source)) != 1:
        raise ValueError("Tekil orijinal gorsel bulunamadi")

    replacement = (
        '<figure style="margin:12px 0 16px">'
        '<img src="' + local + '" '
        'alt="Fotodirenc LDR sembolu - yeniden cizim" '
        'width="99" height="55" loading="lazy" '
        'data-restoration="redrawn" '
        'data-original-src="' + url + '"/>'
        '<figcaption style="font-size:12px;color:#666;'
        'font-weight:normal;margin-top:5px">'
        'Orijinal kaynak bulunamadığı için yeniden çizilmiştir.'
        '</figcaption></figure>'
    )

    result = pattern.sub(lambda m: replacement, source, count=1)

    parser = ImageReader()
    parser.feed(result)
    hits = [
        img for img in parser.images
        if img.get("data-original-src") == url
        and img.get("src") == local
    ]
    if len(hits) != 1:
        raise ValueError("HTML dogrulamasi basarisiz")

    return result

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--image", required=True)
    cli.add_argument("--apply", action="store_true")
    args = cli.parse_args()

    original = args.image.lower()
    if original not in APPROVED:
        raise SystemExit("DURDURULDU: Teknik onay yok.")

    rows = read_plan()
    selected = [r for r in rows if r["Original"] == original]

    if not selected:
        raise SystemExit("Entegrasyon planinda hedef bulunamadi")

    prepared = []

    # Once tum dosyalari denetle.
    for row in selected:
        if row["Integrated"] != "false":
            raise SystemExit("Zaten entegre: " + row["Publication"])
        if row["Status"] != "technical_review":
            raise SystemExit("Beklenmeyen durum: " + row["Status"])

        page = ROOT / "Arsiv/yayinlar" / row["Publication"]
        svg = ROOT / "assets/restored" / row["Restored"]
        backup = V38 / "integration-backups" / (
            row["Publication"] + ".before-" + original
        )

        ET.parse(svg)
        source = page.read_text(encoding="utf-8")
        updated = transform(source, original, row["Restored"])

        if backup.exists() and backup.read_text(encoding="utf-8") != source:
            raise SystemExit("Yedek uyusmazligi: " + str(backup))

        prepared.append((row, page, backup, source, updated))

    if not args.apply:
        folder = V38 / "integration-previews"
        folder.mkdir(parents=True, exist_ok=True)

        for row, page, backup, source, updated in prepared:
            if re.search(r"<base\b", updated, re.I):
                raise SystemExit("Mevcut base etiketi var.")
            preview = re.sub(
                r"(<head\b[^>]*>)",
                lambda m: m.group(1) +
                '<base href="../../../Arsiv/yayinlar/">',
                updated, count=1, flags=re.I
            )
            target = folder / ("preview-" + row["Publication"])
            target.write_text(preview, encoding="utf-8")
            print("ONIZLEME:", target)

        print("Yayin HTML degisikligi: 0")
        print("Kullanmak icin: --apply")
        return

    # Tum kontroller basariliysa yedekle ve uygula.
    for row, page, backup, source, updated in prepared:
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(page, backup)

    for row, page, backup, source, updated in prepared:
        page.write_text(updated, encoding="utf-8")
        row["Integrated"] = "true"
        row["Status"] = "integrated_pending_final_review"
        print("ENTEGRE:", page)
        print("YEDEK:", backup)

    save_plan(rows)
    print("CSV: Guncellendi")
    print("Islem tamamlandi.")

if __name__ == "__main__":
    main()
