#!/usr/bin/env python3
"""Equestrian Land Developments – static website builder.

Turns the Markdown files in content/ into a complete website in public/.
No installs needed – just run:

    python3 build.py

Then upload the contents of public/ to your web host.
See README.md for how to edit pages, add news and set up Stripe checkout.
"""
import datetime
import glob
import hashlib
import html
import json
import os
import re
import shutil
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'public')
C = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
NAV = json.load(open(os.path.join(ROOT, 'content', 'navigation.json'), encoding='utf-8'))
IMG = json.load(open(os.path.join(ROOT, 'assets', 'img', 'manifest.json'), encoding='utf-8'))
# Edited through the website admin (server/): product prices/links and site notices
SHOP_FILE = os.path.join(ROOT, 'content', 'shop.json')
NOTICES_FILE = os.path.join(ROOT, 'content', 'notices.json')
SHOP = json.load(open(SHOP_FILE, encoding='utf-8'))['products']
NOTICES = json.load(open(NOTICES_FILE, encoding='utf-8')).get('notices', [])
SITE = C['site_url'].rstrip('/')
SITE_LIVE = C.get('live_url', 'https://eld-website.onrender.com').rstrip('/')   # where the site is actually served (until the domain moves)
YEAR = datetime.date.today().year
TODAY = datetime.date.today().isoformat()
TODAY_QLD = (datetime.datetime.utcnow() + datetime.timedelta(hours=10)).date().isoformat()   # Queensland has no daylight saving
WARN = []
ORG_ID = SITE + '/#organization'
WEBSITE_ID = SITE + '/#website'
TODD_ID = SITE + '/#todd-cunningham'


def esc(s):
    return html.escape(str(s), quote=True)


def slugify(s):
    s = re.sub(r'<[^>]+>', '', s).lower().replace('&amp;', '').replace('&', '')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def strip_tags(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def absurl(u):
    return SITE + u if u.startswith('/') else u


def money(n):
    return '${:,.2f}'.format(float(n))


def price_text(n):
    """$1,150 for whole dollars, $1,150.50 otherwise (used in sentences)."""
    n = float(n)
    return '${:,.0f}'.format(n) if n == int(n) else '${:,.2f}'.format(n)


def fill(text):
    """Replace {{price:product-key}} placeholders so prices only live in content/shop.json."""
    def sub(m):
        if m.group(1) not in SHOP:
            WARN.append('unknown product in placeholder: ' + m.group(0))
            return m.group(0)
        return price_text(SHOP[m.group(1)]['price'])
    return re.sub(r'\{\{price:([a-z0-9-]+)\}\}', sub, text)


# ---------------------------------------------------------------- loading
def load(path):
    text = fill(open(path, encoding='utf-8').read())
    meta = {}
    body = text
    if text.startswith('---'):
        _, fm, body = text.split('---', 2)
        for line in fm.strip().splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
    meta['body'] = body.strip('\n')
    meta['src'] = os.path.relpath(path, ROOT)
    return meta


PAGES = [load(p) for p in sorted(glob.glob(os.path.join(ROOT, 'content', 'pages', '*.md')))]
POSTS = sorted([load(p) for p in glob.glob(os.path.join(ROOT, 'content', 'news', '*.md'))],
               key=lambda p: (p['date'], p['url']), reverse=True)
PRODUCTS = sorted([load(p) for p in glob.glob(os.path.join(ROOT, 'content', 'products', '*.md'))],
                  key=lambda p: int(p.get('order', 0)))
for p in POSTS:
    p.setdefault('parent', '/news/')
    p['layout'] = 'post'
for p in PRODUCTS:
    p['layout'] = 'product'
    shop = SHOP.get(p['key'], {})
    p['title'] = shop.get('title') or p.get('title', p['key'])
    p['price'] = shop.get('price', 0)
    p['available'] = shop.get('available', True)
    p['note'] = (shop.get('note') or '').strip()
    p['stripe'] = (shop.get('stripe_payment_link') or '').strip() if p['available'] else ''
    p['seo_title'] = p.get('seo_title', '').replace('{{title}}', p['title'])
BY_URL = {p['url']: p for p in PAGES + POSTS + PRODUCTS}
BY_URL.setdefault('/news/', {'url': '/news/', 'title': 'Latest News & Updates', 'parent': '/'})
BY_URL.setdefault('/', {'url': '/', 'title': 'Home'})


def label(url):
    p = BY_URL.get(url, {})
    return p.get('nav_title') or p.get('title') or url


# ---------------------------------------------------------------- images
def img(name, alt, sizes='100vw', cls='', eager=False, extra=''):
    m = IMG.get(name)
    if not m:
        WARN.append('missing image: ' + name)
        return ''
    src = '/assets/img/' + m['file']
    srcset = ''
    if 'thumb' in m:
        srcset = ' srcset="/assets/img/{} {}w, {} {}w" sizes="{}"'.format(m['thumb'], m['tw'], src, m['w'], sizes)
    c = ' class="{}"'.format(cls) if cls else ''
    load_attr = 'eager" fetchpriority="high' if eager else 'lazy'
    return '<img src="{}"{} width="{}" height="{}" alt="{}" loading="{}" decoding="async"{}{}>'.format(
        src, srcset, m['w'], m['h'], esc(alt), load_attr, c, extra)


def img_url(name):
    m = IMG.get(name)
    return absurl('/assets/img/' + m['file']) if m else absurl('/assets/img/hero-arena-corinda.jpg')


# ---------------------------------------------------------------- markdown
def inline(s):
    s = esc(s)

    def link(m):
        text, url = m.group(1), html.unescape(m.group(2))
        ext = url.startswith('http')
        attrs = ' target="_blank" rel="noopener"' if ext else ''
        return '<a href="{}"{}>{}</a>'.format(esc(url), attrs, text)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w/=])_(.+?)_(?![\w])', r'<em>\1</em>', s)
    return s


def split_blocks(body):
    """Yield ('md', [lines]) and ('dir', name, args, [lines]) chunks."""
    lines = body.split('\n')
    i, buf = 0, []
    while i < len(lines):
        line = lines[i]
        if line.startswith('::: '):
            if buf:
                yield ('md', buf)
                buf = []
            head = line[4:].strip()
            name, _, args = head.partition(' ')
            inner = []
            i += 1
            while i < len(lines) and lines[i].strip() != ':::':
                inner.append(lines[i])
                i += 1
            yield ('dir', name, args.strip(), inner)
        else:
            buf.append(line)
        i += 1
    if buf:
        yield ('md', buf)


def md_lines(lines):
    out, para, lst, quote = [], [], [], []

    def flush():
        if para:
            parts = []
            for j, l in enumerate(para):
                if l.endswith('\\'):
                    parts.append(inline(l[:-1].rstrip()) + '<br>')
                else:
                    parts.append(inline(l) + ('' if j == len(para) - 1 else ' '))
            out.append('<p>' + ''.join(parts) + '</p>')
            para.clear()
        if lst:
            out.append('<ul>' + ''.join('<li>' + inline(x) + '</li>' for x in lst) + '</ul>')
            lst.clear()
        if quote:
            out.append('<blockquote><p>' + inline(' '.join(quote)) + '</p></blockquote>')
            quote.clear()
    for raw in lines:
        line = raw.rstrip()
        m = re.match(r'^(#{2,4}) (.+)$', line)
        if m:
            flush()
            lvl = len(m.group(1))
            txt = inline(m.group(2))
            out.append('<h{0} id="{1}">{2}</h{0}>'.format(lvl, slugify(txt), txt))
        elif line.startswith('- '):
            if para or quote:
                flush()
            lst.append(line[2:])
        elif line.startswith('> '):
            if para or lst:
                flush()
            quote.append(line[2:])
        elif not line.strip():
            flush()
        else:
            if lst or quote:
                flush()
            para.append(line)
    flush()
    return '\n'.join(out)


def md(body, ctx):
    out = []
    for chunk in split_blocks(body):
        if chunk[0] == 'md':
            out.append(md_lines(chunk[1]))
        else:
            out.append(directive(chunk[1], chunk[2], chunk[3], ctx))
    return '\n'.join(out)


def rows(lines):
    return [[c.strip() for c in l.split('|')] for l in lines if l.strip()]


# ---------------------------------------------------------------- directives
def directive(name, args, lines, ctx):
    if name == 'include':
        return md(load(os.path.join(ROOT, 'content', 'partials', args + '.md'))['body'], ctx)
    if name == 'gallery':
        items = []
        for r in rows(lines):
            n, cap = r[0], (r[1] if len(r) > 1 else '')
            m = IMG.get(n, {})
            items.append('<figure><a href="/assets/img/{}" class="lb" data-caption="{}">{}</a>{}</figure>'.format(
                m.get('file', ''), esc(cap), img(n, cap or ctx['title'], '(min-width: 1100px) 360px, (min-width: 640px) 45vw, 100vw'),
                '<figcaption>{}</figcaption>'.format(esc(cap)) if cap else ''))
        return '<div class="gallery">{}</div>'.format(''.join(items))
    if name == 'figure':
        n, _, cap = args.partition('|')
        n, cap = n.strip(), cap.strip()
        m = IMG.get(n, {})
        small = ' figure--small' if m.get('w', 1000) < 700 else ''
        return '<figure class="figure{}"><a href="/assets/img/{}" class="lb" data-caption="{}">{}</a><figcaption>{}</figcaption></figure>'.format(
            small, m.get('file', ''), esc(cap), img(n, cap, '(min-width: 1100px) 760px, 100vw'), esc(cap))
    if name == 'downloads':
        items = []
        for r in rows(lines):
            path = os.path.join(ROOT, r[1].lstrip('/'))
            size = os.path.getsize(path) / 1048576 if os.path.exists(path) else 0
            if not size:
                WARN.append('missing download: ' + r[1])
            items.append('<a class="download" href="{}" target="_blank" rel="noopener"><span class="download-icon" aria-hidden="true">PDF</span>'
                         '<span class="download-text"><strong>{}</strong><small>PDF · {:.1f} MB · opens in a new tab</small></span>'
                         '<span class="download-arrow" aria-hidden="true">↓</span></a>'.format(esc(r[1]), esc(r[0]), size))
        return '<div class="downloads">{}</div>'.format(''.join(items))
    if name == 'pricing':
        return '<div class="pricing">{}</div>'.format(''.join(
            '<div class="price-row"><span>{}</span><strong>{}</strong></div>'.format(esc(a), esc(b)) for a, b in rows(lines)))
    if name == 'features':
        cards = []
        for r in rows(lines):
            title, text = r[0], r[1] if len(r) > 1 else ''
            inner = '<h3>{}</h3><p>{}</p>'.format(esc(title), inline(text))
            if len(r) > 2 and r[2]:
                cards.append('<a class="feature feature--link" href="{}">{}<span class="more" aria-hidden="true">→</span></a>'.format(esc(r[2]), inner))
            else:
                cards.append('<div class="feature">{}</div>'.format(inner))
        return '<div class="features">{}</div>'.format(''.join(cards))
    if name == 'stats':
        return '<dl class="stats">{}</dl>'.format(''.join(
            '<div><dt>{}</dt><dd>{}</dd></div>'.format(esc(a), esc(b)) for a, b in rows(lines)))
    if name == 'callout':
        return '<aside class="callout">{}</aside>'.format(md('\n'.join(lines), ctx))
    if name == 'split':
        n, _, cap = args.partition('|')
        return '<div class="split"><div class="split-media">{}</div><div class="split-body">{}</div></div>'.format(
            img(n.strip(), cap.strip(), '(min-width: 900px) 40vw, 100vw'), md('\n'.join(lines), ctx))
    if name == 'logos':
        return '<ul class="logos" role="list">{}</ul>'.format(''.join(
            '<li title="{0}">{1}<span class="sr-only">{0}</span></li>'.format(esc(b), img(a, b, '200px')) for a, b in rows(lines)))
    if name == 'logos-history':
        return '<div class="logo-history">{}</div>'.format(''.join(
            '<figure>{}<figcaption>{}</figcaption></figure>'.format(img(a, b, '240px'), esc(b)) for a, b in rows(lines)))
    if name == 'children':
        return child_cards(ctx['url'])
    if name == 'cta':
        return cta_band(args)
    if name == 'product-teaser':
        return product_cards(compact=True)
    if name == 'video':
        vid, poster, cap = [x.strip() for x in args.split('|')]
        ctx.setdefault('videos', []).append((vid, poster, cap))
        return ('<figure class="video"><video controls preload="none" playsinline poster="/assets/img/{}">'
                '<source src="/assets/video/{}.mp4" type="video/mp4">Your browser does not support video.</video>'
                '<figcaption>{}</figcaption></figure>').format(IMG[poster]['file'], vid, esc(cap))
    if name == 'spec-diagram':
        return SPEC_SVG
    if name == 'verge-diagram':
        return VERGE_SVG
    if name == 'faq':
        items = parse_faq(lines)
        ctx['faq'] = items
        return '<div class="faq">{}</div>'.format(''.join(
            '<details{}><summary><h3>{}</h3><span class="faq-icon" aria-hidden="true"></span></summary><div class="faq-a">{}</div></details>'.format(
                ' open' if i == 0 else '', esc(q), a_html) for i, (q, a_html, _) in enumerate(items)))
    WARN.append('unknown directive: ' + name)
    return ''


