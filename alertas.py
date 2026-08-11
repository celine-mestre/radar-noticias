#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alertas de «tempestade política» e ranking do momentum noticioso.

Depois de cada recolha, compara o volume de notícias de hoje, por área
governativa, com o comportamento habitual dessa mesma área nos últimos dias.
Um crescimento anormal — um disparar de notícias — é sinal de que algo se
passa no setor, e o radar assinala-o.

O MÉTODO, em três regras simples e documentáveis:

1. Comparação à mesma hora. O dia de hoje está sempre incompleto quando a
   recolha corre (às 09h, às 15h…). Comparar o parcial de hoje com dias
   inteiros subestimaria sempre o presente. Por isso a linha de base conta,
   em cada dia anterior, apenas as notícias publicadas ATÉ À MESMA HORA a
   que a avaliação corre. Compara-se manhã com manhãs, tarde com tardes.

2. Linha de base robusta. Para cada área, toma-se a mediana e o desvio
   robusto (1,4826 × desvio absoluto mediano) das contagens dos últimos
   28 dias com recolha. A mediana e o MAD não se deixam arrastar por um ou
   dois dias atípicos, ao contrário da média e do desvio-padrão.

3. Limiar de tempestade. Há alerta quando a contagem de hoje excede
   mediana + máx(2 × desvio robusto, SUBIDA_MINIMA) e, em simultâneo,
   atinge o piso absoluto — para que uma área de volume residual (passar
   de 2 para 7 notícias) não dispare tempestades sem significado. Enquanto
   a série tiver menos de MINIMO_DIAS dias, não se emitem alertas: uma
   linha de base curta não é linha de base.

Além do alerta, calcula-se sempre o MOMENTUM: as cinco áreas com maior
excesso de notícias face à sua própria mediana, com ou sem tempestade.

Tudo fica em alertas.json, incluindo um histórico acumulado de alertas por
área e por dia — a matéria-prima para a análise sazonal (em que meses, em
que setores, com que frequência rebentam as tempestades).

Uso:  python alertas.py [--mensal meses] [--saida alertas.json]
                        [--dias 28] [--data AAAA-MM-DD] [--corte HH:MM]
"""

import argparse
import glob
import gzip
import json
import os
import statistics
from datetime import datetime, timedelta, timezone

# ── Parâmetros do método ─────────────────────────────────────────────────────
DIAS_BASE = 28        # profundidade máxima da linha de base, em dias
MINIMO_DIAS = 7       # dias mínimos de série para se emitirem alertas
SUBIDA_MINIMA = 8     # excesso mínimo sobre a mediana, em notícias
PISO_ABSOLUTO = 12    # contagem mínima do dia para haver tempestade
FATOR_DESVIO = 2.0    # nº de desvios robustos acima da mediana
TOPO_MOMENTUM = 5     # áreas no ranking do momentum

# O método de recolha atual (leitura direta dos feeds) entrou em funcionamento
# a 3 de agosto de 2026 e estabilizou no dia seguinte. Os dias anteriores são
# de outro método, com volumes incomparáveis: misturá-los na linha de base
# infla o desvio e cala tempestades verdadeiras (ou inventa-as). A série
# comparável começa aqui — a mesma convenção do painel de evolução.
INICIO_SERIE = "2026-08-04"


def agora_lisboa():
    """Hora de Lisboa sem depender de bibliotecas externas (UTC+1 no verão)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Lisbon"))
    except Exception:
        return datetime.now(timezone.utc) + timedelta(hours=1)


def ler_arquivo_mensal(pasta):
    """Lê todos os meses/AAAA-MM.jsonl.gz e devolve as notícias sem repetidos.

    A chave de desduplicação é a ligação; faltando, título + domínio + data.
    """
    vistas, linhas = set(), []
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        try:
            with gzip.open(caminho, "rt", encoding="utf-8") as origem:
                for linha in origem:
                    try:
                        registo = json.loads(linha)
                    except json.JSONDecodeError:
                        continue
                    chave = registo.get("ligacao") or (
                        registo.get("titulo", ""), registo.get("dominio", ""),
                        registo.get("data", ""))
                    if chave in vistas:
                        continue
                    vistas.add(chave)
                    linhas.append(registo)
        except OSError:
            continue
    return linhas


def contagens_ate_ao_corte(linhas, corte):
    """{dia: {área: nº de notícias publicadas até à hora de corte}}.

    Uma notícia sem hora conta sempre: na dúvida, inclui-se.
    """
    dias = {}
    for r in linhas:
        data = (r.get("data") or "").strip()
        if len(data) < 10:
            continue
        dia, hora = data[:10], data[11:16]
        if hora and hora > corte:
            continue
        area = r.get("area") or ""
        if not area:
            continue
        dias.setdefault(dia, {})
        dias[dia][area] = dias[dia].get(area, 0) + 1
    return dias


FRACAO_DIA_VALIDO = 0.25  # total mínimo de um dia, como fração da mediana


def dias_validos(dias, anteriores):
    """Afasta da linha de base os dias de recolha atipicamente incompleta.

    Uma falha de feeds ou uma mudança de método deixa dias com uma fração do
    volume habitual; mantê-los na base rebaixaria as medianas e faria soar
    tempestades em dias perfeitamente normais. Um dia só conta para a base
    se o seu total (todas as áreas) atingir ao menos um quarto da mediana
    dos totais dos dias considerados.
    """
    totais = {d: sum(dias[d].values()) for d in anteriores}
    if not totais:
        return anteriores
    mediana_total = statistics.median(totais.values())
    minimo = FRACAO_DIA_VALIDO * mediana_total
    return [d for d in anteriores if totais[d] >= minimo]


