---
title: What REA revealed
---

Guide
{ .eyebrow }

# What REA revealed

Using [morluto/rea](https://github.com/morluto/rea) ("Reverse Engineer Anything") to observe LandingAI's web properties: the method, what it showed, and the line it does not cross.
{ .lead }

## What REA is

REA is an MCP server and CLI for reverse engineering: native binaries through Hopper, Ghidra or IDA; JavaScript and Electron apps; .NET assemblies; Android APKs; and **websites**, where it attaches to a Chrome you start with a remote-debugging port and produces "bounded Evidence about an existing page" through the Chrome DevTools Protocol. The website provider is deliberately passive: it captures DOM structure, scripts, resources, network metadata and screenshots, and it does not navigate, click, evaluate JavaScript, or log in. Source: [REA browser observation docs](https://github.com/morluto/rea/blob/main/docs/browser-observation.md).

## Method

```bash
# a throwaway Chrome profile with CDP on loopback, with the pages of interest open
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9333 --remote-debugging-address=127.0.0.1 \
  --user-data-dir=/tmp/rea-profile --no-first-run \
  https://docs.landing.ai/dpt3/overview https://ade.landing.ai/ https://landing.ai/ade/parse

npx -y rea-agents@latest list-browser-targets http://127.0.0.1:9333 --json
npx -y rea-agents@latest analyze-web-bundle   http://127.0.0.1:9333 <target-id> --json
npx -y rea-agents@latest inspect-web-page     http://127.0.0.1:9333 <target-id> --observation-ms 4000 --json
npx -y rea-agents@latest capture-web-screenshot http://127.0.0.1:9333 <target-id> --json
```

One practical note: on a Mac where another Chrome already holds `127.0.0.1:9222`, a second Chrome binds its debugging port on IPv6 `[::1]` only, and REA's endpoint validation rejects it. Use a fresh port and `--remote-debugging-address=127.0.0.1`.

## Findings

| Target | What REA observed | What it tells you |
|---|---|---|
| `docs.landing.ai` | Next.js bundle served from `/mintlify-assets/_next/`, no API endpoint candidates in the bundle; theme tokens `--primary: 17 120 102`, `--primary-light: 219 255 155`, `--primary-dark: 3 34 29` | The docs are a Mintlify site (the page footer says so too). The palette of this wiki comes from these tokens. |
| `ade.landing.ai` | Immediate redirect to `/signin-redirect`, then to `login.landing.ai/sign-in?app_id=…`; a Next.js app with `(protected)` and `(unprotected)` route groups; the public bundle contains no `api.ade.landing.ai` or `/v2/` strings | The Playground is a separate SPA behind a central login service. The API contract is not discoverable from the public bundle, and REA will not cross the login. |
| `landing.ai/ade/parse` | Marketing page; 15 resource URLs, one in-site route, no API traffic | Nothing beyond the copy quoted on the [overview](overview.md). |

A final pass exported the retained scripts of the public sign-in page (`inspect-web-page --include-script-sources`, then `export-web-scripts`): eight files, all `login.landing.ai/assets/*` vendor bundles (React, i18next, libphonenumber, core-js) with their source maps, and not one occurrence of `api.ade.landing.ai`, `/v2/parse`, or a `dpt-` model name. The public client knows nothing about the parsing API.

Screenshots captured by REA were used to match this wiki's layout to the docs site (dark canvas, lime accent, left navigation, right "On this page", top tabs).

## The boundary

REA sees the **client contract and the vendor stack**: the frameworks, the login flow, the public routes, the published spec. It never sees the model. Everything about how DPT-3 reads a page comes from documents LandingAI chose to publish ([how DPT-3 works](how-dpt3-works.md)), and the most informative of those turned out to be the OpenAPI spec's prose, the changelog's provider notes, and the pricing basis, none of which needed a reverse-engineering tool. REA's contribution here was to confirm quickly that there was nothing more to find on the client side, which is itself useful: it closes the question instead of leaving it open.

What was deliberately not done: signing in to the Playground, exporting or analysing scripts behind authentication, or probing the API without a key. Those are the user's account and the vendor's terms, not a public page.
