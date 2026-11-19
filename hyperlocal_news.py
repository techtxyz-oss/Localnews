#!/usr/bin/env python3
"""Hyperlocal news: Google News RSS se kisi bhi shehar/area ki khabrein laata hai,
trending topics apne aap nikaalta hai aur ek HTML page banata hai.

Sirf Python 3.8+ ki standard library chahiye. Kuch install karne ki zaroorat nahi.

Use:
  python3 hyperlocal_news.py Patna
  python3 hyperlocal_news.py Patna Kankarbagh "Boring Road" --lang hi,en
  python3 hyperlocal_news.py Patna --every 15      # har 15 minute mein refresh
"""
import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

LANGS = {
    "hi": {"hl": "hi", "ceid": "IN:hi", "label": "हिन्दी"},
    "en": {"hl": "en-IN", "ceid": "IN:en", "label": "English"},
}

# Aam shabd jo trending nahi maane jaane chahiye
STOP = set("""
a an the and or of to in on at for by with from is are was were be been as it its this that
these those after before over under into out up down new news live today latest update updates
says say said will would may can could not no yes vs via amid about more than who what when
और का की के को में से पर है हैं था थे थी हो हुआ हुई हुए कर करने किया गया गई गए एक यह ये वह वे
भी तो ही कि जो या न नहीं लिए साथ बाद दिन आज खबर खबरें समाचार ताजा ताज़ा लाइव अपडेट पूरी जानें जानिए
क्या कैसे कब कहां अब फिर सबसे दो तीन चार लोग लोगों मामले मामला
""".split())

TOKEN = re.compile(r"[A-Za-z0-9ऀ-ॣ०-९]+")


