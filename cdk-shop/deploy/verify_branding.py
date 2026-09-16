from pathlib import Path
import json, re, urllib.request, urllib.parse
root=Path(__file__).resolve().parents[1]
base="https://shop.edujerry.icu"
access=json.loads((root/".private/admin-access.json").read_text())
def get(url):
    with urllib.request.urlopen(url,timeout=30) as r:return r.read()
url=access["url"].rstrip("/")+"/"
html=get(url).decode()
assert "<title>TaoAi Admin</title>" in html
script=re.search(r'<script[^>]*src="([^"]+)"',html).group(1)
js=get(urllib.parse.urljoin(url,script)).decode()
for label in ("TaoAi Admin","TaoAi Admin 控制台","TaoAi Admin 后台"):
    assert label in js,label
assert "Dujiao-Next Admin" not in js
print("Live administrator title and brand labels PASS")
for slot in ("dashboard_top_banner","dashboard_kpi_card","dashboard_sponsored"):
    d=json.loads(get(base+"/api/v1/admin/ads/render/"+slot))
    assert d["data"]["items"]==[]
print("Dashboard advertisements remain disabled PASS")
d=json.loads(get(base+"/api/v1/public/products/chatgpt-plus-1-month"))
assert d["status_code"]==0 and float(d["data"]["price_amount"])==139
assert d["data"]["content"]["zh-CN"].count("收取官方实际退款金额的20%作为手续费")==3
assert json.loads(get(base+"/health"))["status"]=="ok"
assert json.loads(get(base+"/api/v1/admin/products"))["status_code"]==401
print("Product, health and authentication PASS")
