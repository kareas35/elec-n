"""simulasyon.html dosyasını Chrome headless ile farklı zamanlarda örnekleyip GIF oluşturur."""
import os
import shutil
import subprocess

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, "sim", "simulasyon.html")
GORS = os.path.join(ROOT, "gorsel")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "file:///" + SIM.replace("\\", "/")
FRAMES = os.path.join(GORS, "_kareler")


def main():
    os.makedirs(FRAMES, exist_ok=True)
    times = list(range(200, 2200, 100))
    paths = []
    for t in times:
        out = os.path.join(FRAMES, f"{t:04d}.png")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                        "--window-size=1200,820", f"--virtual-time-budget={t}",
                        f"--screenshot={out}", URL],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        paths.append(out)
        print("kare", t)

    ims = [Image.open(p).convert("RGB") for p in paths]
    ims[0].save(os.path.join(GORS, "simulasyon.gif"), save_all=True,
                append_images=ims[1:], duration=130, loop=0, optimize=True)
    for i in (2, 7, 12):
        ims[i].save(os.path.join(GORS, f"sim_durum_{i}.png"))
    fark = ImageChops.difference(ims[2], ims[7]).getbbox()
    shutil.rmtree(FRAMES, ignore_errors=True)
    print("GIF yazıldı. Fark bölgesi:", fark)


if __name__ == "__main__":
    main()
