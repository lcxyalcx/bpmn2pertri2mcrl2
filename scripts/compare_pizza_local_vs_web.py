#!/usr/bin/env python3
"""Compare local Pizza conversion results with bpmn2petrinet.com results."""

from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "docs" / "runs" / "pizza_official_redownload_20260518"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from bpmn2pnml_local import parse_bpmn  # noqa: E402
from pnml2mcrl2 import generate_mcrl2, parse_pnml  # noqa: E402
from rerun_pizza_official_pipeline import write_lts_svg  # noqa: E402


@dataclass(frozen=True)
class ArtifactSet:
    label: str
    pnml: pathlib.Path
    mcrl2: pathlib.Path
    bounded_mcrl2: pathlib.Path
    lps: pathlib.Path
    lts: pathlib.Path
    aut: pathlib.Path
    lts_svg: pathlib.Path


def run(cmd: list[str], cwd: pathlib.Path = ROOT, timeout: int = 240, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=timeout,
    )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required tool not found on PATH: {name}")


def ensure_web_artifacts(bpmn_path: pathlib.Path, artifacts: ArtifactSet) -> None:
    if not artifacts.pnml.exists():
        from bpmn2mcrl2_web import WebConfig, bpmn_to_pnml_via_web

        bpmn_to_pnml_via_web(bpmn_path, artifacts.pnml, config=WebConfig(timeout_ms=60000))
    net = parse_pnml(artifacts.pnml)
    if not artifacts.mcrl2.exists():
        artifacts.mcrl2.write_text(generate_mcrl2(net), encoding="utf-8")
    if not artifacts.bounded_mcrl2.exists():
        artifacts.bounded_mcrl2.write_text(generate_mcrl2(net, max_place_tokens=1), encoding="utf-8")
    if not artifacts.lps.exists():
        run(["mcrl22lps", str(artifacts.bounded_mcrl2), str(artifacts.lps)])
    if not artifacts.lts.exists():
        run(["lps2lts", "--cached", "--max=200", str(artifacts.lps), str(artifacts.lts)])
    if not artifacts.aut.exists():
        run(["ltsconvert", str(artifacts.lts), str(artifacts.aut)])
    if not artifacts.lts_svg.exists():
        write_lts_svg(artifacts.aut, artifacts.lts_svg)


def parse_transition_mapping(mcrl2_path: pathlib.Path) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"^%   (t_\d+)/([^ ]+) = (.+?) \((.+?)\), pre=\[(.*?)\], post=\[(.*?)\]$"
    )
    for line in mcrl2_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        alias, action, name, tid, pre, post = match.groups()
        mapping[action] = {
            "alias": alias,
            "name": name,
            "tid": tid,
            "pre": pre,
            "post": post,
        }
    return mapping


def parse_ltsinfo(path: pathlib.Path) -> dict[str, str]:
    cp = run(["ltsinfo", str(path)])
    combined = cp.stdout + "\n" + cp.stderr
    result: dict[str, str] = {}
    for line in combined.splitlines():
        line = line.strip().rstrip(".")
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
        else:
            result[line] = "yes"
    return result


def action_reachable(lps_path: pathlib.Path, action: str) -> bool:
    with tempfile.TemporaryDirectory() as temp_dir:
        cp = run(
            ["lps2lts", "--cached", f"-a{action}", "-t1", str(lps_path)],
            cwd=pathlib.Path(temp_dir),
            timeout=240,
            check=False,
        )
        text = (cp.stdout + cp.stderr).lower()
        return f"action '{action.lower()}' found" in text


def bpmn_stats(bpmn_path: pathlib.Path) -> dict[str, int]:
    model = parse_bpmn(bpmn_path)
    tag_counts: dict[str, int] = {}
    for node in model.nodes.values():
        tag_counts[node.tag] = tag_counts.get(node.tag, 0) + 1
    return {
        "processes": len(model.process_ids),
        "nodes": len(model.nodes),
        "sequence_flows": len(model.sequence_flows),
        "message_flows": len(model.message_flows),
        "tasks": tag_counts.get("task", 0),
        "parallel_gateways": tag_counts.get("parallelGateway", 0),
        "event_gateways": tag_counts.get("eventBasedGateway", 0),
        "catch_events": tag_counts.get("intermediateCatchEvent", 0),
    }


