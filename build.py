#!/usr/bin/env python3
"""Generate the static Microsoft Universe Chronicle site from data/*.json. Stdlib only.
Layout: 'Broadsheet' editorial design. Icons come from icons_data.py (see BRAND.md)."""
import json, os, html, re
from collections import Counter
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

# Product matcher: (pattern, icon key, display name). Most specific first.
# An entry only gets an icon when its title names a product in the icon set,
# so an icon always sits next to the product it depicts (BRAND.md).
PRODUCTS = [
    (r'Business Central', 'd365-business-central', 'D365 Business Central'),
    (r'Customer Service', 'd365-customer-service', 'D365 Customer Service'),
    (r'Contact Center', 'd365-contact-center', 'D365 Contact Center'),
    (r'Field Service', 'd365-field-service', 'D365 Field Service'),
    (r'Project Operations', 'd365-project-ops', 'D365 Project Operations'),
    (r'Supply Chain', 'd365-scm', 'D365 Supply Chain Management'),
    (r'Dynamics 365 Finance|Finance and Operations|finance and operations', 'd365-finance', 'D365 Finance'),
    (r'Dynamics 365 Sales', 'd365-sales', 'D365 Sales'),
    (r'Dynamics 365|Dynamics CRM|Customer Insights|Dynamics 365 Commerce', 'dynamics365', 'Dynamics 365'),
    (r'Copilot Studio', 'copilot-studio', 'Copilot Studio'),
    (r'Agent 365', 'agent-365', 'Agent 365'),
    (r'Power BI', 'power-bi', 'Power BI'),
    (r'Power Apps', 'power-apps', 'Power Apps'),
    (r'Power Automate', 'power-automate', 'Power Automate'),
    (r'Power Pages', 'power-pages', 'Power Pages'),
    (r'Dataverse', 'dataverse', 'Dataverse'),
    (r'Power Platform', 'power-platform', 'Power Platform'),
    (r'Fabric (Data )?Warehouse', 'fabric-warehouse', 'Fabric Data Warehouse'),
    (r'Eventstream', 'fabric-eventstream', 'Fabric Eventstreams'),
    (r'Lakehouse', 'fabric-lakehouse', 'Fabric Lakehouse'),
    (r'Fabric notebook', 'fabric-notebook', 'Fabric notebooks'),
    (r'Fabric|OneLake', 'fabric', 'Microsoft Fabric'),
    (r'Foundry IQ', 'foundry-iq', 'Foundry IQ'),
    (r'Foundry Agent Service', 'foundry-agent-service', 'Foundry Agent Service'),
    (r'Foundry', 'azure-ai-foundry', 'Microsoft Foundry'),
    (r'Sentinel', 'sentinel', 'Microsoft Sentinel'),
    (r'Defender', 'defender-for-cloud', 'Microsoft Defender'),
    (r'Entra', 'entra-id-protection', 'Microsoft Entra'),
    (r'\bAKS\b|Kubernetes', 'aks', 'Azure Kubernetes Service'),
    (r'Azure SQL|SQL database', 'azure-sql', 'Azure SQL'),
    (r'Azure Functions|Function App', 'function-apps', 'Azure Functions'),
    (r'Application Insights', 'app-insights', 'Application Insights'),
    (r'Azure Monitor', 'azure-monitor', 'Azure Monitor'),
    (r'Cost Management', 'cost-management', 'Cost Management'),
    (r'App Service', 'app-services', 'Azure App Service'),
    (r'Azure DevOps', 'azure-devops', 'Azure DevOps'),
    (r'GitHub', 'mono-github', 'GitHub'),
    (r'\bTeams\b', 'mono-teams', 'Microsoft Teams'),
    (r'SharePoint', 'mono-sharepoint', 'SharePoint'),
    (r'Outlook|Exchange', 'mono-outlook', 'Outlook'),
    (r'OneDrive', 'mono-onedrive', 'OneDrive'),
    (r'\bWord\b', 'mono-word', 'Word'),
    (r'\bExcel\b', 'mono-excel', 'Excel'),
    (r'PowerPoint', 'mono-powerpoint', 'PowerPoint'),
    (r'Windows', 'mono-windows', 'Windows'),
    (r'\bMAI\b', 'mono-mai', 'MAI models'),
    (r'Copilot', 'mono-copilot', 'Copilot'),
]
PRODUCTS = [(re.compile(p), k, n) for p, k, n in PRODUCTS if k in ICONS]

