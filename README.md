# Vico - Vision Memory Copilot

Vico couples a streaming Next.js client with a local MLX inference stack to capture, search, and reason over personal memories. The web UI surfaces recent entries, conversational context, and autonomous tool activity while the Python backend orchestrates large language, vision, and retrieval models entirely on-device.

## Feature Highlights
- **Memory-centric workspace** - resizable panels combine assistant output with a searchable grid of DuckDB-stored memories (text + optional image).
- **Search, Chat, Agent modes** - instant text filtering, conversational Q&A, or multi-step agentic reasoning with live token and tool-call telemetry.
- **Tool calling** - the FastAPI service exposes functions for editing memories, running terminal commands, and querying an offline Wikipedia snapshot.
- **Streaming UX** - Server-Sent Events drive typing indicators, thinking blocks, and final responses without blocking the UI.
- **Local-first data** - memories persist in `data/memories.duckdb`, prompt caches live under `data/prompt_caches/`, and large corpora remain on disk.

### Data Assets
- `data/memories.duckdb` - primary memory store (binary blobs encode images as base64).
- `data/prompt_caches/` - persisted ML prompt caches created by the inference service.
- `data/wiki/wiki.db` - full-text index consumed by the offline Wikipedia tool; regenerate with `data/wiki/update_wiki.sh`

## Prerequisites
- Apple Silicon Mac (M1/M2/M3) running macOS 14+ for MLX acceleration.
- [Bun](https://bun.sh/) ≥ 1.1 and Node.js 18+ (for tooling compatibility).
- [uv](https://github.com/astral-sh/uv) ≥ 0.4 with Python 3.10+ on PATH.

## Quick Start
1. **Install dependencies**
   ```bash
   bun install
   (cd python && uv sync)
   ```
2. **Configure models** - copy or edit `python/.env` to configure local models (see below).
3. **Run the inference API**
   ```bash
   cd python
   uv run inference_service.py  # serves on http://localhost:3020/api/
   ```
4. **Start the web client** (separate terminal)
   ```bash
   bun run dev  # http://localhost:3000
   ```
5. Visit http://localhost:3000 and switch between Search, Chat, and Agent modes to verify streaming responses.

## Configuration Reference
Sample `python/.env` model configuration:

```bash
# Chat Model Configuration
CHAT_MODEL_NAME=mlx-community/Qwen2.5-14B-Instruct-1M-8bit

# Agentic Model Configuration
AGENTIC_MODEL_NAME=mlx-community/Qwen3-Next-80B-A3B-Thinking-4bit
AGENTIC_MAX_TOKENS=81920
AGENTIC_MAX_KV_SIZE=256000
AGENTIC_TEMP=0.6
AGENTIC_TOP_P=0.95
AGENTIC_TOP_K=20
AGENTIC_MIN_P=0
AGENTIC_REPETITION_PENALTY=1.05
AGENTIC_REPETITION_CONTEXT_SIZE=64

# Vision Model Configuration
IMAGE_MODEL_NAME=mlx-community/gemma-3-27b-it-8bit
IMAGE_MAX_TOKENS=100000
IMAGE_TEMP=0.7
```


## Memory Backup
```bash
# Backup memories.duckdb twice daily (9am/9pm)
# Creates max 62 rotating backups (31 days × 2 backups/day)
# Format: memories-YEAR_DAY_HOUR.duckdb (e.g., memories-2024_15_09.duckdb)
0 9,21 * * * rsync -avz /path/to/vico/data/memories.duckdb backupserver:/path/to/backup/memories-$(date +\%Y_\%d_\%H).duckdb
```

## Made Possible By (❤️):
[![uv](https://img.shields.io/badge/uv-package%20manager-blue?logo=python&logoColor=white)](https://github.com/astral-sh/uv)
[![Bun](https://img.shields.io/badge/Bun-runtime-black?logo=bun&logoColor=white)](https://github.com/oven-sh/bun)
[![shadcn/ui](https://img.shields.io/badge/shadcn%2Fui-components-black?logo=react&logoColor=white)](https://ui.shadcn.com/)
[![mlx-lm](https://img.shields.io/badge/mlx--lm-language%20models-orange?logo=apple&logoColor=white)](https://github.com/ml-explore/mlx-lm)
[![mlx-vlm](https://img.shields.io/badge/mlx--vlm-vision%20models-orange?logo=apple&logoColor=white)](https://github.com/Blaizzy/mlx-vlm)