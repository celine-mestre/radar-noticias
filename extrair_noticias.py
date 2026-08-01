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
import unicodedata
import os
import re
import sys
import time
from datetime import datetime, timedelta
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
# Domínios excluídos quando se restringe a fontes nacionais: domínios de topo dos
# restantes países de língua portuguesa e grupos de comunicação social que usam
# domínios genéricos.
EXCLUSOES_DOMINIO = [
    "site:.br", "site:.ao", "site:.mz", "site:.cv", "site:.st", "site:.gw",
    "site:.tl", "site:.mo",
    "site:globo.com", "site:r7.com", "site:metropoles.com", "site:abril.com",
    "site:uol.com.br", "site:novojornal.co.ao", "site:jornaldeangola.ao",
    "site:verangola.net", "site:opais.co.mz", "site:verdade.co.mz",
    "site:expressodasilhas.cv", "site:asemana.publ.cv",
]

GRUPOS = {
    "soberania": "Estado e soberania",
    "economia": "Economia, finanças e território",
    "social": "Sociedade e bem-estar",
    "ambiente": "Ambiente, energia e recursos naturais",
}

AREAS = [
    ("estrangeiros", "Negócios Estrangeiros", "soberania",
     ["Ministério dos Negócios Estrangeiros",
      "política externa portuguesa",
      "Conselho Europeu",
      "CPLP",
      "Nações Unidas",
      "diáspora portuguesa",
      "cooperação para o desenvolvimento",
      "rede consular"],
     []),
    ("financas", "Finanças", "economia",
     ["Ministério das Finanças",
      "Orçamento do Estado",
      "défice orçamental",
      "dívida pública",
      "IRS",
      "tributação das empresas",
      "execução orçamental",
      "Autoridade Tributária"],
     []),
    ("presidencia", "Presidência", "soberania",
     ["Conselho de Ministros",
      "Presidência do Conselho de Ministros",
      "Programa do Governo",
      "comunicação do Governo",
      "modernização administrativa",
      "dados abertos",
      "transparência administrativa"],
     []),
    ("reforma", "Reforma do Estado", "soberania",
     ["reforma do Estado",
      "Administração Pública",
      "desburocratização",
      "simplificação administrativa",
      "trabalhadores da Administração Pública",
      "inteligência artificial na Administração Pública",
      "SIADAP"],
     []),
    ("parlamentares", "Assuntos Parlamentares", "soberania",
     ["Assembleia da República",
      "debate parlamentar",
      "interpelação ao Governo",
      "audição parlamentar",
      "comissão parlamentar de inquérito",
      "regulação da comunicação social",
      "Entidade Reguladora para a Comunicação Social"],
     []),
    ("defesa", "Defesa Nacional", "soberania",
     ["Ministério da Defesa Nacional",
      "Forças Armadas",
      "NATO",
      "investimento em defesa",
      "indústria de defesa",
      "missões militares internacionais",
      "serviço militar"],
     []),
    ("interna", "Administração Interna", "soberania",
     ["Ministério da Administração Interna",
      "imigração",
      "pedidos de asilo",
      "controlo de fronteiras",
      "AIMA",
      "proteção civil",
      "segurança interna",
      "sinistralidade rodoviária"],
     []),
    ("justica", "Justiça", "soberania",
     ["Ministério da Justiça",
      "tribunais",
      "Ministério Público",
      "pendências processuais",
      "sistema prisional",
      "registos e notariado",
      "reforma da justiça"],
     []),
    ("economia", "Economia e Coesão Territorial", "economia",
     ["Ministério da Economia",
      "crescimento económico",
      "exportações portuguesas",
      "investimento empresarial",
      "turismo",
      "fundos europeus",
      "coesão territorial",
      "interioridade"],
     []),
    ("infraestruturas", "Infraestruturas e Habitação", "economia",
     ["Ministério das Infraestruturas e Habitação",
      "habitação",
      "arrendamento",
      "obras públicas",
      "ferrovia",
      "novo aeroporto",
      "transportes públicos",
      "licenciamento urbanístico"],
     []),
    ("educacao", "Educação, Ciência e Inovação", "social",
     ["Ministério da Educação",
      "escolas",
      "professores",
      "exames nacionais",
      "ensino superior",
      "investigação científica",
      "bolsas de investigação",
      "abandono escolar"],
     []),
    ("saude", "Saúde", "social",
     ["Ministério da Saúde",
      "Serviço Nacional de Saúde",
      "urgências hospitalares",
      "médicos de família",
      "listas de espera",
      "cuidados continuados",
      "medicamentos",
      "saúde mental"],
     []),
    ("trabalho", "Trabalho, Solidariedade e Segurança Social", "social",
     ["Ministério do Trabalho",
      "emprego",
      "desemprego",
      "salário mínimo",
      "pensões",
      "segurança social",
      "solidariedade social",
      "negociação coletiva",
      "apoios sociais"],
     []),
    ("cultura", "Cultura, Juventude e Desporto", "social",
     ["Ministério da Cultura",
      "património cultural",
      "museus",
      "criação artística",
      "políticas de juventude",
      "desporto",
      "alta competição",
      "língua portuguesa"],
     []),
    ("ambiente", "Ambiente e Energia", "ambiente",
     ["Ministério do Ambiente e Energia",
      "preço da energia",
      "mercado da eletricidade",
      "energias renováveis",
      "alterações climáticas",
      "descarbonização",
      "gestão de resíduos",
      "situação de seca",
      "incêndios florestais"],
     ["clima de negócios", "clima organizacional", "clima de confiança"]),
    ("agricultura", "Agricultura e Mar", "ambiente",
     ["Ministério da Agricultura e Mar",
      "política agrícola comum",
      "produção agrícola",
      "agricultores",
      "desenvolvimento rural",
      "gestão florestal",
      "pescas",
      "aquicultura",
      "economia do mar",
      "segurança alimentar",
      "regadio"],
     [])

]

