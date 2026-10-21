#!/usr/bin/env python3
"""Generate the static Microsoft Universe Chronicle site from data/*.json. Stdlib only."""
import json, os, html, re
from datetime import datetime, timezone
from icons_data import ICONS

def esc(s):
    return html.escape(str(s), quote=True)

FAMILY_ORDER = ['AI & Copilot', 'Azure', 'Business Apps (D365)', 'Modern Work', 'Power Platform & Fabric',
                'Security & Identity', 'Windows & Devices', 'Developer', 'Consumer']

FAMILY_META = {
    'AI & Copilot': ('azure-ai-foundry', 'Copilot, MAI models, Foundry, agents, the IQ ecosystem',
                     ['azure-ai-foundry', 'foundry-iq', 'foundry-agent-service', 'copilot-studio', 'agent-365', 'mono-copilot', 'mono-mai']),
    'Azure': ('app-services', 'Compute, data, networking, management and governance',
              ['app-services', 'aks', 'azure-sql', 'function-apps', 'azure-monitor', 'app-insights', 'cost-management']),
    'Business Apps (D365)': ('dynamics365', 'ERP and CRM: Finance, Supply Chain, Business Central, Sales, Service',
                             ['dynamics365', 'd365-finance', 'd365-scm', 'd365-business-central', 'd365-sales', 'd365-customer-service', 'd365-contact-center', 'd365-field-service', 'd365-project-ops']),
    'Modern Work': ('mono-teams', 'Microsoft 365 apps, Teams, SharePoint, Exchange, OneDrive, Viva',
                    ['mono-teams', 'mono-sharepoint', 'mono-outlook', 'mono-onedrive', 'mono-word', 'mono-excel', 'mono-powerpoint']),
    'Power Platform & Fabric': ('fabric', 'Power BI, Power Apps, Power Automate, Dataverse, Copilot Studio, Fabric',
                                ['fabric', 'power-bi', 'power-apps', 'power-automate', 'power-pages', 'dataverse', 'fabric-warehouse', 'fabric-eventstream', 'fabric-lakehouse', 'fabric-notebook']),
    'Security & Identity': ('defender-for-cloud', 'Defender, Sentinel, Entra, Purview, Intune',
                            ['defender-for-cloud', 'sentinel', 'entra-id-protection']),
    'Windows & Devices': ('mono-windows', 'Windows client, Windows Server, Surface', ['mono-windows']),
    'Developer': ('azure-devops', 'GitHub, Visual Studio, .NET, Azure DevOps', ['azure-devops', 'mono-github']),
    'Consumer': ('mono-consumer', 'Xbox, LinkedIn, Bing, Surface hardware - tracked quietly', []),
}

LENS_ORDER = ['AIOps', 'MLOps', 'FinOps', 'DevSecOps', 'Security happenings', 'Agents', 'MAI models']

SOURCES = [
    ('Microsoft 365 roadmap', 'https://www.microsoft.com/en-us/microsoft-365/roadmap'),
    ('Azure updates', 'https://azure.microsoft.com/en-us/updates'),
    ('Azure blog', 'https://azure.microsoft.com/en-us/blog/'),
    ('Fabric updates blog', 'https://blog.fabric.microsoft.com/en-us/blog/'),
    ('Power Platform blog', 'https://www.microsoft.com/en-us/power-platform/blog/'),
    ('Dynamics 365 blog', 'https://www.microsoft.com/en-us/dynamics-365/blog/'),
    ('Microsoft Security blog', 'https://www.microsoft.com/en-us/security/blog/'),
    ('Microsoft AI news', 'https://microsoft.ai/news/'),
    ('Microsoft Foundry blog', 'https://devblogs.microsoft.com/foundry/'),
    ('Microsoft DevBlogs', 'https://devblogs.microsoft.com/'),
    ('GitHub blog', 'https://github.blog/'),
    ('Windows blog', 'https://blogs.windows.com/'),
    ('Microsoft Learn lifecycle', 'https://learn.microsoft.com/en-us/lifecycle/'),
]

