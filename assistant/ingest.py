"""dlt pipeline pulling a repository's issues into the raw schema."""

import dlt
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator

from assistant.config import get_settings

GITHUB_API = "https://api.github.com"
PER_PAGE = 100


def _client() -> RESTClient:
    """A GitHub client; paginator is explicit — dlt auto-detect can silently drop pages past 1."""
    return RESTClient(
        base_url=GITHUB_API,
        auth=BearerTokenAuth(token=get_settings().github_token),
        paginator=HeaderLinkPaginator(),
    )


@dlt.resource(name="issues", write_disposition="merge", primary_key="id")
def issues(repo: str):
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


def run_ingestion(repo: str) -> None:
    """Load one repo's issues into `raw.issues`; passes the DSN since dlt ignores our .env."""
    pipeline = dlt.pipeline(
        pipeline_name="github_repo_assistant",
        destination=dlt.destinations.postgres(credentials=get_settings().database_url),
        dataset_name="raw",
    )
    info = pipeline.run(issues(repo.lower()))
    print(info)


if __name__ == "__main__":
    run_ingestion(get_settings().repo)
