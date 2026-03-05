# GitHub Persona Builder

Build AI reviewer personas from a developer's GitHub contribution history, then use them to generate PR reviews that match that person's style and technical judgment.

## What's in this repo

### `collect_contributions.py`

A Python script that scrapes a GitHub user's contributions across an organization using the GitHub API. It collects:

- **PR reviews** — PRs where the user left review comments, inline feedback, or review verdicts
- **Authored issues** — Issues filed by the user, including follow-up comments
- **Authored PRs** — PRs written by the user, with their own comments

Output is written as structured Markdown files into a `<username>-contributions/` directory. The script handles GitHub API rate limiting, pagination, and is idempotent (skips already-fetched items).

### `PERSONA_PROMPTS.md`

Prompts for the two-phase persona generation workflow: parallel analysis of PR reviews, authored issues, and authored PRs, followed by synthesis into a single persona document.

## Setup

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_...
```

## Usage

```bash
python collect_contributions.py <username> <org>

# With options
python collect_contributions.py <username> <org> \
    --max-reviews 50 --max-issues 100 --output-dir my-output/
```

Run `python collect_contributions.py --help` for all options.

### Output structure

The script creates a `<username>-contributions/` directory with:

| Directory | Contents |
|---|---|
| `pr-reviews/` | PRs reviewed, with inline comments and verdicts |
| `issues/` | Authored issues with follow-up comments |
| `pr-authored/` | Authored PRs with descriptions and comments |

## Workflow

1. **Collect** — Run `collect_contributions.py <username> <org>` to scrape a user's GitHub history
2. **Analyze** — Use the prompts in `PERSONA_PROMPTS.md` to synthesize the raw data into style analysis reports
3. **Build persona** — Distill the analyses into a reviewer persona (`persona.md`)
4. **Review** — Use the persona as context for an AI agent to review PRs in that person's style
