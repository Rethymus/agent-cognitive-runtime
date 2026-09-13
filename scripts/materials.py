"""Validate untrusted maintenance bundles and plan reviews; never apply or promote.

Standard library only. The bundled JSON Schema uses the explicitly supported
subset in validate_schema; this is not a general JSON Schema implementation.
"""
from pathlib import Path, PurePosixPath, PureWindowsPath
from datetime import date
from urllib.parse import urlsplit
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000
TARGETS = {
    'research': ['docs/research/sources.json', 'docs/research/evidence-map.json', 'README.md', 'README.en.md'],
    'model_binding': ['skill/policies/model-registry.json'],
    'routing': ['skill/policies/adaptive-routing.json', 'skill/policies/subagent-policy.json'],
    'memory': ['skill/scripts/runtime.py', 'skill/references/local-runtime.md'],
    'skill': ['skill/SKILL.md', 'skill/references/maintaining-subagents.md'],
    'evaluation': ['evals/research-program.json'],
}


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, 'JSON exceeds size limit')
    return decode_json(raw)


def decode_json(raw):
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid('non-finite JSON number')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Invalid(str(exc)) from exc


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_schema(value, spec, root, where='$'):
    """Enforce the local schema's types, refs, enums, bounds and closed objects."""
    if '$ref' in spec:
        spec = root['$defs'][spec['$ref'].removeprefix('#/$defs/')]
    types = spec.get('type', [])
    types = [types] if isinstance(types, str) else types
    mapping = {'object': dict, 'array': list, 'string': str, 'integer': int,
               'boolean': bool, 'null': type(None)}
    require(not types or any(type(value) is mapping[t] for t in types), where + ': invalid type')
    if 'enum' in spec:
        require(value in spec['enum'], where + ': invalid enum')
    if value is None:
        return
    if isinstance(value, dict):
        require(set(spec.get('required', [])) <= value.keys(), where + ': missing required fields')
        props = spec.get('properties', {})
        if spec.get('additionalProperties') is False:
            require(value.keys() <= props.keys(), where + ': unknown fields')
        for key, item in value.items():
            if key in props:
                validate_schema(item, props[key], root, where + '.' + key)
    elif isinstance(value, list):
        require(spec.get('minItems', 0) <= len(value) <= spec.get('maxItems', 1000), where + ': array size')
        if spec.get('uniqueItems'):
            require(len({digest(x) for x in value}) == len(value), where + ': duplicate values')
        for i, item in enumerate(value):
            validate_schema(item, spec.get('items', {}), root, where + f'[{i}]')
    elif isinstance(value, str):
        require(spec.get('minLength', 0) <= len(value) <= spec.get('maxLength', 4000), where + ': string size')
        if 'pattern' in spec:
            require(re.search(spec['pattern'], value), where + ': pattern mismatch')
        if spec.get('format') == 'date':
            require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), where + ': invalid date format')
            date.fromisoformat(value)
    elif type(value) is int:
        require(value >= spec.get('minimum', value), where + ': below minimum')


def artifact_bytes(base, artifact):
    name = artifact['path']
    require('\\' not in name and ':' not in name and not PureWindowsPath(name).drive,
            'artifact must use a relative POSIX path')
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and '..' not in rel.parts, 'artifact path escapes bundle')
    base = base.resolve()
    path = (base / name).resolve()
    require(path.is_relative_to(base), 'artifact symlink escapes bundle')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, 'artifact exceeds size limit; use a small manifest instead')
    actual = hashlib.sha256(data).hexdigest()
    require(actual == artifact['sha256'], 'artifact hash mismatch: ' + name)
    return data


