# 📄 Academic to PDF

Converte páginas de plataformas de ensino (Blackboard, Moodle, etc.) em PDFs limpos, sem CSS, menus ou elementos desnecessários — direto pelo navegador, com login manual.

---

## Como funciona

1. O script abre um navegador **Chromium visível**
2. Você **faz o login** normalmente na plataforma
3. Entra em **modo de captura**: navegue até qualquer página e pressione `ENTER` no terminal para salvar como PDF
4. Repita para quantas páginas quiser
5. Digite `sair` para encerrar — todos os PDFs ficam numa pasta organizada e numerada

---

## Instalação

**Requisitos:** Python 3.10+

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/academic-to-pdf.git
cd academic-to-pdf

# 2. Instale as dependências
pip install playwright beautifulsoup4 reportlab lxml

# 3. Instale o navegador Chromium
python -m playwright install chromium
```

---

## Uso

```bash
python academic_to_pdf_playwright.py <URL> [--pasta PASTA]
```

| Argumento | Descrição | Padrão |
|-----------|-----------|--------|
| `url` | URL inicial (página de login ou home da plataforma) | obrigatório |
| `--pasta` / `-p` | Pasta onde os PDFs serão salvos | `./pdfs` |

### Exemplos

```bash
# Salva na pasta padrão ./pdfs
python academic_to_pdf_playwright.py https://blackboard.minhafaculdade.com

# Salva em pasta personalizada
python academic_to_pdf_playwright.py https://blackboard.minhafaculdade.com --pasta "D:/Faculdade/Aulas"
```

---

## Fluxo no terminal

```
Abrindo: https://blackboard.minhafaculdade.com

  Faça o login na janela do navegador.
  Quando estiver logado, volte aqui e pressione ENTER.

  Pronto para começar? Pressione ENTER...

══════════════════════════════════════════════════════════════
  MODO CAPTURA ATIVO
  > Navegue até a página desejada no navegador
  > Pressione ENTER aqui para salvar como PDF
  > Digite  sair  e ENTER para encerrar
══════════════════════════════════════════════════════════════

  [01] ENTER = salvar | sair = encerrar:
  Capturando: Fundamentos da Programação - Aula 1
  OK  Salvo: D:/Faculdade/Aulas/01 - Fundamentos da Programação - Aula 1.pdf

  [02] ENTER = salvar | sair = encerrar:
  Capturando: Estruturas de Dados - Aula 2
  OK  Salvo: D:/Faculdade/Aulas/02 - Estruturas de Dados - Aula 2.pdf

  [03] ENTER = salvar | sair = encerrar: sair

  Sessão encerrada. 2 PDF(s) salvos em: D:/Faculdade/Aulas
    - 01 - Fundamentos da Programação - Aula 1.pdf
    - 02 - Estruturas de Dados - Aula 2.pdf
```

---

## O que é removido do PDF

O script descarta automaticamente:

- Todo CSS e estilos inline
- Menus de navegação (`<nav>`, `<header>`)
- Rodapés (`<footer>`)
- Sidebars, banners e anúncios
- Scripts e iframes
- Popups e modais

O que sobra é só o **conteúdo textual** da página: títulos, parágrafos, listas, blocos de código e citações — formatados de forma limpa e legível.

---

## Estrutura do projeto

```
academic-to-pdf/
├── academic_to_pdf_playwright.py   # Script principal
├── .gitignore
└── README.md
```

---

## Dependências

| Pacote | Função |
|--------|--------|
| `playwright` | Controla o navegador e captura o HTML renderizado |
| `beautifulsoup4` | Faz o parse e limpeza do HTML |
| `lxml` | Parser de HTML de alta performance |
| `reportlab` | Gera os arquivos PDF |

---

## Limitações conhecidas

- Páginas que carregam conteúdo via vídeo ou canvas (ex: slides interativos) não são capturadas — apenas o texto é extraído
- Imagens e equações matemáticas são ignoradas na versão atual
- Tabelas complexas são convertidas para texto linear

---

## Licença

MIT
