# sshtm

Interactive SSH tunnel manager with a terminal UI.

Create, start, stop, and manage SSH port-forwarding tunnels from a single TUI dashboard. Tunnels persist as background SSH processes and survive after exiting sshtm — on next launch it automatically reconnects to any active tunnels.

## Features

- **Local forwarding** (`-L`) and **remote forwarding** (`-R`)
- Persistent background tunnels via SSH ControlMaster multiplexing
- SSH config integration — pick hosts from `~/.ssh/config` or enter credentials manually
- Tunnel history for quick re-creation
- Periodic health checks with live status indicators
- Works on Linux and WSL

## Requirements

- Python 3.11+
- OpenSSH client with ControlMaster support

## Installation

```bash
git clone <repo-url> && cd sshtm
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or with pip directly:

```bash
pip install -r requirements.txt
pip install -e .
```

For development dependencies (pytest, textual-dev):

```bash
pip install -e ".[dev]"
```

## Usage

```bash
sshtm
```

Or run as a module:

```bash
python -m sshtm
```

### Keybindings

| Key     | Action                        |
|---------|-------------------------------|
| `n`     | Create a new tunnel           |
| `s`     | Start / stop selected tunnel  |
| `e`     | Edit selected tunnel          |
| `d`     | Delete selected tunnel        |
| `r`     | Refresh tunnel states         |
| `Enter` | Start / stop selected tunnel  |
| `?`     | Show help                     |
| `q`     | Quit                          |

Arrow keys navigate the tunnel list. The cursor wraps through an unselected state between the last and first rows.

## Configuration

Tunnel definitions and history are stored in `~/.config/sshtm/`:

```
~/.config/sshtm/
├── tunnels.toml    # Saved tunnel definitions
└── history.toml    # Recent tunnel configurations
```

## How It Works

sshtm uses SSH ControlMaster to maintain a single master connection per remote host. Individual tunnels are added and removed via `ssh -O forward` and `ssh -O cancel` on the existing master socket. This means:

- Multiple tunnels to the same host share one SSH connection
- Tunnels survive sshtm exit (the master process runs in the background)
- On restart, sshtm detects running masters and reconciles state

## Project Structure

```
src/sshtm/
├── app.py                 # Textual app shell, keybindings, worker-based SSH ops
├── __main__.py            # CLI entry point
├── config/
│   ├── paths.py           # XDG path resolution
│   └── storage.py         # TOML read/write with atomic saves
├── core/
│   ├── tunnel.py          # Tunnel dataclass, Direction/Status enums
│   ├── manager.py         # ControlMaster lifecycle, forward/cancel
│   ├── process.py         # PID file tracking, stale cleanup
│   ├── health.py          # Port checks, master alive checks
│   └── ssh_config.py      # SSH config parser (via sshconf)
├── screens/
│   ├── main.py            # Main screen with tunnel table
│   ├── tunnel_form.py     # Tunnel creation/edit modal
│   └── help.py            # Help screen
├── widgets/
│   └── tunnel_table.py    # DataTable subclass with wraparound cursor
└── css/
    └── app.tcss           # Textual CSS styles
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## License

MIT
