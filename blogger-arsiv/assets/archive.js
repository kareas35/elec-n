// Elektronik Akademi — archive catalog with clear filters and robust search.
fetch('records.json')
.then(r => { if (!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
.then(data => {
  const q=document.querySelector('#search'), s=document.querySelector('#category');
  const list=document.querySelector('#items'),count=document.querySelector('#count'),results=document.querySelector('#results');
  const normalize=v=>String(v||'').toLocaleLowerCase('tr-TR').replace(/\s+/g,' ').trim();
  count.textContent=data.length+' yayın';
  [...new Set(data.map(x=>x.category))].sort((a,b)=>a.localeCompare(b,'tr')).forEach(c=>{const e=document.createElement('option');e.value=c;e.textContent=c;s.append(e)});
  function render(){
    const query=normalize(q.value);
    const filtered=data.filter(x=>(!s.value||x.category===s.value) && normalize([x.title,x.summary,(x.labels||[]).join(' '),x.category].join(' ')).includes(query));
    results.textContent=filtered.length+' yayın listeleniyor';
    const fragment=document.createDocumentFragment();
    for(const x of filtered){
      const a=document.createElement('article'),h=document.createElement('h3'),ln=document.createElement('a'),p=document.createElement('p'),meta=document.createElement('small');
      a.className='item';ln.textContent=x.title;ln.href=x.url;h.append(ln);p.textContent=x.summary;meta.textContent=x.date+' · '+x.category;a.append(h,meta,p);fragment.append(a);
    }
    list.replaceChildren(fragment);
  }
  q.addEventListener('input',render); s.addEventListener('change',render);
  document.querySelector('#resetFilters').addEventListener('click',()=>{q.value='';s.value='';render();q.focus()});
  render();
})
.catch(err=>{document.querySelector('#results').textContent='Arşiv verileri yüklenemedi: '+err.message});
