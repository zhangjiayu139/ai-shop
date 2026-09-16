"""Disable only dashboard advertising at the shop reverse proxy."""
from pathlib import Path
from datetime import datetime, timezone
import subprocess

root=Path('/opt/taoai-shop')
path=Path('/opt/gpt-cdk/Caddyfile')
before=path.read_bytes()
text=before.decode()
start=text.index('# BEGIN TAOAI-SHOP')
end=text.index('# END TAOAI-SHOP',start)
shop=text[start:end]
assert '# BEGIN TAOAI-NO-ADS' not in shop, 'Already configured'
anchor='    reverse_proxy taoai-shop-app:8080 {'
assert shop.count(anchor)==1
block='''    # BEGIN TAOAI-NO-ADS
    # Empty ad data keeps DashboardAd hidden and prevents upstream ad requests.
    @dashboardAds path /api/v1/admin/ads/render/* /api/v1/admin/ads/impression
    handle @dashboardAds {
        header Content-Type application/json
        header Cache-Control no-store
        respond `{"status_code":0,"msg":"success","data":{"items":[]}}` 200
    }
    # END TAOAI-NO-ADS

'''
candidate=(text[:start]+shop.replace(anchor,block+anchor,1)+text[end:]).encode()
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=root/'changes'/('Caddyfile.before-no-ads-'+stamp)
backup.write_bytes(before)
draft=root/'changes/Caddyfile.no-ads.candidate'
draft.write_bytes(candidate)
subprocess.run(['docker','cp',str(draft),'gpt-cdk-caddy:/tmp/taoai-no-ads.Caddyfile'],check=True)
subprocess.run(['docker','exec','gpt-cdk-caddy','caddy','validate','--config','/tmp/taoai-no-ads.Caddyfile','--adapter','caddyfile'],check=True)
assert path.read_bytes()==before,'Caddy changed concurrently'
try:
    path.write_bytes(candidate)
    subprocess.run(['docker','exec','gpt-cdk-caddy','caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'],check=True)
except Exception:
    path.write_bytes(before)
    subprocess.run(['docker','exec','gpt-cdk-caddy','caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'],check=True)
    raise
print('Dashboard ad render and impression endpoints disabled for shop host only.')
