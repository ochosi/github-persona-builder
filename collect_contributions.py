#!/usr/bin/env python3
"""Collect a GitHub user's contributions to an organization.

Uses PyGithub for API access. Fetches PR reviews, authored PRs,
and authored issues, then writes organized markdown files for each
item with the user's comments.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from github import Auth, Github

_search_timestamps: list[float] = []
_repo_cache: dict = {}


# ---------- GitHub helpers ----------


def _throttle_search():
    """Enforce the GitHub search API's stricter rate limit (~30 req/min)."""
    now = time.time()
    _search_timestamps[:] = [t for t in _search_timestamps if t >= now - 60]
    if len(_search_timestamps) >= 28:
        wait = 62 - (now - _search_timestamps[0])
        if wait > 0:
            print(f"  [rate-limit] search throttle, sleeping {wait:.1f}s", flush=True)
            time.sleep(wait)
    _search_timestamps.append(time.time())


def search_issues(
    g: Github,
    query: str,
    *,
    max_results: int = 1000,
    sort: str = "comments",
    order: str = "desc",
) -> list:
    """Search issues/PRs with search-specific rate limiting."""
    _throttle_search()
    results = []
    paginated = g.search_issues(query, sort=sort, order=order)
    total = paginated.totalCount

    for i, item in enumerate(paginated):
        if i >= max_results:
            break
        results.append(item)
        if (i + 1) % 100 == 0:
            print(
                f"  search page {(i + 1) // 100}: got 100 "
                f"(total so far {i + 1}/{total})",
                flush=True,
            )
            _throttle_search()

    print(f"  search: got {len(results)} results (total available: {total})", flush=True)
    return results


def _get_repo(g: Github, org: str, name: str):
    key = f"{org}/{name}"
    if key not in _repo_cache:
        _repo_cache[key] = g.get_repo(key)
    return _repo_cache[key]


def _repo_name(item) -> str:
    return item.repository_url.split("/")[-1]


def fetch_user_issue_comments(
    g: Github, org: str, repo_name: str, number: int, username: str
) -> list:
    repo = _get_repo(g, org, repo_name)
    return [
        c
        for c in repo.get_issue(number).get_comments()
        if c.user and c.user.login == username
    ]


def fetch_user_review_comments(
    g: Github, org: str, repo_name: str, number: int, username: str
) -> list:
    repo = _get_repo(g, org, repo_name)
    return [
        c
        for c in repo.get_pull(number).get_comments()
        if c.user and c.user.login == username
    ]


def fetch_user_reviews(
    g: Github, org: str, repo_name: str, number: int, username: str
) -> list:
    repo = _get_repo(g, org, repo_name)
    return [
        r
        for r in repo.get_pull(number).get_reviews()
        if r.user and r.user.login == username
    ]


# ---------- formatting helpers ----------