AZUL, CINZA = "2B5683", "F2F5F8"

# ---------------------------------------------------------------------------
# FONTES — os feeds das próprias publicações
#
# Em vez de interrogar um motor de pesquisa, subscreve-se o feed de cada publicação
# e faz-se a marcação por palavras-chave do nosso lado.
# Não há teto de resultados, a ordenação é cronológica, as datas são as de
# publicação, as ligações são diretas e as descrições trazem o lead da redação.
# ---------------------------------------------------------------------------
FONTES = [
    ("Público", "publico.pt", "https://feeds.feedburner.com/PublicoRSS"),
    ("Público · Política", "publico.pt", "https://feeds.feedburner.com/publico-politica"),
    ("Público · Economia", "publico.pt", "https://feeds.feedburner.com/publico-economia"),
    ("Público · Sociedade", "publico.pt", "https://feeds.feedburner.com/publico-sociedade"),
    ("Expresso", "expresso.pt", "https://expresso.pt/rss"),
    ("Observador", "observador.pt", "https://observador.pt/feed/"),
    ("Jornal de Notícias", "jn.pt", "https://www.jn.pt/rss/"),
    ("Diário de Notícias", "dn.pt", "https://www.dn.pt/rss/"),
    ("Correio da Manhã", "cmjornal.pt", "https://www.cmjornal.pt/rss"),
    ("Jornal de Negócios", "jornaldenegocios.pt", "https://www.jornaldenegocios.pt/rss"),
    ("Jornal Económico", "jornaleconomico.pt", "https://jornaleconomico.sapo.pt/feed"),
    ("ECO", "eco.sapo.pt", "https://eco.sapo.pt/feed/"),
    ("RTP Notícias", "rtp.pt", "https://www.rtp.pt/noticias/rss"),
    ("SIC Notícias", "sicnoticias.pt", "https://sicnoticias.pt/rss"),
    ("CNN Portugal", "cnnportugal.iol.pt", "https://cnnportugal.iol.pt/rss"),
    ("TSF", "tsf.pt", "https://www.tsf.pt/rss/"),
    ("Renascença", "rr.sapo.pt", "https://rr.sapo.pt/rss"),
    ("Notícias ao Minuto", "noticiasaominuto.com", "https://www.noticiasaominuto.com/rss/ultima-hora"),
    ("Diário de Notícias da Madeira", "dnoticias.pt", "https://www.dnoticias.pt/rss"),
    ("Sábado", "sabado.pt", "https://www.sabado.pt/rss"),
    ("Visão", "visao.pt", "https://visao.pt/feed/"),
    ("Dinheiro Vivo", "dinheirovivo.pt", "https://www.dinheirovivo.pt/rss/"),
    ("Executive Digest", "executivedigest.sapo.pt", "https://executivedigest.sapo.pt/feed/"),
    ("Ambiente Magazine", "ambientemagazine.com", "https://www.ambientemagazine.com/feed/"),
    ("Agroportal", "agroportal.pt", "https://www.agroportal.pt/feed/"),
]

