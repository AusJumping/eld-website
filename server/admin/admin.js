/* ELD website admin – edits content/notices.json and content/shop.json through the server API. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var state = { shop: null, notices: null };   // {data, sha}
  var saved = { shop: '', notices: '' };       // JSON snapshot at last load/save, for "unsaved changes"
  var savedPrices = {};
  var polling = null;

  // ---------------------------------------------------------------- helpers
  function api(method, path, body) {
    return fetch(path, {
      method: method, credentials: 'same-origin', cache: 'no-store',
      headers: body ? { 'Content-Type': 'application/json', 'X-ELD-Admin': '1' } : { 'X-ELD-Admin': '1' },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, json: j }; });
    }, function () { return { ok: false, status: 0, json: { error: 'Couldn\'t reach the server. Check your internet connection and try again.' } }; });
  }
  function today() {
    try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'Australia/Brisbane', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()); }
    catch (e) { return new Date(Date.now() + 10 * 3600e3).toISOString().slice(0, 10); }
  }
  function nice(d) {
    if (!d) return '';
    var p = d.split('-');
    return new Date(+p[0], +p[1] - 1, +p[2]).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function show(el, on) { el.hidden = !on; }
  function status(kind, html) {
    var s = $('status');
    s.className = 'status ' + (kind || '');
    s.innerHTML = html;
    show(s, !!html);
  }
  function snapshot(key) { return JSON.stringify(state[key] && state[key].data); }
  function markDirty() {
    show($('dirty-notices'), state.notices && snapshot('notices') !== saved.notices);
    show($('dirty-products'), state.shop && snapshot('shop') !== saved.shop);
  }
  function anyDirty() { return (state.notices && snapshot('notices') !== saved.notices) || (state.shop && snapshot('shop') !== saved.shop); }
  window.addEventListener('beforeunload', function (e) { if (anyDirty()) { e.preventDefault(); e.returnValue = ''; } });

  // ---------------------------------------------------------------- sign in
  function showLogin(msg) {
    show($('loading'), false); show($('app'), false); show($('top-nav'), false); show($('login'), true);
    var err = $('login-error');
    err.textContent = msg || ''; show(err, !!msg);
    $('password').value = '';
    $('password').focus();
  }
  $('login-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = e.target.querySelector('button'); btn.disabled = true;
    api('POST', '/admin/api/login', { password: $('password').value }).then(function (r) {
      btn.disabled = false;
      if (r.ok) return load();
      showLogin(r.json.error || 'Sign in failed.');
    });
  });
  $('logout').addEventListener('click', function () {
    if (anyDirty() && !confirm('You have unsaved changes. Sign out anyway?')) return;
    saved = { shop: snapshot('shop'), notices: snapshot('notices') };
    api('POST', '/admin/api/logout', {}).then(function () { location.reload(); });
  });

  // ---------------------------------------------------------------- load
  function load() {
    show($('login'), false); show($('loading'), true);
    api('GET', '/admin/api/data').then(function (r) {
      if (r.status === 401) return showLogin();
      show($('loading'), false);
      if (!r.ok) { show($('app'), true); show($('top-nav'), true); return status('err', esc(r.json.error || 'Couldn\'t load the website data.')); }
      state.shop = r.json.shop; state.notices = r.json.notices;
      saved.shop = snapshot('shop'); saved.notices = snapshot('notices');
      Object.keys(state.shop.data.products).forEach(function (k) { savedPrices[k] = Number(state.shop.data.products[k].price); });
      renderNotices(); renderProducts(); markDirty();
      show($('app'), true); show($('top-nav'), true);
    });
  }
  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // ---------------------------------------------------------------- tabs
  var tabs = ['notices', 'products'];
  tabs.forEach(function (t) {
    $('tab-btn-' + t).addEventListener('click', function () { select(t); });
  });
  function select(t) {
    if (!polling) status('', '');   // clear an old "Done" message (keep it while waiting for the site to update)
    tabs.forEach(function (x) {
      $('tab-btn-' + x).setAttribute('aria-selected', x === t ? 'true' : 'false');
      show($('tab-' + x), x === t);
    });
  }
  document.querySelector('.tabs').addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    var cur = tabs.indexOf(document.activeElement.id.replace('tab-btn-', ''));
    var next = tabs[(cur + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    select(next); $('tab-btn-' + next).focus();
  });

  // ---------------------------------------------------------------- notices
  function bind(card, obj, onChange) {
    card.querySelectorAll('[data-f]').forEach(function (el) {
      var f = el.getAttribute('data-f');
      if (el.type === 'checkbox') el.checked = !!obj[f]; else el.value = obj[f] == null ? '' : obj[f];
      el.addEventListener(el.type === 'checkbox' || el.tagName === 'SELECT' ? 'change' : 'input', function () {
        obj[f] = el.type === 'checkbox' ? el.checked : el.value;
        onChange(); markDirty();
      });
    });
  }
  function noticeState(n) {
    var t = today();
    if (!n.enabled) return ['Turned off – not showing', ''];
    if (!n.message.trim()) return ['Needs a message', ''];
    if (n.end && n.end < t) return ['Ended ' + nice(n.end) + ' – no longer showing', ''];
    if (n.start && n.start > t) return ['Scheduled – shows from ' + nice(n.start), 'is-scheduled'];
    return ['Showing now' + (n.end ? ' (until ' + nice(n.end) + ')' : ''), 'is-live'];
  }
  function renderNotices() {
    var list = state.notices.data.notices, box = $('notices');
    box.innerHTML = '';
    list.forEach(function (n, i) {
      var card = $('notice-tpl').content.firstElementChild.cloneNode(true);
      function refresh() {
        var st = noticeState(n), badge = card.querySelector('[data-k=state]');
        badge.textContent = st[0]; badge.className = 'badge ' + st[1];
        card.classList.toggle('is-off', !n.enabled);
        var p = card.querySelector('[data-k=preview]');
        p.className = 'preview ' + (n.style || 'info');
        p.textContent = n.message.trim() || 'Your message will appear here…';
        if (n.link_url) {
          p.appendChild(document.createTextNode(' '));
          var a = document.createElement('a'); a.textContent = n.link_text || 'More information'; a.href = '#'; a.tabIndex = -1;
          a.addEventListener('click', function (e) { e.preventDefault(); });
          p.appendChild(a);
        }
        card.querySelector('[data-k=count]').textContent = '(' + n.message.length + '/300)';
      }
      bind(card, n, refresh);
      card.querySelector('[data-k=remove]').addEventListener('click', function () {
        if (!confirm('Delete this notice? (It isn\'t removed from the website until you press Save.)')) return;
        list.splice(i, 1); renderNotices(); markDirty();
      });
      refresh();
      box.appendChild(card);
    });
    show($('no-notices'), !list.length);
  }
  function template(kind) {
    var t = today(), y = +t.slice(0, 4);
    if (t > y + '-12-26') y += 1;
    var base = { id: '', enabled: true, message: '', link_text: '', link_url: '', style: 'info', where: 'all', start: '', end: '' };
    if (kind === 'christmas') return Object.assign(base, {
      style: 'holiday', start: y + '-12-01', end: (y + 1) + '-01-05',
      message: 'Our office is closed for the Christmas break from 20 December and reopens on 6 January. Merry Christmas from Todd and the ELD team!' });
    if (kind === 'office') return Object.assign(base, {
      style: 'holiday', start: t, end: t,
      message: 'Our office is closed today. Please email info@equestrianlanddevelopments.com and we\'ll get back to you as soon as possible.' });
    if (kind === 'delivery') return Object.assign(base, {
      where: 'shop', start: t,
      message: 'Spread-a-bar® orders placed now will be dispatched from mid-January.' });
    return base;
  }
  document.querySelectorAll('[data-tpl]').forEach(function (b) {
    b.addEventListener('click', function () {
      state.notices.data.notices.unshift(template(b.getAttribute('data-tpl')));
      renderNotices(); markDirty();
      var first = $('notices').querySelector('textarea');
      if (first) { first.focus(); first.select(); }
    });
  });

  // ---------------------------------------------------------------- products
  function renderProducts() {
    var box = $('products'), products = state.shop.data.products;
    box.innerHTML = '';
    Object.keys(products).forEach(function (key) {
      var p = products[key], card = $('product-tpl').content.firstElementChild.cloneNode(true);
      var view = card.querySelector('[data-k=view]');
      if (p.url) view.href = (window.ELD_SITE || '') + p.url; else view.hidden = true;
      function refresh() {
        card.querySelector('[data-k=heading]').textContent = p.title || key;
        show(card.querySelector('[data-k=unavail]'), !p.available);
        show(card.querySelector('[data-k=pricewarn]'), !!(p.stripe_payment_link || '').trim() && Number(String(p.price).replace(/[$,]/g, '')) !== savedPrices[key]);
      }
      bind(card, p, refresh);
      refresh();
      box.appendChild(card);
    });
  }

  // ---------------------------------------------------------------- save + "is it live yet?"
  function save(key, btn) {
    btn.disabled = true; btn.textContent = 'Saving…';
    if (polling) { clearTimeout(polling); polling = null; }
    api('POST', '/admin/api/save', { file: key, sha: state[key].sha, data: state[key].data }).then(function (r) {
      btn.disabled = false; btn.textContent = key === 'shop' ? 'Save products' : 'Save notices';
      if (r.status === 401) return showLogin('You were signed out after 12 hours. Please sign in again, then make your change again.');
      if (!r.ok) return status('err', esc(r.json.error || 'Couldn\'t save. Please try again.'));
      state[key].sha = r.json.sha; state[key].data = r.json.data; saved[key] = snapshot(key);
      if (key === 'shop') Object.keys(state.shop.data.products).forEach(function (k) { savedPrices[k] = Number(state.shop.data.products[k].price); });
      key === 'shop' ? renderProducts() : renderNotices();
      markDirty();
      if (r.json.unchanged) return status('ok', 'Nothing to save – there were no changes.');
      status('wait', '<strong>Saved.</strong> The website is updating now – this usually takes 1–2 minutes. You can leave this page open or close it.');
      watch(key, r.json.hash, 0);
    });
  }
  function watch(key, hash, n) {
    api('GET', '/admin/api/live?file=' + key + '&hash=' + hash).then(function (r) {
      if (r.ok && r.json.live) return status('ok', '<strong>Done – your changes are live on the website.</strong> <a href="' + esc(window.ELD_SITE || '/') + (key === 'shop' ? '/shop/' : '/') + '" target="_blank" rel="noopener">View website ↗</a>');
      if (n >= 45) return status('wait', '<strong>Saved.</strong> The website is taking longer than usual to update – check it again in a few minutes.');
      polling = setTimeout(function () { watch(key, hash, n + 1); }, 8000);
    });
  }
  $('save-notices').addEventListener('click', function () { save('notices', this); });
  $('save-products').addEventListener('click', function () { save('shop', this); });

  // ---------------------------------------------------------------- start
  api('GET', '/admin/api/session').then(function (r) {
    var j = r.json || {};
    window.ELD_SITE = j.site || '';
    $('view-site').href = j.site || '/';
    if (!j.ready) {
      $('setup-msg').textContent = j.password_too_short
        ? 'The admin password set on the server is too short – it needs at least 12 characters.'
        : 'The admin isn\'t set up yet. In Render, add ADMIN_PASSWORD and GITHUB_TOKEN to the eld-admin service (see the README).';
      show($('setup-msg'), true);
    }
    if (j.signed_in) load(); else showLogin();
  });
})();
