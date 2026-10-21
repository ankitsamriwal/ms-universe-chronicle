#!/usr/bin/env python3
"""Daily ingestion for Microsoft Universe Chronicle. Stdlib only, free official sources.
Fetches Microsoft RSS feeds + Microsoft Learn lifecycle pages + microsoft.ai news,
writes data/entries.json and data/eos.json. A failed source never kills the run;
previously collected entries persist across runs (120-day window)."""
import json, os, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
      'Accept': 'application/rss+xml,application/xml;q=0.9,text/html;q=0.8'}

FEEDS = [
    ('m365_roadmap', 'Microsoft 365 roadmap', 'https://www.microsoft.com/releasecommunications/api/v2/m365/rss'),
    ('azure_updates', 'Azure updates', 'https://www.microsoft.com/releasecommunications/api/v2/azure/rss'),
    ('azure_blog', 'Azure blog', 'https://azure.microsoft.com/en-us/blog/feed/'),
    ('fabric_blog', 'Fabric updates blog', 'https://blog.fabric.microsoft.com/en-us/blog/feed/'),
    ('powerplatform_blog', 'Power Platform blog', 'https://www.microsoft.com/en-us/power-platform/blog/feed/'),
    ('d365_blog', 'Dynamics 365 blog', 'https://www.microsoft.com/en-us/dynamics-365/blog/feed/'),
    ('security_blog', 'Microsoft Security blog', 'https://www.microsoft.com/en-us/security/blog/feed/'),
    ('foundry_blog', 'Microsoft Foundry blog', 'https://devblogs.microsoft.com/foundry/feed/'),
    ('devblogs', 'Microsoft DevBlogs', 'https://devblogs.microsoft.com/feed/'),
    ('github_blog', 'GitHub blog', 'https://github.blog/feed/'),
    ('windows_blog', 'Windows blog', 'https://blogs.windows.com/feed/'),
]

SOURCE_FAMILY = {'azure_updates': 'Azure', 'azure_blog': 'Azure', 'fabric_blog': 'Power Platform & Fabric',
                 'powerplatform_blog': 'Power Platform & Fabric', 'd365_blog': 'Business Apps (D365)',
                 'security_blog': 'Security & Identity', 'mai_news': 'AI & Copilot',
                 'foundry_blog': 'AI & Copilot', 'devblogs': 'Developer', 'github_blog': 'Developer',
                 'windows_blog': 'Windows & Devices', 'm365_roadmap': 'Modern Work'}

ROADMAP_MAP = [
    (r'Dynamics 365|Business Central|Customer Service|Field Service|Project Operations|Finance|Supply Chain|Sales\b', 'Business Apps (D365)'),
    (r'Power Platform|Power BI|Power Apps|Power Automate|Power Pages|Dataverse|Copilot Studio|Fabric', 'Power Platform & Fabric'),
    (r'Purview|Intune|Entra|Defender|Sentinel|Security', 'Security & Identity'),
    (r'Copilot|Agents|Agent 365', 'AI & Copilot'),
    (r'SharePoint|Teams|Exchange|OneDrive|Viva|Outlook|Word|Excel|PowerPoint|Edge|Office|Microsoft 365', 'Modern Work'),
    (r'Windows', 'Windows & Devices'),
]