def avaliar(dias, hoje, profundidade, inicio=INICIO_SERIE):
    """Compara o dia de hoje com a linha de base de cada área."""
    anteriores = sorted(d for d in dias if inicio <= d < hoje)[-profundidade:]
    anteriores = dias_validos(dias, anteriores)
    de_hoje = dias.get(hoje, {})
    areas = set(de_hoje) | {a for d in anteriores for a in dias[d]}

    tempestades, momentum = [], []
    for area in sorted(areas):
        # A linha de base de uma área começa no primeiro dia em que a área
        # existe nos dados. Sem isto, uma área recém-criada arrastava uma
        # cauda de zeros estruturais — dias em que não podia ter contagem —,
        # a mediana caía para zero e qualquer dia normal soava a tempestade.
        primeiro = min((d for d in dias if area in dias[d]), default=None)
        proprios = [d for d in anteriores
                    if primeiro is not None and d >= primeiro]
        base = [dias[d].get(area, 0) for d in proprios]
        n_hoje = de_hoje.get(area, 0)
        if len(base) < MINIMO_DIAS:
            continue                     # série ainda curta: sem juízo

        mediana = statistics.median(base)
        mad = statistics.median(abs(x - mediana) for x in base)
        desvio = 1.4826 * mad
        limiar = mediana + max(FATOR_DESVIO * desvio, SUBIDA_MINIMA)
        excesso = n_hoje - mediana

        registo = {
            "area": area,
            "hoje": n_hoje,
            "mediana": round(mediana, 1),
            "limiar": round(limiar, 1),
            "excesso": round(excesso, 1),
            "variacao_pct": round(100 * excesso / mediana) if mediana else None,
            "dias_base": len(base),
        }
        registo["tempestade"] = bool(
            n_hoje >= limiar and n_hoje >= PISO_ABSOLUTO)
        if registo["tempestade"]:
            tempestades.append(registo)
        if excesso > 0:
            momentum.append(registo)

    tempestades.sort(key=lambda r: -r["excesso"])
    momentum.sort(key=lambda r: (-r["excesso"], -r["hoje"]))
    return tempestades, momentum[:TOPO_MOMENTUM], len(anteriores)


def atualizar_historico(anterior, hoje, tempestades):
    """Histórico acumulado de alertas: um registo por área e por dia.

    Os registos de hoje substituem os de recolhas anteriores do mesmo dia —
    vale a última avaliação, que é a mais completa. Os dias passados nunca
    se apagam: são a série para a análise sazonal.
    """
    historico = [r for r in (anterior or []) if r.get("data") != hoje]
    for t in tempestades:
        historico.append({"data": hoje, "area": t["area"], "hoje": t["hoje"],
                          "mediana": t["mediana"], "limiar": t["limiar"]})
    historico.sort(key=lambda r: (r.get("data", ""), r.get("area", "")))
    return historico


def principal():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mensal", default="meses",
                        help="pasta do arquivo mensal (AAAA-MM.jsonl.gz)")
    parser.add_argument("--saida", default="alertas.json",
                        help="ficheiro de alertas a escrever")
    parser.add_argument("--dias", type=int, default=DIAS_BASE,
                        help="profundidade da linha de base, em dias")
    parser.add_argument("--data", default=None,
                        help="avaliar outro dia (AAAA-MM-DD), para ensaio")
    parser.add_argument("--corte", default=None,
                        help="hora de corte HH:MM, para ensaio")
    parser.add_argument("--inicio", default=INICIO_SERIE,
                        help="primeiro dia comparável da série (método atual)")
    args = parser.parse_args()

    agora = agora_lisboa()
    hoje = args.data or agora.strftime("%Y-%m-%d")
    corte = args.corte or agora.strftime("%H:%M")

    linhas = ler_arquivo_mensal(args.mensal)
    if not linhas:
        print(f"alertas: sem arquivo mensal em {args.mensal}/ — nada a avaliar")
        return

    dias = contagens_ate_ao_corte(linhas, corte)
    tempestades, momentum, n_base = avaliar(dias, hoje, args.dias, args.inicio)

    anterior = {}
    if os.path.exists(args.saida):
        try:
            with open(args.saida, encoding="utf-8") as origem:
                anterior = json.load(origem)
        except (json.JSONDecodeError, OSError):
            anterior = {}

    resultado = {
        "atualizado": agora.strftime("%Y-%m-%d %H:%M"),
        "dia": hoje,
        "corte": corte,
        "dias_base": n_base,
        "regra": (f"Tempestade quando a contagem do dia, até às {corte}, excede "
                  f"a mediana dos últimos {args.dias} dias à mesma hora em "
                  f"máx({FATOR_DESVIO:g} desvios robustos, {SUBIDA_MINIMA} notícias) "
                  f"e atinge pelo menos {PISO_ABSOLUTO} notícias; "
                  f"sem alertas com menos de {MINIMO_DIAS} dias de série, "
                  f"contada desde {args.inicio} (método de recolha atual)."),
        "tempestades": tempestades,
        "momentum": momentum,
        "historico": atualizar_historico(anterior.get("historico"),
                                         hoje, tempestades),
    }

    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump(resultado, destino, ensure_ascii=False, indent=1)

    nomes = ", ".join(t["area"] for t in tempestades) or "nenhuma"
    print(f"alertas: {n_base} dias de base até às {corte} · "
          f"tempestades: {nomes} · momentum: "
          + (", ".join(f"{m['area']} (+{m['excesso']:g})" for m in momentum)
             or "sem áreas acima da mediana"))


if __name__ == "__main__":
    principal()
