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
import time
import urllib.request
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ── HORAS ────────────────────────────────────────────────────────────────────
# Tudo o que este programa escreve fica na hora de Lisboa. São dois problemas
# distintos e ambos davam incoerências visíveis no painel:
#
#  1. O servidor do GitHub corre em UTC. Escrevendo agora_lisboa(), a hora da
#     recolha saía uma hora atrás da real no horário de verão.
#  2. Os feeds datam os artigos no seu próprio fuso. Retirar o fuso sem
#     converter — que era o que se fazia — deixava a hora de Berlim ou de
#     Bruxelas como se fosse a nossa, e apareciam notícias "do futuro".
#
# Converte-se tudo para Europa/Lisboa e só depois se retira o fuso, para que as
# comparações e o que se apresenta digam respeito ao mesmo relógio.
LISBOA = ZoneInfo("Europe/Lisbon")


def agora_lisboa():
    """Hora de Lisboa, sem fuso, para gravar e comparar."""
    return datetime.now(LISBOA).replace(tzinfo=None)


def para_lisboa(momento):
    """Converte uma data com fuso para hora de Lisboa, sem fuso."""
    if momento is None:
        return None
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(LISBOA).replace(tzinfo=None)




def _sem_acentos(t):
    return unicodedata.normalize("NFD", (t or "").lower()).encode("ascii", "ignore").decode()

MODELO = "amalia-llm/AMALIA-9B-0626-DPO"

# O Amália tem pesos abertos sob licença Apache 2.0. Corre no próprio fluxo de
# trabalho, sem depender de qualquer serviço: usa-se uma conversão quantizada de
# cerca de 5,5 GB, que cabe na memória de um servidor comum e dispensa placa
# gráfica. Em contrapartida é lento — cerca de um minuto por área.
REPO_GGUF = "layerx-labs/AMALIA-9B-0626-DPO-GGUF"
FICHEIRO_GGUF = "AMALIA-9B-0626-DPO-Q4_K_M.gguf"
HORAS = {"24h": 24, "48h": 48, "72h": 72, "7d": 168}

# As mesmas plataformas que o relatório descarta: a síntese tem de descrever
# exatamente o que a lista mostra, ou desmente-a.
DOMINIOS_NACIONAIS = ("noticiasaominuto.com", "cnnportugal.iol.pt", "eco.sapo.pt",
                      "sapo.pt", "impresa.pt", "medialivre.pt", "lusa.pt")
DOMINIOS_LUSOFONOS = (".ao", ".mz", ".cv", ".st", ".gw", ".tl", ".br")

# As mesmas três origens do painel e das etiquetas do relatório
ORIGENS = [
    ("nacionais", "Portugal"),
    ("lusofonas", "Lusofonia"),
    ("internacionais", "Internacional"),
]

# País de cada publicação, pelo domínio. Pedir ao modelo que o deduza do nome do
# jornal é pedir de mais: ou não sabe, ou inventa. Dando-lho, a exigência passa a
# ser só a de o usar.
PAISES = {
    ".pt": "Portugal", ".ao": "Angola", ".mz": "Moçambique", ".cv": "Cabo Verde",
    ".st": "São Tomé e Príncipe", ".gw": "Guiné-Bissau", ".tl": "Timor-Leste",
    ".br": "Brasil", ".es": "Espanha", ".fr": "França", ".it": "Itália",
    ".de": "Alemanha", ".uk": "Reino Unido", ".co.uk": "Reino Unido",
    ".eu": "União Europeia",
}
PAISES_POR_DOMINIO = {
    "agenciabrasil.ebc.com.br": "Brasil", "folha.uol.com.br": "Brasil",
    "novojornal.co.ao": "Angola", "cartamz.com": "Moçambique",
    "elpais.com": "Espanha", "elmundo.es": "Espanha", "abc.es": "Espanha",
    "lavanguardia.com": "Espanha", "lemonde.fr": "França", "lefigaro.fr": "França",
    "francetvinfo.fr": "França", "france24.com": "França", "rfi.fr": "França",
    "ansa.it": "Itália", "corriere.it": "Itália", "repubblica.it": "Itália",
    "spiegel.de": "Alemanha", "dw.com": "Alemanha",
    "bbc.com": "Reino Unido", "bbc.co.uk": "Reino Unido",
    "theguardian.com": "Reino Unido",
    "nytimes.com": "Estados Unidos da América",
    "washingtonpost.com": "Estados Unidos da América",
    "apnews.com": "Estados Unidos da América",
    "politico.com": "Estados Unidos da América",
    "politico.eu": "União Europeia", "euractiv.com": "União Europeia",
    "pt.euronews.com": "União Europeia",
}