LENSES = [
    ('AIOps', r'\b(monitor|observability|intraday|anomal|operations|incident|alert)\b'),
    ('MLOps', r'\b(MLOps|model training|fine-tun|evaluation|grader|benchmark|model router)\b'),
    ('FinOps', r'\b(FinOps|cost management|billing|pricing|reservation|savings plan|consumption)\b'),
    ('DevSecOps', r'\b(DevOps|pipeline|CI/CD|GitHub Actions|supply chain|dependabot)\b'),
    ('Security happenings', r'\b(vulnerabilit|CVE-|threat|defender|sentinel|phishing|zero.?day|security)\b'),
    ('Agents', r'\b(agent|agentic|copilot)\b'),
    ('MAI models', r'\bMAI[- ]'),
]

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def clean(html_text, limit=260):
    t = re.sub(r'<[^>]+>', ' ', html_text or '')
    t = re.sub(r'\.([A-Z])', r'. \1', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > limit:
        t = t[:limit].rsplit(' ', 1)[0] + '...'
    return t

def classify(source, title, cats):
    if source == 'm365_roadmap':
        blob = ' '.join(cats) + ' ' + title
        for pat, fam in ROADMAP_MAP:
            if re.search(pat, blob, re.I):
                return fam
        return 'Modern Work'
    fam = SOURCE_FAMILY.get(source, 'Modern Work')
    if fam == 'Azure':
        blob = ' '.join(cats) + ' ' + title
        if re.search(r'Entra|Defender|Sentinel|Security|Confidential', blob, re.I):
            return 'Security & Identity'
        if re.search(r'Copilot|AI Foundry|OpenAI|Machine Learning', blob, re.I):
            return 'AI & Copilot'
    return fam

def lenses_for(source, title, summary):
    out = set()
    blob = title + ' ' + summary
    for name, pat in LENSES:
        if re.search(pat, blob, re.I):
            out.add(name)
    if source == 'security_blog':
        out.add('Security happenings')
    if source == 'mai_news':
        out.add('MAI models')
    return sorted(out)

def parse_dt(s):
    try:
        dt = parsedate_to_datetime(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def entry(dt, title, link, source_label, source_id, cats, summary, status=''):
    return {'date': dt.strftime('%Y-%m-%d'), 'ts': int(dt.timestamp()), 'title': title, 'url': link,
            'source': source_label, 'source_id': source_id, 'family': classify(source_id, title, cats),
            'lenses': lenses_for(source_id, title, summary), 'summary': summary, 'status': status, 'tags': cats[:8]}

def ingest_feeds(cutoff):
    entries, seen, seen_title = {}, set(), set()
    for source, label, url in FEEDS:
        try:
            root = ET.fromstring(fetch(url))
            n = 0
            for it in root.findall('.//item'):
                link = (it.findtext('link') or '').strip()
                title = re.sub(r'\s+', ' ', (it.findtext('title') or '')).strip()
                norm = re.sub(r'^\[(Launched|In preview|In development|Announcing)\]\s*', '', title, flags=re.I).lower()
                norm = re.sub(r'\s*\((gcc|dod|gcch|gcc high|worldwide).*$', '', norm, flags=re.I).strip()
                if not link or not title or link in seen or norm in seen_title:
                    continue
                dt = parse_dt(it.findtext('pubDate') or '')
                if not dt or dt.timestamp() < cutoff:
                    continue
                seen.add(link); seen_title.add(norm)
                cats = [c.text for c in it.findall('category') if c.text]
                desc = re.sub(r'The post .* appeared first on .*$', '', it.findtext('description') or '')
                status = next((c for c in cats if c in ('Launched', 'In preview', 'In development', 'General Availability')), '')
                entries[link] = entry(dt, title, link, label, source, cats, clean(desc), status)
                n += 1
            print(f'OK  {label}: {n} items', flush=True)
        except Exception as e:
            print(f'FAIL {label}: {e}', flush=True)
    return entries

def ingest_mai(cutoff):
    out = {}
    try:
        raw = fetch('https://microsoft.ai/news/').decode('utf-8', 'replace')
        cards = re.findall(r'aria-label="([^"]+)"\s+href="(https://microsoft\.ai/(?:[a-z0-9-]+/)+)"', raw)
        cards += [(t, u) for u, t in re.findall(r'href="(https://microsoft\.ai/(?:[a-z0-9-]+/)+)"[^>]*\s+aria-label="([^"]+)"', raw)]
        uniq, seen = [], set()
        for t, u in cards:
            if u not in seen:
                seen.add(u); uniq.append((t, u))
        for title, link in uniq[:14]:
            try:
                page = fetch(link).decode('utf-8', 'replace')
                m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', page)
                if not m:
                    continue
                dt = datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
                if dt.timestamp() < cutoff:
                    continue
                md = re.search(r'<meta name="description" content="([^"]+)"', page)
                out[link] = entry(dt, title, link, 'Microsoft AI news', 'mai_news', [], clean(md.group(1) if md else ''))
            except Exception:
                continue
        print(f'OK  Microsoft AI news: {len(out)} posts', flush=True)
    except Exception as e:
        print(f'FAIL Microsoft AI news: {e}', flush=True)
    return out

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section, self.rows, self._cell, self._row, self._stack = '', [], None, None, []
    def handle_starttag(self, tag, attrs):
        self._stack.append(tag)
        if tag == 'h2':
            self.section = ''
        if tag == 'tr':
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = ''
        elif tag in ('br', 'li', 'p', 'div') and self._cell is not None:
            self._cell += ' ; '
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None:
            cell = re.sub(r'\s*;\s*', ' · ', self._cell)
            self._row.append(re.sub(r'[ ]+', ' ', cell).strip(' ·')); self._cell = None
        elif tag == 'tr' and self._row is not None:
            if len(self._row) >= 2:
                self.rows.append((self.section, self._row))
            self._row = None
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data
        elif self._stack and self._stack[-1] == 'h2':
            self.section += data

MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'

def ingest_eos():
    rows_out = []
    for year in (datetime.now().year, datetime.now().year + 1):
        url = f'https://learn.microsoft.com/en-us/lifecycle/end-of-support/end-of-support-{year}'
        try:
            p = TableParser()
            p.feed(fetch(url).decode('utf-8', 'replace'))
            n = 0
            for section, row in p.rows:
                product, datestr = row[0], row[1]
                m = re.search(rf'({MONTHS})\s+\d{{1,2}},\s+\d{{4}}', datestr)
                if not product or not m:
                    continue
                try:
                    d = datetime.strptime(m.group(0), '%B %d, %Y').replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                rows_out.append({'section': section or 'Lifecycle', 'product': product,
                                 'date': d.strftime('%Y-%m-%d'), 'date_str': m.group(0), 'ts': int(d.timestamp())})
                n += 1
            print(f'OK  lifecycle {year}: {n} rows', flush=True)
        except Exception as e:
            print(f'FAIL lifecycle {year}: {e}', flush=True)
    return rows_out

if __name__ == '__main__':
    cutoff = datetime.now(timezone.utc).timestamp() - 120 * 86400
    entries = ingest_feeds(cutoff)
    entries.update(ingest_mai(cutoff))
    result = sorted(entries.values(), key=lambda e: -e['ts'])
    try:
        old = json.load(open('data/entries.json'))['entries'] if os.path.exists('data/entries.json') else []
        known = {e['url'] for e in result}
        keep = [e for e in old if e['url'] not in known and e.get('ts', 0) >= cutoff]
        result = sorted(result + keep, key=lambda e: -e['ts'])
        print(f'Persisted {len(keep)} earlier entries', flush=True)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    from collections import defaultdict
    caps = {'m365_roadmap': 120, 'azure_updates': 80}
    by_src = defaultdict(list)
    for e in result:
        by_src[e['source_id']].append(e)
    capped = []
    for sid, lst in by_src.items():
        lst.sort(key=lambda e: -e['ts'])
        capped += lst[:caps.get(sid, 15)]
    result = sorted(capped, key=lambda e: -e['ts'])
    eos = ingest_eos()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    os.makedirs('data', exist_ok=True)
    json.dump({'generated_at': now, 'entries': result}, open('data/entries.json', 'w'), indent=1)
    json.dump({'generated_at': now, 'rows': eos}, open('data/eos.json', 'w'), indent=1)
    print(f'Wrote {len(result)} entries, {len(eos)} lifecycle rows at {now}', flush=True)
