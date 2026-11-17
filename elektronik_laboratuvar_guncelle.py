#!/usr/bin/env python3
"""Elektronik Akademi Dirençler dersi: güvenli laboratuvar yükseltmesi.
Codespaces proje kökünden: python3 elektronik_laboratuvar_guncelle.py
"""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

FILE = Path('Dersler/direncler.html')
MARKER = 'ELEKTRONIK_AKADEMI_LAB_V1'
if not FILE.is_file():
    sys.exit('HATA: Proje kokunde calistir. Dersler/direncler.html bulunamadi.')
original = FILE.read_text(encoding='utf-8')
if MARKER in original:
    sys.exit('Bilgi: Laboratuvar zaten kurulu. Dosyada degisiklik yapilmadi.')

start_section = '<section class="panel" id="seri">'
end_section = '<section class="panel" id="uygulama">'
js_start_pattern = re.compile(r"let mode\s*=\s*'series';")
js_end_anchor = "document.getElementById('quiz').addEventListener"
checks = [original.count(start_section) == 1, original.count(end_section) == 1,
          len(js_start_pattern.findall(original)) == 1,
          original.count(js_end_anchor) == 1,
          original.count('</style>') == 1,
          original.count('<section class="panel" id="renkler">') == 1]
if not all(checks):
    sys.exit('HATA: Dosyanin beklenen yapisi farkli. Hicbir sey degistirilmedi.')
a = original.index(start_section)
b = original.index(end_section)
c = js_start_pattern.search(original).start()
d = original.index(js_end_anchor)
if not (a < b < c < d):
    sys.exit('HATA: Bolumlerin sirasi uygun degil; degisiklik yapilmadi.')

CSS = r'''
/* ELEKTRONIK_AKADEMI_LAB_V1 */
.lab-switch {display:flex;flex-wrap:wrap;gap:9px;margin:15px 0}
.lab-switch .switch {font-size:.92rem}
.lab-controls {display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:16px}
.lab-controls label{display:block;font-weight:650}
.lab-controls [hidden],.lab-stage[hidden]{display:none!important}
.lab-controls input,.lab-controls select {display:block;width:100%;margin-top:6px;padding:9px;border:1px solid #afc0d2;border-radius:9px;background:white;color:#1d2939}
.lab-controls input[type=range]{padding:0;accent-color:#1565c0}
.lab-svg{width:100%;height:auto;display:block}
.lab-stage{background:#edf5ff;border-radius:13px;padding:12px;margin:14px 0}
.lab-stage svg{max-height:none}
.lab-details{margin-top:12px;line-height:1.8}
.lab-details strong{font-size:1.4rem;color:#165d36}
.lab-hint{padding:12px 15px;background:#f4f8ff;border-left:4px solid #1565c0;border-radius:9px;margin-top:12px}
.lab-result{padding:16px;background:#e9f6ee;border:1px solid #bce6cc;border-radius:12px;margin-top:16px}
.lab-answer{display:flex;flex-direction:column;gap:8px;margin:14px 0}
.lab-answer label{padding:9px 12px;border:1px solid #dce4ec;border-radius:9px;cursor:pointer}
.lab-status{margin-top:12px;font-weight:600}
.lab-status.good{color:#136939}.lab-status.bad{color:#9d2626}
.lab-led{transition:fill .2s,filter .2s}
.lab-bb-note{font-size:.91rem;color:#536174}
@media(max-width:600px){.lab-stage{padding:5px}.lab-switch .switch{padding:8px}}
@media(prefers-reduced-motion:reduce){.lab-stage animateMotion{display:none}}
'''

