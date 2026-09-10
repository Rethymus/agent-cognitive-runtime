"""Install, inspect or roll back the Skill. Python 3.11+, standard library only.

No network calls, model calls or config.toml edits. Default commands are read-only
unless install/rollback is given --apply. Receipts and backups stay outside git.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

REPO=Path(__file__).resolve().parents[1]
SKILL=REPO/'skill'
sys.path.insert(0,str(SKILL/'scripts'))
import subagent_router as router

def digest(data): return hashlib.sha256(data).hexdigest()
def read(path): return path.read_bytes() if path.is_file() else None
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.acr-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream: stream.write(data)
        os.replace(name,path)
    finally:
        if Path(name).exists(): Path(name).unlink()

def target(home,relative):
    p=home/relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('invalid managed path')
    if not p.resolve().is_relative_to(home) or p.resolve().is_relative_to(home/'cognitive-runtime/state'):
        raise ValueError('managed path escapes home or touches state')
    return p

@contextmanager
def locked(home):
    parent=home/'cognitive-runtime/packages';parent.mkdir(parents=True,exist_ok=True)
    lock=parent/'.lock'
    lock.mkdir()  # Refuse a concurrent installer; never remove another process lock.
    try: yield parent
    finally: lock.rmdir()

def activation(home):
    path=home/'AGENTS.md';data=read(path) or b'';s=data.decode('utf-8-sig')
    begin='<!-- ACR:BEGIN -->';end='<!-- ACR:END -->'
    matches=list(re.finditer(re.escape(begin)+'.*?'+re.escape(end),s,re.S))
    if s.count(begin)!=len(matches) or s.count(end)!=len(matches) or len(matches)>1:
        raise ValueError('ambiguous ACR activation markers')
    block=f'''{begin}
复杂、持续或可独立委派的任务，按需读取 `{(home/'skills/agent-cognitive-runtime/SKILL.md').as_posix()}`。
遵守当前用户授权与宿主条件；路由依据证据，未知先查证。经济型子代理只用 xhigh/max，强模型日常 medium/high、攻坚 xhigh/max，读取注册表并显式传参。
委派使用同一目标的任务预算，预约成功才启动；主代理核验范围、真实验收与副作用，决策完成后在已验证检查点交回执行。此 Skill 不切换当前主模型、不控制全局 token 上限。
只保存公开可审计资产，不保存私有思维链；候选经验不自行晋升或改写 Skill。普通问答和单步动作直接完成。
{end}'''
    return ((s[:matches[0].start()]+block+s[matches[0].end():]) if matches else (s+('\n' if s and not s.endswith('\n') else '')+'\n'+block+'\n')).encode('utf8')

def desired(home,with_roles=False,activate=False):
    files={}
    for path in SKILL.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
            files['skills/agent-cognitive-runtime/'+path.relative_to(SKILL).as_posix()]=path.read_bytes()
    if with_roles:
        registry,policy=router.load(SKILL)
        for name,body in router.render(registry,policy).items():files['agents/'+name]=body.encode('utf8')
    if activate: files['AGENTS.md']=activation(home)
    for rel in files:target(home,rel)
    return files

def install(home,apply=False,with_roles=False,activate=False,adopt_existing=False):
    home=Path(home).expanduser().resolve();writes=desired(home,with_roles,activate)
    parent=home/'cognitive-runtime/packages'
    latest=parent/'latest.json';known={}
    if latest.is_file():
        previous=json.loads(latest.read_text(encoding='utf8'))
        known=previous['managed_hashes']
    before={rel:read(target(home,rel)) for rel in writes}
    for rel,current in before.items():
        if rel=='AGENTS.md':continue  # Only the marked block is replaced.
        if current is not None and current!=writes[rel]:
            if rel not in known or digest(current)!=known[rel]:
                if not adopt_existing:raise ValueError('unmanaged or locally modified target: '+rel+'; review before --adopt-existing')
    changed={rel:data for rel,data in writes.items() if data!=before[rel]}
    result={'action':'install','dry_run':not apply,'changed_files':list(changed),'with_roles':with_roles,'activate':activate,'config_toml_modified':False,'state_modified':False,'host_model_availability_verified':False}
    if not apply or not changed:return result
    with locked(home):
        # Recheck every target after acquiring our cooperative installer lock.
        for rel,current in before.items():
            if read(target(home,rel))!=current:raise ValueError('concurrent target change: '+rel)
        key=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        backup=parent/key;backup.mkdir()
        entries=[]
        for index,(rel,data) in enumerate(changed.items()):
            filename=str(index)+'.before' if before[rel] is not None else None
            if filename:atomic(backup/filename,before[rel])
            entries.append({'path':rel,'before_sha256':digest(before[rel]) if before[rel] is not None else None,'after_sha256':digest(data),'backup':filename})
        record={'schema_version':'1.0','home':str(home),'source_checkout':str(REPO),'id':key,'files':entries,'managed_hashes':{**known,**{rel:digest(data) for rel,data in writes.items()}},'previous_latest':json.loads(latest.read_text(encoding='utf8')) if latest.exists() else None}
        atomic(backup/'receipt.json',json.dumps(record,ensure_ascii=False,indent=2).encode('utf8'))
        applied=[]
        try:
            for entry in entries:
                rel=entry['path'];path=target(home,rel)
                if read(path)!=before[rel]:raise ValueError('concurrent target change: '+rel)
                atomic(path,changed[rel]);applied.append(entry)
            atomic(latest,json.dumps(record,ensure_ascii=False,indent=2).encode('utf8'))
        except Exception:
            for entry in reversed(applied):
                path=target(home,entry['path'])
                if read(path)==changed[entry['path']]:
                    if before[entry['path']] is None:path.unlink()
                    else:atomic(path,before[entry['path']])
            raise
        result['receipt_id']=key
    return result

def rollback(home,apply=False):
    home=Path(home).expanduser().resolve();parent=home/'cognitive-runtime/packages';latest=parent/'latest.json'
    record=json.loads(latest.read_text(encoding='utf8'))
    if Path(record['home']).resolve()!=home:raise ValueError('receipt home mismatch')
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}',record['id']):raise ValueError('invalid receipt id')
    backup=parent/record['id'];restores=[];skipped=[]
    for entry in reversed(record['files']):
        path=target(home,entry['path']);current=read(path)
        if current is None or digest(current)!=entry['after_sha256']:skipped.append(entry['path']);continue
        data=None
        if entry['backup']:
            if not re.fullmatch(r'[0-9]+\.before',entry['backup']):raise ValueError('invalid backup path')
            data=(backup/entry['backup']).read_bytes()
            if digest(data)!=entry['before_sha256']:raise ValueError('backup corruption')
        restores.append((path,data,current))
    if apply:
        with locked(home):
            for path,data,current in restores:
                if read(path)!=current:skipped.append(path.relative_to(home).as_posix());continue
                if data is None:path.unlink()
                else:atomic(path,data)
            # Do not silently discard a partial rollback or skip later edits.
            if not skipped:
                if record['previous_latest'] is None:latest.unlink()
                else:atomic(latest,json.dumps(record['previous_latest'],ensure_ascii=False,indent=2).encode('utf8'))
    return {'action':'rollback','dry_run':not apply,'restorable':[p.relative_to(home).as_posix() for p,_,_ in restores],'preserved_modified_or_missing':skipped,'state_modified':False}

def doctor(home):
    home=Path(home).expanduser().resolve();installed=home/'skills/agent-cognitive-runtime'
    checks={'python_compatible':sys.version_info>=(3,11),'skill_installed':(installed/'SKILL.md').is_file(),'source_matches':False,'registry_current':False}
    differences=[];registry_error=None
    if checks['skill_installed']:
        for rel,data in desired(home).items():
            if read(target(home,rel))!=data:differences.append(rel)
        checks['source_matches']=not differences
    try:router.load(installed if checks['skill_installed'] else SKILL);checks['registry_current']=True
    except (ValueError,KeyError,OSError,TypeError) as exc:registry_error=str(exc)
    return {'action':'doctor','checks':checks,'different_files':differences,'registry_error':registry_error,'host_model_availability':'not_probed','global_token_cap':False,'database_contents_read':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['install','doctor','rollback'])
    p.add_argument('--home',default=os.environ.get('CODEX_HOME') or str(Path.home()/'.codex'))
    p.add_argument('--apply',action='store_true');p.add_argument('--with-roles',action='store_true');p.add_argument('--activate',action='store_true');p.add_argument('--adopt-existing',action='store_true')
    a=p.parse_args()
    try:
        if a.action=='install':r=install(a.home,a.apply,a.with_roles,a.activate,a.adopt_existing)
        elif a.action=='rollback':r=rollback(a.home,a.apply)
        else:r=doctor(a.home)
        print(json.dumps({'ok':True,'result':r},ensure_ascii=False,indent=2))
        return 1 if a.action=='doctor' and not all(r['checks'].values()) else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
