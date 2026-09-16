"""Replace only the shop application image, with health-gated rollback."""
from pathlib import Path
from datetime import datetime, timezone
import json, shutil, subprocess, time, yaml

root=Path('/opt/taoai-shop')
release=root/'releases/taoai-clean-20260914'
release.mkdir(exist_ok=True)
compose=root/'compose.yaml'
before=compose.read_bytes()
old=yaml.safe_load(before)
old_image=old['services']['app']['image']
new_image='taoai-shop:v1.4.7-taoai-clean-20260914'
assert old_image!=new_image,'Already deployed'
subprocess.run([str(root/'deploy/backup.sh')],check=True)
(release/'compose.before.yaml').write_bytes(before)
baseline=json.loads(subprocess.check_output(['docker','inspect']+subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()))
(release/'containers.before.json').write_text(json.dumps(baseline))
shutil.copy2(root/'runtime/dujiao-next',release/'dujiao-next.before')
shutil.copy2(root/'build/taoai-clean/taoai-shop',root/'runtime/dujiao-next')
(root/'runtime/dujiao-next').chmod(0o755)
subprocess.run(['docker','build','-t',new_image,str(root/'runtime')],check=True)

def healthy():
    for _ in range(60):
        r=subprocess.run(['docker','inspect','taoai-shop-app'],capture_output=True,text=True)
        if r.returncode==0:
            state=json.loads(r.stdout)[0]['State']
            if state.get('Health',{}).get('Status')=='healthy':return True
            if state['Status'] in ('exited','dead'):return False
        time.sleep(1)
    return False

try:
    updated=yaml.safe_load(before)
    updated['services']['app']['image']=new_image
    assert compose.read_bytes()==before,'Compose changed concurrently'
    compose.write_text(yaml.safe_dump(updated,sort_keys=False))
    subprocess.run(['docker','compose','config','--quiet'],cwd=root,check=True)
    subprocess.run(['docker','compose','up','-d','--no-deps','app'],cwd=root,check=True)
    assert healthy(),'New image health check failed'
except Exception:
    compose.write_bytes(before)
    shutil.copy2(release/'dujiao-next.before',root/'runtime/dujiao-next')
    subprocess.run(['docker','compose','up','-d','--no-deps','app'],cwd=root,check=True)
    assert healthy(),'Rollback health check failed'
    raise
for previous in baseline:
    if previous['Name']=='/taoai-shop-app':continue
    current=json.loads(subprocess.check_output(['docker','inspect',previous['Name']]))[0]
    assert (current['Id'],current['State']['StartedAt'],current['RestartCount'])==(previous['Id'],previous['State']['StartedAt'],previous['RestartCount'])
print('TaoAi clean image deployed and healthy; all other containers unchanged.')
