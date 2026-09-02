#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resumo do Amália para cada pico noticioso.

Um pico diz que uma área teve um volume de notícias muito acima do habitual —
mas não diz porquê. Este módulo responde a essa pergunta: para cada pico
registado no alertas.json, reúne as notícias reais desse dia e dessa área e
pede ao Amália um resumo curto do que aconteceu.

DE ONDE VÊM AS NOTÍCIAS. Do arquivo mensal integral (meses/AAAA-MM.jsonl.gz),
que guarda tudo o que foi recolhido — para lá dos sete dias do radar. É isto
que permite explicar um pico de há três semanas, cujas notícias já saíram do
arquivo corrente. O resumo é sempre sobre notícias que existem: o Amália
resume texto real, nunca inventa a explicação de um pico.

INCREMENTAL. Só se resume um pico que ainda não tenha resumo. Os resumos
antigos ficam como estão — o que aconteceu num dia não muda. Guarda-se em
picos-resumos.json, indexado por «data|área».

Uso local:   python resumo_picos.py --local
Por serviço: AMALIA_ENDERECO=... AMALIA_CHAVE=... python resumo_picos.py
"""

import argparse
import glob
import gzip
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

INSTRUCAO = (
    "És um analista de comunicação social da administração pública "
    "portuguesa. Recebes os títulos das notícias de UMA área governativa "
    "num único dia — um dia em que essa área teve um volume de notícias "
    "muito acima do habitual. A tua tarefa é explicar, em três a quatro "
    "frases, O QUE ACONTECEU nesse dia que motivou tanta cobertura. "
    "Agrupa os títulos por acontecimento; se houver um tema dominante, "
    "diz qual e porquê; nomeia os factos concretos, não generalidades. "
    "Escreve em português europeu, de forma sóbria e informativa, sem "
    "opinião. Não inventes nada que não esteja nos títulos: se os títulos "
    "não bastam para perceber a causa, di-lo com franqueza. "
    # As duas regras seguintes nasceram de erros reais: o modelo atribuiu a
    # uma pessoa um ministério que não é o dela e deu o cargo de ministro a
    # outra pessoa, factos que não estavam em título nenhum — vieram da
    # memória do modelo, que é anterior a este Governo. Num produto do
    # Estado, um cargo errado é o erro mais caro que há.
    "NÃO atribuas cargos, funções, ministérios ou partidos a pessoas: "
    "escreve apenas o nome, tal como aparece nos títulos. Só podes indicar "
    "o cargo de alguém se esse cargo estiver escrito num dos títulos que "
    "recebeste, e nesse caso usa exatamente a formulação do título. "
    "Usa exclusivamente a data que te for indicada; nunca escrevas outra."
)


def agora_lisboa():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Lisbon"))
    except Exception:
        return datetime.now(timezone.utc) + timedelta(hours=1)


def modulos():
    """Importa a síntese (carregador do modelo) do próprio repositório."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "sintese_ia", os.path.join(pasta, "sintese_ia.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def noticias_do_dia_area(pasta_mensal, dia, area):
    """Todas as notícias de uma área num dia, do arquivo mensal integral.

    Procura no ficheiro do mês a que o dia pertence. Desduplica pela ligação.
    Devolve pares (fonte, título), que é o que o Amália precisa.
    """
    mes = dia[:7]
    caminho = os.path.join(pasta_mensal, f"{mes}.jsonl.gz")
    if not os.path.exists(caminho):
        return []
    vistos, titulos = set(), []
    with gzip.open(caminho, "rt", encoding="utf-8") as origem:
        for linha in origem:
            try:
                r = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if r.get("area") != area:
                continue
            if (r.get("data") or "")[:10] != dia:
                continue
            chave = r.get("ligacao") or (r.get("titulo") or "").lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            titulos.append((r.get("fonte", ""), r.get("titulo", "").strip()))
    return titulos


def resumir_local(sintese, titulos, area, dia, repo, ficheiro):
    modelo = sintese.carregar_modelo_local(repo, ficheiro)
    lista = "\n".join(f"- [{f}] {t}" for f, t in titulos if t)
    resposta = modelo.create_chat_completion(
        messages=[{"role": "system", "content": INSTRUCAO},
                  {"role": "user", "content": (f"Área: {area}\nDia: {dia}\n\n"
                                               f"Títulos:\n{lista}")}],
        temperature=0.3,
        max_tokens=320,
    )
    return resposta["choices"][0]["message"]["content"].strip()


