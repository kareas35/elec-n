"""sketch.ino dosyasını okur, küçük bir C++ -> JS dönüşümüyle simulasyon.html içine gömer.

Böylece HTML, Wokwi'de kullanılan aynı Arduino koduyla çalışır; ayrı bir kopya yoktur.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SKETCH = os.path.join(HERE, "sketch.ino")
OUT = os.path.join(HERE, "simulasyon.html")

HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>4 Röle - 5 Pinli Düzeltilmiş Devre - Canlı Simülasyon</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--txt:#e6edf3;--mut:#8b949e;
      --red:#f85149;--green:#3fb950;--blue:#58a6ff;--yellow:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 Segoe UI,Arial,sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);background:#11161d}
h1{margin:0;font-size:19px}
h1 small{font-weight:400;color:var(--mut);font-size:13px}
.wrap{display:grid;grid-template-columns:300px 1fr 320px;gap:16px;padding:16px;max-width:1600px;margin:auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
.card h2{margin:0 0 10px;font-size:14px;color:var(--blue)}
.row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.badge{border:1px solid var(--line);border-radius:6px;padding:3px 8px;font:12px Consolas,monospace;color:var(--mut)}
.badge.on{background:#12341d;border-color:var(--green);color:var(--green)}
.badge.off{background:#2a1416;border-color:var(--red);color:var(--red)}
.warn{border:1px solid #7d3b1f;background:#2b1a12;color:#ffb37c;border-radius:8px;padding:9px;font-size:12px}
.pinrow{display:flex;gap:5px;margin:8px 0}
.pin{width:48px;text-align:center;border:1px solid var(--line);border-radius:6px;padding:6px 2px;font:11px Consolas,monospace;background:#0d1117}
.pin b{display:block;color:var(--txt);font-size:12px}
.no5v{color:var(--red);font-weight:bold;text-decoration:line-through}
.supply{display:flex;align-items:center;justify-content:space-between;border:1px solid var(--line);border-radius:7px;padding:8px;margin-top:6px;font:12px Consolas,monospace}
.supply b{color:var(--yellow)}
.sep{text-align:center;color:var(--red);font-size:11px;margin:4px 0}
.roles{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.relay{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.relay .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.relay .name{font-weight:bold;font-size:15px}
.sw{position:relative;height:26px;width:70px;border:1px solid var(--line);border-radius:14px;background:#0d1117;overflow:hidden}
.sw i{position:absolute;top:3px;left:3px;width:20px;height:18px;border-radius:9px;background:#484f58;transition:.25s}
.relay.acik .sw{border-color:var(--green);background:#12341d}
.relay.acik .sw i{left:45px;background:var(--green)}
.led{width:20px;height:20px;border-radius:50%;background:#30363d;border:2px solid #000;box-shadow:inset 0 0 4px #000}
.relay.acik .led{background:var(--lc,#f85149);box-shadow:0 0 14px var(--lc,#f85149)}
.kontak{font:12px Consolas,monospace;color:var(--mut);margin-top:9px}
.relay.acik .kontak{color:var(--green)}
#mon{height:330px;overflow:auto;background:#070a0e;border:1px solid var(--line);border-radius:7px;padding:9px;font:12px/1.45 Consolas,monospace;white-space:pre-wrap}
#mon .cmd{color:var(--yellow)} #mon .sys{color:var(--mut)}
.ctrl{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
button{background:#21262d;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 10px;cursor:pointer;font-size:12px}
button:hover{border-color:var(--blue)}
button.primary{background:#1f6feb;border-color:#1f6feb}
input{width:100%;background:#070a0e;border:1px solid var(--line);color:var(--txt);border-radius:6px;padding:8px;font:13px Consolas,monospace;margin-top:8px}
footer{max-width:1600px;margin:auto;padding:0 16px 24px;color:var(--mut);font-size:12px}
code{color:#79c0ff}
@media(max-width:1100px){.wrap{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>4 Röleli Arduino Sürücüsü <small>· V2 / 5 pinli · sketch.ino canlı olarak yüklenip çalıştırılıyor</small></h1></header>
<div class="wrap">
  <div>
    <div class="card">
      <h2>J1 - KONTROL SOKETİ (5 PIN)</h2>
      <div class="pinrow">
        <div class="pin"><b>1</b>GND</div><div class="pin"><b>2</b>IN1 · D4</div>
        <div class="pin"><b>3</b>IN2 · D5</div><div class="pin"><b>4</b>IN3 · D6</div>
        <div class="pin"><b>5</b>IN4 · D7</div>
      </div>
      <div class="warn">Bu sokette <span class="no5v">+5V</span> YOK.<br>Arduino yalnızca USB'den beslenir. 1 numara Arduino GND'ye gider.</div>
    </div>
    <div class="card">
      <h2>J2 - TEK RÖLE BESLEME GİRİŞİ</h2>
      <div class="supply"><span>Pin 1 · Harici</span><b>+5V DC</b></div>
      <div class="supply"><span>Pin 2</span><b>GND</b></div>
      <p style="color:var(--mut);font-size:12px;margin:10px 0 0">Bu 5V yalnızca röle bobinlerini besler; Arduino'ya verilmez. Gerçek PCB'de PC817 optokuplörleri GND_A / GND_B'yi izole eder; Wokwi/simülasyonda GND ortak gösterilir.</p>
    </div>
    <div class="card">
      <h2>KONTROLLER</h2>
      <div class="row"><button id="btn" class="primary">Durdur</button>
        <span class="badge" id="hiz">hız 4x</span></div>
      <div class="ctrl">
        <button onclick="gonder('a')">a · hepsi aç</button>
        <button onclick="gonder('k')">k · hepsi kapat</button>
        <button onclick="gonder('1')">1</button><button onclick="gonder('2')">2</button>
        <button onclick="gonder('3')">3</button><button onclick="gonder('4')">4</button>
        <button onclick="gonder('s')">s · durum</button>
      </div>
      <input id="inp" placeholder="komut yaz (a, k, 1-4, s) + Enter">
    </div>
  </div>

  <div>
    <div class="roles" id="roles"></div>
    <div class="card" style="margin-top:14px">
      <h2>YÜK TARAFI (COM → NO)</h2>
      <div style="color:var(--mut);font-size:12px">Röle çekildiğinde COM-NO kapanır ve LED, <b style="color:var(--yellow)">J2'den gelen harici +5V DC</b> kaynağından beslenir. Arduino'nun 5V'u devrede hiç kullanılmaz.</div>
    </div>
  </div>

  <div>
    <div class="card">
      <h2>SERİ MONİTÖR (9600 baud)</h2>
      <div id="mon"></div>
      <input id="sin" placeholder="seri komut gönder">
    </div>
  </div>
</div>
<footer>Simülasyon, <code>sketch.ino</code> içeriğini okuyup küçük bir C++→JS dönüşümüyle çalıştırır. Donanım doğrulaması için <code>sim/diagram.json</code> dosyasını Wokwi'ye yükleyin.</footer>

<script>
const SRC = /*__SKETCH__*/;
const RENK = ["#f85149","#3fb950","#58a6ff","#d29922"];
const roles = document.getElementById("roles");
for(let i=0;i<4;i++){
  const d=document.createElement("div"); d.className="relay"; d.style.setProperty("--lc",RENK[i]);
  d.innerHTML='<div class="top"><span class="name">R'+(i+1)+' <span class="badge">D'+(i+4)+'</span></span><span class="sw"><i></i></span></div>'+
   '<div class="row"><span class="led"></span><span class="durum badge off">KAPALI</span><span class="kontak">COM —| |— NO</span></div>';
  roles.appendChild(d);
}
const mon=document.getElementById("mon");
function satir(s,cls){const d=document.createElement("div"); if(cls)d.className=cls; d.textContent=s; mon.appendChild(d); mon.scrollTop=mon.scrollHeight;}
satir("sketch.ino yüklendi ("+SRC.length+" karakter)","sys");
satir("--- SERİ MONİTÖR ---","sys");

let running=true, hiz=4, simMs=0;
const pin={4:0,5:0,6:0,7:0};
function pinMode(p,m){}
function digitalWrite(p,v){pin[p]=v?1:0; goster();}
function millis(){return simMs;}
async function delay(ms){await new Promise(r=>setTimeout(r,Math.max(1,ms/hiz))); simMs+=ms;}
const ser={
  begin(){},
  print(x){satir(String(x));},
  println(x){satir(x===undefined?"":String(x));},
  queue:[], available(){return this.queue.length;}, read(){return this.queue.shift();}
};
function goster(){
  for(let i=0;i<4;i++){
    const el=roles.children[i], on=pin[i+4]===1;
    el.classList.toggle("acik",on);
    const b=el.querySelector(".durum"); b.textContent=on?"ACIK":"KAPALI";
    b.className="durum badge "+(on?"on":"off");
    el.querySelector(".kontak").textContent=on?"COM ——— NO (yük var)":"COM —| |— NO";
  }
}
function gonder(c){ser.queue.push(c.charCodeAt(0)); satir("<- "+c,"cmd");}
document.getElementById("btn").onclick=function(){running=!running;this.textContent=running?"Durdur":"Başlat";};
document.querySelectorAll(".ctrl button").forEach(b=>b.onclick=()=>gonder(b.textContent.trim()[0]));
document.getElementById("inp").addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.value){gonder(e.target.value[0]);e.target.value="";}});
document.getElementById("sin").addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.value){gonder(e.target.value[0]);e.target.value="";}});
document.addEventListener("keydown",e=>{if(e.target.tagName==="INPUT")return; if(e.key>="1"&&e.key<="4")gonder(e.key); if(e.key==="a"||e.key==="k"||e.key==="s")gonder(e.key);});
document.addEventListener("click",e=>{if(e.target.id==="hiz"){hiz=hiz===1?2:hiz===2?4:hiz===4?8:1;e.target.textContent="hız "+hiz+"x";}});
document.getElementById("hiz").style.cursor="pointer";
document.getElementById("hiz").title="Değiştirmek için tıkla";

const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
try{
  const runner=new AsyncFunction("pinMode","digitalWrite","delay","millis","ser","HIGH","LOW","OUTPUT",
    SRC+"\nawait setup();\nwhile(true){ if(!running){await new Promise(r=>setTimeout(r,80));continue;} await loop(); }");
  runner(pinMode,digitalWrite,delay,millis,ser,1,0,1).catch(e=>satir("HATA: "+e,"cmd"));
}catch(e){satir("DERLEME HATASI: "+e,"cmd");}
goster();
</script>
</body>
</html>
"""


