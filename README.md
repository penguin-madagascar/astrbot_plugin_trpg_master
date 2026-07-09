# LLM TRPG 跑团插件

![LLM TRPG 跑团插件 Logo](logo.png)

`astrbot_plugin_trpg_master` 是一个面向 AstrBot 的 LLM TRPG/跑团插件。插件由模型扮演 GM/KP 推动叙事，Python 代码负责骰子、关键判定、角色状态、战役记忆、日志导出和持久化，避免把随机结果和重要状态完全交给模型自由生成。

当前版本：`0.1.0`

## 功能特性

- 通过 `/trpg_start` 启动中文、英文、日文或韩文跑团。
- 支持玩家加入、角色预设、角色卡查看、行动顺序、状态查看和战役回顾。
- 支持剧本玩法模式：简易、进阶和自定义。
- 支持规则系统：内置 `d20_lite` 与 `coc7_lite`，剧本可指定规则并配置检定节点。
- 行动顺序支持两种模式：剧本级 `llm_gm`（LLM 主持人强控制）和 `soft`（玩家软顺序）。
- 支持基础骰子表达式和 GIF 掷骰结果，依赖 `Pillow`。
- 支持 GM 返回结构化 JSON，由插件执行骰子请求、应用白名单状态变更并记录日志。
- 支持战役知识库、线索、剧情线、实体、事实和关系记录。
- 支持 Markdown 日志导出。
- 提供 AstrBot 插件 WebGUI，用于管理插件配置、剧本和战役知识库。

## 安装

在 AstrBot 的插件目录中克隆本仓库：

```bash
cd AstrBot/data/plugins
git clone https://github.com/penguin-madagascar/astrbot_plugin_trpg_master.git
```

AstrBot 安装插件时会读取仓库根目录的 `metadata.yaml` 和 `requirements.txt`。本插件当前只声明一个第三方依赖：

```text
Pillow>=10.0.0
```

安装或更新后，在 AstrBot WebUI 的插件管理中启用或重载本插件。

## 支持平台

`metadata.yaml` 当前声明支持以下 AstrBot 平台适配器：

- `aiocqhttp`
- `qq_official`
- `telegram`
- `discord`

## 配置

插件配置由 `_conf_schema.json` 声明，可在 AstrBot WebUI 的插件配置页或本插件 WebGUI 中调整。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `default_theme` | `奇幻冒险` | `/trpg_start` 未指定主题时使用的默认主题。 |
| `default_ruleset_id` | `d20_lite` | 自由主题跑团使用的默认规则系统；匹配剧本时以剧本内 `ruleset_id` 为准。可用值：`d20_lite`、`coc7_lite`。 |
| `gm_system_prompt` | 内置提示词 | 约束 GM/KP 的叙事、骰子请求和状态变更输出。 |
| `max_recent_events` | `20` | 近期事件保留上限，超出后尝试压缩剧情摘要。 |
| `max_timeline_events` | `80` | 战役时间线保留上限。 |
| `max_turns` | `200` | 单个跑团最大回合数。 |
| `allow_state_patch` | `true` | 是否允许应用 GM JSON 中的白名单状态变更。 |
| `second_pass_resolution` | `true` | 掷骰和状态校验后是否请求模型生成二次结算叙事。 |
| `response_language` | `zh` | 旧数据缺失语言字段时的兜底回复语言。 |
| `strict_json_patch` | `true` | 是否只解析 fenced JSON。 |
| `command_agent_enabled` | `true` | 跑团中是否把自然语言转换为 `/trpg_*` 命令。 |
| `turn_order_enabled` | `true` | 新跑团是否启用多人行动顺序。 |
| `turn_order_mode` | `llm_gm` | 自由主题跑团的行动顺序兜底模式；匹配剧本时以剧本内设置为准。可用值：`llm_gm`、`soft`。 |

## 指令

| 指令 | 说明 |
| --- | --- |
| `/trpg_help` | 显示帮助。 |
| `/trpg_start [简易\|进阶] [主题或剧本名]` | 启动新的跑团；自由主题未指定模式时默认简易模式。 |
| `/trpg_join <角色名> <一句话设定>` | 加入当前跑团并创建角色。 |
| `/trpg_join preset:<名称>` | 使用自己的角色预设加入跑团。 |
| `/trpg_preset create <名称> <一句话设定>` | 创建角色预设。 |
| `/trpg_preset list` | 列出自己的角色预设。 |
| `/trpg_preset show <名称>` | 查看角色预设。 |
| `/trpg_preset update <名称> <属性名称> <新值>` | 修改角色预设字段。 |
| `/trpg_pc` | 查看自己的角色卡。 |
| `/trpg_status` | 查看当前跑团状态。 |
| `/trpg_turn [done|next]` | 查看或推进行动顺序。 |
| `/trpg_recap` | 查看玩家可见的战役回顾。 |
| `/trpg_memory <关键词>` | 搜索玩家可见的战役记忆。 |
| `/trpg_clues` | 查看玩家可见线索。 |
| `/trpg_act <行动内容>` | 提交玩家行动并推进剧情。 |
| `/trpg_roll <表达式>` | 掷基础骰子表达式，例如 `1d20+3`。 |
| `/trpg_end` | 结束当前跑团。 |
| `/trpg_export` | 导出当前跑团 Markdown 日志。 |

