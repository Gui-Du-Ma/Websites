#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador Local de Landing Pages para Clínicas Odontológicas.
Organiza cada site gerado dentro de sua própria subpasta pronta para deploy (Netlify/Vercel),
separando index.html, style.css e script.js, com suporte a cor principal personalizada ({{COR_PRIMARIA}}).
"""

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent

TEMPLATES = {
    "1": BASE_DIR / "template_1.html",
    "2": BASE_DIR / "template_2.html",
    "3": BASE_DIR / "template_3.html",
    "4": BASE_DIR / "template_4.html",
}

DEFAULT_COLORS = {
    "1": "#1B365D",
    "2": "#0F766E",
    "3": "#1E40AF",
    "4": "#0F766E",
}

PLACEHOLDERS = [
    "NOME",
    "CIDADE",
    "WHATSAPP",
    "ENDERECO",
    "LINK_MAPS",
    "HORARIO",
    "NOTA",
    "AVALIACAO_1",
    "AVALIACAO_2",
    "AVALIACAO_3",
    "COR_PRIMARIA",
]


def slugify(text: str) -> str:
    """Converte o nome da clínica em slug limpo (minúsculo, sem acentos, espaços virando hífen)."""
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "clinica"


def normalize_hex_color(color_value: str, template_id: str) -> str:
    """Garante um código HEX válido ou retorna a cor padrão do template escolhido."""
    default_hex = DEFAULT_COLORS.get(str(template_id), "#1B365D")
    raw = str(color_value or "").strip()
    if not raw:
        return default_hex
    if not raw.startswith("#"):
        raw = "#" + raw
    if re.fullmatch(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", raw):
        return raw.upper()
    return default_hex


def resolve_maps_link(link_maps: str, endereco: str) -> str:
    """Retorna o link do Google Maps informado ou gera um link de busca automático pelo endereço."""
    cleaned_link = str(link_maps or "").strip()
    if cleaned_link:
        return cleaned_link
    addr = str(endereco or "").strip()
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(addr)}"


def render_template(template_id: str, data: dict) -> str:
    tid = str(template_id)
    template_path = TEMPLATES.get(tid)
    if not template_path or not template_path.exists():
        raise FileNotFoundError(f"Template não encontrado: {template_id}")

    content = template_path.read_text(encoding="utf-8")

    # Prepara os dados garantindo que COR_PRIMARIA use o padrão do template caso omitida
    # e que LINK_MAPS sempre tenha um link válido (informado ou gerado pelo endereço)
    merged_data = dict(data)
    merged_data["COR_PRIMARIA"] = normalize_hex_color(
        merged_data.get("COR_PRIMARIA", merged_data.get("cor_primaria", "")),
        tid,
    )
    merged_data["LINK_MAPS"] = resolve_maps_link(
        merged_data.get("LINK_MAPS", merged_data.get("link_maps", "")),
        merged_data.get("ENDERECO", merged_data.get("endereco", "")),
    )

    for key in PLACEHOLDERS:
        val = str(merged_data.get(key, "")).strip()
        content = content.replace(f"{{{{{key}}}}}", val)
    return content


def split_html_css_js(rendered_html: str) -> tuple[str, str, str]:
    """
    Extrai blocos <style>...</style> para style.css e blocos <script>...</script> inline
    (exceto tailwind.config) para script.js, mantendo scripts externos e o tailwind.config no index.html.
    """
    css_parts: list[str] = []
    js_parts: list[str] = []

    # 1. Extrair todas as tags <style>...</style>
    style_pattern = re.compile(r"<style\b[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
    for match in style_pattern.finditer(rendered_html):
        style_content = match.group(1).strip()
        if style_content:
            css_parts.append(style_content)

    html_without_styles = style_pattern.sub("", rendered_html)

    # 2. Extrair tags <script>...</script> que NÃO possuem atributo src=... e NÃO contêm tailwind.config
    script_pattern = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.DOTALL | re.IGNORECASE)

    def _replace_inline_script(match: re.Match) -> str:
        attrs = match.group(1) or ""
        body = (match.group(2) or "").strip()
        # Se tiver src= nos atributos (ex: CDN do Tailwind) ou contiver tailwind.config, mantém inline no HTML
        if re.search(r"\bsrc\s*=", attrs, re.IGNORECASE) or "tailwind.config" in body:
            return match.group(0)
        if body:
            js_parts.append(body)
        return ""

    cleaned_html = script_pattern.sub(_replace_inline_script, html_without_styles)

    # 3. Inserir <link rel="stylesheet" href="style.css"> antes de </head>
    link_tag = '  <link rel="stylesheet" href="style.css">\n'
    if re.search(r"</head>", cleaned_html, re.IGNORECASE):
        cleaned_html = re.sub(
            r"(</head>)",
            f"{link_tag}\\1",
            cleaned_html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        cleaned_html = link_tag + cleaned_html

    # 4. Inserir <script src="script.js"></script> antes de </body>
    script_tag = '  <script src="script.js"></script>\n'
    if re.search(r"</body>", cleaned_html, re.IGNORECASE):
        cleaned_html = re.sub(
            r"(</body>)",
            f"{script_tag}\\1",
            cleaned_html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        cleaned_html = cleaned_html + "\n" + script_tag

    # Limpar linhas em branco excessivas deixadas pela remoção de blocos
    cleaned_html = re.sub(r"\n{3,}", "\n\n", cleaned_html).strip() + "\n"

    default_css_header = (
        "/* Folha de estilos da Landing Page */\n"
        "html {\n"
        "  scroll-behavior: smooth;\n"
        "}\n"
    )
    final_css = default_css_header
    if css_parts:
        final_css += "\n" + "\n\n".join(css_parts) + "\n"

    final_js = "\n\n".join(js_parts).strip() + "\n" if js_parts else "// Script da Landing Page\n"

    return cleaned_html, final_css, final_js


def generate_page(
    data: dict,
    template_id: str = "1",
    output_dir: Path = BASE_DIR / "gerados",
    append_style_suffix: bool = False,
) -> Path:
    """
    Cria a subpasta da clínica (ex: gerados/clinica-sorriso/) contendo:
    - index.html
    - style.css
    - script.js
    """
    base_slug = slugify(data.get("NOME", "clinica"))
    folder_name = f"{base_slug}-estilo-{template_id}" if append_style_suffix else base_slug
    site_dir = output_dir / folder_name
    site_dir.mkdir(parents=True, exist_ok=True)

    rendered_html = render_template(template_id, data)
    index_html, style_css, script_js = split_html_css_js(rendered_html)

    index_path = site_dir / "index.html"
    style_path = site_dir / "style.css"
    script_path = site_dir / "script.js"

    index_path.write_text(index_html, encoding="utf-8")
    style_path.write_text(style_css, encoding="utf-8")
    script_path.write_text(script_js, encoding="utf-8")

    return site_dir


def generate_all_styles(data: dict, output_dir: Path = BASE_DIR / "gerados") -> list[Path]:
    paths = []
    for tid in ("1", "2", "3", "4"):
        paths.append(generate_page(data, tid, output_dir, append_style_suffix=True))
    return paths


def interactive_mode():
    print("=" * 60)
    print(" GERADOR LOCAL DE LANDING PAGES ODONTOLÓGICAS (4 ESTILOS)")
    print("=" * 60)
    print("Preencha os dados reais da clínica para gerar a pasta de deploy:\n")

    data = {}
    prompts = [
        ("NOME", "Nome da Clínica"),
        ("CIDADE", "Cidade / UF"),
        ("WHATSAPP", "WhatsApp (ex: (11) 99999-9999)"),
        ("ENDERECO", "Endereço completo"),
        ("LINK_MAPS", "Link do Google Maps (opcional, Enter para gerar pelo endereço)"),
        ("HORARIO", "Horário de funcionamento (ex: Seg a Sex, 08h às 18h)"),
        ("NOTA", "Nota no Google (ex: 4.9)"),
        ("AVALIACAO_1", "Avaliação real 1 do Google"),
        ("AVALIACAO_2", "Avaliação real 2 do Google"),
        ("AVALIACAO_3", "Avaliação real 3 do Google"),
    ]

    for key, label in prompts:
        val = input(f"{label}: ").strip()
        data[key] = val

    escolha = input(
        "\nQual estilo deseja gerar? [1=Clássico, 2=Clínico, 3=Minimalista, 4=Moderno/Conversão] (Padrão: 1): "
    ).strip().upper() or "1"

    padrao_cor = DEFAULT_COLORS.get(escolha, "#1B365D")
    cor_input = input(
        f"Cor Principal em HEX (ex: {padrao_cor}) [Enter para usar a cor padrão do estilo]: "
    ).strip()
    if cor_input:
        data["COR_PRIMARIA"] = cor_input

    if escolha in ("1", "2", "3", "4"):
        site_dir = generate_page(data, escolha)
        print(f"\n[OK] Site gerado pronto para deploy em: {site_dir}")
        print(f"     - {site_dir / 'index.html'}")
        print(f"     - {site_dir / 'style.css'}")
        print(f"     - {site_dir / 'script.js'}")
    elif escolha in ("T", "ALL", "TODOS"):
        outs = generate_all_styles(data)
        print("\n[OK] 4 pastas geradas com sucesso:")
        for p in outs:
            print(f" - {p} (index.html, style.css, script.js)")
    else:
        site_dir = generate_page(data, "1")
        print(f"\n[OK] Site gerado pronto para deploy em: {site_dir}")
        print(f"     - {site_dir / 'index.html'}")
        print(f"     - {site_dir / 'style.css'}")
        print(f"     - {site_dir / 'script.js'}")


def process_csv(csv_path: Path, template_choice: str, output_dir: Path, custom_color: str = ""):
    with csv_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            data = {k: row.get(k, row.get(k.lower(), "")) for k in PLACEHOLDERS}
            if custom_color and not data.get("COR_PRIMARIA"):
                data["COR_PRIMARIA"] = custom_color
            t_id = str(row.get("TEMPLATE", row.get("template", template_choice))).strip() or "1"
            if t_id.upper() in ("ALL", "T", "TODOS"):
                generate_all_styles(data, output_dir)
            else:
                generate_page(data, t_id, output_dir)
            count += 1
    print(f"[OK] {count} clínica(s) gerada(s) em subpastas prontas para deploy em: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Gerador Local de Landing Pages para Clínicas Odontológicas")
    parser.add_argument("--csv", type=str, help="Caminho de um arquivo CSV com os dados das clínicas")
    parser.add_argument("--json", type=str, help="Caminho de um arquivo JSON com os dados da clínica")
    parser.add_argument("--template", type=str, default="1", help="1, 2, 3, 4 ou ALL")
    parser.add_argument("--cor", type=str, default="", help="Cor principal em HEX (ex: #0F766E)")
    parser.add_argument("--saida", type=str, default=str(BASE_DIR / "gerados"), help="Pasta de saída")
    args = parser.parse_args()

    out_dir = Path(args.saida)

    if args.csv:
        process_csv(Path(args.csv), args.template, out_dir, args.cor)
    elif args.json:
        raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            if args.cor and not item.get("COR_PRIMARIA") and not item.get("cor_primaria"):
                item["COR_PRIMARIA"] = args.cor
            t_id = str(item.get("TEMPLATE", item.get("template", args.template))).strip() or "1"
            if t_id.upper() in ("ALL", "T", "TODOS"):
                generate_all_styles(item, out_dir)
            else:
                generate_page(item, t_id, out_dir)
        print(f"[OK] Subpastas geradas em: {out_dir}")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