def parse_faq(lines):
    items, block = [], []
    for l in lines + ['']:
        if l.strip():
            block.append(l)
        elif block:
            q, a = block[0], '\n'.join(block[1:])
            a_html = md_lines(a.split('\n'))
            items.append((q, a_html, strip_tags(a_html)))
            block = []
    return items


def md_plain(body, ctx):
    """Markdown version of a page for AI tools (llms-full.txt and /index.md)."""
    out = []
    for chunk in split_blocks(body):
        if chunk[0] == 'md':
            out.append('\n'.join(chunk[1]))
            continue
        name, args, lines = chunk[1], chunk[2], chunk[3]
        r = rows(lines)
        if name == 'include':
            out.append(md_plain(load(os.path.join(ROOT, 'content', 'partials', args + '.md'))['body'], ctx))
        elif name == 'gallery':
            out.append('Photos:\n' + '\n'.join('- ![{}]({})'.format(x[1] if len(x) > 1 else '', img_url(x[0])) for x in r))
        elif name == 'figure':
            n, _, cap = args.partition('|')
            out.append('![{}]({})'.format(cap.strip(), img_url(n.strip())))
        elif name == 'downloads':
            out.append('Downloads:\n' + '\n'.join('- [{}]({}) (PDF)'.format(x[0], absurl(x[1])) for x in r))
        elif name == 'pricing':
            out.append('\n'.join('- **{}:** {}'.format(a, b) for a, b in r))
        elif name == 'features':
            out.append('\n'.join('- **{}** – {}'.format(x[0], x[1] if len(x) > 1 else '') for x in r))
        elif name == 'stats':
            out.append('\n'.join('- **{}** – {}'.format(a, b) for a, b in r))
        elif name in ('callout', 'split'):
            out.append(md_plain('\n'.join(lines), ctx))
        elif name in ('logos', 'logos-history'):
            out.append('\n'.join('- ' + b for a, b in r))
        elif name == 'children':
            out.append('\n'.join('- [{}]({}): {}'.format(label(u), absurl(u), BY_URL.get(u, {}).get('description', ''))
                                 for u in [c['url'] for c in nav_children(ctx['url'])]))
        elif name == 'cta':
            out.append('**Enquiries:** {} on {} or {}.'.format(C['contact_name'], C['phone_display'], C['email']))
        elif name == 'product-teaser':
            out.append('\n'.join('- [{}]({}) – {} AUD'.format(p['title'], absurl(p['url']), money(p['price'])) for p in PRODUCTS))
        elif name == 'video':
            vid, poster, cap = [x.strip() for x in args.split('|')]
            out.append('Video: [{}]({})'.format(cap, absurl('/assets/video/{}.mp4'.format(vid))))
        elif name == 'spec-diagram':
            out.append(SPEC_TEXT)
        elif name == 'verge-diagram':
            out.append('Diagram: cross-section of the ELD grass verge system – the lawn verge sits 25mm above the finished arena surface level, over the sand layer and existing sub base.')
        elif name == 'faq':
            out.append('\n\n'.join('### {}\n\n{}'.format(q, a) for q, _, a in parse_faq(lines)))
    text = '\n\n'.join(x.strip('\n') for x in out if x.strip())
    text = re.sub(r'\]\((/[^)]*)\)', lambda m: '](' + absurl(m.group(1)) + ')', text)
    return re.sub(r'\n{3,}', '\n\n', text)


# ---------------------------------------------------------------- diagrams
SPEC_TEXT = ('The ELD Full Spec. Arena (cross-section, top to bottom): ELD manufactured sand surface; '
             'two engineered base layers (a base layer and a blinding layer); earthworks – site levelled and prepared; '
             'sleeper surrounds around the perimeter. Generally built in 3–4 days and ready to ride immediately.')

SPEC_SVG = '''<figure class="diagram" aria-labelledby="spec-cap">
<svg viewBox="0 0 800 380" role="img" aria-label="Cross-section of an ELD Full Spec. Arena showing the sleeper surround, ELD sand surface, two engineered base layers and earthworks">
<defs><pattern id="dots" width="9" height="9" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.2" fill="#8a7a5c" opacity=".55"/><circle cx="6.5" cy="6.5" r="1.2" fill="#8a7a5c" opacity=".4"/></pattern>
<pattern id="rocks" width="24" height="16" patternUnits="userSpaceOnUse"><ellipse cx="6" cy="5" rx="5.5" ry="3.2" fill="#7d8178"/><ellipse cx="18" cy="11" rx="4.5" ry="2.8" fill="#90948a"/></pattern></defs>
<path d="M0 270 Q200 262 400 268 T800 266 L800 380 L0 380Z" fill="#8b6a46"/>
<rect x="70" y="214" width="660" height="54" fill="#a7aaa0"/><rect x="70" y="214" width="660" height="54" fill="url(#rocks)" opacity=".55"/>
<rect x="70" y="184" width="660" height="30" fill="#cfcbbb"/>
<rect x="70" y="140" width="660" height="44" fill="#e0c38f"/><rect x="70" y="140" width="660" height="44" fill="url(#dots)"/>
<rect x="52" y="124" width="18" height="144" rx="2" fill="#4b3a2a"/><rect x="730" y="124" width="18" height="144" rx="2" fill="#4b3a2a"/>
<path d="M0 124 L52 124 L52 270 L0 270Z" fill="#5f8f3e"/><path d="M748 124 L800 124 L800 266 L748 266Z" fill="#5f8f3e"/>
<g font-family="Inter, system-ui, sans-serif" font-size="20" fill="#1b1f1a">
<line x1="61" y1="130" x2="61" y2="72" stroke="#1b1f1a" stroke-width="1.5"/><circle cx="61" cy="130" r="4" fill="#1b1f1a"/>
<text x="24" y="38" font-weight="700">Sleeper</text><text x="24" y="62" font-weight="700">surround</text>
<line x1="300" y1="160" x2="300" y2="72" stroke="#1b1f1a" stroke-width="1.5"/><circle cx="300" cy="160" r="4" fill="#1b1f1a"/>
<text x="290" y="38" font-weight="700">ELD surface</text><text x="290" y="62" fill="#5d665a">natural manufactured sand</text>
<line x1="610" y1="199" x2="610" y2="72" stroke="#1b1f1a" stroke-width="1.5"/><circle cx="610" cy="199" r="4" fill="#1b1f1a"/>
<text x="600" y="38" font-weight="700">Blinding layer</text><text x="600" y="62" fill="#5d665a">base layer 2</text>
<text x="400" y="248" font-weight="700" fill="#fff" text-anchor="middle">Engineered base layer</text>
<text x="400" y="330" font-weight="700" fill="#fff" text-anchor="middle">Earthworks included</text>
</g></svg>
<figcaption id="spec-cap"><strong>The ELD Full Spec. Arena.</strong> Two engineered base layers, the ELD surface and sleeper surrounds, with all earthworks included. Generally built in 3–4 days and ready to ride immediately. <em>Illustrative – not to scale.</em></figcaption></figure>'''

VERGE_SVG = '''<figure class="diagram" aria-labelledby="verge-cap">
<svg viewBox="0 0 760 260" role="img" aria-label="Cross-section of the ELD grass verge system: the lawn verge sits 25mm above the finished arena surface level, holding the sand layer in place over the existing sub base">
<rect x="0" y="170" width="760" height="90" fill="#c9b98f"/>
<path d="M0 120 L470 120 L470 170 L0 170Z" fill="#e0c38f"/>
<path d="M470 104 L760 104 L760 170 L470 170Z" fill="#7a5a3a"/>
<path d="M470 104 L760 104 L760 112 L470 112Z" fill="#5f8f3e"/>
<g stroke="#4f7d32" stroke-width="2">''' + ''.join('<line x1="{0}" y1="104" x2="{1}" y2="92"/>'.format(x, x + (3 if x % 2 else -3)) for x in range(476, 760, 9)) + '''</g>
<line x1="0" y1="120" x2="470" y2="120" stroke="#1b1f1a" stroke-dasharray="5 4"/>
<g font-family="Inter, system-ui, sans-serif" font-size="19" fill="#1b1f1a">
<text x="20" y="110" font-weight="600">Finished surface level</text>
<text x="20" y="150">Sand layer (arena surface)</text>
<text x="500" y="80" font-weight="600">Lawn verge</text>
<text x="20" y="220" font-weight="600">Existing sub base</text>
<line x1="450" y1="104" x2="450" y2="120" stroke="#b8643a" stroke-width="2"/><line x1="444" y1="104" x2="456" y2="104" stroke="#b8643a" stroke-width="2"/><line x1="444" y1="120" x2="456" y2="120" stroke="#b8643a" stroke-width="2"/>
<text x="384" y="96" font-weight="700" fill="#b8643a">25mm</text>
</g></svg>
<figcaption id="verge-cap">The 25mm-high grass verge stops the arena surface dispersing beyond the arena perimeter and maximises natural drainage. <em>Illustrative – redrawn from ELD's original cross-section plan.</em></figcaption></figure>'''


# ---------------------------------------------------------------- nav helpers
def walk(nodes, parent=None):
    for n in nodes:
        yield n, parent
        yield from walk(n.get('children', []), n)


def nav_node(url):
    found = [n for n, _ in walk(NAV) if n['url'] == url]
    with_kids = [n for n in found if n.get('children')]
    return (with_kids or found or [None])[0]


def nav_children(url):
    n = nav_node(url)
    return [c for c in (n or {}).get('children', []) if c['url'] != url]


def page_card(url, cls='card'):
    p = BY_URL.get(url, {})
    hero = p.get('hero') or p.get('image') or 'hero-arena-corinda'
    desc = p.get('lead') or p.get('description', '')
    return ('<a class="{}" href="{}"><div class="card-media">{}</div><div class="card-body"><h3>{}</h3><p>{}</p>'
            '<span class="card-more">Explore <span aria-hidden="true">→</span></span></div></a>').format(
        cls, url, img(hero, '', '(min-width: 1000px) 360px, (min-width: 640px) 45vw, 100vw'), esc(label(url)), esc(desc))


def child_cards(url):
    return '<div class="cards">{}</div>'.format(''.join(page_card(c['url']) for c in nav_children(url)))


def contains(node, url):
    return node['url'] == url or any(contains(c, url) for c in node.get('children', []))


