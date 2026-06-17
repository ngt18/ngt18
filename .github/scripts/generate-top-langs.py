\
#!/usr/bin/env python3
"""
Gera profile/top-langs.svg com as cinco linguagens mais utilizadas.

Fontes:
- repositórios públicos e privados pertencentes ao usuário autenticado;
- repositórios adicionais definidos em EXTRA_LANGUAGE_REPOS.

O script usa apenas a biblioteca padrão e não mostra nomes de repositórios
privados no SVG ou nos logs.
"""

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.sax.saxutils as saxutils

GH_STATS_TOKEN = os.environ.get("GH_STATS_TOKEN")
EXTRA_LANGUAGE_REPOS = os.environ.get("EXTRA_LANGUAGE_REPOS", "")

OUTPUT_PATH = "profile/top-langs.svg"
GITHUB_API = "https://api.github.com"

MAX_LANGUAGES = 5
CARD_WIDTH = 520
CARD_HEIGHT = 250
PADDING_X = 28
CONTENT_WIDTH = CARD_WIDTH - (PADDING_X * 2)

LANGUAGE_COLORS = {
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "Python": "#3572A5",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "C#": "#178600",
    "PHP": "#4F5D95",
    "Ruby": "#701516",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Swift": "#ffac45",
    "C": "#555555",
    "C++": "#f34b7d",
    "Shell": "#89e051",
    "Dockerfile": "#384d54",
    "Objective-C": "#438eff",
    "Scala": "#c22d40",
    "Lua": "#000080",
    "R": "#198CE7",
    "Dart": "#00B4AB",
    "Elixir": "#6e4a7e",
    "Haskell": "#5e5086",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "PLpgSQL": "#336790",
    "Batchfile": "#C1F12E",
}

FALLBACK_COLORS = [
    "#ff79c6",
    "#bd93f9",
    "#8be9fd",
    "#50fa7b",
    "#ffb86c",
    "#ff5555",
    "#f1fa8c",
    "#6272a4",
]


def escape_text(value: str) -> str:
    return saxutils.escape(str(value))


def color_for_language(name: str) -> str:
    if name in LANGUAGE_COLORS:
        return LANGUAGE_COLORS[name]

    digest = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return FALLBACK_COLORS[digest % len(FALLBACK_COLORS)]


def api_request(path: str):
    request = urllib.request.Request(GITHUB_API + path)
    request.add_header("Authorization", f"Bearer {GH_STATS_TOKEN}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "github-profile-language-card")

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_owned_repositories() -> list:
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


def parse_extra_repositories(raw: str) -> list:
    if not raw:
        return []

    repositories = []

    for item in re.split(r"[,\s;]+", raw.strip()):
        item = item.strip()

        if item and "/" in item:
            repositories.append(item)

    return repositories


def fetch_languages(owner: str, repository: str) -> dict:
    try:
        return api_request(f"/repos/{owner}/{repository}/languages")
    except Exception:
        return {}


def build_language_totals(
    repositories: list,
    extra_identifiers: list,
) -> tuple[dict, int]:
    seen = set()
    totals: dict[str, int] = {}
    processed = 0

    for repository in repositories:
        if repository.get("fork"):
            continue

        owner = repository.get("owner", {}).get("login")
        name = repository.get("name")

        if not owner or not name:
            continue

        identifier = f"{owner}/{name}"

        if identifier in seen:
            continue

        seen.add(identifier)

        for language, byte_count in fetch_languages(owner, name).items():
            totals[language] = totals.get(language, 0) + int(byte_count)

        processed += 1

    for identifier in extra_identifiers:
        if identifier in seen:
            continue

        parts = identifier.split("/", 1)

        if len(parts) != 2:
            continue

        owner, name = parts
        seen.add(identifier)

        for language, byte_count in fetch_languages(owner, name).items():
            totals[language] = totals.get(language, 0) + int(byte_count)

        processed += 1

    return totals, processed


def svg_document(language_totals: dict) -> str:
    total_bytes = sum(language_totals.values())

    if total_bytes <= 0:
        visible_languages = []
    else:
        visible_languages = sorted(
            language_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:MAX_LANGUAGES]

    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{CARD_WIDTH}" height="{CARD_HEIGHT}" '
            f'viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" role="img" '
            'aria-label="Top 5 linguagens">'
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
            f'  <text x="{PADDING_X}" y="38" fill="#ff79c6" '
            'font-size="22" font-family="Segoe UI, Ubuntu, sans-serif" '
            'font-weight="700">Top 5 linguagens</text>'
        ),
        (
            f'  <rect x="{PADDING_X}" y="52" width="54" height="3" '
            'rx="1.5" fill="#ff79c6"/>'
        ),
    ]

    if not visible_languages:
        lines.append(
            f'  <text x="{PADDING_X}" y="100" fill="#b7b9c5" '
            'font-size="14" font-family="Segoe UI, Ubuntu, sans-serif">'
            'Nenhuma linguagem encontrada</text>'
        )
    else:
        first_baseline = 79
        row_height = 35
        bar_offset = 9
        bar_height = 8

        for index, (language, byte_count) in enumerate(visible_languages):
            percentage = (byte_count / total_bytes) * 100
            color = color_for_language(language)
            baseline_y = first_baseline + (index * row_height)
            bar_y = baseline_y + bar_offset
            filled_width = max(3.0, CONTENT_WIDTH * (percentage / 100))

            lines.extend(
                [
                    (
                        f'  <text x="{PADDING_X}" y="{baseline_y}" '
                        'fill="#f8f8f2" font-size="14" '
                        'font-family="Segoe UI, Ubuntu, sans-serif" '
                        f'font-weight="600">{escape_text(language)}</text>'
                    ),
                    (
                        f'  <text x="{CARD_WIDTH - PADDING_X}" y="{baseline_y}" '
                        'fill="#c3c5cf" font-size="13" '
                        'font-family="Segoe UI, Ubuntu, sans-serif" '
                        f'text-anchor="end">{percentage:.1f}%</text>'
                    ),
                    (
                        f'  <rect x="{PADDING_X}" y="{bar_y}" '
                        f'width="{CONTENT_WIDTH}" height="{bar_height}" rx="4" '
                        'fill="#44475a" opacity="0.62"/>'
                    ),
                    (
                        f'  <rect x="{PADDING_X}" y="{bar_y}" '
                        f'width="{filled_width:.2f}" height="{bar_height}" rx="4" '
                        f'fill="{color}"/>'
                    ),
                ]
            )

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
        owned_repositories = fetch_owned_repositories()
    except urllib.error.HTTPError as error:
        print(
            "Erro: não foi possível consultar a API do GitHub. "
            "Verifique o token.",
            file=sys.stderr,
        )
        print(f"Status HTTP: {error.code}", file=sys.stderr)
        return 1
    except Exception as error:
        print("Erro inesperado ao consultar a API do GitHub.", file=sys.stderr)
        print(f"Detalhe: {error}", file=sys.stderr)
        return 1

    extra_repositories = parse_extra_repositories(EXTRA_LANGUAGE_REPOS)
    language_totals, processed = build_language_totals(
        owned_repositories,
        extra_repositories,
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as output:
        output.write(svg_document(language_totals))

    print(
        "Card de linguagens gerado. "
        f"Repositórios processados: {processed}. "
        f"Linguagens encontradas: {len(language_totals)}."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