如果 `command_agent_enabled` 开启，跑团进行中玩家也可以直接发送自然语言，插件会尝试转换为当前阶段允许的 `/trpg_*` 命令。普通非 TRPG 斜杠命令不会被本插件拦截。

## 规则系统

跑团会话和剧本都带有 `ruleset_id`。自由主题跑团使用全局 `default_ruleset_id`；使用 `/trpg_start 剧本名` 命中剧本时，使用剧本自身规则。

- `d20_lite`：支持 d20 属性/技能检定、豁免、优势/劣势、对抗检定、基础伤害和治疗。
- `coc7_lite`：支持 d100 技能/属性检定、普通/困难/极难成功等级、奖励/惩罚骰和 SAN 检定。

GM JSON 中的 `dice_requests` 会由当前规则系统解析，模型不能直接写死骰点。规则检定生成的状态变化会和 GM 提出的 `state_patches` 一起通过白名单校验；常用状态操作包括 `hp_delta`、`san_delta`、`damage`、`heal`、`resource_delta`、`skill_delta`、`add_status` 和 `remove_status`。

角色预设也带有 `ruleset_id`。使用 `/trpg_join preset:<名称>` 时，预设规则必须与当前跑团规则一致。

## 玩法模式

跑团会话会记录 `play_mode` 和一组核心机制开关。使用 `/trpg_start 剧本名` 命中剧本时，默认使用剧本自身模式；旧剧本缺失模式字段时按进阶模式处理，保留既有复杂机制。使用 `/trpg_start 海上奇遇` 这类一句话自由主题创建时，如果没有写明模式，默认使用简易模式。也可以显式使用 `/trpg_start 进阶 海上奇遇`。

- `simple` / 简易模式：保留 `/trpg_join` 角色加入流程，但关闭命令转换 Agent、行动顺序、结构化 JSON、骰子检定、状态补丁、战役知识库和二次结算。GM 可以像轻量文字冒险一样只返回纯叙事文本。
- `advanced` / 进阶模式：接近此前默认跑团行为，启用绝大部分机制；命令转换、状态补丁和二次结算仍尊重插件全局配置。
- `custom` / 自定义模式：使用剧本内 `feature_flags` 逐项控制核心机制。可用开关包括 `command_agent_enabled`、`turn_order_enabled`、`structured_patch_enabled`、`dice_requests_enabled`、`state_patch_enabled`、`knowledge_enabled` 和 `second_pass_resolution_enabled`。

## 行动顺序模式

每个剧本可以单独设置行动顺序模式，使用 `/trpg_start 剧本名` 启动时会覆盖全局配置；只有自由主题跑团才使用 `turn_order_mode` 全局兜底。

- `llm_gm`：LLM 作为当前团主持人，通过 GM JSON 中的 `turn_controls` 提出设置队列、切换当前行动者、推进、暂停或恢复等控制意图，插件校验后应用。玩家的 `/trpg_turn done|next` 会作为请求交给 LLM 裁定，不会直接改队列。
- `soft`：玩家软顺序。当前行动者可以用 `/trpg_turn done|next` 直接推进；当前行动者提交 `/trpg_act` 后也会自动推进到下一位。非当前行动者直接行动时会收到顺序提示，但仍可执行。

## WebGUI

插件会注册 AstrBot 插件页面，用于：

- 编辑和删除剧本。
- 为每个剧本选择简易、进阶或自定义玩法模式。
- 自定义模式下逐项启用或关闭核心机制。
- 为每个剧本选择行动顺序模式。
- 为每个剧本选择规则系统并编辑检定节点 JSON。
- 导入 Markdown 或 JSON 剧本；Markdown 可用 `## 模式` 指定 `simple`/`advanced`/`custom`，可用 `## 机制开关` 填写 `feature_flags` JSON 对象，可用 `## 行动顺序`、`## turn_order_mode` 或 `## turn order` 指定 `llm_gm`/`soft`，可用 `## 规则` 指定 `ruleset_id`，可用 `## 检定节点` 填写 JSON 对象或对象数组。
- 导出剧本 JSON。
- 查看战役知识库。
- 调整 `_conf_schema.json` 中声明的插件配置。

剧本保存后可通过 `/trpg_start 剧本名` 启动。

## 数据存储

插件通过 `StarTools.get_data_dir("astrbot_plugin_trpg_master")` 获取 AstrBot 插件数据目录，并优先使用 AstrBot KV；同时保留本地 JSON 文件作为兜底。会话、角色预设、剧本、掷骰 GIF 和导出日志都存储在插件数据目录下。

不要把运行时生成的 `data/`、`exports/`、`.venv/`、`__pycache__/` 或 `.pytest_cache/` 提交到插件仓库。它们已在 `.gitignore` 或 `.gitattributes` 中排除。

## 开发与测试

本仓库包含本地测试桩，可以在不启动 AstrBot 本体的情况下测试核心逻辑：

```bash
.venv/bin/python -m pytest
```

如果需要新建本地开发环境，安装测试依赖：

```bash
python3 -m pip install -r requirements-dev.txt
```

发布前建议检查：

```bash
git diff --check
git status --short
```

## 发布说明

- 插件元数据位于 `metadata.yaml`，当前版本为 `0.1.0`。
- AstrBot 插件市场使用 GitHub 托管插件，发布前仓库需要保持 public。
- AstrBot 插件市场限制插件 zip 包大小不超过 16MB。
- 本仓库已提供 1:1 比例、256x256 尺寸的 `logo.png`，可作为 AstrBot 插件 Logo。

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