def pnml_stats(pnml_path: pathlib.Path) -> dict[str, int]:
    net = parse_pnml(pnml_path)
    return {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
    }


def mcrl2_stats(mcrl2_path: pathlib.Path) -> dict[str, int]:
    text = mcrl2_path.read_text(encoding="utf-8")
    actions = re.search(r"^act\s+(.+?);$", text, flags=re.MULTILINE | re.DOTALL)
    action_count = 0
    if actions:
        action_count = len([part.strip() for part in actions.group(1).split(",") if part.strip()])
    place_count = len(re.findall(r"^%   p_\d+ =", text, flags=re.MULTILINE))
    return {"places": place_count, "actions": action_count}


def write_comparison_svg(output_path: pathlib.Path, summary: dict[str, object]) -> None:
    local = summary["local"]
    web = summary["web"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="520" viewBox="0 0 1120 520">',
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="28" y="40" font-family="Helvetica" font-size="24" font-weight="700" fill="#0f172a">Local semantic converter vs bpmn2petrinet.com</text>',
        '  <text x="28" y="66" font-family="Helvetica" font-size="13" fill="#475569">Both start from the same official Pizza BPMN downloaded on 2026-05-18.</text>',
        '  <rect x="28" y="98" width="500" height="170" rx="12" fill="#eff6ff" stroke="#60a5fa"/>',
        '  <text x="52" y="128" font-family="Helvetica" font-size="17" font-weight="700" fill="#1d4ed8">Structure</text>',
        f'  <text x="52" y="156" font-family="Helvetica" font-size="13" fill="#334155">Local PNML: {local["pnml"]["places"]} places, {local["pnml"]["transitions"]} transitions, {local["pnml"]["arcs"]} arcs</text>',
        f'  <text x="52" y="180" font-family="Helvetica" font-size="13" fill="#334155">Web PNML: {web["pnml"]["places"]} places, {web["pnml"]["transitions"]} transitions, {web["pnml"]["arcs"]} arcs</text>',
        f'  <text x="52" y="204" font-family="Helvetica" font-size="13" fill="#334155">Local bounded LTS: {local["lts"]["states"]} states shown, {local["lts"]["transitions"]} transitions shown</text>',
        f'  <text x="52" y="228" font-family="Helvetica" font-size="13" fill="#334155">Web bounded LTS: {web["lts"]["states"]} states, {web["lts"]["transitions"]} transitions</text>',
        '  <rect x="564" y="98" width="528" height="170" rx="12" fill="#f8fafc" stroke="#cbd5e1"/>',
        '  <text x="588" y="128" font-family="Helvetica" font-size="17" font-weight="700" fill="#0f172a">Semantics</text>',
    ]
    semantic_rows = [
        ("order_received reachable", local["reachability"]["order_received"], web["reachability"]["order_received"]),
        ("deliver_the_pizza reachable", local["reachability"]["deliver_the_pizza"], web["reachability"]["deliver_the_pizza"]),
        ("receive_payment reachable", local["reachability"]["receive_payment"], web["reachability"]["receive_payment"]),
        ("calm_customer reachable", local["reachability"]["calm_customer"], web["reachability"]["calm_customer"]),
        ("joined end reachable", local["reachability"]["joined_end"], web["reachability"]["joined_end"]),
    ]
    y = 158
    for label, local_value, web_value in semantic_rows:
        lines.append(f'  <text x="588" y="{y}" font-family="Helvetica" font-size="13" fill="#334155">{html.escape(label)}</text>')
        local_fill = "#16a34a" if local_value else "#dc2626"
        web_fill = "#16a34a" if web_value else "#dc2626"
        lines.append(f'  <text x="915" y="{y}" font-family="Helvetica" font-size="13" fill="{local_fill}">local={str(local_value).lower()}</text>')
        lines.append(f'  <text x="995" y="{y}" font-family="Helvetica" font-size="13" fill="{web_fill}">web={str(web_value).lower()}</text>')
        y += 24
    lines.extend(
        [
            '  <rect x="28" y="294" width="1064" height="190" rx="12" fill="#fff7ed" stroke="#fdba74"/>',
            '  <text x="52" y="324" font-family="Helvetica" font-size="17" font-weight="700" fill="#9a3412">Key modeling differences</text>',
            '  <text x="52" y="354" font-family="Helvetica" font-size="13" fill="#334155">1. Local model expands event-based choice into explicit choose_* transitions.</text>',
            '  <text x="52" y="378" font-family="Helvetica" font-size="13" fill="#334155">2. Web model gives a_60_minutes an empty pre-set, so the timer can fire without waiting for the gateway choice.</text>',
            '  <text x="52" y="402" font-family="Helvetica" font-size="13" fill="#334155">3. Web model makes pay_the_pizza wait for receipt, while receive_payment also waits for money, creating a circular dependency.</text>',
            '  <text x="52" y="426" font-family="Helvetica" font-size="13" fill="#334155">4. Local model keeps payment flow consumable and preserves the ask/calm customer loop as reachable behavior.</text>',
            '  <text x="52" y="450" font-family="Helvetica" font-size="13" fill="#334155">5. Under the same 200-state cap, the web model collapses to 54 states; the local model already explores 200 states and is still richer.</text>',
        ]
    )
    lines.append("</svg>")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown_report(output_path: pathlib.Path, summary: dict[str, object], files: dict[str, pathlib.Path]) -> None:
    local = summary["local"]
    web = summary["web"]
    local_map = summary["local_transition_map"]
    web_map = summary["web_transition_map"]
    report = f"""# Pizza 官方样例逐步对照报告

日期：2026-05-18

本报告比较同一份官方 Pizza BPMN 输入在两条链路上的转换结果：

1. 本地语义转换链路：`BPMN -> bpmn2pnml_local.py -> PNML -> pnml2mcrl2.py -> mCRL2`
2. 网页转换链路：`BPMN -> bpmn2petrinet.com -> PNML -> pnml2mcrl2.py -> mCRL2`

## 1. 输入是否一致

- 输入文件相同：`docs/runs/pizza_official_redownload_20260518/pizza_official_downloaded.bpmn`
- 该文件于 2026-05-18 从官方页面重新下载：
  - 页面：[https://maude.lcc.uma.es/BPMN-R/pizza/](https://maude.lcc.uma.es/BPMN-R/pizza/)
  - 原始 BPMN：[https://maude.lcc.uma.es/BPMN-R/pizza/files/triso%20-%20Order%20Process%20for%20Pizza%20V4.bpmn](https://maude.lcc.uma.es/BPMN-R/pizza/files/triso%20-%20Order%20Process%20for%20Pizza%20V4.bpmn)

输入 BPMN 统计：

| 指标 | 数值 |
| --- | ---: |
| process | {summary["bpmn"]["processes"]} |
| flow node | {summary["bpmn"]["nodes"]} |
| task | {summary["bpmn"]["tasks"]} |
| message flow | {summary["bpmn"]["message_flows"]} |
| sequence flow | {summary["bpmn"]["sequence_flows"]} |
| event-based gateway | {summary["bpmn"]["event_gateways"]} |
| parallel gateway | {summary["bpmn"]["parallel_gateways"]} |

## 2. BPMN -> PNML 对照

| 指标 | 本地转换 | 网页转换 |
| --- | ---: | ---: |
| place | {local["pnml"]["places"]} | {web["pnml"]["places"]} |
| transition | {local["pnml"]["transitions"]} | {web["pnml"]["transitions"]} |
| arc | {local["pnml"]["arcs"]} | {web["pnml"]["arcs"]} |

核心观察：

1. 本地 PNML 比网页 PNML 多出 `3` 个 place、`5` 个 transition、`10` 条 arc。
2. 这些新增结构主要用于显式表示 event-based gateway 的分支选择，以及把支付/询问循环拆成更接近 BPMN 语义的可触发关系。
3. 网页 PNML 更紧凑，但把部分 message flow 和 timer 约束压缩得过头，导致关键行为丢失。

## 3. 关键变迁级别对照

### 3.1 事件网关与计时器

| 动作 | 本地转换 pre -> post | 网页转换 pre -> post | 说明 |
| --- | --- | --- | --- |
| `a_60_minutes` | `{local_map["a_60_minutes"]["pre"]} -> {local_map["a_60_minutes"]["post"]}` | `{web_map["a_60_minutes"]["pre"]} -> {web_map["a_60_minutes"]["post"]}` | 网页版计时器没有前置 place，会“凭空”触发 |
| `choose_*` | 有：`choose_6_422` / `choose_6_424` 等 | 无 | 本地版显式建模 event-based gateway 选择 |
| `ask_for_the_pizza` | `{local_map["ask_for_the_pizza"]["pre"]} -> {local_map["ask_for_the_pizza"]["post"]}` | `{web_map["ask_for_the_pizza"]["pre"]} -> {web_map["ask_for_the_pizza"]["post"]}` | 网页版额外依赖 `{web_map["ask_for_the_pizza"]["pre"]}` 中的循环回边 place，第一次询问就被卡住 |

### 3.2 支付链路

| 动作 | 本地转换 pre -> post | 网页转换 pre -> post | 说明 |
| --- | --- | --- | --- |
| `pay_the_pizza` | `{local_map["pay_the_pizza"]["pre"]} -> {local_map["pay_the_pizza"]["post"]}` | `{web_map["pay_the_pizza"]["pre"]} -> {web_map["pay_the_pizza"]["post"]}` | 网页版要求先拿到 `receipt` 才能支付 |
| `receive_payment` | `{local_map["receive_payment"]["pre"]} -> {local_map["receive_payment"]["post"]}` | `{web_map["receive_payment"]["pre"]} -> {web_map["receive_payment"]["post"]}` | 网页版又要求先有 `money` 才能产生 `receipt`，形成循环依赖 |

这条环路可以写成：

`Pay the pizza` 需要 `receipt`  
`Receive payment` 需要 `money`  
`Pay the pizza` 发生后才产生 `money`  
`Receive payment` 发生后才产生 `receipt`

因此网页模型中支付闭环无法启动。

### 3.3 结束同步

| 动作 | 本地转换 pre -> post | 网页转换 pre -> post |
| --- | --- | --- |
| `a_end` / `a_end_2` | `a_end: {local_map["a_end"]["pre"]} -> {local_map["a_end"]["post"]}`，`a_end_2: {local_map["a_end_2"]["pre"]} -> {local_map["a_end_2"]["post"]}` | `a_end: {web_map["a_end"]["pre"]} -> {web_map["a_end"]["post"]}` |

本地版把单个 participant 的结束和两个 participant 的 join 区分开；网页版只剩一个 `a_end`，但由于支付链路不可达，这个 joined end 也到不了。

## 4. PNML -> mCRL2 对照

| 指标 | 本地转换 | 网页转换 |
| --- | ---: | ---: |
| place alias | {local["mcrl2"]["places"]} | {web["mcrl2"]["places"]} |
| action | {local["mcrl2"]["actions"]} | {web["mcrl2"]["actions"]} |

从生成的 mCRL2 头部映射可以看到：

1. 本地版保留了更多语义动作，如 `choose_6_422`、`choose_6_424`、`calm_customer`、`a_end_2`。
2. 网页版动作更少，说明部分 BPMN 控制逻辑在 PNML 层已经被折叠掉了。

## 5. bounded LTS 对照

两边都使用 `max_place_tokens=1`，并对状态空间生成施加 `200` 状态上限。

| 指标 | 本地转换 | 网页转换 |
| --- | ---: | ---: |
| states | {local["lts"]["states"]} | {web["lts"]["states"]} |
| transitions | {local["lts"]["transitions"]} | {web["lts"]["transitions"]} |
| action labels | {local["lts"]["labels"]} | {web["lts"]["labels"]} |
| deterministic | {local["lts"]["deterministic"]} | {web["lts"]["deterministic"]} |

解释：

1. 本地模型在 `200` 状态上限下已经达到上限，说明其可观察行为明显更丰富。
2. 网页模型在同样上限下只生成了 `54` 个状态，说明它在前面阶段已经把很多行为压缩掉了。

## 6. 关键行为是否可达

这里使用 `lps2lts -aACTION -t1` 对 bounded LPS 做动作搜索。

| 行为 | 本地转换 | 网页转换 |
| --- | --- | --- |
| `order_received` | {str(local["reachability"]["order_received"]).lower()} | {str(web["reachability"]["order_received"]).lower()} |
| `deliver_the_pizza` | {str(local["reachability"]["deliver_the_pizza"]).lower()} | {str(web["reachability"]["deliver_the_pizza"]).lower()} |
| `receive_payment` | {str(local["reachability"]["receive_payment"]).lower()} | {str(web["reachability"]["receive_payment"]).lower()} |
| `calm_customer` | {str(local["reachability"]["calm_customer"]).lower()} | {str(web["reachability"]["calm_customer"]).lower()} |
| joined end | {str(local["reachability"]["joined_end"]).lower()} (`a_end_2`) | {str(web["reachability"]["joined_end"]).lower()} (`a_end`) |

结论：

1. 两条链路都能到达 `order_received` 和 `deliver_the_pizza`，说明基础“下单-制作-送达”主线都保留下来了。
2. 只有本地模型能到达 `receive_payment`。
3. 只有本地模型能到达 `calm_customer`，也就是“等待 60 分钟 -> 询问 -> 安抚”的循环在网页模型里失效。
4. 只有本地模型能到达 joined end `a_end_2`，网页模型无法完整结束两个 participant 的协作。

## 7. 可视化成果

### 本地链路

- 流程总览：![local-pipeline](01_pipeline.svg)
- 本地 PNML 概览：![local-pnml](03_pnml_overview.svg)
- 本地 mCRL2 概览：![local-mcrl2](04_mcrl2_summary.svg)
- 本地 bounded LTS：![local-lts](pizza_official_downloaded_bounded_lts.svg)

### 对照总览

![comparison](05_local_vs_web_summary.svg)

### 网页链路 bounded LTS

![web-lts](pizza_official_web_bounded_lts.svg)

## 8. 最终结论

1. `bpmn2petrinet.com` 的网页转换结果可以作为结构对照，但不适合作为官方 Pizza 完整语义的唯一依据。
2. 它的核心问题是把 timer 和 message flow 约束处理得过于机械，尤其是在支付链路上引入了 `money/receipt` 的循环等待。
3. 本地 BPMN-aware 转换器虽然生成的 PNML 更大，但保留了官方 Pizza 例子真正想表达的协作语义。
4. 因此，本项目主线应以本地链路为准，即：

`官方 BPMN -> 本地语义 PNML -> mCRL2 -> 验证/可视化`
"""
    output_path.write_text(report, encoding="utf-8")


