# claude-colab

Give Claude Code GPU access via Google Colab.

AI coding agents can read files, run bash, and edit code — but they have zero GPU access. claude-colab bridges that gap using Colab's free T4 GPU.

## How It Works

```
Colab (T4 GPU)                              Your Mac / PC
┌─────────────────────────┐                 ┌──────────────────────┐
│ Flask API               │                 │ claude-colab CLI     │
│  /exec, /python,        │◄── HTTPS ──────►│  or                  │
│  /upload, /download     │    (tunnel)     │ MCP Server           │
│                         │  E2E encrypted  │  (Claude Code tools) │
│ Bearer token + Fernet   │                 │                      │
└─────────────────────────┘                 └──────────────────────┘
```

1. Open one Colab notebook, hit "Run All"
2. Copy the connection string
3. Claude Code gains GPU access

## Quick Start

### Install

Requires Python 3.10+.

```bash
pip install claude-colab
```

### Start the Colab server

Open [`notebooks/claude_colab_server.ipynb`](notebooks/claude_colab_server.ipynb) in Google Colab. Set runtime to **T4 GPU**. Pick a tunnel in Cell 1, run all cells, and copy the connection string.

#### Choose a tunnel

| Tunnel | Account | When to use |
|--------|---------|-------------|
| `cloudflare` (default) | None | Works on most networks |
| `ngrok` | Free [ngrok account](https://dashboard.ngrok.com) | Your network blocks `*.trycloudflare.com` |

For ngrok, add your authtoken in Colab's 🔑 **Secrets** tab as `NGROK_AUTHTOKEN` and enable notebook access. A fallback form field exists, but it saves the token in the notebook.

If `claude-colab status` reports `Cannot reach ...`, check whether Cloudflare quick tunnels are blocked on your network:

```bash
curl -I https://trycloudflare.com   # a connection timeout means blocked, so switch to ngrok
```

### Connect

```bash
claude-colab connect cc://TOKEN:KEY@your-tunnel.trycloudflare.com   # or ...@xxxx.ngrok-free.app
```

### Use it

```bash
claude-colab status                          # GPU info
claude-colab exec "nvidia-smi"               # Run shell commands
claude-colab python -c "import torch; print(torch.cuda.get_device_name(0))"
claude-colab upload model.py /content/model.py
claude-colab download /content/results.csv ./results.csv
```

## MCP Server (Claude Code Integration)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "claude-colab": {
      "command": "claude-colab",
      "args": ["mcp-serve"]
    }
  }
}
```

Claude Code now has 5 GPU tools:

| Tool | What it does |
|------|-------------|
| `colab_status` | GPU info, VRAM, disk, uptime |
| `colab_exec` | Run shell commands |
| `colab_python` | Execute Python code |
| `colab_upload` | Upload files to Colab |
| `colab_download` | Download files from Colab |

### Example

```
You: "Benchmark this model on the GPU"

Claude:
1. colab_status → Tesla T4, 15GB VRAM
2. colab_upload → sends model.py
3. colab_exec → "pip install torch transformers"
4. colab_exec → "python model.py"
5. colab_download → fetches results.json
```

## Connection Safety

The connection string contains your auth token and encryption key. Three ways to connect:

```bash
# Direct (convenient, visible in shell history)
claude-colab connect cc://TOKEN:KEY@host

# Interactive prompt (nothing in history)
claude-colab connect

# Pipe from clipboard (nothing in ps aux or history)
pbpaste | claude-colab connect -
```

## Security

### E2E Encryption

All request and response bodies are encrypted with [Fernet](https://cryptography.io/en/latest/fernet/) (AES-128-CBC + HMAC-SHA256). The encryption key is generated per Colab session and is separate from the bearer token.

| Actor | Can see | Cannot see |
|-------|---------|------------|
| Random user | Nothing (no token) | Everything |
| Tunnel provider (Cloudflare / ngrok) | URL paths, timing, token | Request/response bodies |
| Google (Colab) | Everything on the VM | Your local files |

### What we don't protect against

- Google seeing data on the Colab VM — it's their hardware
- Arbitrary code execution on Colab — intentional, it's your session
- Local machine compromise exposing `~/.claude-colab.json`

## Limitations

- **Session timeout**: Free Colab dies after 90min idle / 12hr max. You'll need to restart and reconnect.
- **No streaming**: Long-running commands return nothing until completion. Redirect to file: `colab_exec "python train.py > output.log 2>&1"`
- **50MB file limit**: For larger files, use `colab_exec` with `wget` or `gdown`.
- **No persistent state**: Each `/python` call runs in a fresh namespace.

## License

MIT
