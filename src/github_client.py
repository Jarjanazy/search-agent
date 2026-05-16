"""GitHub client for committing Markdown files via PyGitHub."""

from github import Github, GithubException


def commit_markdown(
    github_token: str,
    repo_name: str,
    file_path: str,
    content: str,
    branch: str,
    commit_message: str,
) -> None:
    """Commit a Markdown file to a GitHub repo, creating or updating as needed.

    Args:
        github_token: Personal access token with repo write permissions.
        repo_name: Full repo name, e.g. "owner/repo".
        file_path: Path within the repo, e.g. "reports/output.md".
        content: String content of the file.
        branch: Target branch name.
        commit_message: Commit message string.
    """
    with Github(github_token) as gh:
        repo = gh.get_repo(repo_name)

        try:
            existing = repo.get_contents(file_path, ref=branch)
            # get_contents returns a list when file_path is a directory; take the
            # first entry defensively, though callers should always pass a file path.
            if isinstance(existing, list):
                existing = existing[0]
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
        except GithubException as e:
            if e.status != 404:
                raise
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch,
            )