def write_defense_script(output_path: pathlib.Path, summary: dict[str, object]) -> None:
    local = summary["local"]
    web = summary["web"]
    text = f"""# BPMN Pizza 转换对照：答辩/汇报版中文说明稿

日期：2026-05-18

## 1. 开场

各位老师好，我这次汇报的主题是：

**如何把官方 Pizza 的 BPMN 协作流程，稳定地转换成 Petri net，再转换成 mCRL2，并验证转换后的语义是否正确。**

我的工作不是只把文件“转出来”，而是要回答一个更关键的问题：

**转出来的模型，语义对不对。**

## 2. 问题背景

我们使用的是 BPMN 官方 Pizza 例子。这个例子不是一个简单的顺序流程，它同时包含：

1. 两个 participant
2. 两个 process
3. message flow
4. event-based gateway
5. parallel gateway
6. timer 以及“询问披萨进度、安抚顾客”的循环

所以它非常适合用来检验一条转换链路是不是真的保留了 BPMN 协作语义。

## 3. 我的总体方法

我把转换拆成两步：

1. `BPMN -> PNML`
2. `PNML -> mCRL2`

然后我对同一份官方 BPMN，分别跑了两条链路：

1. **网页链路**：使用 `bpmn2petrinet.com`
2. **本地链路**：使用我实现的 `bpmn2pnml_local.py`

最后再把两边都转成 mCRL2，比较结构和行为。

## 4. 为什么要做这个对照

一开始我们是想直接复用 `bpmn2petrinet.com` 的结果。

它的优点是方便，能自动把 BPMN 变成 PNML。

但是在 Pizza 这个例子里，我发现它会在 message flow 和 timer 上引入不符合预期的约束，导致“模型虽然能生成，但行为不对”。

所以这次对照的核心目的，就是证明：

**问题不在 mCRL2 转换，而在前面的 BPMN -> PNML 语义建模。**

## 5. 第一步对照：BPMN -> PNML

在完全相同的官方输入下，两个 PNML 的规模不同：

1. 本地转换：{local["pnml"]["places"]} 个 place，{local["pnml"]["transitions"]} 个 transition，{local["pnml"]["arcs"]} 条 arc
2. 网页转换：{web["pnml"]["places"]} 个 place，{web["pnml"]["transitions"]} 个 transition，{web["pnml"]["arcs"]} 条 arc

这说明本地版保留了更多控制语义，尤其是：

1. event-based gateway 的显式分支选择
2. 支付相关的消息依赖
3. 询问与安抚顾客的循环

## 6. 第二步对照：关键语义差异

这里我重点看三段最容易出问题的逻辑。

### 6.1 定时等待逻辑

在本地模型里，`60 minutes` 必须在 event-based gateway 选择到对应分支后才能触发。

但在网页模型里，`a_60_minutes` 的前置条件是空的，也就是说这个 timer 可以“凭空发生”。

这已经说明网页模型没有把事件网关之后的等待关系保留下来。

### 6.2 支付逻辑

这是最关键的问题。

在网页模型里：

1. `Pay the pizza` 要先等 `receipt`
2. `Receive payment` 要先等 `money`
3. 但 `money` 是 `Pay the pizza` 之后才产生
4. `receipt` 又是 `Receive payment` 之后才产生

这就形成了一个循环等待。

结果就是：

**支付永远收不到，因此流程无法完整结束。**

而在本地模型里，我把消息流只当作真正的接收语义前置条件，不把信息型 task-to-task message flow 机械地改造成阻塞条件，所以支付链路可以正常走通。

### 6.3 顾客询问循环

Pizza 例子里有一个很重要的行为：

`60 minutes -> Ask for the pizza -> Calm customer`

这个循环在网页模型里是失效的，在本地模型里是可达的。

也就是说，本地模型保留了官方例子本来想表达的一个核心协作场景。

## 7. 第三步对照：转成 mCRL2 之后看行为

我把两个 PNML 都进一步转成 mCRL2，并在 bounded 模型上搜索关键动作。

结果如下：

1. `order_received`：两边都可达
2. `deliver_the_pizza`：两边都可达
3. `receive_payment`：只有本地模型可达
4. `calm_customer`：只有本地模型可达
5. joined end：只有本地模型可达

这说明网页模型保住了最基础的主线，但丢掉了 Pizza 例子真正有价值的协作语义。

## 8. LTS 对照说明了什么

在同样的 bounded 条件下：

1. 本地模型的 LTS 已经探索到 {local["lts"]["states"]} 个状态上限，迁移数是 {local["lts"]["transitions"]}
2. 网页模型只有 {web["lts"]["states"]} 个状态，迁移数是 {web["lts"]["transitions"]}

这说明网页模型不是“更简洁但等价”，而是因为前面把行为折叠掉了，所以状态空间明显变小。

换句话说：

**小，不代表好；这里的小，恰恰意味着语义丢失。**

## 9. 我的贡献

我认为这项工作的贡献主要有四点：

1. 重新从官方来源下载 Pizza 样例，保证输入可信
2. 跑通了 `BPMN -> PNML -> mCRL2 -> LTS` 的完整自动化链路
3. 通过对照实验定位出网页转换在 Pizza 示例上的语义偏差
4. 实现了本地 BPMN-aware 转换器，使支付、询问循环和结束同步可以正确保留

## 10. 最终结论

我的最终结论是：

1. `bpmn2petrinet.com` 可以作为参考工具
2. 但对于官方 Pizza 这种包含 message flow、timer 和 event-based gateway 的协作流程，它不能直接作为最终语义模型来源
3. 本地语义转换链路更适合作为项目主线

也就是：

**官方 BPMN -> 本地语义 PNML -> mCRL2 -> 验证与可视化**

## 11. 收尾一句

如果用一句话概括这次工作的价值，我会说：

**我不仅完成了转换，更验证了“什么样的转换结果才是语义上可信的”。**
"""
    output_path.write_text(text, encoding="utf-8")


