# mibe

[![CI](https://github.com/yihong0618/mibe/actions/workflows/ci.yml/badge.svg)](https://github.com/yihong0618/mibe/actions/workflows/ci.yml)

Monitor Codex / Kimi session logs and broadcast task status via Xiaomi smart speaker.

## Notes

Voice broadcast content can be customized through configuration file.

## Quick Start

Refer to the project [MiService](https://github.com/yihong0618/MiService)

```bash
# Install dependencies
uv venv
uv sync

# Set environment variables
export MI_USER="Your Xiaomi Account"
export MI_PASS="Your Xiaomi Password"
export MI_DID="Device miotDID"  # Optional, uses first device if not set


# Verify login & list devices
uv run python mibe.py login

# Start monitoring
uv run python mibe.py monitor
```

## Subcommands

| Command | Description |
|---------|-------------|
| `login` | Test login, list available devices |
| `monitor` | Monitor Codex/Kimi logs and broadcast |

`monitor` optional arguments:

- `--replay-existing {none,latest,all}` — Replay existing logs on startup (default: `none`)
- `--verbose` — Verbose logging
- `--codex-only` — Monitor Codex sessions only
- `--kimi-only` — Monitor Kimi sessions only
- `-c, --config PATH` — Specify configuration file path

## Behavior

| Event | Broadcast | Action |
|-------|-----------|--------|
| Codex `task_started` | codex started | Mute after broadcast, send silent TTS periodically to keep light on |
| Codex `task_complete` | codex completed | Restore volume, then broadcast |
| Codex `turn_aborted` | codex aborted | Restore volume, then broadcast |
| Kimi `TurnBegin` | kimi started | Mute after broadcast, send silent TTS periodically to keep light on |
| Kimi `TurnEnd` | kimi completed | Restore volume, then broadcast |

Volume is automatically restored on exit (Ctrl+C / SIGTERM).

## Configuration File

Supports customization of broadcast messages and settings via TOML configuration file.

Configuration file search paths (in priority order):
1. Path specified by `-c, --config`
2. `./config.toml`
3. `~/.config/mibe/config.toml`

### Example Configuration

```toml
[messages]
# Codex related messages
codex_started = "codex started"
codex_complete = "codex completed"
codex_aborted = "codex aborted"

# Kimi related messages
kimi_started = "kimi started"
kimi_complete = "kimi completed"

[settings]
# Silence duration for Kimi completion detection (seconds)
kimi_completion_silence = 2.0
```

Copy `config.toml.example` as a starting point:

```bash
cp config.toml.example config.toml
# Edit config.toml to customize your broadcast messages
```

## Thanks

- yetone