SECTION = r'''
<section class="panel" id="seri">
  <h2>4. Seri, paralel ve karışık devre laboratuvarı</h2>
  <p>Bağlantı türünü seç, dirençleri ve pil gerilimini değiştir. Yeşil noktalar <strong>geleneksel akım yönünü</strong> temsil eder. Animasyon hızı yalnızca öğretici amaçlıdır; elektronların gerçek hızını göstermez.</p>
  <div class="lab-switch" role="group" aria-label="Bağlantı türleri">
    <button type="button" class="switch" id="seriesBtn" aria-pressed="true">Seri</button>
    <button type="button" class="switch" id="parallelBtn" aria-pressed="false">Paralel</button>
    <button type="button" class="switch" id="mixedBtn" aria-pressed="false">Seri + Paralel</button>
    <button type="button" class="switch" id="breadBtn" aria-pressed="false">Breadboard</button>
  </div>
  <div class="lab-stage" id="schematicStage">
    <svg id="labCircuit" class="lab-svg" viewBox="0 0 620 270" role="img" aria-label="Pil ile beslenen direnç devresi">
      <g id="labWires" fill="none" stroke="#1565c0" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></g>
      <g id="labComponents"></g>
      <g id="labTexts" fill="#234d7b" text-anchor="middle" font-size="16"></g>
      <g id="labParticles"></g>
    </svg>
  </div>
  <div class="lab-stage" id="breadboardStage" hidden>
    <svg id="labBreadboard" class="lab-svg" viewBox="0 0 720 400" role="img" aria-label="A-J delikleri ve numaralı satırları gösteren karışık devre breadboard yerleşimi"></svg>
    <p class="lab-bb-note">A–E ve F–J, <strong>aynı numaralı satırda ayrı</strong> beşli bağlantı gruplarıdır. Ortadaki kanal onları ayırır. Kırmızı/mavi güç hatları bu örnekte kesintisiz varsayılmıştır. Gerçek breadboard'un bağlantı şemasını kontrol et.</p>
  </div>
  <div class="lab-controls">
    <label>R1 (Ω)<input id="r1" type="number" min="1" max="1000000" step="1" value="220"></label>
    <label>R2 (Ω)<input id="r2" type="number" min="1" max="1000000" step="1" value="330"></label>
    <label id="r3Field">R3 (Ω)<input id="r3" type="number" min="1" max="1000000" step="1" value="330"></label>
    <label>Pil gerilimi (V)<input id="source" type="number" min="0" max="50" step="0.5" value="9"></label>
    <label>Gerilimi kaydır<input id="sourceSlider" type="range" min="0" max="50" step="0.5" value="9"></label>
  </div>
  <div class="lab-result" aria-live="polite">
    <div>Eşdeğer direnç</div><strong id="equivalent">—</strong>
    <div id="seriesExplanation" class="lab-details"></div>
    <div id="currentResult"></div><div id="branchResult"></div>
    <div id="branchVoltage"></div>
  </div>
  <p class="lab-hint" id="labTeaching">Seride aynı akım tüm dirençlerden geçer.</p>
</section>
<section class="panel" id="bbExercise">
  <h2>5. Breadboard bağlantı alıştırması</h2>
  <p>Karışık devrede <strong>R2 ve R3 paralel</strong> olabilmesi için, sol ve sağ tarafın bağlantı düğümleri ortak olmalıdır. Breadboard üzerindeki orta kanalın iki tarafını doğru kabloyla birleştirmek gerekir.</p>
  <p><strong>Soru:</strong> Hangi jumper (bağlantı kablosu), R2 ile R3'ün giriş uçlarını aynı düğüme bağlar?</p>
  <div class="lab-answer" id="bbAnswers">
    <label><input type="radio" name="bbQuestion" value="ok"> E5 ile F5'i bağlamak</label>
    <label><input type="radio" name="bbQuestion" value="wrong"> E5 ile F8'i bağlamak</label>
    <label><input type="radio" name="bbQuestion" value="danger"> Pozitif ve negatif güç hatlarını doğrudan bağlamak</label>
  </div>
  <button class="action" type="button" id="bbCheck">Bağlantıyı kontrol et</button>
  <div class="lab-status" id="bbFeedback" role="status" aria-live="polite"></div>
  <p class="small muted">Bu alıştırma temsili bağlantıları değerlendirir. Kısa devre olabilecek bağlantıları gerçek pil üzerinde deneme.</p>
</section>
<section class="panel" id="ledBreadboard">
  <h2>6. LED + direnç + breadboard mini uygulaması</h2>
  <p>LED'in uzun bacağı genellikle <strong>anot (+)</strong>, kısa bacağı <strong>katot (−)</strong> olarak adlandırılır. Uygun yönde ve seri dirençle bağlanmalıdır. LED'in veri sayfası esas alınır.</p>
  <div class="lab-stage">
    <svg class="lab-svg" viewBox="0 0 620 220" role="img" aria-label="Direnç ile seri bağlı LED devre çizimi">
      <g stroke="#1565c0" stroke-width="4" fill="none" stroke-linejoin="round">
        <path d="M90 45 H185 M255 45 H370 M422 45 H525 V177 H90 V108 M90 86 V45"/>
        <path d="M66 86 H114 M76 108 H104" stroke="#234d7b"/>
        <rect x="185" y="32" width="70" height="26" rx="5" fill="#e8bb7b" stroke="#98622e"/>
        <path d="M370 24 L370 66 L414 45 Z" fill="#cbd5e1" stroke="#234d7b"/>
        <path d="M422 24 V66" stroke="#234d7b"/>
      </g>
      <circle id="labLedGlow" class="lab-led" cx="396" cy="45" r="29" fill="#94a3b8" opacity=".30"/>
      <g font-size="15" fill="#234d7b" text-anchor="middle">
        <text x="220" y="20">Seri direnç</text><text x="395" y="105">LED</text>
        <text x="125" y="88">+</text><text x="125" y="112">−</text>
        <text x="310" y="201">Breadboard bağlantı ilkesi (şematik)</text>
      </g>
    </svg>
  </div>
  <div class="lab-stage">
    <svg class="lab-svg" viewBox="0 0 620 230" role="img" aria-label="LED ve seri direnç için breadboard üzerinde örnek doğru yerleşim">
      <rect x="75" y="25" width="470" height="180" rx="14" fill="white" stroke="#b7c4d6" stroke-width="2"/>
      <path d="M105 47 H515" stroke="#e34848" stroke-width="3"/>
      <path d="M105 185 H515" stroke="#3475cc" stroke-width="3"/>
      <g font-size="12" fill="#234d7b" text-anchor="middle">
        <text x="155" y="78">A</text><text x="185" y="78">B</text><text x="215" y="78">C</text><text x="245" y="78">D</text><text x="275" y="78">E</text>
        <text x="335" y="78">F</text><text x="365" y="78">G</text><text x="395" y="78">H</text><text x="425" y="78">I</text><text x="455" y="78">J</text>
        <text x="105" y="115">2</text><text x="105" y="145">3</text>
        <text x="310" y="158">Orta kanal</text>
      </g>
      <g fill="#cbd5e1">
        <circle cx="155" cy="110" r="4"/><circle cx="185" cy="110" r="4"/><circle cx="215" cy="110" r="4"/><circle cx="245" cy="110" r="4"/><circle cx="275" cy="110" r="4"/>
        <circle cx="335" cy="110" r="4"/><circle cx="365" cy="110" r="4"/><circle cx="395" cy="110" r="4"/><circle cx="425" cy="110" r="4"/><circle cx="455" cy="110" r="4"/>
        <circle cx="155" cy="140" r="4"/><circle cx="185" cy="140" r="4"/><circle cx="215" cy="140" r="4"/><circle cx="245" cy="140" r="4"/><circle cx="275" cy="140" r="4"/>
        <circle cx="335" cy="140" r="4"/><circle cx="365" cy="140" r="4"/><circle cx="395" cy="140" r="4"/><circle cx="425" cy="140" r="4"/><circle cx="455" cy="140" r="4"/>
      </g>
      <g stroke-width="4" fill="none"><path d="M155 47 V68 M155 91 V110" stroke="#e34848"/><path d="M455 110 V185" stroke="#3475cc"/><path d="M275 110 H335" stroke="#16a34a"/></g>
      <rect x="146" y="68" width="18" height="23" rx="6" fill="#e8bb7b" stroke="#98622e" stroke-width="2"/>
      <circle cx="305" cy="110" r="12" fill="#facc15" stroke="#98622e" stroke-width="2"/>
      <g font-size="12" fill="#234d7b"><text x="120" y="90">R</text><text x="290" y="97">LED</text><text x="108" y="40">+</text><text x="108" y="198">−</text></g>
    </svg>
    <p class="lab-bb-note">Örnek bağlantı: kırmızı (+) hat → seri direnç → A2–E2 grubu → LED anot → LED katot → F2–J2 grubu → mavi (−) hat. LED, orta kanalı aşar. Bu bir bağlantı öğretim çizimidir.</p>
  </div>
  <div class="lab-controls">
    <label>Pil gerilimi (V)<input id="ledV" type="number" min="0" max="24" step="0.5" value="9"></label>
    <label>Seri direnç (Ω)<input id="ledR" type="number" min="1" max="1000000" step="1" value="470"></label>
    <label>LED bağlantısı
      <select id="ledConnection">
        <option value="correct">Doğru: direnç seri, LED ileri yönde</option>
        <option value="reverse">Yanlış: LED ters yönde</option>
        <option value="open">Yanlış: bağlantı kablosu eksik</option>
        <option value="short">Tehlikeli: LED'in seri direnci atlanmış</option>
      </select>
    </label>
  </div>
  <div class="lab-result" aria-live="polite"><strong id="ledCurrent">—</strong><div id="ledFeedback"></div></div>
  <p class="small muted">Basitleştirilmiş kırmızı LED modeli: ileri gerilim yaklaşık 2 V; 5–20 mA eğitim için örnek çalışma aralığıdır, evrensel güvenli aralık değildir. Ters akım, sıcaklık ve LED güç sınırları fiziksel simülatör düzeyinde modellenmez.</p>
</section>
'''

