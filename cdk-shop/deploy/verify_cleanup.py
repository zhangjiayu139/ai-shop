import json,urllib.request,urllib.parse,re,sys
from pathlib import Path
base='https://shop.edujerry.icu'
def get(path):
 with urllib.request.urlopen(base+path,timeout=30) as r:return r.read()
def snapshot():
 out={}
 for path in ('products','categories','config'):
  obj=json.loads(get('/api/v1/public/'+path));assert obj['status_code']==0
  data=obj['data']
  if path=='config':
   data.pop('server_time',None)
   data.pop('version',None)
   data.pop('app_version',None)
  out[path]=data
 return out
p=Path('/opt/taoai-shop/releases/taoai-clean-20260914/public.before.json')
if sys.argv[1]=='before':
 p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(snapshot(),sort_keys=True));print('Saved current products, categories and storefront configuration')
else:
 before=json.loads(p.read_text())
 before['config'].pop('app_version',None)
 assert before==snapshot(),'Public store data changed'
 assert json.loads(get('/health'))['status']=='ok'
 assert json.loads(get('/api/v1/admin/products'))['status_code']==401
 for slot in ('dashboard_top_banner','dashboard_kpi_card','dashboard_sponsored'):
  assert json.loads(get('/api/v1/admin/ads/render/'+slot))['data']['items']==[]
 for entry,folder in [('/', 'user'),('/manage-5101069e31706a7cefb8/','admin')]:
  html=get(entry).decode();local=Path('/opt/taoai-shop/build/taoai-clean/internal/web/dist')/folder
  expected=re.search(r'<script[^>]*src="([^"]+)"',(local/'index.html').read_text()).group(1)
  actual=re.search(r'<script[^>]*src="([^"]+)"',html).group(1)
  assert expected==actual,(expected,actual)
  js=get(urllib.parse.urljoin(entry,actual)).decode()
  assert 'https://github.com/dujiao-next' not in js
  assert 'Dujiao-Next' not in js
 print('PASS: latest storefront/admin assets; unchanged products/categories/config; health, authentication and disabled ads')
