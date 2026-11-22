/* ELD website chat assistant.
   - TRIAL mode (no endpoint configured): answers instantly from /assets/chat-kb.json (FAQ + page summaries). No AI, no cost.
   - AI mode (endpoint set in config.json → chat.endpoint): sends the conversation to the chat server, which calls Claude.
     If the server is unreachable it falls back to trial answers. */
(function () {
  var CFG = window.ELD_CHAT || {};
  var AI = !!CFG.endpoint;
  var KB = null, history = [], busy = false;
  var STORE = 'eld-chat-v1';

  // ---------- helpers
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  // Minimal, safe Markdown for AI replies: escape first, then **bold**, [links](url), line breaks, bullet lists.
  function md(text) {
    var h = esc(text);
    h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/\[([^\]]+)\]\(((?:https?:\/\/|\/|mailto:|tel:)[^)\s]+)\)/g, function (_, t, u) {
      var ext = /^https?:/.test(u) && u.indexOf(location.host) < 0;
      return '<a href="' + u + '"' + (ext ? ' target="_blank" rel="noopener"' : '') + '>' + t + '</a>';
    });
    var lines = h.split(/\n/), out = [], inList = false;
    lines.forEach(function (l) {
      var m = l.match(/^\s*[-*•]\s+(.*)/);
      if (m) { if (!inList) { out.push('<ul>'); inList = true; } out.push('<li>' + m[1] + '</li>'); return; }
      if (inList) { out.push('</ul>'); inList = false; }
      if (l.trim()) out.push('<p>' + l + '</p>');
    });
    if (inList) out.push('</ul>');
    return out.join('');
  }
  function save() { try { sessionStorage.setItem(STORE, JSON.stringify(history.slice(-30))); } catch (e) {} }
  function load() { try { return JSON.parse(sessionStorage.getItem(STORE) || '[]'); } catch (e) { return []; } }

  // ---------- trial-mode matcher
  var STOP = 'a an the and or of to in on for is are be do does can could i we you my our your me it this that with what how when where who which much many about please there have has any get will would should at by from as im id eld tell know want need like just also its arena arenas horse horses equestrian'.split(' ');
  var SYN = { cost: 'price', costs: 'price', pricing: 'price', prices: 'price', priced: 'price', expensive: 'price', cheap: 'price', dollars: 'price', budget: 'price',
    quote: 'quotation', quotes: 'quotation', estimate: 'quotation', long: 'time', duration: 'time', days: 'time', weeks: 'time', quickly: 'time', fast: 'time', build: 'construct',
    building: 'construct', built: 'construct', construction: 'construct', make: 'construct', sand: 'surface', footing: 'surface', surfaces: 'surface', synthetics: 'synthetic',
    rubber: 'synthetic', levelling: 'level', wa: 'australia', qld: 'australia', nsw: 'australia', vic: 'australia', tas: 'australia', nt: 'australia', queensland: 'australia', victoria: 'australia', perth: 'australia', melbourne: 'australia', sydney: 'australia', adelaide: 'australia', darwin: 'australia', leveling: 'level', levelled: 'level', fibre: 'synthetic', fibres: 'synthetic', plastic: 'synthetic', maintain: 'maintenance', maintaining: 'maintenance', upkeep: 'maintenance',
    groom: 'maintenance', grooming: 'maintenance', located: 'based', location: 'based', where: 'based', area: 'based', areas: 'based', service: 'based', servicing: 'based',
    phone: 'contact', call: 'contact', email: 'contact', ring: 'contact', spreadabar: 'spread', spreader: 'spread', harrows: 'harrow', leveller: 'harrow', drag: 'harrow',
    fix: 'rebuild', repair: 'rebuild', restore: 'rebuild', restoration: 'rebuild', renovate: 'rebuild', covered: 'indoor', shed: 'indoor', roof: 'indoor',
    flooding: 'flood', floods: 'flood', flooded: 'flood', ship: 'delivery', shipping: 'delivery', deliver: 'delivery', delivered: 'delivery', post: 'delivery', postage: 'delivery', freight: 'delivery', send: 'delivery', owns: 'founder', owner: 'founder', own: 'founder', boss: 'founder', started: 'founder', founded: 'founder', jumping: 'jump', showjumping: 'jump', reining: 'western', campdraft: 'western', campdrafting: 'western', last: 'lifespan', life: 'lifespan', lifetime: 'lifespan' };
  function tokens(s) {
    return String(s).toLowerCase().replace(/<[^>]+>/g, ' ').replace(/spread-a-bar/g, 'spreadabar').replace(/[^a-z0-9$ ]+/g, ' ').split(/\s+/)
      .filter(function (w) { return w && STOP.indexOf(w) < 0; })
      .map(function (w) { w = SYN[w] || w; if (w.length > 4 && /ies$/.test(w)) w = w.slice(0, -3) + 'y'; else if (w.length > 4 && /s$/.test(w) && !/ss$/.test(w)) w = w.slice(0, -1); return SYN[w] || w; });
  }
  function overlap(q, set) { var n = 0; q.forEach(function (w) { if (set[w]) n++; }); return n; }
  function toSet(arr) { var o = {}; arr.forEach(function (w) { o[w] = 1; }); return o; }
  function prep() {
    KB.faq.forEach(function (f) { f.qs = toSet(tokens(f.q)); f.as = toSet(tokens(f.t)); });
    KB.pages.forEach(function (p) { p.ts = toSet(tokens(p.title + ' ' + p.k)); p.ds = toSet(tokens(p.desc)); });
  }
  function localAnswer(q) {
    var qt = tokens(q);
    if (!KB || !qt.length) return fallback();
    if (/^(hi|hello|hey|g.?day|thanks|thank you|cheers)\b/i.test(q.trim()) && qt.length <= 2)
      return /thank|cheers/i.test(q) ? 'You\'re welcome! Anything else I can help with?' : 'Hello! What would you like to know about arenas, surfaces, maintenance or the shop?';
    var best = null, bestScore = 0;
    KB.faq.forEach(function (f) {
      var extra = qt.filter(function (w) { return !f.qs[w]; });
      var s = overlap(qt, f.qs) * 3 + Math.min(overlap(extra, f.as), 3);
      if (s > bestScore) { bestScore = s; best = f; }
    });
    var hits = best ? overlap(qt, best.qs) : 0;
    if (best && bestScore >= 3 && (hits >= 2 || qt.length <= 1 || bestScore >= 4)) return best.a;
    var page = null, ps = 0;
    KB.pages.forEach(function (p) {
      var s = overlap(qt, p.ts) * 2 + overlap(qt, p.ds);
      if (s > ps) { ps = s; page = p; }
    });
    if (page && ps >= 3) return '<p>This page should help: <a href="' + page.url + '">' + esc(page.title) + '</a></p><p>' + esc(page.desc) + '</p>';
    return fallback();
  }
  function fallback() {
    return '<p>Sorry, I don\'t have an answer for that yet. Todd can help directly:</p><p><a href="tel:' + CFG.phoneIntl + '">📞 ' + esc(CFG.phone) +
      '</a><br><a href="mailto:' + CFG.email + '">✉️ ' + esc(CFG.email) + '</a></p>';
  }

  // ---------- UI
  var launcher = el('button', 'chat-launcher', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16a2 2 0 012 2v10a2 2 0 01-2 2H9l-5 4v-4H4a2 2 0 01-2-2V6a2 2 0 012-2zm3 6.5A1.5 1.5 0 108.5 9 1.5 1.5 0 007 10.5zm5 0A1.5 1.5 0 1013.5 9 1.5 1.5 0 0012 10.5zm5 0A1.5 1.5 0 1018.5 9 1.5 1.5 0 0017 10.5z" fill="currentColor"/></svg><span>Ask ELD</span>');
  launcher.type = 'button';
  launcher.setAttribute('aria-expanded', 'false');
  launcher.setAttribute('aria-controls', 'eld-chat');
  var panel = el('section', 'chat-panel');
  panel.id = 'eld-chat';
  panel.hidden = true;
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Chat with ' + (CFG.name || 'ELD'));
  panel.innerHTML =
    '<header class="chat-head"><span class="chat-avatar" aria-hidden="true">ELD</span><div class="chat-title"><strong>' + esc(CFG.name || 'ELD Assistant') + '</strong>' +
    '<small>' + (AI ? 'AI assistant · answers from our website' : 'Trial assistant · instant answers from our website') + '</small></div>' +
    '<button class="chat-reset" type="button" title="Start a new chat" aria-label="Start a new chat">↺</button>' +
    '<button class="chat-close" type="button" aria-label="Close chat">×</button></header>' +
    '<div class="chat-log" role="log" aria-live="polite"></div>' +
    '<div class="chat-chips"></div>' +
    '<form class="chat-form"><label class="sr-only" for="eld-chat-input">Type your question</label>' +
    '<input id="eld-chat-input" type="text" maxlength="600" autocomplete="off" placeholder="Ask about arenas, surfaces, the shop…">' +
    '<button type="submit" aria-label="Send"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20.5l18-8.5L3 3.5 3 10l12 2-12 2z" fill="currentColor"/></svg></button></form>' +
    '<p class="chat-foot">For quotes, call Todd on <a href="tel:' + CFG.phoneIntl + '">' + esc(CFG.phone) + '</a></p>';
  document.body.appendChild(panel);
  document.body.appendChild(launcher);
  var log = panel.querySelector('.chat-log'), chips = panel.querySelector('.chat-chips'), form = panel.querySelector('form'), input = panel.querySelector('input');

  function bubble(role, html) {
    var b = el('div', 'chat-msg chat-msg--' + (role === 'user' ? 'user' : 'bot'), html);
    log.appendChild(b);
    log.scrollTop = log.scrollHeight;
    return b;
  }
  function renderChips() {
    chips.innerHTML = '';
    if (history.length > 1) return;
    (CFG.suggestions || []).forEach(function (s) {
      var c = el('button', 'chat-chip', esc(s));
      c.type = 'button';
      c.addEventListener('click', function () { ask(s); });
      chips.appendChild(c);
    });
  }
  function start() {
    log.innerHTML = '';
    history = load();
    if (!history.length) history = [{ role: 'assistant', html: esc(CFG.greeting || 'Hi! How can I help?'), text: CFG.greeting || '' }];
    history.forEach(function (m) { bubble(m.role, m.role === 'user' ? esc(m.text) : m.html); });
    renderChips();
  }
  function open() {
    panel.hidden = false;
    launcher.setAttribute('aria-expanded', 'true');
    document.body.classList.add('chat-open');
    if (!log.children.length) start();
    if (!KB) fetch(CFG.kb).then(function (r) { return r.json(); }).then(function (d) { KB = d; prep(); }).catch(function () {});
    setTimeout(function () { input.focus(); }, 50);
  }
  function close() {
    panel.hidden = true;
    launcher.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('chat-open');
    launcher.focus();
  }

  function ask(q) {
    q = q.trim();
    if (!q || busy) return;
    busy = true;
    input.value = '';
    history.push({ role: 'user', text: q });
    bubble('user', esc(q));
    renderChips();
    var typing = bubble('bot', '<span class="chat-typing" aria-label="Typing"><i></i><i></i><i></i></span>');
    function finish(html, text) {
      typing.innerHTML = html;
      history.push({ role: 'assistant', html: html, text: text || html.replace(/<[^>]+>/g, ' ') });
      save();
      log.scrollTop = log.scrollHeight;
      busy = false;
    }
    if (AI) {
      var msgs = history.filter(function (m, i) { return i > 0; }).slice(-12).map(function (m) { return { role: m.role, content: m.text }; });
      fetch(CFG.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: msgs, page: location.pathname }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { finish(md(d.reply || ''), d.reply); })
        .catch(function () { finish(localAnswer(q)); });
    } else {
      setTimeout(function () { finish(localAnswer(q)); }, 450);
    }
  }

  launcher.addEventListener('click', function () { panel.hidden ? open() : close(); });
  panel.querySelector('.chat-close').addEventListener('click', close);
  panel.querySelector('.chat-reset').addEventListener('click', function () { try { sessionStorage.removeItem(STORE); } catch (e) {} start(); input.focus(); });
  form.addEventListener('submit', function (e) { e.preventDefault(); ask(input.value); });
  panel.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  // Any link on the page with href="#chat" opens the assistant
  document.addEventListener('click', function (e) { var a = e.target.closest('a[href="#chat"]'); if (a) { e.preventDefault(); open(); } });
})();
