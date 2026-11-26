#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buscador Automatizado de Clínicas Odontológicas sem Site no Google Maps.
Utiliza Playwright (síncrono) com navegador visível (headless=False) e salva os leads
no formato exato compatível com o gerador.py (leads_encontrados.json).
"""

import json
import random
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "leads_encontrados.json"

# Domínios de redes sociais / agregadores de links que NÃO contam como site próprio oficial
ALLOWED_NON_WEBSITE_DOMAINS = (
    "instagram.com",
    "instagr.am",
    "facebook.com",
    "fb.com",
    "linktr.ee",
    "wa.me",
    "whatsapp.com",
    "api.whatsapp.com",
    "bit.ly",
    "taplink.cc",
    "beacons.ai",
    "bio.site",
    "campsite.bio",
)

FALLBACK_REVIEWS = [
    "Atendimento excelente, equipe muito atenciosa e ambiente super limpo e moderno.",
    "Profissionais muito cuidadosos e pontuais. Explicaram todo o tratamento com clareza.",
    "Ótima estrutura e atendimento humanizado desde a recepção até o consultório.",
]


def human_delay(min_s: float = 1.5, max_s: float = 3.0) -> None:
    """Pausa aleatória curta para simular navegação humana."""
    time.sleep(random.uniform(min_s, max_s))


def clean_phone_to_whatsapp(raw_phone: str) -> str:
    """
    Remove caracteres não numéricos e garante o DDI 55.
    Retorna string vazia se não parecer um telefone válido.
    """
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if not digits:
        return ""
    # Remove prefixo 0 de operadora/DDD se houver (ex: 015...)
    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]
    if len(digits) in (10, 11) and not digits.startswith("55"):
        digits = "55" + digits
    if len(digits) < 12 or len(digits) > 13:
        return ""
    return digits


def parse_rating(raw_text: str) -> float:
    """Extrai nota numérica (ex: '4,8' -> 4.8)."""
    if not raw_text:
        return 0.0
    match = re.search(r"(\d[.,]\d)", str(raw_text))
    if not match:
        return 0.0
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def unwrap_google_redirect(url: str) -> str:
    """Se o link do Google Maps estiver encapsulado em /url?q=..., extrai a URL real."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if "google." in parsed.netloc and parsed.path.startswith("/url"):
            qs = parse_qs(parsed.query)
            if "q" in qs and qs["q"]:
                return qs["q"][0]
    except Exception:
        pass
    return url


def is_official_website(url: str) -> bool:
    """
    Retorna True se a URL for um site próprio oficial.
    Retorna False se estiver vazia ou se for apenas Instagram, Facebook, Linktree ou WhatsApp.
    """
    if not url:
        return False
    real_url = unwrap_google_redirect(url).lower().strip()
    if not real_url:
        return False
    for domain in ALLOWED_NON_WEBSITE_DOMAINS:
        if domain in real_url:
            return False
    return True


def clean_aria_prefix(text: str, prefixes: tuple[str, ...]) -> str:
    """Remove prefixos como 'Endereço: ', 'Telefone: ' de atributos aria-label."""
    cleaned = str(text or "").strip()
    for p in prefixes:
        if cleaned.lower().startswith(p.lower()):
            cleaned = cleaned[len(p):].strip()
    # Remove caracteres invisíveis comuns do Google Maps ( ícones/marcadores Unicode)
    cleaned = re.sub(r"[\u200e\u200f\u202a-\u202e\ue000-\uf8ff]", "", cleaned).strip()
    return cleaned