def resumir_servico(endereco, chave, titulos, area, dia, modelo_nome,
                    tempo_limite=90):
    import urllib.request
    lista = "\n".join(f"- [{f}] {t}" for f, t in titulos if t)
    pedido = urllib.request.Request(
        endereco,
        data=json.dumps({
            "model": modelo_nome, "temperature": 0.3, "max_tokens": 320,
            "messages": [{"role": "system", "content": INSTRUCAO},
                         {"role": "user", "content": (f"Área: {area}\nDia: {dia}"
                                                      f"\n\nTítulos:\n{lista}")}],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {chave}"})
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        corpo = json.load(resposta)
    return corpo["choices"][0]["message"]["content"].strip()


def principal():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--alertas", default="alertas.json")
    ap.add_argument("--mensal", default="meses")
    ap.add_argument("--saida", default="picos-resumos.json")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--ficheiro", default=None)
    ap.add_argument("--endereco", default=os.environ.get("AMALIA_ENDERECO", ""))
    ap.add_argument(
        "--refazer", default="",
        help=("Chaves de picos a refazer, separadas por vírgula, no formato "
              "AAAA-MM-DD|Área (ex.: 2026-09-01|Assuntos Parlamentares). "
              "Sem isto, só se escrevem os picos que ainda não têm resumo, "
              "pelo que um resumo com um erro ficaria lá para sempre."))
    args = ap.parse_args()

    sintese = modulos()
    repo = args.repo or sintese.REPO_GGUF
    ficheiro = args.ficheiro or sintese.FICHEIRO_GGUF
    chave = os.environ.get("AMALIA_CHAVE", "")
    if not args.local and (not args.endereco or not chave):
        print("Sem modo local nem ponto de acesso. Nada a fazer.")
        return

    if not os.path.exists(args.alertas):
        print(f"Sem {args.alertas} — nada a resumir.")
        return
    with open(args.alertas, encoding="utf-8") as origem:
        picos = json.load(origem).get("historico", [])
    if not picos:
        print("Nenhum pico registado — nada a resumir.")
        return

    anteriores = {}
    if os.path.exists(args.saida):
        try:
            with open(args.saida, encoding="utf-8") as origem:
                anteriores = json.load(origem).get("resumos", {})
        except (json.JSONDecodeError, OSError):
            anteriores = {}

    resumos = dict(anteriores)
    for alvo in [x.strip() for x in args.refazer.split(",") if x.strip()]:
        if resumos.pop(alvo, None) is not None:
            print(f"  a refazer: {alvo}")
        else:
            print(f"  aviso: «{alvo}» não tem resumo guardado — nada a refazer")

    feitos = 0
    for pico in picos:
        dia, area = pico.get("data"), pico.get("area")
        if not dia or not area:
            continue
        chave_pico = f"{dia}|{area}"
        if chave_pico in resumos:
            continue                      # já resumido; não se repete
        titulos = noticias_do_dia_area(args.mensal, dia, area)
        if not titulos:
            resumos[chave_pico] = {
                "texto": "As notícias deste dia já não estão no arquivo — "
                         "o pico é anterior ao início do arquivo integral.",
                "n": 0}
            continue
        try:
            if args.local:
                texto = resumir_local(sintese, titulos, area, dia,
                                      repo, ficheiro)
            else:
                texto = resumir_servico(args.endereco, chave, titulos,
                                        area, dia, sintese.MODELO)
        except Exception as erro:                              # noqa: BLE001
            print(f"  {chave_pico}: falhou ({type(erro).__name__}) — "
                  f"fica para a próxima")
            continue
        resumos[chave_pico] = {"texto": texto, "n": len(titulos)}
        feitos += 1
        print(f"  {chave_pico}: resumido ({len(titulos)} notícias)")

    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump({
            "gerado": agora_lisboa().strftime("%Y-%m-%d %H:%M"),
            "modelo": sintese.MODELO,
            "nota": ("Resumo do que motivou cada pico, a partir das notícias "
                     "reais do dia e da área, arquivadas no depósito mensal."),
            "resumos": resumos,
        }, destino, ensure_ascii=False, indent=1)

    print(f"resumo dos picos: {feitos} novos, {len(resumos)} no total "
          f"em {args.saida}")


if __name__ == "__main__":
    principal()