def render_nav(current):
    items = []
    for i, n in enumerate(NAV):
        active = ' is-active' if contains(n, current) and current != '/' else ''
        if not n.get('children'):
            cur = ' aria-current="page"' if n['url'] == current else ''
            items.append('<li class="nav-item{}"><a class="nav-link" href="{}"{}>{}</a></li>'.format(active, n['url'], cur, esc(n['title'])))
            continue
        sub = []
        if all(c['url'] != n['url'] for c in n['children']):
            sub.append('<li class="sub-overview"><a href="{}">{} overview <span aria-hidden="true">→</span></a></li>'.format(n['url'], esc(n['title'])))
        for c in n['children']:
            cur = ' aria-current="page"' if c['url'] == current else ''
            if c.get('children'):
                kids = ''.join('<li><a href="{}"{}>{}</a></li>'.format(k['url'], ' aria-current="page"' if k['url'] == current else '', esc(k['title'])) for k in c['children'])
                sub.append('<li class="sub-group"><a href="{}"{}>{}</a><ul>{}</ul></li>'.format(c['url'], cur, esc(c['title']), kids))
            else:
                sub.append('<li><a href="{}"{}>{}</a></li>'.format(c['url'], cur, esc(c['title'])))
        wide = ' sub--wide' if any(c.get('children') for c in n['children']) else ''
        items.append(('<li class="nav-item has-sub{0}"><button class="nav-link" type="button" aria-expanded="false" aria-controls="sub-{1}">{2}'
                      '<svg class="chev" viewBox="0 0 12 8" aria-hidden="true"><path d="M1 1.5l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></button>'
                      '<div class="sub{3}" id="sub-{1}"><ul>{4}</ul></div></li>').format(active, i, esc(n['title']), wide, ''.join(sub)))
    return '<ul class="nav-list">{}</ul>'.format(''.join(items))


