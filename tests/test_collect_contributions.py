"""Tests for collect_contributions.py."""

import types
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import collect_contributions as cc


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_module_state():
    """Reset module-level caches/timestamps between tests."""
    cc._search_timestamps.clear()
    cc._repo_cache.clear()


def _make_user(login="testuser"):
    return types.SimpleNamespace(login=login)


def _make_item(
    *,
    title="Fix widget",
    number=42,
    html_url="https://github.com/acme/repo/pull/42",
    state="open",
    created_at=datetime(2025, 6, 15),
    body="PR body text",
    repository_url="https://api.github.com/repos/acme/repo",
    user=None,
):
    return types.SimpleNamespace(
        title=title,
        number=number,
        html_url=html_url,
        state=state,
        created_at=created_at,
        body=body,
        repository_url=repository_url,
        user=user or _make_user(),
    )


def _make_comment(
    *,
    body="Looks good",
    created_at=datetime(2025, 6, 16),
    user=None,
    path=None,
    diff_hunk=None,
):
    return types.SimpleNamespace(
        body=body,
        created_at=created_at,
        user=user or _make_user(),
        path=path,
        diff_hunk=diff_hunk,
    )


def _make_review(
    *,
    body="LGTM",
    state="APPROVED",
    submitted_at=datetime(2025, 6, 16),
    user=None,
):
    return types.SimpleNamespace(
        body=body,
        state=state,
        submitted_at=submitted_at,
        user=user or _make_user(),
    )


# ── pure helper tests ────────────────────────────────────────────────


class TestFmtDate:
    def test_formats_datetime(self):
        assert cc._fmt_date(datetime(2025, 1, 9)) == "2025-01-09"

    def test_none_returns_empty(self):
        assert cc._fmt_date(None) == ""


class TestFmtTimestamp:
    def test_formats_datetime(self):
        assert cc._fmt_timestamp(datetime(2025, 1, 9, 14, 5)) == "2025-01-09 14:05"

    def test_none_returns_empty(self):
        assert cc._fmt_timestamp(None) == ""


class TestRepoName:
    def test_extracts_name(self):
        item = _make_item(repository_url="https://api.github.com/repos/acme/widgets")
        assert cc._repo_name(item) == "widgets"


class TestParseArgs:
    def test_positional_args(self):
        args = cc.parse_args(["alice", "myorg"])
        assert args.username == "alice"
        assert args.org == "myorg"

    def test_defaults(self):
        args = cc.parse_args(["alice", "myorg"])
        assert args.max_reviews == 200
        assert args.max_issues == 200
        assert args.max_authored_prs == 50
        assert args.output_dir is None

    def test_custom_flags(self):
        args = cc.parse_args([
            "alice", "myorg",
            "--max-reviews", "10",
            "--max-issues", "20",
            "--max-authored-prs", "5",
            "--output-dir", "/tmp/out",
            "--token", "ghp_fake",
        ])
        assert args.max_reviews == 10
        assert args.max_issues == 20
        assert args.max_authored_prs == 5
        assert args.output_dir == "/tmp/out"
        assert args.token == "ghp_fake"

    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_env")
        args = cc.parse_args(["alice", "myorg"])
        assert args.token == "ghp_env"


# ── markdown writer tests ────────────────────────────────────────────


class TestWritePrReviewMd:
    def test_creates_file_with_expected_content(self, tmp_path):
        (tmp_path / "pr-reviews").mkdir()
        item = _make_item()
        review = _make_review()
        inline = _make_comment(path="src/widget.py", diff_hunk="@@ -1 +1 @@\n-old\n+new")
        general = _make_comment(body="Nice work")

        cc.write_pr_review_md(tmp_path, "acme", item, [general], [inline], [review])

        outfile = tmp_path / "pr-reviews" / "repo__PR-42.md"
        assert outfile.exists()
        text = outfile.read_text()
        assert "# Fix widget" in text
        assert "**Repository:** acme/repo" in text
        assert "## Review Verdicts" in text
        assert "Approved" in text
        assert "## Inline Review Comments" in text
        assert "`src/widget.py`" in text
        assert "## General Comments" in text
        assert "Nice work" in text


class TestWriteIssueMd:
    def test_creates_file_with_expected_content(self, tmp_path):
        (tmp_path / "issues").mkdir()
        item = _make_item(
            html_url="https://github.com/acme/repo/issues/7",
            number=7,
            body="Something is broken",
        )
        comment = _make_comment(body="Still broken on main")

        cc.write_issue_md(tmp_path, "acme", "testuser", item, [comment])

        outfile = tmp_path / "issues" / "repo__ISSUE-7.md"
        assert outfile.exists()
        text = outfile.read_text()
        assert "# Fix widget" in text
        assert "Something is broken" in text
        assert "## Follow-up Comments by testuser" in text
        assert "Still broken on main" in text


