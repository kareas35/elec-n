// Shared image viewer: no HTML rewrite or third-party libraries required.
(()=>{
  const container=document.querySelector('article.panel'); if(!container) return;
  const overlay=document.createElement('div');overlay.className='lightbox';overlay.hidden=true;
  overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-label','Görsel büyütme');
  const close=document.createElement('button');close.textContent='Kapat ✕';close.type='button';
  const picture=document.createElement('img');picture.alt='Büyütülmüş devre görseli';
  const tip=document.createElement('p');tip.textContent='Kapatmak için ESC tuşuna basabilir veya görselin dışına tıklayabilirsiniz.';
  overlay.append(close,picture,tip);document.body.append(overlay);
  let previous=null;
  function hide(){overlay.hidden=true;picture.removeAttribute('src');document.body.style.overflow='';if(previous)previous.focus()}
  function show(img){previous=img;picture.src=img.currentSrc||img.src;picture.alt=img.alt||'Büyütülmüş görsel';overlay.hidden=false;document.body.style.overflow='hidden';close.focus()}
  for(const img of container.querySelectorAll('img')){if(img.closest('a[href]')) continue;img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label',(img.alt||'Görsel')+' - büyüt');img.addEventListener('click',()=>show(img));img.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show(img)}})}
  
  container.addEventListener('click',e=>{
    const img=e.target.closest('a[href] img');
    if(!img || !container.contains(img)) return;
    e.preventDefault();
    e.stopPropagation();
    show(img);
  });
  close.addEventListener('click',hide);overlay.addEventListener('click',e=>{if(e.target===overlay||e.target===picture)hide()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!overlay.hidden)hide()});
})();