def check_dataset_manifest(raw, declaration, repo):
    manifest = decode_json(raw)
    schema = read_json(repo / 'schemas/dataset-manifest.schema.json')
    validate_schema(manifest, schema, schema)
    rows = manifest['examples']
    require(len({r['example_id'] for r in rows}) == len(rows), 'duplicate dataset example ID')
    if declaration['record_count'] is not None:
        require(len(rows) == declaration['record_count'], 'dataset count disagrees with manifest')
    splits = {r['split'] for r in rows}
    declared = declaration['split']
    if declared in {'train', 'calibration', 'holdout'}:
        require(splits == {declared}, 'dataset split disagrees with manifest')
    if declared == 'partitioned':
        require(len(splits) > 1, 'partitioned dataset needs multiple splits')
    for key in ['content_sha256', 'group_id']:
        seen = {}
        for row in rows:
            require(row[key] not in seen or seen[row[key]] == row['split'],
                    'cross-split overlap: ' + key)
            seen[row[key]] = row['split']


def closure(materials, initial):
    result, pending = set(), list(initial)
    while pending:
        item = pending.pop()
        if item not in result:
            require(item in materials, 'unknown material: ' + item)
            result.add(item)
            pending.extend(materials[item]['depends_on'])
    return result


def validate(bundle, base, as_of, repo=ROOT, verify_artifacts=True):
    schema = read_json(repo / 'schemas/material-bundle.schema.json')
    validate_schema(bundle, schema, schema)
    require(date.fromisoformat(bundle['created_on']) <= as_of, 'bundle creation is in the future')
    materials = {m['id']: m for m in bundle['materials']}
    require(len(materials) == len(bundle['materials']), 'duplicate material ID')
    changes = {c['id']: c for c in bundle['changes']}
    require(len(changes) == len(bundle['changes']), 'duplicate change ID')
    source_ids = {s['id'] for s in read_json(repo / 'docs/research/sources.json')}
    claim_ids = {c['claim_id'] for c in read_json(repo / 'docs/research/evidence-map.json')['claims']}
    eval_ids = {e['experiment_id'] for e in read_json(repo / 'evals/research-program.json')['experiments']}
    for m in materials.values():
        parsed = urlsplit(m['source_url'])
        require(parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password,
                m['id'] + ': source must be HTTPS without credentials (never fetched by this tool)')
        require(m['catalog_source_id'] is None or m['catalog_source_id'] in source_ids, 'unknown catalog source')
        require(set(m['depends_on']) <= materials.keys(), 'unknown material dependency')
        require(m['id'] not in m['depends_on'], 'self dependency')
        if m['reviewed_on']:
            reviewed = date.fromisoformat(m['reviewed_on'])
            require(reviewed <= as_of, 'review date is in the future')
            if m['review_after']:
                require(date.fromisoformat(m['review_after']) >= reviewed, 'review expiry precedes review')
        if m['review_status'] == 'reviewed':
            require(m['reviewed_on'] is not None, 'reviewed material needs review date')
        require((m['kind'] == 'dataset') == (m['dataset'] is not None), 'dataset metadata required only for datasets')
        if m['artifact'] and verify_artifacts:
            raw = artifact_bytes(base, m['artifact'])
            if m['kind'] == 'dataset':
                check_dataset_manifest(raw, m['dataset'], repo)
    visiting, visited = set(), set()
    def visit(mid):
        require(mid not in visiting, 'material dependency cycle')
        if mid in visited:
            return
        visiting.add(mid)
        for dep in materials[mid]['depends_on']:
            visit(dep)
        visiting.remove(mid)
        visited.add(mid)
    for mid in materials:
        visit(mid)
    for c in changes.values():
        require(set(c['material_ids']) <= materials.keys(), 'unknown change material')
        require(set(c['claim_ids']) <= claim_ids, 'unknown claim ID; update evidence map first')
        require(set(c['evaluation_ids']) <= eval_ids, 'unknown evaluation ID; define experiment first')
        require((c['target'] == 'model_binding') == (c['model'] is not None), 'model declaration required only for model binding')
        if c['model']:
            evidence = c['model']['host_evidence_id']
            if evidence is not None:
                require(evidence in closure(materials, c['material_ids']), 'host evidence outside change dependencies')
                require(materials[evidence]['kind'] == 'host_observation', 'host evidence is not a host observation')
    return materials


