"""KiCad SVG çıktılarını Chrome headless ile PNG'ye çevirir."""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

JOBS = [
    (os.path.join(HERE, "sema_svg", "relay_4ch_5pin.svg"), os.path.join(HERE, "sema.png"), 1700, 1200),
    (os.path.join(HERE, "pcb.svg"), os.path.join(HERE, "pcb.png"), 1800, 1200),
]


def main():
    for svg, png, w, h in JOBS:
        html = os.path.join(HERE, "_gecici_" + os.path.basename(png) + ".html")
        with open(html, "w", encoding="utf-8") as f:
            f.write("<!doctype html><meta charset='utf-8'><style>"
                    "html,body{margin:0;background:#fff}img{display:block;width:100%%;height:auto}"
                    "</style><img src='file:///%s'>" % svg.replace("\\", "/"))
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               "--force-device-scale-factor=1", f"--window-size={w},{h}",
               f"--screenshot={png}", "file:///" + html.replace("\\", "/")]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(html)
        print("yazıldı:", png)


if __name__ == "__main__":
    main()