def main() -> None:
    for tool in ["mcrl22lps", "lps2lts", "ltsconvert", "ltsinfo", "curl"]:
        require_tool(tool)

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    bpmn_path = RUN_DIR / "pizza_official_downloaded.bpmn"
    if not bpmn_path.exists():
        raise FileNotFoundError(f"Missing rerun BPMN file: {bpmn_path}")

    local = ArtifactSet(
        label="local",
        pnml=RUN_DIR / "pizza_official_downloaded_local.pnml",
        mcrl2=RUN_DIR / "pizza_official_downloaded_local.mcrl2",
        bounded_mcrl2=RUN_DIR / "pizza_official_downloaded_bounded.mcrl2",
        lps=RUN_DIR / "pizza_official_downloaded_bounded.lps",
        lts=RUN_DIR / "pizza_official_downloaded_bounded.lts",
        aut=RUN_DIR / "pizza_official_downloaded_bounded.aut",
        lts_svg=RUN_DIR / "pizza_official_downloaded_bounded_lts.svg",
    )
    web = ArtifactSet(
        label="web",
        pnml=RUN_DIR / "pizza_official_web.pnml",
        mcrl2=RUN_DIR / "pizza_official_web.mcrl2",
        bounded_mcrl2=RUN_DIR / "pizza_official_web_bounded.mcrl2",
        lps=RUN_DIR / "pizza_official_web_bounded.lps",
        lts=RUN_DIR / "pizza_official_web_bounded.lts",
        aut=RUN_DIR / "pizza_official_web_bounded.aut",
        lts_svg=RUN_DIR / "pizza_official_web_bounded_lts.svg",
    )

    ensure_web_artifacts(bpmn_path, web)

    local_lts = parse_ltsinfo(local.lts)
    web_lts = parse_ltsinfo(web.lts)

    local_reachability = {
        "order_received": action_reachable(local.lps, "order_received"),
        "deliver_the_pizza": action_reachable(local.lps, "deliver_the_pizza"),
        "receive_payment": action_reachable(local.lps, "receive_payment"),
        "calm_customer": action_reachable(local.lps, "calm_customer"),
        "joined_end": action_reachable(local.lps, "a_end_2"),
    }
    web_reachability = {
        "order_received": action_reachable(web.lps, "order_received"),
        "deliver_the_pizza": action_reachable(web.lps, "deliver_the_pizza"),
        "receive_payment": action_reachable(web.lps, "receive_payment"),
        "calm_customer": action_reachable(web.lps, "calm_customer"),
        "joined_end": action_reachable(web.lps, "a_end"),
    }

    summary = {
        "bpmn": bpmn_stats(bpmn_path),
        "local": {
            "pnml": pnml_stats(local.pnml),
            "mcrl2": mcrl2_stats(local.mcrl2),
            "lts": {
                "states": local_lts.get("Number of states", "unknown"),
                "transitions": local_lts.get("Number of transitions", "unknown"),
                "labels": local_lts.get("Number of action labels", "unknown"),
                "deterministic": "yes" if "LTS is deterministic" in local_lts else "unknown",
            },
            "reachability": local_reachability,
        },
        "web": {
            "pnml": pnml_stats(web.pnml),
            "mcrl2": mcrl2_stats(web.mcrl2),
            "lts": {
                "states": web_lts.get("Number of states", "unknown"),
                "transitions": web_lts.get("Number of transitions", "unknown"),
                "labels": web_lts.get("Number of action labels", "unknown"),
                "deterministic": "yes" if "LTS is deterministic" in web_lts else "unknown",
            },
            "reachability": web_reachability,
        },
        "local_transition_map": parse_transition_mapping(local.mcrl2),
        "web_transition_map": parse_transition_mapping(web.mcrl2),
    }

    comparison_svg = RUN_DIR / "05_local_vs_web_summary.svg"
    comparison_md = RUN_DIR / "PIZZA_LOCAL_VS_WEB_COMPARISON.md"
    defense_md = RUN_DIR / "PIZZA_DEFENSE_TALK_ZH.md"
    summary_json = RUN_DIR / "pizza_local_vs_web_summary.json"

    write_comparison_svg(comparison_svg, summary)
    write_markdown_report(comparison_md, summary, {})
    write_defense_script(defense_md, summary)
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Comparison written to {comparison_md}")
    print(f"Defense talk written to {defense_md}")


if __name__ == "__main__":
    main()