class TestWritePrAuthoredMd:
    def test_creates_file_with_expected_content(self, tmp_path):
        (tmp_path / "pr-authored").mkdir()
        item = _make_item(body="Implements the new widget API")
        issue_comment = _make_comment(body="Rebased on main")
        inline_comment = _make_comment(path="api.py", body="Renamed this")

        cc.write_pr_authored_md(
            tmp_path, "acme", "testuser", item, [issue_comment], [inline_comment]
        )

        outfile = tmp_path / "pr-authored" / "repo__PR-42.md"
        assert outfile.exists()
        text = outfile.read_text()
        assert "# Fix widget" in text
        assert "Implements the new widget API" in text
        assert "## testuser's Comments" in text
        assert "Rebased on main" in text
        assert "Inline on `api.py`" in text


# ── collector integration test ────────────────────────────────────────


class TestCollectPrReviews:
    def _setup_out_dir(self, tmp_path):
        for sub in ("pr-reviews", "issues", "pr-authored"):
            (tmp_path / sub).mkdir(parents=True)
        return tmp_path

    @patch("collect_contributions._throttle_search")
    def test_writes_files_for_items_with_comments(self, _throttle, tmp_path):
        out = self._setup_out_dir(tmp_path)
        items = [_make_item(number=1), _make_item(number=2)]

        g = MagicMock()
        paginated = MagicMock()
        paginated.totalCount = len(items)
        paginated.__iter__ = lambda self: iter(items)
        g.search_issues.return_value = paginated

        comment = _make_comment()
        review = _make_review()

        with (
            patch.object(cc, "fetch_user_issue_comments", return_value=[comment]),
            patch.object(cc, "fetch_user_review_comments", return_value=[comment]),
            patch.object(cc, "fetch_user_reviews", return_value=[review]),
        ):
            cc.collect_pr_reviews(g, "testuser", "acme", out, max_items=10)

        written = list((out / "pr-reviews").glob("*.md"))
        assert len(written) == 2

    @patch("collect_contributions._throttle_search")
    def test_skips_existing_files(self, _throttle, tmp_path):
        out = self._setup_out_dir(tmp_path)
        items = [_make_item(number=1)]

        # Pre-create the file so the collector skips it
        (out / "pr-reviews" / "repo__PR-1.md").write_text("already here")

        g = MagicMock()
        paginated = MagicMock()
        paginated.totalCount = len(items)
        paginated.__iter__ = lambda self: iter(items)
        g.search_issues.return_value = paginated

        with (
            patch.object(cc, "fetch_user_issue_comments") as fetch_ic,
            patch.object(cc, "fetch_user_review_comments") as fetch_rc,
            patch.object(cc, "fetch_user_reviews") as fetch_rv,
        ):
            cc.collect_pr_reviews(g, "testuser", "acme", out, max_items=10)

        fetch_ic.assert_not_called()
        fetch_rc.assert_not_called()
        fetch_rv.assert_not_called()


# ── CLI / main smoke test ────────────────────────────────────────────


class TestMain:
    def test_creates_output_dirs_and_calls_collectors(self, tmp_path, monkeypatch):
        out_dir = tmp_path / "testuser-contributions"

        monkeypatch.chdir(tmp_path)

        with (
            patch("collect_contributions.Github") as MockGithub,
            patch.object(cc, "collect_pr_reviews") as m_reviews,
            patch.object(cc, "collect_authored_issues") as m_issues,
            patch.object(cc, "collect_authored_prs") as m_prs,
        ):
            mock_g = MockGithub.return_value
            mock_rate = MagicMock()
            mock_rate.core.remaining = 4999
            mock_rate.core.limit = 5000
            mock_rate.search.remaining = 29
            mock_rate.search.limit = 30
            mock_g.get_rate_limit.return_value = mock_rate

            cc.main(["testuser", "testorg", "--token", "ghp_fake"])

        assert (out_dir / "pr-reviews").is_dir()
        assert (out_dir / "issues").is_dir()
        assert (out_dir / "pr-authored").is_dir()

        m_reviews.assert_called_once()
        m_issues.assert_called_once()
        m_prs.assert_called_once()

        assert m_reviews.call_args[0][1] == "testuser"
        assert m_reviews.call_args[0][2] == "testorg"

    def test_exits_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            cc.main(["testuser", "testorg"])
