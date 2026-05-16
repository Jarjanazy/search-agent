"""Tests for src/github_client.py — no real GitHub API calls."""

import pytest
from unittest.mock import MagicMock, patch
from github import GithubException

from src.github_client import commit_markdown


GITHUB_TOKEN = "fake-token"
REPO_NAME = "user/repo"
FILE_PATH = "reports/output.md"
CONTENT = "# Hello World"
BRANCH = "main"
COMMIT_MSG = "docs: add research report"


@pytest.fixture()
def mock_repo():
    """Return a mock repo object."""
    return MagicMock()


@pytest.fixture()
def patched_github(mock_repo):
    """Patch Github so no real HTTP calls are made.

    Github is now used as a context manager (`with Github(...) as gh:`), so we
    configure __enter__ to return the same mock instance and __exit__ to be a
    no-op, ensuring get_repo() is still reachable on the yielded mock.
    """
    with patch("src.github_client.Github") as MockGithub:
        instance = MockGithub.return_value
        # Support `with Github(...) as gh:` — __enter__ must return the instance.
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=False)
        instance.get_repo.return_value = mock_repo
        yield MockGithub, mock_repo


class TestCommitMarkdown:
    def test_creates_file_when_not_exists(self, patched_github):
        """When get_contents raises 404, create_file is called; update_file is not."""
        _, mock_repo = patched_github
        not_found = GithubException(404, {"message": "Not Found"}, None)
        mock_repo.get_contents.side_effect = not_found

        commit_markdown(GITHUB_TOKEN, REPO_NAME, FILE_PATH, CONTENT, BRANCH, COMMIT_MSG)

        mock_repo.create_file.assert_called_once_with(
            path=FILE_PATH,
            message=COMMIT_MSG,
            content=CONTENT,
            branch=BRANCH,
        )
        mock_repo.update_file.assert_not_called()

    def test_updates_file_when_exists(self, patched_github):
        """When get_contents returns an object, update_file is called with sha; create_file is not."""
        _, mock_repo = patched_github
        existing = MagicMock()
        existing.sha = "abc123sha"
        mock_repo.get_contents.return_value = existing

        commit_markdown(GITHUB_TOKEN, REPO_NAME, FILE_PATH, CONTENT, BRANCH, COMMIT_MSG)

        mock_repo.update_file.assert_called_once_with(
            path=FILE_PATH,
            message=COMMIT_MSG,
            content=CONTENT,
            sha="abc123sha",
            branch=BRANCH,
        )
        mock_repo.create_file.assert_not_called()

    def test_reraises_non_404_exception(self, patched_github):
        """When get_contents raises a non-404 GithubException (e.g. 403), it is re-raised."""
        _, mock_repo = patched_github
        forbidden = GithubException(403, {"message": "Forbidden"}, None)
        mock_repo.get_contents.side_effect = forbidden

        with pytest.raises(GithubException) as exc_info:
            commit_markdown(GITHUB_TOKEN, REPO_NAME, FILE_PATH, CONTENT, BRANCH, COMMIT_MSG)

        assert exc_info.value.status == 403
        mock_repo.create_file.assert_not_called()
        mock_repo.update_file.assert_not_called()

    def test_commit_message_passed_to_create_file(self, patched_github):
        """commit_message is forwarded correctly to create_file."""
        _, mock_repo = patched_github
        not_found = GithubException(404, {"message": "Not Found"}, None)
        mock_repo.get_contents.side_effect = not_found
        custom_msg = "chore: custom commit message"

        commit_markdown(GITHUB_TOKEN, REPO_NAME, FILE_PATH, CONTENT, BRANCH, custom_msg)

        call_kwargs = mock_repo.create_file.call_args.kwargs
        assert call_kwargs["message"] == custom_msg

    def test_commit_message_passed_to_update_file(self, patched_github):
        """commit_message is forwarded correctly to update_file."""
        _, mock_repo = patched_github
        existing = MagicMock()
        existing.sha = "def456sha"
        mock_repo.get_contents.return_value = existing
        custom_msg = "fix: update existing report"

        commit_markdown(GITHUB_TOKEN, REPO_NAME, FILE_PATH, CONTENT, BRANCH, custom_msg)

        call_kwargs = mock_repo.update_file.call_args.kwargs
        assert call_kwargs["message"] == custom_msg
