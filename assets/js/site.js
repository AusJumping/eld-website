/* Equestrian Land Developments – small progressive enhancements (site works without JS). */
(function () {
  var header = document.querySelector('.site-header');
  var toggle = document.querySelector('.nav-toggle');
  var mobile = window.matchMedia('(max-width: 1020px)');

  // Header shadow on scroll
  var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // Pop-up version of a notice: shown once per visit
  function popup(n, id) {
    var seen = {};
    try { seen = JSON.parse(sessionStorage.getItem('eld-popups') || '{}') || {}; } catch (e) {}
    if (seen[id] || document.querySelector('.notice-pop')) return;
    var style = /notice--(holiday|urgent)/.exec(n.className);
    var t = n.querySelector('.notice-title'), m = n.querySelector('.notice-msg'), a = n.querySelector('p > a'), ic = n.querySelector('.notice-icon');
    var box = document.createElement('div');
    box.className = 'notice-pop';
    box.innerHTML = '<div class="notice-pop-card' + (style ? ' is-' + style[1] : '') + '" role="dialog" aria-modal="true" aria-labelledby="np-title">' +
      '<button class="notice-pop-x" type="button" aria-label="Close">×</button><div class="notice-pop-icon"></div><h2 id="np-title"></h2><p></p>' +
      '<div class="notice-pop-actions"><button class="btn btn-primary np-ok" type="button">OK, thanks</button></div></div>';
    box.querySelector('.notice-pop-icon').innerHTML = ic ? ic.innerHTML : '';
    box.querySelector('h2').textContent = t ? t.textContent : 'Please note';
    box.querySelector('p').textContent = m ? m.textContent : '';
    if (a) { var l = a.cloneNode(true); l.className = 'btn btn-outline'; box.querySelector('.notice-pop-actions').appendChild(l); }
    var last = document.activeElement;
    function close() {
      box.remove(); document.removeEventListener('keydown', esc);
      seen[id] = 1; try { sessionStorage.setItem('eld-popups', JSON.stringify(seen)); } catch (e) {}
      if (last && last.focus) last.focus();
    }
    function esc(e) { if (e.key === 'Escape') close(); }
    box.addEventListener('click', function (e) { if (e.target === box) close(); });
    box.querySelector('.notice-pop-x').addEventListener('click', close);
    box.querySelector('.np-ok').addEventListener('click', close);
    document.addEventListener('keydown', esc);
    document.body.appendChild(box);
    box.querySelector('.np-ok').focus();
  }

  // Site notices (set in the admin): shown between their start/end dates in Queensland time; dismissible for the visit
  var notices = document.querySelectorAll('.notice[data-notice]');
  if (notices.length) {
    var today, gone = {};
    try { today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Australia/Brisbane', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()); }
    catch (e) { today = new Date(Date.now() + 10 * 3600e3).toISOString().slice(0, 10); }
    try { gone = JSON.parse(sessionStorage.getItem('eld-notices') || '{}') || {}; } catch (e) {}
    notices.forEach(function (n) {
      var s = n.getAttribute('data-start'), e = n.getAttribute('data-end'), id = n.getAttribute('data-notice');
      n.hidden = !!((s && today < s) || (e && today > e) || gone[id]);
      if (!n.hidden && n.getAttribute('data-popup') === '1') popup(n, id);
      var x = n.querySelector('.notice-close');
      if (x) x.addEventListener('click', function () {
        n.hidden = true; gone[id] = 1;
        try { sessionStorage.setItem('eld-notices', JSON.stringify(gone)); } catch (err) {}
      });
    });
  }

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