def crumbs(page):
    chain, url, seen = [], page.get('parent'), set()
    while url and url not in seen:
        seen.add(url)
        chain.insert(0, url)
        url = BY_URL.get(url, {}).get('parent') if url != '/' else None
    if chain and chain[0] != '/':
        chain.insert(0, '/')
    trail = [(u, label(u)) for u in chain] + [(page['url'], page.get('nav_title') or page['title'])]
    html_ = '<nav class="crumbs" aria-label="Breadcrumb"><ol>{}</ol></nav>'.format(''.join(
        ('<li><a href="{}">{}</a></li>' if i < len(trail) - 1 else '<li aria-current="page">{1}</li>').format(u, esc(t))
        for i, (u, t) in enumerate(trail)))
    ld = {'@type': 'BreadcrumbList', '@id': absurl(page['url']) + '#breadcrumb', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': t, 'item': absurl(u)} for i, (u, t) in enumerate(trail)]}
    return html_, ld


# ---------------------------------------------------------------- shared blocks
ICON = {
    'phone': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 006.6 6.6l2.2-2.2a1 1 0 011-.25 11.4 11.4 0 003.6.57 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.45.57 3.57a1 1 0 01-.25 1z" fill="currentColor"/></svg>',
    'mail': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h18a1 1 0 011 1v12a1 1 0 01-1 1H3a1 1 0 01-1-1V6a1 1 0 011-1zm9 7.2L4 7.3V17h16V7.3z" fill="currentColor"/></svg>',
    'pin': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a7 7 0 017 7c0 5-7 13-7 13S5 14 5 9a7 7 0 017-7zm0 4.5A2.5 2.5 0 1012 11.5 2.5 2.5 0 0012 6.5z" fill="currentColor"/></svg>',
    'facebook': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 21v-7.5H16l.4-3h-2.9V8.6c0-.9.25-1.5 1.5-1.5h1.6V4.4A21 21 0 0014.3 4C12 4 10.5 5.4 10.5 7.9v2.6H8v3h2.5V21z" fill="currentColor"/></svg>',
    'instagram': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7.3A4.7 4.7 0 1016.7 12 4.7 4.7 0 0012 7.3zm0 7.7a3 3 0 113-3 3 3 0 01-3 3zm6-7.9a1.1 1.1 0 11-1.1-1.1A1.1 1.1 0 0118 7.1zM21 7.4a5.4 5.4 0 00-1.5-3.9A5.4 5.4 0 0015.6 2C14 2 10 2 8.4 2a5.4 5.4 0 00-3.9 1.5A5.4 5.4 0 003 7.4C2.9 9 2.9 15 3 16.6a5.4 5.4 0 001.5 3.9A5.4 5.4 0 008.4 22c1.6.1 5.6.1 7.2 0a5.4 5.4 0 003.9-1.5 5.4 5.4 0 001.5-3.9c.1-1.6.1-7.6 0-9.2zM19 18.4a3 3 0 01-1.7 1.7c-1.2.5-4 .4-5.3.4s-4.1.1-5.3-.4A3 3 0 015 18.4c-.5-1.2-.4-4-.4-5.4s-.1-4.1.4-5.3A3 3 0 016.7 6c1.2-.5 4-.4 5.3-.4s4.1-.1 5.3.4A3 3 0 0119 7.7c.5 1.2.4 4 .4 5.3s.1 4.2-.4 5.4z" fill="currentColor"/></svg>',
    'check': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 16.2l-3.5-3.5L4 14.2l5 5 11-11-1.5-1.4z" fill="currentColor"/></svg>',
}


def cta_band(kind=''):
    if kind == 'maintenance':
        return ('<section class="cta-band"><div><p class="eyebrow">Arena maintenance visits</p><h2>Book a professional maintenance visit</h2>'
                '<p>Every 3, 6 or 12 months depending on use. Lead times are a minimum 4–6 weeks. Currently servicing SE QLD and Northern NSW.</p></div>'
                '<div class="cta-actions"><a class="btn btn-sand" href="mailto:{0}?subject=Arena%20Maintenance%20Visit%20booking">Email to book</a>'
                '<a class="btn btn-ghost-light" href="tel:{1}">Call {2}</a></div></section>').format(C['email'], C['phone_intl'], C['phone_display'])
    return ('<section class="cta-band"><div><p class="eyebrow">Start your project</p><h2>Talk to Todd about your arena</h2>'
            '<p>Onsite consultations, quotations and pre-purchase inspections across South East Queensland and surrounding areas.</p></div>'
            '<div class="cta-actions"><a class="btn btn-sand" href="/arena-construct/eld-construction-quotation-process/">Book a consultation</a>'
            '<a class="btn btn-ghost-light" href="tel:{0}">{1} {2}</a></div></section>').format(C['phone_intl'], ICON['phone'], C['phone_display'])


def order_mailto(title):
    body = ("Hi Todd,\n\nI'd like to order: {}\nQuantity: 1\n\nName:\nPhone:\nDelivery address:\n\nThanks").format(title.replace('®', ''))
    return 'mailto:{}?subject={}&body={}'.format(C['email'], urllib.parse.quote('Order: ' + title.replace('®', '')), urllib.parse.quote(body))


STRIPE_ON = any(p['stripe'] for p in PRODUCTS)
PAY_BADGES = ('<ul class="pay-badges" role="list" aria-label="Payment options"><li class="pay-stripe">'
              '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 9V7a5 5 0 00-10 0v2H5v12h14V9zm-8 0V7a3 3 0 016 0v2z" fill="currentColor"/></svg>'
              'Secure checkout by Stripe</li><li>Apple Pay</li><li>Google Pay</li><li>Visa</li><li>Mastercard</li><li>Amex</li></ul>')


def order_ways():
    """Shop page: how to order. Email first, then Todd's phone (plus online checkout once Stripe links are set)."""
    ways = []
    if STRIPE_ON:
        ways.append(('Buy online', 'Choose your Spread-a-bar® above and tap <strong>Buy now</strong>. Pay by card, Apple Pay or Google Pay through secure Stripe checkout.', ''))
    ways.append(('Email your order', 'Email <a href="{0}">{1}</a> with the model, your name, phone and delivery address.'.format(
        esc(order_mailto('ELD Arena Spread-a-bar')), C['email']), '<a class="btn btn-small btn-primary" href="{}">Email to order</a>'.format(esc(order_mailto('ELD Arena Spread-a-bar')))))
    ways.append(('Call {}'.format(C['contact_name'].split()[0]), 'Prefer to talk it through? Call {} on <a href="tel:{}">{}</a>.'.format(
        esc(C['contact_name']), C['phone_intl'], C['phone_display']), '<a class="btn btn-small btn-outline" href="tel:{}">Call {}</a>'.format(C['phone_intl'], C['phone_display'])))
    cards = ''.join('<li><span class="ow-num">{}</span><div><h3>{}</h3><p>{}</p>{}</div></li>'.format(i + 1, esc(t), d, b) for i, (t, d, b) in enumerate(ways))
    return '<section class="order-ways" aria-labelledby="order-h"><h2 id="order-h">How to order</h2><ol role="list">{}</ol>{}</section>'.format(
        cards, PAY_BADGES if STRIPE_ON else '')


def product_cards(compact=False):
    cards = []
    for p in PRODUCTS:
        cards.append(('<a class="product-card" href="{url}"><div class="product-media">{img}</div><div class="product-body">'
                      '<p class="eyebrow">{size} width</p><h3>{title}</h3><p class="price">{price} <span>AUD</span></p>{status}'
                      '<span class="btn btn-small">{cta}</span></div></a>').format(
            url=p['url'], img=img('spread-a-bar-in-use', p['title'], '(min-width: 900px) 380px, 100vw'),
            size=esc(p['size']), title=esc(p['title']), price=money(p['price']),
            status='' if p['available'] else '<p class="stock-flag">Currently unavailable</p>',
            cta='View &amp; buy' if p['stripe'] else 'View &amp; order'))
    cards.append(('<a class="product-card product-card--custom" href="mailto:{}?subject=Spread-a-bar%20made%20to%20order%20enquiry">'
                  '<div class="product-body"><p class="eyebrow">Made to order</p><h3>Need a different size?</h3>'
                  '<p>The ELD Arena Spread-a-bar® is available in three sizes or can be made to order upon request.</p>'
                  '<span class="btn btn-small btn-outline">Enquire about sizes</span></div></a>').format(C['email']))
    return '<div class="products{}">{}</div>'.format(' products--compact' if compact else '', ''.join(cards))


NOTICE_ICON = {
    'info': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2zm0-8h-2V7h2z" fill="currentColor"/></svg>',
    'holiday': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2h-2V2h-2v2H9V2zM5 9h14v11H5zm2 2v2h2v-2zm4 0v2h2v-2zm4 0v2h2v-2z" fill="currentColor"/></svg>',
    'urgent': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M1 21h22L12 2zm12-3h-2v-2h2zm0-4h-2v-4h2z" fill="currentColor"/></svg>',
}


def live_notices():
    """Enabled notices that haven't ended (start dates are checked again in the browser, so future ones appear on their own)."""
    return [n for n in NOTICES if n.get('enabled', True) and (n.get('message') or '').strip() and not (n.get('end') and n['end'] < TODAY_QLD)]


def notice_dates(n):
    s, e = n.get('start'), n.get('end')
    f = lambda d: datetime.date.fromisoformat(d).strftime('%-d %B %Y')
    return ('from {} to {}'.format(f(s), f(e)) if s and e else 'from ' + f(s) if s else 'until ' + f(e) if e else '')


def notice_bar(url):
    on_shop = url.startswith('/shop/') or url.startswith('/product/')
    out = []
    for n in live_notices():
        if n.get('where') == 'shop' and not on_shop:
            continue
        style = n.get('style') if n.get('style') in NOTICE_ICON else 'info'
        link = ''
        if n.get('link_url'):
            link = ' <a href="{}">{}</a>'.format(esc(n['link_url']), esc(n.get('link_text') or 'More information'))
        key = '{}-{}'.format(n.get('id', 'n'), hashlib.md5(n['message'].encode()).hexdigest()[:6])
        out.append('<div class="notice notice--{st}" role="status" data-notice="{k}" data-start="{s}" data-end="{e}"{h}><div class="container notice-inner">'
                   '<span class="notice-icon">{ic}</span><p>{m}{l}</p><button class="notice-close" type="button" aria-label="Dismiss this notice">×</button></div></div>'.format(
                       st=style, k=esc(key), s=esc(n.get('start', '')), e=esc(n.get('end', '')), h=' hidden' if n.get('start') and n['start'] > TODAY_QLD else '',
                       ic=NOTICE_ICON[style], m=esc(n['message'].strip()), l=link))
    return '\n'.join(out)


def header(current):
    return notice_bar(current) + '''<a class="skip" href="#content">Skip to content</a>
<div class="topbar"><div class="container topbar-inner">
<div class="topbar-contact"><a href="tel:{pi}">{ip}<span>{pd}</span></a><a href="mailto:{em}">{im}<span>{em}</span></a></div>
<div class="topbar-social"><span class="topbar-note">Est. 2000 · Australian family-owned</span><a href="{fb}" target="_blank" rel="noopener" aria-label="ELD on Facebook">{ifb}</a><a href="{ig}" target="_blank" rel="noopener" aria-label="ELD on Instagram">{iig}</a></div>
</div></div>
<header class="site-header"><div class="container header-inner">
<a class="brand" href="/" aria-label="Equestrian Land Developments – home"><img src="/assets/img/eld-logo.png" width="692" height="308" alt="Equestrian Land Developments Pty Ltd – ELD, Est. 2000"></a>
<nav class="primary-nav" id="primary-nav" aria-label="Main">{nav}
<div class="nav-mobile-extra"><a class="btn btn-primary" href="/arena-construct/eld-construction-quotation-process/">Book a consultation</a><a class="btn btn-outline" href="tel:{pi}">Call {pd}</a></div></nav>
<a class="btn btn-primary header-cta" href="/arena-construct/eld-construction-quotation-process/">Book a consultation</a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="primary-nav"><span class="sr-only">Menu</span><span class="bars" aria-hidden="true"></span></button>
</div></header>'''.format(pi=C['phone_intl'], pd=C['phone_display'], em=C['email'], fb=C['social']['facebook'], ig=C['social']['instagram'],
                          ip=ICON['phone'], im=ICON['mail'], ifb=ICON['facebook'], iig=ICON['instagram'], nav=render_nav(current))


def footer():
    a = C['postal']

    def col(url):
        n = nav_node(url)
        links = [(n['url'], n['title'])] if n['url'] not in [c['url'] for c in n.get('children', [])] else []
        for c in n.get('children', []):
            links.append((c['url'], c['title']))
            links += [(k['url'], k['title']) for k in c.get('children', [])]
        return '<ul>{}</ul>'.format(''.join('<li><a href="{}">{}</a></li>'.format(u, esc(t)) for u, t in links))
    return '''<footer class="site-footer">
<div class="container footer-grid">
<div class="footer-brand"><a class="footer-logo" href="/"><img src="/assets/img/eld-logo.png" width="692" height="308" alt="Equestrian Land Developments" loading="lazy"></a>
<p>{tag} Designing and building quality equestrian arenas and properties since {founded}.</p>
<div class="social"><a href="{fb}" target="_blank" rel="noopener" aria-label="Facebook">{ifb}</a><a href="{ig}" target="_blank" rel="noopener" aria-label="Instagram">{iig}</a></div></div>
<div><h2>Arena Construction</h2>{c1}</div>
<div><h2>Maintenance &amp; Property</h2>{c2}{c3}</div>
<div><h2>About</h2>{c4}<h2 class="mt">Shop</h2><ul><li><a href="/shop/">Arena Shop</a></li>{prods}</ul></div>
<div class="footer-contact"><h2>Contact Us</h2>
<p><strong>{who}</strong><br><a href="tel:{pi}">{ip} {pd}</a></p>
<p><a href="mailto:{em}">{im} {em}</a></p>
<address>{ipin} {legal}<br>{l1}<br>{loc} {reg} {pc}<br>{country}</address>
<a class="btn btn-sand btn-small" href="/arena-construct/eld-construction-quotation-process/">Book a consultation</a></div>
</div>
<div class="footer-bottom"><p>© {year} {legal}. All rights reserved.</p>
<p><a href="/contact-us/">Contact</a> · <a href="/employment/">Employment</a> · <a href="/faq/">FAQ</a> · <a href="/sitemap.xml">Sitemap</a> · <a href="/llms.txt">llms.txt</a></p></div>
</footer>'''.format(tag=esc(C['tagline']), founded=C['founded'], fb=C['social']['facebook'], ig=C['social']['instagram'],
                    ifb=ICON['facebook'], iig=ICON['instagram'], c1=col('/arena-construct/'), c2=col('/maintenance-surface-products/'),
                    c3=col('/property-development/'), c4=col('/experience-quality/'),
                    prods=''.join('<li><a href="{}">{}</a></li>'.format(p['url'], esc(p['title'])) for p in PRODUCTS),
                    who=esc(C['contact_name']), pi=C['phone_intl'], pd=C['phone_display'], em=C['email'], ip=ICON['phone'], im=ICON['mail'],
                    ipin=ICON['pin'], legal=esc(C['legal_name']), l1=a['line1'], loc=a['locality'], reg=a['region'], pc=a['postcode'],
                    country=a['country'], year=YEAR)


def aside(page):
    url = page['url']
    links = nav_children(url) if nav_children(url) else nav_children(page.get('parent', ''))
    heading = label(url) if nav_children(url) else label(page.get('parent', '/'))
    sect = ''
    if links:
        sect = '<div class="aside-card"><h2>{}</h2><ul class="aside-links">{}</ul></div>'.format(esc(heading), ''.join(
            '<li><a href="{}"{}>{}</a></li>'.format(c['url'], ' aria-current="page"' if c['url'] == url else '', esc(c['title'])) for c in links))
    return '''<aside class="page-aside">
<div class="aside-card aside-contact"><p class="eyebrow">Talk to ELD</p><h2>{who}</h2><p>Founder &amp; Director</p>
<a class="aside-line" href="tel:{pi}">{ip} {pd}</a><a class="aside-line" href="mailto:{em}">{im} Email us</a>
<a class="btn btn-primary btn-block" href="/arena-construct/eld-construction-quotation-process/">Book a consultation</a></div>
{sect}</aside>'''.format(who=esc(C['contact_name']), pi=C['phone_intl'], pd=C['phone_display'], em=C['email'], ip=ICON['phone'], im=ICON['mail'], sect=sect)


def page_hero(page, crumb_html, small=False):
    hero = page.get('hero') or 'hero-arena-corinda'
    return '''<section class="page-hero{}"><div class="page-hero-media">{}</div><div class="container page-hero-inner">{}
<p class="eyebrow">{}</p><h1>{}</h1>{}</div></section>'''.format(
        ' page-hero--small' if small else '', img(hero, '', '100vw', eager=True), crumb_html, esc(page.get('eyebrow', '')), esc(page['title']),
        '<p class="lead">{}</p>'.format(esc(page['lead'])) if page.get('lead') else '')


# ---------------------------------------------------------------- structured data
def org_ld():
    a = C['postal']
    return {
        '@type': ['GeneralContractor', 'Organization'], '@id': ORG_ID, 'name': C['name'], 'legalName': C['legal_name'],
        'alternateName': C['short_name'], 'url': SITE + '/', 'slogan': C['tagline'],
        'description': ('Australian family-owned company established in 2000 by Todd Cunningham, specialising in the design and construction of '
                        'equestrian arenas (dressage, show jumping, campdraft & reining, competition, indoor, polo fields, round yards and walker pads), '
                        'arena rebuild, restoration and maintenance, natural manufactured sand arena surfaces, equestrian property layout and earthworks.'),
        'logo': {'@type': 'ImageObject', 'url': absurl('/assets/img/eld-logo.png')}, 'image': img_url('hero-arena-corinda'),
        'foundingDate': C['founded'], 'founder': {'@id': TODD_ID}, 'telephone': C['phone_intl'], 'email': C['email'],
        'address': {'@type': 'PostalAddress', 'postOfficeBoxNumber': '98', 'streetAddress': a['line1'], 'addressLocality': a['locality'],
                    'addressRegion': a['region'], 'postalCode': a['postcode'], 'addressCountry': a['country_code']},
        'areaServed': [{'@type': 'AdministrativeArea', 'name': x} for x in C['service_areas']],
        'contactPoint': {'@type': 'ContactPoint', 'contactType': 'sales', 'name': C['contact_name'], 'telephone': C['phone_intl'],
                         'email': C['email'], 'areaServed': 'AU', 'availableLanguage': 'English'},
        'sameAs': list(C['social'].values()),
        'knowsAbout': ['Equestrian arena construction', 'Dressage arenas', 'Show jumping arenas', 'Campdraft and reining arenas',
                       'Indoor arenas', 'Polo fields', 'Arena surfaces', 'Arena maintenance', 'Equestrian property design', 'Earthworks',
                       'Flood-prone property construction'],
    }


def todd_ld():
    return {'@type': 'Person', '@id': TODD_ID, 'name': 'Todd Cunningham', 'jobTitle': 'Founder & Director', 'worksFor': {'@id': ORG_ID},
            'description': ('Founder of Equestrian Land Developments (est. 2000). Grew up on a property with spelling stables for over 120 horses; '
                            'son of Master Farrier Claye Cunningham; background in earthmoving and construction including international '
                            'underwater excavation and road building. Equitana Australia educator.'),
            'knowsAbout': ['Equestrian arena construction', 'Earthworks', 'Horse property layout']}


def website_ld():
    return {'@type': 'WebSite', '@id': WEBSITE_ID, 'url': SITE + '/', 'name': C['name'], 'alternateName': 'ELD',
            'publisher': {'@id': ORG_ID}, 'inLanguage': 'en-AU'}


def webpage_ld(page, crumb_ld, kind='WebPage'):
    d = {'@type': kind, '@id': absurl(page['url']) + '#webpage', 'url': absurl(page['url']), 'name': page.get('seo_title') or page['title'],
         'description': page.get('description', ''), 'isPartOf': {'@id': WEBSITE_ID}, 'about': {'@id': ORG_ID}, 'inLanguage': 'en-AU'}
    if crumb_ld:
        d['breadcrumb'] = {'@id': crumb_ld['@id']}
    hero = page.get('hero') or page.get('image')
    if hero:
        d['primaryImageOfPage'] = {'@type': 'ImageObject', 'url': img_url(hero)}
    return d


def service_ld(page):
    d = {'@type': 'Service', '@id': absurl(page['url']) + '#service', 'name': page['title'], 'serviceType': page.get('service', page['title']),
         'description': page.get('description', ''), 'provider': {'@id': ORG_ID}, 'url': absurl(page['url']),
         'areaServed': [{'@type': 'AdministrativeArea', 'name': x} for x in C['service_areas']]}
    if page.get('hero'):
        d['image'] = img_url(page['hero'])
    if page['url'] == '/arena-construct/eld-construction-quotation-process/':
        d['offers'] = [{'@type': 'Offer', 'name': name, 'priceCurrency': 'AUD', 'validFrom': '2025-08-01',
                        'priceSpecification': {'@type': 'PriceSpecification', 'minPrice': lo, 'maxPrice': hi, 'priceCurrency': 'AUD',
                                               'valueAddedTaxIncluded': False},
                        'description': 'Full-spec ELD arena: two engineered base layers, ELD surface, sleeper surrounds, earthworks included. '
                                       'Pricing as at 01/08/2025, subject to change; varies with earthworks, location and site.'}
                       for name, lo, hi in [('20m x 60m full-spec arena', 70000, 80000), ('20m x 40m full-spec arena', 60000, 70000)]]
    return d


def video_ld(ctx, date):
    return [{'@type': 'VideoObject', 'name': cap, 'description': cap, 'thumbnailUrl': img_url(poster),
             'contentUrl': absurl('/assets/video/{}.mp4'.format(vid)), 'uploadDate': date or '2022-11-21', 'publisher': {'@id': ORG_ID}}
            for vid, poster, cap in ctx.get('videos', [])]


# ---------------------------------------------------------------- page shell
CSS_V = hashlib.md5(open(os.path.join(ROOT, 'assets', 'css', 'site.css'), 'rb').read()).hexdigest()[:8]
JS_V = hashlib.md5(open(os.path.join(ROOT, 'assets', 'js', 'site.js'), 'rb').read()).hexdigest()[:8]
CHAT = C.get('chat', {})
CHAT_V = hashlib.md5(open(os.path.join(ROOT, 'assets', 'js', 'chat.js'), 'rb').read()).hexdigest()[:8] if CHAT.get('enabled') else ''


def chat_tags():
    if not CHAT.get('enabled'):
        return ''
    cfg = {'endpoint': CHAT.get('endpoint', '').strip(), 'name': CHAT.get('assistant_name', 'ELD Assistant'),
           'greeting': CHAT.get('greeting', ''), 'suggestions': CHAT.get('suggestions', []),
           'phone': C['phone_display'], 'phoneIntl': C['phone_intl'], 'email': C['email'], 'kb': '/assets/chat-kb.json?v=' + TODAY}
    return '<script>window.ELD_CHAT = {};</script>\n<script src="/assets/js/chat.js?v={}" defer></script>\n'.format(
        json.dumps(cfg, ensure_ascii=False).replace('</', '<\\/'), CHAT_V)


def shell(page, body, graph, body_class='', noindex=False, og_type='website'):
    title = page.get('seo_title') or '{} | {}'.format(page['title'], C['name'])
    desc = page.get('description') or C['tagline']
    hero = page.get('hero') or page.get('image') or 'hero-arena-corinda'
    ld = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=1).replace('</', '<\\/')
    robots = 'noindex, follow' if noindex else 'index, follow, max-image-preview:large'
    return '''<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canon}">
{mdlink}<meta property="og:type" content="{ogt}">
<meta property="og:site_name" content="{name}">
<meta property="og:locale" content="en_AU">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{ogimg}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#265e14">
<link rel="icon" href="/assets/icons/favicon-32.jpg" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/icons/icon-192.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="/assets/css/site.css?v={cssv}">
<script type="application/ld+json">
{ld}
</script>
</head>
<body class="{bc}">
{header}
<main id="content">
{body}
</main>
{footer}
<div class="lightbox" hidden><button class="lb-close" type="button" aria-label="Close">×</button><button class="lb-prev" type="button" aria-label="Previous photo">‹</button><figure><img alt=""><figcaption></figcaption></figure><button class="lb-next" type="button" aria-label="Next photo">›</button></div>
<script src="/assets/js/site.js?v={jsv}" defer></script>
{chat}</body>
</html>
'''.format(title=esc(title), desc=esc(desc), robots=robots, canon=absurl(page['url']), mdlink='' if noindex else '<link rel="alternate" type="text/markdown" href="{}index.md" title="Markdown version of this page">\n'.format(page['url']), ogt=og_type,
           name=esc(C['name']), ogimg=img_url(hero), cssv=CSS_V, jsv=JS_V, ld=ld, bc=body_class, header=header(page['url']),
           body=body, footer=footer(), chat=chat_tags())


