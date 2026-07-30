#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Notícias por Área Governativa — extração para Excel
Secretaria-Geral do Governo · Suporte à Decisão · Unidade de Pesquisa e Estatísticas

Lê os feeds das 16 áreas governativas e grava um ficheiro Excel com uma linha por
notícia: área, agrupamento, data de publicação, fonte, título, resumo e ligação.

Utilização:
    python extrair_noticias.py                      janela predefinida (7 dias)
    python extrair_noticias.py --periodo 24h        últimas 24 horas
    python extrair_noticias.py --periodo 30d --saida noticias_julho.xlsx
    python extrair_noticias.py --area saude         apenas uma área

Requisitos: Python 3.9 ou superior e a biblioteca openpyxl (pip install openpyxl).
"""

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.entities import name2codepoint
from base64 import urlsafe_b64decode
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO — manter alinhada com o painel HTML
# ---------------------------------------------------------------------------
EDICAO = {"hl": "pt-PT", "gl": "PT", "ceid": "PT:pt-150"}
EXCLUSOES_DOMINIO = ["site:.br", "site:globo.com", "site:r7.com",
                     "site:metropoles.com", "site:abril.com"]

GRUPOS = {
    "soberania": "Estado e soberania",
    "economia": "Economia, finanças e território",
    "social": "Sociedade e bem-estar",
    "ambiente": "Ambiente, energia e recursos naturais",
}

AREAS = [
    ("presidencia", "Presidência", "soberania",
     ["Conselho de Ministros", "Presidência do Conselho de Ministros", "comunicação do Governo",
      "transparência administrativa", "dados abertos", "modernização administrativa"], []),
    ("parlamentares", "Assuntos Parlamentares", "soberania",
     ["Assembleia da República", "debate parlamentar", "interpelação ao Governo",
      "comissão parlamentar de inquérito", "regulação da comunicação social",
      "Entidade Reguladora para a Comunicação Social"], []),
    ("reforma", "Reforma do Estado", "soberania",
     ["reforma do Estado", "Administração Pública", "desburocratização",
      "simplificação administrativa", "inteligência artificial na Administração Pública",
      "SIADAP"], []),
    ("estrangeiros", "Negócios Estrangeiros", "soberania",
     ["política externa portuguesa", "Conselho Europeu", "CPLP", "Nações Unidas",
      "diáspora portuguesa", "cooperação para o desenvolvimento", "consulado de Portugal"], []),
    ("defesa", "Defesa Nacional", "soberania",
     ["Forças Armadas", "NATO", "investimento em defesa", "indústria de defesa",
      "missões militares internacionais", "cibersegurança"], []),
    ("interna", "Administração Interna", "soberania",
     ["imigração", "pedidos de asilo", "controlo de fronteiras", "AIMA", "proteção civil",
      "segurança interna", "GNR", "PSP", "sinistralidade rodoviária"], []),
    ("justica", "Justiça", "soberania",
     ["tribunais", "Ministério Público", "pendências processuais", "registos e notariado",
      "sistema prisional", "reforma da justiça"], []),
    ("financas", "Finanças", "economia",
     ["Orçamento do Estado", "défice orçamental", "dívida pública", "impostos", "IRS",
      "tributação das empresas", "execução orçamental", "despesa pública"], []),
    ("economia", "Economia e Coesão Territorial", "economia",
     ["crescimento económico", "exportações portuguesas", "investimento empresarial", "turismo",
      "comércio externo", "fundos europeus", "coesão territorial", "interioridade"], []),
    ("infraestruturas", "Infraestruturas e Habitação", "economia",
     ["habitação", "arrendamento", "obras públicas", "ferrovia", "novo aeroporto",
      "transportes públicos", "licenciamento urbanístico"], []),
    ("educacao", "Educação, Ciência e Inovação", "social",
     ["escolas", "professores", "exames nacionais", "ensino superior", "bolsas de investigação",
      "investigação científica", "abandono escolar"], []),
    ("saude", "Saúde", "social",
     ["Serviço Nacional de Saúde", "urgências hospitalares", "médicos de família",
      "listas de espera", "cuidados continuados", "medicamentos", "saúde mental"], []),
    ("trabalho", "Trabalho, Solidariedade e Segurança Social", "social",
     ["emprego", "desemprego", "salário mínimo", "pensões", "segurança social",
      "negociação coletiva", "apoios sociais", "pobreza"], []),
    ("cultura", "Cultura, Juventude e Desporto", "social",
     ["património cultural", "museus", "criação artística", "políticas de juventude", "desporto",
      "alta competição", "língua portuguesa"], []),
    ("ambiente", "Ambiente e Energia", "ambiente",
     ["preço da energia", "mercado da eletricidade", "energias renováveis",
      "alterações climáticas", "descarbonização", "gestão de resíduos", "situação de seca",
      "incêndios florestais"],
     ["clima de negócios", "clima organizacional", "clima de confiança"]),
    ("agricultura", "Agricultura e Mar", "ambiente",
     ["agricultura", "política agrícola comum", "pescas", "economia azul", "floresta",
      "regadio", "segurança alimentar"], []),
]

AZUL, CINZA = "2B5683", "F2F5F8"


# ---------------------------------------------------------------------------
# Construção das consultas
# ---------------------------------------------------------------------------
def consulta(palavras, excluir, periodo, so_nacionais=True):
    termos = "(" + " OR ".join(f'"{p}"' for p in palavras) + ")"
    termos += "".join(f' -"{t}"' for t in excluir)
    if so_nacionais:
        termos += " " + " ".join(f"-{d}" for d in EXCLUSOES_DOMINIO)
    if periodo:
        termos += f" when:{periodo}"
    return termos


def url_feed(q):
    p = f"hl={EDICAO['hl']}&gl={EDICAO['gl']}&ceid={EDICAO['ceid']}"
    return f"https://news.google.com/rss/search?q={quote(q, safe='')}&{p}"


# ---------------------------------------------------------------------------
# Leitura e tratamento
# ---------------------------------------------------------------------------
def limpar(texto):
    """Remove marcação HTML e normaliza espaços."""
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def endereco_do_artigo(ligacao, tempo_limite=12):
    """Converte o reencaminhamento do Google no endereço do jornal.

    Primeiro tenta descodificar o identificador, onde as versões mais antigas
    trazem o endereço em claro. Não resultando, segue o reencaminhamento na rede
    e devolve o endereço final. Falhando ambos, devolve a ligação original, que
    abre o artigo à mesma.
    """
    if not ligacao or "news.google.com" not in ligacao:
        return ligacao

    identificador = ligacao.split("/articles/")[-1].split("?")[0]
    try:
        bruto = urlsafe_b64decode(identificador + "=" * (-len(identificador) % 4))
        achado = re.search(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{12,}", bruto)
        if achado:
            return achado.group(0).decode("utf-8", "replace").rstrip("\x00 ")
    except Exception:                                          # noqa: BLE001
        pass

    try:
        pedido = Request(ligacao, headers={"User-Agent": "Mozilla/5.0 SGGov-UPE-Radar/1.0"})
        with urlopen(pedido, timeout=tempo_limite) as resposta:
            final = resposta.geturl()
            if final and "news.google.com" not in final:
                return final
            corpo = resposta.read(20000).decode("utf-8", "replace")
        for padrao in (r'data-n-au="([^"]+)"', r'<meta[^>]+url=([^">]+)', r'href="(https?://(?!\w*\.?google\.)[^"]+)"'):
            achado = re.search(padrao, corpo)
            if achado:
                return html.unescape(achado.group(1))
    except Exception:                                          # noqa: BLE001
        pass

    return ligacao


def resolver_ligacoes(linhas, trabalhadores=8):
    """Resolve em paralelo os reencaminhamentos de todas as notícias."""
    enderecos = [l[6] for l in linhas]
    unicos = list(dict.fromkeys(enderecos))
    print(f"A resolver {len(unicos)} ligações…", end=" ", flush=True)
    with ThreadPoolExecutor(max_workers=trabalhadores) as piscina:
        resolvidos = dict(zip(unicos, piscina.map(endereco_do_artigo, unicos)))
    convertidas = 0
    for l in linhas:
        novo = resolvidos.get(l[6], l[6])
        if novo != l[6]:
            convertidas += 1
            l[6] = novo
    print(f"{convertidas} convertidas em endereço do jornal")
    return linhas


def ler_feed(url, tempo_limite=30):
    pedido = Request(url, headers={"User-Agent": "SGGov-UPE-Radar/1.0"})
    with urlopen(pedido, timeout=tempo_limite) as resposta:
        return resposta.read()


def preparar_xml(bruto):
    """Converte entidades HTML que o XML não reconhece (&nbsp;, &eacute;, ...).

    Os feeds noticiosos incluem com frequência entidades definidas em HTML mas não
    em XML, que fariam falhar a leitura de todo o feed.
    """
    texto = bruto.decode("utf-8", errors="replace") if isinstance(bruto, bytes) else bruto
    reservadas = {"amp", "lt", "gt", "quot", "apos"}

    def trocar(m):
        nome = m.group(1)
        if nome in reservadas:
            return m.group(0)
        ponto = name2codepoint.get(nome)
        return chr(ponto) if ponto else " "

    return re.sub(r"&([a-zA-Z][a-zA-Z0-9]{1,31});", trocar, texto)


def extrair_itens(xml_bruto):
    """Devolve a lista de notícias de um feed RSS."""
    raiz = ElementTree.fromstring(preparar_xml(xml_bruto))
    itens = []
    for item in raiz.iter("item"):
        titulo = limpar(item.findtext("title"))
        ligacao = (item.findtext("link") or "").strip()

        fonte_no = item.find("source")
        fonte = limpar(fonte_no.text) if fonte_no is not None else ""
        dominio = ""
        if fonte_no is not None and fonte_no.get("url"):
            dominio = urlparse(fonte_no.get("url")).netloc

        # O Google acrescenta " - Fonte" ao fim do título; retira-se para não duplicar.
        if " - " in titulo:
            cabeca, cauda = titulo.rsplit(" - ", 1)
            if not fonte:
                titulo, fonte = cabeca, cauda
            elif cauda.strip().lower() == fonte.lower():
                titulo = cabeca

        data = None
        bruta = item.findtext("pubDate")
        if bruta:
            try:
                data = parsedate_to_datetime(bruta).replace(tzinfo=None)
            except (TypeError, ValueError):
                data = None

        resumo = limpar(item.findtext("description"))
        # O Google devolve, na descrição, uma repetição do título seguida do nome da
        # publicação, ou uma lista de artigos relacionados. Nesses casos não há resumo.
        simplificar = lambda t: re.sub(r"[^a-z0-9áàâãéêíóôõúç ]", "", t.lower()).strip()  # noqa: E731
        if not resumo or simplificar(resumo).startswith(simplificar(titulo)[:45]):
            resumo = ""

        itens.append({"data": data, "fonte": fonte, "dominio": dominio,
                      "titulo": titulo, "resumo": resumo, "ligacao": ligacao})
    return itens


def recolher(periodo, apenas=None, so_nacionais=True, pausa=1.5):
    linhas, falhas = [], []
    vistos = set()
    alvo = [a for a in AREAS if apenas is None or a[0] == apenas]

    for i, (ident, nome, grupo, palavras, excluir) in enumerate(alvo, 1):
        q = consulta(palavras, excluir, periodo, so_nacionais)
        print(f"[{i}/{len(alvo)}] {nome}…", end=" ", flush=True)
        try:
            itens = extrair_itens(ler_feed(url_feed(q)))
        except Exception as erro:                              # noqa: BLE001
            print(f"falhou ({erro})")
            falhas.append((nome, str(erro)))
            continue

        novos = 0
        for it in itens:
            chave = (ident, it["ligacao"])
            if chave in vistos:
                continue
            vistos.add(chave)
            linhas.append([nome, GRUPOS[grupo], it["data"], it["fonte"], it["dominio"],
                           it["titulo"], it["ligacao"]])
            novos += 1
        print(f"{novos} notícias")
        if i < len(alvo):
            time.sleep(pausa)

    # Mais recentes primeiro; as notícias sem data reconhecível ficam no fim.
    com_data = [l for l in linhas if l[2] is not None]
    sem_data = [l for l in linhas if l[2] is None]
    com_data.sort(key=lambda l: l[2], reverse=True)
    return com_data + sem_data, falhas


# ---------------------------------------------------------------------------
# Escrita do Excel
# ---------------------------------------------------------------------------
def gravar(linhas, falhas, caminho, periodo, so_nacionais):
    fonte = lambda **k: Font(name="Arial", **k)                # noqa: E731
    cab = PatternFill("solid", fgColor=AZUL)
    alt = PatternFill("solid", fgColor=CINZA)
    borda = Border(bottom=Side(style="thin", color="D5DCE4"))

    wb = Workbook()
    ws = wb.active
    ws.title = "Notícias"
    cabecalhos = ["Área governativa", "Agrupamento temático", "Data de publicação", "Fonte",
                  "Domínio", "Título", "Ligação"]
    for j, h in enumerate(cabecalhos, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = fonte(bold=True, color="FFFFFF", size=10)
        c.fill = cab
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 28

    for i, l in enumerate(linhas, 2):
        for j, v in enumerate(l, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = fonte(size=10)
            c.border = borda
            c.alignment = Alignment(vertical="top", wrap_text=(j == 6))
            if i % 2 == 0:
                c.fill = alt
            if j == 3 and v is not None:
                c.number_format = "yyyy-mm-dd hh:mm"
            if j == 7 and v:
                c.hyperlink = v
                c.font = fonte(size=10, color="2B5683", underline="single")

    for j, w in enumerate([30, 28, 19, 24, 22, 62, 52], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{max(2, len(linhas) + 1)}"

    # --- Folha de síntese ---
    wr = wb.create_sheet("Síntese")
    wr.column_dimensions["A"].width = 44
    wr.column_dimensions["B"].width = 16
    wr["A1"] = "Síntese da recolha"
    wr["A1"].font = fonte(size=13, bold=True, color=AZUL)

    contexto = [
        ("Data da recolha", datetime.now().strftime("%d de %B de %Y, %Hh%M")),
        ("Janela temporal", periodo or "sem limite"),
        ("Restrição a fontes nacionais", "sim" if so_nacionais else "não"),
        ("Notícias recolhidas", len(linhas)),
        ("Áreas com falha na recolha", len(falhas)),
    ]
    for i, (t, v) in enumerate(contexto, start=3):
        wr.cell(row=i, column=1, value=t).font = fonte(size=10)
        wr.cell(row=i, column=2, value=v).font = fonte(size=10, bold=True)

    wr.cell(row=9, column=1, value="Notícias por área governativa").font = fonte(size=11, bold=True, color=AZUL)
    ultima = max(2, len(linhas) + 1)
    for i, (_, nome, _, _, _) in enumerate(AREAS, start=10):
        wr.cell(row=i, column=1, value=nome).font = fonte(size=10)
        c = wr.cell(row=i, column=2, value=f'=COUNTIF(Notícias!$A$2:$A${ultima},A{i})')
        c.font = fonte(size=10, bold=True)
        c.alignment = Alignment(horizontal="center")

    aviso = wr.cell(row=10 + len(AREAS) + 1, column=1,
                    value=("Nota: o serviço devolve no máximo cerca de 100 artigos por consulta. "
                           "As contagens medem exposição mediática indexada e não são comparáveis "
                           "entre áreas. A coluna Resumo fica vazia quando o feed não fornece texto "
                           "próprio, o que sucede na maioria dos casos."))
    aviso.font = fonte(size=9, italic=True, color="5B6068")
    aviso.alignment = Alignment(wrap_text=True, vertical="top")
    wr.merge_cells(start_row=aviso.row, start_column=1, end_row=aviso.row, end_column=2)
    wr.row_dimensions[aviso.row].height = 60

    if falhas:
        wf = wb.create_sheet("Falhas")
        wf.column_dimensions["A"].width = 34
        wf.column_dimensions["B"].width = 80
        wf["A1"], wf["B1"] = "Área", "Erro"
        for c in ("A1", "B1"):
            wf[c].font = fonte(bold=True, color="FFFFFF", size=10)
            wf[c].fill = cab
        for i, (nome, erro) in enumerate(falhas, 2):
            wf.cell(row=i, column=1, value=nome).font = fonte(size=10)
            wf.cell(row=i, column=2, value=erro).font = fonte(size=10)

    wb.save(caminho)


# ---------------------------------------------------------------------------
def principal():
    ap = argparse.ArgumentParser(description="Extrai as notícias do radar para Excel.")
    ap.add_argument("--periodo", default="7d",
                    help="janela temporal: 24h, 48h, 72h, 7d, 30d, 365d ou vazio")
    ap.add_argument("--area", default=None, help="identificador de uma única área (ex.: saude)")
    ap.add_argument("--todas-as-fontes", action="store_true",
                    help="não excluir os domínios estrangeiros")
    ap.add_argument("--saida", default=None, help="nome do ficheiro Excel a criar")
    ap.add_argument("--json", default=None,
                    help="grava também um ficheiro JSON com as notícias (para publicar junto ao painel)")
    ap.add_argument("--sem-resolver-ligacoes", action="store_true",
                    help="não converter os reencaminhamentos do Google no endereço do jornal")
    ap.add_argument("--historico", default=None,
                    help="ficheiro JSON de série diária, atualizado a cada recolha")
    args = ap.parse_args()

    if args.area and args.area not in {a[0] for a in AREAS}:
        sys.exit(f"Área desconhecida: {args.area}")

    saida = args.saida or f"radar_noticias_{datetime.now():%Y%m%d_%H%M}.xlsx"
    so_nacionais = not args.todas_as_fontes

    linhas, falhas = recolher(args.periodo, args.area, so_nacionais)
    if not args.sem_resolver_ligacoes and linhas:
        linhas = resolver_ligacoes(linhas)
    gravar(linhas, falhas, saida, args.periodo, so_nacionais)
    print(f"\n{len(linhas)} notícias gravadas em {saida}")

    if args.json:
        campos = ["area", "grupo", "data", "fonte", "dominio", "titulo", "ligacao"]
        noticias = []
        for l in linhas:
            registo = dict(zip(campos, l))
            registo["data"] = registo["data"].strftime("%Y-%m-%d %H:%M") if registo["data"] else ""
            noticias.append(registo)
        pacote = {
            "gerado": datetime.now().strftime("%d de %B de %Y, %Hh%M"),
            "periodo": args.periodo or "sem limite",
            "so_nacionais": so_nacionais,
            "noticias": noticias,
        }
        with open(args.json, "w", encoding="utf-8") as destino:
            json.dump(pacote, destino, ensure_ascii=False, indent=1)
        print(f"{len(noticias)} notícias gravadas em {args.json}")

    if args.historico:
        atualizar_historico(args.historico, linhas, args.periodo)
    if falhas:
        print(f"{len(falhas)} áreas falharam — ver a folha Falhas.")


def atualizar_historico(caminho, linhas, periodo):
    """Acrescenta à série diária o retrato de hoje, por área governativa.

    Guarda apenas agregados — número de notícias e de publicações distintas por
    área e por dia. É deliberadamente pequeno: cresce cerca de 2 KB por dia e
    pode ser lido de uma vez pelo painel.
    """
    hoje = datetime.now().strftime("%Y-%m-%d")

    serie = {"atualizado": hoje, "dias": []}
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as origem:
                anterior = json.load(origem)
            if isinstance(anterior.get("dias"), list):
                serie["dias"] = [d for d in anterior["dias"] if d.get("data") != hoje]
        except (json.JSONDecodeError, OSError):
            pass                                   # série ilegível: recomeça-se

    por_area = {}
    for l in linhas:
        registo = por_area.setdefault(l[0], {"noticias": 0, "fontes": set()})
        registo["noticias"] += 1
        if l[3]:
            registo["fontes"].add(l[3])

    serie["dias"].append({
        "data": hoje,
        "periodo": periodo or "sem limite",
        "areas": {nome: {"noticias": v["noticias"], "fontes": len(v["fontes"])}
                  for nome, v in sorted(por_area.items())},
    })
    serie["dias"].sort(key=lambda d: d["data"])

    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(serie, destino, ensure_ascii=False, indent=1)
    print(f"série diária atualizada: {len(serie['dias'])} dias em {caminho}")


if __name__ == "__main__":
    principal()
