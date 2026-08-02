#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Notícias — síntese diária por área, gerada pelo Amália
Secretaria-Geral do Governo · Unidade de Pesquisa e Estatísticas

Lê o arquivo da recolha e pede ao Amália, por cada área governativa, um parágrafo
que dê conta do que foi notícia no período. Grava o resultado em sinteses.json,
que o painel e o relatório por email leem se existir.

O modelo trabalha apenas sobre títulos e resumos já recolhidos: não acede à
internet, não é fonte de factos, e cada síntese é acompanhada das notícias que a
originaram, para que quem lê possa verificar.

Sem ponto de acesso configurado, o programa não faz nada e sai em silêncio — a
aplicação continua a funcionar como hoje.

Utilização:
    export AMALIA_CHAVE="..."
    python sintese_ia.py --dados arquivo.json --periodo 24h \\
        --endereco https://amalia.exemplo.gov.pt/v1/chat/completions
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

MODELO = "amalia-llm/AMALIA-9B-0626-DPO"

# O Amália tem pesos abertos sob licença Apache 2.0. Corre no próprio fluxo de
# trabalho, sem depender de qualquer serviço: usa-se uma conversão quantizada de
# cerca de 5,5 GB, que cabe na memória de um servidor comum e dispensa placa
# gráfica. Em contrapartida é lento — cerca de um minuto por área.
REPO_GGUF = "layerx-labs/AMALIA-9B-0626-DPO-GGUF"
FICHEIRO_GGUF = "AMALIA-9B-0626-DPO-Q4_K_M.gguf"
HORAS = {"24h": 24, "48h": 48, "72h": 72, "7d": 168}

INSTRUCAO = (
    "És um analista da Secretaria-Geral do Governo. Recebes os títulos das notícias "
    "de hoje sobre uma área governativa e escreves um parágrafo único, de três a "
    "cinco frases, que dê conta do que foi notícia.\n\n"
    "Regras:\n"
    "- Usa apenas o que está nos títulos. Não acrescentes factos, números, causas "
    "ou consequências que não estejam lá.\n"
    "- Começa pelo assunto com mais peso e agrupa os que se repetem.\n"
    "- Escreve em português de Portugal, em registo institucional e neutro.\n"
    "- Não emitas juízos, não recomendes nada, não uses adjetivos valorativos.\n"
    "- Não uses expressões como 'as notícias indicam' ou 'segundo os títulos'.\n"
    "- Devolve apenas o parágrafo, sem título nem marcas de formatação."
)


def carregar(caminho):
    with open(caminho, encoding="utf-8") as origem:
        return json.load(origem).get("noticias", [])


def do_periodo(noticias, area, periodo):
    limite = datetime.now() - timedelta(hours=HORAS.get(periodo, 24))
    saida = []
    for n in noticias:
        if n.get("area") != area or not n.get("data"):
            continue
        try:
            if datetime.strptime(n["data"][:16], "%Y-%m-%d %H:%M") < limite:
                continue
        except ValueError:
            continue
        saida.append(n)
    saida.sort(key=lambda n: n.get("data", ""), reverse=True)
    return saida


