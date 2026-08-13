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
import glob
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
    "N=valor\n"
    "(exemplo: «3=negativo»), sem repetir os títulos, sem comentários, "
    "sem outra formatação."
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


def carregar_do_mensal(pasta, datas):
    """Notícias de dias já fora do arquivo corrente, lidas do depósito mensal.

    O arquivo.json guarda sete dias: passado esse prazo, uma notícia que nunca
    chegou a ser avaliada deixa de ser alcançável — e o dia fica para sempre
    com cobertura parcial. O depósito mensal guarda tudo, e é daqui que se
    repescam esses dias. Serve para fechar buracos deixados por avarias, não
    para trabalho corrente.
    """
    import gzip
    registos, vistos = [], set()
    meses = {d[:7] for d in datas}
    for mes in sorted(meses):
        caminho = os.path.join(pasta, f"{mes}.jsonl.gz")
        if not os.path.exists(caminho):
            continue
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            for linha in origem:
                try:
                    r = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if (r.get("data") or "")[:10] not in datas:
                    continue
                if not (r.get("area") or "").strip():
                    continue
                chave = (r.get("ligacao") or (r.get("titulo") or "").lower(),
                         r.get("area"))
                if chave in vistos:
                    continue
                vistos.add(chave)
                registos.append(r)
    return registos


def caminho_sentimento_mensal(pasta, mes):
    return os.path.join(pasta, f"{mes}.jsonl.gz")


def carregar_sentimento_arquivado(pasta):
    """Todas as avaliações já feitas, de sempre, do arquivo permanente.

    O sentimentos.json é o ficheiro de trabalho e é podado — guarda apenas a
    janela recente, para não crescer sem fim. Mas uma avaliação é um facto que
    não muda: a notícia foi classificada uma vez e não precisa de o ser outra.
    Por isso as avaliações são também arquivadas por mês, à maneira do arquivo
    das notícias. É este arquivo que permite, no futuro, alargar a janela do
    painel ou repescar meses inteiros sem mandar o Amália trabalhar de novo.
    """
    import gzip
    arquivadas = {}
    if not os.path.isdir(pasta):
        return arquivadas
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        try:
            with gzip.open(caminho, "rt", encoding="utf-8") as origem:
                for linha in origem:
                    try:
                        r = json.loads(linha)
                    except json.JSONDecodeError:
                        continue
                    lig = r.get("lig")
                    if lig and r.get("s") in VALORES:
                        arquivadas[lig] = {"s": r["s"], "d": r.get("d", "")}
        except OSError:
            continue
    return arquivadas


def arquivar_sentimento(pasta, avaliacoes, ja_arquivadas):
    """Acrescenta ao arquivo permanente as avaliações que ainda lá não estão.

    Escreve por mês, em acréscimo — nunca reescreve o que já lá está, para o
    ficheiro não mudar por inteiro a cada execução.
    """
    import gzip
    novas = {lig: v for lig, v in avaliacoes.items() if lig not in ja_arquivadas}
    if not novas:
        return 0
    os.makedirs(pasta, exist_ok=True)
    por_mes = {}
    for lig, v in novas.items():
        mes = (v.get("d") or "")[:7]
        if len(mes) != 7:
            continue
        por_mes.setdefault(mes, []).append(
            {"lig": lig, "s": v["s"], "d": v.get("d", "")})
    total = 0
    for mes, registos in sorted(por_mes.items()):
        with gzip.open(caminho_sentimento_mensal(pasta, mes), "at",
                       encoding="utf-8") as destino:
            for r in registos:
                destino.write(json.dumps(r, ensure_ascii=False) + "\n")
        total += len(registos)
    print(f"arquivo de sentimento: +{total} avaliações guardadas para sempre")
    return total


def pendentes(noticias, avaliacoes, origem_da_fonte, dias, datas_extra=frozenset()):
    """Notícias nacionais ainda sem avaliação, uma por ligação, recentes
    primeiro. A ligação é a identidade: a mesma notícia marcada em duas
    áreas classifica-se uma só vez. As datas em `datas_extra` entram mesmo
    estando fora da janela — é por aí que se repescam dias antigos."""
    limite = (agora_lisboa() - timedelta(days=dias)).strftime("%Y-%m-%d")
    vistas, fila = set(), []
    for n in sorted(noticias, key=lambda x: x.get("data", ""), reverse=True):
        lig = n.get("ligacao") or (n.get("titulo") or "").lower()
        if not lig or lig in vistas or lig in avaliacoes:
            continue
        vistas.add(lig)
        dia = (n.get("data") or "")[:10]
        if dia < limite and dia not in datas_extra:
            continue
        if origem_da_fonte(n.get("dominio") or "") != "nacionais":
            continue
        fila.append(n)
    return fila


