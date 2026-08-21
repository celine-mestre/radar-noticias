#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resumo do Amália para os dias em que uma área teve cobertura muito negativa.

A matriz do tom mostra, para cada área e dia, a percentagem de notícias
negativas. Um 85% diz que a cobertura foi dura — não diz porquê. Este módulo
responde a essa pergunta: para cada célula acima do limiar, reúne as notícias
NEGATIVAS reais desse dia e dessa área e pede ao Amália três a quatro frases
sobre o que aconteceu.

DUAS DIFERENÇAS EM RELAÇÃO AOS RESUMOS DE PICOS. A seleção é pelo TOM e não
pelo volume — um dia pode ser muito negativo sem ser um pico —, e as notícias
que vão para o Amália são apenas as classificadas como negativas: o resumo
explica a parte negativa da cobertura, que é o que a célula mede.

POR DIA, E SÓ POR DIA. O dia é o átomo: gera-se uma vez e nunca muda. Não se
resumem semanas nem meses — uma semana em curso mudaria de conteúdo todos os
dias e o resumo de segunda-feira ficaria obsoleto à quarta. Nas vistas
agregadas, o painel junta os resumos dos dias que compõem o período.

INCREMENTAL. Só se resume uma célula sem resumo. Guarda-se em
matriz-resumos.json, indexado por «data|área».

Uso local:   python resumo_matriz.py --local
Por serviço: AMALIA_ENDERECO=... AMALIA_CHAVE=... python resumo_matriz.py
"""

import argparse
import gzip
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone

# O limiar a partir do qual uma célula merece explicação. Medido nos dados de
# agosto de 2026: 75% dá cerca de meia célula por dia — uma dúzia por mês.
# Baixá-lo para 70% duplicaria o número e começaria a apanhar dias banais.
LIMIAR = 75               # cobertura muito negativa
LIMIAR_POSITIVO = 50      # cobertura muito positiva — o lado bom raramente vai
                          # tão alto: metade das notícias de uma área serem
                          # positivas já é um dia fora do comum. Medido em
                          # agosto de 2026: 12 células acima de 75% de negativas
                          # e 7 acima de 50% de positivas, no mesmo período.
MINIMO_AVALIADAS = 8      # o mesmo do painel: abaixo disto a proporção é ruído

INSTRUCAO_NEGATIVO = (
    "És um analista de comunicação social da administração pública "
    "portuguesa. Recebes os títulos das notícias NEGATIVAS de UMA área "
    "governativa num único dia — um dia em que a cobertura dessa área foi "
    "maioritariamente negativa. A tua tarefa é dizer, em três a quatro "
    "frases, O QUE ACONTECEU: que casos, decisões ou problemas concretos "
    "estão por trás desses títulos. Agrupa por acontecimento e nomeia os "
    "factos; se houver um tema dominante, diz qual. Escreve em português "
    "europeu, de forma sóbria e informativa. Descreve os ACONTECIMENTOS, "
    "nunca a atitude dos jornais nem a qualidade da cobertura, e não emitas "
    "opinião. Não inventes nada que não esteja nos títulos: se os títulos "
    "não bastarem para perceber o que se passou, di-lo com franqueza."
)

INSTRUCAO_POSITIVO = (
    "És um analista de comunicação social da administração pública "
    "portuguesa. Recebes os títulos das notícias POSITIVAS de UMA área "
    "governativa num único dia — um dia em que boa parte da cobertura dessa "
    "área foi positiva, o que é raro. A tua tarefa é dizer, em três a quatro "
    "frases, O QUE ACONTECEU: que medidas, resultados, acordos ou "
    "reconhecimentos concretos estão por trás desses títulos. Agrupa por "
    "acontecimento e nomeia os factos; se houver um tema dominante, diz qual. "
    "Escreve em português europeu, de forma sóbria e informativa. Descreve os "
    "ACONTECIMENTOS, nunca a atitude dos jornais nem a qualidade da cobertura, "
    "e não faças propaganda: relata, não celebra. Não inventes nada que não "
    "esteja nos títulos; se os títulos não bastarem, di-lo com franqueza."
)

# A chave com que cada resumo é guardado. As negativas mantêm a chave antiga,
# para os resumos já gerados continuarem a valer; as positivas levam sufixo.
def chave_resumo(data, area, lado):
    return f"{data}|{area}" + ("" if lado == "negativas" else "|+")


def agora_lisboa():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Lisbon"))
    except Exception:                                          # noqa: BLE001
        return datetime.now(timezone.utc) + timedelta(hours=1)


def modulos():
    """Importa a síntese (carregador do modelo) do próprio repositório."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "sintese_ia", os.path.join(pasta, "sintese_ia.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def celulas_extremas(caminho_serie, lado="negativas", limiar=None):
    """Pares (dia, área) cuja cobertura passou o limiar, de um dos lados.

    Lê a mesma série que alimenta a matriz do painel, para que o que se resume
    seja exatamente o que se vê — sem recontar por outro caminho, que é como
    dois números do mesmo indicador acabam diferentes.
    """
    try:
        with open(caminho_serie, encoding="utf-8") as origem:
            dias = json.load(origem).get("dias", [])
    except (json.JSONDecodeError, OSError):
        return []
    neg = lado == "negativas"
    if limiar is None:
        limiar = LIMIAR if neg else LIMIAR_POSITIVO
    campo = "negativo" if neg else "positivo"
    fora = []
    for d in dias:
        data = d.get("data")
        for area, c in (d.get("areas") or {}).items():
            av = c.get("avaliadas", 0)
            if av < MINIMO_AVALIADAS:
                continue
            pct = round(100 * c.get(campo, 0) / av)
            if pct >= limiar:
                fora.append({"data": data, "area": area, "pct": pct,
                             "avaliadas": av, "quantas": c.get(campo, 0),
                             "lado": lado})
    fora.sort(key=lambda x: x["data"])
    return fora


