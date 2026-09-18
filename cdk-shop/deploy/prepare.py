"""Run once on the authorized VPS; never prints generated secrets."""
from pathlib import Path
import hashlib, ipaddress, json, os, secrets, subprocess, tarfile
import yaml

os.umask(0o077)
root = Path('/opt/taoai-shop')
def run(*args):
    return subprocess.check_output(args, text=True).strip()

assert not (root/'config.yml').exists(), 'Existing shop configuration: stop instead of overwriting'
archive = root/'releases/dujiao-next_v1.4.7_Linux_x86_64.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '4528ffdae52a9ebcc893fdd08f250f59c83b633686414b33a4d9f810459a04f5'
(root/'runtime').mkdir(exist_ok=True)
with tarfile.open(archive) as t:
    for name in ('dujiao-next', 'config.yml.example'):
        (root/'runtime'/name).write_bytes(t.extractfile(name).read())
(root/'runtime/dujiao-next').chmod(0o755)
network = 'taoai_shop_front'
existing = run('docker','network','ls','--format','{{.Name}}').splitlines()
assert network not in existing, 'Unexpected existing shop network'
run('docker','network','create',network)
n = json.loads(run('docker','network','inspect',network))[0]
gateway = n['IPAM']['Config'][0]['Gateway']
proxy_ip = str(ipaddress.ip_address(gateway)+1)
run('docker','network','connect','--ip',proxy_ip,'--gw-priority','-1',network,'gpt-cdk-caddy')
(root/'deploy/proxy.json').write_text(json.dumps({'network':network,'ip':proxy_ip}))

db_password, redis_password = secrets.token_hex(24), secrets.token_hex(24)
admin_name = 'taoai_'+secrets.token_hex(4)
admin_password = 'Tao!'+secrets.token_urlsafe(24)+'9a'
admin_path = '/manage-'+secrets.token_hex(10)
cfg = yaml.safe_load((root/'runtime/config.yml.example').read_text())
cfg['app'].update(secret_key=secrets.token_hex(32),totp_issuer='TaoAi')
cfg['server'].update(mode='release',trusted_proxies=[proxy_ip+'/32'])
cfg['database'] = {'driver':'postgres','dsn':f'host=postgres user=taoai_shop password={db_password} dbname=taoai_shop port=5432 sslmode=disable TimeZone=Asia/Shanghai','pool':{'max_open_conns':15,'max_idle_conns':5,'conn_max_lifetime_seconds':1800,'conn_max_idle_time_seconds':300}}
cfg['jwt'].update(secret=secrets.token_hex(32),expire_hours=4)
cfg['user_jwt']['secret'] = secrets.token_hex(32)
cfg['bootstrap'] = {'default_admin_username':admin_name,'default_admin_password':admin_password}
for name in ('redis','queue'):
    cfg[name].update(host='redis',password=redis_password)
cfg['queue']['concurrency']=3
cfg['email']['enabled']=False
cfg['cors']['allowed_origins']=['https://shop.edujerry.icu']
cfg['reseller'].update(
    enabled=True,
    main_hosts=['shop.edujerry.icu', 'localhost', '127.0.0.1', '::1'],
    trusted_forwarded_host=False,
    subdomain_base='edujerry.icu',
    self_apply_enabled=True,
    settlement_confirm_days=7,
)
cfg['security']['password_policy']['min_length']=12
cfg['upload']['allowed_types'].remove('image/svg+xml')
cfg['upload']['allowed_extensions'].remove('.svg')
cfg['web']['admin_path']=admin_path
(root/'config.yml').write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False))
(root/'config.yml').chmod(0o600)
os.chown(root/'config.yml',10001,10001)
for name in ('uploads','logs','db'):
    p=root/name;p.mkdir(exist_ok=True);p.chmod(0o700);os.chown(p,10001,10001)
(root/'postgres.env').write_text(f'POSTGRES_DB=taoai_shop\nPOSTGRES_USER=taoai_shop\nPOSTGRES_PASSWORD={db_password}\n')
(root/'redis.conf').write_text(f'bind 0.0.0.0\nprotected-mode yes\nport 6379\nrequirepass {redis_password}\nappendonly yes\ndir /data\nmaxmemory 192mb\nmaxmemory-policy noeviction\n')
# Redis must read its configuration after dropping privileges.
(root/'redis.conf').chmod(0o644)
(root/'admin-access.json').write_text(json.dumps({'url':'https://shop.edujerry.icu'+admin_path,'username':admin_name,'password':admin_password},ensure_ascii=False,indent=2))
(root/'runtime/Dockerfile').write_text('FROM alpine@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40\nRUN apk add --no-cache ca-certificates tzdata\nWORKDIR /app\nCOPY --chmod=755 dujiao-next /app/dujiao-next\nUSER 10001:10001\nEXPOSE 8080\nCMD ["/app/dujiao-next"]\n')
logging={'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}
common={'restart':'unless-stopped','logging':logging,'security_opt':['no-new-privileges:true']}
compose={'name':'taoai-shop','services':{
 'app':{**common,'image':'taoai-shop:v1.4.7','build':'./runtime','container_name':'taoai-shop-app','user':'10001:10001','read_only':True,'cap_drop':['ALL'],'tmpfs':['/tmp:rw,noexec,nosuid,size=64m'],'mem_limit':'768m','cpus':1.5,'pids_limit':200,'environment':{'TZ':'Asia/Shanghai'},'volumes':['./config.yml:/app/config.yml:ro','./uploads:/app/uploads','./logs:/app/logs','./db:/app/db'],'networks':{'backend':{},'front':{'aliases':['taoai-shop-app']}},'depends_on':{'postgres':{'condition':'service_healthy'},'redis':{'condition':'service_healthy'}},'healthcheck':{'test':['CMD','wget','-q','-O','/dev/null','http://127.0.0.1:8080/health'],'interval':'20s','timeout':'5s','retries':5,'start_period':'60s'}},
 'postgres':{**common,'image':'postgres@sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b','container_name':'taoai-shop-postgres','env_file':['./postgres.env'],'volumes':['postgres-data:/var/lib/postgresql/data'],'networks':['backend'],'mem_limit':'512m','cpus':1,'healthcheck':{'test':['CMD-SHELL','pg_isready -U taoai_shop -d taoai_shop'],'interval':'10s','timeout':'5s','retries':6}},
 'redis':{**common,'image':'redis@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf','container_name':'taoai-shop-redis','command':['redis-server','/usr/local/etc/redis/redis.conf'],'volumes':['./redis.conf:/usr/local/etc/redis/redis.conf:ro','redis-data:/data'],'networks':['backend'],'mem_limit':'256m','cpus':0.5,'healthcheck':{'test':['CMD-SHELL',"REDISCLI_AUTH=$(awk '/^requirepass / {print $2}' /usr/local/etc/redis/redis.conf) redis-cli ping | grep -q PONG"],'interval':'10s','timeout':'5s','retries':6}}
},'networks':{'backend':{'internal':True},'front':{'external':True,'name':network}},'volumes':{'postgres-data':{},'redis-data':{}}}
(root/'compose.yaml').write_text(yaml.safe_dump(compose,sort_keys=False))
print('Shop configuration created; secrets kept in restricted files; proxy IP:',proxy_ip)
