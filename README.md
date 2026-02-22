# mibe

[![CI](https://github.com/yihong0618/mibe/actions/workflows/ci.yml/badge.svg)](https://github.com/yihong0618/mibe/actions/workflows/ci.yml)

监听 Codex / Kimi 会话日志，通过小爱音箱播报任务状态。

## Notes

语音播报内容可以通过配置文件自定义

## 快速开始

参考项目 [MiService](https://github.com/yihong0618/MiService)

```bash
# 安装依赖
uv venv
uv sync

# 设置环境变量
export MI_USER="小米账号"
export MI_PASS="小米密码"
export MI_DID="设备miotDID"  # 可选，不设则用第一个设备


# 验证登录 & 查看设备
uv run python mibe.py login

# 开始监听
uv run python mibe.py monitor
```

## 子命令

| 命令 | 说明 |
|------|------|
| `login` | 测试登录，列出可用设备 |
| `monitor` | 监听 Codex/Kimi 日志并播报 |

`monitor` 可选参数：

- `--replay-existing {none,latest,all}` — 启动时回放已有日志（默认 `none`）
- `--verbose` — 详细日志
- `--codex-only` — 仅监听 Codex 会话
- `--kimi-only` — 仅监听 Kimi 会话
- `-c, --config PATH` — 指定配置文件路径

## 行为

| 事件 | 播报 | 动作 |
|------|------|------|
| Codex `task_started` | codex启动 | 播完后静音，定时发送静默 TTS 保持亮灯 |
| Codex `task_complete` | codex完成 | 恢复音量后播报 |
| Codex `turn_aborted` | codex中断 | 恢复音量后播报 |
| Kimi `TurnBegin` | kimi启动 | 播完后静音，定时发送静默 TTS 保持亮灯 |
| Kimi `TurnEnd` | kimi完成 | 恢复音量后播报 |

退出时（Ctrl+C / SIGTERM）自动恢复音量。

## 配置文件

支持通过 TOML 配置文件自定义播报消息和设置。

配置文件搜索路径（按优先级）：
1. `-c, --config` 指定的路径
2. `./config.toml`
3. `~/.config/mibe/config.toml`

### 示例配置

```toml
[messages]
# Codex 相关消息
codex_started = "codex启动"
codex_complete = "codex完成"
codex_aborted = "codex中断"

# Kimi 相关消息
kimi_started = "kimi启动"
kimi_complete = "kimi完成"

[settings]
# Kimi 完成检测的静音时间（秒）
kimi_completion_silence = 2.0
```

复制 `config.toml.example` 作为起点：

```bash
cp config.toml.example config.toml
# 编辑 config.toml 自定义你的播报消息
```

## 感谢

- yetone
