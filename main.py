"""
academic_to_pdf_playwright.py
Converte páginas de ambiente de estudos (com login) em PDFs limpos.

Fluxo:
  1. Abre o navegador visível
  2. Você faz o login manualmente
  3. Loop infinito:
       - Navegue até a página desejada
       - Pressione ENTER → PDF salvo automaticamente
       - Vá para a próxima página, repita
       - Digite 'sair' para encerrar

Uso:
    python academic_to_pdf_playwright.py <URL_de_login> [--pasta pdfs]

Exemplos:
    python academic_to_pdf_playwright.py https://blackboard.com
    python academic_to_pdf_playwright.py https://blackboard.com --pasta "D:/Aulas"

Dependências:
    pip install playwright beautifulsoup4 reportlab lxml
    python -m playwright install chromium
"""

import argparse
import os
import re
import sys

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate


# ── Configurações ─────────────────────────────────────────────────────────────

MARGEM = 2 * cm

TAGS_CONTEUDO = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "li", "blockquote", "pre", "figcaption",
    "caption", "td", "th", "dt", "dd",
]

TAGS_IGNORAR = {
    "nav", "footer", "header", "aside", "script",
    "style", "noscript", "iframe", "form", "button",
    "input", "select", "textarea",
}

CLASSES_IGNORAR = {
    "nav", "navbar", "menu", "sidebar", "footer",
    "header", "banner", "ad", "advertisement", "cookie",
    "popup", "modal", "breadcrumb", "social", "share",
    "related", "comments", "comment", "widget",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def nome_arquivo_seguro(titulo: str, contador: int) -> str:
    """Gera um nome de arquivo seguro a partir do título da página."""
    limpo = re.sub(r'[\\/*?:"<>|]', "", titulo)
    limpo = re.sub(r'\s+', " ", limpo).strip()
    limpo = limpo[:80]
    return f"{contador:02d} - {limpo}.pdf"


# ── Limpeza do HTML ───────────────────────────────────────────────────────────

def deve_ignorar(tag) -> bool:
    if tag.name in TAGS_IGNORAR:
        return True
    attrs = tag.attrs or {}
    classes = set(attrs.get("class", []))
    tag_id = attrs.get("id", "").lower()
    return bool(classes & CLASSES_IGNORAR) or any(
        c in tag_id for c in CLASSES_IGNORAR
    )


def limpar_html(soup: BeautifulSoup) -> BeautifulSoup:
    for tag in soup.find_all(True):
        if deve_ignorar(tag):
            tag.decompose()
    for tag in soup.find_all(True):
        if tag.attrs is not None:
            tag.attrs = {}
    return soup


def extrair_blocos(soup: BeautifulSoup) -> list:
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(id="main-content")
        or soup.find(class_="content")
        or soup.body
    )
    if not main:
        return []

    blocos, vistos = [], set()
    for tag in main.find_all(TAGS_CONTEUDO):
        texto = tag.get_text(separator=" ", strip=True)
        if not texto or len(texto) < 3 or texto in vistos:
            continue
        vistos.add(texto)
        blocos.append({"tipo": tag.name, "texto": texto})
    return blocos


# ── Estilos ReportLab ─────────────────────────────────────────────────────────

def criar_estilos() -> dict:
    base = getSampleStyleSheet()
    return {
        "titulo_doc": ParagraphStyle("titulo_doc", parent=base["Title"],   fontSize=20, leading=26, spaceAfter=14),
        "url":        ParagraphStyle("url",        parent=base["Normal"],  fontSize=8,  textColor="#888888", spaceAfter=20),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=16, leading=20, spaceBefore=14, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=14, leading=18, spaceBefore=12, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=12, leading=16, spaceBefore=10, spaceAfter=3),
        "h4": ParagraphStyle("h4", parent=base["Heading4"], fontSize=11, leading=15, spaceBefore=8,  spaceAfter=2),
        "h5": ParagraphStyle("h5", parent=base["Heading5"], fontSize=10, leading=14, spaceBefore=6,  spaceAfter=2),
        "h6": ParagraphStyle("h6", parent=base["Heading6"], fontSize=10, leading=14, spaceBefore=6,  spaceAfter=2),
        "normal": ParagraphStyle("normal", parent=base["Normal"], fontSize=10, leading=14, spaceAfter=6),
        "item":   ParagraphStyle("item",   parent=base["Normal"], fontSize=10, leading=14, spaceAfter=4, leftIndent=20, bulletIndent=10),
        "pre":    ParagraphStyle("pre",    parent=base["Code"],   fontSize=8,  leading=12, leftIndent=20, backColor="#F4F4F4", spaceAfter=8),
        "quote":  ParagraphStyle("quote",  parent=base["Normal"], fontSize=10, leading=14, leftIndent=30, rightIndent=10, textColor="#444444", spaceAfter=8),
    }