def write(url, content, name='index.html'):
    d = os.path.join(OUT, url.strip('/'))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
        f.write(content)


def write_md(page, text, extra=''):
    head = '# {}\n\n'.format(page['title'])
    if page.get('lead') or page.get('description'):
        head += '> {}\n\n'.format(page.get('lead') or page.get('description'))
    head += 'Source: {}\n\n'.format(absurl(page['url']))
    doc = head + extra + text.strip() + '\n'
    write(page['url'], doc, 'index.md')
    MARKDOWN[page['url']] = doc


MARKDOWN = {}


# ---------------------------------------------------------------- layouts
def render_page(page):
    ctx = {'url': page['url'], 'title': page['title']}
    layout = page.get('layout', 'page')
    crumb_html, crumb_ld = crumbs(page)
    content = md(page['body'], ctx)
    kind = {'AboutPage': 'AboutPage', 'ContactPage': 'ContactPage', 'FAQPage': 'FAQPage', 'CollectionPage': 'CollectionPage'}.get(page.get('schema'), 'WebPage')
    graph = [org_ld(), website_ld(), webpage_ld(page, crumb_ld, kind), crumb_ld]
    if page.get('schema') == 'Service':
        graph.append(service_ld(page))
    if page.get('schema') == 'AboutPage':
        graph.append(todd_ld())
    if ctx.get('faq'):
        graph[2]['mainEntity'] = [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, _, a in ctx['faq']]
    graph += video_ld(ctx, None)

    hero = page_hero(page, crumb_html)
    if layout == 'hub':
        body = '{}<div class="container section hub"><div class="prose prose--wide">{}</div></div>'.format(hero, content)
    elif layout == 'contact':
        form = ''
        if C['contact_form'].get('action'):
            form = '''<form class="enquiry" action="{}" method="post"><h2>Send an enquiry</h2>
<label>Name<input name="name" autocomplete="name" required></label>
<label>Email<input type="email" name="email" autocomplete="email" required></label>
<label>Phone<input type="tel" name="phone" autocomplete="tel"></label>
<label>Property location<input name="location" placeholder="Town / suburb, state"></label>
<label>How can we help?<textarea name="message" rows="5" required></textarea></label>
<button class="btn btn-primary" type="submit">Send enquiry</button></form>'''.format(esc(C['contact_form']['action']))
        a = C['postal']
        body = '''{hero}<div class="container section contact-grid">
<div class="contact-cards">
<a class="contact-card" href="tel:{pi}"><span class="ci">{ip}</span><span><small>Contact</small><strong>{who}</strong><span>{pd}</span></span></a>
<a class="contact-card" href="mailto:{em}"><span class="ci">{im}</span><span><small>Enquiries</small><strong>{em}</strong></span></a>
<div class="contact-card"><span class="ci">{ipin}</span><span><small>Postal</small><strong>{l1}, {loc}, {reg}. {pc}, {country}</strong></span></div>
<div class="contact-card"><span class="ci">{ifb}</span><span><small>Weekly project updates</small><strong><a href="{fb}" target="_blank" rel="noopener">Facebook</a> · <a href="{ig}" target="_blank" rel="noopener">Instagram</a></strong></span></div>
</div>
<div class="prose">{content}{form}</div></div>'''.format(
            hero=hero, pi=C['phone_intl'], ip=ICON['phone'], who=esc(C['contact_name']), pd=C['phone_display'], em=C['email'], im=ICON['mail'],
            ipin=ICON['pin'], l1=a['line1'], loc=a['locality'], reg=a['region'], pc=a['postcode'], country=a['country'],
            ifb=ICON['facebook'], fb=C['social']['facebook'], ig=C['social']['instagram'], content=content, form=form)
    elif layout == 'shop':
        feats = ''.join('<li>{}{}</li>'.format(ICON['check'], esc(t)) for t in
                        ['Designed by Todd Cunningham', 'Made in Australia (Brisbane)', 'Australia-wide delivery', '30mm tines – protects your base',
                         'No wheels or tyres – no corrugations', 'Folds away for storage'])
        body = '''{}<div class="container section"><div class="prose prose--wide">{}</div>{}
<ul class="ticks" role="list">{}</ul>
{}<p class="secure-note">Prices in Australian dollars. Australia-wide delivery.</p></div>'''.format(hero, content, product_cards(), feats, order_ways())
    else:
        body = '{}<div class="container page-grid"><article class="prose">{}</article>{}</div>'.format(hero, content, aside(page))
    write(page['url'], shell(page, body, graph, 'layout-' + layout))
    write_md(page, md_plain(page['body'], ctx))


def render_product(p):
    ctx = {'url': p['url'], 'title': p['title']}
    crumb_html, crumb_ld = crumbs(p)
    content = md(p['body'], ctx)
    first = C['contact_name'].split()[0]
    buttons = []
    if p['stripe']:
        buttons.append('<a class="btn btn-primary btn-block btn-buy" href="{}">Buy now<span class="btn-sub">Card, Apple Pay or Google Pay</span></a>'.format(esc(p['stripe'])))
        buttons.append('<p class="or-line"><span>or order direct</span></p>')
    if not p['available']:
        buttons.append('<p class="stock-note"><strong>Currently unavailable to buy online.</strong> Email or call {} to check availability.</p>'.format(esc(first)))
    if not p['stripe']:
        WARN.append('no Stripe link for {} – showing email/phone ordering'.format(p['key']))
    buttons.append('<a class="btn {} btn-block" href="{}">{}Email to order</a>'.format(
        'btn-outline' if p['stripe'] else 'btn-primary', esc(order_mailto(p['title'])), ICON['mail']))
    buttons.append('<a class="btn btn-outline btn-block" href="tel:{}">{}Call {} on {}</a>'.format(C['phone_intl'], ICON['phone'], esc(first), C['phone_display']))
    note = '<p class="product-note">{}</p>'.format(esc(p['note'])) if p['note'] else ''
    sizes = ''.join('<a class="size-chip{}" href="{}"{}>{}</a>'.format(
        ' is-current' if q['url'] == p['url'] else '', q['url'], ' aria-current="page"' if q['url'] == p['url'] else '', esc(q['size'].replace(' metre', 'm')))
        for q in PRODUCTS)
    sizes += '<a class="size-chip size-chip--ghost" href="mailto:{}?subject=Spread-a-bar%20made%20to%20order%20enquiry">Other size?</a>'.format(C['email'])
    imgs = [x.strip() for x in p['images'].split(',')]
    thumbs = ''.join('<a href="/assets/img/{}" class="lb pthumb" data-caption="{}">{}</a>'.format(IMG[n]['file'], esc(p['title']), img(n, p['title'], '160px')) for n in imgs[1:])
    video = '<figure class="video"><video controls preload="none" playsinline poster="/assets/img/{}"><source src="/assets/video/{}.mp4" type="video/mp4"></video><figcaption>Watch the Spread-a-bar® in action.</figcaption></figure>'.format(IMG[imgs[0]]['file'], p['video'])
    ctx.setdefault('videos', []).append((p['video'], imgs[0], 'The ELD Arena Spread-a-bar® in use on a sand arena'))
    feats = ''.join('<li>{}{}</li>'.format(ICON['check'], esc(t)) for t in
                    ['Designed by Todd Cunningham, made in Australia', '30mm tines won\'t damage your arena base', 'Flat edge one side, harrows on the reverse',
                     'Tow with a mower, bike, ute or tractor', 'Easy fold-away storage', 'Australia-wide delivery'])
    others = [q for q in PRODUCTS if q['url'] != p['url']]
    body = '''<div class="container product-top">{crumbs}
<div class="product-grid">
<div class="product-gallery"><a href="/assets/img/{mainf}" class="lb product-main" data-caption="{t}">{main}</a><div class="product-thumbs">{thumbs}</div>{video}</div>
<div class="buy-box"><p class="eyebrow">Arena Shop · Arena maintenance made easy</p><h1>{t}</h1>
<p class="buy-price">{price} <span>AUD</span></p>
<div class="sizes" aria-label="Choose a size"><span class="sizes-label">Width</span>{sizes}</div>
<ul class="ticks" role="list">{feats}</ul>
{note}<div class="buy-actions">{buttons}</div>
{badges}<p class="secure-note">Questions before you buy? Email <a href="mailto:{em}">{em}</a> or call {who} on <a href="tel:{pi}">{pd}</a>.</p>
</div></div></div>
<div class="container page-grid"><article class="prose">{content}</article>
<aside class="page-aside"><div class="aside-card"><h2>Also available</h2>{others}</div>
<div class="aside-card"><h2>Maintenance help</h2><ul class="aside-links"><li><a href="/maintenance-surface-products/arena-maintenance/">Arena maintenance tips</a></li><li><a href="/maintenance-surface-products/eld-arena-spread-a-bar/">About the Spread-a-bar®</a></li><li><a href="/faq/">FAQ</a></li></ul></div></aside></div>'''.format(
        crumbs=crumb_html, mainf=IMG[imgs[0]]['file'], main=img(imgs[0], p['title'] + ' in use on a sand arena', '(min-width: 900px) 55vw, 100vw', eager=True),
        t=esc(p['title']), thumbs=thumbs, video=video, price=money(p['price']), sizes=sizes, feats=feats, buttons=''.join(buttons),
        note=note, badges=PAY_BADGES if p['stripe'] else '', em=C['email'],
        who=esc(C['contact_name']), pi=C['phone_intl'], pd=C['phone_display'], content=content,
        others=''.join('<a class="mini-product" href="{}">{}<span><strong>{}</strong><span>{} AUD</span></span></a>'.format(
            q['url'], img(imgs[0], '', '80px'), esc(q['title']), money(q['price'])) for q in others))
    product = {'@type': 'Product', '@id': absurl(p['url']) + '#product', 'name': p['title'], 'sku': p['sku'],
               'description': strip_tags(md_lines(load(os.path.join(ROOT, 'content', 'partials', 'product-body.md'))['body'].split('\n')[:8])),
               'image': [img_url(n) for n in imgs], 'brand': {'@type': 'Brand', 'name': 'ELD'}, 'manufacturer': {'@id': ORG_ID},
               'countryOfOrigin': 'AU', 'additionalProperty': [{'@type': 'PropertyValue', 'name': 'Width', 'value': p['size']},
                                                                {'@type': 'PropertyValue', 'name': 'Tine length', 'value': '30mm'}],
               'offers': {'@type': 'Offer', 'url': absurl(p['url']), 'price': '{:.2f}'.format(float(p['price'])), 'priceCurrency': 'AUD',
                          'availability': 'https://schema.org/' + ('InStock' if p['available'] else 'OutOfStock'), 'itemCondition': 'https://schema.org/NewCondition', 'seller': {'@id': ORG_ID},
                          'areaServed': 'AU'}}
    graph = [org_ld(), website_ld(), webpage_ld(dict(p, hero=imgs[0]), crumb_ld, 'ItemPage'), crumb_ld, product] + video_ld(ctx, p.get('date'))
    write(p['url'], shell(dict(p, hero=imgs[0]), body, graph, 'layout-product', og_type='product'))
    write_md(p, md_plain(p['body'], ctx), '**Price:** {} AUD · **Width:** {} · **SKU:** {} · Australia-wide delivery{}\n\n**How to order:** {}email {} or call {} on {}.{}\n\n'.format(
        money(p['price']), p['size'], p['sku'], '' if p['available'] else ' · **Currently unavailable**',
        'buy online at {} (Stripe: card, Apple Pay or Google Pay), '.format(absurl(p['url'])) if p['stripe'] else '',
        C['email'], C['contact_name'], C['phone_display'], ('\n\n**Note:** ' + p['note']) if p['note'] else ''))