def _fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def _fmt_timestamp(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


# ---------- markdown writers ----------


def write_pr_review_md(
    out_dir: Path, org: str, item, issue_comments: list,
    review_comments: list, reviews: list,
):
    repo = _repo_name(item)
    number = item.number
    outpath = out_dir / "pr-reviews" / f"{repo}__PR-{number}.md"

    lines = [
        f"# {item.title}",
        "",
        f"**Repository:** {org}/{repo}",
        f"**PR:** [{repo}#{number}]({item.html_url})",
        f"**Author:** {item.user.login}",
        f"**State:** {item.state}",
        f"**Created:** {_fmt_date(item.created_at)}",
        "",
    ]

    if reviews:
        lines.append("## Review Verdicts")
        lines.append("")
        for r in sorted(reviews, key=lambda x: x.submitted_at or datetime.min):
            state_label = (r.state or "COMMENTED").replace("_", " ").title()
            ts = _fmt_date(r.submitted_at)
            body = (r.body or "").strip()
            lines.append(f"### {state_label} ({ts})")
            lines.append("")
            if body:
                lines.append(body)
                lines.append("")

    if review_comments:
        lines.append("## Inline Review Comments")
        lines.append("")
        for c in sorted(review_comments, key=lambda x: x.created_at or datetime.min):
            ts = _fmt_timestamp(c.created_at)
            path = c.path or ""
            diff_hunk = c.diff_hunk or ""
            body = (c.body or "").strip()
            lines.append(f"### `{path}` ({ts})")
            lines.append("")
            if diff_hunk:
                lines.append("```diff")
                lines.append(diff_hunk)
                lines.append("```")
                lines.append("")
            lines.append(body)
            lines.append("")

    if issue_comments:
        lines.append("## General Comments")
        lines.append("")
        for c in sorted(issue_comments, key=lambda x: x.created_at or datetime.min):
            ts = _fmt_timestamp(c.created_at)
            body = (c.body or "").strip()
            lines.append(f"### Comment ({ts})")
            lines.append("")
            lines.append(body)
            lines.append("")

    outpath.write_text("\n".join(lines), encoding="utf-8")


def write_issue_md(out_dir: Path, org: str, username: str, item, comments: list):
    repo = _repo_name(item)
    number = item.number
    outpath = out_dir / "issues" / f"{repo}__ISSUE-{number}.md"

    body = (item.body or "").strip()
    lines = [
        f"# {item.title}",
        "",
        f"**Repository:** {org}/{repo}",
        f"**Issue:** [{repo}#{number}]({item.html_url})",
        f"**State:** {item.state}",
        f"**Created:** {_fmt_date(item.created_at)}",
        "",
        "## Issue Body",
        "",
        body,
        "",
    ]

    if comments:
        lines.append(f"## Follow-up Comments by {username}")
        lines.append("")
        for c in sorted(comments, key=lambda x: x.created_at or datetime.min):
            ts = _fmt_timestamp(c.created_at)
            cbody = (c.body or "").strip()
            lines.append(f"### Comment ({ts})")
            lines.append("")
            lines.append(cbody)
            lines.append("")

    outpath.write_text("\n".join(lines), encoding="utf-8")


def write_pr_authored_md(
    out_dir: Path, org: str, username: str, item,
    issue_comments: list, review_comments: list,
):
    repo = _repo_name(item)
    number = item.number
    outpath = out_dir / "pr-authored" / f"{repo}__PR-{number}.md"

    body = (item.body or "").strip()
    lines = [
        f"# {item.title}",
        "",
        f"**Repository:** {org}/{repo}",
        f"**PR:** [{repo}#{number}]({item.html_url})",
        f"**State:** {item.state}",
        f"**Created:** {_fmt_date(item.created_at)}",
        "",
        "## PR Description",
        "",
        body,
        "",
    ]

    all_comments = sorted(
        [("general", c) for c in issue_comments]
        + [("inline", c) for c in review_comments],
        key=lambda x: x[1].created_at or datetime.min,
    )

    if all_comments:
        lines.append(f"## {username}'s Comments")
        lines.append("")
        for kind, c in all_comments:
            ts = _fmt_timestamp(c.created_at)
            cbody = (c.body or "").strip()
            if kind == "inline":
                path = c.path or ""
                lines.append(f"### Inline on `{path}` ({ts})")
            else:
                lines.append(f"### Comment ({ts})")
            lines.append("")
            lines.append(cbody)
            lines.append("")

    outpath.write_text("\n".join(lines), encoding="utf-8")


# ---------- collectors ----------


def collect_pr_reviews(
    g: Github, username: str, org: str, out_dir: Path, *, max_items: int = 200
):
    print(f"\n{'='*60}", flush=True)
    print(
        f"Collecting PRs reviewed/commented on by {username} "
        f"(top {max_items} by comments)",
        flush=True,
    )
    print(f"{'='*60}", flush=True)

    items = search_issues(
        g, f"commenter:{username} org:{org} is:pr", max_results=max_items
    )
    print(f"Found {len(items)} PRs to process", flush=True)

    written = 0
    skipped = 0
    for i, item in enumerate(items):
        repo = _repo_name(item)
        number = item.number
        outpath = out_dir / "pr-reviews" / f"{repo}__PR-{number}.md"
        if outpath.exists():
            skipped += 1
            continue
        print(f"  [{i+1}/{len(items)}] {repo}#{number}: {item.title[:60]}", flush=True)

        issue_comments = fetch_user_issue_comments(g, org, repo, number, username)
        review_comments = fetch_user_review_comments(g, org, repo, number, username)
        reviews = fetch_user_reviews(g, org, repo, number, username)

        total = len(issue_comments) + len(review_comments) + len(reviews)
        if total == 0:
            print(f"         (no comments by {username}, skipping)", flush=True)
            continue

        write_pr_review_md(out_dir, org, item, issue_comments, review_comments, reviews)
        written += 1
        print(f"         wrote {total} comments", flush=True)

    print(
        f"  => Wrote {written} PR review files "
        f"({skipped} already existed, skipped)",
        flush=True,
    )


def collect_authored_issues(
    g: Github, username: str, org: str, out_dir: Path, *, max_items: int = 200
):
    print(f"\n{'='*60}", flush=True)
    print(
        f"Collecting issues authored by {username} "
        f"(top {max_items} by comments)",
        flush=True,
    )
    print(f"{'='*60}", flush=True)

    items = search_issues(
        g, f"author:{username} org:{org} is:issue", max_results=max_items
    )
    print(f"Found {len(items)} issues to process", flush=True)

    written = 0
    skipped = 0
    for i, item in enumerate(items):
        repo = _repo_name(item)
        number = item.number
        outpath = out_dir / "issues" / f"{repo}__ISSUE-{number}.md"
        if outpath.exists():
            skipped += 1
            continue
        print(f"  [{i+1}/{len(items)}] {repo}#{number}: {item.title[:60]}", flush=True)

        comments = fetch_user_issue_comments(g, org, repo, number, username)
        write_issue_md(out_dir, org, username, item, comments)
        written += 1
        print(f"         wrote (body + {len(comments)} comments)", flush=True)

    print(
        f"  => Wrote {written} issue files "
        f"({skipped} already existed, skipped)",
        flush=True,
    )


def collect_authored_prs(
    g: Github, username: str, org: str, out_dir: Path, *, max_items: int = 50
):
    print(f"\n{'='*60}", flush=True)
    print(
        f"Collecting PRs authored by {username} "
        f"(top {max_items} by comments)",
        flush=True,
    )
    print(f"{'='*60}", flush=True)

    items = search_issues(
        g, f"author:{username} org:{org} is:pr", max_results=max_items
    )
    print(f"Found {len(items)} PRs to process", flush=True)

    written = 0
    skipped = 0
    for i, item in enumerate(items):
        repo = _repo_name(item)
        number = item.number
        outpath = out_dir / "pr-authored" / f"{repo}__PR-{number}.md"
        if outpath.exists():
            skipped += 1
            continue
        print(f"  [{i+1}/{len(items)}] {repo}#{number}: {item.title[:60]}", flush=True)

        issue_comments = fetch_user_issue_comments(g, org, repo, number, username)
        review_comments = fetch_user_review_comments(g, org, repo, number, username)

        write_pr_authored_md(out_dir, org, username, item, issue_comments, review_comments)
        written += 1
        print(
            f"         wrote (body + {len(issue_comments) + len(review_comments)} comments)",
            flush=True,
        )

    print(
        f"  => Wrote {written} authored PR files "
        f"({skipped} already existed, skipped)",
        flush=True,
    )


# ---------- CLI ----------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a GitHub user's contributions across an organization.",
    )
    parser.add_argument(
        "username", help="GitHub username to collect contributions for"
    )
    parser.add_argument("org", help="GitHub organization to search within")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (default: $GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: <username>-contributions)",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=200,
        help="Max PR reviews to fetch (default: 200)",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=200,
        help="Max authored issues to fetch (default: 200)",
    )
    parser.add_argument(
        "--max-authored-prs",
        type=int,
        default=50,
        help="Max authored PRs to fetch (default: 50)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    args = parse_args(argv)

    if not args.token:
        print(
            "Error: GitHub token required. Set GITHUB_TOKEN or use --token.",
            file=sys.stderr,
        )
        sys.exit(1)

    out_dir = Path(args.output_dir or f"{args.username}-contributions")
    for subdir in ("pr-reviews", "issues", "pr-authored"):
        (out_dir / subdir).mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {out_dir}", flush=True)
    print(f"User: {args.username}  Org: {args.org}", flush=True)

    g = Github(auth=Auth.Token(args.token), per_page=100)

    collect_pr_reviews(g, args.username, args.org, out_dir, max_items=args.max_reviews)
    collect_authored_issues(
        g, args.username, args.org, out_dir, max_items=args.max_issues
    )
    collect_authored_prs(
        g, args.username, args.org, out_dir, max_items=args.max_authored_prs
    )

    print(f"\n{'='*60}", flush=True)
    print("Done!", flush=True)
    pr_reviews = len(list((out_dir / "pr-reviews").glob("*.md")))
    issues = len(list((out_dir / "issues").glob("*.md")))
    pr_authored = len(list((out_dir / "pr-authored").glob("*.md")))
    print(
        f"Files on disk: {pr_reviews} PR reviews, {issues} issues, "
        f"{pr_authored} authored PRs",
        flush=True,
    )


if __name__ == "__main__":
    main()
