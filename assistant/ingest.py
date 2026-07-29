"""dlt pipeline pulling a repo's issues, pull requests, comments and docs into the raw schema."""

import base64
import logging
import re
from collections.abc import Iterator
from typing import Any

import dlt
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator

from assistant.config import get_settings

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
MAX_DOC_BYTES = 500_000

logger = logging.getLogger(__name__)


def _client() -> RESTClient:
    """A GitHub client. Paginator is explicit, dlt auto-detect can silently drop pages past 1."""
    return RESTClient(
        base_url=GITHUB_API,
        auth=BearerTokenAuth(token=get_settings().github_token),
        paginator=HeaderLinkPaginator(),
    )


@dlt.resource(name="issues", write_disposition="merge", primary_key="id")
def issues(repo: str) -> Iterator[dict[str, Any]]:
    """Yield one repo's issues since `ingest_since`; PRs (marked `pull_request`) are filtered."""
    settings = get_settings()
    params = {"state": "all", "per_page": PER_PAGE, "since": settings.ingest_since.isoformat()}
    for page in _client().paginate(f"/repos/{repo}/issues", params=params):
        for row in page:
            if "pull_request" in row:
                continue
            yield {
                "id": row["id"],
                "number": row["number"],
                "title": row["title"],
                "body": row["body"] or "",
                "html_url": row["html_url"],
                "updated_at": row["updated_at"],
                "repo": repo,
            }


@dlt.resource(name="pull_requests", write_disposition="merge", primary_key="id")
def pull_requests(repo: str) -> Iterator[dict[str, Any]]:
    """Yield PRs since `ingest_since`; `/pulls` has no `since` param, so stop early once past it."""
    since = get_settings().ingest_since.isoformat()
    params = {"state": "all", "per_page": PER_PAGE, "sort": "updated", "direction": "desc"}
    for page in _client().paginate(f"/repos/{repo}/pulls", params=params):
        for row in page:
            if row["updated_at"] < since:
                return
            yield {
                "id": row["id"],
                "number": row["number"],
                "title": row["title"],
                "body": row["body"] or "",
                "html_url": row["html_url"],
                "updated_at": row["updated_at"],
                "repo": repo,
            }


@dlt.resource(name="comments", write_disposition="merge", primary_key="id")
def comments(repo: str) -> Iterator[dict[str, Any]]:
    """Yield comments since `ingest_since`, each carrying the thread's `issue_url`."""
    params = {"per_page": PER_PAGE, "since": get_settings().ingest_since.isoformat()}
    for page in _client().paginate(f"/repos/{repo}/issues/comments", params=params):
        for row in page:
            yield {
                "id": row["id"],
                "body": row["body"] or "",
                "html_url": row["html_url"],
                "issue_url": row["issue_url"],
                "updated_at": row["updated_at"],
                "repo": repo,
            }


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Glob to regex: `**/` and a trailing `**` match any depth; elsewhere `*` is one segment."""
    regex = ""
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i : i + 3] == "**/":
            regex += "(?:[^/]*/)*"
            i += 3
        elif pattern[i : i + 2] == "**" and i + 2 == n:
            regex += ".*"
            i += 2
        elif pattern[i] == "*":
            regex += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            regex += "[^/]"
            i += 1
        else:
            regex += re.escape(pattern[i])
            i += 1
    return re.compile(f"^{regex}$")


@dlt.resource(name="docs", write_disposition="merge", primary_key=("repo", "path"))
def docs(repo: str) -> Iterator[dict[str, Any]]:
    """Yield one commit's snapshot of every blob matching `DOCS_GLOBS`, decoded from base64."""
    # Case-sensitive like git's own globs: the default skips README.MD, add `**/*.MD` to catch it.
    patterns = [_glob_to_regex(glob) for glob in get_settings().docs_globs_list()]
    client = _client()
    branch = client.get(f"/repos/{repo}").json()["default_branch"]
    sha = client.get(f"/repos/{repo}/branches/{branch}").json()["commit"]["sha"]
    response = client.get(f"/repos/{repo}/git/trees/{sha}", params={"recursive": 1}).json()
    # GitHub silently truncates very large trees; response["truncated"] is not checked here.
    for entry in response["tree"]:
        path = entry["path"]
        if entry["type"] != "blob" or not any(pattern.match(path) for pattern in patterns):
            continue
        if entry["size"] > MAX_DOC_BYTES:
            logger.warning(
                "skipping %s: %d bytes over the %d byte limit", path, entry["size"], MAX_DOC_BYTES
            )
            continue
        blob = client.get(f"/repos/{repo}/git/blobs/{entry['sha']}").json()
        try:
            text = base64.b64decode(blob["content"]).decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("skipping %s: not valid UTF-8", path)
            continue
        yield {
            "id": entry["sha"],
            "path": path,
            "body": text,
            "html_url": f"https://github.com/{repo}/blob/{branch}/{path}",
            "repo": repo,
        }


def run_ingestion(repo: str) -> None:
    """Load one repo's issues, pull requests, comments and docs into `raw`."""
    pipeline = dlt.pipeline(
        pipeline_name="github_repo_assistant",
        destination=dlt.destinations.postgres(credentials=get_settings().database_url),
        dataset_name="raw",
    )
    resources = [
        issues(repo.lower()),
        pull_requests(repo.lower()),
        comments(repo.lower()),
        docs(repo.lower()),
    ]
    info = pipeline.run(resources)
    print(info)


if __name__ == "__main__":
    for repo in get_settings().repo_list():
        run_ingestion(repo)