JS = r'''
/* Direnç devresi ve breadboard laboratuvarı */
(function () {
  'use strict';
  const byId = id => document.getElementById(id);
  const fmtLab = (n,d=3) => Number(n).toLocaleString('tr-TR',{maximumFractionDigits:d});
  const unitLab = n => n>=1e6?fmtLab(n/1e6)+' MΩ':n>=1000?fmtLab(n/1000)+' kΩ':fmtLab(n)+' Ω';
  let mode = 'series';
  const svgNS = 'http://www.w3.org/2000/svg';
  const makeSVG = (tag, attributes, content) => {
    const el=document.createElementNS(svgNS,tag);
    Object.entries(attributes||{}).forEach(([k,v])=>el.setAttribute(k,v));
    if(content!==undefined)el.textContent=content;
    return el;
  };
  const textAt=(g,x,y,value,size=15)=>g.appendChild(makeSVG('text',{x,y,'font-size':size},value));
  const rectAt=(g,x,y,w=65,h=26)=>g.appendChild(makeSVG('rect',{x,y,width:w,height:h,rx:5,fill:'#e8bb7b',stroke:'#98622e','stroke-width':2}));
  const pathAt=(g,d,stroke='#1565c0',width=4)=>g.appendChild(makeSVG('path',{d,fill:'none',stroke,'stroke-width':width,'stroke-linejoin':'round'}));
  const addParticle=(g,path,dur,begin,opacity=1)=>{
    const circle=makeSVG('circle',{r:5,fill:'#16a34a',opacity});
    circle.appendChild(makeSVG('animateMotion',{path,dur:dur+'s',begin:begin+'s',repeatCount:'indefinite'}));
    g.appendChild(circle);
  };
  const battery=(w,t)=>{
    pathAt(w,'M72 48 V91 M72 116 V193');
    pathAt(w,'M49 91 H95 M59 116 H85','#234d7b',4);
    textAt(t,114,92,'+',16);textAt(t,114,120,'−',16);
  };
  function diagram(currentTotal=0,current2=0,current3=0){
    const w=byId('labWires'),t=byId('labTexts'),p=byId('labParticles'),c=byId('labComponents');
    [w,t,p,c].forEach(el=>el.replaceChildren());
    battery(w,t);
    let v=byId('source').value;
    textAt(t,140,236,'Pil: '+(v===''?'—':fmtLab(+v,1)+' V'),17);
    const speed=I=>Math.max(.75,Math.min(9,120/Math.max(I,.05)));
    if(mode==='series'){
      pathAt(w,'M72 48 H165 M235 48 H305 M375 48 H516 V193 H72');
      rectAt(c,165,35,70);rectAt(c,305,35,70);
      textAt(t,200,28,'R1 = '+byId('r1').value+' Ω',13);
      textAt(t,340,28,'R2 = '+byId('r2').value+' Ω',13);
      const route='M72 48 H516 V193 H72 V116';
      for(let i=0;i<4;i++)addParticle(p,route,speed(currentTotal),(-i*speed(currentTotal)/4).toFixed(2));
    }else if(mode==='parallel'){
      pathAt(w,'M72 48 H148 H235 M305 48 H516 V193 H72 M148 48 V124 H235 M305 124 H516');
      rectAt(c,235,35,70);rectAt(c,235,111,70);
      textAt(t,270,27,'R1 = '+byId('r1').value+' Ω',13);
      textAt(t,270,104,'R2 = '+byId('r2').value+' Ω',13);
      addParticle(p,'M72 48 H148',speed(currentTotal),0);
      for(let i=0;i<3;i++){
        addParticle(p,'M148 48 H516 V193 H72 V116',speed(current2),-i*speed(current2)/3);
        addParticle(p,'M148 48 V124 H516 V193 H72 V116',speed(current3),-i*speed(current3)/3);
      }
    }else{
      pathAt(w,'M72 48 H158 M228 48 H290 H370 M440 48 H516 V193 H72 M290 48 V128 H370 M440 128 H516');
      rectAt(c,158,35,70);rectAt(c,370,35,70);rectAt(c,370,115,70);
      textAt(t,193,27,'R1 = '+byId('r1').value+' Ω',13);
      textAt(t,405,27,'R2 = '+byId('r2').value+' Ω',13);
      textAt(t,405,107,'R3 = '+byId('r3').value+' Ω',13);
      for(let i=0;i<4;i++){
        addParticle(p,'M72 48 H290',speed(currentTotal),-i*speed(currentTotal)/4);
      }
      for(let i=0;i<4;i++){
        addParticle(p,'M290 48 H516 V193 H72 V116',speed(current2),-i*speed(current2)/4);
        addParticle(p,'M290 48 V128 H516 V193 H72 V116',speed(current3),-i*speed(current3)/4);
      }
    }
  }

  function breadboard(){
    const svg=byId('labBreadboard');svg.replaceChildren();
    svg.appendChild(makeSVG('rect',{x:90,y:48,width:570,height:305,rx:18,fill:'#fff',stroke:'#b7c4d6','stroke-width':2}));
    // Seçilen model: A-E ve F-J, aynı numaralı satırda beşli bağlantı gruplarıdır.
    const xs=[195,225,255,285,315,395,425,455,485,515];
    const letters='ABCDEFGHIJ';
    xs.forEach((x,i)=>textAt(svg,x,111,letters[i],12));
    for(let row=1;row<=10;row++){
      const y=112+row*20;
      textAt(svg,146,y+4,String(row),11);
      xs.forEach(x=>svg.appendChild(makeSVG('circle',{cx:x,cy:y,r:4.5,fill:'#d0d9e4',stroke:'#9aa9b9','stroke-width':.5})));
    }
    pathAt(svg,'M125 69 H625','#e34848',4);pathAt(svg,'M125 334 H625','#3475cc',4);
    textAt(svg,108,74,'+',16);textAt(svg,108,339,'−',16);
    pathAt(svg,'M355 125 V323','#c6ced8',1);
    textAt(svg,355,365,'Orta kanal',13);
    // R1: A2 -> A5; R2: B5 -> B8; R3: H5 -> H8.
    // Jumper E5-F5 ve E8-F8, iki yarım sırayı bağlar.
    // Güç rail+ A2'ye, rail- B8'e gider.
    const segments=[
      ['M150 69 V152 H195','#e34848'],
      ['M195 152 V212','#a56b2a'],
      ['M225 212 V272','#a56b2a'],
      ['M455 212 V272','#a56b2a'],
      ['M315 212 H395','#16a34a'],
      ['M315 272 H395','#16a34a'],
      ['M225 272 V334 H150','#3475cc']
    ];
    segments.forEach(([d,color])=>pathAt(svg,d,color,5));
    rectAt(svg,185,171,20,22);rectAt(svg,215,231,20,22);rectAt(svg,445,231,20,22);
    textAt(svg,177,165,'R1',12);textAt(svg,205,226,'R2',12);textAt(svg,473,226,'R3',12);
    textAt(svg,557,178,'R1 seri',14);textAt(svg,557,202,'R2 ∥ R3',14);
    textAt(svg,565,226,'E5–F5',12);textAt(svg,565,245,'E8–F8',12);
    textAt(svg,553,297,'Pil: '+fmtLab(+byId('source').value||0,1)+' V',13);
  }
  function updateNetwork(){
    const ids=mode==='series'||mode==='parallel'?['r1','r2']:['r1','r2','r3'];
    const valid=ids.every(id=>byId(id).value.trim()!=='' && Number.isFinite(+byId(id).value) && +byId(id).value>0 && +byId(id).value<=1000000)
      && byId('source').value.trim()!=='' && Number.isFinite(+byId('source').value)
      && +byId('source').value>=0 && +byId('source').value<=50;
    if(!valid){
      byId('equivalent').textContent='Geçersiz değer';
      byId('seriesExplanation').textContent='Dirençler: 1–1.000.000 Ω, gerilim: 0–50 V.';
      byId('currentResult').textContent='';byId('branchResult').textContent='';byId('branchVoltage').textContent='';
      byId('labParticles').replaceChildren();return;
    }
    const r1=+byId('r1').value,r2=+byId('r2').value,r3=+byId('r3').value,v=+byId('source').value;
    let req,description='',branch='',branchv='',i2=0,i3=0;
    if(mode==='series'){
      req=r1+r2;description=`R eş = ${fmtLab(r1)} + ${fmtLab(r2)} = ${fmtLab(req)} Ω`;
    }else if(mode==='parallel'){
      req=r1*r2/(r1+r2);i2=v/r1*1000;i3=v/r2*1000;
      description=`R eş = (R1 × R2) / (R1 + R2) = ${fmtLab(req)} Ω`;
      branch=`R1 kolu: ${fmtLab(i2)} mA | R2 kolu: ${fmtLab(i3)} mA`;
      branchv=`Paralel kollarda gerilim: ${fmtLab(v)} V`;
    }else{
      const rp=r2*r3/(r2+r3);req=r1+rp;
      const vp=v*rp/req;i2=vp/r2*1000;i3=vp/r3*1000;
      description=`R2 ∥ R3 = ${fmtLab(rp)} Ω; R eş = R1 + (R2 ∥ R3) = ${fmtLab(req)} Ω`;
      branch=`R2 kolu: ${fmtLab(i2)} mA | R3 kolu: ${fmtLab(i3)} mA`;
      branchv=`R2 ve R3 üzerindeki gerilim: ${fmtLab(vp)} V`;
    }
    const it=v/req*1000;
    byId('equivalent').textContent=unitLab(req);
    byId('seriesExplanation').textContent=description;
    byId('currentResult').textContent=`Kaynak akımı: ${fmtLab(it)} mA`;
    byId('branchResult').textContent=branch;
    byId('branchVoltage').textContent=branchv;
    diagram(it,i2,i3);
    breadboard();
  }
  function setMode(next){
    mode=next;
    const modes={seriesBtn:'series',parallelBtn:'parallel',mixedBtn:'mixed',breadBtn:'breadboard'};
    Object.entries(modes).forEach(([id,m])=>byId(id).setAttribute('aria-pressed',String(m===mode)));
    byId('schematicStage').hidden=mode==='breadboard';
    byId('breadboardStage').hidden=mode!=='breadboard';
    byId('r3Field').hidden=mode==='series'||mode==='parallel';
    const guide={
      series:'Seri devrede akım bütün dirençlerden aynı miktarda geçer.',
      parallel:'Paralel devrede tüm kollarda gerilim aynı, akım ise dirençlere göre farklıdır.',
      mixed:'R1 üzerinden toplam akım geçer; R2 ve R3 kollarına bölünür. Direnci düşük kolda akım daha fazladır.',
      breadboard:'Breadboard: aynı satırdaki A–E ve F–J grupları ayrıdır; E5–F5 ve E8–F8 jumper kablolarıyla köprülenir.'
    };
    byId('labTeaching').textContent=guide[mode];
    updateNetwork();
  }
  Object.entries({seriesBtn:'series',parallelBtn:'parallel',mixedBtn:'mixed',breadBtn:'breadboard'})
    .forEach(([id,m])=>byId(id).addEventListener('click',()=>setMode(m)));
  ['r1','r2','r3'].forEach(id=>byId(id).addEventListener('input',updateNetwork));
  byId('source').addEventListener('input',()=>{byId('sourceSlider').value=byId('source').value;updateNetwork();});
  byId('sourceSlider').addEventListener('input',()=>{byId('source').value=byId('sourceSlider').value;updateNetwork();});
  byId('bbCheck').addEventListener('click',()=>{
    const chosen=document.querySelector('input[name="bbQuestion"]:checked');
    const el=byId('bbFeedback');el.className='lab-status';
    if(!chosen){el.textContent='Önce bir bağlantı seç.';return;}
    if(chosen.value==='ok'){
      el.classList.add('good');el.textContent='✓ Doğru! E5 ile F5 jumper kablosu, iki yarım sıradaki paralel giriş düğümünü birleştirir. E8–F8 çıkış için ayrıca bağlanmalıdır.';
    }else if(chosen.value==='danger'){
      el.classList.add('bad');el.textContent='✗ Tehlikeli! Pozitif ve negatif güç hatlarını doğrudan birleştirmek kısa devre yapabilir. Gerçek pil ile deneme.';
    }else{
      el.classList.add('bad');el.textContent='✗ E5 ile F8 farklı düğümlerdir; bu jumper R2/R3 girişini doğru birleştirmez ve bağlantıyı değiştirir.';
    }
  });
  function updateLed(){
    const rawV=byId('ledV').value,rawR=byId('ledR').value,mode=byId('ledConnection').value;
    const out=byId('ledCurrent'),feedback=byId('ledFeedback'),glow=byId('labLedGlow');
    const v=+rawV,r=+rawR;
    if(rawV===''||rawR===''||!Number.isFinite(v)||!Number.isFinite(r)||v<0||v>24||r<1||r>1e6){
      out.textContent='Geçersiz değer';feedback.textContent='Pil: 0–24 V, direnç: 1–1.000.000 Ω.';
      glow.setAttribute('fill','#94a3b8');glow.setAttribute('opacity','.3');return;
    }
    let current=0,message='',status='';
    if(mode==='reverse'){message='LED ters yönde: bu basit modelde yanmaz. Yüksek ters gerilim gerçek LED’e zarar verebilir.';status='bad';}
    else if(mode==='open'){message='Açık devre: kablo eksik, akım geçmez ve LED yanmaz.';status='bad';}
    else if(mode==='short'){message='Tehlikeli bağlantı: seri direnç atlandığında akım güvenli biçimde hesaplanamaz. Bu düzeni gerçek devrede kurma.';status='bad';}
    else{
      current=Math.max(0,(v-2)/r*1000);
      if(v<2){message='Pil gerilimi LED’in yaklaşık 2 V ileri gerilimine ulaşmadı: LED sönük.';status='bad';}
      else if(current<5){message='Akım düşük; LED sönük veya çok zayıf görünebilir.';status='bad';}
      else if(current<=20){message='Uygun örnek akım: LED yanıyor. Kesin sınır için LED veri sayfasını kontrol et.';status='good';}
      else{message='Aşırı akım riski! Daha yüksek bir seri direnç seç. Gerçek LED zarar görebilir.';status='bad';}
    }
    out.textContent=mode==='short'?'Akım: güvenli hesaplanamaz':'Hesaplanan akım: '+fmtLab(current)+' mA';
    feedback.textContent=message;feedback.className='lab-status '+status;
    const on=mode==='correct' && current>=5 && current<=20;
    glow.setAttribute('fill',on?'#facc15':'#94a3b8');
    glow.setAttribute('opacity',on?'.85':'.3');
  }
  ['ledV','ledR','ledConnection'].forEach(id=>byId(id).addEventListener('input',updateLed));
  setMode('series');updateLed();
})();
'''

