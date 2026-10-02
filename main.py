"""
main.py
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
    python main.py <URL_de_login> [--pasta pdfs]

Exemplos:
    python main.py https://blackboard.com
    python main.py https://blackboard.com --pasta "D:/Aulas"

Dependências:
    pip install playwright beautifulsoup4 reportlab lxml
    python -m playwright install chromium
"""

import argparse
import os
import re
import sys
from urllib.parse import urldefrag, urlparse

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

EXTENSOES_IGNORAR = (
    ".pdf", ".zip", ".rar", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".mp4", ".mp3", ".docx", ".xlsx", ".pptx",
)

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
    tag_id = (attrs.get("id") or "").lower()
    tokens_id = set(re.split(r"[-_\s]+", tag_id))
    return bool(classes & CLASSES_IGNORAR) or bool(tokens_id & CLASSES_IGNORAR)


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
        if tag.name == "pre":
            texto = tag.get_text().strip("\n")
        else:
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


def formatar_codigo(texto_escapado: str) -> str:
    """Mantem quebras de linha e indentacao de blocos de codigo."""
    linhas = []
    for linha in texto_escapado.split("\n"):
        recuo = len(linha) - len(linha.lstrip(" "))
        linhas.append("&nbsp;" * recuo + linha.lstrip(" "))
    return "<br/>".join(linhas)


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
        if bloco["tipo"] == "pre":
            texto = formatar_codigo(texto)
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


# ── Modo automatico: segue todos os links de uma pagina ───────────────────────

def coletar_links(page, seletor: str, filtro: str) -> list:
    """Le os links da pagina atual (antes da limpeza) e devolve URLs unicas, em ordem."""
    alvo = f"{seletor} a[href]" if seletor else "a[href]"
    hrefs = page.eval_on_selector_all(alvo, "els => els.map(e => e.href)")

    origem = urlparse(page.url).netloc
    padrao = re.compile(filtro) if filtro else None

    vistos, links = set(), []
    for href in hrefs:
        href, _ = urldefrag(href)          # remove #ancora
        if not href.startswith(("http://", "https://")):
            continue
        if urlparse(href).netloc != origem:  # so o mesmo site
            continue
        if href.lower().endswith(EXTENSOES_IGNORAR):
            continue
        if padrao and not padrao.search(href):
            continue
        if href in vistos:
            continue
        vistos.add(href)
        links.append(href)
    return links


def modo_auto(page, pasta: str, contador: int, salvos: list) -> int:
    print("\n" + "=" * 60)
    print("  MODO AUTOMATICO")
    print("  Abra a pagina que tem a lista de links (indice/sumario)")
    print("  e responda as perguntas abaixo.")
    print("=" * 60)

    seletor = input("\n  Seletor CSS da area dos links (ex: #sidebar) [ENTER = pagina toda]: ").strip()
    filtro  = input("  Filtro regex na URL (ex: /book/.*\\.html$)  [ENTER = sem filtro]: ").strip()

    try:
        links = coletar_links(page, seletor, filtro)
    except Exception as e:
        print(f"  [!] Nao consegui coletar os links: {e}")
        return contador

    if not links:
        print("  [!] Nenhum link encontrado com esses criterios.")
        return contador

    print(f"\n  {len(links)} link(s) encontrado(s):")
    for url in links[:10]:
        print(f"    {url}")
    if len(links) > 10:
        print(f"    ... e mais {len(links) - 10}")

    if input("\n  Salvar todos como PDF? (s/n): ").strip().lower() != "s":
        return contador

    falhas = []
    try:
        for i, url in enumerate(links, 1):
            print(f"\n  [{i}/{len(links)}] {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                resultado = salvar_pagina(page, pasta, contador)
            except Exception as e:
                print(f"  [!] Falhou: {e}")
                falhas.append(url)
                continue

            if resultado:
                salvos.append(resultado)
                contador += 1
            page.wait_for_timeout(800)   # pausa curta para nao sobrecarregar o site
    except KeyboardInterrupt:
        print("\n  Interrompido (Ctrl+C). O que ja foi salvo continua na pasta.")

    if falhas:
        print(f"\n  {len(falhas)} pagina(s) falharam:")
        for url in falhas:
            print(f"    - {url}")
    return contador


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
        print("  > Digite  auto  e ENTER para salvar todos os links de uma pagina")
        print("  > Digite  sair  e ENTER para encerrar")
        print("=" * 60)

        while True:
            cmd = input(f"\n  [{contador:02d}] ENTER = salvar | sair = encerrar: ").strip().lower()

            if cmd == "sair":
                break

            if cmd == "auto":
                contador = modo_auto(page, pasta, contador, salvos)
                continue

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