def post_excerpt(p, n=170):
    if p.get('description'):
        return p['description']
    t = strip_tags(md(p['body'], {'url': p['url'], 'title': p['title']}))
    return (t[:n].rsplit(' ', 1)[0] + '…') if len(t) > n else t


def fmt_date(d):
    return datetime.date.fromisoformat(d).strftime('%-d %B %Y')


def news_card(p):
    media = img(p['image'], '', '(min-width: 1000px) 360px, 100vw') if p.get('image') else '<div class="card-fallback" aria-hidden="true">ELD</div>'
    return ('<a class="card news-card" href="{}"><div class="card-media">{}</div><div class="card-body"><time datetime="{}">{}</time>'
            '<h3>{}</h3><p>{}</p><span class="card-more">Read more <span aria-hidden="true">→</span></span></div></a>').format(
        p['url'], media, p['date'], fmt_date(p['date']), esc(p['title']), esc(post_excerpt(p)))


def render_news_index():
    page = {'url': '/news/', 'title': 'Latest News & Updates', 'eyebrow': 'News',
            'seo_title': 'Latest News & Updates | Equestrian Land Developments',
            'description': "What's happening at Equestrian Land Developments? Keep up with our latest news and updates regarding ELD Arena Construction.",
            'lead': 'Keep up to date with the latest news from Equestrian Land Developments!', 'hero': 'arena-35x35-uralla-nsw', 'parent': '/'}
    BY_URL['/news/'] = page
    crumb_html, crumb_ld = crumbs(page)
    body = '''{}<div class="container section"><div class="cards cards--news">{}</div>
<div class="follow"><p>For weekly project updates follow ELD on <a href="{}" target="_blank" rel="noopener">Facebook</a> and <a href="{}" target="_blank" rel="noopener">Instagram</a>.</p></div></div>'''.format(
        page_hero(page, crumb_html), ''.join(news_card(p) for p in POSTS), C['social']['facebook'], C['social']['instagram'])
    blog = {'@type': 'Blog', '@id': SITE + '/news/#blog', 'name': page['title'], 'publisher': {'@id': ORG_ID},
            'blogPost': [{'@type': 'BlogPosting', 'headline': p['title'], 'url': absurl(p['url']), 'datePublished': p['date']} for p in POSTS]}
    write('/news/', shell(page, body, [org_ld(), website_ld(), webpage_ld(page, crumb_ld, 'CollectionPage'), crumb_ld, blog], 'layout-news'))
    write_md(page, '\n'.join('- [{}]({}) – {}{}'.format(p['title'], absurl(p['url']), fmt_date(p['date']),
                                                       ': ' + post_excerpt(p) if post_excerpt(p) else '') for p in POSTS))


def render_post(p, i):
    ctx = {'url': p['url'], 'title': p['title']}
    crumb_html, crumb_ld = crumbs(p)
    content = md(p['body'], ctx)
    lead_img = ''
    if p.get('image') and '::: figure ' + p['image'] not in p['body']:
        m = IMG[p['image']]
        lead_img = '<figure class="figure post-image{}">{}</figure>'.format(' figure--small' if m['w'] < 700 else '',
                                                                             img(p['image'], p['title'], '(min-width: 900px) 760px, 100vw', eager=True))
    tags = ''
    if p.get('tags'):
        tags = '<p class="tags">' + ''.join('<span>{}</span>'.format(esc(t.strip())) for t in p['tags'].split(',')) + '</p>'
    newer = POSTS[i - 1] if i > 0 else None
    older = POSTS[i + 1] if i + 1 < len(POSTS) else None
    pager = '<nav class="post-pager" aria-label="More news">{}{}</nav>'.format(
        '<a class="older" href="{}"><small>Older</small>{}</a>'.format(older['url'], esc(older['title'])) if older else '<span></span>',
        '<a class="newer" href="{}"><small>Newer</small>{}</a>'.format(newer['url'], esc(newer['title'])) if newer else '')
    share_u = absurl(p['url'])
    share = ('<div class="share"><span>Share</span><a href="https://www.facebook.com/sharer/sharer.php?u={0}" target="_blank" rel="noopener" aria-label="Share on Facebook">{1}</a>'
             '<a href="https://www.linkedin.com/shareArticle?mini=true&amp;url={0}" target="_blank" rel="noopener">in</a>'
             '<a href="mailto:?subject={2}&amp;body={0}" aria-label="Share by email">{3}</a></div>').format(share_u, ICON['facebook'], esc(p['title']), ICON['mail'])
    body = '''<div class="container post-head">{crumbs}<p class="eyebrow">News</p><h1>{title}</h1>
<p class="post-meta"><time datetime="{date}">{datef}</time> · by {author}</p></div>
<div class="container page-grid"><article class="prose">{img}{content}{tags}
<p class="follow-inline">For weekly project updates follow ELD on <a href="{fb}" target="_blank" rel="noopener">Facebook</a>.</p>{share}{pager}</article>{aside}</div>'''.format(
        crumbs=crumb_html, title=esc(p['title']), date=p['date'], datef=fmt_date(p['date']), author=esc(p['author']),
        img=lead_img, content=content, tags=tags, fb=C['social']['facebook'], share=share, pager=pager, aside=aside(p))
    posting = {'@type': 'BlogPosting', '@id': absurl(p['url']) + '#article', 'headline': p['title'], 'datePublished': p['date'],
               'dateModified': p.get('updated', p['date']), 'author': {'@type': 'Person', 'name': p['author']}, 'publisher': {'@id': ORG_ID},
               'mainEntityOfPage': {'@id': absurl(p['url']) + '#webpage'}, 'inLanguage': 'en-AU', 'description': post_excerpt(p, 300)}
    if p.get('image'):
        posting['image'] = img_url(p['image'])
    if p.get('tags'):
        posting['keywords'] = p['tags']
    dup = sum(1 for q in POSTS if q['title'] == p['title']) > 1
    seo = '{} – {} | ELD News'.format(p['title'], datetime.date.fromisoformat(p['date']).strftime('%B %Y')) if dup else '{} | ELD News'.format(p['title'])
    pg = dict(p, description=post_excerpt(p, 300), seo_title=seo)
    write(p['url'], shell(pg, body, [org_ld(), website_ld(), webpage_ld(pg, crumb_ld), crumb_ld, posting], 'layout-post', og_type='article'))
    write_md(p, md_plain(p['body'], ctx), '_Published {} by {}._\n\n'.format(fmt_date(p['date']), p['author']))


