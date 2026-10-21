# Microsoft Universe Chronicle

An unofficial, daily-refreshed chronicle of official Microsoft updates: Dynamics 365,
Microsoft 365, Azure, Copilot, agents, Fabric, Power Platform, security, MAI models,
the Microsoft IQ ecosystem, and an end-of-support watch across the catalogue.

**Unofficial project. Not affiliated with or endorsed by Microsoft.** Every entry links
to the official Microsoft source it came from.

## How it works

- `ingest.py` (stdlib only) reads official Microsoft RSS feeds, the Microsoft Learn
  lifecycle pages, and microsoft.ai/news, classifies each item into nine product
  families and practice lenses (AIOps, MLOps, FinOps, DevSecOps, Security happenings,
  Agents, MAI models), and writes `data/entries.json` + `data/eos.json`.
- `build.py` renders the static site into `site/`.
- `.github/workflows/daily.yml` runs both daily (07:30 GST) and on push, commits the
  data back, and deploys `site/` to GitHub Pages.

## Run locally

```
python3 ingest.py
python3 build.py
open site/index.html
```

## Icons and brand

See BRAND.md. Product icons are Microsoft's official architecture icon sets, used
unmodified under Microsoft's stated terms for diagrams and documentation. Products
without an official free icon set are shown with original letter tiles.
