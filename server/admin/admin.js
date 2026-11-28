/* ELD website admin – edits notices, shop products and page text through the server API. */
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
  function anyDirty() { return (state.notices && snapshot('notices') !== saved.notices) || (state.shop && snapshot('shop') !== saved.shop) || pageDirty(); }
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
    saved = { shop: snapshot('shop'), notices: snapshot('notices') }; page = null;
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
  var tabs = ['notices', 'products', 'pages'];
  tabs.forEach(function (t) {
    $('tab-btn-' + t).addEventListener('click', function () { select(t); });
  });
  function select(t) {
    if (!polling) status('', '');   // clear an old "Done" message (keep it while waiting for the site to update)
    tabs.forEach(function (x) {
      $('tab-btn-' + x).setAttribute('aria-selected', x === t ? 'true' : 'false');
      show($('tab-' + x), x === t);
    });
    if (t === 'pages' && !pageList) loadPageList();
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
        p.textContent = '';
        if ((n.title || '').trim()) { var b = document.createElement('strong'); b.textContent = n.title.trim() + ' '; p.appendChild(b); }
        p.appendChild(document.createTextNode(n.message.trim() || 'Your message will appear here…'));
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
    var base = { id: '', enabled: true, title: '', message: '', link_text: '', link_url: '', style: 'info', where: 'all', start: '', end: '', popup: false };
    if (kind === 'christmas') return Object.assign(base, {
      title: 'Christmas closure', popup: true, style: 'holiday', start: y + '-12-01', end: (y + 1) + '-01-05',
      message: 'Our office is closed for the Christmas break from 20 December and reopens on 6 January. Merry Christmas from Todd and the ELD team!' });
    if (kind === 'office') return Object.assign(base, {
      title: 'Office closed', style: 'holiday', start: t, end: t,
      message: 'Our office is closed today. Please email info@equestrianlanddevelopments.com and we\'ll get back to you as soon as possible.' });
    if (kind === 'delivery') return Object.assign(base, {
      title: 'Delivery update', where: 'shop', start: t,
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
  function watch(key, hash, n, viewPath) {
    api('GET', '/admin/api/live?file=' + encodeURIComponent(key) + '&hash=' + hash).then(function (r) {
      if (r.ok && r.json.live) { polling = null; return status('ok', '<strong>Done – your changes are live on the website.</strong> <a href="' + esc(window.ELD_SITE || '') + esc(viewPath || (key === 'shop' ? '/shop/' : '/')) + '" target="_blank" rel="noopener">View ' + (viewPath ? 'page' : 'website') + ' ↗</a>'); }
      if (n >= 45) { polling = null; return status('wait', '<strong>Saved.</strong> The website is taking longer than usual to update – check it again in a few minutes.'); }
      polling = setTimeout(function () { watch(key, hash, n + 1, viewPath); }, 8000);
    });
  }
  $('save-notices').addEventListener('click', function () { save('notices', this); });
  $('save-products').addEventListener('click', function () { save('shop', this); });

  // ---------------------------------------------------------------- pages (text only)
  var pageList = null, page = null, pageSaved = '';
  function pageDirty() { return !!page && JSON.stringify({ f: page.fields, b: page.blocks }) !== pageSaved; }
  function markPageDirty() { show($('dirty-page'), pageDirty()); }

  function loadPageList() {
    var sel = $('page-select');
    sel.innerHTML = '<option value="">Loading pages…</option>';
    api('GET', '/admin/api/pages').then(function (r) {
      if (r.status === 401) return showLogin();
      if (!r.ok) { sel.innerHTML = '<option value="">Couldn\'t load the pages</option>'; return status('err', esc(r.json.error || 'Couldn\'t load the pages.')); }
      pageList = r.json.pages;
      sel.innerHTML = '<option value="">Choose a page…</option>' + pageList.map(function (p) {
        return '<option value="' + esc(p.file) + '">' + esc(p.title) + '</option>';
      }).join('');
    });
  }
  $('page-select').addEventListener('change', function () {
    var file = this.value;
    if (pageDirty() && !confirm('You have unsaved changes on this page. Discard them?')) { this.value = page.file; return; }
    if (!file) { page = null; show($('page-editor'), false); return; }
    openPage(file);
  });
  function openPage(file) {
    show($('page-editor'), false); show($('page-loading'), true);
    api('GET', '/admin/api/page?file=' + encodeURIComponent(file)).then(function (r) {
      show($('page-loading'), false);
      if (r.status === 401) return showLogin();
      if (!r.ok) return status('err', esc(r.json.error || 'Couldn\'t open that page.'));
      page = r.json;
      pageSaved = JSON.stringify({ f: page.fields, b: page.blocks });
      renderPage();
    });
  }

  // A small preview that follows the website's formatting rules
  function inline(t) {
    t = esc(t).replace(/\{\{price:([a-z0-9-]+)\}\}/g, function (m, k) {
      var p = state.shop && state.shop.data.products[k];
      return p ? '$' + Number(p.price).toLocaleString('en-AU') : m;
    });
    t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="#" title="$2">$1</a>');
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    return t.replace(/(^|[^\w\/=])_(.+?)_(?!\w)/g, '$1<em>$2</em>');
  }
  function preview(md) {
    var out = [], para = [], list = [];
    function flush() {
      if (para.length) { out.push('<p>' + para.map(inline).join(' ') + '</p>'); para = []; }
      if (list.length) { out.push('<ul>' + list.map(function (x) { return '<li>' + inline(x) + '</li>'; }).join('') + '</ul>'); list = []; }
    }
    md.split('\n').forEach(function (line) {
      var h = /^(#{2,4}) (.+)$/.exec(line);
      if (h) { flush(); out.push('<h' + h[1].length + '>' + inline(h[2]) + '</h' + h[1].length + '>'); }
      else if (/^- /.test(line)) { if (para.length) flush(); list.push(line.slice(2)); }
      else if (!line.trim()) flush();
      else { if (list.length) flush(); para.push(line.replace(/\\$/, '')); }
    });
    flush();
    return out.join('') || '<p class="muted">Nothing here yet.</p>';
  }

  function grow(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight + 4, 640) + 'px'; }
  function wrapSel(ta, before, after, placeholder) {
    var s0 = ta.selectionStart, s1 = ta.selectionEnd, v = ta.value, sel = v.slice(s0, s1) || placeholder;
    ta.value = v.slice(0, s0) + before + sel + after + v.slice(s1);
    ta.focus(); ta.setSelectionRange(s0 + before.length, s0 + before.length + sel.length);
    ta.dispatchEvent(new Event('input'));
  }
  function linePrefix(ta, prefix) {
    var v = ta.value, s0 = v.lastIndexOf('\n', ta.selectionStart - 1) + 1;
    ta.value = v.slice(0, s0) + prefix + v.slice(s0);
    ta.focus(); ta.setSelectionRange(ta.selectionStart + prefix.length, ta.selectionStart + prefix.length);
    ta.dispatchEvent(new Event('input'));
  }
  function textEditor(obj, key, label, hint) {
    var wrap = document.createElement('div');
    wrap.className = 'md-edit';
    wrap.innerHTML = '<div class="md-bar" role="toolbar" aria-label="Formatting">' +
      '<button type="button" data-a="b" title="Bold"><strong>B</strong></button>' +
      '<button type="button" data-a="h" title="Heading">Heading</button>' +
      '<button type="button" data-a="li" title="Bullet point">• List</button>' +
      '<button type="button" data-a="a" title="Link">Link</button>' +
      '<button type="button" data-a="p" class="md-toggle" aria-pressed="false">Preview</button></div>' +
      '<textarea rows="4" spellcheck="true"></textarea><div class="md-preview prose-preview" hidden></div>' +
      (hint ? '<p class="hint">' + hint + '</p>' : '');
    var ta = wrap.querySelector('textarea'), pv = wrap.querySelector('.md-preview');
    ta.setAttribute('aria-label', label);
    ta.value = obj[key] || '';
    ta.addEventListener('input', function () { obj[key] = ta.value; grow(ta); if (!pv.hidden) pv.innerHTML = preview(ta.value); markPageDirty(); });
    wrap.querySelector('.md-bar').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var a = b.getAttribute('data-a');
      if (a === 'b') wrapSel(ta, '**', '**', 'bold text');
      if (a === 'h') linePrefix(ta, '## ');
      if (a === 'li') linePrefix(ta, '- ');
      if (a === 'a') {
        var url = prompt('Link address – a page on this site (e.g. /contact-us/) or a full https:// address:', '/contact-us/');
        if (url) wrapSel(ta, '[', '](' + url.trim() + ')', 'link text');
      }
      if (a === 'p') {
        var on = pv.hidden; pv.hidden = !on; ta.hidden = on;
        b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.textContent = on ? 'Edit' : 'Preview';
        if (on) pv.innerHTML = preview(ta.value); else ta.focus();
      }
    });
    setTimeout(function () { grow(ta); }, 0);
    return wrap;
  }

  function renderPage() {
    var f = page.fields, box = $('page-blocks');
    $('page-view').href = (window.ELD_SITE || '') + page.url;
    [['title', 'pf-title'], ['lead', 'pf-lead'], ['description', 'pf-desc']].forEach(function (x) {
      var el = $(x[1]);
      el.value = f[x[0]] || '';
      el.oninput = function () { f[x[0]] = el.value; if (x[0] === 'description') $('pf-desc-count').textContent = '(' + el.value.length + ' characters – aim for 120–160)'; markPageDirty(); };
    });
    $('pf-desc-count').textContent = '(' + (f.description || '').length + ' characters – aim for 120–160)';
    box.innerHTML = '';
    var n = 0;
    page.blocks.forEach(function (b) {
      var card = document.createElement('div');
      if (b.type === 'locked') {
        card.className = 'block block--locked';
        card.innerHTML = '<span class="lock" aria-hidden="true">🔒</span><div><strong></strong><span class="muted"> – stays as it is (ask your web person to change it)</span></div>';
        card.querySelector('strong').textContent = b.label;
      } else if (b.type === 'text') {
        n++;
        if (!b.text.trim()) {
          card.className = 'block block--add';
          var add = document.createElement('button');
          add.type = 'button'; add.className = 'link-btn'; add.textContent = '+ Add text here';
          add.addEventListener('click', function () {
            card.className = 'block'; card.innerHTML = '<p class="block-label">Text</p>';
            card.appendChild(textEditor(b, 'text', 'Text'));
            card.querySelector('textarea').focus();
          });
          card.appendChild(add);
        } else {
          card.className = 'block';
          card.innerHTML = '<p class="block-label">Text</p>';
          card.appendChild(textEditor(b, 'text', 'Text', /\{\{price:/.test(b.text) ? '<code>{{price:…}}</code> shows the current shop price automatically – leave it as it is.' : ''));
        }
      } else if (b.type === 'callout') {
        card.className = 'block block--callout';
        card.innerHTML = '<p class="block-label">Highlighted box</p>';
        card.appendChild(textEditor(b, 'text', 'Highlighted box'));
      } else if (b.type === 'pricing') {
        card.className = 'block';
        renderRows(card, b);
      } else if (b.type === 'faq') {
        card.className = 'block';
        renderFaq(card, b);
      }
      box.appendChild(card);
    });
    show($('page-editor'), true);
    markPageDirty();
  }
  function renderRows(card, b) {
    card.innerHTML = '<p class="block-label">Price table</p><div class="rows"></div><button type="button" class="link-btn add-row">+ Add a row</button>';
    var rows = card.querySelector('.rows');
    b.rows.forEach(function (r, i) {
      var row = document.createElement('div');
      row.className = 'row';
      row.innerHTML = '<input aria-label="Item" placeholder="e.g. 20m x 60m arena"><input aria-label="Price" placeholder="e.g. $70,000 + GST"><button type="button" class="link-btn danger" aria-label="Remove row">Remove</button>';
      var ins = row.querySelectorAll('input');
      ins[0].value = r.item; ins[1].value = r.price;
      ins[0].oninput = function () { r.item = ins[0].value; markPageDirty(); };
      ins[1].oninput = function () { r.price = ins[1].value; markPageDirty(); };
      row.querySelector('button').onclick = function () { if (b.rows.length > 1) { b.rows.splice(i, 1); renderRows(card, b); markPageDirty(); } };
      rows.appendChild(row);
    });
    card.querySelector('.add-row').onclick = function () { b.rows.push({ item: '', price: '' }); renderRows(card, b); markPageDirty(); };
  }
  function renderFaq(card, b) {
    card.innerHTML = '<p class="block-label">Questions &amp; answers</p><div class="faq-items"></div><button type="button" class="link-btn add-q">+ Add a question</button>';
    var list = card.querySelector('.faq-items');
    b.items.forEach(function (it, i) {
      var item = document.createElement('div');
      item.className = 'faq-item';
      item.innerHTML = '<label>Question ' + (i + 1) + '<input maxlength="300"></label><p class="block-label">Answer</p>';
      var q = item.querySelector('input');
      q.value = it.q;
      q.oninput = function () { it.q = q.value; markPageDirty(); };
      item.appendChild(textEditor(it, 'a', 'Answer ' + (i + 1), /\{\{price:/.test(it.a) ? '<code>{{price:…}}</code> shows the current shop price automatically – leave it as it is.' : ''));
      var del = document.createElement('button');
      del.type = 'button'; del.className = 'link-btn danger'; del.textContent = 'Delete this question';
      del.onclick = function () { if (b.items.length > 1 && confirm('Delete this question?')) { b.items.splice(i, 1); renderFaq(card, b); markPageDirty(); } };
      item.appendChild(del);
      list.appendChild(item);
    });
    card.querySelector('.add-q').onclick = function () { b.items.push({ q: '', a: '' }); renderFaq(card, b); markPageDirty(); list.lastChild && card.querySelector('.faq-item:last-child input').focus(); };
  }
  $('save-page').addEventListener('click', function () {
    if (!page) return;
    var btn = this;
    btn.disabled = true; btn.textContent = 'Saving…';
    if (polling) { clearTimeout(polling); polling = null; }
    api('POST', '/admin/api/save-page', { file: page.file, sha: page.sha, fields: page.fields, blocks: page.blocks }).then(function (r) {
      btn.disabled = false; btn.textContent = 'Save page';
      if (r.status === 401) return showLogin('You were signed out after 12 hours. Please sign in again, then make your change again.');
      if (!r.ok) return status('err', esc(r.json.error || 'Couldn\'t save. Please try again.'));
      page.sha = r.json.sha;
      pageSaved = JSON.stringify({ f: page.fields, b: page.blocks });
      markPageDirty();
      if (r.json.unchanged) return status('ok', 'Nothing to save – there were no changes.');
      if (pageList) pageList.forEach(function (p) { if (p.file === page.file) p.title = page.fields.title; });
      status('wait', '<strong>Saved.</strong> The website is updating now – this usually takes 1–2 minutes. You can leave this page open or close it.');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      watch('page:' + page.file, r.json.hash, 0, page.url);
    });
  });

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
