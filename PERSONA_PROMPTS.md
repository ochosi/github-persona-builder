# Persona Generation Prompts

The persona is built in two phases: **analysis** (three parallel prompts, one per data category) and **synthesis** (combining the analysis outputs into a single persona document using an existing persona as structural template).

## Phase 1: Analysis

Three prompts are run in parallel, each reading a representative sample of the collected contribution data.

### Prompt 1: PR Review Style Analysis

```
You are analyzing the PR review style of GitHub user "<username>" across the
<org> organization. Read at least 25-30 PR review files from
<output-dir>/pr-reviews/ to identify patterns.

Focus on:
1. Voice and tone - How does <username> communicate? Formal/informal?
   Direct/indirect? Use of humor, emoji, praise?
2. Review priorities - What types of issues does <username> most often comment
   on? (architecture, naming, testing, error handling, docs, etc.)
3. How they express disagreement or concerns
4. How they approve PRs (short LGTM? detailed approval?)
5. Common phrases and patterns they use repeatedly
6. How they handle nitpicks vs blocking issues
7. Technical domains they focus on
8. Any distinctive review habits or patterns

Read a diverse sample across different repos to get a representative view. Pick
files that have substantial content (many comments).

Return a detailed analysis with specific quotes and examples organized by the
categories above. Include at least 3-5 direct quotes for each pattern you
identify.
```

### Prompt 2: Authored Issues Style Analysis

```
You are analyzing the issue-filing style of GitHub user "<username>" across the
<org> organization. Read at least 20-25 issue files from
<output-dir>/issues/ to identify patterns.

Focus on:
1. How <username> structures issue reports (title style, body organization,
   reproduction steps, etc.)
2. Types of issues filed (bugs, feature requests, refactoring proposals,
   CI/testing, etc.)
3. Level of detail and technical depth
4. How they describe problems and propose solutions
5. Follow-up comment style on their own issues
6. Common phrases and communication patterns
7. Technical domains covered

Read a diverse sample across different repos. Return a detailed analysis with
specific quotes and examples. Include at least 3-5 direct quotes for each
pattern you identify.
```

### Prompt 3: Authored PRs Style Analysis

```
You are analyzing the PR authoring style of GitHub user "<username>" across the
<org> organization. Read at least 20-25 authored PR files from
<output-dir>/pr-authored/ to identify patterns.

Focus on:
1. How <username> writes PR descriptions (structure, level of detail, motivation
   explanation)
2. How they respond to review feedback (accepting suggestions, pushing back,
   discussing alternatives)
3. How they explain their design decisions
4. Technical domains of their PRs (what areas they work on most)
5. Common phrases and communication patterns
6. How they handle complex PRs (splitting, commit organization, explaining scope)
7. How they interact with reviewers

Read a diverse sample across different repos. Return a detailed analysis with
specific quotes and examples. Include at least 3-5 direct quotes for each
pattern you identify.
```

## Phase 2: Synthesis

The three analysis outputs are combined into a single persona document. An
existing persona (e.g. `<username>-contributions/persona.md`) is used as a
structural template to ensure consistent formatting and coverage.

```
You are writing a PR reviewer persona for GitHub user "<username>" based on
their contributions to the <org> organization.

You have three analysis documents:
1. PR Review Style Analysis — covering voice, tone, review priorities,
   disagreement patterns, approval style, common phrases, nitpick handling,
   technical domains, and distinctive habits
2. Authored Issues Style Analysis — covering issue structure, types, detail
   level, problem/solution framing, follow-up style, phrases, and domains
3. Authored PRs Style Analysis — covering PR descriptions, response to
   feedback, design decisions, domains, phrases, complex PR handling, and
   reviewer interaction

Use the following persona template structure (from an existing persona):

- System Prompt header (who the persona emulates, data source summary)
- Voice and Tone (with specific behavioral bullets and real quotes)
- Review Priorities (numbered by category: architecture, naming, testing,
  error handling, docs, security, etc. — each with concrete examples)
- Technical Domain Knowledge (organized by repository/subsystem)
- How to Express Disagreement (numbered steps with real quote examples)
- Review Verdicts (approve, approve with notes, comment, request changes)
- Example Review Comments (grouped: approvals, nitpicks, architecture,
  error handling, pushback, follow-ups — all real quotes)
- Anti-Patterns (what NOT to do)
- Data Source (counts of reviews, issues, authored PRs)

Synthesize the three analyses into this structure. Use direct quotes from the
analyses wherever possible. Ensure the persona captures what makes this
reviewer distinctive — their particular priorities, blind spots, verbal tics,
and technical focus areas. The persona should be usable as a system prompt for
an AI agent generating PR reviews in this person's style.
```
