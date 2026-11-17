// Elektronik Akademi V3.2 - coklu arsiv filtreleri
fetch('records.json')
.then(response => {
  if (!response.ok) throw new Error('HTTP ' + response.status);
  return response.json();
})
.then(data => {
  const search = document.querySelector('#search');
  const category = document.querySelector('#category');
  const contentType = document.querySelector('#contentType');
  const technicalTag = document.querySelector('#technicalTag');
  const list = document.querySelector('#items');
  const count = document.querySelector('#count');
  const results = document.querySelector('#results');
  const reset = document.querySelector('#resetFilters');

  const normalize = value =>
    String(value || '')
      .toLocaleLowerCase('tr-TR')
      .replace(/\s+/g, ' ')
      .trim();

  count.textContent = data.length + ' yayın';

  function addOptions(select, values) {
    for (const value of values) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    }
  }

  const categories = [...new Set(data.map(x => x.category))]
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, 'tr'));

  const tags = [...new Set(
    data.flatMap(x => x.technical_tags || [])
  )].sort((a, b) => a.localeCompare(b, 'tr'));

  addOptions(category, categories);
  addOptions(technicalTag, tags);

  function render() {
    const query = normalize(search.value);

    const filtered = data.filter(item => {
      const matchCategory =
        !category.value || item.category === category.value;

      const matchType =
        !contentType.value ||
        item.content_type === contentType.value;

      const matchTag =
        !technicalTag.value ||
        (item.technical_tags || []).includes(technicalTag.value);

      const searchable = [
        item.title,
        item.summary,
        item.category,
        ...(item.labels || []),
        ...(item.technical_tags || [])
      ].join(' ');

      return matchCategory && matchType &&
        matchTag && normalize(searchable).includes(query);
    });

    results.textContent =
      filtered.length + ' / ' + data.length + ' yayın listeleniyor';

    const fragment = document.createDocumentFragment();

    for (const item of filtered) {
      const article = document.createElement('article');
      article.className = 'item';

      const heading = document.createElement('h3');
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = item.title;
      heading.appendChild(link);

      const meta = document.createElement('small');
      const contentTypeLabels = {
        project: 'Elektronik Projesi',
        lesson: 'Ders',
        component_catalog: 'Bileşen Kataloğu',
        technical_reference: 'Teknik Referans',
        announcement: 'Duyuru'
      };

      const typeLabel = contentTypeLabels[item.content_type]
        ? ' · ' + contentTypeLabels[item.content_type]
        : '';

      meta.textContent =
        item.date + ' · ' + item.category + typeLabel;

      const description = document.createElement('p');
      description.textContent = item.summary || '';

      article.append(heading, meta, description);

      const itemTags = item.technical_tags || [];
      if (itemTags.length) {
        const tagLine = document.createElement('div');
        tagLine.className = 'technical-tags';

        for (const tag of itemTags) {
          const chip = document.createElement('span');
          chip.className = 'pill';
          chip.textContent = tag;
          tagLine.appendChild(chip);
        }

        article.appendChild(tagLine);
      }

      fragment.appendChild(article);
    }

    if (!filtered.length) {
      const empty = document.createElement('p');
      empty.className = 'panel';
      empty.textContent =
        'Seçili filtrelerle eşleşen yayın bulunamadı. Filtreleri temizleyerek yeniden deneyin.';
      fragment.appendChild(empty);
    }

    list.replaceChildren(fragment);
  }

  for (const control of [
    search, category, contentType, technicalTag
  ]) {
    control.addEventListener(
      control === search ? 'input' : 'change',
      render
    );
  }

  reset.addEventListener('click', () => {
    search.value = '';
    category.value = '';
    contentType.value = '';
    technicalTag.value = '';
    render();
    search.focus();
  });

  render();
})
.catch(error => {
  document.querySelector('#results').textContent =
    'Arşiv verileri yüklenemedi: ' + error.message;
});
