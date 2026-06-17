#!/usr/bin/env python3
"""
Gera o card profile/top-langs.svg somando as linguagens dos repositórios
pertencentes ao usuário autenticado e dos repositórios extras informados
pela variável de ambiente EXTRA_LANGUAGE_REPOS.

Não registra em log nomes de repositórios privados.
Usa apenas a biblioteca padrão do Python.
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
MAX_LANGS = 8
CARD_WIDTH = 350

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
    """Escapa caracteres especiais do XML."""
    return saxutils.escape(str(value))


def color_for_language(name: str) -> str:
    """Retorna a cor conhecida de uma linguagem ou uma cor fallback consistente."""
    if name in LANGUAGE_COLORS:
        return LANGUAGE_COLORS[name]
    index = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % len(FALLBACK_COLORS)
    return FALLBACK_COLORS[index]


def api_request(path: str):
    """Faz uma requisição autenticada à API REST do GitHub."""
    url = GITHUB_API + path
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {GH_STATS_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "generate-top-langs")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_owned_repositories() -> list:
    """Lista todos os repositórios pertencentes ao usuário autenticado."""
    results = []
    page = 1
    while True:
        batch = api_request(
            f"/user/repos?affiliation=owner&per_page=100&page={page}"
        )
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def parse_extra_repositories(raw: str) -> list:
    """Parseia EXTRA_LANGUAGE_REPOS separado por vírgula, ponto-e-vírgula ou quebra de linha."""
    if not raw:
        return []
    parts = re.split(r"[,\s;]+", raw.strip())
    repos = []
    for part in parts:
        part = part.strip()
        if part and "/" in part:
            repos.append(part)
    return repos


def fetch_languages(owner: str, repo: str) -> dict:
    """Consulta as linguagens de um repositório. Falhas retornam dicionário vazio."""
    try:
        return api_request(f"/repos/{owner}/{repo}/languages")
    except Exception:
        return {}


def build_language_totals(repositories: list, extra_identifiers: list) -> dict:
    """Soma os bytes de cada linguagem, evitando contar o mesmo repositório duas vezes."""
    seen = set()
    totals = {}
    processed = 0

    for repo in repositories:
        if repo.get("fork"):
            continue
        owner = repo.get("owner", {}).get("login")
        name = repo.get("name")
        if not owner or not name:
            continue
        identifier = f"{owner}/{name}"
        if identifier in seen:
            continue
        seen.add(identifier)

        languages = fetch_languages(owner, name)
        for language, bytes_count in languages.items():
            totals[language] = totals.get(language, 0) + bytes_count
        processed += 1

    for identifier in extra_identifiers:
        if identifier in seen:
            continue
        seen.add(identifier)
        parts = identifier.split("/", 1)
        if len(parts) != 2:
            continue
        owner, name = parts
        languages = fetch_languages(owner, name)
        for language, bytes_count in languages.items():
            totals[language] = totals.get(language, 0) + bytes_count
        processed += 1

    return totals, processed


def generate_svg(language_totals: dict) -> str:
    """Gera o SVG final com as oito linguagens principais."""
    total_bytes = sum(language_totals.values())

    if total_bytes == 0:
        return (
            f'<svg width="{CARD_WIDTH}" height="120" xmlns="http://www.w3.org/2000/svg">\n'
            f'  <rect width="{CARD_WIDTH}" height="120" rx="8" fill="#282a36"/>\n'
            '  <text x="20" y="35" fill="#ff79c6" font-size="16" font-family="Segoe UI, Ubuntu, sans-serif" font-weight="600">Linguagens mais utilizadas</text>\n'
            '  <text x="20" y="75" fill="#a9a9b3" font-size="12" font-family="Segoe UI, Ubuntu, sans-serif">Nenhuma linguagem encontrada</text>\n'
            '</svg>'
        )

    sorted_languages = sorted(
        language_totals.items(), key=lambda item: item[1], reverse=True
    )[:MAX_LANGS]

    row_height = 28
    header_height = 50
    footer_padding = 20
    height = header_height + len(sorted_languages) * row_height + footer_padding

    lines = [
        f'<svg width="{CARD_WIDTH}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        f'  <rect width="{CARD_WIDTH}" height="{height}" rx="8" fill="#282a36"/>',
        '  <text x="20" y="32" fill="#ff79c6" font-size="16" font-family="Segoe UI, Ubuntu, sans-serif" font-weight="600">Linguagens mais utilizadas</text>',
    ]

    y = header_height
    bar_max_width = CARD_WIDTH - 40

    for language, bytes_count in sorted_languages:
        percentage = bytes_count / total_bytes * 100
        color = color_for_language(language)
        bar_width = max(2, int((percentage / 100) * bar_max_width))

        lines.append(f'  <g transform="translate(20, {y})">')
        lines.append(
            f'    <text x="0" y="14" fill="#f8f8f2" font-size="13" font-family="Segoe UI, Ubuntu, sans-serif" font-weight="500">{escape_text(language)}</text>'
        )
        lines.append(
            f'    <text x="{bar_max_width}" y="14" fill="#a9a9b3" font-size="12" font-family="Segoe UI, Ubuntu, sans-serif" text-anchor="end">{percentage:.1f}%</text>'
        )
        lines.append(
            f'    <rect x="0" y="19" width="{bar_max_width}" height="6" rx="3" fill="#44475a" opacity="0.4"/>'
        )
        lines.append(
            f'    <rect x="0" y="19" width="{bar_width}" height="6" rx="3" fill="{color}"/>'
        )
        lines.append('  </g>')
        y += row_height

    lines.append('</svg>')
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
    except urllib.error.HTTPError as exc:
        print(
            "Erro: não foi possível consultar a API do GitHub. Verifique o token.",
            file=sys.stderr,
        )
        print(f"Status HTTP: {exc.code}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            "Erro inesperado ao consultar a API do GitHub.",
            file=sys.stderr,
        )
        print(f"Detalhe: {exc}", file=sys.stderr)
        return 1

    extra_identifiers = parse_extra_repositories(EXTRA_LANGUAGE_REPOS)
    language_totals, processed = build_language_totals(
        owned_repositories, extra_identifiers
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    svg = generate_svg(language_totals)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Card gerado com sucesso. Repositórios processados: {processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
