#!/usr/bin/env python3
"""Fecha os dias já passados a partir do arquivo mensal.

Porquê
------
A série diária (historico.json) e a série de sentimento (sentimento-serie.json)
eram construídas a partir do arquivo.json, que só guarda sete dias. Quando um
dia saía dessa janela, ficava congelado com o número que tinha nesse momento — e
deixava de acompanhar duas coisas que continuam a acontecer depois:

  1. a REVALIDAÇÃO, que retira do arquivo mensal as marcações que já não casam
     com as expressões em vigor (foi o caso do termo «empresas» na Economia);
  2. as notícias publicadas ao fim da noite, que só entram na recolha da manhã
     seguinte — a recolha das 23h07 não chega às 23h59.

O resultado eram três contagens diferentes para o mesmo dia. Este programa
resolve-o pela raiz: o arquivo mensal (meses/ e sentimento-meses/) passa a ser a
ÚNICA fonte de verdade, e cada dia é recontado a partir dele.

Quando um dia fecha
-------------------
O dia D fica selado na primeira recolha de D+1, porque só então está lá tudo o
que foi publicado entre as 00h00 e as 23h59 de D. Por isso este programa
reconstrói todos os dias ANTERIORES a hoje e nunca toca no dia em curso, que
continua a crescer a cada recolha, como sempre.

Uso
---
    python3 reconstruir_series.py                 # fecha tudo o que já passou
    python3 reconstruir_series.py --simular       # mostra o que mudaria
    python3 reconstruir_series.py --desde 2026-08-04
"""

import argparse
import glob
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

LISBOA = ZoneInfo("Europe/Lisbon")

# As mesmas regras de origem do painel, do relatório e da recolha. Ficam aqui
# repetidas de propósito: este programa tem de poder correr sozinho, sem
# importar o extrair_noticias.py, que é pesado e traz o classificador todo.
DOMINIOS_PT = ("noticiasaominuto.com", "theportugalnews.com", "portugalresident.com",
               "agencialusa.com", "cnnportugal.iol.pt", "iol.pt", "eco.sapo.pt",
               "sapo.pt", "aeiou.pt", "impresa.pt", "medialivre.pt", "lusa.pt")
DOMINIOS_LUSOFONOS = (".ao", ".mz", ".cv", ".st", ".gw", ".tl", ".br")


def origem_da_fonte(dominio):
    d = (dominio or "").lower().replace("www.", "")
    if not d:
        return "nacionais"
    if d.endswith(".pt") or any(d == x or d.endswith("." + x) for x in DOMINIOS_PT):
        return "nacionais"
    if any(d.endswith(t) for t in DOMINIOS_LUSOFONOS):
        return "lusofonas"
    return "internacionais"


def hoje():
    return datetime.now(LISBOA).strftime("%Y-%m-%d")


# ── LEITURA DO ARQUIVO ───────────────────────────────────────────────────────

def titulo_fonte(n):
    return ((n.get("titulo") or "").strip().lower(),
            (n.get("fonte") or n.get("dominio") or "").strip().lower())


class Juntar:
    """Junta os registos que são o mesmo artigo, por qualquer das duas vias.

    Nenhuma chave sozinha chega:
      · pela LIGAÇÃO escapam as peças que o mesmo órgão publica em dois
        endereços — a RTP em /mundo/ e em /guerra-na-ucrania/, o SAPO Tek em
        /computadores/ e em /mobile/apps/ —, e como o arquivo de sete dias (de
        onde o Amália trabalha) as junta por título+fonte, só uma era avaliada
        e a outra ficava eternamente «por avaliar»;
      · por TÍTULO+FONTE escapam as peças cujo título o órgão corrige ao longo
        do dia, que passariam a contar duas vezes.
    Junta-se por ambas: dois registos são o mesmo artigo se partilharem a
    ligação ou o par título+fonte. É o mesmo que o arquivo faz, mais o caso das
    ligações repetidas.
    """

    def __init__(self):
        self.pai = {}

    def raiz(self, x):
        self.pai.setdefault(x, x)
        while self.pai[x] != x:
            self.pai[x] = self.pai[self.pai[x]]
            x = self.pai[x]
        return x

    def unir(self, a, b):
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            self.pai[rb] = ra


