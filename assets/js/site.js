/* Equestrian Land Developments – small progressive enhancements (site works without JS). */
(function () {
  var header = document.querySelector('.site-header');
  var toggle = document.querySelector('.nav-toggle');
  var mobile = window.matchMedia('(max-width: 1020px)');

  // Header shadow on scroll
  var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // Mobile menu
  toggle.addEventListener('click', function () {
    document.documentElement.style.setProperty('--nav-top', Math.round(header.getBoundingClientRect().bottom) + 'px');
    var open = document.body.classList.toggle('nav-open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  // Dropdowns: click/tap + keyboard, hover on desktop
  var items = document.querySelectorAll('.nav-item.has-sub');
  function closeAll(except) {
    items.forEach(function (li) {
      if (li !== except) { li.classList.remove('is-open'); li.querySelector('button').setAttribute('aria-expanded', 'false'); }
    });
  }
  items.forEach(function (li) {
    var btn = li.querySelector('button');
    var timer;
    btn.addEventListener('click', function () {
      var open = !li.classList.contains('is-open');
      closeAll(li);
      li.classList.toggle('is-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    li.addEventListener('mouseenter', function () {
      if (mobile.matches) return;
      clearTimeout(timer); closeAll(li); li.classList.add('is-open'); btn.setAttribute('aria-expanded', 'true');
    });
    li.addEventListener('mouseleave', function () {
      if (mobile.matches) return;
      timer = setTimeout(function () { li.classList.remove('is-open'); btn.setAttribute('aria-expanded', 'false'); }, 160);
    });
    li.addEventListener('focusout', function (e) {
      if (!mobile.matches && !li.contains(e.relatedTarget)) { li.classList.remove('is-open'); btn.setAttribute('aria-expanded', 'false'); }
    });
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.nav-item.has-sub')) closeAll(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeAll();
      if (document.body.classList.contains('nav-open')) { document.body.classList.remove('nav-open'); toggle.setAttribute('aria-expanded', 'false'); toggle.focus(); }
    }
  });

  // Lightbox for galleries and figures
  var box = document.querySelector('.lightbox');
  var links = Array.prototype.slice.call(document.querySelectorAll('a.lb'));
  if (!box || !links.length) return;
  var bimg = box.querySelector('img'), bcap = box.querySelector('figcaption'), idx = 0, lastFocus;
  function show(i) {
    idx = (i + links.length) % links.length;
    var a = links[idx];
    bimg.src = a.getAttribute('href');
    bimg.alt = a.dataset.caption || '';
    bcap.textContent = a.dataset.caption || '';
  }
  function open(i) { lastFocus = document.activeElement; show(i); box.hidden = false; document.body.style.overflow = 'hidden'; box.querySelector('.lb-close').focus(); }
  function close() { box.hidden = true; bimg.src = ''; document.body.style.overflow = ''; if (lastFocus) lastFocus.focus(); }
  links.forEach(function (a, i) { a.addEventListener('click', function (e) { e.preventDefault(); open(i); }); });
  box.querySelector('.lb-close').addEventListener('click', close);
  box.querySelector('.lb-prev').addEventListener('click', function () { show(idx - 1); });
  box.querySelector('.lb-next').addEventListener('click', function () { show(idx + 1); });
  box.addEventListener('click', function (e) { if (e.target === box) close(); });
  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') show(idx - 1);
    if (e.key === 'ArrowRight') show(idx + 1);
  });
  if (links.length < 2) { box.querySelector('.lb-prev').hidden = true; box.querySelector('.lb-next').hidden = true; }
})();