def match_product(text):
    for rx, key, name in PRODUCTS:
        if rx.search(text or ''):
            return key, name
    return None, None

def match_all(text, limit=6):
    """All distinct products named in a ' · '-joined lifecycle row."""
    out, seen = [], set()
    for part in (text or '').split('·'):
        k, n = match_product(part)
        if k and k not in seen:
            seen.add(k)
            out.append((k, n))
    return out[:limit]

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
    if not key or key not in ICONS:
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

def status_class(s):
    s = (s or '').lower()
    if 'launch' in s or 'general' in s:
        return 'ga'
    if 'preview' in s:
        return 'pv'
    if 'develop' in s:
        return 'dev'
    return ''

CSS = """
:root{--bg:#FAFAF7;--paper:#FFFFFF;--ink:#16181D;--ink2:#3A3E47;--muted:#5A5F6B;--line:#D9D8D2;--line2:#E4E3DD;--accent:#1F45C7;--warn:#A4400B;--ok:#1B6B3A;
--serif:'Newsreader',Georgia,'Times New Roman',serif;--sans:'Public Sans',system-ui,-apple-system,'Segoe UI',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}a:hover{color:#16338F}
.wrap{max-width:1200px;margin:0 auto;padding:0 32px 80px}
.strip{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 12px;padding:14px 0;border-bottom:1px solid var(--line);font-size:13px;color:var(--muted)}
.mast{padding:40px 0 24px;text-align:center;border-bottom:3px double var(--ink)}
.kicker{font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
.mast h1{margin-top:12px;font-family:var(--serif);font-weight:700;font-size:clamp(40px,7vw,76px);line-height:1;letter-spacing:-.02em}
nav.sections{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}
nav.sections .links{display:flex;flex-wrap:wrap;gap:6px 28px;font-size:15px;font-weight:500}
nav.sections .links a{color:var(--ink);text-decoration:none;padding:10px 0}
nav.sections .links a:hover{text-decoration:underline;text-underline-offset:4px}
.search{display:flex;align-items:center;gap:8px;border:1px solid #C9C8C1;border-radius:6px;padding:0 12px;height:44px;background:var(--paper)}
.search label{font-size:13px;color:var(--muted)}
.search input{border:0;outline:none;font:inherit;font-size:14px;width:220px;max-width:50vw;background:transparent;color:var(--ink)}
.search:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px rgba(31,69,199,.15)}
.lead{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:48px;padding:48px 0;border-bottom:1px solid var(--line)}
.lead h2{font-family:var(--serif);font-weight:600;font-size:clamp(32px,4.4vw,48px);line-height:1.08;letter-spacing:-.01em}
.lead p{margin-top:20px;font-size:18px;line-height:1.6;color:var(--ink2);max-width:560px}
.lead .refresh{margin-top:14px;font-size:13px;color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-top:1px solid var(--ink);align-self:start}
.stats>div{padding:20px 16px;border-bottom:1px solid var(--line)}
.stats>div:nth-child(odd){padding-left:0}
.stats>div:nth-child(even){border-left:1px solid var(--line)}
.stats>div:nth-last-child(-n+2){border-bottom:0}
.stats .n{font-family:var(--serif);font-size:52px;font-weight:600;line-height:1.1}
.stats .n.warn{color:var(--warn)}
.stats .l{font-size:14px;color:var(--muted)}
section.block{padding:48px 0;border-bottom:1px solid var(--line)}
.bhead{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:12px 16px;margin-bottom:20px}
.bhead h2{font-family:var(--serif);font-size:34px;font-weight:600}
.bhead .note{font-size:14px;color:var(--muted);max-width:620px}
.famgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));border-top:1px solid var(--ink)}
.fam{all:unset;box-sizing:border-box;cursor:pointer;display:flex;gap:14px;padding:20px 16px;border-bottom:1px solid var(--line);border-right:1px solid var(--line);min-height:44px}
.fam:hover{background:var(--paper)}
.fam:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.fam.on{background:var(--paper);box-shadow:inset 0 3px 0 var(--ink)}
.fam .body{flex:1;min-width:0}
.fam .t{display:block;font-weight:600;font-size:16px}
.fam .d{display:block;font-size:13px;color:var(--muted);margin-top:2px}
.fam .prods{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.fam .bar{display:block;height:3px;background:var(--line2);margin-top:12px}
.fam .bar span{display:block;height:3px;background:var(--ink)}
.fam .c{font-family:var(--serif);font-size:26px;font-weight:600}
.fam.zero .t,.fam.zero .c{color:var(--muted)}
.ic{display:inline-flex;flex:none}.ic svg{width:100%;height:100%;border-radius:4px}
.filters{display:flex;flex-direction:column;gap:10px;margin-bottom:8px}
.frow{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.frow .lab{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);width:110px}
.chip{font:inherit;font-size:14px;height:36px;padding:0 14px;border-radius:18px;border:1px solid #C9C8C1;background:transparent;color:var(--ink);cursor:pointer}
.chip:hover{border-color:var(--ink)}
.chip.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.day h3{margin-top:40px;padding-bottom:8px;border-bottom:1px solid var(--ink);font-size:13px;letter-spacing:.14em;text-transform:uppercase}
.entry{display:grid;grid-template-columns:240px minmax(0,1fr);gap:8px 32px;padding:24px 0;border-bottom:1px solid var(--line2)}
.meta{display:flex;flex-direction:column;gap:8px;font-size:13px;color:var(--muted)}
.prod{display:flex;align-items:center;gap:8px;font-weight:600;color:var(--ink)}
.badges{display:flex;flex-wrap:wrap;gap:6px}
.badge{padding:2px 8px;border:1px solid var(--muted);color:var(--ink2);border-radius:3px;font-size:12px;font-weight:600}
.badge.ga{border-color:var(--ok);color:var(--ok)}
.badge.pv{border-color:var(--accent);color:var(--accent)}
.badge.dev{border-color:var(--warn);color:var(--warn)}
.badge.lens{border-style:dashed}
.entry h4{font-family:var(--serif);font-size:24px;font-weight:600;line-height:1.22}
.entry h4 a{color:var(--ink);text-decoration:none}
.entry h4 a:hover{text-decoration:underline;text-underline-offset:3px}
.entry p{margin-top:8px;font-size:16px;line-height:1.6;color:var(--ink2);max-width:760px}
.src{margin-top:10px;font-size:13px;color:var(--muted)}
.empty{display:none;padding:32px 0;color:var(--muted);font-size:15px}
.viewcard{border-top:3px solid var(--ink);padding:20px 0 8px;margin-bottom:24px;max-width:820px}
.viewmeta{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);display:flex;gap:10px;align-items:center;margin-bottom:10px}
.viewlens{border:1px dashed var(--muted);padding:2px 8px;border-radius:3px}
.viewtitle{font-family:var(--serif);font-size:28px;font-weight:600;margin-bottom:12px}
.viewcard p{font-size:16px;line-height:1.65;color:var(--ink2);margin-bottom:12px}
.viewsrc{font-size:13px;color:var(--muted);border-top:1px solid var(--line2);padding-top:10px}
.countdown{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-bottom:32px}
.cd{border-top:3px solid var(--ink);padding-top:16px}
.cd.soon{border-top-color:var(--warn)}
.cd .n{font-family:var(--serif);font-size:56px;font-weight:600;line-height:1}
.cd.soon .n{color:var(--warn)}
.cd .n small{font-size:20px;color:var(--muted);font-weight:400}
.cd .p{margin-top:12px;font-weight:600;font-size:17px}
.cd .w{margin-top:4px;font-size:14px;color:var(--muted)}
.icons{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.watch{border-top:1px solid var(--ink)}
.wr{display:grid;grid-template-columns:minmax(0,1fr) 170px 150px 120px;gap:8px 16px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line2);font-size:14px}
.wr .wp{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.wr .wp .icons{margin-top:0}
.wr .ws,.wr .wd{color:var(--muted);font-size:13px}
.wr .pill{justify-self:end;font-size:12px;font-weight:600;padding:2px 8px;border-radius:3px;border:1px solid var(--muted);color:var(--ink2);white-space:nowrap}
.wr .pill.soon{border-color:var(--warn);color:var(--warn)}
.wr .pill.gone{border-style:dashed}
footer{padding-top:40px;font-size:14px;line-height:1.7;color:var(--muted)}
footer b{color:var(--ink)}
footer .srclist{columns:3;margin:8px 0 16px}
footer .srclist a{color:var(--muted)}
footer p{margin-top:8px;max-width:860px}
@media (max-width:760px){
 .wrap{padding:0 16px 60px}
 .entry{grid-template-columns:1fr}
 .wr{grid-template-columns:1fr auto}
 .wr .ws{display:none}
 footer .srclist{columns:1}
 .frow .lab{width:100%}
 .search{width:100%}.search input{width:100%;max-width:none}
}
"""

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
        views_html = ('<section class="block" id="views"><div class="bhead"><h2>Expert views</h2>'
                      '<span class="note">Original analysis by Ankit Samriwal, linked to the official entries it cites. Each view is published with his approval.</span></div>'
                      + ''.join(cards) + '</section>')
        views_nav = '<a href="#views">Expert views</a>'
    else:
        views_html = ''
        views_nav = ''

    edata = json.load(open('data/entries.json'))
    entries = edata['entries']
    eos = json.load(open('data/eos.json'))
    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    fam_counts = Counter(e['family'] for e in entries)
    lens_present = sorted({l for e in entries for l in e['lenses']}, key=lambda l: LENS_ORDER.index(l) if l in LENS_ORDER else 99)
    latest_date = max((e['date'] for e in entries), default='')
    new_latest = sum(1 for e in entries if e['date'] == latest_date)

    # landscape
    maxc = max(fam_counts.values() or [1])
    cards = []
    for fam in FAMILY_ORDER:
        icon, tagline, prods = FAMILY_META[fam]
        n = fam_counts.get(fam, 0)
        prow = ''.join(ic(k, 20) for k in prods if k != icon)
        cards.append(f'''<button class="fam{' zero' if not n else ''}" data-fam="{esc(fam)}" aria-pressed="false" onclick="setFam(this.dataset.fam)">
  {ic(icon, 36)}
  <span class="body"><span class="t">{esc(fam)}</span><span class="d">{esc(tagline)}</span>
  {f'<span class="prods">{prow}</span>' if prow else ''}
  <span class="bar"><span style="width:{round(100 * n / maxc)}%"></span></span></span>
  <span class="c">{n}</span></button>''')

    famchips = '<button class="chip on" data-fam="" onclick="setFam(\'\')">All</button>' + ''.join(
        f'<button class="chip" data-fam="{esc(f)}" onclick="setFam(this.dataset.fam)">{esc(f)}</button>'
        for f in FAMILY_ORDER if fam_counts.get(f))
    lenschips = ''.join(f'<button class="chip" data-lens="{esc(l)}" onclick="setLens(this.dataset.lens)">{esc(l)}</button>' for l in lens_present)

    # chronicle
    days, cur = [], None
    for e in entries:
        if e['date'] != cur:
            cur = e['date']
            d = datetime.strptime(cur, '%Y-%m-%d')
            days.append((cur, d.strftime('%A %-d %B %Y'), []))
        days[-1][2].append(e)
    tl = []
    for _, label, es in days:
        body = []
        for e in es:
            fam = e['family']
            key, pname = match_product(e['title'])
            if not key and e.get('source_id') == 'github_blog':
                key, pname = 'mono-github', 'GitHub'
            prod = f'<span class="prod">{ic(key, 28)}{esc(pname or fam)}</span>'
            famline = f'<span>{esc(fam)}</span>' if pname else ''
            badges = ''
            if e.get('status'):
                badges += f'<span class="badge {status_class(e["status"])}">{esc(e["status"])}</span>'
            badges += ''.join(f'<span class="badge lens">{esc(l)}</span>' for l in e['lenses'][:3])
            body.append(f'''<article class="entry" data-fam="{esc(fam)}" data-lens="{esc('|'.join(e['lenses']))}">
  <div class="meta">{prod}{famline}{f'<span class="badges">{badges}</span>' if badges else ''}</div>
  <div><h4><a href="{esc(e['url'])}">{esc(e['title'])}</a></h4>
  <p>{esc(e['summary'])}</p>
  <div class="src">Source: <a href="{esc(e['url'])}">{esc(e['source'])}</a></div></div>
</article>''')
        tl.append(f'<section class="day"><h3>{esc(label)}</h3>{"".join(body)}</section>')

    # support watch
    upcoming = sorted([r for r in eos['rows'] if r['ts'] >= now_ts], key=lambda r: r['ts'])
    next_days = round((upcoming[0]['ts'] - now_ts) / 86400) if upcoming else None
    cds = []
    for i, r in enumerate(upcoming[:3]):
        dl = round((r['ts'] - now_ts) / 86400)
        icons = ''.join(ic(k, 28) for k, _ in match_all(r['product']))
        cds.append(f'''<div class="cd{' soon' if i == 0 else ''}"><div class="n">{dl}<small> days</small></div>
  <div class="p">{esc(r['product'])}</div>
  <div class="w">{esc(section_label(r['section']))} &middot; {esc(r['date_str'])}</div>
  {f'<div class="icons">{icons}</div>' if icons else ''}</div>''')
    window = sorted([r for r in eos['rows'] if r['ts'] >= now_ts - 30 * 86400], key=lambda r: r['ts'])[:14]
    wrows = []
    for r in window:
        dl = round((r['ts'] - now_ts) / 86400)
        if dl >= 0:
            pill = f'<span class="pill{" soon" if dl <= 45 else ""}">in {dl} days</span>'
        else:
            pill = f'<span class="pill gone">ended {-dl} days ago</span>'
        icons = ''.join(ic(k, 22) for k, _ in match_all(r['product']))
        wrows.append(f'''<div class="wr"><span class="wp">{f'<span class="icons">{icons}</span>' if icons else ''}<span>{esc(r['product'])}</span></span>
  <span class="ws">{esc(section_label(r['section']))}</span>
  <span class="wd">{esc(r['date_str'])}</span>{pill}</div>''')

    srclist = ''.join(f'<div><a href="{esc(u)}">{esc(n)}</a></div>' for n, u in SOURCES)
    gen = edata.get('generated_at', '')
    total = len(entries)
    try:
        today_label = datetime.strptime(latest_date, '%Y-%m-%d').strftime('%a %-d %b %Y')
    except Exception:
        today_label = ''

    stats = (f'<div><div class="n">{total}</div><div class="l">entries this cycle</div></div>'
             f'<div><div class="n">{new_latest}</div><div class="l">new on {esc(today_label)}</div></div>'
             f'<div><div class="n">{sum(1 for f in FAMILY_ORDER if fam_counts.get(f))}</div><div class="l">active product families</div></div>'
             + (f'<div><div class="n warn">{next_days}</div><div class="l">days to next retirement</div></div>' if next_days is not None
                else '<div><div class="n">0</div><div class="l">retirements due</div></div>'))

    sprite = _sprite_defs()
    page = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Microsoft Universe Chronicle</title>
