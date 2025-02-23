# Vico - Vision Memory Copilot

<div align="center">

[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Next.js](https://img.shields.io/badge/Next.js%2014-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![DuckDB](https://img.shields.io/badge/Duckdb-000000?style=for-the-badge&logo=Duckdb&logoColor=yellow)](https://duckdb.org/)
[![MLX](https://img.shields.io/badge/MLX-F80000?style=for-the-badge&logo=Apple&logoColor=white)](https://github.com/ml-explore/mlx)
[![Bun](https://img.shields.io/badge/Bun-000000?style=for-the-badge&logo=bun)](https://bun.sh/)

</div>

## Overview

Vico is an advanced memory management system that combines cutting-edge visual processing with sophisticated text analysis. Built with modern web technologies and optimized for Apple Silicon, it offers an intuitive interface for storing, managing, and searching through digital memories.

## Key Features

### Visual Processing
- **Intelligent Image Analysis**: Automated detailed image descriptions using MLX-powered vision models
- **Visual Memory Storage**: Efficient image processing and storage with base64 encoding
- **Multi-Modal Search**: Combined text and visual content search capabilities

### Memory Management
- **Real-time Operations**: Instant memory creation, editing, and deletion
- **Advanced Search**: Natural language processing for intuitive memory retrieval
- **Context-Aware Responses**: AI-powered memory analysis and correlation

## Architecture

### Frontend
- Next.js 14 App Router with TypeScript
- React Server Components for optimal performance
- Tailwind CSS + shadcn/ui for component styling
- Client-side state management with React hooks

### Backend
- Python FastAPI service for ML operations
- MLX for efficient model inference
- DuckDB for fast, reliable data storage
- CORS support for Chrome extension integration

### ML Pipeline
- Qwen2.5-VL-72B for image analysis
- DeepSeek-R1-Distill-Qwen-14B for short-context memory reasoning
- Qwen2.5-14B-Instruct-1M for long-context memory processing
- Optimized inference using MLX on Apple Silicon

## System Requirements

- Apple Silicon Mac (M1/M2/M3)
- Python 3.10+
- Node.js 18+
- Bun runtime

## Quick Start

1. **Install Dependencies**

```bash
bun install
pip install -r requirements.txt
```

2. **Run the Development Server**

```bash
bun run dev
```

3. **Run the Inference Service**

```bash
python python/inference_service.py
```

## Acknowledgments

Built using [shadcn/ui](https://ui.shadcn.com/) and ML implementations from [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) ❤️.

## Memory Backup
```bash
# Backup memories.duckdb twice daily (9am/9pm)
# Creates max 62 rotating backups (31 days × 2 backups/day)
# Format: memories-YEAR_DAY_HOUR.duckdb (e.g., memories-2024_15_09.duckdb)
0 9,21 * * * rsync -avz /path/to/vico/data/memories.duckdb backupserver:/path/to/backup/memories-$(date +\%Y_\%d_\%H).duckdb
```
