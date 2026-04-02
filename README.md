<p align="center">
  <h1 align="center">AI Content API</h1>
  <p align="center">
    <strong>Multi-LLM REST API for AI Content Generation</strong> &mdash; OpenAI, Gemini & Ollama in one unified interface.
  </p>
</p>

<p align="center">
  <a href="https://github.com/brolyroly007/ai-content-api/actions/workflows/ci.yml"><img src="https://github.com/brolyroly007/ai-content-api/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/brolyroly007/ai-content-api/actions/workflows/docker.yml"><img src="https://github.com/brolyroly007/ai-content-api/actions/workflows/docker.yml/badge.svg" alt="Docker Build"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

---

Open-source REST API that generates content using **OpenAI GPT**, **Google Gemini**, or **Ollama** (local) through a single unified interface. Includes 8 built-in templates, API key management, rate limiting, SSE streaming, and a web dashboard.

### How it works

```
   Client Request                 AI Content API                    LLM Provider
  ┌────────────┐    ┌──────────────────────────────────┐    ┌──────────────────┐
  │ POST       │    │  1. Validate API Key             │    │   OpenAI GPT-4o  │
  │ /api/      │───▶│  2. Select Template              │───▶│   Google Gemini  │
  │ generate   │    │  3. Build Prompt                 │    │   Ollama Local   │
  │            │◀───│  4. Stream / Return Response     │◀───│                  │
  └────────────┘    │  5. Log Usage                    │    └──────────────────┘
                    └──────────────────────────────────┘
```

## Features

- **Multi-LLM Support** - Switch between OpenAI, Gemini, and Ollama per request
- **8 Content Templates** - Blog posts, social media, emails, SEO meta, ad copy, tweet threads, YouTube descriptions, product descriptions
- **SSE Streaming** - Real-time streaming with configurable timeout (default 120s)
- **API Key Security** - Keys are hashed (SHA-256) at rest; plain key shown only once on creation
- **Rate Limiting** - Per-minute and daily request limits per API key
- **Usage Analytics** - Track requests, tokens, and provider usage per key
- **Input Validation** - Template variable validation with max lengths and unknown field rejection
- **Auto-Retry** - Exponential backoff on transient LLM errors (rate limits, timeouts, 5xx)
- **Connection Pooling** - Singleton SQLite connection with WAL mode for better performance
- **Health Checks** - Deep health endpoint verifying database and each provider's availability
- **Web Dashboard** - Dark-themed UI for testing templates and managing keys
- **Export Formats** - Markdown, plain text, or JSON output
- **Docker Ready** - Docker Compose setup with Ollama included

## Quick Start

### Prerequisites

