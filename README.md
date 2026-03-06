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

## Using the persona with Claude Code

Once you have a `persona.md`, you can use it with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) in several ways.

### One-off review via CLI

Pass the persona as a system prompt with `-p` and ask Claude to review a PR by URL:

```bash
claude -p "$(cat <username>-contributions/persona.md)" \
    "Review this PR: https://github.com/<org>/<repo>/pull/123"
```

### Persistent project instructions via `CLAUDE.md` (recommended)

For ongoing use, add the persona to a `CLAUDE.md` file in your project root. Claude Code automatically reads this file as context for every session.

```bash
cp <username>-contributions/persona.md CLAUDE.md
```

You can also prepend a short instruction header:

```bash
{
  echo "# Reviewer Persona"
  echo ""
  echo "When reviewing PRs, follow the reviewer persona below."
  echo ""
  cat <username>-contributions/persona.md
} > CLAUDE.md
```

### One-off review with a local diff

Pipe `gh pr diff` output alongside the persona to review changes without navigating to GitHub:

```bash
claude -p "$(cat <username>-contributions/persona.md)

Review the changes in this diff and provide feedback in the style described above:

$(gh pr diff 123)"
```

## Build a persona with Cursor

The fastest way to build a persona is to open this repository in [Cursor](https://cursor.sh) and let the AI agent drive the entire workflow. Copy the prompt below into Cursor's chat (Agent mode), replacing `<username>` and `<org>` with the GitHub username and organization you want to analyze.

**Before you start:**

- You need a **GitHub personal access token** (`GITHUB_TOKEN`). Without one, GitHub's API rate limits are severely restrictive (60 core requests/hr and 10 search requests/min unauthenticated, vs 5,000 core/hr and 30 search/min with a token). Create one at [github.com/settings/tokens](https://github.com/settings/tokens) — no special scopes are needed for public repos.
- You can pull a **sample** of the data for a quick test, or the **full** dataset for a richer persona. The script is idempotent, so you can start with a sample and re-run with higher limits later without re-fetching existing files.
- Persona generation is a **two-phase** process: first, three parallel analyses (PR reviews, authored issues, authored PRs), then a synthesis step that merges them into a single `persona.md`.

### The prompt

````text
Build a GitHub reviewer persona for the user <username> in the <org> organization.
Follow these steps in order:

1. SETUP
   - Run `pip install -r requirements.txt` to install dependencies.
   - Make sure GITHUB_TOKEN is set in the environment (it is required to avoid
     GitHub API rate limiting). If it is not set, stop and ask me to provide it.

2. COLLECT DATA
   Run `collect_contributions.py` to fetch the user's GitHub contribution history.

   For a quick sample (faster, good for testing):
   ```
   python collect_contributions.py <username> <org> \
       --max-reviews 30 --max-issues 20 --max-authored-prs 15
   ```

   For the full dataset (slower, produces a better persona):
   ```
   python collect_contributions.py <username> <org>
   ```

   Ask me whether I want a sample or the full dataset before running.

3. ANALYZE (Phase 1)
   Read the three Phase 1 analysis prompts from PERSONA_PROMPTS.md. For each one,
   read the specified number of files from the corresponding subdirectory under
   <username>-contributions/ and produce a detailed analysis. Write each analysis
   to a file:
   - <username>-contributions/analysis-pr-reviews.md
   - <username>-contributions/analysis-issues.md
   - <username>-contributions/analysis-authored-prs.md

4. SYNTHESIZE (Phase 2)
   Read the Phase 2 synthesis prompt from PERSONA_PROMPTS.md. Combine the three
   analysis documents into a single reviewer persona. Write the result to:
   - <username>-contributions/persona.md

5. DONE
   Tell me the persona is ready and show me a brief summary of the reviewer's
   style. The full persona is in <username>-contributions/persona.md.
````
