#!/usr/bin/env python3
"""Datasheets.com - ozel gelistirme onizlemesi."""
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

API = "https://www.datasheets.com/api/v1/search"

def search_parts(query):
    key = os.environ.get("DATASHEETS_API_KEY")
    if not key:
        raise ValueError("API anahtari bulunamadi")

    params = urllib.parse.urlencode({
        "q": query,
        "limit": 5,
        "page": 1
    })

    request = urllib.request.Request(
        API + "?" + params,
        headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "User-Agent": "ElektronikAkademi/3.8"
        }
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)

def esc(value):
    return html.escape(str(value or ""), quote=True)


def safe_link(value):
    url = str(value or "")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        return ""
    if parsed.hostname not in (
        "datasheets.com",
        "www.datasheets.com",
        "static.datasheets.com"
    ):
        return ""
    return url

def render_part(item):
    mpn = esc(item.get("mpn"))
    manufacturer = esc(item.get("manufacturer"))
    title = esc(item.get("title"))
    package = esc(item.get("packageType"))
    lifecycle = str(item.get("lifecycleStatus") or "")

    status = (
        "Uretimden kaldirilmis"
        if lifecycle.lower() == "obsolete"
        else esc(lifecycle)
    )

    result = [
        "<article>",
        f"<h3>{mpn}</h3>",
        f"<p><b>Uretici:</b> {manufacturer}</p>",
        f"<p>{title}</p>",
        f"<p><b>Kilif:</b> {package}</p>",
        f"<p><b>Urun durumu:</b> {status}</p>"
    ]

    image = safe_link(item.get("primaryImageUrl"))
    if image:
        result.append(
            f'<img src="{esc(image)}" alt="{mpn} gorseli" '
            'style="max-width:150px;max-height:110px;'
            'object-fit:contain" loading="lazy">'
        )

    specs = item.get("specs")
    if isinstance(specs, list):
        result.append("<h4>Teknik ozellikler</h4><dl>")
        for spec in specs[:12]:
            if not isinstance(spec, dict):
                continue
            name = esc(spec.get("name"))
            value = esc(spec.get("value"))
            result.append(
                f"<dt>{name}</dt><dd>{value}</dd>"
            )
        result.append("</dl>")

    pdf = safe_link(item.get("datasheetUrl"))
    if pdf:
        result.append(
            f'<p><a href="{esc(pdf)}" target="_blank" '
            'rel="noopener noreferrer">'
            'Teknik veri sayfasini (PDF) ac</a></p>'
        )

    product = safe_link(item.get("url"))
    if product:
        result.append(
            f'<p><a href="{esc(product)}" target="_blank" '
            'rel="noopener noreferrer">'
            'Datasheets.com uzerinde incele</a></p>'
        )

    result.append("</article>")
    return "".join(result)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path != "/":
            self.send_error(404)
            return

        query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
        query = query.strip()[:80]

        content = []

        if query:
            try:
                data = search_parts(query)
                for item in data.get("results", []):
                    if not isinstance(item, dict):
                        continue

                    url = str(item.get("url") or "")
                    target = urllib.parse.urlsplit(url)

                    if target.scheme != "https" or target.hostname not in (
                        "datasheets.com", "www.datasheets.com"
                    ):
                        continue

                    content.append(render_part(item))

                if not content:
                    content.append("<p>Sonuc bulunamadi.</p>")

            except urllib.error.HTTPError as error:
                content.append(
                    f"<p>API HTTP hatasi: {error.code}</p>"
                )
            except Exception:
                content.append(
                    "<p>API baglantisi basarisiz.</p>"
                )

        page = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Elektronik Akademi - Bilesen Arama</title>
<style>
body{font-family:Arial,sans-serif;max-width:850px;
margin:40px auto;padding:0 20px;background:#f6f8fb;color:#17263b}
h1{color:#123a66}
form{display:flex;gap:10px;margin:25px 0}
input{flex:1;padding:13px;border:1px solid #bbc8d8;
border-radius:7px;font-size:16px;min-width:0}
button{padding:12px 22px;background:#1764ac;color:white;
border:0;border-radius:7px;cursor:pointer}
article{background:white;border:1px solid #dde5ef;
border-radius:10px;padding:18px;margin:12px 0}
article h3{margin-top:0}dt{font-weight:bold;margin-top:9px}dd{margin:3px 0 8px 12px;color:#40536b}
a{color:#1764ac}
small{color:#626e7e}
</style></head><body>
<h1>Elektronik Akademi</h1>
<h2>Elektronik Bilesen Arama</h2>
<form method="get">
<input name="q" maxlength="80" placeholder="NE555, BAV99, LM358..."
value="QUERY" required>
<button type="submit">Ara</button>
</form>
RESULTS
<p><small>Veri kaynagi: Datasheets.com.
Bu ekran yalnizca ozel gelistirme testi icindir.</small></p>
</body></html>"""

        page = page.replace("QUERY", esc(query))
        page = page.replace("RESULTS", "\n".join(content))
        body = page.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print("Elektronik Akademi Datasheets onizlemesi")
    print("Port: 8766 - Codespaces'te PRIVATE tutun")
    HTTPServer(("0.0.0.0", 8766), Handler).serve_forever()
