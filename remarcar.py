#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica as regras de marcação ATUAIS a tudo o que já está arquivado.

A marcação acontece no momento da recolha. Uma expressão acrescentada hoje só
marca daí para a frente, e uma expressão removida continua a sustentar
marcações antigas — pelo que o arquivo vai ficando com a memória de várias
versões das regras ao mesmo tempo. Uma palavra-chave nova aparece a zero
durante dias, não porque não haja notícias, mas porque chegou tarde.

Este passo relê cada notícia guardada, reaplica as regras de hoje ao título e
ao resumo, e reescreve o arquivo:

  · marcações que hoje já não se sustentam    → saem
  · marcações que hoje se sustentam e faltam  → entram
  · notícias que passam a pertencer a novas áreas → ganham linha nessas áreas

Sobre reescrever a história: é deliberado e é o ponto. O arquivo passa a
responder à pergunta «o que as regras de hoje encontram nas notícias de então»,
que é a única com resposta estável. A alternativa — deixar cada dia marcado
pelas regras que vigoravam nesse dia — dá uma série em que uma subida pode ser
apenas uma expressão nova, o que é precisamente o que se quer evitar.

DOIS MODOS, E O PREDEFINIDO É O PRUDENTE.

  --palavras (predefinido)
      Mantém as áreas de cada notícia como estão e atualiza apenas as
      palavras-chave de cada par notícia-área. As contagens por área — que são
      a série — não mexem; o que muda é o quadro das palavras, onde uma
      expressão acrescentada tarde deixa de aparecer a zero.

  --completo
      Reclassifica tudo, incluindo artigos hoje sem área nenhuma, que podem
      passar a pertencer a uma.

      ATENÇÃO, e é uma razão séria: o arquivo mensal só começou a guardar os
      artigos NÃO marcados a partir de 10 de agosto de 2026. Antes disso
      guardava apenas o que já estava classificado. Uma reclassificação
      completa só encontra material novo nos dias recentes — medido em agosto
      de 2026: +0,5% nos dias 3 a 9, +15% a +22% de 11 em diante. Ou seja,
      corrigiria a série de um lado e não do outro, criando um degrau
      artificial exatamente do género que este projeto anda a evitar. Use-o
      apenas quando o arquivo integral cobrir todo o período em análise.

CORRER SEMPRE COM --ensaio PRIMEIRO: mostra o que mudaria, sem tocar em nada.

Uso:
    python remarcar.py --ensaio            # relatório, não escreve
    python remarcar.py                     # atualiza as palavras-chave
    python remarcar.py --completo --ensaio # ver o efeito da reclassificação