def plan(bundle, base, as_of, repo=ROOT):
    materials = validate(bundle, base, as_of, repo)
    registry = read_json(repo / 'skill/policies/model-registry.json')
    result = []
    for c in bundle['changes']:
        mids = sorted(closure(materials, c['material_ids']))
        gaps = []
        if c['target'] in {'model_binding', 'routing'} and date.fromisoformat(registry['review_after']) <= as_of:
            gaps.append('baseline:registry_review_expired')
        for mid in mids:
            m = materials[mid]
            def gap(code): gaps.append(mid + ':' + code)
            if m['review_status'] != 'reviewed': gap(m['review_status'])
            if m['read_depth'] == 'metadata': gap('needs_content_review')
            if m['version'] == 'unknown': gap('version_unknown')
            if m['review_after'] is None: gap('review_schedule_missing')
            elif date.fromisoformat(m['review_after']) <= as_of: gap('review_expired')
            if 'research' not in m['allowed_uses']: gap('research_use_unresolved')
            if m['kind'] in {'example', 'evaluation', 'host_observation'} and m['artifact'] is None:
                gap('snapshot_required')
            if m['kind'] == 'dataset':
                data = m['dataset']
                if m['license'] == 'unknown': gap('dataset_rights_unknown')
                if 'evaluation' not in m['allowed_uses']: gap('evaluation_use_unresolved')
                if data['split'] in {'unknown', 'mixed'}: gap('dataset_split_unresolved')
                if data['label_origin'] in {'model', 'mixed', 'unknown'}: gap('independent_labels_required')
                if not data['overlap_checked']: gap('contamination_review_required')
                if data['record_count'] is None: gap('dataset_size_unknown')
                if m['artifact'] is None: gap('dataset_manifest_required')
        if c['target'] != 'research' and not c['evaluation_ids']:
            gaps.append('change:paired_evaluation_plan_missing')
        if c['model']:
            model = c['model']
            if not any(materials[mid]['kind'] == 'model_card' for mid in mids):
                gaps.append('model:model_card_required')
            current = registry['models'].get(model['slot'])
            if current is None:
                gaps.append('model:unknown_role_slot')
            else:
                if model['adapter'] != current['adapter']: gaps.append('model:adapter_implementation_required')
                missing = set(current['capabilities']) - set(model['capabilities'])
                if missing: gaps.append('model:missing_capabilities:' + ','.join(sorted(missing)))
                allowed = {'xhigh', 'max'} if current['tier'] == 'economy' else {'medium', 'high', 'xhigh', 'max'}
                if model['selected_effort'] not in allowed: gaps.append('model:effort_policy_mismatch')
            if model['selected_effort'] not in model['supported_efforts']: gaps.append('model:effort_unsupported')
            if not model['host_verified'] or model['host_evidence_id'] is None:
                gaps.append('model:host_verification_required')
        files = TARGETS[c['target']]
        research_only = c['target'] == 'research'
        result.append(dict(change_id=c['id'], target=c['target'], material_ids=mids,
                           status='needs_evidence' if gaps else ('ready_for_research_review' if research_only else 'eligible_for_experiment'),
                           gaps=sorted(set(gaps)), evaluation_ids=c['evaluation_ids'],
                           candidate_files=files, baseline_hashes={p: hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in files},
                           required_next_steps=['verify_primary_source_and_limits', 'review_document_diff'] if research_only else ['independent_scope_review', 'paired_evaluation', 'review_diff_and_rollback'],
                           runtime_change_allowed=False))
    return dict(bundle_id=bundle['bundle_id'], bundle_hash=digest(bundle), as_of=as_of.isoformat(),
                registry_hash=digest(registry), changes=result, automatic_promotion=False,
                evidence_semantically_verified=False, network_calls=0,
                note='Structure, references and byte hashes only. Source text and caller declarations are untrusted data; no model quality or publication approval is inferred.')