def ler_arquivo_mensal(pasta):
    """Devolve, por dia: as marcações (par área×notícia) e as notícias distintas.

    O arquivo grava uma linha por par área-notícia, e a mesma notícia pode estar
    em várias áreas — daí a distinção. Também guarda as notícias NÃO marcadas
    (área vazia), que existem para futuros retroativos mas não contam para
    nenhuma série: essas ficam de fora.
    """
    # Primeira passagem: descobrir que registos são o mesmo artigo.
    grupos = defaultdict(Juntar)
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            for linha in origem:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    n = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if not (n.get("area") and n.get("ligacao")):
                    continue
                data = (n.get("data") or "")[:10]
                if len(data) != 10:
                    continue
                grupos[data].unir(("l", n["ligacao"]), ("t", titulo_fonte(n)))

    dias = defaultdict(lambda: {"pares": {}, "distintas": {},
                                "ligacoes": defaultdict(set)})
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            for linha in origem:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    n = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                area = n.get("area") or ""
                lig = n.get("ligacao") or ""
                data = (n.get("data") or "")[:10]
                if not area or not lig or len(data) != 10:
                    continue
                d = dias[data]
                ident = grupos[data].raiz(("l", lig))
                d["pares"][(ident, area)] = n
                d["distintas"][ident] = origem_da_fonte(n.get("dominio"))
                d["ligacoes"][ident].add(lig)
    return dias


def ler_sentimento_arquivado(pasta):
    """Devolve {ligação: tom}. O arquivo é permanente e nunca é podado."""
    tom = {}
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            for linha in origem:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    r = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if r.get("lig") and r.get("s"):
                    tom[r["lig"]] = r["s"]
    return tom


# ── RECONSTRUÇÃO ─────────────────────────────────────────────────────────────

def dia_da_serie(data, registo):
    """Um dia do historico.json, recontado do arquivo."""
    areas = {}
    for (_, area), n in registo["pares"].items():
        a = areas.setdefault(area, {
            "noticias": 0, "novas": 0, "fontes": set(),
            "origens": {"nacionais": 0, "lusofonas": 0, "internacionais": 0},
            "palavras": defaultdict(int),
        })
        a["noticias"] += 1
        a["fontes"].add(n.get("fonte") or n.get("dominio") or "")
        a["origens"][origem_da_fonte(n.get("dominio"))] += 1
        for p in (n.get("palavras") or []):
            a["palavras"][p] += 1

    saida = {}
    for nome, a in sorted(areas.items()):
        saida[nome] = {
            "noticias": a["noticias"],
            # Mantido por compatibilidade com o formato antigo: desde que a
            # série é recontada do arquivo, cada notícia conta uma só vez no
            # seu dia e "novas" é sempre igual a "noticias".
            "novas": a["noticias"],
            "fontes": len([f for f in a["fontes"] if f]),
            "origens": a["origens"],
            "palavras": dict(sorted(a["palavras"].items(),
                                    key=lambda kv: (-kv[1], kv[0]))),
        }

    por_origem = {"nacionais": 0, "lusofonas": 0, "internacionais": 0}
    for o in registo["distintas"].values():
        por_origem[o] += 1

    return {
        "data": data,
        "periodo": "dia completo",
        # Notícias distintas: uma notícia que toca três áreas conta uma vez
        # aqui e três vezes nas áreas. É esta a contagem que o painel mostra
        # como "notícias"; a das áreas é de marcações.
        "distintas": {"total": len(registo["distintas"]), **por_origem},
        "areas": saida,
    }


