(() => {
  const container = document.querySelector('article.panel');
  if (!container) return;

  // Stil dosyasi onbellekte kalsa bile lightbox duzgun gorunsun.
  const style = document.createElement('style');
  style.textContent = `
    .ea-lightbox[hidden] { display: none !important; }
    .ea-lightbox {
      position: fixed !important;
      inset: 0 !important;
      z-index: 2147483647 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      background: rgba(8, 15, 28, .94) !important;
      padding: 64px 20px 45px !important;
      box-sizing: border-box !important;
    }
    .ea-lightbox img {
      display: block !important;
      width: auto !important;
      height: auto !important;
      max-width: 96vw !important;
      max-height: calc(100dvh - 110px) !important;
      object-fit: contain !important;
      border-radius: 5px !important;
      box-shadow: 0 12px 50px rgba(0,0,0,.5) !important;
    }
    .ea-lightbox-close {
      position: absolute !important;
      top: 16px !important;
      right: 22px !important;
      align-self: auto !important;
      color: white !important;
      background: #26364d !important;
      border: 1px solid #8493a7 !important;
      border-radius: 50% !important;
      width: 44px !important;
      height: 44px !important;
      padding: 0 !important;
      font: 28px Arial, sans-serif !important;
      cursor: pointer !important;
    }
    .ea-lightbox-close:hover { background: #475569 !important; }
    .ea-lightbox-close:focus-visible {
      outline: 3px solid #fbbf24 !important;
    }
    @media (max-width: 600px) {
      .ea-lightbox { padding: 65px 8px 25px !important; }
    }
  `;
  document.head.appendChild(style);

  const overlay = document.createElement('div');
  overlay.className = 'ea-lightbox';
  overlay.hidden = true;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Büyütülmüş görsel');

  const close = document.createElement('button');
  close.className = 'ea-lightbox-close';
  close.type = 'button';
  close.textContent = '×';
  close.setAttribute('aria-label', 'Görseli kapat');

  const picture = document.createElement('img');
  picture.alt = 'Büyütülmüş görsel';

  overlay.append(close, picture);
  document.body.appendChild(overlay);

  let previous = null;
  let oldOverflow = '';

  function hide() {
    if (overlay.hidden) return;
    overlay.hidden = true;
    picture.removeAttribute('src');
    document.body.style.overflow = oldOverflow;
    if (previous && previous.isConnected) previous.focus();
  }

  function show(img) {
    previous = img.closest('a[href]') || img;
    oldOverflow = document.body.style.overflow;

    const link = img.closest('a[href]');
    const href = link && link.href;
    const isImage = href && (
      /\.(png|jpe?g|gif|webp|bmp)(\?|#|$)/i.test(href) ||
      href.includes('blogger.googleusercontent.com')
    );

    picture.src = isImage ? href : (img.currentSrc || img.src);
    picture.alt = img.alt || 'Büyütülmüş görsel';
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    close.focus();
  }

  for (const img of container.querySelectorAll('img')) {
    img.style.cursor = 'zoom-in';
    const link = img.closest('a[href]');

    if (!link) {
      img.tabIndex = 0;
      img.setAttribute('role', 'button');
      img.setAttribute('aria-label', 'Görseli büyüt');
    }

    img.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      show(img);
    });

    if (!link) {
      img.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          show(img);
        }
      });
    }
  }

  // Baglanti icindeki resimlerde klavye destegi.
  container.addEventListener('click', e => {
    if (!e.target.closest('img')) return;
    e.preventDefault();
  });

  close.addEventListener('click', hide);

  overlay.addEventListener('click', e => {
    if (e.target === overlay) hide();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !overlay.hidden) {
      e.preventDefault();
      hide();
    }
  });
})();
