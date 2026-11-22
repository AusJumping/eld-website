# Equestrian Land Developments: new website

A fast, modern, AI-friendly rebuild of equestrianlanddevelopments.com. It's a **static site**: plain HTML files with no WordPress, no database and no plugins to update. It can be hosted almost anywhere for little or nothing.

## Folder layout

| Folder / file | What it is |
|---|---|
| `content/pages/*.md` | One file per page. Edit the words here. |
| `content/news/*.md` | News posts. Add a new file to publish a post. |
| `content/products/*.md` | Shop product pages (size, SKU, photos). |
| `content/shop.json` | Product names, **prices**, availability, notes and **Stripe links**. Edited in the website admin. |
| `content/notices.json` | **Website notices** (Christmas closures etc.). Edited in the website admin. |
| `content/partials/product-body.md` | The Spread-a-bar® description shared by both product pages. |
| `content/navigation.json` | The main menu. |
| `config.json` | Phone, email, address, social links, chat settings. |
| `server/` | The **website admin** and the AI chat back end (a small Python web service on Render). |
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

## Website admin (prices and notices)

Staff can change shop prices and put notices on the website without touching any code:

**https://eld-admin.onrender.com/admin** (or `/admin` on the website, which redirects there)

- **Notices tab:** banners across the top of the website, e.g. *"Our office is closed for the Christmas break…"*. Pick a colour, choose every page or shop pages only, and set start and end dates. Notices appear and disappear by themselves on those dates (Queensland time). There are quick-start buttons for a Christmas closure, an office closure and a delivery delay. Current notices are also given to the chat assistant and to AI tools (`llms.txt`).
- **Products & prices tab:** product name, price, *available to buy* on/off, a note shown on the product page (e.g. *"Orders after 15 December ship in January"*) and the Stripe payment link. A price changed here updates everywhere on the site: product pages, shop, home page, FAQ, chat and AI files.
- Press **Save**. The website updates in about 1–2 minutes, and the admin shows *"Done – your changes are live"* when it has. Every save is recorded in the GitHub history, so any change can be undone.
- The admin runs on Render's free plan, so the first visit after a quiet spell can take up to a minute to wake up.

**One-time setup** (the `eld-admin` service is created automatically from `render.yaml`):
1. **Create a GitHub access key** so the admin can save changes. On github.com go to *Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token*:
   - Name: `ELD website admin`. Expiration: your choice. If it expires, the admin shows a clear message and you create a new one.
   - Resource owner: `AusJumping`. Repository access: *Only select repositories* → `eld-website`.
   - Permissions → Repository permissions → **Contents: Read and write**. Nothing else is needed.
   - Generate the token and copy it.
2. In **Render → eld-admin → Environment**, set:
   - `GITHUB_TOKEN` = the token from step 1
   - `ADMIN_PASSWORD` = the password staff will use (at least 12 characters, e.g. three or four random words)

   Save, and Render restarts the admin.
3. Visit the admin and sign in. To change the password later, change `ADMIN_PASSWORD` in Render; this signs everyone out.

Security: one shared password, with sign-in limited to 8 attempts per 15 minutes. Sessions last 12 hours. Everything a user types is checked on the server: only Stripe links are accepted as payment links, only on-site or https links in notices, and text is escaped. The admin can only change those two files, and the token can only touch this one repository.

## Setting up the shop checkout (Stripe)

The shop uses **Stripe hosted checkout**, so card details never touch this website and there's nothing to keep PCI-compliant. Stripe's checkout page offers **card, Apple Pay and Google Pay** automatically. Apple Pay shows on iPhone, iPad and Mac (Safari) when the customer has a card in Apple Wallet, and Google Pay shows on Android and Chrome.

1. In the Stripe Dashboard → *Settings → Payment methods*, check that **Apple Pay** and **Google Pay** are turned on (they usually are by default).
2. In *Payment Links*, create one link per product at the same price as the website.
3. In each link's options, turn on **collect shipping address** (and add a shipping rate if you charge delivery), and optionally **let customers adjust quantity**.
4. Under *After payment*, set the redirect to `https://www.equestrianlanddevelopments.com/shop/thank-you/`.
5. Paste each link into the **website admin → Products & prices** and save.
6. Test: open a product page on your iPhone in Safari, tap **Buy now** and check that the black Apple Pay button appears at the top of the checkout.

**Important:** a Stripe payment link charges the price set *in Stripe*. If you change a price in the admin, change it in Stripe too (edit the link's price or make a new link). The admin reminds you when you change the price of a product that has a Stripe link.

Ordering options on the site: **Buy now** (Stripe, when a link is set), then **Email to order** (opens an email with the product filled in, asking for name, phone and delivery address), then **Call Todd**. Without a Stripe link, email is the first option.

## Chat assistant

Every page has an **Ask ELD** chat bubble (bottom right). It has two modes:

- **Trial mode (current, free):** answers instantly from the FAQ page, `content/partials/chat-answers.md` and the page summaries. There's no AI and no cost. To teach it a new answer, add a question and answer to `chat-answers.md` and rebuild. If it can't find an answer, it gives Todd's phone number and email.
- **AI mode:** the bubble sends the conversation to the `eld-admin` server (`server/`), which asks Claude to answer **using only the website's own content** (`llms-full.txt`). The API key stays on the server and visitors never see it. If the server is ever down, the bubble quietly falls back to trial answers.

**Turning on AI mode:**
1. Get an API key from console.anthropic.com (Settings → API keys). Set a monthly spend limit there too.
2. In **Render → eld-admin → Environment**, add `ANTHROPIC_API_KEY` = your key and save.
3. In `config.json` → `chat.endpoint`, put `https://eld-admin.onrender.com/chat`, then run `python3 build.py` and push.

Built-in safeguards: the server only answers requests from your own website, allows 30 messages per visitor per hour and 1,000 per day in total (change these with the `MAX_PER_IP_HOUR` / `MAX_PER_DAY` environment variables), never logs what visitors type, and caches the site content so repeat questions cost much less. It uses Claude Opus 5.5 at low effort for quick, conversational replies. If a question is ever declined, the request is automatically retried on a fallback model.

The assistant's name, greeting and suggested questions are in `config.json` → `chat`. Set `"enabled": false` to remove the bubble.

## Hosting

**Current setup: GitHub + Render.** The site deploys automatically: every push to the `main` branch on GitHub makes Render run `python3 build.py` and publish `public/`. `render.yaml` (created by the build) holds the Render settings for both services (the static website and `eld-admin`), including redirects from old WordPress addresses. Saving in the admin is just another commit, so it triggers the same rebuild. So to update the live site: edit `content/`, commit, push. You don't need to upload anything by hand.

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