<meta name="description" content="An unofficial daily chronicle of official Microsoft updates: D365, M365, Azure, Copilot, agents, Fabric, Power Platform, security, MAI models, the IQ ecosystem, and end-of-support watch.">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600;6..72,700&amp;family=Public+Sans:wght@400;500;600&amp;display=swap">
<style>{CSS}</style></head>
<body>
{sprite}
<div class="wrap">
<div class="strip"><span>Unofficial chronicle &middot; not affiliated with or endorsed by Microsoft &middot; every entry links to an official Microsoft source</span><span>Refreshed {esc(gen)}</span></div>
<header class="mast"><div class="kicker">All of Microsoft &middot; one chronicle &middot; official sources only</div><h1>Microsoft Universe Chronicle</h1></header>
<nav class="sections" aria-label="Sections">
  <div class="links"><a href="#map">Landscape</a>{views_nav}<a href="#chronicle">Chronicle</a><a href="#support">Support watch</a><a href="#sources">Sources</a></div>
  <div class="search"><label for="q">Search</label><input id="q" type="search" placeholder="Fabric, Entra, retirement&hellip;" autocomplete="off" oninput="setQ(this.value)"></div>
</nav>

<section class="lead">
  <div><h2>Every Microsoft update, in order, in plain language.</h2>
  <p>D365, M365, Azure, Copilot, agents, Fabric, Power Platform, security, MAI models and the IQ ecosystem &mdash; refreshed daily, covering roughly the last 120 days.</p>
  <div class="refresh">Last refreshed {esc(gen)} by automation</div></div>
  <div class="stats">{stats}</div>
