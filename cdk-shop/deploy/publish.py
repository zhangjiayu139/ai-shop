"""Add only the shop virtual host; validate and reload shared Caddy."""
from pathlib import Path
import json, subprocess, yaml
root=Path('/opt/taoai-shop')
caddy=Path('/opt/gpt-cdk/Caddyfile')
override=Path('/opt/gpt-cdk/compose.override.yaml')
before=caddy.read_bytes();old_override=override.read_bytes()
assert before==(root/'changes/Caddyfile.before').read_bytes(),'Caddy changed concurrently; inspect first'
assert old_override==(root/'changes/compose.override.yaml.before').read_bytes(),'Compose changed concurrently; inspect first'
assert b'shop.edujerry.icu' not in before
block='''
# BEGIN TAOAI-SHOP
shop.edujerry.icu {
    encode zstd gzip
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        X-Frame-Options SAMEORIGIN
        Strict-Transport-Security "max-age=31536000"
        -Server
    }
    @private path /.env* /.git/* /config.yml* /compose.yaml* /logs/* /db/* /deploy/* /admin-access.json
    respond @private 404

    # 开店准备阶段禁止创建真实订单/支付；配置正式库存与支付渠道后移除此段。
    @salesDisabled {
        method POST
        path /api/v1/guest/orders /api/v1/guest/orders/create-and-pay /api/v1/guest/payments /api/v1/guest/payments/* /api/v1/user/orders /api/v1/user/orders/create-and-pay /api/v1/user/payments /api/v1/user/payments/*
    }
    handle @salesDisabled {
        header Content-Type application/json
        respond `{"code":503,"message":"正式库存准备中，暂未开放购买。客服微信：lc07130922"}` 503
    }
    reverse_proxy taoai-shop-app:8080 {
        header_up X-Real-IP {client_ip}
    }
}
# END TAOAI-SHOP
'''
candidate=before+b'\n'+block.encode()
draft=root/'changes/Caddyfile.candidate';draft.write_bytes(candidate)
subprocess.run(['docker','cp',str(draft),'gpt-cdk-caddy:/tmp/taoai-shop.Caddyfile'],check=True)
subprocess.run(['docker','exec','gpt-cdk-caddy','caddy','validate','--config','/tmp/taoai-shop.Caddyfile','--adapter','caddyfile'],check=True)
proxy=json.loads((root/'deploy/proxy.json').read_text())
config=yaml.safe_load(old_override)
config['services']['caddy']['networks'][proxy['network']]={'gw_priority':-1,'ipv4_address':proxy['ip']}
config['networks'][proxy['network']]={'external':True,'name':proxy['network']}
try:
    override.write_text(yaml.safe_dump(config,sort_keys=False))
    subprocess.run(['docker','compose','config','--quiet'],cwd='/opt/gpt-cdk',check=True)
    assert caddy.read_bytes()==before,'Caddy changed concurrently'
    caddy.write_bytes(candidate)
    subprocess.run(['docker','exec','gpt-cdk-caddy','caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'],check=True)
except Exception:
    caddy.write_bytes(before);override.write_bytes(old_override)
    subprocess.run(['docker','exec','gpt-cdk-caddy','caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'],check=False)
    raise
print('Shop route added; Caddy reloaded without container restart; proxy network persisted.')
