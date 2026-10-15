"""File-only CLI: validate r=1 logs, then create D0 descriptive JSON/Markdown."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def seal(value):
    result = {k: v for k, v in value.items() if k != 'sha256'}
    result['sha256'] = digest(result)
    return result


def verify_seal(value):
    require(isinstance(value, dict) and seal(value) == value, 'Invalid object content seal')


def read(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'Duplicate JSON field: ' + key)
            obj[key] = value
        return obj
    def invalid(value):
        raise ValueError('Non-finite JSON: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique, parse_constant=invalid)


def binding(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    relative = path.relative_to(root)
    raw = path.read_bytes()
    return {'path': relative.as_posix(), 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def verify_bindings(entries, root):
    for entry in entries:
        require(binding(root / entry['path'], root) == {k: entry[k] for k in ('path', 'size', 'sha256')},
                'Bound input bytes changed: ' + entry['path'])


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def build_bound_dataset(root, hydrated_path, runs_path):
    from analysis_inputs import build_dataset
    before = [binding(hydrated_path, root), binding(runs_path, root)]
    value = build_dataset(root, hydrated_path, read(runs_path))
    verify_bindings(before + value['input_files'], root)
    value['construction'] = {'hydrated_inputs_file': before[0], 'runs_file': before[1]}
    return seal(value)


def dataset_closure(value):
    return value['input_files'] + list(value['construction'].values())


def load_bound_dataset(root, path):
    value = read(path)
    verify_seal(value)
    require(value.get('kind') == 'd0_descriptive_dataset' and value.get('schema_version') == 1,
            'Wrong dataset kind or schema')
    require(value.get('runtime_authorized') is False and isinstance(value.get('construction'), dict),
            'Dataset lacks offline construction provenance')
    verify_bindings(dataset_closure(value), root)
    construction = value['construction']
    rebuilt = build_bound_dataset(root, root / construction['hydrated_inputs_file']['path'],
                                 root / construction['runs_file']['path'])
    require(rebuilt == value, 'Dataset does not regenerate from bound source logs')
    return value


def make_report(dataset):
    from analysis_metrics import analyze
    from analysis_cases import select_cases
    from analysis_diagnostics import summarize_diagnostics
    from analysis_sensitivity import summarize_sensitivity
    from analysis_costs import summarize_costs
    metrics = analyze(dataset)
    return {'schema_version': 1, 'kind': 'd0_descriptive_report',
            'status': 'descriptive_complete' if dataset['status'] == 'complete' else 'descriptive_collection_incomplete',
            'runtime_authorized': False, 'formal_inference_accepted': False,
            'dataset_sha256': dataset['sha256'], 'D0_game_count': dataset['D0_game_count'],
            'original_selected_state_count': dataset['original_selected_state_count'],
            'collection': {key: dataset[key] for key in ('status', 'games', 'no_observed_decision_games',
                                                        'collection_incomplete_games', 'admission_pending_games')},
            'metrics': metrics, 'cases': select_cases(dataset, metrics['point_metrics']),
            'diagnostics': summarize_diagnostics(dataset),
            'game_sensitivity': summarize_sensitivity(dataset, metrics['point_metrics']),
            'costs': summarize_costs(dataset),
            'analysis_environment': {'python_version': platform.python_version(),
                                     'python_implementation': platform.python_implementation(),
                                     'numeric_representation': 'Python float; no score rounding/tolerance grouping',
                                     'summation': 'math.fsum for weighted aggregates'},
            'limits': ['D0 development description, not D1/E inference.',
                       'Y differences are single observations, not measured true conditional V differences.',
                       'EM/token-F1 are text-match proxies; confidence is a ranking score, not calibrated probability.',
                       'No confidence intervals, p-values, certified C bound or automatically selected D1 size.',
                       'Missing or pending evidence remains visible; available-case summaries do not complete collection.',
                       'Deployment metadata is not live GPU/service admission proof.'],
            'new_model_calls': 0, 'new_environment_instances': 0}


def _cell(value):
    text = '—' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')


def render_markdown(report):
    lines = ['# D0-var 描述性报告', '',
             f"状态：`{report['status']}`。原计划 {report['D0_game_count']} 个游戏、{report['original_selected_state_count']} 个状态。",
             '', '本报告只描述 D0 观测。三种单次结果差不等于真实条件效用；不提供正式置信区间、p 值或 C 上界。', '',
             '## 采集分母', '', '| 游戏 | 原 k_j | 状态 |', '|---|---:|---|']
    for game in report['collection']['games']:
        lines.append(f"| {_cell(game['canonical_game_id'])} | {game['original_k_j']} | {_cell(game['status'])} |")
    lines += ['', '## 均值与排序描述', '',
              '主值因缺测或资格未完成而不可给出时保留为 —；available-case 列仅描述已知交集。各交集仍使用原 k_j 权重。', '',
              '| 分析池 / 指标 | 主值 | 已知交集描述 | 目标 / 已知状态数 | 已知原权重质量 |',
              '|---|---:|---:|---:|---:|']
    for pool_name, pool in report['metrics']['aggregate'].items():
        stats = [('Y_' + name, stat) for name, stat in pool['branch_available'].items()]
        stats += [('U_' + name, stat) for name, stat in pool['observed_U'].items()]
        stats += [(name, stat) for name, stat in pool['accuracy'].items()]
        for name, stat in stats:
            lines.append(f"| {pool_name} / {name} | {_cell(stat['mean'])} | {_cell(stat['available_case_mean'])} | {stat['target_denominator']['points']} / {stat['observed_denominator']['points']} | {_cell(stat['observed_denominator']['original_weight_mass'])} |")
    lines += ['', '| 排序 | 状态 | G admission / info / revision | 已知完整交集 G |', '|---|---|---|---|']
    for name, rank in report['metrics']['ranking_diagnostics'].items():
        primary = ' / '.join(_cell(rank['G'][x]) for x in ('admission', 'info', 'revision'))
        partial = ' / '.join(_cell(rank['available_complete_case_G'][x]) for x in ('admission', 'info', 'revision'))
        lines.append(f"| {name} | {_cell(rank['status'])} | {primary} | {partial} |")
    lines += ['', '这些是观测差的代入值，不含正式区间或检验。预测长度按原预测 token span 计数，固定较长优先。', '',
              '| confidence 与准确性 | Pearson | 平均秩相关 | 交集状态数 | 不可估原因 |',
              '|---|---:|---:|---:|---|']
    for name, relation in report['metrics']['relationships']['confidence_accuracy'].items():
        lines.append(f"| {name} | {_cell(relation['pearson'])} | {_cell(relation['spearman'])} | {relation['n']} | {_cell(relation['undefined_reason'])} |")
    lines += ['', '## 逐点观测与准确性', '',
              'Y 列保留原始观测；U 列只展示通过该项资格核验的观测差。缺失不填零。', '',
              '| 游戏 / 状态 | 预算 | D / N / P 原始 Y | U admission / info / revision | EM | token-F1 | mean logprob |',
              '|---|---:|---|---|---:|---:|---:|']
    for p in report['metrics']['point_metrics']:
        raw = ' / '.join(_cell(p['raw_Y'][b]) for b in ('D', 'N', 'P'))
        u = ' / '.join(_cell(p['observed_U'][x]) for x in ('admission', 'info', 'revision'))
        lines.append(f"| {_cell(p['canonical_game_id'])} / {_cell(p['state_id'])} | {p['remaining_budget']} | {raw} | {u} | {_cell(p['EM'])} | {_cell(p['token_F1'])} | {_cell(p['mean_logprob'])} |")
    lines += ['', '## 固定类别案例', '',
              f"从全部原计划点按冻结哈希抽取 {report['cases']['selected_count']} 例；缺少类别不补造。", '']
    for category in report['cases']['categories']:
        lines.append(f"- `{category['category']}`：候选 {category['eligible_count']}，选中 {_cell(category['selected'])}，缺省原因 {_cell(category['reason'])}。")
    for case in report['cases']['selected']:
        p = case['point']
        evidence = {'game': p['canonical_game_id'], 'state': p['state_id'], 'draft': p.get('draft_action'),
                    'prediction': (p.get('prediction') or {}).get('wm_prediction'),
                    'actual_D_reference': (p.get('D_reference') or {}).get('observation'),
                    'raw_Y': {b: p['branches'][b].get('raw_Y') for b in ('D', 'N', 'P')},
                    'limitations': case['evidence_limitations']}
        lines += ['', '### ' + case['category'], '', '```json', json.dumps(evidence, ensure_ascii=False, indent=2), '```']
    lines += ['', '## 解释边界', '']
    lines += ['- ' + text for text in report['limits']]
    lines += ['', '完整加权均值、分层、排序、相关、游戏敏感性、物理路径诊断及成本明细见同名 JSON。', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    ds = sub.add_parser('dataset')
    ds.add_argument('--hydrated-inputs', required=True, type=Path)
    ds.add_argument('--runs', required=True, type=Path)
    report = sub.add_parser('report')
    report.add_argument('--dataset', required=True, type=Path)
    for command in (ds, report):
        command.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    def resolve(path):
        actual = (root / path).resolve()
        require(actual.is_relative_to(root), 'Path leaves project root')
        return actual
    output = resolve(args.out)
    require(not output.exists(), 'Output already exists')
    if args.command == 'dataset':
        value = build_bound_dataset(root, resolve(args.hydrated_inputs), resolve(args.runs))
    else:
        path = resolve(args.dataset)
        markdown_path = output.with_suffix('.md')
        require(output.suffix.lower() == '.json' and not markdown_path.exists(),
                'Report requires a new .json path and a new matching .md path')
        package = Path(__file__).resolve().parent.parent
        implementation = [binding(p, root) for p in sorted((package / 'sidecar').glob('*.py'))]
        implementation.append(binding(package / 'ANALYSIS_SPEC.json', root))
        before = [binding(path, root), *implementation]
        dataset = load_bound_dataset(root, path)
        value = make_report(dataset)
        value['input_files'] = before
        value = seal(value)
        rendered = render_markdown(value)
        verify_bindings(before + dataset_closure(dataset), root)
        write_new(output, value)
        with markdown_path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(rendered)
        print(json.dumps({'status': value['status'], 'sha256': value['sha256'], 'runtime_authorized': False}))
        return 0
    write_new(output, value)
    print(json.dumps({'status': value['status'], 'sha256': value['sha256'], 'runtime_authorized': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