</section>

<section class="block" id="map">
  <div class="bhead"><h2>The landscape</h2><span class="note">Select a family to filter the chronicle. Product icons are Microsoft's official architecture icons, shown beside the product they depict (see Sources).</span></div>
  <div class="famgrid">{''.join(cards)}</div>
</section>

{views_html}

<section class="block" id="chronicle">
  <div class="bhead"><h2>The chronicle</h2><span class="note"><span id="shown">{total}</span> of {total} entries</span></div>
  <div class="filters">
    <div class="frow"><span class="lab">Family</span>{famchips}</div>
    <div class="frow"><span class="lab">Practice lens</span>{lenschips}</div>
  </div>
  {''.join(tl)}
  <div class="empty" id="empty">No entries match. Clear the search or filters.</div>
</section>

<section class="block" id="support">
  <div class="bhead"><h2>Support watch</h2><span class="note">End of support and retirements across the Microsoft catalogue, from the Microsoft Learn lifecycle pages. Next milestones first.</span></div>
  <div class="countdown">{''.join(cds)}</div>
  <div class="watch">{''.join(wrows)}</div>
</section>

<footer id="sources">
  <b>Sources</b> &mdash; all official Microsoft, all public, all free:
  <div class="srclist">{srclist}</div>
  <p>Method: a daily automated job reads these feeds and the Microsoft Learn lifecycle pages, classifies each item into a product family and practice lens, and rebuilds this page. Chronicle entries are not editorial opinion; every entry links to its Microsoft source. Expert views, when present, are original analysis by Ankit Samriwal, published with his per-item approval.</p>
  <p>Icons: official Microsoft architecture icon sets (Azure, Dynamics 365, Power Platform, Fabric, Entra), used under Microsoft's icon terms for diagrams and documentation, unmodified, and always beside the product they depict. Products without an official free icon set are shown with original letter tiles. Microsoft product names are trademarks of Microsoft. This is an independent, unofficial chronicle.</p>
  <p>Built and maintained by Instinct for Ankit Samriwal.</p>