def render_home():
    page = BY_URL['/']
    faq = parse_faq([l for l in next(x for x in PAGES if x['url'] == '/faq/')['body'].split('::: faq', 1)[1].split('\n:::', 1)[0].split('\n')])
    services = [
        ('/arena-construct/dressage-arenas/', 'dressage-arena-construction'),
        ('/arena-construct/jumping-arenas/', 'arena-with-jumps-estate'),
        ('/arena-construct/campdraftreining-arenas/', 'campdraft-arena-charlwood-qld'),
        ('/shed-construction/indoor-arena-construction-equestrian-land-developments/', 'indoor-arena-huntingdon-nsw'),
        ('/arena-construct/competition-arenas/', 'qsec-indoor-warm-up-arena-caboolture-qld'),
        ('/arena-construct/polo-fields/', 'polo-field-larapinta'),
        ('/arena-construct/round-yards-and-walker-pads/', 'walker-pad'),
        ('/property-development/', 'stable-building-belli-park-qld'),
    ]
    svc = ''.join('<a class="svc" href="{}">{}<span class="svc-label"><strong>{}</strong><span aria-hidden="true">→</span></span></a>'.format(
        u, img(im, '', '(min-width: 1100px) 280px, (min-width: 640px) 45vw, 100vw'), esc(label(u))) for u, im in services)
    logos = ''.join('<li title="{0}">{1}<span class="sr-only">{0}</span></li>'.format(esc(b), img(a, b, '160px')) for a, b in
                    rows(next(x for x in PAGES if x['url'] == '/the-benefits-of-using-eld/')['body'].split('::: logos', 1)[1].split('\n:::', 1)[0].split('\n')))
    news = ''.join(news_card(p) for p in POSTS[:3])
    faqs = ''.join('<details><summary><h3>{}</h3><span class="faq-icon" aria-hidden="true"></span></summary><div class="faq-a">{}</div></details>'.format(esc(q), a)
                   for q, a, _ in faq[:5])
    body = '''
<section class="hero">
  <div class="hero-media">{hero_img}</div>
  <div class="container hero-inner">
    <p class="eyebrow eyebrow--light">Est. 2000 · Australian family-owned</p>
    <h1>Equestrian Land Developments</h1>
    <p class="hero-lead">{tag}</p>
    <div class="hero-actions"><a class="btn btn-sand btn-lg" href="/arena-construct/eld-construction-quotation-process/">Book a consultation</a>
    <a class="btn btn-ghost-light btn-lg" href="/arena-construct/">Explore arena construction</a></div>
  </div>
  <div class="hero-facts"><div class="container"><dl>
    <div><dt>25+ yrs</dt><dd>Building arenas since 2000</dd></div>
    <div><dt>~1 / week</dt><dd>Arenas built on average</dd></div>
    <div><dt>3–4 days</dt><dd>Typical full-spec build – ride immediately</dd></div>
    <div><dt>100% natural</dt><dd>Manufactured sand surfaces, no synthetics</dd></div>
  </dl></div></div>
</section>

<section class="section container intro">
  <div class="intro-text">
    <p class="eyebrow">About ELD</p>
    <h2>Born from a simple request. Built one arena a week, for over 25 years.</h2>
    <p>Equestrian Land Developments was born when a family friend needed a custom-built equestrian arena. From that first project the <strong>ELD Spec. Arena</strong> was created, and in 2000 Equestrian Land Developments Pty Ltd was officially established.</p>
    <p>Founder &amp; Director <strong>Todd Cunningham</strong> grew up on a property with spelling stables for over 120 horses and spent his career in earthmoving and construction – combining horse knowledge with precision earthworks on every project.</p>
    <a class="text-link" href="/experience-quality/">Read our story <span aria-hidden="true">→</span></a>
  </div>
  <div class="intro-media">{intro_img}<div class="intro-badge"><strong>2000</strong><span>Year ELD was established</span></div></div>
</section>

<section class="section section--tint">
  <div class="container">
    <div class="section-head"><p class="eyebrow">What we build</p><h2>Arenas and facilities for every discipline</h2>
    <p>Dressage, show jumping, Western, competition and indoor arenas, polo fields, round yards and walker pads – plus property layout, earthworks and arena rebuild &amp; restoration.</p></div>
    <div class="svc-grid">{svc}</div>
  </div>
</section>

<section class="section container spec">
  <div class="spec-text">
    <p class="eyebrow">The ELD Full Spec. Arena</p>
    <h2>Engineered from the ground up</h2>
    <p>Todd Cunningham designed the first ELD Full Spec. Arena in early 2000 and, to this day, the design has proven successful and long lasting. Todd personally oversees every arena project.</p>
    <ul class="ticks" role="list"><li>{ck}Two engineered base layers</li><li>{ck}ELD natural manufactured sand surface</li><li>{ck}Sleeper surrounds</li><li>{ck}Earthworks included</li><li>{ck}Generally built in 3–4 days, ready to ride immediately</li></ul>
    <div class="spec-price"><div><span>20m x 60m arena</span><strong>$70,000 – $80,000* + GST</strong></div><div><span>20m x 40m arena</span><strong>$60,000 – $70,000* + GST</strong></div>
    <small>*Current pricing as at 01/08/2025, subject to change. Pricing varies based on earthworks, property location and site requirements.</small></div>
    <a class="btn btn-primary" href="/arena-construct/eld-construction-quotation-process/">Consultation &amp; quotation</a>
  </div>
  <div class="spec-visual">{spec}</div>
</section>

<section class="section section--dark eco">
  <div class="eco-media">{eco_img}</div>
  <div class="container eco-inner">
    <div class="eco-text">
      <p class="eyebrow eyebrow--light">Environmental sustainability</p>
      <h2>Natural surfaces. Healthier horses. Lighter footprint.</h2>
      <p>ELD has made a clear commitment to move away from synthetic additives in all arena surfaces – no microplastics, no fibre top-ups, no costly end-of-life removal. We exclusively use our own Australian-manufactured sand surfaces, suited to Australia's climate.</p>
      <p>We contribute a portion of revenue to organisations such as Sea Shepherd, Greenfleet, OzHarvest and The Great Barrier Reef Foundation – and planted a little over 600 trees on our home property by the end of 2021.</p>
      <div class="eco-links"><a class="btn btn-sand" href="/environmental-sustainability-commitment/">Our commitment</a><a class="btn btn-ghost-light" href="/arena-surfaces/">Arena surfaces</a></div>
    </div>
  </div>
</section>

<section class="section container shop-feature">
  <div class="shop-media"><video autoplay muted loop playsinline preload="metadata" poster="/assets/img/spread-a-bar-in-use.jpg" aria-label="The ELD Arena Spread-a-bar in use"><source src="/assets/video/spread-a-bar.mp4" type="video/mp4"></video></div>
  <div class="shop-text">
    <p class="eyebrow">Arena Shop</p>
    <h2>Arena maintenance made easy</h2>
    <p>The <strong>ELD Arena Spread-a-bar®</strong> is engineered to retain the depth of your surface – a flat edge on one side, 30mm harrows on the other, and no wheels to cause corrugations. Designed by Todd Cunningham and made in Australia.</p>
    <div class="price-pills">{pills}</div>
    <div class="hero-actions"><a class="btn btn-primary" href="/shop/">Shop now</a><a class="btn btn-outline" href="/maintenance-surface-products/arena-maintenance/">Maintenance tips</a></div>
  </div>
</section>

<section class="section section--tint clients">
  <div class="container"><div class="section-head section-head--center"><p class="eyebrow">Trusted by</p><h2>Clubs, councils, venues and riders</h2></div>
  <ul class="logos logos--home" role="list">{logos}</ul>
  <p class="center"><a class="text-link" href="/the-benefits-of-using-eld/">Why choose ELD <span aria-hidden="true">→</span></a></p></div>
</section>

<section class="section container">
  <div class="section-head section-head--row"><div><p class="eyebrow">News</p><h2>Latest from ELD</h2></div><a class="text-link" href="/news/">All news <span aria-hidden="true">→</span></a></div>
  <div class="cards cards--news">{news}</div>
</section>

<section class="section container faq-home">
  <div class="section-head"><p class="eyebrow">FAQ</p><h2>Common questions</h2><p>Straight answers about cost, timing, surfaces and maintenance.</p><a class="text-link" href="/faq/">See all questions <span aria-hidden="true">→</span></a></div>
  <div class="faq">{faqs}</div>
</section>

<div class="container section-bottom">{cta}</div>
'''.format(hero_img=img('hero-arena-corinda', 'Sand riding arena with post-and-rail fencing built by Equestrian Land Developments', '100vw', eager=True),
           tag=esc(C['tagline']), intro_img=img('arena-boonah-showgrounds-qld', 'Arena constructed by ELD at Boonah Showgrounds, QLD', '(min-width: 900px) 45vw, 100vw'),
           svc=svc, ck=ICON['check'], spec=SPEC_SVG, eco_img=img('trees-planting', '', '100vw'),
           pills=''.join('<a href="{}"><span>{}</span><strong>{}</strong></a>'.format(p['url'], esc(p['size'].replace(' metre', 'm')), money(p['price']).replace('.00', '')) for p in PRODUCTS),
           logos=logos, news=news, faqs=faqs, cta=cta_band())
    graph = [org_ld(), website_ld(), todd_ld(), webpage_ld(dict(page, hero='hero-arena-corinda'), None)]
    graph[-1]['mainEntity'] = {'@id': ORG_ID}
    write('/', shell(dict(page, hero='hero-arena-corinda'), body, graph, 'layout-home'))
    write_md(dict(page, title='Equestrian Land Developments (ELD)', lead=C['tagline']), md_plain(page['body'], {'url': '/', 'title': 'Home'}))


def render_simple(url, title, body_html, noindex=True, desc=''):
    page = {'url': url, 'title': title, 'description': desc, 'parent': '/'}
    write(url, shell(page, '<div class="container section narrow prose">{}</div>'.format(body_html), [org_ld(), website_ld()], 'layout-simple', noindex=noindex))


# ---------------------------------------------------------------- AI / SEO files
def write_chat_kb():
    """Knowledge file for the chat widget's trial mode (no AI): FAQ answers + page summaries."""
    if not CHAT.get('enabled'):
        return
    faq_body = next(x for x in PAGES if x['url'] == '/faq/')['body']
    extra = load(os.path.join(ROOT, 'content', 'partials', 'chat-answers.md'))['body']

    def block(body):
        inner = body.split('::: faq', 1)[1].split('\n:::', 1)[0]
        return parse_faq(inner.strip('\n').split('\n'))
    items = []
    if live_notices():   # one answer listing every current (or upcoming) notice, so "are you open over Christmas?" finds them
        lis = ''.join('<li>{}{}</li>'.format(esc(n['message'].strip()), ' <a href="{}">{}</a>'.format(esc(n['link_url']), esc(n.get('link_text') or 'More information')) if n.get('link_url') else '')
                      for n in live_notices())
        starts = [n.get('start') or '' for n in live_notices()]
        ends = [n.get('end') or '' for n in live_notices()]
        items.append({'q': 'Notice / notices / are you open / closed / closure / holiday / holidays / christmas / easter / shutdown / break',
                      't': ' '.join(n['message'] for n in live_notices()), 'a': '<p><strong>Current notices:</strong></p><ul>{}</ul>'.format(lis),
                      'from': min(starts) if all(starts) else '', 'to': max(ends) if all(ends) else ''})
    items += [{'q': q, 'a': a_html, 't': a_text} for q, a_html, a_text in block(faq_body) + block(extra)]
    pages = []
    for u, p in BY_URL.items():
        if not p.get('title') or u in ('/',):
            continue
        heads = ' '.join(re.findall(r'^#{2,3} (.+)$', p.get('body', ''), flags=re.M))
        pages.append({'url': u, 'title': p.get('nav_title') or p['title'], 'desc': p.get('lead') or p.get('description', ''), 'k': heads})
    with open(os.path.join(OUT, 'assets', 'chat-kb.json'), 'w', encoding='utf-8') as f:
        json.dump({'faq': items, 'pages': pages}, f, ensure_ascii=False)