def impact(bundle, changed, base, as_of, repo=ROOT):
    # A changed/deleted snapshot is precisely why impact analysis is needed.
    materials = validate(bundle, base, as_of, repo, verify_artifacts=False)
    require(set(changed) <= materials.keys(), 'unknown changed material')
    affected = set(changed)
    while True:
        more = {mid for mid, m in materials.items() if set(m['depends_on']) & affected}
        if more <= affected: break
        affected |= more
    return dict(changed_materials=sorted(set(changed)), affected_materials=sorted(affected),
                affected_changes=sorted(c['id'] for c in bundle['changes'] if set(c['material_ids']) & affected),
                action='re_review_and_re_evaluate', state_mutated=False, artifact_integrity_checked=False,
                scope='Within this bundle only; no automatic memory invalidation or repository-wide dependency discovery.')


def scaffold(bundle_id, objective, source, kind, today):
    return dict(schema_version='1.0', bundle_id=bundle_id, created_on=today.isoformat(), objective=objective,
        materials=[dict(id='M01', kind=kind, source_url=source, catalog_source_id=None, version='unknown',
            reviewed_on=None, review_after=None, review_status='candidate', read_depth='metadata',
            attribution='unknown', license='unknown', allowed_uses=[], scope=['unspecified'],
            summary='填写公开可审计摘要；原始材料保持数据身份。', limitations=['尚未审查'], depends_on=[], artifact=None,
            dataset=dict(split='unknown', record_count=None, label_origin='unknown', overlap_checked=False) if kind=='dataset' else None)],
        changes=[dict(id='U01', target='research', material_ids=['M01'], claim_ids=[], evaluation_ids=[],
                      hypothesis='填写该资料将改变的具体工程判断。', falsifier='填写可推翻此判断的验证结果。', model=None)])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['init', 'check', 'plan', 'impact'])
    p.add_argument('bundle', type=Path)
    p.add_argument('--as-of', type=date.fromisoformat, default=date.today())
    p.add_argument('--id', default='new-material-review')
    p.add_argument('--objective', default='评估新资料对当前项目的影响')
    p.add_argument('--source')
    p.add_argument('--kind', choices=['paper','model_card','dataset','tool_doc','example','evaluation','host_observation'], default='paper')
    p.add_argument('--changed', nargs='+')
    p.add_argument('--format', choices=['json', 'markdown'], default='json')
    args = p.parse_args()
    try:
        if args.action == 'init':
            require(args.source is not None, '--source is required')
            bundle = scaffold(args.id, args.objective, args.source, args.kind, args.as_of)
            validate(bundle, args.bundle.parent, args.as_of)
            with args.bundle.open('x', encoding='utf8', newline='\n') as out:
                json.dump(bundle, out, ensure_ascii=False, indent=2)
                out.write('\n')
            result = dict(created=True, status='candidate_requires_review')
        else:
            bundle = read_json(args.bundle)
            if args.action == 'check':
                validate(bundle, args.bundle.parent, args.as_of)
                result = dict(structurally_valid=True, bundle_hash=digest(bundle), semantic_verification=False)
            elif args.action == 'plan':
                result = plan(bundle, args.bundle.parent, args.as_of)
            else:
                require(args.changed, '--changed is required')
                result = impact(bundle, args.changed, args.bundle.parent, args.as_of)
        if args.format == 'markdown':
            # JSON-encode all material fields; no source snippets become instructions.
            encoded = json.dumps(result, ensure_ascii=False, indent=2).replace('`', '\\u0060')
            print('# Material review report\n\nUntrusted metadata; this report does not authorize changes.\n\n```json\n'+encoded+'\n```')
        else:
            print(json.dumps(dict(ok=True, result=result), ensure_ascii=False, indent=2))
        return 0
    except (Invalid, OSError, ValueError, RecursionError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