</footer>
</div>
<script>
let F='',L='',Q='';
const items=[...document.querySelectorAll('.entry')].map(e=>({{e,t:e.textContent.toLowerCase()}}));
function setFam(f){{F=(F===f)?'':f;paint();if(f)document.getElementById('chronicle').scrollIntoView({{behavior:'smooth'}});}}
function setLens(l){{L=(L===l)?'':l;paint();}}
function setQ(q){{Q=q.trim().toLowerCase();paint();}}
function paint(){{
  document.querySelectorAll('.chip[data-fam]').forEach(c=>c.classList.toggle('on',c.dataset.fam===F));
  document.querySelectorAll('.fam').forEach(c=>{{const on=c.dataset.fam===F;c.classList.toggle('on',on);c.setAttribute('aria-pressed',on);}});
  document.querySelectorAll('.chip[data-lens]').forEach(c=>c.classList.toggle('on',c.dataset.lens===L));
  let n=0;
  items.forEach(({{e,t}})=>{{
    const ok=(!F||e.dataset.fam===F)&&(!L||e.dataset.lens.split('|').includes(L))&&(!Q||t.includes(Q));
    e.style.display=ok?'':'none';if(ok)n++;
  }});
  document.querySelectorAll('.day').forEach(g=>{{
    g.style.display=[...g.querySelectorAll('.entry')].some(e=>e.style.display!=='none')?'':'none';
  }});
  document.getElementById('shown').textContent=n;
  document.getElementById('empty').style.display=n?'none':'block';
}}
</script>
</body></html>'''
    os.makedirs('site', exist_ok=True)
    open('site/index.html', 'w').write(page)
    print(f'site/index.html written: {len(page)} bytes, {len(entries)} entries')

if __name__ == '__main__':
    main()