def pais_da_fonte(dominio):
    """País da publicação, para o modelo o poder nomear."""
    d = (dominio or "").lower().replace("www.", "")
    if not d:
        return ""
    if d in PAISES_POR_DOMINIO:
        return PAISES_POR_DOMINIO[d]
    for sufixo, pais in PAISES.items():
        if d.endswith(sufixo):
            return pais
    return ""


PLATAFORMAS = (
    "instagram.com", "facebook.com", "fb.com", "x.com", "twitter.com", "tiktok.com",
    "youtube.com", "youtu.be", "linkedin.com", "reddit.com", "threads.net",
    "bsky.app", "t.me", "medium.com", "substack.com", "blogspot.com", "wordpress.com",
)

INSTRUCAO = (
    "És um analista da Secretaria-Geral do Governo. Recebes os títulos das notícias "
    "de hoje sobre uma área governativa e escreves um parágrafo único que dê conta "
    "do que foi notícia.\n\n"
    "Regras:\n"
    "- Usa apenas o que está nos títulos. Não acrescentes factos, números, causas, "
    "consequências nem lugares que não estejam lá. Se um título não diz onde "
    "aconteceu, o teu parágrafo também não pode dizer.\n"
    "- Não escrevas que não houve notícias de determinado país. Recebeste os "
    "títulos que há; sobre o que não recebeste, nada dizes.\n"
    "- NÃO enumeres uma notícia atrás da outra. Escolhe os assuntos com mais peso "
    "e agrupa os que se repetem: o parágrafo é uma leitura, não um índice.\n"
    "- Começa pelo assunto com mais peso e agrupa os que se repetem.\n"
    "- Escreve em português de Portugal, em registo institucional e neutro.\n"
    "- Não emitas juízos, não recomendes nada, não uses adjetivos valorativos.\n"
    "- Não uses expressões como 'as notícias indicam' ou 'segundo os títulos'.\n"
    "- Cada título vem precedido, entre parênteses retos, da publicação que o "
    "difundiu e do país onde essa publicação se edita.\n"
    "- ATENÇÃO: o país entre parênteses é o da PUBLICAÇÃO, não o do "
    "acontecimento. Um jornal angolano noticia factos do mundo inteiro. NUNCA "
    "escrevas 'Em Angola' só porque o título veio de um jornal angolano.\n"
    "- Só nomeias um país, uma cidade ou uma região se o nome constar do próprio "
    "título. Não estando lá, não digas onde foi. Inventar o lugar é o pior erro "
    "que podes cometer.\n"
    "- Querendo situar a proveniência, atribui-a à imprensa e não ao facto: "
    "'a imprensa angolana noticiou', 'segundo a imprensa espanhola'.\n"
    "- Não trates imprensa estrangeira como se falasse de Portugal.\n"
    "- Devolve apenas o parágrafo, sem título nem marcas de formatação."
)


def carregar(caminho):
    with open(caminho, encoding="utf-8") as origem:
        return json.load(origem).get("noticias", [])


def origem_da_fonte(n):
    """Portugal, lusofonia ou internacional — as mesmas três do painel."""
    d = (n.get("dominio") or "").lower().replace("www.", "")
    if not d:
        return "nacionais"
    if d.endswith(".pt") or any(d == x or d.endswith("." + x) for x in DOMINIOS_NACIONAIS):
        return "nacionais"
    if any(d.endswith(t) for t in DOMINIOS_LUSOFONOS):
        return "lusofonas"
    return "internacionais"


def do_periodo(noticias, area, periodo):
    limite = agora_lisboa() - timedelta(hours=HORAS.get(periodo, 24))
    saida = []
    for n in noticias:
        if n.get("area") != area or not n.get("data"):
            continue
        d = (n.get("dominio") or "").lower().replace("www.", "")
        if d and any(d == p or d.endswith("." + p) for p in PLATAFORMAS):
            continue
        try:
            if datetime.strptime(n["data"][:16], "%Y-%m-%d %H:%M") < limite:
                continue
        except ValueError:
            continue
        saida.append(n)
    saida.sort(key=lambda n: n.get("data", ""), reverse=True)
    return saida


