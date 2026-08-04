#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Notícias — análise longitudinal
Secretaria-Geral do Governo · Unidade de Pesquisa e Estatísticas

Lê a memória de longo prazo do radar e devolve-a em quadros prontos a analisar.
Serve de ponto de partida para relatórios, gráficos ou um painel estatístico.

DOIS FICHEIROS, DUAS PROFUNDIDADES

  historico.json            Agregados por dia e por área. Leve, cobre tudo desde
                            o início. É a base de qualquer série temporal.

  meses/AAAA-MM.jsonl.gz    As notícias uma a uma, com título, resumo, publicação
                            e palavras-chave. Pesado, mas é o que permite voltar
                            atrás e ler o que foi noticiado.

Os outros dois ficheiros do repositório — arquivo.json e corpus.json — guardam
apenas sete dias e servem o painel. Não têm memória e não entram aqui.

UTILIZAÇÃO

    pip install pandas requests
    python analise_longitudinal.py                    # do repositório publicado
    python analise_longitudinal.py --local .          # de uma cópia local
    python analise_longitudinal.py --por mes          # agregado mensal
    python analise_longitudinal.py --saida serie.xlsx # gravar em Excel
"""

import argparse
import gzip
import io
import json
import os
import sys
from datetime import datetime

REPOSITORIO = "https://raw.githubusercontent.com/celine-mestre/radar-noticias/main"


# ── LEITURA ──────────────────────────────────────────────────────────────────

def ler_json(origem, caminho):
    """Lê um JSON, do repositório publicado ou de uma pasta local."""
    if origem.startswith("http"):
        import requests
        r = requests.get(f"{origem}/{caminho}", timeout=30)
        r.raise_for_status()
        return r.json()
    with open(os.path.join(origem, caminho), encoding="utf-8") as f:
        return json.load(f)


def ler_mes(origem, mes):
    """Lê um arquivo mensal comprimido. Devolve a lista de notícias."""
    caminho = f"meses/{mes}.jsonl.gz"
    if origem.startswith("http"):
        import requests
        r = requests.get(f"{origem}/{caminho}", timeout=60)
        r.raise_for_status()
        bruto = io.BytesIO(r.content)
    else:
        bruto = open(os.path.join(origem, caminho), "rb")

    with gzip.open(bruto, "rt", encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


# ── QUADROS ──────────────────────────────────────────────────────────────────

def serie_por_area(historico):
    """Uma linha por dia e por área.

    Colunas: data, area, noticias, publicadas, fontes, nacionais, lusofonas,
    internacionais. É o quadro de base para tendências.
    """
    import pandas as pd

    linhas = []
    for dia in historico.get("dias", []):
        data = dia.get("data")
        for area, v in (dia.get("areas") or {}).items():
            origens = v.get("origens") or {}
            linhas.append({
                "data": data,
                "area": area,
                "noticias": v.get("noticias", 0),
                "publicadas": v.get("novas", 0),
                "fontes": v.get("fontes", 0),
                "nacionais": origens.get("nacionais", 0),
                "lusofonas": origens.get("lusofonas", 0),
                "internacionais": origens.get("internacionais", 0),
            })

    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values(["data", "area"]).reset_index(drop=True)


def serie_por_palavra(historico):
    """Uma linha por dia, área e palavra-chave. Mostra que expressões rendem."""
    import pandas as pd

    linhas = []
    for dia in historico.get("dias", []):
        for area, v in (dia.get("areas") or {}).items():
            for palavra, quantas in (v.get("palavras") or {}).items():
                linhas.append({"data": dia.get("data"), "area": area,
                               "palavra": palavra, "noticias": quantas})

    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values(["data", "area", "noticias"],
                          ascending=[True, True, False]).reset_index(drop=True)


def agregar(df, por="dia"):
    """Agrega a série por dia, semana, mês, trimestre ou ano.

    A soma é legítima porque todas as recolhas usam o mesmo método e a mesma
    janela: o que se compara é sempre o mesmo tipo de medida.
    """
    import pandas as pd

    if df.empty:
        return df
    regra = {"dia": "D", "semana": "W", "mes": "ME",
             "trimestre": "QE", "ano": "YE"}.get(por)
    if not regra:
        sys.exit(f"Período desconhecido: {por}")

    numericas = [c for c in df.columns if c not in ("data", "area", "palavra")]
    chaves = ["area"] + (["palavra"] if "palavra" in df.columns else [])
    return (df.set_index("data")
              .groupby(chaves)[numericas]
              .resample(regra).sum()
              .reset_index())


def quadro_de_titulos(noticias):
    """Uma linha por notícia, a partir de um arquivo mensal."""
    import pandas as pd

    df = pd.DataFrame(noticias)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["dia"] = df["data"].dt.date
    df["publicacao"] = df.get("fonte", "")
    return df


# ── APRESENTAÇÃO ─────────────────────────────────────────────────────────────

def resumir(df, por):
    """Umas quantas leituras imediatas, para confirmar que os dados servem."""
    import pandas as pd

    if df.empty:
        print("Sem dados. O historico.json ainda não tem dias registados.")
        return

    print(f"\n{len(df)} linhas · {df['area'].nunique()} áreas · "
          f"de {df['data'].min():%d/%m/%Y} a {df['data'].max():%d/%m/%Y}\n")

    total = df.groupby("area")["noticias"].sum().sort_values(ascending=False)
    print("VOLUME TOTAL POR ÁREA")
    for area, n in total.items():
        print(f"  {area:46} {int(n):6}")

    if {"nacionais", "lusofonas", "internacionais"} <= set(df.columns):
        origens = df[["nacionais", "lusofonas", "internacionais"]].sum()
        soma = origens.sum() or 1
        print("\nREPARTIÇÃO POR ORIGEM")
        for nome, n in origens.items():
            print(f"  {nome:16} {int(n):6}  {n / soma * 100:5.1f}%")

    if por != "dia":
        print(f"\nAGREGADO POR {por.upper()} — primeiras linhas")
        print(agregar(df, por).head(12).to_string(index=False))


def principal():
    ap = argparse.ArgumentParser(description="Análise longitudinal do Radar de Notícias.")
    ap.add_argument("--local", default=None,
                    help="pasta com uma cópia do repositório (em vez do publicado)")
    ap.add_argument("--por", default="dia",
                    choices=["dia", "semana", "mes", "trimestre", "ano"])
    ap.add_argument("--palavras", action="store_true",
                    help="série por palavra-chave em vez de por área")
    ap.add_argument("--mes", default=None,
                    help="ler um arquivo mensal de notícias, ex.: 2026-08")
    ap.add_argument("--saida", default=None,
                    help="gravar o quadro num ficheiro .xlsx ou .csv")
    args = ap.parse_args()

    try:
        import pandas  # noqa: F401
    except ImportError:
        sys.exit("Falta o pandas. Instale com:  pip install pandas requests")

    origem = args.local or REPOSITORIO
    print(f"A ler de: {origem}")

    if args.mes:
        noticias = ler_mes(origem, args.mes)
        df = quadro_de_titulos(noticias)
        print(f"\n{len(df)} notícias em {args.mes}")
        if not df.empty:
            print("\nPOR ÁREA")
            print(df["area"].value_counts().to_string())
            print("\nPUBLICAÇÕES MAIS PRESENTES")
            print(df["publicacao"].value_counts().head(15).to_string())
    else:
        historico = ler_json(origem, "historico.json")
        df = serie_por_palavra(historico) if args.palavras else serie_por_area(historico)
        resumir(df, args.por) if not args.palavras else print(df.head(20).to_string(index=False))
        if args.por != "dia":
            df = agregar(df, args.por)

    if args.saida and not df.empty:
        if args.saida.endswith(".csv"):
            df.to_csv(args.saida, index=False, encoding="utf-8-sig")
        else:
            df.to_excel(args.saida, index=False)
        print(f"\nGravado em {args.saida}")


if __name__ == "__main__":
    principal()
