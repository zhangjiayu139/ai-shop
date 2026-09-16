from pathlib import Path
import subprocess, time
root=Path('/opt/taoai-shop')
backup=sorted((root/'backups').iterdir())[-1]
name='taoai-shop-restore-check'
subprocess.run(['docker','run','-d','--name',name,'--network','none','--memory','256m','--tmpfs','/var/lib/postgresql/data:rw,size=256m','-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres@sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b'],check=True,stdout=subprocess.DEVNULL)
try:
    # The initialization server only exposes a Unix socket. Wait for final TCP listener.
    for i in range(30):
        r=subprocess.run(['docker','exec',name,'pg_isready','-h','127.0.0.1','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if r.returncode==0:break
        time.sleep(1)
    else:raise RuntimeError('Restore database failed to become ready')
    subprocess.run(['docker','exec',name,'createdb','-U','postgres','restore_check'],check=True)
    with (backup/'database.dump').open('rb') as f:
        subprocess.run(['docker','exec','-i',name,'pg_restore','-U','postgres','-d','restore_check','--no-owner','--no-acl','--exit-on-error'],stdin=f,check=True,stdout=subprocess.DEVNULL)
    q="SELECT 'products='||count(*) FROM products UNION ALL SELECT 'test_cards='||count(*) FROM card_secrets UNION ALL SELECT 'orders='||count(*) FROM orders;"
    r=subprocess.check_output(['docker','exec',name,'psql','-U','postgres','-d','restore_check','-Atc',q],text=True)
    assert 'products=2' in r and 'test_cards=10' in r and 'orders=0' in r,r
    (root/'changes/restore-verification.txt').write_text('Isolated PostgreSQL restore successful\n'+r)
    print('Isolated backup restore PASS:',r.replace('\n','; '))
finally:
    subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,check=True)
