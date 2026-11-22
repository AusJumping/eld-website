# Equestrian Land Developments: new website

A fast, modern, AI-friendly rebuild of equestrianlanddevelopments.com. It's a **static site**: plain HTML files with no WordPress, no database and no plugins to update. It can be hosted almost anywhere for little or nothing.

## Folder layout

| Folder / file | What it is |
|---|---|
| `content/pages/*.md` | One file per page. Edit the words here. |
| `content/news/*.md` | News posts. Add a new file to publish a post. |
| `content/products/*.md` | Shop products (price, size, SKU). |
| `content/partials/product-body.md` | The Spread-a-bar® description shared by both product pages. |
| `content/navigation.json` | The main menu. |
| `config.json` | Phone, email, address, social links, **Stripe checkout links**. |
| `assets/` | Images, PDFs, video, CSS and JS. |
| `build.py` | Turns everything above into the finished website. |
| `public/` | **The finished website. Upload this folder's contents to your host.** |

## Making changes

1. Edit a file in `content/` (any text editor works).
2. Open Terminal in this folder and run:

```bash
python3 build.py
```

3. Upload the contents of `public/` to your host (or push to Git if your host deploys from it).

### Page file format

```
---
url: /arena-construct/dressage-arenas/     ← web address (keep the same as the old site)
title: Dressage Arenas                      ← page heading
seo_title: …                                ← Google / browser-tab title
description: …                              ← Google snippet + AI summary
lead: …                                     ← intro line under the heading
hero: dressage-arena-construction           ← banner photo (name from assets/img)
parent: /outdoor-arena-construction/        ← for breadcrumbs
---
Normal text. **Bold**, [a link](/contact-us/), ## Heading, - bullet points.
```

Special blocks start with `::: name` and end with `:::`:

- `::: gallery`: one `image-name | caption` per line
- `::: figure image-name | caption`: a single photo
- `::: downloads`: `Title | /assets/docs/file.pdf` per line
- `::: features`: `Title | text | optional-link` per line (card grid)
- `::: pricing`: `Item | Price` per line
- `::: callout`: a highlighted box
- `::: faq`: question on one line, answer below, blank line between each
- `::: cta`: the "Talk to Todd" banner

### Adding a news post

Create `content/news/my-post.md`:

```
---
url: /news/my-post/
title: My post title
date: 2026-12-01
author: Joanne
image: arena-20x60-tamborine-qld
description: One-sentence summary for Google and AI tools.
---
Post text here…
```

### Adding new photos

Put the originals somewhere, add a line to `tools/images.tsv` (`new-name<TAB>path`), then run `python3 tools/optimize_images.py "<folder containing the originals>"` (needs `pip install pillow` once). It creates web-sized copies in `assets/img/`.

## Setting up the shop checkout (Stripe)

The shop uses **Stripe hosted checkout**, so card details never touch this website and there's nothing to keep PCI-compliant. Stripe's checkout page offers **card, Apple Pay and Google Pay** automatically. Apple Pay shows on iPhone, iPad and Mac (Safari) when the customer has a card in Apple Wallet, and Google Pay shows on Android and Chrome.

1. In the Stripe Dashboard → *Settings → Payment methods*, check that **Apple Pay** and **Google Pay** are turned on (they usually are by default).
2. In *Payment Links*, create one link per product (1m at $1,150 AUD, 1.5m at $1,480 AUD).
3. In each link's options, turn on **collect shipping address** (and add a shipping rate if you charge delivery), and optionally **let customers adjust quantity**.
4. Under *After payment*, set the redirect to `https://www.equestrianlanddevelopments.com/shop/thank-you/`.
5. Paste each link into `config.json` → `shop.products.<product>.stripe_payment_link`, then run `python3 build.py` (or push, and Render rebuilds).
6. Test: open a product page on your iPhone in Safari, tap **Buy now** and check that the black Apple Pay button appears at the top of the checkout.

If a product has no link yet, its page shows an **Order by email** button, so the site still works while you set up Stripe.

## Chat assistant

Every page has an **Ask ELD** chat bubble (bottom right). It has two modes:

- **Trial mode (current, free):** answers instantly from the FAQ page, `content/partials/chat-answers.md` and the page summaries. There's no AI and no cost. To teach it a new answer, add a question and answer to `chat-answers.md` and rebuild. If it can't find an answer, it gives Todd's phone number and email.
- **AI mode:** the bubble sends the conversation to the small server in `chat-server/`, which asks Claude to answer **using only the website's own content** (`llms-full.txt`). The API key stays on the server and visitors never see it. If the server is ever down, the bubble quietly falls back to trial answers.

**Turning on AI mode:**
1. Get an API key from console.anthropic.com (Settings → API keys). Set a monthly spend limit there too.
2. In Render: **New → Web Service** → choose the `eld-website` repo, then:
   - Root Directory: `chat-server`
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `python app.py`
   - Environment variable: `ANTHROPIC_API_KEY` = your key
3. Copy the service's address (e.g. `https://eld-chat.onrender.com`) into `config.json` → `chat.endpoint` with `/chat` on the end, then run `python3 build.py` and push.

Built-in safeguards: the server only answers requests from your own website, allows 30 messages per visitor per hour and 1,000 per day in total (change these with the `MAX_PER_IP_HOUR` / `MAX_PER_DAY` environment variables), never logs what visitors type, and caches the site content so repeat questions cost much less. It uses Claude Opus 5.5 at low effort for quick, conversational replies. If a question is ever declined, the request is automatically retried on a fallback model.

The assistant's name, greeting and suggested questions are in `config.json` → `chat`. Set `"enabled": false` to remove the bubble.

## Hosting

**Current setup: GitHub + Render.** The site deploys automatically: every push to the `main` branch on GitHub makes Render run `python3 build.py` and publish `public/`. `render.yaml` (created by the build) holds the Render settings, including redirects from old WordPress addresses. So to update the live site: edit `content/`, commit, push. You don't need to upload anything by hand.

Any other static host also works. Low-cost options:
- **Netlify** or **Cloudflare Pages** (free tier): drag-and-drop the `public/` folder. The included `_redirects` file automatically forwards old WordPress addresses (cart, my-account, tag pages, old PDF links).
- **Existing cPanel/Apache host:** upload `public/` to `public_html`. The included `.htaccess` handles the same redirects.

All page addresses are **the same as the old site**, so Google rankings and existing links keep working.

## What makes it AI-friendly

- **`/llms.txt`**: a plain-English summary of the business, key facts (pricing, timeframes, service area, contacts) and a map of every page, in the format AI assistants look for.
- **`/llms-full.txt`**: the entire site's content in one Markdown file.
- **A Markdown copy of every page** (`/any-page/index.md`), linked from each page's `<head>`.
- **Structured data (schema.org JSON-LD)** on every page: business details, founder, services with pricing, products with prices, FAQ, news articles, breadcrumbs and video.
- **`robots.txt`** explicitly welcomes search engines and AI crawlers (ChatGPT, Claude, Perplexity, Google, Apple, Bing…).
- **New FAQ page** answering the questions people actually ask AI tools ("how much does an arena cost?", "how long does it take?"), using only facts from the existing site.
- Descriptive photo file names and alt text (e.g. `arena-20x60-tamborine-qld.jpg`), clean semantic HTML and an XML sitemap.
