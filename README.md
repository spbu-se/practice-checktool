# Student Repo Analyzer

CLI tool for analyzing student GitHub repositories against a set of software engineering
best practices. Integrates with the Practice Grading API to fetch meeting data, then
uses [opencode](https://opencode.ai) agents to evaluate student projects.

## Features

- **Practice Grading API bindings** — list meetings, view talks/students
- **Repo analysis** — clones student repos and evaluates them across 26 rules covering:
  - Licensing (1–3)
  - CI/CD (4–7)
  - Code quality (6, 8, 11, 18, 20)
  - C/C++ sanitizers (12)
  - Repository hygiene (9–10)
  - Documentation (13–17, 19, 21–22)
  - Git practices (23–24)
  - Releases and security (25–26)
- **Size guard** — rejects repos larger than 30 MB to keep analysis fast

## Requirements

- Python >= 3.10
- [opencode](https://opencode.ai) CLI installed and configured
- `jq` (for JSON output parsing)

## Installation

```bash
uv sync          # or: pip install -e .
cp .env.example .env   # then edit credentials
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PRACTICE_GRADING_URL` | `http://127.0.0.1:8080/api` | Practice Grading API base URL |
| `PRACTICE_GRADING_LOGIN` | `login` | API login |
| `PRACTICE_GRADING_PASSWORD` | `password` | API password |
| `LLM_MODEL` | `opencode/big-pickle` | LLM model for opencode agents |

## Usage

```bash
# List all meetings
python pg-cli.py list

# Show meeting details
python pg-cli.py show-meeting 1

# Show talk details
python pg-cli.py show-talk 42

# Analyze a single talk's repos
python pg-cli.py analyze-talk 42

# Analyze all talks in a meeting (save results to folder)
python pg-cli.py analyze-meeting 1 -o ./reports
```