def compor_lote(lote):
    """Apresenta as notícias ao modelo. Usa «[N]» como marcador, distinto do
    formato de resposta pedido («N=valor»), para o modelo não ser tentado a
    ecoar a entrada e o parsing não confundir título com classificação."""
    linhas = []
    for i, n in enumerate(lote, start=1):
        resumo = (n.get("resumo") or "").strip()
        extra = f" — {resumo[:140]}" if resumo else ""
        linhas.append(f"[{i}] {n.get('titulo', '').strip()}{extra}")
    return "\n".join(linhas)


def interpretar(texto, tamanho):
    """Lê a classificação de cada notícia da resposta do modelo.

    Tolerante ao formato: aceita «N=valor», «N: valor», «N - valor» e, se o
    modelo ecoar o título antes do valor, apanha a classificação mesmo assim.
    Estratégia por linha: se houver um separador (= : -) depois do número,
    procura a classificação NO QUE VEM A SEGUIR (evita apanhar uma palavra do
    título); se não houver, usa a última palavra-chave reconhecida da linha.
    O que não se entender fica sem avaliação e volta à fila — nunca se inventa.
    """
    equivalencias = {"positivo": "positivo", "positiva": "positivo",
                     "negativo": "negativo", "negativa": "negativo",
                     "neutro": "neutro", "neutra": "neutro",
                     "neutral": "neutro"}

    def classificar(fragmento):
        achado = None
        for palavra in re.findall(r"[A-Za-zÀ-ÿ]+", fragmento):
            v = _sem_acentos(palavra).lower()
            if v in equivalencias:
                achado = equivalencias[v]      # última reconhecida
        return achado

    resultado = {}
    for linha in texto.splitlines():
        ini = re.match(r"\s*\[?(\d+)\]?\s*([=:).\-–]?)(.*)", linha)
        if not ini:
            continue
        i = int(ini.group(1))
        if not (1 <= i <= tamanho):
            continue
        # com separador, o valor vem depois dele; sem, procura na linha toda
        depois = ini.group(3) if ini.group(2) else linha
        valor = classificar(depois) or classificar(linha)
        if valor:
            resultado[i] = valor
    return resultado


