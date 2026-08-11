#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Passo retroativo, de execução única: as marcações novas — a área
Primeiro-Ministro e as expressões de cargo — aplicadas aos dados já
recolhidos.

A marcação por áreas acontece no momento da recolha. Uma área criada hoje
nasceria vazia, e uma expressão acrescentada hoje só marcaria daqui para a
frente. Mas o corpus.json guarda TUDO o que os feeds trouxeram nos últimos
sete dias, marcado ou não: este passo primeiro REVALIDA todas as marcações
existentes sob as regras atuais (retirando os pares que só existiam por
expressões entretanto removidas, como «empresas»), depois reclassifica o
corpus por inteiro e injeta o que faltava onde a recolha o teria posto —

  1. arquivo.json          — as notícias do PM entram no arquivo de 7 dias;
  2. noticias.json         — as que pertencem ao retrato da última recolha;
  3. meses/AAAA-MM.jsonl.gz — o arquivo permanente recebe as mesmas linhas,
                              para a linha de base dos alertas as conhecer;
  4. historico.json        — a série diária é reconstruída do arquivo, como
                              em cada recolha, e a área nasce com história;
  5. alertas.json          — reavaliam-se os dias desde --alertas-desde
                              (fim de dia, 23h59) e, por fim, o dia de hoje.
                              Sem 7 dias comparáveis desde o início da série
                              (4 de agosto), nenhum dia dispara: os alertas
                              retroativos só nascem quando a base os sustenta.

Para trás da janela do corpus não há recuperação possível: os feeds já não
expõem o que passou. O arquivo permanente só terá o Primeiro-Ministro a
partir da janela reclassificada — fica dito, em nome da rastreabilidade.

Correr uma única vez, depois de publicada a versão com a área nova:
    python retroativo_pm.py [--alertas-desde 2026-08-07]

Correr segunda vez não duplica nada: tudo é desduplicado pela ligação.
"""

import argparse
import glob
import gzip
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta



def modulo_recolha():
    """Importa extrair_noticias.py do próprio repositório."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "extrair_noticias", os.path.join(pasta, "extrair_noticias.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def chave(n):
    """Identidade de uma notícia: a ligação; faltando, o título."""
    return n.get("ligacao") or (n.get("titulo") or "").lower()


def casa_com_a_area(mod, registo, areas_por_nome):
    """Verifica se um par área-notícia continua válido sob as regras atuais.

    É o inverso da marcação: quando uma expressão é retirada por dar ruído
    (caso de «empresas»), os pares que só existiam por ela têm de sair do
    arquivo e do depósito mensal — deixá-los ficar contaminaria as séries e
    as linhas de base dos alertas, que passariam a comparar dias marcados
    por regras diferentes. Uma área desconhecida mantém-se por prudência.
    """
    area = areas_por_nome.get(registo.get("area"))
    if area is None:
        return True
    _, _, _, palavras, excluir = area
    if not mod.escreve_em_portugues(registo.get("dominio") or ""):
        return False
    original = f"{registo.get('titulo', '')} {registo.get('resumo', '')}"
    texto = mod._sem_acentos(original).lower()
    if any(mod.contem_expressao(texto, e, original) for e in excluir):
        return False
    return any(mod.contem_expressao(texto, p, original) for p in palavras)


def revalidar_json(caminho, mod, areas_por_nome):
    """Remove de um ficheiro {noticias: […]} os pares que já não casam."""
    with open(caminho, encoding="utf-8") as origem:
        dados = json.load(origem)
    antes = len(dados["noticias"])
    dados["noticias"] = [n for n in dados["noticias"]
                         if casa_com_a_area(mod, n, areas_por_nome)]
    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(dados, destino, ensure_ascii=False, indent=1)
    return antes - len(dados["noticias"])


def revalidar_mensal(pasta, mod, areas_por_nome):
    """O mesmo, mês a mês, no depósito permanente."""
    retiradas = 0
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        linhas, fora = [], 0
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            for linha in origem:
                try:
                    r = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if casa_com_a_area(mod, r, areas_por_nome):
                    linhas.append(r)
                else:
                    fora += 1
        if fora:
            with gzip.open(caminho, "wt", encoding="utf-8") as destino:
                for r in linhas:
                    destino.write(json.dumps(r, ensure_ascii=False) + "\n")
        retiradas += fora
    return retiradas


def reclassificar(mod, corpus):
    """Reaplica TODAS as áreas a todo o corpus, como a recolha faria: só
    fontes que escrevem em português, com as exclusões primeiro.

    Devolve todos os pares área-notícia; o injetar seguinte descarta os que
    o arquivo já tem, pelo que só as marcações novas — de uma área criada ou
    de expressões acrescentadas — acabam por entrar."""
    achadas = []
    for n in corpus:
        if not mod.escreve_em_portugues(n.get("dominio") or ""):
            continue
        original = f"{n.get('titulo', '')} {n.get('resumo', '')}"
        texto = mod._sem_acentos(original).lower()
        for _, nome, grupo, palavras, excluir in mod.AREAS:
            if any(mod.contem_expressao(texto, e, original) for e in excluir):
                continue
            casadas = [p for p in palavras
                       if mod.contem_expressao(texto, p, original)]
            if not casadas:
                continue
            achadas.append({"area": nome, "grupo": mod.GRUPOS[grupo],
                            "data": n.get("data", ""), "fonte": n.get("fonte", ""),
                            "dominio": n.get("dominio", ""),
                            "titulo": n.get("titulo", ""),
                            "resumo": n.get("resumo", ""),
                            "ligacao": n.get("ligacao", ""),
                            "imagem": n.get("imagem", ""),
                            "palavras": casadas})
    return achadas


