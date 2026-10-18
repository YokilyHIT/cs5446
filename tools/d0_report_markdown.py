"""Readable Chinese rendering of the reproducible D0 report."""
from __future__ import annotations

import json
import statistics


def cell(value):
    if value is None:
        return '—'
    if isinstance(value, float):
        return f'{value:.10g}'
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + [
        '| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows] + ['']


def available(stat):
    return stat['available_case_mean']


def pool_row(name, pool):
    paired = pool['paired_complete']
    d = paired['denominator']
    return [name, d['points'], d['games'], d['original_weight_mass'],
            *[paired['branch_means'][b] for b in ('D', 'N', 'P')],
            *[paired['mean_observed_U'][u] for u in ('admission', 'info', 'revision')]]


def render_markdown(report):
    m, check = report['metrics'], report['integrity']
    pool = m['aggregate']['all_planned']
    core = m['aggregate']['core_A']
    lines = ['# D0 开发数据完整描述报告', '',
        '本报告分析固定 4B Planner 与一步 World Model 在 ALFWorld D0 开发游戏中的局部 D/N/P 测量。'
        '在 68 个有完整结果的状态上，按原状态权重归一后的 D/N/P 成功均值分别为 '
        + ' / '.join(cell(core['paired_complete']['branch_means'][b]) for b in ('D', 'N', 'P')) + '。'
        '首动作变化较多，终局差异集中于同一游戏的两个状态。confidence 与文本匹配准确性呈正向描述性关联；'
        '局部效用的非零观测很少，尚不能据此确定其稳定排序能力。', '',
        '这是现有数据的完整描述性报告。每物理组仅续跑一次（r=1），D0 用于开发和诊断；'
        '本报告不估计真实条件效用，不提供确认性区间、p 值、认证 C 上界或 D1 样本量。N/P 候选已在后文列出，实际跨作业抽查仍待运行。', '',
        '## 研究设置与分母', '',
        'Planner 和 WM 为 Qwen3-4B-Instruct-2507，profile 为 `react_single_env_action_v1`；'
        'seed 42、temperature 0、top_p 0.5，输出上限分别为 384/256，history 50，无 memory，H=30，采集使用整卡 A100-PCIE-40GB。'
        '源轨迹使用 None 策略。D 执行原 draft，N 不看预测再次决策，P 看预测再次决策；'
        '三者从同一预选状态恢复，之后均使用无预测策略 μ。剩余预算为 30−t，包含干预动作。', '',
        '期望效用定义为 U_admission=V_P−V_D、U_info=V_P−V_N、U_revision=V_N−V_D。'
        '下文的“观测差”是单次 Y 差。共享物理组只执行和计数一次，不增加独立样本。', '']
    lines += table(['覆盖项', '数量或原权重'], [
        ['原计划游戏 / 预选点', f"{check['games']} / {check['selected_states']}"],
        ['完整 D/N/P 点 / 物理组', f"{check['complete_DNP_states']} / {check['physical_groups']}"],
        ['源 draft 失败点', check['source_draft_failures']['points']],
        ['全部原权重', check['original_weight_mass']],
        ['可用 D/N/P 原权重', core['denominator']['original_weight_mass']],
        ['源 draft 失败原权重', check['source_draft_failures']['original_weight_mass']],
        ['D 检查状态', json.dumps(check['D_check_status_counts'], ensure_ascii=False)],
        ['D 新 μ 请求对', check['D_new_mu_request_pairs']],
    ])
    lines += ['68 个通过的 D 检查中，67 点包含新 μ 请求比对，另 1 点只覆盖环境转移。'
              '这些 D 复现检查不替代独立 N/P 抽查。', '',
              '每点原权重为 1/(24×original_k_j)。每个指标只在自己的合格集合内整体归一；'
              '删点后不按每局剩余点数重新平权。3 个源 draft 失败点没有形成局部预测事件，保留在 71 点分母中，'
              '局部 Y、confidence、accuracy 和 U 均为缺失。71 点全计划均值因此为 null；下面的可用交集结果只描述已观测部分。', '',
              '## 局部结果与动作变化', '']
    rows = []
    for b in ('D', 'N', 'P'):
        s = pool['branch_available'][b]
        rows.append(['Y_' + b, s['mean'], available(s), s['observed_denominator']['points'],
                     s['observed_denominator']['original_weight_mass'], check['branch_outcome_counts_unweighted'][b].get('1', 0)])
    for u in ('admission', 'info', 'revision'):
        s = pool['observed_U'][u]
        rows.append(['观测 ' + u, s['mean'], available(s), s['observed_denominator']['points'],
                     s['observed_denominator']['original_weight_mass'], '见下表'])
    lines += table(['指标', '全计划均值', '可用交集加权均值', '观测点数', '原权重覆盖', '不加权成功点数'], rows)
    rows = []
    for u in ('admission', 'info', 'revision'):
        c = check['observed_difference_counts_unweighted'][u]
        rows.append([u, c.get('1', 0), c.get('0', 0), c.get('-1', 0), c.get('None', 0),
                     available(pool['observed_rescue'][u]), available(pool['observed_harm'][u])])
    lines += table(['观测差', '+1 点数', '0 点数', '−1 点数', '缺失', '加权正差比例', '加权负差比例'], rows)
    rows = []
    for u, label in (('admission', 'P 对 D'), ('revision', 'N 对 D'), ('info', 'P 对 N')):
        c, s = check['action_changes_unweighted'][u], pool['action_changes'][u]
        rows.append([label, f"{c['changed']}/{c['comparable']}", available(s), s['observed_denominator']['original_weight_mass']])
    lines += table(['可解析首动作比较', '改变数 / 可比较数', '加权改变比例', '原权重覆盖'], rows)
    lines += ['N 的一次首动作格式失败是有效 Y=0，但没有可执行 N 动作。它保留在 P−N、N−D 的终局比较中，'
              '仅从要求双方动作可解析的比较中排除。因此 N 对 D 为 20/67。', '',
              '## 预测准确性与 confidence', '',
              '准确性参考是 D 执行原 draft 后的真实第一步 observation。EM 和 token-F1 使用冻结文本规范化，'
              '仅为文本匹配代理。排序使用原始 mean logprob；exp 分数仅用于展示，不是校准概率。', '']
    lines += table(['准确性', '加权均值', '点数', '原权重覆盖'], [
        [q, available(m['accuracy_description'][q]), m['accuracy_description'][q]['observed_denominator']['points'],
         m['accuracy_description'][q]['observed_denominator']['original_weight_mass']] for q in ('EM', 'token_F1')])
    exp = [p['exp_score'] for p in m['point_metrics'] if p['core_A_eligible'] is True]
    lines += [f"展示分数的未加权中位数为 {cell(statistics.median(exp))}，其中 {sum(x >= .95 for x in exp)}/{len(exp)} ≥ 0.95。"
              f"原 mean logprob 有 {m['score_diagnostics']['exact_unique_mean_logprobs']} 个精确不同值。", '']
    relations = []
    for q, stat in m['relationships']['confidence_accuracy'].items():
        relations.append(['mean logprob', q, stat['pearson'], stat['spearman'], stat['n'], stat['weight_mass']])
    for q, utilities in m['relationships']['accuracy_observed_U'].items():
        for u, stat in utilities.items():
            relations.append([q, '观测 ' + u, stat['pearson'], stat['spearman'], stat['n'], stat['weight_mass']])
    lines += table(['变量一', '变量二', '加权 Pearson', '加权秩相关', '点数', '原权重覆盖'], relations)
    lines += ['秩相关按冻结定义为普通平均秩的加权 Pearson，精确同分保留平均秩。相关系数没有确认性显著性解释。', '',
              '以下四组按 mean logprob 从高到低排序，各占合格原权重的 25%；跨边界的精确同分按相同比例分配。'
              '同一点可对相邻组贡献部分权重，组内点数不能相加视为独立样本。', '']
    lines += table(['confidence 组', '参与点数', '原权重', 'EM', 'token-F1', '观测 P−D', '观测 P−N', '观测 N−D'], [
        [b['bin'], b['summary']['denominator']['points'], b['summary']['denominator']['original_weight_mass'],
         *[available(b['summary']['accuracy'][q]) for q in ('EM', 'token_F1')],
         *[available(b['summary']['observed_U'][u]) for u in ('admission', 'info', 'revision')]] for b in m['confidence_bins']])
    lines += ['冻结 top-half 描述量为 G=Σ normalized_w×(g−0.5)×观测差，g 为精确同分规则下的前半权重归属。'
              '解析 Random 的 G=0。这里的 plug-in G 依赖单次续跑，不能据其符号判断总体收益或真实效用排序。', '']
    lines += table(['排序', 'G_admission', 'G_info', 'G_revision', '共同点数', '原权重', '选择覆盖'], [
        [name, *[r['available_complete_case_G'][u] for u in ('admission', 'info', 'revision')],
         r['common_denominator']['points'], r['common_denominator']['original_weight_mass'], r.get('weighted_coverage')]
        for name, r in m['ranking_diagnostics'].items()])
    lines += ['## 菜单与预算分层', '',
              '每行均在该层的完整 D/N/P 交集内使用原权重归一；这些是条件描述，不可直接相加。'
              'draft 不在可见菜单中不等于环境反馈必然为 Nothing happens.。', '']
    headers = ['层', '完整点数', '游戏数', '原权重', 'D', 'N', 'P', 'P−D', 'P−N', 'N−D']
    lines += table(headers, [pool_row('menu ' + name, value['all_planned']) for name, value in m['by_menu'].items()]
                   + [pool_row('budget ' + name, value['all_planned']) for name, value in m['by_budget'].items()])
    lines += ['每层准确性、动作变化、正负差及缺失分母保留于 JSON 的 `metrics.by_menu` 与 `metrics.by_budget`。', '',
              '## 跨作业与逐游戏删除敏感性', '',
              '跨作业分类沿实际物理组恢复出处关联 job_id 和 service_instance_id；源 draft 采集阶段不计入局部分支的跨作业比较。'
              '主分析保留全部原资格集合，敏感性只保留身份核实为 false 的状态。true、unknown 和 not_applicable 分列。', '']
    cross = report['cross_job_sensitivity']
    lines += table(['实际身份分类', '点数', '游戏数', '原权重'], [
        [label, r['points'], r['games'], r['original_weight_mass']] for label, r in cross['categories'].items()])
    lines += table(headers, [pool_row('主分析可用交集', pool),
                            pool_row('仅 verified false', cross['verified_false']['aggregate']['all_planned'])])
    lines += table(['关系', '主 Pearson', '排除后 Pearson', '主秩相关', '排除后秩相关'], [
        [q, stat['pearson'], cross['verified_false']['relationships']['confidence_accuracy'][q]['pearson'],
         stat['spearman'], cross['verified_false']['relationships']['confidence_accuracy'][q]['spearman']]
        for q, stat in m['relationships']['confidence_accuracy'].items()])
    lines += ['完整的排除后准确性、三项观测差、分层、重新分箱及排序见 JSON；没有把剩余状态重新按游戏平权。', '',
              '逐游戏删除时移除整局，再用剩余原权重整体归一。下表范围是敏感性描述，不是置信区间。', '']
    lines += table(['指标', '可用均值', '点数', '原权重', '删除一局的范围', '范围不可用原因'], [
        [name, s['observed_subset']['mean'], s['observed_subset']['n'], s['observed_subset']['base_weight_mass'],
         s['leave_one_game_out_range'], s['range_unavailable_reason']]
        for name, s in report['game_sensitivity']['means'].items()])
    lines += ['两个终局差异状态都来自第 14 局；删除这局后，三项观测差均为零。'
              '这说明效用描述对单个游戏敏感，也说明更多同游戏状态不能当成新的独立游戏证据。', '',
              '## 物理轨迹诊断与固定案例', '']
    lines += render_paths(report)
    lines += ['## 成本与未知范围', '']
    lines += render_costs(report)
    lines += ['## 冻结 N/P 候选', '']
    lines += render_np(report)
    lines += ['## 结论与后续边界', '',
        '本配置的 WM confidence 能在 D0 中区分部分文本匹配准确性，首动作也经常因再次决策或预测而改变。'
        '这些变化只在同一游戏的两个状态形成终局差异；P−N 的正差包含一次 N 格式失败，P−D 没有正差。'
        '现有证据支持继续做有界 N/P 复核，尚不足以证明 confidence 无用、真实效用为零或整局 Always 无用。'
        '低成功率与后续 μ 可能影响差异显现，但本次轨迹观察不能确认这些机制。', '',
        '后续 N/P 实际抽查与 D1/E 的资格、样本量和分析方案是独立决定。本报告沿用现有 4B 数据，'
        '不把未核实的 32B NPU 配置混入同配置结论。', '',
        '## 复算与来源', '',
        '在仓库根目录使用 Python 3.10+ 标准库运行：', '', '```sh',
        'python -B tools/build_d0_report.py --out gpu_analysis/generated/d0_report_new.json', '```', '',
        '输出 JSON 和同名 Markdown；已有文件不会覆盖。全部分析只读取本仓库便携数据，普通复算无需原归档、SSH、GPU 或模型服务。'
        '重新导出逐调用、身份和候选证据才需要原归档。输入与实际分析代码的 SHA-256 记录在 JSON 中。', '',
        f"数据内容 SHA-256：`{report['snapshot_content_sha256']}`。", '',
        '原 71 点快照、117 组摘要、冻结分析模块及指标字节保持；新增证据是从已有原件导出的派生数据。'
        '真实逐调用成本的已知部分与不可恢复部分分开，身份绑定是对已接受原件的本地核查，不是新的服务运行验收。', '']
    lines += table(['输入', '字节数', 'SHA-256'], [[r['name'], r['size'], '`' + r['sha256'] + '`'] for r in report.get('input_files', [])])
    return '\n'.join(lines)


def render_paths(report):
    p = report['paths']['physical_behavior']
    repeat, nothing = p['adjacent_mu_repetition'], p['mu_exact_Nothing_happens']
    lines = ['全部物理组按真实 rollout ID 去重，以下是路径计数，不使用状态总体权重。'
             'μ 相邻重复包含第一条 μ 动作与缓存首动作的比较；最长连续重复也包含缓存首动作。', '']
    lines += table(['物理行为', '结果'], [
        ['物理组 / 已执行动作', f"{p['physical_groups']} / {p['executed_transitions']}"],
        ['新 μ 逻辑调用 / 已执行 μ 动作', f"{p['recorded_new_mu_calls']} / {repeat['denominator']}"],
        ['μ 相邻动作重复', f"{repeat['numerator']}/{repeat['denominator']} = {cell(repeat['rate'])}"],
        ['μ 精确 Nothing happens.', f"{nothing['numerator']}/{nothing['denominator']} = {cell(nothing['rate'])}"],
        ['最长相同动作连续段', p['maximum_action_streak']],
        *[['终止 ' + key, value] for key, value in p['termination_counts'].items()],
    ])
    lines += ['新 μ 调用包括结尾策略失败调用，因而调用数可以大于已执行动作数。'
              '共享分支的失败只形成一个物理失败事件，不能按 D/N/P 引用次数重复计费或当成独立失败。'
              '上述重复和无变化反馈是路径描述，不能直接用来解释终局效用的因果机制。', '']
    for row in report['cases']['categories']:
        lines.append(f"- `{row['category']}`：合格 {row['eligible_count']} 点；"
                     + ('类别不存在，不补样。' if row['selected'] is None else f"按冻结哈希选择 `{row['selected'][1]}`。"))
    lines += ['', '固定案例从全部原 71 点的合格池选择；额外列出全部终局差异点用于核对，二者不混作案例抽样规则。', '']
    for example in report['path_examples']:
        p = example['point']
        tag = '固定哈希案例' if example['fixed_case'] else '全部差异点补充说明'
        lines += [f"### 第 {p['game_position_0based'] + 1} 局 t={p['step_id']} {tag}", '',
                  f"游戏：`{p['canonical_game_id']}`。状态：`{p['state_id']}`；剩余预算 {p['remaining_budget']}。", '',
                  'D/N/P=' + '/'.join(cell(p['branches'][b]['raw_Y']) for b in ('D', 'N', 'P')) + '。', '']
        if p['source_decision_status'] == 'source_draft_policy_failure':
            lines += ['源 draft 策略失败，没有局部预测事件或 D/N/P 续跑；局部结果保持缺失。', '']
        else:
            lines += [f"预测：{cell((p['prediction'] or {}).get('wm_prediction'))}", '',
                      f"D 真实首步观察：{cell((p['D_reference'] or {}).get('observation'))}", '']
        lines += table(['分支', '首动作', '结果状态', 'Y'], [
            [b, p['branches'][b].get('first_action'), p['branches'][b]['outcome_status'], p['branches'][b]['raw_Y']]
            for b in ('D', 'N', 'P')])
        for g in example['groups']:
            lines += [f"物理组 `{g['group_id']}`，共享分支 {', '.join(g['branches'])}，"
                      f"终止 `{g['termination_reason']}`，{len(g['steps'])} 个已执行动作、{g['new_mu_calls']} 次新 μ 调用。", '']
            lines += table(['步', '阶段', '动作', '真实观察', '成功'], [
                [s['step'], s['phase'], s['action'], s['next_obs'], s['success']] for s in g['steps']])
    lines += ['第 14 局 t=10 的 N 首动作不可解析，因此 N=0，P−N=+1；D 与 P 都成功，P−D=0。'
              't=16 的 P 预算耗尽，而 D/N 成功。两点 P 首动作均把 dishsponge 放入 sinkbasin，'
              '故动作名称本身不是已确认的失败原因。', '']
    return lines


def render_costs(report):
    costs = report['costs']
    lines = ['成本只覆盖当前 campaign 的 15 次尝试，既保留接受样本，也保留旧失败和未完成片段。'
             '逐调用按原日志文件与 call ID 去重；共享分支不会重复计费。下面先列原接受账本，'
             '再列实际审计记录，二者口径分别保留。', '']
    labels = {'d0_var_all_13_attempts': 'D0-var 13 次尝试', 'd0_source_two_attempts': '源阶段 2 次尝试',
              'entire_campaign_15_attempts': 'campaign 合计 15 次', 'ten_accepted_batches': '其中 10 个接受批次'}
    lines += table(['账本范围', '记录逻辑调用', 'observed HTTP charged', '保守 charged 逻辑调用',
                    '保守 charged HTTP', '观测 allocation 秒', 'charged allocation 秒'], [
        [labels[name], r['observed']['logical_model_calls'], r['observed']['http_attempts_charged'],
         r['charged']['logical_model_calls'], r['charged']['http_attempts_charged'],
         r['observed']['allocation_seconds'], r['charged']['allocation_seconds']]
        for name, r in costs['accounting_totals'].items()])
    lines += ['这些集合互相包含，不可逐行相加。charged allocation 是保守预算扣额，不是 GPU 忙碌时间。', '',
              '### 真实逐调用记录', '']
    scopes = {'source': '源轨迹', 'local': '局部 N/WM/P 与 μ', 'acceptance': '后端验收'}
    lines += table(['调用归属', 'request starts', '完整终端', '已保存 HTTP 尝试', '已知 prompt tokens',
                    '已知 completion tokens', '已知请求耗时秒', '缺终端 starts'], [
        [scopes.get(name, name), r['logical_calls'], r['terminal_records'], r['http_attempts_recorded'],
         r['prompt_tokens']['known_sum'], r['completion_tokens']['known_sum'],
         r['request_elapsed_s']['known_sum'], r['terminal_missing_starts']]
        for name, r in costs['by_scope'].items()])
    total = costs['per_call_total']
    lines += [f"合计 {total['logical_calls']} 条 request_start、{total['terminal_records']} 条完整终端记录、"
              f"{total['http_attempts_recorded']} 条已保存 HTTP 尝试。已知 prompt/completion tokens 为 "
              f"{cell(total['prompt_tokens']['known_sum'])}/{cell(total['completion_tokens']['known_sum'])}，"
              f"已知请求耗时合计 {cell(total['request_elapsed_s']['known_sum'])} 秒。"
              '这些是已保存记录的已知小计；未知调用的 HTTP、tokens、耗时和结果保持 null，不能当成完整实际成本。', '',
              '后端验收共 130 次，其中源阶段 20 次、D0-var 阶段 110 次。因此账本源阶段 586 次包含 '
              '566 次源轨迹调用和 20 次验收。10 个完整接受批次的 1,336 次调用分为 100 次验收与 1,236 次采集。', '']
    lines += table(['阶段', 'request starts', '完整终端', '可见 HTTP 尝试', '策略内容失败', '缺终端 starts'], [
        [name, r['logical_calls'], r['terminal_records'], r['http_attempts_recorded'],
         r['failure_categories'].get('policy_content', 0), r['terminal_missing_starts']]
        for name, r in costs['by_phase'].items()])
    lines += ['局部 first_action 共 204 次，即 68 个局部事件各有 N、WM、P 调用。'
              '全部局部 continuation 有 1,300 条开始记录，而最终接受的 117 物理组只有 1,295 次新 μ 调用；'
              '差额属于旧失败或未完成片段，不能加入最终轨迹步数。', '']
    timing = costs['physical_group_timings']
    lines += table(['最终接受物理组的时间记录', '已知合计秒', '已知组数', '未知组数'], [
        [label, row['known_sum'], row['known_groups'], row['unknown_groups']]
        for label, row in [('rollout elapsed', timing['rollout_elapsed_s']),
                           ('恢复 wall', timing['recovery_timings']['restore_wall_s']),
                           ('恢复 cleanup', timing['recovery_timings']['cleanup_s']),
                           ('恢复 total', timing['recovery_timings']['total_s'])]])
    lines += ['这里仅统计最终接受的 117 个物理组，不含旧中断或失效片段。恢复 total 已含恢复 wall 与 cleanup，'
              'build/reset/replay/validation 子项另留 JSON，不把这些重叠时间相加。'
              '这些物理组耗时也不能代替完整 runner 或作业 wall；跨已接受、恢复与停止尝试的完整 runner wall 未形成统一输入，保持 null。', '',
              '### 935310 的未知调用与账本对照', '',
              '935310 原审计有 278 条唯一 request_start、277 条完整终端和 277 条已保存 HTTP 尝试；'
              '最终账本保留 recorded logical=277、observed http_attempts_charged=279。'
              '多出的请求开始记录没有终端，实际 HTTP 次数、usage 和结果未知。HTTP 的 2 个计费单位差额是保守会计口径，'
              '不能据此断言发生了两次真实 HTTP 请求。request_start 本身也不证明请求已到达服务器。', '',
              '因此当前 campaign 的真实开始记录为 2,200，而账本记录逻辑调用为 2,199；'
              '已保存 HTTP 尝试为 2,199，而账本 observed HTTP charged 为 2,201。原账本不改，未知 start 不删。'
              '这条旧中断片段中的调用不纳入最终接受物理组的新 μ 调用数。', '',
              '### 失败与成本覆盖', '',
              '逐调用记录中已观测策略内容失败为 21 次，其中源轨迹 5 次、局部 16 次。'
              '源阶段 5 次是调用层失败，不等于原预选点中的 3 个源 draft 失败。D0-var 停止线另将 1 次未知保守计入，'
              '形成 17/30；账本 charged 中的 95 个策略失败预算单位不是 95 次观测失败。'
              '已有终端记录未出现 request_error，但 1 条缺终端记录的结果未知，不能据此声称没有技术缺失。', '',
              '计数未完整的作业为 ' + '、'.join(costs['coverage']['unrecorded_attempt_calls_unknown_jobs']) + '。'
              '其中 943125 的 stage 原件未在固定归档位置找到，最终账本记零调用；保留此覆盖缺口，不构造空审计冒充已核实零成本。'
              '源阶段的后端验收报告通过自身 seal 与 audit artifact SHA 核对；最终账本只直接绑定 stage result，'
              '没有独立绑定这两份 backend report。', '',
              '逐调用 usage、耗时及错误分类、每次尝试的账本差额、全部来源 SHA 见 JSON `costs` 和 '
              '`d0_cost_evidence.json`。请求耗时、恢复、runner wall 和 allocation 有重叠，不能相加；'
              '本报告不把它们换算成货币价格或完整 GPU 成本。', '']
    return lines


def render_np(report):
    plan = report['np_candidates']
    d = plan['denominators']
    lines = ['候选由冻结两遍哈希选择器生成，完整选择记录见 JSON `np_candidates`。'
            '要求 6 个严格异 D 首动作物理组、至少 4 游戏、每游戏最多 2 组，且每组至少 10 次新 μ 调用。'
            '策略失败结尾的合格长尾组保留，候选选择不代表复测通过。', '',
            f"选择状态：`{plan['status']}`。全 {d['input_groups']} 组中，严格资格且满足长度阈值的候选为 "
            f"{d['eligible_groups']} 组、{d['eligible_games']} 游戏；最终选择 {d['selected_groups']} 组、"
            f"{d['selected_games']} 游戏，合计 {d['selected_new_mu_calls']} 次原新 μ 调用。", '']
    lines += table(['顺序', '游戏', '状态步', '分支', '首动作', '新 μ 调用', '结果状态'], [
        [i + 1, r['canonical_game_id'], r['state_id'].rsplit(':', 1)[-1], '='.join(r['branches']),
         r['first_action'], r['new_mu_calls'], r['outcome_status']] for i, r in enumerate(plan['selected'])])
    lines += ['这是按冻结规则选择的长尾工程抽查，不是代表性样本或通过复现的证据。'
              '实际 N/P 作业尚未启动，当前交付到候选清单为止。', '']
    return lines