result = original[:a] + SECTION + original[b:c] + JS + original[d:]
# Yeni modüllerden sonra ders numaralarını tutarlı hale getir.
result = result.replace('<section class="panel" id="uygulama"><h2>5.', '<section class="panel" id="uygulama"><h2>7.', 1)
result = result.replace('<section class="panel" id="test"><h2>6.', '<section class="panel" id="test"><h2>8.', 1)
result = result.replace('<a href="#seri">4. Seri ve paralel</a><a href="#uygulama">5. Mini uygulama</a><a href="#test">6. Bilgi testi</a>',
  '<a href="#seri">4. Devre laboratuvarı</a><a href="#bbExercise">5. Breadboard alıştırması</a><a href="#ledBreadboard">6. LED uygulaması</a><a href="#uygulama">7. Mini uygulama</a><a href="#test">8. Bilgi testi</a>',1)
result = result.replace('<span class="chip">6 konu</span>', '<span class="chip">8 konu</span>', 1)
result = result.replace('</style>', CSS + '\n</style>', 1)
# Script only changes the teaching section and its own JS, preserving quiz and color code model.
if result.count(MARKER) != 1 or result.count('id="quiz"') != 1 or result.count('id="c1"') != 1:
    sys.exit('HATA: Degisiklik dogrulanamadi; dosyaya dokunulmadi.')
backup = FILE.with_name(FILE.name + '.before-lab-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.bak')
shutil.copy2(FILE, backup)
FILE.write_text(result, encoding='utf-8')
print('BAŞARILI: Seri, paralel, karışık, breadboard, akım animasyonu, bağlantı alıştırması ve LED mini uygulaması eklendi.')
print('Yedek:',backup)
print('Şimdi: git diff --check && git diff --stat')
