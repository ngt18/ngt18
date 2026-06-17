\
#!/usr/bin/env python3
"""
Gera profile/stats.svg com estatísticas públicas e privadas do usuário
autenticado pelo GH_STATS_TOKEN.

O card mostra:
- commits reconhecidos no gráfico de contribuições;
- pull requests abertos;
- issues abertas;
- estrelas recebidas em repositórios próprios não-forks.

Usa apenas a biblioteca padrão do Python.
"""

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.sax.saxutils as saxutils

GH_STATS_TOKEN = os.environ.get("GH_STATS_TOKEN")
OUTPUT_PATH = "profile/stats.svg"
GITHUB_API = "https://api.github.com"

CARD_WIDTH = 520
CARD_HEIGHT = 250

GRAPHQL_USER_QUERY = """
query {
  viewer {
    login
    createdAt
  }
}
"""

GRAPHQL_COMMITS_QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
    }
  }
}
"""


def escape_text(value: str) -> str:
    return saxutils.escape(str(value))


def api_request(path: str):
    request = urllib.request.Request(GITHUB_API + path)
    request.add_header("Authorization", f"Bearer {GH_STATS_TOKEN}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "github-profile-stats-card")

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def graphql_request(query: str, variables: dict | None = None):
    payload = json.dumps(
        {"query": query, "variables": variables or {}}
    ).encode("utf-8")

    request = urllib.request.Request(
        GITHUB_API + "/graphql",
        data=payload,
        method="POST",
    )
    request.add_header("Authorization", f"Bearer {GH_STATS_TOKEN}")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "github-profile-stats-card")

    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("errors"):
        raise RuntimeError(result["errors"][0].get("message", "Erro GraphQL"))

    return result["data"]


def fetch_all_owned_repositories() -> list:
    repositories = []
    page = 1

    while True:
        batch = api_request(
            f"/user/repos?affiliation=owner&per_page=100&page={page}"
        )

        if not batch:
            break

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return repositories


def fetch_search_count(login: str, item_type: str) -> int:
    query = urllib.parse.quote(f"author:{login} type:{item_type}")
    result = api_request(f"/search/issues?q={query}&per_page=1")
    return int(result.get("total_count", 0))


def fetch_total_commits(created_at: str) -> int:
    created_year = int(created_at[:4])
    current_year = dt.datetime.now(dt.timezone.utc).year
    now = dt.datetime.now(dt.timezone.utc)
    total = 0

    for year in range(created_year, current_year + 1):
        start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)

        if year == current_year:
            end = now
        else:
            end = dt.datetime(
                year,
                12,
                31,
                23,
                59,
                59,
                tzinfo=dt.timezone.utc,
            )

        data = graphql_request(
            GRAPHQL_COMMITS_QUERY,
            {
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": end.isoformat().replace("+00:00", "Z"),
            },
        )

        total += int(
            data["viewer"]["contributionsCollection"][
                "totalCommitContributions"
            ]
        )

    return total


def metric_card(
    x: int,
    y: int,
    label: str,
    value: int,
    accent: str,
) -> list[str]:
    return [
        (
            f'  <rect x="{x}" y="{y}" width="224" height="68" rx="12" '
            'fill="#303240" stroke="#44475a"/>'
        ),
        (
            f'  <circle cx="{x + 20}" cy="{y + 20}" r="5" '
            f'fill="{accent}"/>'
        ),
        (
            f'  <text x="{x + 34}" y="{y + 24}" fill="#b9bbc7" '
            'font-size="13" font-family="Segoe UI, Ubuntu, sans-serif" '
            f'font-weight="600">{escape_text(label)}</text>'
        ),
        (
            f'  <text x="{x + 18}" y="{y + 55}" fill="#f8f8f2" '
            'font-size="25" font-family="Segoe UI, Ubuntu, sans-serif" '
            f'font-weight="700">{value}</text>'
        ),
    ]


def generate_svg(
    commits: int,
    pull_requests: int,
    issues: int,
    stars: int,
) -> str:
    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{CARD_WIDTH}" height="{CARD_HEIGHT}" '
            f'viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" role="img" '
            'aria-label="GitHub Stats">'
        ),
        "  <defs>",
        '    <linearGradient id="card-bg" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0%" stop-color="#282a36"/>',
        '      <stop offset="100%" stop-color="#242631"/>',
        "    </linearGradient>",
        "  </defs>",
        (
            f'  <rect x="0.5" y="0.5" width="{CARD_WIDTH - 1}" '
            f'height="{CARD_HEIGHT - 1}" rx="16" fill="url(#card-bg)" '
            'stroke="#44475a"/>'
        ),
        (
            '  <text x="28" y="38" fill="#ff79c6" font-size="22" '
            'font-family="Segoe UI, Ubuntu, sans-serif" '
            'font-weight="700">GitHub Stats</text>'
        ),
        '  <rect x="28" y="52" width="54" height="3" rx="1.5" fill="#ff79c6"/>',
    ]

    lines.extend(metric_card(28, 70, "Commits", commits, "#8be9fd"))
    lines.extend(metric_card(268, 70, "Pull requests", pull_requests, "#bd93f9"))
    lines.extend(metric_card(28, 154, "Issues", issues, "#ffb86c"))
    lines.extend(metric_card(268, 154, "Estrelas", stars, "#f1fa8c"))
    lines.append("</svg>")

    return "\n".join(lines)


def main() -> int:
    if not GH_STATS_TOKEN:
        print(
            "Erro: a variável de ambiente GH_STATS_TOKEN não está definida.",
            file=sys.stderr,
        )
        return 1

    try:
        viewer = graphql_request(GRAPHQL_USER_QUERY)["viewer"]
        login = viewer["login"]
        created_at = viewer["createdAt"]

        repositories = fetch_all_owned_repositories()
        stars = sum(
            int(repository.get("stargazers_count", 0))
            for repository in repositories
            if not repository.get("fork")
        )

        commits = fetch_total_commits(created_at)
        pull_requests = fetch_search_count(login, "pr")
        issues = fetch_search_count(login, "issue")

    except urllib.error.HTTPError as error:
        print(
            "Erro: não foi possível consultar a API do GitHub. "
            "Verifique o token.",
            file=sys.stderr,
        )
        print(f"Status HTTP: {error.code}", file=sys.stderr)
        return 1
    except Exception as error:
        print("Erro ao gerar as estatísticas.", file=sys.stderr)
        print(f"Detalhe: {error}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as output:
        output.write(generate_svg(commits, pull_requests, issues, stars))

    print(
        "Card de estatísticas gerado. "
        f"Commits: {commits}; PRs: {pull_requests}; "
        f"Issues: {issues}; Estrelas: {stars}."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
