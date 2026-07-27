"""dlt pipeline pulling a repository's issues into the raw schema."""

import dlt
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator

from assistant.config import get_settings

GITHUB_API = "https://api.github.com"
PER_PAGE = 100


def _client() -> RESTClient:
    """A GitHub REST client authenticated with the configured token.

    The paginator is declared explicitly: dlt auto-detects one from the first response and
    silently falls back to a single page when detection scores zero, which would drop every
    row past page 1 with no error raised.
    """
    return RESTClient(
        base_url=GITHUB_API,
        auth=BearerTokenAuth(token=get_settings().github_token),
        paginator=HeaderLinkPaginator(),
    )


@dlt.resource(name="issues", write_disposition="merge", primary_key="id")
def issues(repo: str):
    """Yield one repository's issues since `ingest_since`, excluding pull requests.

    GitHub's `/issues` endpoint also returns pull requests, marked by a `pull_request` key;
    those are filtered out here or every PR would be ingested twice under two source types.
    """
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
    """Load one repository's issues into `raw.issues`, tagging rows with the lower-cased slug.

    dlt's postgres destination does not read `DATABASE_URL`: by default it resolves its own
    credentials from `DESTINATION__POSTGRES__CREDENTIALS`, an env var our own `.env` loader
    (pydantic-settings) never exports into `os.environ`. Passing the connection string straight
    from `get_settings()` here avoids that mismatch and a second copy of the secret in `.env`.
    """
    pipeline = dlt.pipeline(
        pipeline_name="github_repo_assistant",
        destination=dlt.destinations.postgres(credentials=get_settings().database_url),
        dataset_name="raw",
    )
    info = pipeline.run(issues(repo.lower()))
    print(info)


if __name__ == "__main__":
    run_ingestion(get_settings().repo)