def _sprite_defs():
    defs = []
    for k, svg in ICONS.items():
        for i in set(re.findall(r'id="([^"]+)"', svg)):
            svg = (svg.replace(f'url(#{i})', f'url(#{k}--{i})')
                      .replace(f'href="#{i}"', f'href="#{k}--{i}"')
                      .replace(f'id="{i}"', f'id="{k}--{i}"'))
        m = re.search(r'viewBox="([^"]+)"', svg)
        vb = m.group(1) if m else '0 0 48 48'
        inner = svg[svg.find('>') + 1:svg.rfind('</svg>')]
        defs.append(f'<symbol id="i-{k}" viewBox="{vb}">{inner}</symbol>')
    return '<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">' + ''.join(defs) + '</svg>'

def ic(key, size=18, cls=''):
    if key not in ICONS:
        return ''
    return f'<span class="ic {cls}" style="width:{size}px;height:{size}px" aria-hidden="true"><svg style="width:100%;height:100%"><use href="#i-{key}"/></svg></span>'

def section_label(s):
    t = re.sub(r'\s+', ' ', s or '')
    for pat, lab in [('Retire', 'Retirement'), ('End of Servicing', 'End of servicing'),
                     ('End of Support', 'End of support'), ('Extended', 'Moves to extended support'),
                     ('Azure', 'Azure change')]:
        if pat in t:
            return lab
    return 'Lifecycle'

