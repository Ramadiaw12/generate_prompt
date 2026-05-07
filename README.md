<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=DM+Serif+Display&size=32&duration=3000&pause=1000&color=E8740C&center=true&vCenter=true&width=600&lines=Prompt+Engineering+Platform;Build+better+prompts%2C+faster." alt="Typing SVG" />

<br/>

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-1a5fb4?style=for-the-badge&logo=chainlink&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![OpenAI](https://img.shields.io/badge/GPT--4o--mini-powered-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)](https://docs.astral.sh/uv)
[![License](https://img.shields.io/badge/License-MIT-276f4c?style=for-the-badge)](LICENSE)

<br/>

> **An agentic platform that transforms raw ideas into structured, production-ready prompts**  
> using a 3-node LangGraph pipeline — analyze → structure → refine.

<br/>

**Author:** DIAWANE Ramatoulaye &nbsp;·&nbsp; [Report Bug](../../issues) &nbsp;·&nbsp; [Request Feature](../../issues) &nbsp;·&nbsp; [API Docs](http://localhost:8000/docs)

</div>

---

## 📑 Table of Contents

- [✨ Overview](#-overview)
- [🏗️ Architecture](#-architecture)
- [📁 Project Structure](#-project-structure)
- [⚙️ Prerequisites](#-prerequisites)
- [🚀 Getting Started](#-getting-started)
- [🔐 Environment Variables](#-environment-variables)
- [📡 API Reference](#-api-reference)
- [🤖 Agent Pipeline](#-agent-pipeline)
- [🔑 Authentication](#-authentication)
- [🖥️ Frontend](#-frontend)
- [🤝 Contributing](#-contributing)
- [🗺️ Roadmap](#-roadmap)

---

## ✨ Overview

This platform takes a **free-text user request** and runs it through a 3-node LangGraph agent that:

| Step | Node | Output |
|------|------|--------|
| 1️⃣ | `analyze_input` | intent · domain · complexity |
| 2️⃣ | `structure_prompt` | role · context · task · output_format · constraints |
| 3️⃣ | `refine_output` | a single fluent, production-ready prompt |

Users authenticate via **JWT** before accessing the generation pipeline. The interactive frontend also serves as a visual reference on prompt engineering concepts (clickable SVG diagram).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         FRONTEND                            │
│          Vanilla JS · HTML · CSS  ·  port 3000              │
│   Auth modal · Interactive SVG diagram · Results display    │
└───────────────────────────┬─────────────────────────────────┘
                            │  HTTP + Bearer JWT
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      FASTAPI BACKEND  · port 8000            │
│                                                             │
│   🔓 POST /auth/register    🔓 POST /auth/login             │
│   🔒 POST /generate-prompt  (JWT required)                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  LangGraph Agent                      │  │
│  │                                                       │  │
│  │   analyze_input → structure_prompt → refine_output    │  │
│  │        ↓                  ↓                ↓          │  │
│  │   intent/domain      5 sections       full_prompt     │  │
│  │                                                       │  │
│  │              GPT-4o-mini via LangChain                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
prompt-eng/
│
├── 📂 backend/
│   ├── 📂 agent/
│   │   ├── __init__.py
│   │   ├── graph.py          # LangGraph graph definition & compilation
│   │   ├── nodes.py          # 3 agent nodes: analyze · structure · refine
│   │   ├── router.py         # FastAPI router for agent endpoints
│   │   └── state.py          # AgentState TypedDict
│   │
│   ├── 📂 auth/
│   │   ├── __init__.py
│   │   └── router.py         # JWT auth: register · login · me
│   │
│   ├── 📂 models/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic request/response schemas
│   │
│   ├── 📂 db/
│   │   └── database.py       # DB layer (in-memory → SQLAlchemy)
│   │
│   └── main.py               # FastAPI app entry point
│
├── 📂 front/
│   └── index.html            # Single-page frontend (no build step)
│
├── .env                      # ⚠️ Never commit — local secrets only
├── .env.example              # Template for contributors
├── .gitignore
├── pyproject.toml            # uv project config + pinned dependencies
├── uv.lock
└── README.md
```

---

## ⚙️ Prerequisites

| Tool | Min Version | Install |
|------|-------------|---------|
| 🐍 Python | `3.12` | [python.org](https://python.org) |
| 📦 uv | `latest` | `curl -Ls https://astral.sh/uv/install.sh \| sh` |
| 🔑 OpenAI API Key | — | [platform.openai.com](https://platform.openai.com/api-keys) |

---

## 🚀 Getting Started

### 1 · Clone

```bash
git clone https://github.com/your-username/prompt-eng.git
cd prompt-eng
```

### 2 · Install dependencies

```bash
uv sync
```

> All dependencies are pinned in `uv.lock`. **Do not use `pip install` directly.**

### 3 · Configure environment

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and SECRET_KEY
```

### 4 · Start the backend

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

✅ API running at `http://localhost:8000`  
📖 Swagger UI at `http://localhost:8000/docs`

### 5 · Start the frontend

```bash
cd front
python -m http.server 3000
```

🌐 Open `http://localhost:3000`

---

## 🔐 Environment Variables

```bash
# .env.example

# ── OpenAI ──────────────────────────────
OPENAI_API_KEY=sk-proj-...

# ── JWT ─────────────────────────────────
# Generate with: openssl rand -hex 32
SECRET_KEY=your-secret-key-here
```

> ⚠️ `.env` is already in `.gitignore`. Never expose your `OPENAI_API_KEY` publicly.

---

## 📡 API Reference

### 🔓 Auth endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/auth/register` | ❌ | Create a new user account |
| `POST` | `/auth/login` | ❌ | Login — returns JWT |
| `GET` | `/auth/me` | ✅ | Get current user info |

<details>
<summary><b>POST /auth/register</b></summary>

```jsonc
// Request
{
  "email": "user@example.com",
  "password": "mypassword",
  "name": "Ramatoulaye"
}

// Response 201
{
  "message": "Compte créé avec succès.",
  "email": "user@example.com"
}
```
</details>

<details>
<summary><b>POST /auth/login</b></summary>

```
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=mypassword
```

```jsonc
// Response 200
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
</details>

---

### 🔒 Generation endpoint

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/generate-prompt` | ✅ Bearer | Run the full agent pipeline |

<details>
<summary><b>POST /generate-prompt</b></summary>

```jsonc
// Request
{
  "user_input": "Je veux un assistant pour rédiger des emails professionnels en anglais"
}

// Response 200
{
  "intent":        "Rédiger des emails professionnels en anglais",
  "domain":        "redaction",
  "complexity":    "medium",
  "role":          "You are an expert business communication specialist...",
  "context":       "The user needs to write professional emails in English...",
  "task":          "1. Analyze the email context and recipient...",
  "output_format": "Structured email: subject · opening · body · closing",
  "constraints":   "Formal tone · no slang · max 300 words",
  "full_prompt":   "You are an expert business communication specialist..."
}
```
</details>

---

## 🤖 Agent Pipeline

The pipeline is a **deterministic LangGraph graph** — no cycles, no branching, predictable latency.

```
                     ┌─────────────────────────────┐
  user_input  ──────►│       analyze_input          │
                     │                             │
                     │  model  : gpt-4o-mini        │
                     │  output : intent             │
                     │           domain             │
                     │           complexity         │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
                     │      structure_prompt        │
                     │                             │
                     │  model  : gpt-4o-mini        │
                     │  output : role               │
                     │           context            │
                     │           task               │
                     │           output_format      │
                     │           constraints        │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
                     │       refine_output          │
                     │                             │
                     │  model  : gpt-4o-mini        │
                     │  output : full_prompt        │
                     └─────────────────────────────┘
```

Each node is a **pure function** `(AgentState) -> AgentState`.  
Errors are caught per-node and propagated via the `error` key — the pipeline short-circuits gracefully.

### Adding a new node

```python
# 1. backend/agent/nodes.py
def my_new_node(state: AgentState) -> AgentState:
    if state.get("error"):
        return state
    # ... call LLM ...
    return {**state, "my_new_field": result}

# 2. backend/agent/state.py
class AgentState(TypedDict):
    ...
    my_new_field: str   # add your new key

# 3. backend/agent/graph.py
graph.add_node("my_new_node", my_new_node)
graph.add_edge("refine_output", "my_new_node")  # wire it in

# 4. backend/main.py — expose in PromptResponse
# 5. front/index.html — display the new field
```

---

## 🔑 Authentication

- Tokens signed with **HS256**, valid **7 days**
- Passwords hashed with **Argon2** (`argon2-cffi`)
- Client stores token in `localStorage`, sent as `Authorization: Bearer <token>`
- On `401`, frontend clears session and prompts re-login automatically

> ⚠️ **Current limitation:** users are stored in an **in-memory dict** (`_users_db`).  
> They are lost on server restart. See [Roadmap](#-roadmap) for the SQLAlchemy migration.

---

## 🖥️ Frontend

Single `index.html` — **no build step, no framework, no bundler.**

| Feature | Detail |
|---------|--------|
| 🗺️ Interactive SVG diagram | Clickable nodes with modals explaining each prompt concept |
| 🔐 Auth modal | Login / Register with tab switching and error handling |
| ⚡ Generation form | Textarea → API call → 5-section results + full prompt |
| 📋 Copy to clipboard | One-click copy of the generated prompt |
| ⌨️ Keyboard shortcut | `Ctrl+Enter` / `Cmd+Enter` to submit |
| 🎨 Design system | CSS custom properties · DM Serif Display · DM Mono · Instrument Sans |

---

## 🤝 Contributing

Contributions are welcome and appreciated. Please follow these steps:

### Workflow

```bash
# 1. Fork the repo and clone your fork
git clone https://github.com/your-username/prompt-eng.git

# 2. Create a feature branch
git checkout -b feat/your-feature-name

# 3. Install dependencies
uv sync

# 4. Make your changes, test locally

# 5. Commit — use Conventional Commits
git commit -m "feat(agent): add memory node to graph"

# 6. Push and open a Pull Request against main
git push origin feat/your-feature-name
```

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | When to use |
|--------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Restructure without changing behavior |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `chore` | Tooling, deps, config |

### Code Rules

- ✅ Type hints on every function
- ✅ Docstring on every node and route
- ✅ Keep nodes **pure** — no side effects outside `AgentState`
- ❌ Never commit `.env` or API keys
- ❌ Do not use `pip install` — always use `uv add`

### Opening Issues

Please include:
- Expected vs actual behavior
- Steps to reproduce
- Python version (`python --version`)
- uv version (`uv --version`)

---

## 🗺️ Roadmap

| Status | Feature |
|--------|---------|
| 🔲 | **Persistent DB** — SQLite via SQLAlchemy (drop-in for `_users_db`) |
| 🔲 | **Prompt history** — save and retrieve past generations per user |
| 🔲 | **Streaming** — stream `refine_output` token-by-token via SSE |
| 🔲 | **Export** — download generated prompt as `.txt` or `.md` |
| 🔲 | **Multi-model** — let users choose GPT-4o · Claude · Mistral |
| 🔲 | **Rate limiting** — per-user request throttling |
| 🔲 | **Docker** — containerized deployment guide |
| 🔲 | **Tests** — pytest suite for all nodes and API routes |

---

<div align="center">

Made with 🧠 and ☕ by **DIAWANE Ramatoulaye**

*Pull requests are welcome. For major changes, please open an issue first.*

[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=for-the-badge&logo=github)](https://github.com/your-username)

</div>