ESTILOS = criar_estilos()


def escapar(texto: str) -> str:
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def blocos_para_flowables(blocos: list) -> list:
    mapa = {
        "h1": ESTILOS["h1"], "h2": ESTILOS["h2"], "h3": ESTILOS["h3"],
        "h4": ESTILOS["h4"], "h5": ESTILOS["h5"], "h6": ESTILOS["h6"],
        "p":  ESTILOS["normal"], "li": ESTILOS["item"],
        "blockquote": ESTILOS["quote"], "pre": ESTILOS["pre"],
        "figcaption": ESTILOS["normal"], "caption": ESTILOS["normal"],
        "td": ESTILOS["normal"], "th": ESTILOS["normal"],
        "dt": ESTILOS["normal"], "dd": ESTILOS["normal"],
    }
    flowables = []
    for bloco in blocos:
        texto  = escapar(bloco["texto"])
        estilo = mapa.get(bloco["tipo"], ESTILOS["normal"])
        prefixo = "bullet  " if bloco["tipo"] == "li" else ""
        try:
            flowables.append(Paragraph(prefixo + texto, estilo))
        except Exception:
            pass
    return flowables


# ── Salvar uma página como PDF ────────────────────────────────────────────────

def salvar_pagina(page, pasta: str, contador: int):
    titulo    = page.title() or f"pagina_{contador}"
    url_atual = page.url

    print(f"\n  Capturando: {titulo}")

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1200)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)

    html   = page.content()
    soup   = BeautifulSoup(html, "lxml")
    soup   = limpar_html(soup)
    blocos = extrair_blocos(soup)

    if not blocos:
        print("  [!] Nenhum conteudo encontrado nessa pagina - pulando.")
        return None

    nome    = nome_arquivo_seguro(titulo, contador)
    caminho = os.path.join(pasta, nome)

    doc = SimpleDocTemplate(
        caminho, pagesize=A4,
        leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=MARGEM,  bottomMargin=MARGEM,
        title=titulo,
    )
    doc.build([
        Paragraph(escapar(titulo), ESTILOS["titulo_doc"]),
        Paragraph(f"Fonte: {url_atual}", ESTILOS["url"]),
        HRFlowable(width="100%", thickness=1, color="#CCCCCC", spaceAfter=14),
        *blocos_para_flowables(blocos),
    ])

    print(f"  OK  Salvo: {caminho}")
    return caminho


# ── Loop principal ────────────────────────────────────────────────────────────

def iniciar_loop(url_inicial: str, pasta: str) -> None:
    os.makedirs(pasta, exist_ok=True)
    contador = 1
    salvos   = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page    = context.new_page()

        print(f"\nAbrindo: {url_inicial}")
        page.goto(url_inicial, wait_until="domcontentloaded", timeout=60_000)

        print("\n" + "=" * 60)
        print("  Faca o login na janela do navegador.")
        print("  Quando estiver logado, volte aqui e pressione ENTER.")
        print("=" * 60)
        input("\n  Pronto para comecar? Pressione ENTER... ")

        print("\n" + "=" * 60)
        print("  MODO CAPTURA ATIVO")
        print("  > Navegue ate a pagina desejada no navegador")
        print("  > Pressione ENTER aqui para salvar como PDF")
        print("  > Digite  sair  e ENTER para encerrar")
        print("=" * 60)

        while True:
            cmd = input(f"\n  [{contador:02d}] ENTER = salvar | sair = encerrar: ").strip().lower()

            if cmd == "sair":
                break

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

            resultado = salvar_pagina(page, pasta, contador)
            if resultado:
                salvos.append(resultado)
                contador += 1

        browser.close()

    print("\n" + "=" * 60)
    print(f"  Sessao encerrada. {len(salvos)} PDF(s) salvos em: {pasta}")
    for arq in salvos:
        print(f"    - {os.path.basename(arq)}")
    print("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Captura multiplas paginas de plataforma de estudos em PDFs (modo loop)."
    )
    parser.add_argument("url", help="URL inicial (pagina de login ou home)")
    parser.add_argument(
        "--pasta", "-p",
        default="pdfs",
        help="Pasta onde os PDFs serao salvos (padrao: ./pdfs)",
    )
    args = parser.parse_args()
    iniciar_loop(args.url, args.pasta)


if __name__ == "__main__":
    main()