def avaliacoes(caminho="sentimentos.json"):
    """{chave da notícia: tom} — a mesma indexação que o painel usa."""
    try:
        with open(caminho, encoding="utf-8") as origem:
            return json.load(origem).get("avaliacoes", {})
    except (json.JSONDecodeError, OSError):
        return {}


def titulos_do_dia_area(pasta_mensal, dia, area, tons, tom_alvo="negativo"):
    """Títulos das notícias de um dado tom, de uma área num dia, do arquivo.

    A avaliação está indexada pela ligação, com o título em minúsculas como
    recurso — é a convenção que o sentimento usa, e repeti-la aqui evita que
    um artigo avaliado apareça como não avaliado só por ter mudado de
    endereço.
    """
    caminho = os.path.join(pasta_mensal, f"{dia[:7]}.jsonl.gz")
    if not os.path.exists(caminho):
        return []
    vistos, titulos = set(), []
    with gzip.open(caminho, "rt", encoding="utf-8") as origem:
        for linha in origem:
            try:
                r = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if r.get("area") != area or (r.get("data") or "")[:10] != dia:
                continue
            titulo = (r.get("titulo") or "").strip()
            chave = r.get("ligacao") or titulo.lower()
            if not chave or chave in vistos:
                continue
            aval = tons.get(chave) or tons.get(titulo.lower())
            tom = (aval or {}).get("s") if isinstance(aval, dict) else aval
            if tom != tom_alvo:
                continue
            vistos.add(chave)
            titulos.append((r.get("fonte", ""), titulo))
    return titulos


def pedir_local(sintese, titulos, area, dia, repo, ficheiro, instrucao):
    modelo = sintese.carregar_modelo_local(repo, ficheiro)
    lista = "\n".join(f"- [{f}] {t}" for f, t in titulos if t)
    resposta = modelo.create_chat_completion(
        messages=[{"role": "system", "content": instrucao},
                  {"role": "user", "content": (f"Área: {area}\nDia: {dia}\n\n"
                                               f"Títulos:\n{lista}")}],
        temperature=0.3,
        max_tokens=320,
    )
    return resposta["choices"][0]["message"]["content"].strip()


