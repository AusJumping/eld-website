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
| `config.json` | Phone, email, address, social links, **Stripe and PayPal settings**. |
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

## Setting up the shop checkout (Stripe and/or PayPal)

The shop uses **hosted checkout**, so card details never touch this website and there's nothing to keep PCI-compliant.

**Stripe (recommended: cards, Apple Pay, Google Pay):**
1. In the Stripe Dashboard → *Payment Links* → create one link per product (1m at $1,150 AUD, 1.5m at $1,480 AUD).
2. In each link's options, turn on **collect shipping address** (and add a shipping rate if you charge delivery), and optionally **let customers adjust quantity**.
3. Under *After payment*, set the redirect to `https://www.equestrianlanddevelopments.com/shop/thank-you/`.
4. Paste each link into `config.json` → `shop.products.<product>.stripe_payment_link`.

**PayPal:**
- Put your PayPal Business account email in `config.json` → `shop.paypal_business_email`. A "Pay with PayPal" button then appears on each product, with buyers' shipping address required.

If neither is set, the product pages show an **Order by email** button, so the site still works while you set up payments. Run `python3 build.py` after changing `config.json`.

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
