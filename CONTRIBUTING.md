# KNEXUS Team Setup & Contribution Guide

Welcome to the **KNEXUS** project! This guide contains everything your team members need to set up their local development environment and collaborate smoothly without code collisions.

---

## 🌿 Git & Branching Strategy

> [!IMPORTANT]
> **Do NOT commit directly to `main`!**
> `main` is our stable production branch that should always remain working and deployable.

### Recommended Workflow: Feature / Member Branches

Each team member works on an isolated branch and merges into `main` through a Pull Request or fast-forward merge once their feature is tested and verified.

#### 1. Branch Naming Convention
- `feat/<member>-<feature>` (e.g. `feat/hassan-ingestion`, `feat/ali-ollama-chain`, `feat/omar-docker-setup`)
- `fix/<member>-<bug>` (e.g. `fix/hassan-pgvector-index`)

#### 2. Day-to-Day Git Flow
```bash
# 1. Start from latest main
git checkout main
git pull origin main

# 2. Create your feature branch
git checkout -b feat/yourname-feature-description

# 3. Work on your code, test locally, and commit frequently
git add .
git commit -m "feat(rag): add recursive chunking logic for PDF documents"

# 4. Push your branch to GitHub
git push -u origin feat/yourname-feature-description

# 5. Open a Pull Request on GitHub to merge into main!
```

---

## 💻 Local Environment Setup (Phase 0)

### 1. Prerequisites
Ensure you have the following installed on your machine:
- **Python 3.10+** (Python 3.11 recommended)
- **Docker & Docker Compose** (for running PostgreSQL + pgvector)
- **Git**
- **Ollama** ([Download Ollama](https://ollama.com/))

---

### 2. Clone the Repository
```bash
git clone https://github.com/Hassan092-prog/KNEXUS.git
cd KNEXUS
```

---

### 3. Start PostgreSQL with `pgvector` via Docker
We use Docker to run PostgreSQL with the `pgvector` extension pre-configured so no manual C-compilation is required:

```bash
docker compose up -d
```
Verify the container is running:
```bash
docker ps
```
*(You should see `knexus-postgres` running mapped to port `5435`).*

---

### 4. Set Up Python Virtual Environment & Backend
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment:
# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (cmd):
.\venv\Scripts\activate.bat

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 5. Configure Environment Variables
Copy `.env.example` in the project root to `.env`:
```bash
cp .env.example .env
```
The defaults already match the `docker-compose.yml` settings.

---

### 6. Set Up Ollama (Local LLM)
In a separate terminal, ensure Ollama is running and pull the default model:
```bash
# Verify Ollama is running
ollama list

# Pull the lightweight, high-performance Llama 3.2 model
ollama pull llama3.2
```

---

### 7. Run the FastAPI Development Server
From the `backend` directory (with your virtualenv active):
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Now open your browser:
- **Interactive API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

The `/health` endpoint checks database connectivity, the `pgvector` extension, and the Ollama server automatically.

---

## 👥 Team Roles & Responsibilities Reference
Refer to [`docs/KNEXUS_Project_Plan.md`](docs/KNEXUS_Project_Plan.md) for full phase allocations and deliverables.
