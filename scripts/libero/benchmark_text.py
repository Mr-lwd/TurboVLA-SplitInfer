"""English display text for legacy catalog notes; source records stay unchanged."""

import re

_NOTES = {
    "使用现有原始记录重算，未重新评测。按 task ID / episode 匹配；均值与 p95 从保留调用和控制步重新汇总。": "Recomputed from existing records without rerunning evaluation. Cases match by task ID / episode; means and p95 use retained calls and control steps.",
    "共同成功样本数不代表整体成功率；完整运行的失败记录和成功比例保留在原始全案例分组。": "Matched case counts are not overall success rates. Complete successes and failures remain in the source records.",
    "推理均值与 p95 仍按每回合排除首次调用；任务总耗时包含首次推理等待，控制间隔不额外剔除回合内的慢间隔。": "Response mean and p95 exclude the first call per episode. Total time includes initial inference waits; slow within-episode control intervals are retained.",
    "同为 LIBERO Spatial、10 个任务各 1 次、seed 7、BF16、chunk 12。本机无墙钟限频，远程为 20 Hz 上限；远程重规划间隔 4 步、融合窗口 3 步、额外延迟 0。": "All runs use LIBERO Spatial, 10 tasks with one trial each, seed 7, BF16 and chunk size 12. Local runs have no wall-clock rate cap; remote runs are capped at 20 Hz with replanning every 4 steps, a 3-step blend window and no injected delay.",
    "Orin 本机成功 10/10、1002 步；Thor 本机成功 9/10、1118 步，task 4 失败。远程 Sync 同样在 task 4 失败；各模式轨迹与执行步数不同，总耗时差不等于纯模型加速。": "Full runs: Orin local succeeds in 10/10 episodes over 1002 steps; Thor local succeeds in 9/10 over 1118 steps, failing task 4. Sync also fails task 4. Trajectories and step counts differ, so duration differences are not pure model speedups.",
    "各次运行来自不同代码提交与运行时刻；本机 metadata 未记录 checkpoint SHA-256，不能仅凭文件名确认与远程权重一致。": "Runs were recorded at different revisions and times. Local metadata does not include checkpoint SHA-256, so filenames alone cannot establish weight identity with remote runs.",
    "Orin 板卡 metadata 为 Orin NX Engineering Reference Developer Kit，与项目 Orin Nano 标注存在差异，结果保留 Orin 泛称。": "The recorded Orin board is Orin NX Engineering Reference Developer Kit, which differs from the project Orin Nano label. Results therefore use the generic Orin name.",
}


def english_note(note):
    """Translate known historical prose without changing metrics or provenance."""
    note = note.removeprefix("原始组说明：").removeprefix("Source note: ")
    if note in _NOTES:
        return _NOTES[note]
    matched = re.fullmatch(r"仅统计全部 (\d+) 种模式共同成功的 (\d+) 个案例；统一排除：(.*)。", note)
    if matched:
        modes, cases, excluded = matched.groups()
        return f"Only {cases} cases successful in all {modes} modes are included; excluded: {excluded}."
    return note.replace("、", ", ").replace("。", ".")