# Imprensa dos restantes países de língua portuguesa. Matéria da CPLP, cooperação,
# diáspora e política externa é frequentemente tratada primeiro nestes títulos.
FONTES_LUSOFONAS = [
    ("Jornal de Angola", "jornaldeangola.ao", "https://www.jornaldeangola.ao/ao/rss/"),
    ("Novo Jornal (Angola)", "novojornal.co.ao", "https://www.novojornal.co.ao/rss"),
    ("Angop", "angop.ao", "https://www.angop.ao/rss/ultimas.xml"),
    ("O País (Moçambique)", "opais.co.mz", "https://opais.co.mz/feed/"),
    ("Carta de Moçambique", "cartamz.com", "https://cartamz.com/index.php/component/obrss/rss-noticias"),
    ("Expresso das Ilhas (Cabo Verde)", "expressodasilhas.cv", "https://expressodasilhas.cv/rss"),
    ("Inforpress (Cabo Verde)", "inforpress.cv", "https://inforpress.cv/feed/"),
    ("Tatoli (Timor-Leste)", "tatoli.tl", "https://tatoli.tl/pt/feed/"),
    ("STP-Press (São Tomé)", "stp-press.st", "https://www.stp-press.st/feed/"),
    ("Agência Brasil", "agenciabrasil.ebc.com.br", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
    ("Folha de S.Paulo · Mundo", "folha.uol.com.br", "https://feeds.folha.uol.com.br/mundo/rss091.xml"),
]

# Imprensa internacional não lusófona, para ver como uma matéria portuguesa ou
# europeia é tratada fora.
FONTES_INTERNACIONAIS = [
    ("Euronews (português)", "pt.euronews.com", "https://pt.euronews.com/rss"),
    ("Politico Europe", "politico.eu", "https://www.politico.eu/feed/"),
    ("EURACTIV", "euractiv.com", "https://www.euractiv.com/feed/"),
    ("El País", "elpais.com", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
    ("El País · Internacional", "elpais.com", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada"),
    ("Le Monde", "lemonde.fr", "https://www.lemonde.fr/rss/une.xml"),
    ("BBC Mundo", "bbc.com", "https://feeds.bbci.co.uk/mundo/rss.xml"),
    ("Deutsche Welle (português)", "dw.com", "https://rss.dw.com/rdf/rss-br-all"),
    ("France 24 (português)", "france24.com", "https://www.france24.com/pt/rss"),
    ("RFI (português)", "rfi.fr", "https://www.rfi.fr/pt/rss"),
    ("The Guardian · Europe", "theguardian.com", "https://www.theguardian.com/world/europe-news/rss"),
    ("Agência Lusa · Internacional", "lusa.pt", "https://www.lusa.pt/rss/internacional"),
]


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


DOMINIOS_ALHEIOS = ("google.com", "google.pt", "gstatic.com", "googleusercontent.com",
                    "googleapis.com", "policies.google", "accounts.google", "consent.google")

# Publicações dos restantes países de língua portuguesa, para referência de quem
# analisar os ficheiros. A seleção por origem é feita no painel, sobre o domínio.
PUBLICACOES_LUSOFONAS = (
    "globo.com", "uol.com.br", "r7.com", "metropoles.com", "abril.com", "terra.com.br",
    "conjur.com.br", "migalhas.com.br", "jota.info", "exame.com",
    "jornaldeangola.ao", "novojornal.co.ao", "verangola.net", "angop.ao",
    "opais.co.mz", "idolo.co.mz", "verdade.co.mz", "carta.co.mz",
    "expressodasilhas.cv", "asemana.publ.cv", "inforpress.cv", "vozdoarquipelago.com",
    "tatoli.tl", "timorpost.com", "stp-press.st", "odemocratagb.com",
)

FICHEIROS_DE_IMAGEM = re.compile(r"\.(png|jpe?g|gif|webp|svg|ico|bmp)(\?|#|$)", re.IGNORECASE)


def endereco_plausivel(url):
    """Verifica se o endereço encontrado é mesmo o artigo de um jornal.

    Sem esta verificação, a leitura da página de reencaminhamento devolve o
    primeiro endereço que lá encontra — que costuma ser uma imagem alojada nos
    servidores do próprio Google, igual para todos os artigos.
    """
    if not url or not url.lower().startswith(("http://", "https://")) or len(url) < 24:
        return False
    if any(d in url for d in DOMINIOS_ALHEIOS):
        return False
    if FICHEIROS_DE_IMAGEM.search(url):
        return False
    return True


def endereco_do_artigo(ligacao, tempo_limite=12):
    """Converte o reencaminhamento do Google no endereço do jornal.

    Primeiro tenta descodificar o identificador, onde as versões mais antigas
    trazem o endereço em claro. Não resultando, segue o reencaminhamento na rede
    e devolve o endereço final. Falhando ambos, devolve a ligação original, que
    abre o artigo à mesma — é preferível a devolver um endereço errado.
    """
    if not ligacao or "news.google.com" not in ligacao:
        return ligacao

    identificador = ligacao.split("/articles/")[-1].split("?")[0]
    try:
        bruto = urlsafe_b64decode(identificador + "=" * (-len(identificador) % 4))
        for achado in re.findall(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{20,}", bruto):
            candidato = achado.decode("utf-8", "replace")
            if endereco_plausivel(candidato):
                return candidato
    except Exception:                                          # noqa: BLE001
        pass

    try:
        pedido = Request(ligacao, headers={"User-Agent": "Mozilla/5.0 SGGov-UPE-Radar/1.0"})
        with urlopen(pedido, timeout=tempo_limite) as resposta:
            final = resposta.geturl()
            if endereco_plausivel(final):
                return final
            corpo = resposta.read(60000).decode("utf-8", "replace")
        # O atributo data-n-au traz o endereço do artigo na página de reencaminhamento
        for padrao in (r'data-n-au="([^"]+)"',
                       r'<meta[^>]+http-equiv="refresh"[^>]+url=([^">]+)',
                       r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"'):
            for achado in re.findall(padrao, corpo, re.IGNORECASE):
                candidato = html.unescape(achado).strip()
                if endereco_plausivel(candidato):
                    return candidato
    except Exception:                                          # noqa: BLE001
        pass

    return ligacao


def resolver_ligacoes(linhas, trabalhadores=8):
    """Resolve em paralelo os reencaminhamentos de todas as notícias."""
    enderecos = [l[7] for l in linhas]
    unicos = list(dict.fromkeys(enderecos))
    print(f"A resolver {len(unicos)} ligações…", end=" ", flush=True)
    with ThreadPoolExecutor(max_workers=trabalhadores) as piscina:
        resolvidos = dict(zip(unicos, piscina.map(endereco_do_artigo, unicos)))
    convertidas = 0
    for l in linhas:
        novo = resolvidos.get(l[7], l[7])
        if novo != l[7]:
            convertidas += 1
            l[7] = novo
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
                      "titulo": titulo, "resumo": resumo, "ligacao": ligacao,
                      "imagem": imagem_do_item(item)})
    return itens


def imagem_do_item(item):
    """Endereço da imagem que o feed associa ao artigo, se houver.

    As publicações declaram-na de várias formas — media:content, media:thumbnail,
    enclosure ou uma etiqueta img dentro da descrição. Percorrem-se todas, pela
    ordem em que costumam dar melhor resultado.
    """
    for etiqueta in ("content", "thumbnail"):
        for no in item.iter():
            if no.tag.endswith("}" + etiqueta) or no.tag == "media:" + etiqueta:
                url = no.get("url") or ""
                if url.startswith("http"):
                    return url

    fecho = item.find("enclosure")
    if fecho is not None:
        tipo = (fecho.get("type") or "")
        url = fecho.get("url") or ""
        if url.startswith("http") and (tipo.startswith("image") or not tipo):
            return url

    for campo in ("description", "{http://purl.org/rss/1.0/modules/content/}encoded"):
        bruto = item.findtext(campo) or ""
        achado = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', bruto)
        if achado and achado.group(1).startswith("http"):
            return achado.group(1)

    return ""


def _sem_acentos(t):
    return unicodedata.normalize("NFD", t.lower()).encode("ascii", "ignore").decode()


def _raiz(palavra):
    """Reduz a palavra à raiz, para o plural e o singular casarem entre si."""
    for fim, troca in (("coes", "ca"), ("cao", "ca"), ("oes", ""), ("ao", ""),
                       ("ais", "a"), ("al", "a"), ("eis", "e"), ("el", "e"),
                       ("res", "r"), ("ses", "s"), ("es", "")):
        if palavra.endswith(fim):
            return palavra[: -len(fim)] + troca
    return palavra[:-1] if palavra.endswith("s") else palavra


def contem_expressao(texto, expressao):
    """Procura a expressão no texto, aceitando singular e plural.

    Sem isto, "medicamentos" não encontraria "medicamento" — e a maioria dos
    títulos usa o singular.
    """
    palavras = [p for p in _sem_acentos(expressao).split() if p]
    if not palavras:
        return False
    padrao = r"\s+".join(re.escape(_raiz(p)) + r"\w{0,4}" for p in palavras)
    return re.search(r"(^|\W)" + padrao + r"(\W|$)", texto) is not None


def marcar_por_areas(it, alvo):
    """Devolve as áreas e as palavras-chave que este artigo satisfaz.

    É a mesma regra que se aplicaria numa condição de um agregador de feeds:
    procura da expressão no título e no resumo. Um artigo pode pertencer a mais
    do que uma área.
    """
    texto = _sem_acentos(it["titulo"] + " " + (it["resumo"] or ""))
    achados = []
    for ident, nome, grupo, palavras, excluir in alvo:
        if any(contem_expressao(texto, e) for e in excluir):
            continue
        casadas = [p for p in palavras if contem_expressao(texto, p)]
        if casadas:
            achados.append((nome, GRUPOS[grupo], casadas))
    return achados


def recolher_fontes(alvo, dias=7, pausa=0.4, internacionais=True, lusofonas=True):
    """Lê os feeds das publicações e marca os artigos pelas áreas governativas.

    Um artigo é recolhido por ser de uma fonte conhecida, e não por corresponder
    a uma pesquisa.
    """
    limite = datetime.now() - timedelta(days=dias)
    encontrados, lidos, falhas = {}, 0, []
    lista = list(FONTES)
    if lusofonas:
        lista += FONTES_LUSOFONAS
    if internacionais:
        lista += FONTES_INTERNACIONAIS

    for i, (nome_fonte, dominio, url) in enumerate(lista, 1):
        print(f"[{i}/{len(lista)}] {nome_fonte}…", end=" ", flush=True)
        try:
            itens = extrair_itens(ler_feed(url))
        except Exception as erro:                              # noqa: BLE001
            print(f"falhou ({erro})")
            falhas.append((nome_fonte, str(erro)))
            continue

        lidos += len(itens)
        marcados = 0
        for it in itens:
            if it["data"] and it["data"] < limite:
                continue
            for nome_area, grupo_nome, palavras in marcar_por_areas(it, alvo):
                chave = (nome_area, it["titulo"].lower())
                if chave in encontrados:
                    encontrados[chave]["palavras"].update(palavras)
                    continue
                encontrados[chave] = {
                    "area": nome_area, "grupo": grupo_nome, "data": it["data"],
                    "fonte": it["fonte"] or nome_fonte, "dominio": it["dominio"] or dominio,
                    "titulo": it["titulo"], "resumo": it["resumo"],
                    "ligacao": it["ligacao"], "imagem": it.get("imagem", ""),
                    "palavras": set(palavras),
                }
                marcados += 1
        print(f"{len(itens)} artigos, {marcados} marcados")
        if i < len(lista):
            time.sleep(pausa)

    print(f"\n{lidos} artigos lidos · {len(encontrados)} marcados por área")
    return list(encontrados.values()), falhas


def recolher_palavras(periodo, alvo, pausa=1.0, teto=60):
    """Uma consulta por palavra-chave, além da consulta da área.

    É isto que permite ao painel responder a pesquisas por palavra-chave sem
    interrogar o serviço: os resultados de cada termo ficam nos ficheiros.
    Cada notícia guarda as palavras-chave que a trouxeram.
    """
    encontradas = {}
    total = sum(len(a[3]) for a in alvo)
    feitas = 0

    for ident, nome, grupo, palavras, excluir in alvo:
        for palavra in palavras:
            feitas += 1
            q = f'"{palavra}"'
            if periodo:
                q += f" when:{periodo}"
            try:
                itens = extrair_itens(ler_feed(url_feed(q)))[:teto]
            except Exception as erro:                          # noqa: BLE001
                print(f"  [{feitas}/{total}] {palavra}: falhou ({erro})")
                continue
            novas = 0
            for it in itens:
                # o serviço faz correspondência aproximada: confirma-se o termo
                texto = _sem_acentos(it["titulo"] + " " + (it["resumo"] or ""))
                if not contem_expressao(texto, palavra):
                    continue
                chave = (nome, it["titulo"].lower(), (it["fonte"] or "").lower())
                if chave in encontradas:
                    encontradas[chave]["palavras"].add(palavra)
                else:
                    registo = dict(it)
                    registo.update({"area": nome, "grupo": GRUPOS[grupo], "palavras": {palavra}})
                    encontradas[chave] = registo
                    novas += 1
            print(f"  [{feitas}/{total}] {palavra}: {novas} novas")
            time.sleep(pausa)

    return list(encontradas.values())


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
                  "Domínio", "Título", "Resumo", "Ligação"]
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
            c.alignment = Alignment(vertical="top", wrap_text=(j in (6, 7)))
            if i % 2 == 0:
                c.fill = alt
            if j == 3 and v is not None:
                c.number_format = "yyyy-mm-dd hh:mm"
            if j == 8 and v:
                c.hyperlink = v
                c.font = fonte(size=10, color="2B5683", underline="single")

    for j, w in enumerate([30, 28, 19, 24, 22, 54, 54, 46], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{max(2, len(linhas) + 1)}"

    # --- Folha de síntese ---
    wr = wb.create_sheet("Síntese")
    wr.column_dimensions["A"].width = 44
    wr.column_dimensions["B"].width = 16
    wr["A1"] = "Síntese da recolha"
    wr["A1"].font = fonte(size=13, bold=True, color=AZUL)

    contexto = [
        ("Data da recolha", datetime.now().strftime("%Y-%m-%d %H:%M")),
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
    ap.add_argument("--arquivo", default=None,
                    help="ficheiro JSON com as notícias dos últimos dias, acumulado a cada recolha")
    ap.add_argument("--dias-arquivo", type=int, default=7,
                    help="dias a manter no arquivo (predefinição: 7)")
    ap.add_argument("--por-palavra", action="store_true",
                    help="recolher também uma consulta por cada palavra-chave")
    ap.add_argument("--fontes", action="store_true",
                    help="ler os feeds das publicações e marcar por área (método de agregador)")
    ap.add_argument("--sem-internacionais", action="store_true",
                    help="ler apenas as publicações portuguesas, sem imprensa estrangeira")
    args = ap.parse_args()

    if args.area and args.area not in {a[0] for a in AREAS}:
        sys.exit(f"Área desconhecida: {args.area}")

    saida = args.saida or f"radar_noticias_{datetime.now():%Y%m%d_%H%M}.xlsx"
    so_nacionais = not args.todas_as_fontes

    alvo = [a for a in AREAS if args.area is None or a[0] == args.area]
    das_fontes = []

    if args.fontes:
        # Origem principal: os feeds das próprias publicações
        print("Leitura dos feeds das publicações:")
        das_fontes, falhas = recolher_fontes(
            alvo, args.dias_arquivo,
            internacionais=not args.sem_internacionais,
            lusofonas=not args.sem_internacionais)
        campos = ["area", "grupo", "data", "fonte", "dominio", "titulo", "resumo", "ligacao"]
        linhas = [[n["area"], n["grupo"], n["data"], n["fonte"], n["dominio"],
                   n["titulo"], n["resumo"], n["ligacao"]] for n in das_fontes]
        linhas.sort(key=lambda l: (l[2] is None, l[2]), reverse=True)
    else:
        # Origem alternativa: pesquisa no Google Notícias
        linhas, falhas = recolher(args.periodo, args.area, so_nacionais)
        if not args.sem_resolver_ligacoes and linhas:
            linhas = resolver_ligacoes(linhas)
        linhas = [l[:6] + [""] + l[6:] for l in linhas]   # coluna de resumo vazia
    gravar(linhas, falhas, saida, args.periodo, so_nacionais)
    print(f"\n{len(linhas)} notícias gravadas em {saida}")

    vistos_anteriores = ligacoes_da_recolha_anterior(args.json) if (args.json and args.historico) else {}

    if args.json:
        campos = ["area", "grupo", "data", "fonte", "dominio", "titulo", "resumo", "ligacao"]
        noticias = []
        for l in linhas:
            registo = dict(zip(campos, l))
            registo["data"] = registo["data"].strftime("%Y-%m-%d %H:%M") if registo["data"] else ""
            noticias.append(registo)
        MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        agora = datetime.now()
        if args.fontes:
            for registo, n in zip(noticias, das_fontes):
                registo["palavras"] = sorted(n["palavras"])
        pacote = {
            "gerado": f"{agora.day} de {MESES[agora.month - 1]} de {agora.year}, {agora:%Hh%M}",
            "origem": "feeds das publicações" if args.fontes else "Google Notícias",
            "periodo": args.periodo or "sem limite",
            "noticias": noticias,
        }
        with open(args.json, "w", encoding="utf-8") as destino:
            json.dump(pacote, destino, ensure_ascii=False, indent=1)
        print(f"{len(noticias)} notícias gravadas em {args.json}")

    por_palavra = list(das_fontes)

    if args.por_palavra:
        print("\nRecolha por palavra-chave:")
        por_palavra = recolher_palavras(args.periodo, alvo)
        if not args.sem_resolver_ligacoes and por_palavra:
            enderecos = {n["ligacao"] for n in por_palavra}
            print(f"A resolver {len(enderecos)} ligações…", end=" ", flush=True)
            with ThreadPoolExecutor(max_workers=8) as piscina:
                mapa = dict(zip(enderecos, piscina.map(endereco_do_artigo, enderecos)))
            for n in por_palavra:
                n["ligacao"] = mapa.get(n["ligacao"], n["ligacao"])
            print("feito")
        print(f"{len(por_palavra)} notícias com palavra-chave identificada")

    if args.arquivo:
        atualizar_arquivo(args.arquivo, linhas, args.dias_arquivo, por_palavra)

    if args.historico:
        atualizar_historico(args.historico, linhas, args.periodo, vistos_anteriores)
    if falhas:
        print(f"{len(falhas)} áreas falharam — ver a folha Falhas.")


def ligacoes_da_recolha_anterior(caminho_json):
    """Ligações da recolha anterior, para distinguir o que é novo.

    As janelas de 24 horas não são perfeitamente disjuntas: o operador de tempo
    do Google atua sobre a data de indexação e um artigo reindexado volta a
    aparecer. Comparar com a véspera é o que permite contar notícias novas em
    vez de contar repetições.
    """
    if not os.path.exists(caminho_json):
        return {}
    try:
        with open(caminho_json, encoding="utf-8") as origem:
            anterior = json.load(origem)
    except (json.JSONDecodeError, OSError):
        return {}
    vistos = {}
    for n in anterior.get("noticias", []):
        vistos.setdefault(n.get("area", ""), set()).add(n.get("ligacao", ""))
    return vistos


def atualizar_arquivo(caminho, linhas, dias=7, por_palavra=None):
    """Acumula as notícias dos últimos dias num único ficheiro.

    É o que permite ao painel responder a pesquisas por palavra-chave e a
    janelas de vários dias sem depender de serviços externos: em vez de
    interrogar o serviço, filtra este arquivo.
    """
    campos = ["area", "grupo", "data", "fonte", "dominio", "titulo", "ligacao"]
    limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

    anteriores = []
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as origem:
                anteriores = json.load(origem).get("noticias", [])
        except (json.JSONDecodeError, OSError):
            anteriores = []

    def registo(l):
        r = dict(zip(campos, l))
        r["data"] = r["data"].strftime("%Y-%m-%d %H:%M") if r["data"] else ""
        return r

    novas = [registo(l) for l in linhas]
    for n in (por_palavra or []):
        registo_novo = {
            "area": n["area"], "grupo": n["grupo"],
            "data": n["data"].strftime("%Y-%m-%d %H:%M") if n["data"] else "",
            "fonte": n["fonte"], "dominio": n["dominio"], "titulo": n["titulo"],
            "ligacao": n["ligacao"], "palavras": sorted(n["palavras"]),
        }
        if n.get("resumo"):
            registo_novo["resumo"] = n["resumo"]
        if n.get("imagem"):
            registo_novo["imagem"] = n["imagem"]
        novas.append(registo_novo)

    juntas = anteriores + novas
    vistos, mantidas = {}, []
    for n in juntas:
        # Sem data reconhecida não entra: seria impossível saber se está na janela
        if not n.get("data") or n["data"][:10] < limite:
            continue
        chave = (n.get("area", ""), n.get("titulo", "").lower(), n.get("fonte", "").lower())
        if chave in vistos:
            # já existe: junta-se apenas as palavras-chave que a trouxeram
            anterior = vistos[chave]
            if n.get("palavras"):
                anterior["palavras"] = sorted(set(anterior.get("palavras", [])) | set(n["palavras"]))
            if n.get("resumo") and not anterior.get("resumo"):
                anterior["resumo"] = n["resumo"]
            continue
        vistos[chave] = n
        mantidas.append(n)

    mantidas.sort(key=lambda n: n.get("data", ""), reverse=True)
    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump({"dias": dias, "atualizado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "noticias": mantidas}, destino, ensure_ascii=False)
    print(f"arquivo de {dias} dias: {len(mantidas)} notícias em {caminho}")


def atualizar_historico(caminho, linhas, periodo, vistos=None):
    """Acrescenta à série diária o retrato de hoje, por área governativa.

    Guarda apenas agregados — notícias recolhidas, notícias novas face à recolha
    anterior e publicações distintas. É deliberadamente pequeno: cresce cerca de
    2 KB por dia e pode ser lido de uma vez pelo painel.
    """
    vistos = vistos or {}
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
        registo = por_area.setdefault(l[0], {"noticias": 0, "novas": 0, "fontes": set()})
        registo["noticias"] += 1
        if l[7] and l[7] not in vistos.get(l[0], set()):
            registo["novas"] += 1
        if l[3]:
            registo["fontes"].add(l[3])

    serie["dias"].append({
        "data": hoje,
        "periodo": periodo or "sem limite",
        "areas": {nome: {"noticias": v["noticias"], "novas": v["novas"], "fontes": len(v["fontes"])}
                  for nome, v in sorted(por_area.items())},
    })
    serie["dias"].sort(key=lambda d: d["data"])

    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(serie, destino, ensure_ascii=False, indent=1)
    print(f"série diária atualizada: {len(serie['dias'])} dias em {caminho}")


if __name__ == "__main__":
    principal()