def injetar_json(caminho, novas):
    """Acrescenta a um ficheiro {noticias: […]} as linhas da área nova que ele
    ainda não tem, mantendo a ordenação por data descendente."""
    with open(caminho, encoding="utf-8") as origem:
        dados = json.load(origem)
    existentes = {(n.get("area"), chave(n)) for n in dados["noticias"]}
    entradas = [n for n in novas
                if (n["area"], chave(n)) not in existentes]
    dados["noticias"].extend(entradas)
    dados["noticias"].sort(key=lambda n: n.get("data", ""), reverse=True)
    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(dados, destino, ensure_ascii=False, indent=1)
    return len(entradas)


def injetar_no_snapshot(caminho, novas):
    """No retrato do dia só entram as notícias que ele próprio já conhece por
    outra área — o retrato é o que a última recolha leu, nem mais nem menos."""
    with open(caminho, encoding="utf-8") as origem:
        dados = json.load(origem)
    conhecidas = {chave(n) for n in dados["noticias"]}
    return injetar_json(caminho, [n for n in novas if chave(n) in conhecidas])


def injetar_mensal(pasta, novas):
    """Acrescenta as linhas ao mês respetivo do arquivo permanente."""
    campos = ("area", "grupo", "data", "fonte", "dominio",
              "titulo", "resumo", "ligacao", "palavras")
    por_mes = {}
    for n in novas:
        mes = (n.get("data") or "")[:7]
        if mes:
            por_mes.setdefault(mes, []).append(
                {c: n.get(c, [] if c == "palavras" else "") for c in campos})

    acrescentadas = 0
    for mes, linhas in sorted(por_mes.items()):
        caminho = os.path.join(pasta, f"{mes}.jsonl.gz")
        existentes = set()
        if os.path.exists(caminho):
            with gzip.open(caminho, "rt", encoding="utf-8") as origem:
                for linha in origem:
                    try:
                        r = json.loads(linha)
                    except json.JSONDecodeError:
                        continue
                    existentes.add((r.get("area"), chave(r)))
        entradas = [l for l in linhas
                    if (l["area"], chave(l)) not in existentes]
        if not entradas:
            continue
        with gzip.open(caminho, "at", encoding="utf-8") as destino:
            for l in entradas:
                destino.write(json.dumps(l, ensure_ascii=False) + "\n")
        acrescentadas += len(entradas)
    return acrescentadas


def reavaliar_alertas(desde):
    """Reavalia os alertas dia a dia (fim de dia) e termina no dia de hoje.

    Cada chamada substitui no histórico apenas o dia avaliado; a última deixa
    o ficheiro no estado corrente. Antes de --alertas-desde a linha de base
    era de outro método de recolha e os alertas não seriam comparáveis.
    """
    pasta = os.path.dirname(os.path.abspath(__file__))
    ontem = datetime.now().date() - timedelta(days=1)
    dia = datetime.strptime(desde, "%Y-%m-%d").date()
    while dia <= ontem:
        subprocess.run([sys.executable, os.path.join(pasta, "alertas.py"),
                        "--data", dia.isoformat(), "--corte", "23:59"],
                       check=True)
        dia += timedelta(days=1)
    subprocess.run([sys.executable, os.path.join(pasta, "alertas.py")],
                   check=True)


def principal():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", default="corpus.json")
    parser.add_argument("--arquivo", default="arquivo.json")
    parser.add_argument("--noticias", default="noticias.json")
    parser.add_argument("--historico", default="historico.json")
    parser.add_argument("--mensal", default="meses")
    parser.add_argument("--alertas-desde", default="2026-08-04",
                        help="primeiro dia a reavaliar nos alertas")
    args = parser.parse_args()

    mod = modulo_recolha()
    with open(args.corpus, encoding="utf-8") as origem:
        corpus = json.load(origem).get("noticias", [])

    areas_por_nome = {a[1]: a for a in mod.AREAS}
    print("retroativo: a revalidar as marcações existentes sob as regras atuais…")
    print(f"  arquivo:  -{revalidar_json(args.arquivo, mod, areas_por_nome)} pares retirados")
    print(f"  retrato:  -{revalidar_json(args.noticias, mod, areas_por_nome)} pares retirados")
    print(f"  mensal:   -{revalidar_mensal(args.mensal, mod, areas_por_nome)} linhas retiradas")

    achadas = reclassificar(mod, corpus)
    dias = sorted({(n.get("data") or "")[:10] for n in achadas if n.get("data")})
    print(f"retroativo: {len(achadas)} pares área-notícia no corpus "
          f"({dias[0] if dias else '—'} a {dias[-1] if dias else '—'})")

    print(f"  arquivo:  +{injetar_json(args.arquivo, achadas)} notícias")
    print(f"  retrato:  +{injetar_no_snapshot(args.noticias, achadas)} notícias")
    print(f"  mensal:   +{injetar_mensal(args.mensal, achadas)} linhas")

    # A série diária reconstrói-se do arquivo, exatamente como em cada recolha.
    mod.atualizar_historico(args.historico, [], "dia completo",
                            None, arquivo=args.arquivo)

    reavaliar_alertas(args.alertas_desde)
    print("retroativo: concluído")


if __name__ == "__main__":
    principal()