def transpile(src):
    s = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    s = re.sub(r"//[^\n]*", "", s)
    s = s.replace("\r", "")
    s = re.sub(r"\bconst int (\w+)\[\d+\] =", r"const \1 =", s)
    s = re.sub(r"\bconst char\* (\w+)\[\d+\] =", r"const \1 =", s)
    s = re.sub(r"\bint (\w+)\[\d+\] =", r"let \1 =", s)
    s = re.sub(r"\bint (\w+) =", r"let \1 =", s)
    s = re.sub(r"= \{([^{}]*)\};", r"= [\1];", s)
    s = re.sub(r"\bfor \(int ", "for (let ", s)

    def fn(m):
        params = re.sub(r"\b(?:int|char|bool|byte)\s+", "", m.group(2))
        return "async function %s(%s)" % (m.group(1), params)
    s = re.sub(r"\bvoid (\w+)\(([^)]*)\)", fn, s)

    s = s.replace("Serial.", "ser.")
    s = s.replace("F(", "(")
    s = s.replace("delay(", "await delay(")
    for name in ("setRelay", "allOn", "allOff", "bekle", "komut"):
        s = re.sub(r"(?<![\w.])" + name + r"\(", "await " + name + "(", s)
    s = s.replace("async function await ", "async function ")
    s = s.replace("await await ", "await ")
    return s.strip()


def main():
    with open(SKETCH, encoding="utf-8") as f:
        src = f.read()
    js = transpile(src)
    html = HTML.replace("/*__SKETCH__*/", json.dumps(js, ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    check = os.path.join(HERE, "build", "_check.js")
    os.makedirs(os.path.dirname(check), exist_ok=True)
    with open(check, "w", encoding="utf-8") as f:
        f.write("async function __test(){\n" + js + "\n}\n")
    print("yazıldı:", OUT)
    print("kaynak:", len(src), "karakter -> JS:", len(js), "karakter")


if __name__ == "__main__":
    main()