def fetch_feed(area, lang, window="1d"):
    cfg = LANGS[lang]
    q = urllib.parse.quote(f"{area} when:{window}")
    url = (f"https://news.google.com/rss/search?q={q}"
           f"&hl={cfg['hl']}&gl=IN&ceid={cfg['ceid']}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        # Google title ka format: "Headline - Source"
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        try:
            when = parsedate_to_datetime(it.findtext("pubDate"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            when = None
        if title and link:
            items.append({"title": title, "link": link, "source": source, "when": when})
    return items


def tokens(text, skip):
    out = []
    for t in TOKEN.findall(text):
        low = t.lower()
        if len(low) < 3 or low in STOP or low in skip or low.isdigit():
            continue
        out.append(low)
    return out


def trending(items, area, top=10):
    """Har headline mein ek shabd/jodi sirf ek baar gini jaati hai.
    Taaza khabar ko zyada wazan milta hai. Kam se kam 2 headline chahiye."""
    skip = set(tokens(area, set())) | {area.lower()}
    now = datetime.now(timezone.utc)
    score, count, where = Counter(), Counter(), {}
    for idx, it in enumerate(items):
        toks = tokens(it["title"], skip)
        terms = set(toks) | {f"{a} {b}" for a, b in zip(toks, toks[1:])}
        age_h = (now - it["when"]).total_seconds() / 3600 if it["when"] else 24
        weight = 2.0 if age_h <= 6 else 1.0
        for term in terms:
            score[term] += weight
            count[term] += 1
            where.setdefault(term, []).append(idx)
    ranked = []
    for term, s in score.most_common():
        if count[term] < 2:
            continue
        # jodi (do shabd) ko pehle rakho agar uski ginti ek shabd jitni hi hai
        ranked.append((term, count[term], s))
    ranked.sort(key=lambda x: (-x[2] - (0.5 if " " in x[0] else 0), x[0]))
    chosen, used = [], set()
    for term, n, s in ranked:
        idxs = frozenset(where[term])
        if idxs in used:  # wahi headlines dobara nahi dikhani
            continue
        used.add(idxs)
        chosen.append({"term": term, "count": n, "items": sorted(idxs)})
        if len(chosen) == top:
            break
    return chosen


def ago(when):
    if not when:
        return ""
    mins = int((datetime.now(timezone.utc) - when).total_seconds() // 60)
    if mins < 1:
        return "अभी / just now"
    if mins < 60:
        return f"{mins} मिनट / min"
    if mins < 1440:
        return f"{mins // 60} घंटे / hr"
    return f"{mins // 1440} दिन / d"


CSS = """
:root{--bg:#f6f5f1;--fg:#1d2321;--mut:#5d6762;--card:#ffffff;--line:#dcdad2;--acc:#0b6b5c;--chip:#e3efec}
@media(prefers-color-scheme:dark){:root{--bg:#121816;--fg:#e8ece9;--mut:#9aa6a0;--card:#1a221f;--line:#2b3631;--acc:#4fd1b8;--chip:#1f2f2b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,"Noto Sans Devanagari",sans-serif;
padding:24px max(16px,env(safe-area-inset-left,0px)) 48px}
main{max-width:860px;margin:0 auto}
h1{font-size:1.6rem;margin:0 0 4px}
h2{font-size:1.2rem;margin:32px 0 4px}
h3{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin:20px 0 8px}
.sub{color:var(--mut);margin:0}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:.92rem}
.chip b{color:var(--acc);margin-left:6px;font-variant-numeric:tabular-nums}
ul.news{list-style:none;margin:0;padding:0;display:grid;gap:8px}
ul.news li{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:0}
ul.news a{color:var(--fg);text-decoration:none;overflow-wrap:anywhere}
ul.news a:hover{color:var(--acc);text-decoration:underline}
.meta{display:block;color:var(--mut);font-size:.82rem;margin-top:2px}
.err{color:#b3261e}
"""


def render(results, interval):
    stamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
    refresh = f'<meta http-equiv="refresh" content="{interval * 60}">' if interval else ""
    parts = [f"<!doctype html><html lang='hi'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Hyperlocal News</title>{refresh}<style>{CSS}</style></head><body><main>"
             f"<h1>Hyperlocal News</h1><p class='sub'>Google News से · अपडेट: {html.escape(stamp)}</p>"]
    for area, per_lang in results.items():
        parts.append(f"<h2>{html.escape(area)}</h2>")
        for lang, (items, err) in per_lang.items():
            parts.append(f"<h3>{LANGS[lang]['label']}</h3>")
            if err:
                parts.append(f"<p class='err'>Feed nahi mili: {html.escape(err)}</p>")
                continue
            if not items:
                parts.append("<p class='sub'>पिछले 24 घंटे में कोई खबर नहीं मिली।</p>")
                continue
            trends = trending(items, area)
            if trends:
                parts.append("<ul class='chips'>" + "".join(
                    f"<li class='chip'>{html.escape(t['term'])}<b>{t['count']}</b></li>" for t in trends) + "</ul>")
            parts.append("<ul class='news' style='margin-top:14px'>")
            for it in sorted(items, key=lambda x: x["when"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:25]:
                parts.append(
                    f"<li><a href='{html.escape(it['link'])}' target='_blank' rel='noopener'>{html.escape(it['title'])}</a>"
                    f"<span class='meta'>{html.escape(it['source'])} · {ago(it['when'])}</span></li>")
            parts.append("</ul>")
    parts.append("</main></body></html>")
    return "".join(parts)


def run_once(areas, langs, out, interval):
    results = {}
    for area in areas:
        results[area] = {}
        for lang in langs:
            try:
                results[area][lang] = (parse_feed(fetch_feed(area, lang)), None)
            except Exception as e:  # network, XML, etc.
                results[area][lang] = ([], str(e))
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(results, interval))
    print(f"[{datetime.now():%H:%M:%S}] {out} update ho gayi")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("areas", nargs="*", default=["Patna"], help="shehar ya area ke naam")
    p.add_argument("--lang", default="hi,en", help="hi, en ya hi,en")
    p.add_argument("--out", default="news.html")
    p.add_argument("--every", type=int, default=0, help="har N minute mein dobara chalao (0 = ek baar)")
    a = p.parse_args()
    langs = [l for l in a.lang.split(",") if l in LANGS]
    if not langs:
        sys.exit("--lang mein hi ya en do")
    while True:
        run_once(a.areas, langs, a.out, a.every)
        if not a.every:
            break
        time.sleep(a.every * 60)


if __name__ == "__main__":
    main()