"""

import argparse
import gzip
import importlib.util
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone


def agora_lisboa():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Lisbon"))
    except Exception:                                          # noqa: BLE001
        return datetime.now(timezone.utc) + timedelta(hours=1)


def modulo(nome, ficheiro):
    pasta = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(nome, os.path.join(pasta, ficheiro))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def chave_noticia(r):
    """Identidade de um artigo, independente da área em que está marcado."""
    return (r.get("ligacao") or "").strip() or (r.get("titulo") or "").strip().lower()


def remarcar_registos(registos, alvo, en, completo=False):
    """Devolve (linhas novas, contadores) para um conjunto de linhas do arquivo.

    Uma notícia pode aparecer várias vezes no arquivo, uma por área. Agrupa-se
    por artigo, decide-se de novo a que áreas pertence, e reconstroem-se as
    linhas — preservando tudo o resto do registo original (data, fonte,
    domínio, ligação), que não depende das regras.
    """
    por_artigo = {}
    for r in registos:
        por_artigo.setdefault(chave_noticia(r), []).append(r)

    saida, cont = [], Counter()
    for _, linhas in por_artigo.items():
        base = linhas[0]
        it = {"titulo": base.get("titulo") or "", "resumo": base.get("resumo") or ""}
        achados = en.marcar_por_areas(it, alvo)
        antes = {r.get("area"): set(r.get("palavras") or []) for r in linhas if r.get("area")}
        # No modo prudente, o conjunto de áreas não muda: só se atualizam as
        # palavras das áreas que a notícia já tinha.
        if not completo:
            achados = [a for a in achados if a[0] in antes]
        depois = {nome: set(casadas) for nome, _, casadas in achados}

        # Linhas sem área — artigos lidos mas não classificados — passam pelo
        # mesmo crivo: podem ter passado a pertencer a alguma área.
        sem_area = [r for r in linhas if not r.get("area")]

        for nome, grupo, casadas in achados:
            modelo = next((r for r in linhas if r.get("area") == nome), None) \
                or (sem_area[0] if sem_area else base)
            nova = dict(modelo)
            nova["area"] = nome
            nova["grupo"] = grupo
            casadas = set(casadas)
            nova["palavras"] = sorted(casadas)
            saida.append(nova)
            if nome not in antes:
                cont["areas_novas"] += 1
            else:
                ganhas = casadas - antes[nome]
                perdidas = antes[nome] - casadas
                cont["palavras_novas"] += len(ganhas)
                cont["palavras_retiradas"] += len(perdidas)

        for nome in antes:
            if nome not in depois:
                cont["areas_retiradas"] += 1

        # Um artigo que não pertence a área nenhuma continua no arquivo sem
        # área: é ele que sustenta a pesquisa por termo livre e a contagem de
        # notícias distintas.
        if not achados:
            guardar = sem_area or linhas
            r = dict(guardar[0])
            r.pop("area", None); r.pop("grupo", None); r.pop("palavras", None)
            saida.append(r)

    return saida, cont


def principal():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mensal", default="meses")
    ap.add_argument("--mes", default=None, help="Só este mês (AAAA-MM).")
    ap.add_argument("--arquivo", default="arquivo.json")
    ap.add_argument("--completo", action="store_true",
                    help="Reclassifica tudo, incluindo artigos sem área. "
                         "Ver a ressalva no cabeçalho antes de usar.")
    ap.add_argument("--ensaio", action="store_true",
                    help="Mostra o que mudaria e não escreve nada.")
    ap.add_argument("--sem-copia", action="store_true",
                    help="Não guarda cópia de segurança dos ficheiros alterados.")
    args = ap.parse_args()

    en = modulo("extrair_noticias", "extrair_noticias.py")
    alvo = list(en.AREAS)
    print(f"regras atuais: {len(alvo)} áreas, "
          f"{sum(len(a[3]) for a in alvo)} expressões")
    print("modo: " + ("COMPLETO — reclassifica tudo, incluindo artigos sem área"
                      if args.completo else
                      "palavras — mantém as áreas, atualiza só as palavras-chave"))

    meses = sorted(f for f in os.listdir(args.mensal) if f.endswith(".jsonl.gz"))
    if args.mes:
        meses = [f for f in meses if f.startswith(args.mes)]
    if not meses:
        print("Sem ficheiros mensais para tratar.")
        return

    total = Counter()
    for ficheiro in meses:
        caminho = os.path.join(args.mensal, ficheiro)
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            registos = [json.loads(l) for l in origem if l.strip()]
        novas, cont = remarcar_registos(registos, alvo, en, args.completo)
        total.update(cont)
        print(f"  {ficheiro}: {len(registos)} linhas → {len(novas)} "
              f"(+{cont['areas_novas']} áreas, -{cont['areas_retiradas']}, "
              f"+{cont['palavras_novas']} palavras, -{cont['palavras_retiradas']})")

        if args.ensaio:
            continue
        if not args.sem_copia:
            shutil.copy2(caminho, caminho + ".antes")
        # Ordena por data para o ficheiro continuar legível e estável.
        novas.sort(key=lambda r: ((r.get("data") or ""), r.get("area") or ""))
        with gzip.open(caminho, "wt", encoding="utf-8") as destino:
            for r in novas:
                destino.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nresumo: +{total['areas_novas']} marcações de área, "
          f"-{total['areas_retiradas']} retiradas, "
          f"+{total['palavras_novas']} palavras-chave, "
          f"-{total['palavras_retiradas']} removidas")

    if args.ensaio:
        print("\n(ensaio: nada foi escrito)")
        return

    print("\nO arquivo mensal é a fonte de verdade das séries. Reconstrua-as com:")
    print("  python reconstruir_series.py")
    print("e recalcule os alertas com:")
    print("  python alertas.py --mensal meses --saida alertas.json")


if __name__ == "__main__":
    principal()
