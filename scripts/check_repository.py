"""Check publishable layout, relative Markdown links and research data shapes."""
from pathlib import Path
import json
import re
import sys
from datetime import date
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]

CORE_PAPER_IDS = {6, 7, 8, 11, 12, 17, 23, 25, 31, 39, 43, 44, 45, 46}
PRESERVED_SOURCE_IDS = set(range(1, 34)) | set(range(35, 47))


def readme_evidence_errors(body, sources, heading):
    """Keep direct paper evidence visible in README, not only in subdirectories."""
    if heading not in body:
        return ['missing visible paper section']
    section=body.split(heading,1)[1].split('\n## ',1)[0]
    section=re.sub(r'<!--.*?-->', '', section, flags=re.S)
    urls=set(re.findall(r'\[[^\]\n]+\]\((https://[^)\s]+)\)', section))
    catalog={s['id']:s for s in sources}
    return [f'missing direct paper link: source {sid}' for sid in sorted(CORE_PAPER_IDS)
            if sid not in catalog or not urls.intersection(catalog[sid]['urls'])]


def research_checks():
    from materials import read_json, validate
    errors=[]
    sources=read_json(ROOT/'docs/research/sources.json')
    sids={s['id'] for s in sources}
    if len(sids)!=len(sources): errors.append('duplicate research source ID')
    if not PRESERVED_SOURCE_IDS <= sids: errors.append('preserved research sources removed')
    claims=read_json(ROOT/'docs/research/evidence-map.json')['claims']
    experiments=read_json(ROOT/'evals/research-program.json')['experiments']
    cids={c['claim_id'] for c in claims};eids={e['experiment_id'] for e in experiments}
    if len(cids)!=len(claims) or len(eids)!=len(experiments): errors.append('duplicate claim/experiment ID')
    for c in claims:
        if not set(c['source_ids'])<=sids or not set(c['experiment_ids'])<=eids:
            errors.append('broken evidence reference: '+c['claim_id'])
    for e in experiments:
        if not set(e['claim_ids'])<=cids: errors.append('broken experiment claim: '+e['experiment_id'])
    if {(c['claim_id'],e) for c in claims for e in c['experiment_ids']} != {(c,e['experiment_id']) for e in experiments for c in e['claim_ids']}:
        errors.append('asymmetric claim/experiment links')
    for name,heading in [('README.md','## 论文与研究依据'),('README.en.md','## Papers and research foundations')]:
        errors += [name+': '+e for e in readme_evidence_errors((ROOT/name).read_text(encoding='utf8'),sources,heading)]
    # Reproduce examples at their documented creation snapshot; CLI uses today.
    for path in (ROOT/'examples/material-bundles').glob('*/bundle.json'):
        validate(read_json(path),path.parent,date(2026,9,13),ROOT)
    return errors

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
    try: errors.extend(research_checks())
    except (ValueError,OSError,KeyError,TypeError) as exc: errors.append('research checks: '+str(exc))
    return {'ok':not errors,'checked_text_files':len(paths),'errors':errors,'note':'Structural checks are not a semantic secret detector or model quality evaluation.'}

if __name__=='__main__':
    result=check();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