CSS = """
:root{--bg:#f6f2ea;--ink:#16130e;--muted:#6d665b;--accent:#a33d21;--line:#ddd4c4;--chipbg:#efe9dc}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:Georgia,'Times New Roman',serif;line-height:1.5}
.topbar{background:var(--ink);color:#d8d2c4;font-family:Arial,sans-serif;font-size:11px;letter-spacing:.1em;text-transform:uppercase;text-align:center;padding:7px 12px}
header.top{display:flex;justify-content:space-between;align-items:center;padding:16px 28px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:8px}
.brand{font-size:19px}
nav a{font-family:Arial,sans-serif;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-decoration:none;margin-left:18px}
.wrap{max-width:1060px;margin:0 auto;padding:0 28px 60px}
.hero{padding:40px 0 6px}
.kicker{font-family:Arial,sans-serif;font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-bottom:12px}
h1{font-size:42px;font-weight:normal;line-height:1.12;max-width:760px}
.sub{color:var(--muted);font-size:16px;max-width:660px;margin-top:12px}
.refresh{font-family:Arial,sans-serif;font-size:12px;color:var(--muted);margin-top:14px}
h2.sec{font-size:27px;font-weight:normal;margin:44px 0 4px}
.secnote{font-family:Arial,sans-serif;font-size:12.5px;color:var(--muted);margin-bottom:16px}
.famgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}
.famcard{background:#fbf8f1;border:1px solid var(--line);border-radius:10px;padding:16px;cursor:pointer}
.famcard h3{font-size:17px;font-weight:normal;margin:10px 0 4px}
.famcard p{font-size:12.5px;color:var(--muted);font-family:Arial,sans-serif}
.famcard .n{font-family:Arial,sans-serif;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin-top:10px}
.iconrow{display:flex;gap:6px;flex-wrap:wrap}
.ic{display:inline-flex;flex:none}.ic svg{width:100%;height:100%;border-radius:6px}
.axislabel{font-family:Arial,sans-serif;font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:20px 0 6px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}
.chip{font-family:Arial,sans-serif;font-size:11.5px;padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:#fbf8f1;color:var(--ink);cursor:pointer}
.chip.on{background:var(--ink);color:#f6f2ea;border-color:var(--ink)}
.chip.lens{border-style:dashed;color:var(--accent);border-color:#cfa48f;background:transparent}
.chip.lens.on{background:var(--accent);color:#fff;border-color:var(--accent)}

.viewcard{background:#fffdf8;border:1px solid #e5ddcf;border-radius:14px;padding:26px 30px;margin:14px 0 26px;max-width:820px}
.viewmeta{font:600 12px/1 'Inter',sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#8a8272;display:flex;gap:10px;align-items:center;margin-bottom:10px}
.viewlens{background:#f3e7de;color:#a33d21;border-radius:999px;padding:4px 12px;font-size:11px}
.viewtitle{font-family:Georgia,serif;font-size:26px;font-weight:600;margin:0 0 12px;color:#16130e}
.viewcard p{font:15px/1.65 Georgia,serif;color:#2c2820;margin:0 0 12px}
.viewcard a{color:#a33d21;text-decoration:underline;text-underline-offset:2px}
.viewsrc{font:12px/1.5 'Inter',sans-serif;color:#8a8272;border-top:1px solid #ece4d4;padding-top:10px;margin-top:14px}
.pulse{margin-top:8px}
.prow{display:flex;align-items:center;gap:12px;padding:5px 0;font-family:Arial,sans-serif;font-size:12px}
.prow .pl{flex:0 0 190px;color:#3d382f}
.prow .bar{height:8px;background:var(--accent);border-radius:4px;opacity:.75}
.prow .pc{color:var(--muted)}
.daygroup{margin-top:30px}
.dayrow{display:flex;gap:26px}
.daterail{flex:0 0 118px;font-family:Arial,sans-serif;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);padding-top:4px}
.entries{flex:1;border-top:1px solid var(--line)}
.entry{padding:18px 0 20px;border-bottom:1px solid var(--line)}
.etop{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:7px}
.tag{font-family:Arial,sans-serif;font-size:10px;letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;border-radius:999px;background:var(--chipbg);color:#4d4638;border:1px solid var(--line)}
.tag.lens{background:transparent;color:var(--accent);border:1px solid #cfa48f}
.tag.status{background:#e4ecda;color:#415d23;border:1px solid #c3d1a8}
.entry h3{font-size:20px;font-weight:normal;margin-bottom:5px}
.entry h3 a{color:var(--ink);text-decoration:none}
.entry h3 a:hover{text-decoration:underline}
.entry p{font-size:14px;color:#3d382f;max-width:760px}
.src{font-family:Arial,sans-serif;font-size:11px;color:var(--muted);margin-top:7px}
.src a{color:var(--muted)}
table{border-collapse:collapse;width:100%}
.watchrow{display:flex;gap:14px;align-items:baseline;padding:10px 0;border-bottom:1px solid var(--line)}
.watchrow .wp{flex:1;font-size:14px}
.watchrow .wd{font-family:Arial,sans-serif;font-size:12px;color:var(--muted);white-space:nowrap}
.watchrow .ws{font-family:Arial,sans-serif;font-size:12px;color:#3d382f;flex:0 0 150px}
.pill{font-family:Arial,sans-serif;font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:2px 8px;border-radius:999px;white-space:nowrap}
.pill.soon{background:#f4e3c2;color:#7a5410}
.pill.late{background:#f0d5cd;color:#7c2f16}
.pill.gone{background:#e8d9d3;color:#7c2f16}
.eosline{width:100%;height:auto;margin:10px 0 4px}
.el1{font-family:Arial,sans-serif;font-size:11px;fill:var(--accent);font-weight:bold}
.el2{font-family:Arial,sans-serif;font-size:10.5px;fill:#4d4638}
footer{margin-top:50px;padding-top:18px;border-top:1px solid var(--line);font-family:Arial,sans-serif;font-size:11.5px;color:var(--muted)}
footer .srclist{columns:2;margin:8px 0 14px}
footer a{color:var(--muted)}
@media (max-width:760px){
 h1{font-size:30px}
 .dayrow{flex-direction:column;gap:4px}
 .famgrid{grid-template-columns:1fr}
 nav a{margin-left:0;margin-right:14px}
 .prow .pl{flex:0 0 130px}
 footer .srclist{columns:1}
 .watchrow .ws{display:none}
}
"""