- Python 3.10+
- At least one LLM provider:
  - **OpenAI** API key ([get one](https://platform.openai.com/api-keys))
  - **Google Gemini** API key ([get one](https://aistudio.google.com/apikey))
  - **Ollama** installed locally ([download](https://ollama.ai))

### Installation

```bash
# Clone
git clone https://github.com/brolyroly007/ai-content-api.git
cd ai-content-api

# Virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python app.py
```

Open **http://localhost:8000** for the dashboard.

### Docker (includes Ollama)

```bash
docker compose up -d
# API: http://localhost:8000
# Ollama: http://localhost:11434
```

## Usage

### 1. Create an API Key

```bash
curl -X POST "http://localhost:8000/api/keys?name=my-app"
```

Response:
```json
{
  "key": "ak_a1b2c3d4e5f6...",
  "name": "my-app",
  "rate_limit": 60,
  "daily_limit": 1000
}
```

### 2. Generate Content

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_a1b2c3d4e5f6..." \
  -d '{
    "template_id": "blog-post",
    "variables": {
      "topic": "Benefits of AI in content creation",
      "tone": "professional",
      "word_count": "800",
      "keywords": "AI, content, automation"
    },
    "provider": "openai"
  }'
```

Response:
```json
{
  "content": "# Benefits of AI in Content Creation\n\n...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "tokens_used": 856,
  "template_id": "blog-post"
}
```

### 3. Stream Generation (SSE)

```bash
curl -N -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_a1b2c3d4e5f6..." \
  -d '{
    "template_id": "social-media",
    "variables": {
      "platform": "linkedin",
      "topic": "Remote work trends",
      "goal": "engagement",
      "include_hashtags": "yes"
    },
    "stream": true
  }'
```

## Templates

| Template | Category | Description |
|----------|----------|-------------|
| `blog-post` | Marketing | Full blog post with SEO keywords |
| `social-media` | Social | Platform-optimized posts (Instagram, LinkedIn, Twitter, Facebook) |
| `product-description` | Marketing | E-commerce product copy |
| `email` | Email | Marketing, outreach, newsletter, follow-up |
| `seo-meta` | SEO | Meta titles, descriptions, OG tags |
| `tweet-thread` | Social | Viral Twitter/X threads |
| `youtube-description` | Video | SEO-optimized video descriptions |
| `ad-copy` | Marketing | Google Ads, Facebook Ads, LinkedIn Ads |

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/generate` | Key | Generate content from template |
| `GET` | `/api/templates` | No | List all templates |
| `GET` | `/api/templates/{id}` | No | Get template details |
| `POST` | `/api/keys` | No | Create new API key |
| `GET` | `/api/keys` | No | List all keys (masked) |
| `GET` | `/api/keys/{key}/usage` | No | Usage statistics |
| `GET` | `/api/keys/{key}/history` | No | Recent generations |
| `DELETE` | `/api/keys/{key}` | No | Deactivate key |
| `GET` | `/api/providers` | No | List LLM providers |
| `GET` | `/api/health` | No | Deep health check (DB + providers) |
| `GET` | `/` | No | Web dashboard |

## Architecture

```
ai-content-api/
├── app.py                  # FastAPI entry point
├── config.py               # Pydantic Settings
├── middleware.py            # API key auth + rate limiting
├── export.py               # Content export formats
│
├── providers/              # LLM abstraction layer
│   ├── base.py             # Abstract BaseProvider interface
│   ├── openai_provider.py  # OpenAI GPT
│   ├── gemini_provider.py  # Google Gemini
│   └── ollama_provider.py  # Ollama (local)
│
├── templates/              # Content template system
│   ├── models.py           # Pydantic models
│   └── registry.py         # 8 built-in templates
│
├── database/               # SQLite async layer
│   ├── connection.py       # aiosqlite + schema
│   └── repositories.py     # CRUD operations
│
├── api/                    # Route modules
│   ├── generate.py         # POST /api/generate (+ SSE)
│   ├── templates.py        # Template endpoints
│   ├── keys.py             # API key management
│   ├── providers.py        # Provider listing
│   └── health.py           # Health check
│
├── web/index.html          # Dashboard (Tailwind + vanilla JS)
└── tests/                  # pytest suite
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model to use |
| `DEFAULT_PROVIDER` | `openai` | Default LLM provider |
| `DEFAULT_RATE_LIMIT` | `60` | Requests per minute per key |
| `DEFAULT_DAILY_LIMIT` | `1000` | Requests per day per key |
| `STREAM_TIMEOUT` | `120` | SSE stream timeout in seconds |

See `.env.example` for all options.

> **Note on API Keys**: Keys are hashed with SHA-256 before storage. The plain key is returned **only once** at creation time — store it securely. Existing keys from before v1.1 will need to be recreated.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn
- **Database**: SQLite (aiosqlite)
- **LLM**: OpenAI SDK, Google Generative AI, Ollama API
- **Streaming**: Server-Sent Events (SSE)
- **Frontend**: Tailwind CSS (CDN), vanilla JavaScript
- **Validation**: Pydantic v2
- **Logging**: Loguru
- **Testing**: pytest, pytest-asyncio
- **Linting**: Ruff
- **Containers**: Docker, Docker Compose

## Development

```bash
# Install dev dependencies
make dev

# Run tests
make test

# Run with coverage
make test-cov

# Lint
make lint

# Format
make format

# Run in dev mode (auto-reload)
make run-dev
```

## Roadmap

- [x] Multi-LLM provider abstraction
- [x] 8 content templates
- [x] API key management + rate limiting
- [x] SSE streaming generation
- [x] Web dashboard
- [x] Docker + Ollama support
- [x] CI/CD pipeline
- [x] API key hashing (SHA-256 at rest)
- [x] Auto-retry with exponential backoff for LLM calls
- [x] SSE stream timeout
- [x] Input validation on generate endpoint
- [x] Singleton DB connection with WAL mode
- [x] Deep health checks (DB + provider connectivity)
- [ ] Custom template creation via API
- [ ] Prompt history and favorites
- [ ] Webhook notifications
- [ ] Batch generation endpoint
- [ ] Response caching (Redis)
- [ ] OpenAPI SDK generation (Python, TypeScript)

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