# Quantas publicações se guardam por área e por dia. O cruzamento área ×
# publicação precisa de uma tabela por dia, mas a cauda longa não interessa a
# ninguém: guardam-se as que mais noticiaram e o ficheiro fica sob controlo.
#
# O valor era 12 e serviu enquanto uma área era noticiada por nove ou dez
# publicações por dia. Depois do alargamento da leitura, a mediana passou a
# dezanove e o máximo a vinte e nove — e o corte, que perdia 1% das marcações,
# passou a perder 17,5%. Medido em agosto de 2026: com 20 a perda cai para 1,2%
# e com 25 para 0,2%. Fica em 25, que cobre praticamente tudo sem inchar o
# ficheiro: são poucos quilobytes por dia mais.
PUBS_POR_AREA = 25

# Nomes que não são publicações: créditos de fotografia e restos de título que
# alguns publicadores metem no campo <source> do artigo. A recolha já deixou de
# os aceitar, mas o arquivo é permanente e guarda os que entraram — e o painel
# de evolução lê o arquivo, pelo que sem isto ficariam à vista para sempre.
CREDITO = re.compile(r"^(AFP|REUTERS|AP|EPA|LUSA|DPA|ASSOCIATED PRESS)\b[\s\-]", re.I)


def parece_credito(nome):
    return (not nome or len(nome) > 38 or "©" in nome or "/" in nome
            or nome.count(" ") > 5 or CREDITO.match(nome) is not None)


def nomes_por_dominio(dias):
    """O nome verdadeiro de cada órgão, deduzido do próprio arquivo.

    Para cada domínio, o nome mais frequente que não pareça um crédito. Funciona
    porque o erro é minoritário: o Expresso das Ilhas aparece 297 vezes com o
    seu nome e 8 vezes com o título de outra peça. Onde nem isso resolve — o
    caso do s.rfi.fr, em que quase todos os registos são créditos —, fica o
    domínio, que é feio mas verdadeiro, e corrige-se sozinho à medida que as
    recolhas novas trazem o nome certo.
    """
    contagem = defaultdict(lambda: defaultdict(int))
    for registo in dias.values():
        for n in registo["pares"].values():
            dominio = (n.get("dominio") or "").lower()
            if dominio:
                contagem[dominio][n.get("fonte") or ""] += 1
    # A lista das fontes configuradas manda: se o domínio consta dela, o nome é
    # esse e não há dedução que valha. A heurística fica para o que sobra — um
    # domínio que já não esteja na lista, mas cujo histórico ainda conte.
    try:
        from extrair_noticias import _mapa_dominios
        oficiais = _mapa_dominios()
    except Exception:                                          # noqa: BLE001
        oficiais = {}

    mapa = {}
    for dominio, nomes in contagem.items():
        limpo = dominio.replace("www.", "")
        if limpo in oficiais:
            mapa[dominio] = oficiais[limpo]
            continue
        bons = sorted(((q, nome) for nome, q in nomes.items()
                       if not parece_credito(nome)), reverse=True)
        mapa[dominio] = bons[0][1] if bons else dominio
    return mapa


def dia_das_publicacoes(data, registo, origens, nomes):
    """Que publicações sustentaram cada área nesse dia.

    A origem não se grava por dia: cada publicação tem sempre a mesma, e uma
    tabela no topo do ficheiro chega para o painel poder filtrar. Guardá-la em
    cada linha engordava o ficheiro para dizer sempre o mesmo.
    """
    contagem = {}
    for (_, area), n in registo["pares"].items():
        # O nome vem da tabela do domínio, não do registo: assim um crédito de
        # fotografia que tenha entrado num dia solto não vira publicação.
        fonte = nomes.get((n.get("dominio") or "").lower()) \
            or n.get("dominio") or ""
        # Deliberadamente NÃO se recorre ao campo «fonte» do registo: é
        # precisamente aí que moram os créditos de fotografia e os títulos de
        # outras peças que se faziam passar por publicações. Sem domínio, a
        # linha não entra no quadro das publicações — continua a contar para o
        # volume da área, que é o que ela mede de facto.
        if not fonte:
            continue
        origens.setdefault(fonte, origem_da_fonte(n.get("dominio")))
        contagem.setdefault(area, {})
        contagem[area][fonte] = contagem[area].get(fonte, 0) + 1
    areas = {}
    for area, pubs in sorted(contagem.items()):
        melhores = sorted(pubs.items(), key=lambda kv: (-kv[1], kv[0]))[:PUBS_POR_AREA]
        areas[area] = dict(melhores)
    return {"data": data, "areas": areas}


