#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Análise de sentimento das notícias, pelo Amália — em modo de ensaio.

Classifica o tom de cada notícia da imprensa NACIONAL em positivo, neutro ou
negativo. As outras origens ficam de fora por decisão metodológica: o
sentimento mede o clima noticioso interno de cada área governativa; a
comunicação social lusófona e internacional serve outra leitura (a da
reputação externa) e será tratada, se for caso disso, como camada própria.

O QUE SE CLASSIFICA. O tom do acontecimento noticiado, não a opinião sobre o
Governo: "incêndio destrói escola" é negativo, "listas de espera diminuem" é
positivo, "ministro reúne com sindicatos" é neutro. É a definição mais
simples e a mais verificável por um leitor humano.

COMO CORRE. De forma incremental: cada execução classifica apenas as
notícias ainda sem avaliação, em lotes de vários títulos por pergunta — uma
geração do modelo classifica um lote inteiro, o que torna o trabalho viável
sem placa gráfica. Um teto por execução impede que o acumulado de dias
anteriores rebente a janela de tempo; o que ficar por fazer fica para a
execução seguinte. As avaliações guardam-se em sentimentos.json, ao lado
das notícias mas fora delas — o arquivo é reescrito a cada recolha e
perderia o campo.

ENSAIO PRIMEIRO. Nenhum agregado, série ou gráfico é produzido por este
módulo. As avaliações aparecem apenas como um ponto discreto junto a cada
notícia no painel, para validação humana. Só depois de validada a precisão
é que se constrói a série por área — números que não se conferiram não se
publicam.

Uso local:   python sentimento_ia.py --local
Por serviço: AMALIA_ENDERECO=... AMALIA_CHAVE=... python sentimento_ia.py
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

VALORES = ("positivo", "neutro", "negativo")

INSTRUCAO = (
    "És um classificador de tom noticioso para a administração pública "
    "portuguesa. Recebes uma lista numerada de notícias (título e, quando "
    "exista, o início do resumo). Para cada uma, classificas o TOM DO "
    "ACONTECIMENTO NOTICIADO:\n"
    "- positivo: facto favorável, melhoria, conquista, boa notícia para o "
    "setor ou para as pessoas.\n"
    "- negativo: problema, crise, acidente, crime, conflito, crítica, "
    "degradação, má notícia.\n"
    "- neutro: anúncio, agenda, nomeação, informação factual sem carga, "
    "processo em curso sem desfecho.\n"
    "Classificas o acontecimento, não a tua opinião nem a qualidade do "
    "texto. Na dúvida entre dois valores, escolhe neutro.\n"
    "RESPONDE APENAS com uma linha por notícia, no formato exato\n"
    "N: valor\n"
    "sem comentários, sem repetir os títulos, sem outra formatação."
)


def agora_lisboa():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Lisbon"))
    except Exception:
        return datetime.now(timezone.utc) + timedelta(hours=1)