def perguntar(endereco, chave, titulos, area, tempo_limite=60):
    """Uma chamada ao Amália, pela interface compatível com OpenAI."""
    lista = "\n".join(f"- {t}" for t in titulos)
    corpo = {
        "model": MODELO,
        "messages": [
            {"role": "system", "content": INSTRUCAO},
            {"role": "user", "content": f"Área governativa: {area}\n\nTítulos:\n{lista}"},
        ],
        "temperature": 0.2,
        "max_tokens": 320,
    }

    pedido = urllib.request.Request(
        endereco,
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {chave}"},
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    return dados["choices"][0]["message"]["content"].strip()


_modelo_local = None


def carregar_modelo_local(repo, ficheiro, contexto=4096, fios=0):
    """Carrega o Amália em memória, a partir da conversão quantizada.

    O ficheiro é descarregado uma vez e fica em cache. Sem placa gráfica, a
    geração faz-se no processador: é lenta mas suficiente para um parágrafo.
    """
    global _modelo_local
    if _modelo_local is not None:
        return _modelo_local

    try:
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama
    except ImportError:
        sys.exit("Faltam bibliotecas. Instale com:\n"
                 "  pip install llama-cpp-python huggingface-hub")

    print(f"A obter {ficheiro} de {repo}…")
    caminho = hf_hub_download(repo_id=repo, filename=ficheiro)
    print(f"A carregar o modelo ({os.path.getsize(caminho) / 1e9:.1f} GB)…")

    _modelo_local = Llama(
        model_path=caminho,
        n_ctx=contexto,
        n_threads=fios or (os.cpu_count() or 4),
        verbose=False,
    )
    return _modelo_local


def perguntar_local(titulos, area, repo, ficheiro):
    """A mesma pergunta, respondida pelo modelo carregado neste computador."""
    modelo = carregar_modelo_local(repo, ficheiro)
    lista = "\n".join(f"- {t}" for t in titulos)
    resposta = modelo.create_chat_completion(
        messages=[
            {"role": "system", "content": INSTRUCAO},
            {"role": "user", "content": f"Área governativa: {area}\n\nTítulos:\n{lista}"},
        ],
        temperature=0.2,
        max_tokens=320,
    )
    return resposta["choices"][0]["message"]["content"].strip()


def principal():
    ap = argparse.ArgumentParser(description="Síntese diária por área, pelo Amália.")
    ap.add_argument("--dados", default="arquivo.json")
    ap.add_argument("--saida", default="sinteses.json")
    ap.add_argument("--periodo", default="24h", choices=list(HORAS) + ["auto"],
                    help="'auto' alarga a janela à segunda-feira, para cobrir o fim de semana")
    ap.add_argument("--local", action="store_true",
                    help="correr o Amália neste computador, sem serviço externo")
    ap.add_argument("--repo", default=REPO_GGUF, help="repositório da conversão quantizada")
    ap.add_argument("--ficheiro", default=FICHEIRO_GGUF, help="ficheiro do modelo")
    ap.add_argument("--endereco", default=os.environ.get("AMALIA_ENDERECO", ""),
                    help="ponto de acesso a um serviço já instalado (alternativa a --local)")
    ap.add_argument("--minimo", type=int, default=3,
                    help="notícias mínimas para valer a pena sintetizar")
    ap.add_argument("--maximo", type=int, default=40,
                    help="títulos a enviar por área, dos mais recentes")
    args = ap.parse_args()

    chave = os.environ.get("AMALIA_CHAVE", "")
    if not args.local and (not args.endereco or not chave):
        print("Sem modo local nem ponto de acesso configurado. Nada a fazer.")
        return

    # A síntese acompanha a janela do relatório que a vai apresentar
    if args.periodo == "auto":
        args.periodo = "72h" if datetime.now().weekday() == 0 else "24h"
        print(f"Janela automática: {args.periodo}")

    if not os.path.exists(args.dados):
        sys.exit(f"Ficheiro de dados não encontrado: {args.dados}")

    noticias = carregar(args.dados)
    areas = sorted({n.get("area") for n in noticias if n.get("area")})

    agora = datetime.now()
    resultado = {"gerado": agora.strftime("%Y-%m-%d %H:%M"),
                 "periodo": args.periodo, "modelo": MODELO,
                 "modo": "local" if args.local else "serviço", "areas": {}}

    for area in areas:
        doDia = do_periodo(noticias, area, args.periodo)
        if len(doDia) < args.minimo:
            print(f"  {area}: {len(doDia)} notícias, abaixo do mínimo — sem síntese")
            continue

        titulos = [n["titulo"] for n in doDia[: args.maximo]]
        try:
            texto = (perguntar_local(titulos, area, args.repo, args.ficheiro)
                     if args.local else
                     perguntar(args.endereco, chave, titulos, area))
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError, RuntimeError) as erro:
            print(f"  {area}: falhou ({erro})")
            continue

        # O modelo pode devolver texto vazio ou marcas de formatação
        texto = texto.strip().strip("*_` ")
        if len(texto) < 60:
            print(f"  {area}: resposta demasiado curta, ignorada")
            continue

        resultado["areas"][area] = {
            "texto": texto,
            "noticias": len(doDia),
            "titulos": titulos[:10],   # amostra, para verificação
        }
        print(f"  {area}: {len(doDia)} notícias → {len(texto)} caracteres")

    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump(resultado, destino, ensure_ascii=False, indent=1)

    print(f"\n{len(resultado['areas'])} sínteses gravadas em {args.saida}")


if __name__ == "__main__":
    principal()