def pedir_servico(endereco, chave, titulos, area, dia, modelo_nome, instrucao,
                  tempo_limite=180):
    import urllib.request
    lista = "\n".join(f"- [{f}] {t}" for f, t in titulos if t)
    corpo = json.dumps({
        "model": modelo_nome, "temperature": 0.3, "max_tokens": 320,
        "messages": [{"role": "system", "content": instrucao},
                     {"role": "user", "content": (f"Área: {area}\nDia: {dia}\n\n"
                                                  f"Títulos:\n{lista}")}],
    }).encode("utf-8")
    pedido = urllib.request.Request(
        endereco, data=corpo,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {chave}"})
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        d = json.loads(resposta.read())
    return d["choices"][0]["message"]["content"].strip()


def principal():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serie", default="sentimento-serie.json")
    ap.add_argument("--sentimentos", default="sentimentos.json")
    ap.add_argument("--mensal", default="meses")
    ap.add_argument("--saida", default="matriz-resumos.json")
    ap.add_argument("--limiar", type=int, default=None,
                    help="Sobrepõe o limiar; só com um lado escolhido.")
    ap.add_argument("--lado", default="ambos",
                    choices=["ambos", "negativas", "positivas"])
    ap.add_argument("--teto", type=int, default=8,
                    help="Máximo de resumos por execução, para não prender o fluxo.")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--ficheiro", default=None)
    ap.add_argument("--endereco", default=os.environ.get("AMALIA_ENDERECO", ""))
    args = ap.parse_args()

    sintese = modulos()
    repo = args.repo or sintese.REPO_GGUF
    ficheiro = args.ficheiro or sintese.FICHEIRO_GGUF
    chave_api = os.environ.get("AMALIA_CHAVE", "")
    if not args.local and (not args.endereco or not chave_api):
        print("Sem modo local nem ponto de acesso. Nada a fazer.")
        return

    lados = ["negativas", "positivas"] if args.lado == "ambos" else [args.lado]
    celulas = []
    for lado in lados:
        limiar = args.limiar if (args.limiar and len(lados) == 1) else None
        celulas += celulas_extremas(args.serie, lado, limiar)
    if not celulas:
        print("Nenhuma área passou os limiares — nada a resumir.")
        return

    anteriores = {}
    if os.path.exists(args.saida):
        try:
            with open(args.saida, encoding="utf-8") as origem:
                anteriores = json.load(origem).get("resumos", {})
        except (json.JSONDecodeError, OSError):
            anteriores = {}

    tons = avaliacoes(args.sentimentos)
    resumos = dict(anteriores)
    feitos = 0
    for c in celulas:
        chave = chave_resumo(c["data"], c["area"], c["lado"])
        if chave in resumos:
            continue
        if feitos >= args.teto:
            print(f"  (teto de {args.teto} atingido nesta passagem; "
                  f"o resto fica para a próxima)")
            break
        neg = c["lado"] == "negativas"
        titulos = titulos_do_dia_area(args.mensal, c["data"], c["area"], tons,
                                      "negativo" if neg else "positivo")
        if not titulos:
            # Sem títulos não se inventa resumo — e regista-se porquê, para o
            # painel poder dizer alguma coisa em vez de ficar mudo.
            resumos[chave] = {
                "texto": "As notícias deste dia já não estão no arquivo, ou "
                         "ainda não têm avaliação de tom.",
                "n": 0, "pct": c["pct"], "lado": c["lado"]}
            continue
        try:
            instrucao = INSTRUCAO_NEGATIVO if neg else INSTRUCAO_POSITIVO
            if args.local:
                texto = pedir_local(sintese, titulos, c["area"], c["data"],
                                    repo, ficheiro, instrucao)
            else:
                texto = pedir_servico(args.endereco, chave_api, titulos,
                                      c["area"], c["data"], sintese.MODELO, instrucao)
        except Exception as erro:                              # noqa: BLE001
            print(f"  {chave}: falhou ({type(erro).__name__}) — fica para a próxima")
            continue
        resumos[chave] = {"texto": texto, "n": len(titulos), "pct": c["pct"],
                          "lado": c["lado"]}
        feitos += 1
        print(f"  {chave}: resumido ({c['pct']}% {c['lado']}, {len(titulos)} notícias)")

    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump({
            "gerado": agora_lisboa().strftime("%Y-%m-%d %H:%M"),
            "modelo": sintese.MODELO,
            "limiar": LIMIAR,
            "limiar_positivo": LIMIAR_POSITIVO,
            "nota": ("O que aconteceu nos dias em que a cobertura de uma área foi "
                     f"negativa em {LIMIAR}% ou mais, ou positiva em "
                     f"{LIMIAR_POSITIVO}% ou mais, a partir dos títulos das "
                     "notícias desse tom nesse dia. Descreve acontecimentos, não a "
                     "atitude das publicações. As chaves com «|+» no fim são do "
                     "lado positivo."),
            "resumos": resumos,
        }, destino, ensure_ascii=False, indent=1)

    print(f"resumo da matriz: {feitos} novos, {len(resumos)} no total em "
          f"{args.saida} (limiares: {LIMIAR}% negativas, {LIMIAR_POSITIVO}% positivas)")


if __name__ == "__main__":
    principal()
