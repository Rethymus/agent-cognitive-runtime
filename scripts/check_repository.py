"""Check publishable layout, relative Markdown links and research data shapes."""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]

def check():
    errors=[];paths=[]
    for p in ROOT.rglob('*'):
        rel=p.relative_to(ROOT)
        if any(s in {'.git','__pycache__','.venv','work','.acr-state'} for s in rel.parts) or not p.is_file():continue
        if p.suffix in {'.sqlite3','.db','.before','.pyc'}:errors.append('non-publishable state: '+str(rel));continue
        if p.suffix not in {'.md','.json','.jsonl','.py','.yml','.toml','.txt'}:continue
        s=p.read_text(encoding='utf8');paths.append(str(rel))
        if re.search(r'[A-Za-z]:[\\/](?:Users|Codex)[\\/]',s):errors.append('originating-machine reference: '+str(rel))
        if p.suffix=='.md':
            for ref in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)',s):
                ref=ref.split(' "',1)[0].strip('<>')
                if '://' in ref or ref.startswith(('#','mailto:')):continue
                dest=unquote(ref.split('#',1)[0])
                if dest and not (p.parent/dest).exists():errors.append('broken relative link: '+str(rel)+' -> '+ref)
        if p.suffix=='.json':
            try:json.loads(s)
            except ValueError as e:errors.append(str(rel)+': '+str(e))
        if p.suffix=='.jsonl':
            for n,line in enumerate(s.splitlines(),1):
                if line:
                    try:json.loads(line)
                    except ValueError as e:errors.append(f'{rel}:{n}: {e}')
    audit=[json.loads(x) for x in (ROOT/'docs/research/attachment-audit.jsonl').read_text(encoding='utf8').splitlines()]
    if len(audit)!=461 or any('anchor' in x for x in audit):errors.append('attachment audit export changed unexpectedly')
    if (ROOT/'docs/research/Claude-Fable-5.1.md').exists():errors.append('raw attachment included')
    return {'ok':not errors,'checked_text_files':len(paths),'errors':errors,'note':'Structural checks are not a semantic secret detector or model quality evaluation.'}

if __name__=='__main__':
    result=check();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