def eos_svg(rows, now_ts):
    """Monthly milestone timeline: one dot per month with a count, no label collisions."""
    from collections import Counter
    up = [r for r in rows if r['ts'] >= now_ts - 3 * 86400]
    if not up:
        return ''
    months = Counter()
    for r in up:
        months[r['date'][:7]] += 1
    keys = sorted(months)[:10]
    if len(keys) < 2:
        return ''
    W, pad, axis_y = 1040, 60, 120
    step = (W - 2 * pad) / (len(keys) - 1)
    parts = [f'<svg viewBox="0 0 {W} 210" class="eosline" role="img" aria-label="End of support timeline">',
             f'<line x1="{pad}" y1="{axis_y}" x2="{W-pad}" y2="{axis_y}" stroke="#16130e" stroke-width="1.5"/>']
    for i, k in enumerate(keys):
        xx = pad + i * step
        d = datetime.strptime(k + '-01', '%Y-%m-%d')
        label = d.strftime('%b %Y')
        above = i % 2 == 0
        ty = 62 if above else 182
        parts.append(f'<line x1="{xx:.0f}" y1="{axis_y - 14 if above else axis_y}" x2="{xx:.0f}" y2="{axis_y if above else axis_y + 14}" stroke="#a33d21" stroke-width="1"/>')
        parts.append(f'<circle cx="{xx:.0f}" cy="{axis_y}" r="5" fill="#a33d21"/>')
        parts.append(f'<text x="{xx:.0f}" y="{ty}" text-anchor="middle" class="el1">{esc(label)}</text>')
        parts.append(f'<text x="{xx:.0f}" y="{ty + 17}" text-anchor="middle" class="el2">{months[k]} product group{"s" if months[k] > 1 else ""}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def main():
    views = []
    try:
        views = [v for v in json.load(open('data/views.json'))['views'] if v.get('status') == 'approved']
    except Exception:
        views = []

    def _md(t):
        t = esc(t)
        return re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', r'<a href="\2">\1</a>', t)

    if views:
        cards = []
        for v in views:
            paras = ''.join(f'<p>{_md(par)}</p>' for par in v['body'])
            try:
                when = datetime.strptime(v['approved_at'], '%Y-%m-%d').strftime('%d %b %Y')
            except Exception:
                when = esc(v.get('approved_at', ''))
            cards.append(
                f'<article class="viewcard"><div class="viewmeta"><span class="viewlens">{esc(v["lens"])}</span>'
                f'Ankit Samriwal &middot; {when}</div>'
                f'<h3 class="viewtitle">{esc(v["title"])}</h3>{paras}'
                f'<div class="viewsrc">{esc(v["sources"])}</div></article>')
        views_html = ('<h2 class="sec" id="views">Expert views</h2>'
                      '<div class="secnote">Original analysis by Ankit Samriwal - his reading of the cycle, linked to the official entries it cites. Each view is published with his approval.</div>'
                      + ''.join(cards))
        views_nav = '<a href="#views">Expert views</a>'
    else:
        views_html = ''
        views_nav = ''
    edata = json.load(open('data/entries.json'))
    entries = edata['entries']
    eos = json.load(open('data/eos.json'))
    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    from collections import Counter
    fam_counts = Counter(e['family'] for e in entries)
    lens_present = sorted({l for e in entries for l in e['lenses']}, key=lambda l: LENS_ORDER.index(l) if l in LENS_ORDER else 99)

    # family map cards
    cards = []
    for fam in FAMILY_ORDER:
        icon, tagline, prods = FAMILY_META[fam]
        prows = ''.join(ic(k, 30) for k in prods[:8])
        cards.append(f'''<div class="famcard" data-fam="{esc(fam)}" onclick="setFam(this.dataset.fam)">
  <div class="iconrow">{ic(icon, 34)}{prows}</div>
  <h3>{esc(fam)}</h3><p>{esc(tagline)}</p>
  <div class="n">{fam_counts.get(fam, 0)} entries this cycle</div></div>''')

    # pulse bars
    maxc = max(fam_counts.values() or [1])
    pulse = ''.join(f'''<div class="prow"><span class="pl">{esc(f)}</span>
  <span class="bar" style="width:{max(2, int(380 * fam_counts.get(f, 0) / maxc))}px"></span>
  <span class="pc">{fam_counts.get(f, 0)}</span></div>''' for f in FAMILY_ORDER if fam_counts.get(f, 0))

    famchips = '<button class="chip on" data-fam="" onclick="setFam(\'\')">All</button>' + ''.join(
        f'<button class="chip" data-fam="{esc(f)}" onclick="setFam(this.dataset.fam)">{esc(f)}</button>' for f in FAMILY_ORDER)
    lenschips = ''.join(f'<button class="chip lens" data-lens="{esc(l)}" onclick="setLens(this.dataset.lens)">{esc(l)}</button>' for l in lens_present)

    # timeline
    days, cur = [], None
    for e in entries:
        if e['date'] != cur:
            cur = e['date']
            d = datetime.strptime(cur, '%Y-%m-%d')
            days.append((cur, d.strftime('%a %-d %b %Y'), []))
        days[-1][2].append(e)
    tl = []
    for _, label, es in days:
        body = []
        for e in es:
            fam = e['family']
            tags = f'<span class="tag">{esc(fam)}</span>'
            if e.get('status'):
                tags += f'<span class="tag status">{esc(e["status"])}</span>'
            tags += ''.join(f'<span class="tag lens">{esc(l)}</span>' for l in e['lenses'][:3])
            famicon = FAMILY_META.get(fam, ('', '', []))[0]
            body.append(f'''<article class="entry" data-fam="{esc(fam)}" data-lens="{esc('|'.join(e['lenses']))}">
  <div class="etop">{ic(famicon, 20)}{tags}</div>
  <h3><a href="{esc(e['url'])}">{esc(e['title'])}</a></h3>
  <p>{esc(e['summary'])}</p>
  <div class="src">Source: {esc(e['source'])} &middot; <a href="{esc(e['url'])}">{esc(re.sub(r'^https?://', '', e['url']))}</a></div>
</article>''')
        tl.append(f'<section class="daygroup"><div class="dayrow"><div class="daterail">{esc(label)}</div><div class="entries">{"".join(body)}</div></div></section>')

    # support watch
    up = sorted([r for r in eos['rows'] if r['ts'] >= now_ts - 30 * 86400], key=lambda r: r['ts'])[:14]
    wrows = []
    for r in up:
        days_left = round((r['ts'] - now_ts) / 86400)
        if days_left >= 0:
            pill = f'<span class="pill soon">in {days_left}d</span>' if days_left <= 45 else f'<span class="pill late">in {days_left}d</span>'
        else:
            pill = f'<span class="pill gone">ended {-days_left}d ago</span>'
        wrows.append(f'''<div class="watchrow"><span class="wp">{esc(r['product'])}</span>
  <span class="ws">{esc(section_label(r['section']))}</span>
  <span class="wd">{esc(r['date_str'])}</span>{pill}</div>''')

    srclist = ''.join(f'<div>&middot; <a href="{esc(u)}">{esc(n)}</a></div>' for n, u in SOURCES)
    gen = edata.get('generated_at', '')
    total = len(entries)

    sprite = _sprite_defs()
    page = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Microsoft Universe Chronicle</title>
<meta name="description" content="An unofficial daily chronicle of official Microsoft updates: D365, M365, Azure, Copilot, agents, Fabric, Power Platform, security, MAI models, the IQ ecosystem, and end-of-support watch.">
<style>{CSS}</style></head>
<body>
{sprite}
<div class="topbar">Unofficial chronicle &middot; not affiliated with or endorsed by Microsoft &middot; every entry links to an official Microsoft source</div>
<header class="top">
  <div class="brand">Microsoft Universe Chronicle</div>
  <nav><a href="#map">Landscape</a>{views_nav}<a href="#chronicle">Chronicle</a><a href="#support">Support watch</a><a href="#sources">Sources</a></nav>
</header>
<div class="wrap">
  <section class="hero">
    <div class="kicker">All of Microsoft &middot; one chronicle &middot; official sources only</div>
    <h1>Every Microsoft update, in order, in plain language.</h1>
    <p class="sub">D365, M365, Azure, Copilot, Agents, Fabric, Power Platform, Security, MAI models, the IQ ecosystem. Refreshed daily. {total} entries in the current cycle.</p>
    <div class="refresh">Last refreshed: {esc(gen)} &middot; refreshed daily by automation &middot; entries cover roughly the last 120 days</div>
  </section>

  <h2 class="sec" id="map">The landscape</h2>
  <div class="secnote">Nine product families, tracked across official Microsoft feeds. Select a family to filter the chronicle. Product icons are Microsoft's official architecture icons (see Sources for terms).</div>
  <div class="famgrid">{''.join(cards)}</div>

  <h2 class="sec">This cycle at a glance</h2>
  <div class="secnote">Entries per family across the tracked official feeds in the current 120-day window. Computed from the feeds listed under Sources.</div>
  <div class="pulse">{pulse}</div>

  {views_html}
  <h2 class="sec" id="chronicle">The chronicle</h2>
  <div class="axislabel">Filter by product family</div>
  <div class="chips">{famchips}</div>
  <div class="axislabel">Practice lens</div>
  <div class="chips">{lenschips}</div>
  {''.join(tl)}

  <h2 class="sec" id="support">Support watch</h2>
  <div class="secnote">End of support and retirements across the Microsoft catalogue, from the Microsoft Learn lifecycle pages. Next milestones first.</div>
  {eos_svg(eos['rows'], now_ts)}
  {''.join(wrows)}

  <footer id="sources">
    <b>Sources</b> (all official Microsoft, all public, all free):
    <div class="srclist">{srclist}</div>
    <p>Method: a daily automated job reads these feeds and the Microsoft Learn lifecycle pages, classifies each item into a product family and practice lens, and rebuilds this page. Chronicle entries are not editorial opinion; every entry links to its Microsoft source. Expert views, when present, are original analysis by Ankit Samriwal, published with his per-item approval.</p>
    <p style="margin-top:8px">Icons: official Microsoft architecture icon sets (Azure, Dynamics 365, Power Platform, Fabric, Entra), used under Microsoft's icon terms for diagrams and documentation, unmodified. Products without an official free icon set are shown with original letter tiles. Microsoft product names are trademarks of Microsoft. This is an independent, unofficial chronicle.</p>
    <p style="margin-top:8px">Built and maintained by Instinct for Ankit Samriwal.</p>
  </footer>
</div>
<script>
let F='',L='';
function setFam(f){{F=(F===f)?'':f;paint();}}
function setLens(l){{L=(L===l)?'':l;paint();}}
function paint(){{
  document.querySelectorAll('.chip[data-fam]').forEach(c=>c.classList.toggle('on',c.dataset.fam===F));
  document.querySelectorAll('.chip[data-lens]').forEach(c=>c.classList.toggle('on',c.dataset.lens===L));
  document.querySelectorAll('.entry').forEach(e=>{{
    const okF=!F||e.dataset.fam===F;
    const okL=!L||(''+e.dataset.lens).split('|').includes(L);
    e.style.display=(okF&&okL)?'':'none';
  }});
  document.querySelectorAll('.daygroup').forEach(g=>{{
    g.style.display=[...g.querySelectorAll('.entry')].some(e=>e.style.display!=='none')?'':'none';
  }});
}}
</script>
</body></html>'''
    os.makedirs('site', exist_ok=True)
    open('site/index.html', 'w').write(page)
    print(f'site/index.html written: {len(page)} bytes, {len(entries)} entries')

if __name__ == '__main__':
    main()