def write_ai_files(all_urls):
    by = BY_URL
    a = C['postal']

    def line(u):
        p = by.get(u, {})
        return '- [{}]({}index.md): {}'.format(label(u), absurl(u), p.get('description', '') or p.get('lead', ''))
    sections = [
        ('About ELD', ['/experience-quality/', '/the-benefits-of-using-eld/', '/environmental-sustainability-commitment/', '/faq/']),
        ('Arena construction', ['/arena-construct/', '/arena-surfaces/', '/shed-construction/indoor-arena-construction-equestrian-land-developments/',
                                '/outdoor-arena-construction/', '/arena-construct/dressage-arenas/', '/arena-construct/jumping-arenas/',
                                '/arena-construct/campdraftreining-arenas/', '/arena-construct/polo-fields/', '/arena-construct/verge-systems/',
                                '/arena-construct/competition-arenas/', '/arena-construct/round-yards-and-walker-pads/']),
        ('Arena maintenance & surfaces', ['/maintenance-surface-products/', '/maintenance-surface-products/arena-maintenance/',
                                          '/maintenance-surface-products/eld-arena-spread-a-bar/', '/maintenance-surface-products/surface-products/']),
        ('Property development', ['/property-development/', '/arena-construct/equine-property-layout-design/', '/property-development/earthworks/',
                                  '/arena-construct/flood-prone-areas/', '/real-estate-equestrian-land-developments/']),
        ('Shop', ['/shop/'] + [p['url'] for p in PRODUCTS]),
        ('Contact', ['/contact-us/', '/arena-construct/eld-construction-quotation-process/', '/employment/']),
    ]
    txt = '''# Equestrian Land Developments (ELD)

> Equestrian Land Developments Pty Ltd (ELD) is an Australian family-owned company, established in 2000 by Todd Cunningham and based in South East Queensland, that designs and constructs equestrian arenas and facilities – dressage, show jumping, campdraft & reining, competition, indoor, polo fields, round yards and walker pads – and provides arena rebuild & restoration, maintenance visits, equestrian property layout, earthworks and pre-purchase property consultations. ELD uses only natural manufactured sand surfaces (no synthetic additives) and sells the ELD Arena Spread-a-bar® maintenance implement online.

Key facts:
- Founded: 2000, by Todd Cunningham (Founder & Director). On average one arena built per week for over 25 years.
- Full-spec ELD arena: two engineered base layers, ELD surface, sleeper surrounds, earthworks included; generally built in 3–4 days and ready to ride immediately.
- Pricing (as at 01/08/2025, subject to change; varies with earthworks, location and site): 20m x 60m arena $70,000–$80,000 + GST; 20m x 40m arena $60,000–$70,000 + GST.
- Onsite consultations attract a fee, credited toward arena construction if you proceed. Pre-purchase property inspections available. ELD keeps records of every arena built since 2000 and can verify claims that an arena is ELD-built.
- Arena surface life: on average 5–7 years, extended with maintenance. Maintenance visits (Automated Laser Planes) every 3, 6 or 12 months; minimum 4–6 weeks lead time; currently servicing SE QLD and Northern NSW.
- Shop: {shop}; other sizes made to order. {order} Made in Australia (Brisbane). Australia-wide delivery.
- Contact: {who}, phone {pd} ({pi}), email {em}. Postal: {l1}, {loc} {reg} {pc}, {country}. Facebook: {fb} · Instagram: {ig}

'''.format(order='Order online (Stripe: card, Apple Pay, Google Pay), by email or by phone.' if STRIPE_ON else 'Order by email or phone.',
           shop='; '.join('{} {} AUD{}'.format(p['title'], price_text(p['price']), '' if p['available'] else ' (currently unavailable)') for p in PRODUCTS),
           who=C['contact_name'], pd=C['phone_display'], pi=C['phone_intl'], em=C['email'], l1=a['line1'], loc=a['locality'], reg=a['region'],
           pc=a['postcode'], country=a['country'], fb=C['social']['facebook'], ig=C['social']['instagram'])
    if live_notices():
        notes = '\n'.join('- {}{}{}'.format(n['message'].strip(), ' ({})'.format(notice_dates(n)) if notice_dates(n) else '',
                                             ' [shop orders]' if n.get('where') == 'shop' else '') for n in live_notices())
        txt += '## Current notices (as at {})\n\n{}\n\n'.format(TODAY_QLD, notes)
    for title, urls in sections:
        txt += '## {}\n\n{}\n\n'.format(title, '\n'.join(line(u) for u in urls))
    txt += '## News\n\n- [Latest News & Updates]({}/news/index.md)\n{}\n\n'.format(SITE, '\n'.join(
        '- [{}]({}index.md): {}'.format(p['title'], absurl(p['url']), fmt_date(p['date'])) for p in POSTS))
    txt += '## Optional\n\n- [Full site content in one file]({}/llms-full.txt)\n- [Sitemap]({}/sitemap.xml)\n'.format(SITE, SITE)
    open(os.path.join(OUT, 'llms.txt'), 'w', encoding='utf-8').write(txt)

    order = ['/'] + [u for _, us in sections for u in us] + ['/news/'] + [p['url'] for p in POSTS]
    full = '# Equestrian Land Developments – full website content\n\nGenerated {} from {}\n\n'.format(TODAY, SITE)
    if live_notices():
        full += '## Current notices\n\n' + '\n'.join('- {}{}'.format(n['message'].strip(), ' ({})'.format(notice_dates(n)) if notice_dates(n) else '') for n in live_notices()) + '\n\n---\n\n'
    full += '\n\n---\n\n'.join(MARKDOWN[u] for u in order if u in MARKDOWN)
    open(os.path.join(OUT, 'llms-full.txt'), 'w', encoding='utf-8').write(full)

    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in all_urls:
        p = by.get(u, {})
        lastmod = p.get('updated') or p.get('date') or TODAY
        sm.append('<url><loc>{}</loc><lastmod>{}</lastmod></url>'.format(absurl(u), lastmod))
    sm.append('</urlset>')
    open(os.path.join(OUT, 'sitemap.xml'), 'w').write('\n'.join(sm) + '\n')

    bots = ['GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-SearchBot', 'Claude-User', 'PerplexityBot', 'Perplexity-User',
            'Google-Extended', 'Applebot-Extended', 'Bingbot', 'Googlebot', 'CCBot', 'DuckAssistBot', 'meta-externalagent']
    robots = '# Equestrian Land Developments – search engines and AI assistants are welcome.\n# AI-friendly summaries: /llms.txt and /llms-full.txt\n\n'
    robots += ''.join('User-agent: {}\nAllow: /\n\n'.format(b) for b in bots)
    robots += 'User-agent: *\nAllow: /\nDisallow: /shop/thank-you/\n\nSitemap: {}/sitemap.xml\n'.format(SITE)
    open(os.path.join(OUT, 'robots.txt'), 'w').write(robots)


REDIRECTS = [
    ('/shed-construction/', '/shed-construction/indoor-arena-construction-equestrian-land-developments/'),
    ('/product-category/products/', '/shop/'),
    ('/cart/', '/shop/'),
    ('/checkout/', '/shop/'),
    ('/my-account/', '/shop/'),
    ('/my-account/lost-password/', '/shop/'),
    ('/home/', '/'),
    ('/wp-content/uploads/2026/03/ELD_Maintenance-Tips_A4_2026-1.pdf', '/assets/docs/ELD-Maintenance-Tips-2026.pdf'),
    ('/wp-content/uploads/2026/03/ELD_Spread-a-bar_Tips_A4_2026-1.pdf', '/assets/docs/ELD-Spread-a-bar-Tips-2026.pdf'),
    ('/wp-content/uploads/2026/03/ELD_SyntheticSurfaces_A4_2026.pdf', '/assets/docs/ELD-Synthetic-Surfaces-2026.pdf'),
    ('/wp-content/uploads/2026/10/Indoor-Arena-Construction-Tips-Advice-2026-6.pdf', '/assets/docs/Indoor-Arena-Construction-Tips-Advice-2026.pdf'),
    ('/wp-content/uploads/2022/12/ELD_Spread-a-bar_A4_2022.pdf', '/assets/docs/ELD-Spread-a-bar-2022.pdf'),
]
WILDCARDS = [('/news/category/', '/news/'), ('/news/tag/', '/news/'), ('/news/author/', '/news/'), ('/product-category/', '/shop/')]


def write_version():
    """Fingerprints of the admin-edited files, so the admin can tell when a saved change is live."""
    v = {k: hashlib.sha256(open(f, 'rb').read()).hexdigest()[:16] for k, f in (('shop', SHOP_FILE), ('notices', NOTICES_FILE))}
    v['built'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump(v, open(os.path.join(OUT, 'version.json'), 'w'))


def write_redirects():
    admin = C.get('admin_url', '').strip()
    redirects = REDIRECTS + ([('/admin', admin), ('/admin/', admin)] if admin else [])
    nl = ['# Redirects from the old WordPress site (Netlify / Cloudflare Pages format)']
    nl += ['{}  {}  301'.format(a, b) for a, b in redirects]
    nl += ['{}*  {}  301'.format(a, b) for a, b in WILDCARDS]
    open(os.path.join(OUT, '_redirects'), 'w').write('\n'.join(nl) + '\n')
    ht = ['# Apache (cPanel) hosting: redirects from the old WordPress site', 'ErrorDocument 404 /404.html', 'DirectoryIndex index.html',
          'AddType text/markdown .md', 'AddCharset utf-8 .md .txt']
    ht += ['Redirect 301 {} {}'.format(a, b) for a, b in redirects]
    ht += ['RedirectMatch 301 ^{}.*$ {}'.format(re.escape(a), b) for a, b in WILDCARDS]
    open(os.path.join(OUT, '.htaccess'), 'w').write('\n'.join(ht) + '\n')
    # Render.com blueprint (lives in the project root, next to build.py)
    ry = ['# Render.com static site – generated by build.py (edit REDIRECTS in build.py, not here)', 'services:',
          '  - type: web', '    name: eld-website', '    runtime: static', '    buildCommand: python3 build.py',
          '    staticPublishPath: ./public', '    pullRequestPreviewsEnabled: false',
          '    buildFilter:', '      ignoredPaths:', '        - server/**', '        - README.md', '    headers:',
          '      - path: /version.json', '        name: Cache-Control', '        value: no-store',
          '      - path: /assets/*', '        name: Cache-Control', '        value: public, max-age=2592000',
          '      - path: /*', '        name: X-Content-Type-Options', '        value: nosniff', '    routes:']
    for a, b in redirects:
        ry += ['      - type: redirect', '        source: ' + a, '        destination: ' + b]
    for a, b in WILDCARDS:
        ry += ['      - type: redirect', '        source: {}*'.format(a), '        destination: ' + b]
    # The admin + chat back end (server/): a small Python web service
    ry += ['', '  - type: web', '    name: eld-admin', '    runtime: python', '    plan: free', '    rootDir: server',
           '    buildCommand: pip install -r requirements.txt', '    startCommand: python app.py', '    healthCheckPath: /health',
           '    envVars:', '      - key: PYTHON_VERSION', '        value: 3.12.7',
           '      - key: GITHUB_REPO', '        value: AusJumping/eld-website', '      - key: SITE_URL', '        value: ' + SITE_LIVE,
           '      - key: ADMIN_PASSWORD', '        sync: false', '      - key: GITHUB_TOKEN', '        sync: false',
           '      - key: ANTHROPIC_API_KEY', '        sync: false']
    open(os.path.join(ROOT, 'render.yaml'), 'w').write('\n'.join(ry) + '\n')


# ---------------------------------------------------------------- main
def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, 'assets'), os.path.join(OUT, 'assets'),
                    ignore=shutil.ignore_patterns('manifest.json', '.DS_Store'))
    for p in PAGES:
        if p.get('layout') == 'home' or p['url'] == '/':
            continue
        render_page(p)
    for p in PRODUCTS:
        render_product(p)
    render_news_index()
    for i, p in enumerate(POSTS):
        render_post(p, i)
    render_home()
    render_simple('/shop/thank-you/', 'Thank you for your order', '''<p class="eyebrow">Arena Shop</p><h1>Thank you for your order</h1>
<p>Your payment has been received and a receipt has been emailed to you by our payment provider.</p>
<p>If you have any questions about your order or delivery, please contact {} on <a href="tel:{}">{}</a> or email <a href="mailto:{}">{}</a>.</p>
<p><a class="btn btn-primary" href="/">Back to home</a></p>'''.format(esc(C['contact_name']), C['phone_intl'], C['phone_display'], C['email'], C['email']))
    render_simple('/404/', 'Page not found', '''<p class="eyebrow">404</p><h1>Sorry, we couldn't find that page</h1>
<p>The page may have moved when our website was updated. Try one of these:</p>
<ul><li><a href="/arena-construct/">Arena construction</a></li><li><a href="/maintenance-surface-products/">Arena maintenance</a></li>
<li><a href="/shop/">Arena shop</a></li><li><a href="/news/">Latest news</a></li><li><a href="/contact-us/">Contact us</a></li></ul>''')
    shutil.move(os.path.join(OUT, '404', 'index.html'), os.path.join(OUT, '404.html'))
    shutil.rmtree(os.path.join(OUT, '404'))
    all_urls = ['/'] + [p['url'] for p in PAGES if p['url'] != '/'] + [p['url'] for p in PRODUCTS] + ['/news/'] + [p['url'] for p in POSTS]
    write_ai_files(all_urls)
    write_chat_kb()
    write_redirects()
    write_version()
    n = len(glob.glob(os.path.join(OUT, '**', 'index.html'), recursive=True))
    print('Built {} pages into public/'.format(n))
    for w in sorted(set(WARN)):
        print('  note:', w)


if __name__ == '__main__':
    main()