def extract_clinic_name(page) -> str:
    """Extrai o título principal da clínica aberta no painel de detalhes."""
    selectors = [
        "h1.DUwDvf",
        "div[role='main'] h1",
        "h1.fontHeadlineLarge",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                txt = (loc.inner_text(timeout=2000) or "").strip()
                if txt and txt.lower() not in ("resultados", "results"):
                    return txt
        except Exception:
            continue
    return ""


def extract_rating(page) -> float:
    """Extrai a nota da clínica no painel lateral."""
    selectors = [
        "div.F7nice span[aria-hidden='true']",
        "span.ceNzKf[role='img']",
        "div[role='main'] span[aria-label*='estrela']",
        "div[role='main'] span[aria-label*='star']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                txt = loc.inner_text(timeout=1500) or loc.get_attribute("aria-label") or ""
                val = parse_rating(txt)
                if val > 0:
                    return val
        except Exception:
            continue
    return 0.0


def extract_website_url(page) -> str:
    """Verifica se existe botão de website na ficha da clínica e retorna o href."""
    selectors = [
        "a[data-item-id='authority']",
        "a[data-tooltip*='website' i]",
        "a[data-tooltip*='site' i]",
        "a[aria-label*='Website:' i]",
        "a[aria-label*='Site:' i]",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                href = loc.get_attribute("href", timeout=1500) or ""
                if href:
                    return unwrap_google_redirect(href)
        except Exception:
            continue
    return ""


def extract_phone(page) -> str:
    """Extrai o telefone da clínica e converte para formato numérico com DDI 55."""
    # 1. Tenta pelo atributo data-item-id="phone:tel:..."
    try:
        phone_btn = page.locator("button[data-item-id^='phone:tel:']").first
        if phone_btn.count() > 0:
            aria = phone_btn.get_attribute("aria-label") or ""
            txt = phone_btn.inner_text(timeout=1500) or ""
            data_id = phone_btn.get_attribute("data-item-id") or ""
            for candidate in (txt, aria, data_id):
                cleaned = clean_phone_to_whatsapp(candidate)
                if cleaned:
                    return cleaned
    except Exception:
        pass

    # 2. Fallback por aria-label de telefone
    for sel in (
        "button[aria-label*='Telefone:' i]",
        "button[aria-label*='Phone:' i]",
        "[data-tooltip*='telefone' i]",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                raw = (loc.get_attribute("aria-label") or "") + " " + (loc.inner_text(timeout=1500) or "")
                cleaned = clean_phone_to_whatsapp(raw)
                if cleaned:
                    return cleaned
        except Exception:
            continue

    return ""


def extract_address(page) -> str:
    """Extrai o endereço completo da clínica."""
    selectors = [
        "button[data-item-id='address']",
        "button[aria-label*='Endereço:' i]",
        "button[aria-label*='Address:' i]",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                aria = loc.get_attribute("aria-label") or ""
                txt = loc.inner_text(timeout=1500) or ""
                raw = aria if len(aria) > len(txt) else txt
                cleaned = clean_aria_prefix(raw, ("Endereço:", "Address:"))
                if cleaned:
                    return cleaned
        except Exception:
            continue
    return "Endereço sob consulta"


def extract_hours(page) -> str:
    """Extrai o horário de funcionamento ou retorna o texto padrão."""
    default_hours = "Consulte horários pelo WhatsApp"
    selectors = [
        "[data-item-id^='oh']",
        "div[aria-label*='Horário' i]",
        "button[aria-label*='Horário' i]",
        "div.t39EBf",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                aria = loc.get_attribute("aria-label") or ""
                txt = loc.inner_text(timeout=1500) or ""
                candidate = clean_aria_prefix(aria or txt, ("Horário de funcionamento:", "Hours:"))
                # Limpa quebras de linha excessivas e textos de "Ocultar horário..."
                candidate = re.sub(r"\s+", " ", candidate).strip()
                candidate = candidate.split("Ocultar")[0].split("Ver mais")[0].strip(" .;,-")
                if candidate and len(candidate) >= 5:
                    # Limita tamanho caso a tabela inteira da semana venha no aria-label
                    if len(candidate) > 110:
                        candidate = candidate[:107].rstrip() + "..."
                    return candidate
        except Exception:
            continue
    return default_hours


def extract_reviews(page) -> list[str]:
    """
    Clica na aba 'Avaliações' e coleta até 3 depoimentos reais com texto.
    Preenche com frases padrão caso a clínica tenha menos de 3 avaliações com texto.
    """
    reviews: list[str] = []
    try:
        tab_selectors = [
            "button[role='tab'][aria-label*='Avaliaç' i]",
            "button[role='tab'][aria-label*='Review' i]",
            "button[role='tab']:has-text('Avaliações')",
            "button[role='tab']:has-text('Reviews')",
        ]
        clicked_tab = False
        for sel in tab_selectors:
            tab = page.locator(sel).first
            if tab.count() > 0:
                tab.click(timeout=3000)
                clicked_tab = True
                break

        if clicked_tab:
            human_delay(1.5, 2.4)

            # Expande botões "Mais" dentro dos comentários se existirem
            try:
                more_buttons = page.locator("button.w8nwRe.kyuRq")
                for i in range(min(more_buttons.count(), 4)):
                    try:
                        more_buttons.nth(i).click(timeout=1000)
                    except Exception:
                        pass
            except Exception:
                pass

            review_spans = page.locator("span.wiI7pd")
            total = review_spans.count()
            for i in range(total):
                if len(reviews) >= 3:
                    break
                try:
                    txt = (review_spans.nth(i).inner_text(timeout=1500) or "").strip()
                    txt = re.sub(r"\s+", " ", txt)
                    if len(txt) >= 15 and txt not in reviews:
                        if len(txt) > 260:
                            txt = txt[:257].rstrip() + "..."
                        reviews.append(txt)
                except Exception:
                    continue
    except Exception:
        pass

    # Garante sempre 3 avaliações preenchidas para não quebrar o layout dos templates
    for idx in range(3):
        if len(reviews) <= idx:
            reviews.append(FALLBACK_REVIEWS[idx])

    return reviews[:3]


def save_leads(leads: list[dict]) -> None:
    """Salva a lista de leads em leads_encontrados.json com encoding UTF-8."""
    OUTPUT_FILE.write_text(
        json.dumps(leads, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    print("=" * 65)
    print(" BUSCADOR DE CLÍNICAS ODONTOLÓGICAS SEM SITE (GOOGLE MAPS)")
    print("=" * 65)

    cidade = input("Digite a Cidade e Estado (ex: Sorocaba SP): ").strip()
    if not cidade:
        cidade = "Sorocaba SP"
        print(f"-> Usando cidade padrão: {cidade}")

    qtd_str = input("Quantidade máxima de clínicas sem site para coletar [Padrão: 10]: ").strip()
    try:
        max_leads = int(qtd_str) if qtd_str else 10
        if max_leads <= 0:
            max_leads = 10
    except ValueError:
        max_leads = 10

    termo_busca = f"clínica odontológica em {cidade}"
    url_busca = f"https://www.google.com/maps/search/{quote_plus(termo_busca)}?hl=pt-BR"

    print(f"\n[*] Iniciando navegador visível (headless=False)...")
    print(f"[*] Pesquisando: '{termo_busca}'")
    print(f"[*] Meta: {max_leads} clínica(s) sem site oficial | Nota > 4.2 | Com telefone\n")

    leads_coletados: list[dict] = []
    nomes_processados: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            locale="pt-BR",
            viewport={"width": 1366, "height": 850},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(url_busca, wait_until="domcontentloaded", timeout=60000)
            human_delay(2.5, 4.0)

            # Caso apareça tela de consentimento de cookies do Google
            try:
                consent_btn = page.locator(
                    "button:has-text('Aceitar tudo'), button:has-text('Accept all')"
                ).first
                if consent_btn.count() > 0:
                    consent_btn.click(timeout=3000)
                    human_delay(1.5, 2.5)
            except Exception:
                pass

            # Aguarda a lista lateral de resultados aparecer
            page.wait_for_selector("div[role='feed'], a.hfpxzc", timeout=30000)

            indice_atual = 0
            tentativas_sem_novos_cards = 0

            while len(leads_coletados) < max_leads:
                cards = page.locator("a.hfpxzc")
                total_cards = cards.count()

                if indice_atual >= total_cards:
                    # Faz scroll no feed lateral para carregar mais clínicas
                    try:
                        feed = page.locator("div[role='feed']").first
                        if feed.count() > 0:
                            feed.evaluate("el => el.scrollBy(0, 900)")
                        else:
                            page.mouse.wheel(0, 900)
                    except Exception:
                        pass

                    human_delay(2.0, 3.0)
                    novo_total = page.locator("a.hfpxzc").count()

                    if novo_total <= total_cards:
                        tentativas_sem_novos_cards += 1
                        # Verifica se chegou ao final da lista do Google Maps
                        fim_lista = page.locator("text='Você chegou ao final da lista.'").count() > 0
                        if fim_lista or tentativas_sem_novos_cards >= 4:
                            print("\n[!] Fim dos resultados disponíveis no Google Maps para esta busca.")
                            break
                    else:
                        tentativas_sem_novos_cards = 0
                    continue

                card = cards.nth(indice_atual)
                indice_atual += 1

                try:
                    nome_card = (card.get_attribute("aria-label") or "").strip()
                    if nome_card and nome_card in nomes_processados:
                        continue

                    card.scroll_into_view_if_needed(timeout=3000)
                    card.click(timeout=5000)
                    human_delay(1.8, 3.0)

                    nome = extract_clinic_name(page) or nome_card
                    if not nome or nome in nomes_processados:
                        continue
                    nomes_processados.add(nome)

                    # 1. Filtro de Nota (> 4.2)
                    nota_num = extract_rating(page)
                    if nota_num > 0 and nota_num <= 4.2:
                        print(f"[-] Ignorada (Nota {nota_num:.1f} <= 4.2): {nome}")
                        continue
                    if nota_num == 0.0:
                        print(f"[-] Ignorada (Sem avaliações/nota): {nome}")
                        continue

                    # 2. Filtro de Website Oficial
                    website_url = extract_website_url(page)
                    if is_official_website(website_url):
                        print(f"[-] Ignorada (Já possui site oficial: {website_url[:40]}...): {nome}")
                        continue

                    # 3. Filtro de Telefone / WhatsApp obrigatório
                    whatsapp = extract_phone(page)
                    if not whatsapp:
                        print(f"[-] Ignorada (Sem número de telefone): {nome}")
                        continue

                    # Extrai os demais dados para a clínica aprovada
                    link_maps = page.url
                    endereco = extract_address(page)
                    horario = extract_hours(page)
                    avaliacoes = extract_reviews(page)

                    lead = {
                        "NOME": nome,
                        "CIDADE": cidade,
                        "WHATSAPP": whatsapp,
                        "ENDERECO": endereco,
                        "LINK_MAPS": link_maps,
                        "HORARIO": horario,
                        "NOTA": f"{nota_num:.1f}",
                        "AVALIACAO_1": avaliacoes[0],
                        "AVALIACAO_2": avaliacoes[1],
                        "AVALIACAO_3": avaliacoes[2],
                        "COR_PRIMARIA": "#0F766E",
                    }

                    leads_coletados.append(lead)
                    # Ordena por maior nota e salva incrementalmente
                    leads_coletados.sort(key=lambda item: float(item.get("NOTA", "0")), reverse=True)
                    save_leads(leads_coletados)

                    rede_info = f" (Link social aceito: {website_url})" if website_url else " (Sem site)"
                    print(
                        f"[+] APROVADA [{len(leads_coletados)}/{max_leads}]: {nome} | "
                        f"Nota: {nota_num:.1f} | Tel: {whatsapp}{rede_info}"
                    )

                except PlaywrightTimeoutError:
                    print("    [!] Tempo esgotado ao carregar ficha da clínica, pulando para a próxima...")
                    continue
                except Exception as exc:
                    print(f"    [!] Erro ao processar item ({exc}), continuando...")
                    continue

        except KeyboardInterrupt:
            print("\n[!] Busca interrompida manualmente pelo usuário.")
        except Exception as e:
            print(f"\n[!] Erro durante a navegação: {e}")
        finally:
            browser.close()

    # Salva resultado final ordenado por nota decrescente
    leads_coletados.sort(key=lambda item: float(item.get("NOTA", "0")), reverse=True)
    save_leads(leads_coletados)

    print("\n" + "=" * 65)
    print(f"[OK] Busca concluída! {len(leads_coletados)} clínica(s) salva(s) em:")
    print(f"     {OUTPUT_FILE}")
    print("\nPara gerar os sites em lote a partir dos leads coletados, execute:")
    print("     python gerador.py --json leads_encontrados.json --template 4")
    print("=" * 65)


if __name__ == "__main__":
    main()