def dia_do_sentimento(data, registo, tom):
    """Um dia do sentimento-serie.json, recontado do arquivo.

    Por área continua a contar marcações, para casar com o volume; o bloco
    "total" conta notícias distintas, porque uma notícia tem um só tom e somar
    as áreas contá-la-ia mais do que uma vez.
    """
    def vazio():
        return {"nacionais": 0, "avaliadas": 0,
                "positivo": 0, "neutro": 0, "negativo": 0}

    def tom_de(ident):
        """O tom do artigo, por qualquer um dos endereços em que saiu.

        As ligações são percorridas por ordem, e não pela do conjunto: o mesmo
        artigo em dois endereços pode ter sido avaliado duas vezes com
        resultados diferentes, e sem ordem fixa a série mudava de uma execução
        para a outra sem nada ter mudado nos dados.
        """
        for lig in sorted(registo["ligacoes"].get(ident, ())):
            if tom.get(lig):
                return tom[lig]
        return None

    areas = {}
    for (ident, area), n in registo["pares"].items():
        if origem_da_fonte(n.get("dominio")) != "nacionais":
            continue
        a = areas.setdefault(area, vazio())
        a["nacionais"] += 1
        s = tom_de(ident)
        if s in ("positivo", "neutro", "negativo"):
            a["avaliadas"] += 1
            a[s] += 1

    total = vazio()
    for ident, o in registo["distintas"].items():
        if o != "nacionais":
            continue
        total["nacionais"] += 1
        s = tom_de(ident)
        if s in ("positivo", "neutro", "negativo"):
            total["avaliadas"] += 1
            total[s] += 1

    return {"data": data, "total": total, "areas": dict(sorted(areas.items()))}


def juntar(dias_antigos, dias_novos, limite):
    """Substitui os dias reconstruídos e deixa intacto o dia em curso."""
    por_data = {d["data"]: d for d in dias_antigos}
    for d in dias_novos:
        por_data[d["data"]] = d
    return [por_data[k] for k in sorted(por_data)], limite


def carregar(caminho, omissao):
    if not os.path.exists(caminho):
        return dict(omissao)
    try:
        with open(caminho, encoding="utf-8") as origem:
            return json.load(origem)
    except (json.JSONDecodeError, OSError):
        return dict(omissao)