def perguntar(endereco, chave, titulos, area, rotulo="", tempo_limite=60):
    """Uma chamada ao Amália, pela interface compatível com OpenAI."""
    lista = "\n".join(f"- [{f}] {t}" for f, t in titulos)
    corpo = {
        "model": MODELO,
        "messages": [
            {"role": "system", "content": INSTRUCAO},
            {"role": "user", "content": (f"Área governativa: {area}\n"
                                        f"Origem da imprensa: {rotulo or 'não especificada'}\n"
                                        f"Extensão pedida: um parágrafo {extensao(len(titulos))}.\n\n"
                                        f"Títulos:\n{lista}")},
        ],
        "temperature": 0.3,
        "max_tokens": 380,
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
    except ImportError as erro:
        sys.exit(f"Faltam bibliotecas ({erro}). Instale com:\n"
                 "  pip install llama-cpp-python huggingface-hub")

    print(f"A obter {ficheiro} de {repo}…", flush=True)
    try:
        caminho = hf_hub_download(repo_id=repo, filename=ficheiro)
    except Exception as erro:                                  # noqa: BLE001
        sys.exit(f"Não foi possível obter o modelo: {type(erro).__name__}: {erro}")
    print(f"A carregar o modelo ({os.path.getsize(caminho) / 1e9:.1f} GB)…", flush=True)

    # A memória do servidor é limitada: o modelo ocupa cerca de 5,6 GB e a
    # janela de contexto acresce a isso. Uma janela grande demais faz o sistema
    # interromper o processo sem explicação. Falhando, tenta-se com metade.
    for janela in (contexto, contexto // 2):
        try:
            _modelo_local = Llama(
                model_path=caminho,
                n_ctx=janela,
                n_threads=fios or (os.cpu_count() or 4),
                verbose=False,
            )
            print(f"Modelo carregado com janela de {janela} tokens.")
            return _modelo_local
        except Exception as erro:                              # noqa: BLE001
            print(f"Falhou com janela de {janela}: {type(erro).__name__}: {erro}")
    sys.exit("Não foi possível carregar o modelo.")


def extensao(n):
    """Quantas frases pedir, conforme o material disponível.

    Resumir cento e trinta títulos em duas frases não é síntese, é omissão; e
    pedir oito frases sobre três notícias obrigaria o modelo a encher.
    """
    if n >= 40:
        return "de sete a dez frases"
    if n >= 15:
        return "de cinco a sete frases"
    return "de três a cinco frases"


def perguntar_local(titulos, area, repo, ficheiro, rotulo=""):
    """A mesma pergunta, respondida pelo modelo carregado neste computador."""
    modelo = carregar_modelo_local(repo, ficheiro)
    lista = "\n".join(f"- [{f}] {t}" for f, t in titulos)
    resposta = modelo.create_chat_completion(
        messages=[
            {"role": "system", "content": INSTRUCAO},
            {"role": "user", "content": (f"Área governativa: {area}\n"
                                        f"Origem da imprensa: {rotulo or 'não especificada'}\n"
                                        f"Extensão pedida: um parágrafo {extensao(len(titulos))}.\n\n"
                                        f"Títulos:\n{lista}")},
        ],
        temperature=0.3,
        max_tokens=380,
    )
    return resposta["choices"][0]["message"]["content"].strip()


def juntar(pasta, saida):
    """Junta as sínteses parciais produzidas em paralelo.

    Cada área é tratada por um trabalho seu, porque uma área demora mais de vinte
    minutos e dezasseis, em sequência, não caberiam na manhã. Cada trabalho grava
    um ficheiro; este passo funde-os num só.
    """
    partes = sorted(f for f in os.listdir(pasta) if f.endswith(".json"))
    if not partes:
        sys.exit(f"Sem ficheiros parciais em {pasta}.")

    resultado = None
    for nome in partes:
        with open(os.path.join(pasta, nome), encoding="utf-8") as origem:
            d = json.load(origem)
        if resultado is None:
            resultado = {k: v for k, v in d.items() if k != "areas"}
            resultado["areas"] = {}
        resultado["areas"].update(d.get("areas", {}))

    # A hora é a da parte mais recente: é a que o relatório usa para se datar
    resultado["gerado"] = max(
        (json.load(open(os.path.join(pasta, n), encoding="utf-8")).get("gerado", "")
         for n in partes), default=resultado.get("gerado", ""))

    with open(saida, "w", encoding="utf-8") as destino:
        json.dump(resultado, destino, ensure_ascii=False, indent=1)
    print(f"{len(partes)} ficheiros juntos · {len(resultado['areas'])} áreas em {saida}")


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
    ap.add_argument("--apenas", default=None,
                    help="tratar apenas esta área — útil para um primeiro ensaio")
    ap.add_argument("--juntar", default=None,
                    help="pasta com sínteses parciais, a juntar num só ficheiro")
    ap.add_argument("--minimo", type=int, default=3,
                    help="notícias mínimas para valer a pena sintetizar")
    ap.add_argument("--maximo", type=int, default=35,
                    help="títulos a enviar por área, dos mais recentes")
    args = ap.parse_args()

    if args.juntar:
        juntar(args.juntar, args.saida)
        return

    chave = os.environ.get("AMALIA_CHAVE", "")
    if not args.local and (not args.endereco or not chave):
        print("Sem modo local nem ponto de acesso configurado. Nada a fazer.")
        return

    # A síntese acompanha a janela do relatório que a vai apresentar
    if args.periodo == "auto":
        args.periodo = "72h" if agora_lisboa().weekday() == 0 else "24h"
        print(f"Janela automática: {args.periodo}")

    if not os.path.exists(args.dados):
        sys.exit(f"Ficheiro de dados não encontrado: {args.dados}")

    noticias = carregar(args.dados)
    areas = sorted({n.get("area") for n in noticias if n.get("area")})

    if args.apenas:
        # Aceita várias áreas separadas por vírgula: "Finanças, Saúde, Justiça".
        # Antes tomava a linha inteira por um só nome, não encontrava nada e
        # terminava com erro — que foi o que sucedeu.
        pedidas = [_sem_acentos(x.strip()) for x in args.apenas.split(",") if x.strip()]
        escolhidas = [a for a in areas if any(p in _sem_acentos(a) for p in pedidas)]
        desconhecidas = [p for p in pedidas
                         if not any(p in _sem_acentos(a) for a in areas)]
        if desconhecidas:
            print(f"Não reconhecidas, ignoradas: {', '.join(desconhecidas)}")
        if not escolhidas:
            sys.exit(f"Nenhuma área corresponde a: {args.apenas}")
        areas = escolhidas
        print(f"Ensaio limitado a: {', '.join(areas)}")

    agora = agora_lisboa()
    resultado = {"gerado": agora.strftime("%Y-%m-%d %H:%M"),
                 "periodo": args.periodo, "modelo": MODELO,
                 "modo": "local" if args.local else "serviço", "areas": {}}

    contas = {"poucas": 0, "falhou": 0, "curta": 0, "escrita": 0}

    # Um parágrafo por origem: misturar o orçamento português com o cabo-verdiano
    # num só texto confunde quem lê, e a origem é justamente o que distingue as
    # duas notícias.
    for area in areas:
        doDia = do_periodo(noticias, area, args.periodo)
        if not doDia:
            print(f"  {area}: sem notícias no período")
            contas["poucas"] += 1
            continue

        print(f"  {area}: {len(doDia)} notícias no período")
        por_origem = {}

        for chave_origem, rotulo in ORIGENS:
            desta = [n for n in doDia if origem_da_fonte(n) == chave_origem]
            if len(desta) < args.minimo:
                if desta:
                    print(f"     {rotulo}: {len(desta)} notícias, abaixo do mínimo "
                          f"de {args.minimo} — sem parágrafo")
                contas["poucas"] += 1
                continue

            # A publicação segue com o título: é o que permite ao modelo dizer
            # de que país fala cada notícia, em vez de as apresentar sem lugar.
            # Publicação e país seguem com o título
            titulos = []
            for n in desta[: args.maximo]:
                fonte = n.get("fonte") or "publicação não identificada"
                pais = pais_da_fonte(n.get("dominio"))
                titulos.append((f"{fonte} · {pais}" if pais else fonte, n["titulo"]))
            inicio = time.monotonic()
            try:
                texto = (perguntar_local(titulos, area, args.repo, args.ficheiro, rotulo)
                         if args.local else
                         perguntar(args.endereco, chave, titulos, area, rotulo))
            except (urllib.error.URLError, KeyError, ValueError,
                    TimeoutError, RuntimeError) as erro:
                print(f"     {rotulo}: falhou ({type(erro).__name__}: {erro})")
                contas["falhou"] += 1
                continue

            texto = texto.strip().strip("*_` ")
            if len(texto) < 40:
                print(f"     {rotulo}: resposta demasiado curta ({len(texto)}), ignorada")
                contas["curta"] += 1
                continue

            por_origem[chave_origem] = {
                "rotulo": rotulo,
                "texto": texto,
                "noticias": len(desta),
            }
            contas["escrita"] += 1
            print(f"     {rotulo}: {len(desta)} notícias → {len(texto)} caracteres "
                  f"em {time.monotonic() - inicio:.0f}s")
            print(f"        {texto[:140]}{'…' if len(texto) > 140 else ''}")

        if por_origem:
            resultado["areas"][area] = {
                "noticias": len(doDia),
                "origens": por_origem,
            }

    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump(resultado, destino, ensure_ascii=False, indent=1)

    print(f"\nResumo: {contas['escrita']} escritas · {contas['poucas']} sem notícias "
          f"suficientes · {contas['falhou']} falhadas · {contas['curta']} descartadas "
          f"por serem curtas")
    print(f"{len(resultado['areas'])} sínteses gravadas em {args.saida} "
          f"({os.path.getsize(args.saida)} bytes)")
    if not resultado["areas"]:
        print("::warning::O ficheiro foi gravado sem qualquer síntese. "
              "Veja acima o motivo de cada área.")


if __name__ == "__main__":
    principal()