def perguntar_local(sintese, lote, repo, ficheiro):
    modelo = sintese.carregar_modelo_local(repo, ficheiro)
    resposta = modelo.create_chat_completion(
        messages=[{"role": "system", "content": INSTRUCAO},
                  {"role": "user", "content": compor_lote(lote)}],
        temperature=0.0,
        max_tokens=16 * len(lote) + 64,
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


def atualizar_serie(caminho, noticias, avaliacoes, origem_da_fonte, dias,
                    datas_extra=frozenset()):
    """Agregados diários por área — o alicerce da futura vista na evolução.

    Acumula desde o primeiro dia, mesmo em modo de ensaio: quando a precisão
    das avaliações for validada, o gráfico nasce com história e não do zero.
    Enquanto isso, nada disto é mostrado. Os dias dentro da janela do arquivo
    recontam-se a cada execução (as avaliações vão chegando); os dias que já
    saíram da janela ficam fechados como estão — a não ser que venham em
    `datas_extra`, o caso dos dias repescados do arquivo mensal, que são
    recontados e substituem o registo parcial que lá estava. Cresce cerca de
    2 KB por dia.
    """
    serie = {"atualizado": "", "estado": "em validação — leitura humana em curso", "dias": []}
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
        if not dia or not area or (dia < limite and dia not in datas_extra):
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
    ap.add_argument("--lote", type=int, default=10,
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
    ap.add_argument("--arquivo-sentimento", default="sentimento-meses",
                    dest="arquivo_sentimento",
                    help="pasta do arquivo permanente das avaliações, por mês")
    ap.add_argument("--reter", type=int, default=35,
                    help="dias de avaliações a guardar (a janela do arquivo é "
                         "menor; guarda-se mais para o painel poder alargar)")
    ap.add_argument("--recuperar", default="",
                    help="datas (AAAA-MM-DD, por vírgulas) a repescar do arquivo "
                         "mensal — para fechar dias que ficaram sem avaliação")
    ap.add_argument("--mensal", default="meses",
                    help="pasta do arquivo mensal, usada com --recuperar")
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

    datas_extra = frozenset(d.strip() for d in args.recuperar.split(",") if d.strip())
    if datas_extra:
        repescadas = carregar_do_mensal(args.mensal, datas_extra)
        noticias = noticias + repescadas
        print(f"repesca: {len(repescadas)} registos de {len(datas_extra)} dia(s) "
              f"lidos do arquivo mensal")

    # As avaliações de sempre — o arquivo permanente. Juntam-se às da janela
    # para nada ser reclassificado e para a série poder recontar dias antigos.
    arquivadas = carregar_sentimento_arquivado(args.arquivo_sentimento)
    if arquivadas:
        print(f"arquivo de sentimento: {len(arquivadas)} avaliações de sempre")

    anterior = {}
    if os.path.exists(args.saida):
        try:
            with open(args.saida, encoding="utf-8") as origem:
                anterior = json.load(origem)
        except (json.JSONDecodeError, OSError):
            anterior = {}
    avaliacoes = anterior.get("avaliacoes", {})

    # Poda: as avaliações guardam-se muito para lá da janela do arquivo, para
    # o painel poder mostrar o tom de notícias antigas quando a janela de
    # consulta se alargar (as quatro semanas pedidas). São ~170 bytes cada:
    # um mês inteiro fica na ordem do megabyte, o que é comportável.
    limite = (agora_lisboa() - timedelta(days=args.reter)).strftime("%Y-%m-%d")
    avaliacoes = {lig: v for lig, v in avaliacoes.items()
                  if (v.get("d") or "9999") >= limite
                  or (v.get("d") or "") in datas_extra}

    # Para saber o que falta e para reconstruir a série, vale tudo o que já se
    # sabe: a janela de trabalho mais o arquivo de sempre.
    conhecidas = dict(arquivadas)
    conhecidas.update(avaliacoes)

    fila = pendentes(noticias, conhecidas, recolha.origem_da_fonte, args.dias,
                     datas_extra)
    por_fazer = len(fila)
    fila = fila[:args.teto]
    print(f"sentimento: {por_fazer} notícias nacionais por avaliar; "
          f"{len(fila)} nesta execução, em lotes de {args.lote}")

    def gravar():
        """Escreve o estado atual — chamada durante a corrida e no fim, para
        que uma execução interrompida (limite de tempo do GitHub, falha de
        rede) não perca o que já classificou. Gravar por partes é o que torna
        seguras as corridas longas."""
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

        # O arquivo permanente fica com tudo o que se souber — é ele que
        # sobrevive à poda e que permitirá repescar meses no futuro.
        if args.arquivo_sentimento:
            guardadas = arquivar_sentimento(args.arquivo_sentimento,
                                            conhecidas, arquivadas)
            if guardadas:
                arquivadas.update({lig: v for lig, v in conhecidas.items()
                                   if lig not in arquivadas})

        if args.serie:
            atualizar_serie(args.serie, noticias, conhecidas,
                            recolha.origem_da_fonte, args.dias, datas_extra)

    novas, falhas = 0, 0
    total_lotes = (len(fila) + args.lote - 1) // args.lote
    for indice, inicio in enumerate(range(0, len(fila), args.lote)):
        lote = fila[inicio:inicio + args.lote]
        try:
            if args.local:
                resposta = perguntar_local(sintese, lote, repo, ficheiro)
            else:
                resposta = perguntar_servico(args.endereco, chave, lote,
                                             sintese.MODELO)
        except Exception as erro:                              # noqa: BLE001
            print(f"  lote {indice + 1}/{total_lotes}: falhou "
                  f"({type(erro).__name__}: {erro}) — fica para a próxima")
            falhas += 1
            continue
        lidas = interpretar(resposta, len(lote))
        for i, n in enumerate(lote, start=1):
            if i not in lidas:
                continue
            lig = n.get("ligacao") or (n.get("titulo") or "").lower()
            avaliacoes[lig] = {"s": lidas[i], "d": (n.get("data") or "")[:10]}
            conhecidas[lig] = avaliacoes[lig]
            novas += 1
        print(f"  lote {indice + 1}/{total_lotes}: "
              f"{len(lidas)}/{len(lote)} avaliadas (acumulado: {len(avaliacoes)})")
        # Grava o progresso de tempos a tempos: se a corrida for cortada a
        # seguir, o trabalho feito até aqui fica salvo.
        if (indice + 1) % 2 == 0:
            gravar()

    gravar()
    print(f"sentimento: {novas} novas avaliações, {falhas} lotes falhados, "
          f"{len(avaliacoes)} no total em {args.saida}")


if __name__ == "__main__":
    principal()