def _sem_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def modulos_do_repositorio():
    """Importa os módulos vizinhos: a recolha (origem das fontes) e a
    síntese (carregador do modelo local), para não duplicar código."""
    pasta = os.path.dirname(os.path.abspath(__file__))

    def importar(nome):
        spec = importlib.util.spec_from_file_location(
            nome, os.path.join(pasta, nome + ".py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    return importar("extrair_noticias"), importar("sintese_ia")


def pendentes(noticias, avaliacoes, origem_da_fonte, dias):
    """Notícias nacionais ainda sem avaliação, uma por ligação, recentes
    primeiro. A ligação é a identidade: a mesma notícia marcada em duas
    áreas classifica-se uma só vez."""
    limite = (agora_lisboa() - timedelta(days=dias)).strftime("%Y-%m-%d")
    vistas, fila = set(), []
    for n in sorted(noticias, key=lambda x: x.get("data", ""), reverse=True):
        lig = n.get("ligacao") or (n.get("titulo") or "").lower()
        if not lig or lig in vistas or lig in avaliacoes:
            continue
        vistas.add(lig)
        if (n.get("data") or "")[:10] < limite:
            continue
        if origem_da_fonte(n.get("dominio") or "") != "nacionais":
            continue
        fila.append(n)
    return fila


def compor_lote(lote):
    linhas = []
    for i, n in enumerate(lote, start=1):
        resumo = (n.get("resumo") or "").strip()
        extra = f" — {resumo[:140]}" if resumo else ""
        linhas.append(f"{i}: {n.get('titulo', '').strip()}{extra}")
    return "\n".join(linhas)


def interpretar(texto, tamanho):
    """Lê as linhas «N: valor» da resposta. O que não se entender fica sem
    avaliação — volta à fila na execução seguinte, não se inventa."""
    resultado = {}
    for linha in texto.splitlines():
        m = re.match(r"\s*(\d+)\s*[:).\-]\s*([A-Za-zÀ-ÿ]+)", linha)
        if not m:
            continue
        i = int(m.group(1))
        valor = _sem_acentos(m.group(2)).lower()
        equivalencias = {"positivo": "positivo", "positiva": "positivo",
                         "negativo": "negativo", "negativa": "negativo",
                         "neutro": "neutro", "neutra": "neutro"}
        if 1 <= i <= tamanho and valor in equivalencias:
            resultado[i] = equivalencias[valor]
    return resultado


def perguntar_local(sintese, lote, repo, ficheiro):
    modelo = sintese.carregar_modelo_local(repo, ficheiro)
    resposta = modelo.create_chat_completion(
        messages=[{"role": "system", "content": INSTRUCAO},
                  {"role": "user", "content": compor_lote(lote)}],
        temperature=0.0,
        max_tokens=12 * len(lote) + 40,
    )
    return resposta["choices"][0]["message"]["content"].strip()


def perguntar_servico(endereco, chave, lote, modelo_nome, tempo_limite=90):
    import urllib.request
    pedido = urllib.request.Request(
        endereco,
        data=json.dumps({
            "model": modelo_nome,
            "temperature": 0.0,
            "max_tokens": 12 * len(lote) + 40,
            "messages": [{"role": "system", "content": INSTRUCAO},
                         {"role": "user", "content": compor_lote(lote)}],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {chave}"})
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        corpo = json.load(resposta)
    return corpo["choices"][0]["message"]["content"].strip()


def atualizar_serie(caminho, noticias, avaliacoes, origem_da_fonte, dias):
    """Série diária de sentimento por área, acumulada desde o primeiro dia.

    O sentimentos.json é podado à janela do arquivo; sem esta série, o dia em
    que a validação terminasse seria também o dia zero da história. Aqui, os
    agregados de cada dia (quantas positivas, neutras, negativas e por avaliar,
    por área, comunicação social nacional) ficam registados desde já — pequenos, cerca de
    um quilobyte por dia. Se a validação reprovar o método, apaga-se o ficheiro
    e nada se perdeu; se aprovar, a série já existe desde o início.

    Os dias dentro da janela são recalculados a cada execução (chegam sempre
    avaliações novas de notícias antigas); os dias que já saíram da janela
    ficam como estão — são história fechada.
    """
    limite = (agora_lisboa() - timedelta(days=dias)).strftime("%Y-%m-%d")
    hoje = agora_lisboa().strftime("%Y-%m-%d")

    por_dia = {}
    for n in noticias:
        dia = (n.get("data") or "")[:10]
        area = n.get("area") or ""
        if not dia or not area or dia < limite:
            continue
        if origem_da_fonte(n.get("dominio") or "") != "nacionais":
            continue
        registo = por_dia.setdefault(dia, {}).setdefault(area, {
            "nacionais": 0, "avaliadas": 0,
            "positivo": 0, "neutro": 0, "negativo": 0})
        registo["nacionais"] += 1
        lig = n.get("ligacao") or (n.get("titulo") or "").lower()
        a = avaliacoes.get(lig)
        if a and a.get("s") in VALORES:
            registo["avaliadas"] += 1
            registo[a["s"]] += 1

    serie = {"estado": "ensaio — método por validar", "dias": []}
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as origem:
                anterior = json.load(origem)
            if isinstance(anterior.get("dias"), list):
                serie["estado"] = anterior.get("estado", serie["estado"])
                serie["dias"] = [d for d in anterior["dias"]
                                 if d.get("data", "") < limite]
        except (json.JSONDecodeError, OSError):
            pass

    for dia in sorted(por_dia):
        serie["dias"].append({"data": dia,
                              "fechado": dia < hoje,
                              "areas": por_dia[dia]})
    serie["dias"].sort(key=lambda d: d.get("data", ""))
    serie["atualizado"] = agora_lisboa().strftime("%Y-%m-%d %H:%M")

    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(serie, destino, ensure_ascii=False, indent=1)
    print(f"série de sentimento: {len(serie['dias'])} dias em {caminho}")


def atualizar_serie(caminho, noticias, avaliacoes, origem_da_fonte, dias):
    """Agregados diários por área — o alicerce da futura vista na evolução.

    Acumula desde o primeiro dia, mesmo em modo de ensaio: quando a precisão
    das avaliações for validada, o gráfico nasce com história e não do zero.
    Enquanto isso, nada disto é mostrado. Os dias dentro da janela do arquivo
    recontam-se a cada execução (as avaliações vão chegando); os dias que já
    saíram da janela ficam fechados como estão. Cresce cerca de 2 KB por dia.
    """
    serie = {"atualizado": "", "estado": "ensaio — por validar", "dias": []}
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as origem:
                anterior = json.load(origem)
            if isinstance(anterior.get("dias"), list):
                serie["dias"] = anterior["dias"]
        except (json.JSONDecodeError, OSError):
            pass

    limite = (agora_lisboa() - timedelta(days=dias)).strftime("%Y-%m-%d")
    por_dia = {}
    for n in noticias:
        dia = (n.get("data") or "")[:10]
        area = n.get("area")
        if not dia or not area or dia < limite:
            continue
        if origem_da_fonte(n.get("dominio") or "") != "nacionais":
            continue
        registo = por_dia.setdefault(dia, {}).setdefault(area, {
            "nacionais": 0, "avaliadas": 0,
            "positivo": 0, "neutro": 0, "negativo": 0})
        registo["nacionais"] += 1
        lig = n.get("ligacao") or (n.get("titulo") or "").lower()
        avaliacao = avaliacoes.get(lig)
        if avaliacao and avaliacao.get("s") in VALORES:
            registo["avaliadas"] += 1
            registo[avaliacao["s"]] += 1

    recontados = set(por_dia)
    serie["dias"] = [d for d in serie["dias"] if d.get("data") not in recontados]
    for dia, areas in por_dia.items():
        serie["dias"].append({"data": dia, "areas": areas})
    serie["dias"].sort(key=lambda d: d.get("data", ""))
    serie["atualizado"] = agora_lisboa().strftime("%Y-%m-%d %H:%M")

    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(serie, destino, ensure_ascii=False, indent=1)
    return len(serie["dias"])


def principal():
    ap = argparse.ArgumentParser(
        description="Sentimento das notícias nacionais, pelo Amália.")
    ap.add_argument("--dados", default="arquivo.json")
    ap.add_argument("--saida", default="sentimentos.json")
    ap.add_argument("--teto", type=int, default=300,
                    help="notícias a classificar, no máximo, nesta execução")
    ap.add_argument("--lote", type=int, default=20,
                    help="notícias por pergunta ao modelo")
    ap.add_argument("--dias", type=int, default=8,
                    help="idade máxima das notícias a classificar")
    ap.add_argument("--serie", default="sentimento-serie.json",
                    help="série diária de agregados por área (vazio desliga)")
    ap.add_argument("--local", action="store_true",
                    help="correr o Amália neste computador")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--ficheiro", default=None)
    ap.add_argument("--endereco", default=os.environ.get("AMALIA_ENDERECO", ""))
    ap.add_argument("--serie", default="sentimento-serie.json",
                    help="agregados diários por área (alicerce da evolução)")
    args = ap.parse_args()

    recolha, sintese = modulos_do_repositorio()
    repo = args.repo or sintese.REPO_GGUF
    ficheiro = args.ficheiro or sintese.FICHEIRO_GGUF

    chave = os.environ.get("AMALIA_CHAVE", "")
    if not args.local and (not args.endereco or not chave):
        print("Sem modo local nem ponto de acesso configurado. Nada a fazer.")
        return

    if not os.path.exists(args.dados):
        sys.exit(f"Ficheiro de dados não encontrado: {args.dados}")
    with open(args.dados, encoding="utf-8") as origem:
        noticias = json.load(origem).get("noticias", [])

    anterior = {}
    if os.path.exists(args.saida):
        try:
            with open(args.saida, encoding="utf-8") as origem:
                anterior = json.load(origem)
        except (json.JSONDecodeError, OSError):
            anterior = {}
    avaliacoes = anterior.get("avaliacoes", {})

    # Poda: avaliações de notícias já fora da janela não servem para nada
    limite = (agora_lisboa() - timedelta(days=args.dias + 2)).strftime("%Y-%m-%d")
    avaliacoes = {lig: v for lig, v in avaliacoes.items()
                  if (v.get("d") or "9999") >= limite}

    fila = pendentes(noticias, avaliacoes, recolha.origem_da_fonte, args.dias)
    por_fazer = len(fila)
    fila = fila[:args.teto]
    print(f"sentimento: {por_fazer} notícias nacionais por avaliar; "
          f"{len(fila)} nesta execução, em lotes de {args.lote}")

    novas, falhas = 0, 0
    for inicio in range(0, len(fila), args.lote):
        lote = fila[inicio:inicio + args.lote]
        try:
            if args.local:
                resposta = perguntar_local(sintese, lote, repo, ficheiro)
            else:
                resposta = perguntar_servico(args.endereco, chave, lote,
                                             sintese.MODELO)
        except Exception as erro:                              # noqa: BLE001
            print(f"  lote {inicio // args.lote + 1}: falhou "
                  f"({type(erro).__name__}: {erro}) — fica para a próxima")
            falhas += 1
            continue
        lidas = interpretar(resposta, len(lote))
        for i, n in enumerate(lote, start=1):
            if i not in lidas:
                continue
            lig = n.get("ligacao") or (n.get("titulo") or "").lower()
            avaliacoes[lig] = {"s": lidas[i], "d": (n.get("data") or "")[:10]}
            novas += 1
        print(f"  lote {inicio // args.lote + 1}: "
              f"{len(lidas)}/{len(lote)} avaliadas")

    agora = agora_lisboa()
    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump({
            "gerado": agora.strftime("%Y-%m-%d %H:%M"),
            "modelo": sintese.MODELO,
            "estado": "em validação — avaliações automáticas, leitura humana em curso",
            "criterio": ("Tom do acontecimento noticiado (positivo, neutro, "
                         "negativo), comunicação social nacional apenas, uma avaliação "
                         "por notícia."),
            "avaliacoes": avaliacoes,
        }, destino, ensure_ascii=False, indent=1)

    n_dias = atualizar_serie(args.serie, noticias, avaliacoes,
                             recolha.origem_da_fonte, args.dias)
    print(f"sentimento: {novas} novas avaliações, {falhas} lotes falhados, "
          f"{len(avaliacoes)} no total em {args.saida}; "
          f"série diária com {n_dias} dias em {args.serie}")

    if args.serie:
        atualizar_serie(args.serie, noticias, avaliacoes,
                        recolha.origem_da_fonte, args.dias)


if __name__ == "__main__":
    principal()