def principal():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mensal", default="meses")
    ap.add_argument("--mensal-sentimento", default="sentimento-meses")
    ap.add_argument("--historico", default="historico.json")
    ap.add_argument("--serie-sentimento", default="sentimento-serie.json")
    ap.add_argument("--publicacoes", default="publicacoes.json")
    ap.add_argument("--dias-publicacoes", type=int, default=120,
                    help="quantos dias de publicações guardar (0 = todos)")
    ap.add_argument("--desde", default=None,
                    help="primeira data a reconstruir (AAAA-MM-DD)")
    ap.add_argument("--simular", action="store_true",
                    help="mostra as diferenças sem gravar")
    args = ap.parse_args()

    corte = hoje()
    print(f"Hoje é {corte}; fecham-se os dias anteriores.")

    if not os.path.isdir(args.mensal):
        sys.exit(f"Sem arquivo mensal em {args.mensal}: nada a fazer.")

    arquivo = ler_arquivo_mensal(args.mensal)
    tom = ler_sentimento_arquivado(args.mensal_sentimento) \
        if os.path.isdir(args.mensal_sentimento) else {}
    print(f"{len(arquivo)} dias no arquivo, {len(tom)} avaliações arquivadas.")

    datas = sorted(d for d in arquivo
                   if d < corte and (not args.desde or d >= args.desde))
    if not datas:
        print("Nenhum dia por fechar.")
        return

    hist = carregar(args.historico, {"atualizado": None, "dias": []})
    sent = carregar(args.serie_sentimento,
                    {"atualizado": None, "estado": None, "dias": []})

    antes_h = {d["data"]: sum(a["noticias"] for a in d["areas"].values())
               for d in hist.get("dias", [])}
    antes_s = {d["data"]: sum(a["nacionais"] for a in d.get("areas", {}).values())
               for d in sent.get("dias", [])}

    novos_h = [dia_da_serie(d, arquivo[d]) for d in datas]
    novos_s = [dia_do_sentimento(d, arquivo[d], tom) for d in datas]
    origens_pub = {}
    nomes = nomes_por_dominio(arquivo)
    novos_p = [dia_das_publicacoes(d, arquivo[d], origens_pub, nomes) for d in datas]

    print(f"\n{'dia':12}{'marcações':>11}{'antes':>8}{'notícias':>10}"
          f"{'nac. aval.':>12}")
    for h, s in zip(novos_h, novos_s):
        m = sum(a["noticias"] for a in h["areas"].values())
        a0 = antes_h.get(h["data"], 0)
        print(f"{h['data']:12}{m:11}{a0:8}{h['distintas']['total']:10}"
              f"{s['total']['avaliadas']:6}/{s['total']['nacionais']:<6}")

    tot_m = sum(sum(a["noticias"] for a in h["areas"].values()) for h in novos_h)
    tot_a = sum(antes_h.get(h["data"], 0) for h in novos_h)
    print(f"\nMarcações: {tot_a} → {tot_m} ({tot_m - tot_a:+d})")
    mudou_s = sum(1 for s in novos_s
                  if antes_s.get(s["data"]) !=
                  sum(a["nacionais"] for a in s["areas"].values()))
    print(f"Dias com sentimento recontado: {mudou_s} de {len(novos_s)}")

    if args.simular:
        print("\n(simulação: nada foi gravado)")
        return

    hist["dias"], _ = juntar(hist.get("dias", []), novos_h, corte)
    hist["atualizado"] = corte
    with open(args.historico, "w", encoding="utf-8") as saida:
        json.dump(hist, saida, ensure_ascii=False, indent=1)

    sent["dias"], _ = juntar(sent.get("dias", []), novos_s, corte)
    # Só a data: com a hora, o ficheiro mudava a cada recolha mesmo sem
    # nada de novo, e o repositório enchia-se de gravações vazias.
    sent["atualizado"] = corte
    sent.setdefault("estado", "em validação — leitura humana em curso")
    with open(args.serie_sentimento, "w", encoding="utf-8") as saida:
        json.dump(sent, saida, ensure_ascii=False, indent=1)

    pub = carregar(args.publicacoes, {"atualizado": None, "dias": []})
    pub["dias"], _ = juntar(pub.get("dias", []), novos_p, corte)
    if args.dias_publicacoes > 0:
        pub["dias"] = pub["dias"][-args.dias_publicacoes:]
    # A tabela de origens acumula-se: uma publicação que deixe de aparecer nos
    # dias recentes continua a ter origem conhecida para os dias antigos.
    pub["origens"] = {**(pub.get("origens") or {}), **origens_pub}
    pub["atualizado"] = corte
    with open(args.publicacoes, "w", encoding="utf-8") as saida:
        json.dump(pub, saida, ensure_ascii=False, indent=1)

    print(f"\nGravados {args.historico}, {args.serie_sentimento} "
          f"e {args.publicacoes} ({len(pub['dias'])} dias).")


if __name__ == "__main__":
    principal()
