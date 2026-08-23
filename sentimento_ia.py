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

# ── A INSTRUÇÃO ──────────────────────────────────────────────────────────────
# Reescrita depois de uma auditoria a 5 042 títulos já classificados (agosto de
# 2026). Duas medições motivaram cada regra:
#
#   · numa amostra de 40 títulos anotada à mão, a concordância era de 69%;
#   · em 1 196 pares do MESMO acontecimento noticiado por jornais diferentes, o
#     modelo dava tons diferentes em 25% dos casos.
#
# Os enganos não eram aleatórios: caíam em seis padrões, e cada um deles tem
# agora uma regra explícita, porque a instrução anterior deixava o caso em
# aberto e o modelo resolvia-o de maneira diferente de cada vez.
#
#   A. alertas e preocupações («devem preocupar», «alerta para») saíam neutros
#      — o acontecimento é o problema que se denuncia, e esse é negativo;
#   B. propostas e declarações («PSP defende criminalização») saíam positivas
#      — uma proposta ainda não é um facto;
#   C. consequências claras («cancela voos devido à greve») saíam neutras;
#   D. avanços úteis com uma palavra dura no título saíam negativos — o caso
#      «IA que prevê incêndios mais perigosos 16 dias antes» classificado como
#      negativo é o exemplo puro: o modelo agarrou-se a «incêndios»;
#   E. indicadores sem regra («descida do preço dos combustíveis») saíam
#      neutros por não se saber para que lado olhar;
#   F. títulos de opinião e títulos degenerados não tinham destino.
#
# NEUTRALIDADE, que aqui é requisito e não preferência: o tom é do
# ACONTECIMENTO, nunca do seu efeito político. Um facto mau é negativo quer
# favoreça quer prejudique quem governa. A instrução di-lo explicitamente
# porque um classificador que medisse «bom ou mau para o Governo» seria
# indefensável num organismo do Estado.
# Versão das regras de classificação. Sobe sempre que a INSTRUCAO mudar de
# forma que possa alterar resultados. Cada avaliação fica marcada com a versão
# que a produziu — sem isso não há maneira de saber o que já foi refeito e o
# que não foi, e uma reavaliação faseada torna-se um jogo às cegas: repetir uma
# corrida apagaria trabalho bom em vez de continuar de onde ia.
INSTRUCAO_VERSAO = 2

INSTRUCAO = (
    "És um classificador de tom noticioso para a administração pública "
    "portuguesa. Recebes uma lista numerada de notícias (título e, quando "
    "exista, o início do resumo). Para cada uma, classificas o TOM DO "
    "ACONTECIMENTO NOTICIADO:\n"
    "- positivo: facto favorável já concretizado ou decidido — melhoria, "
    "conquista, acordo fechado, apoio atribuído, indicador que melhora a vida "
    "das pessoas.\n"
    "- negativo: problema, crise, acidente, crime, conflito, degradação, "
    "perda, risco assinalado, acusação, ou consequência prejudicial para "
    "alguém.\n"
    "- neutro: anúncio de agenda, nomeação, informação factual sem carga, "
    "processo em curso sem desfecho, proposta ou intenção ainda por decidir, "
    "declaração de posição, pergunta ou debate sem facto novo.\n"
    "\n"
    "REGRAS PARA OS CASOS DUVIDOSOS:\n"
    "1. Quem alerta, critica, acusa ou denuncia um problema traz uma notícia "
    "NEGATIVA: o acontecimento é o problema, não o ato de falar. «X alerta "
    "para falta de meios» é negativo.\n"
    "2. Uma proposta, defesa de ideia ou intenção ainda não decidida é "
    "NEUTRA, por melhor que pareça. «Y defende a criação de Z» é neutro; "
    "«Z foi criado» é positivo.\n"
    "3. Classifica pela CONSEQUÊNCIA quando ela está no título: «cancela voos "
    "devido a greve» é negativo, porque quem viaja fica sem voo.\n"
    "4. Não te deixes levar por uma palavra dura isolada. Uma solução, um "
    "avanço ou uma prevenção são POSITIVOS mesmo que falem de um mal: "
    "«sistema que prevê incêndios com antecedência» é positivo; «campanha "
    "contra a violência» é positivo.\n"
    "5. Indicadores: melhora a vida de quem os sofre = positivo (preços a "
    "descer, desemprego a descer, salários a subir, listas de espera a "
    "encurtar); piora = negativo. Um número sem direção clara é neutro.\n"
    "6. Títulos de opinião, crónica, entrevista ou programa, e títulos "
    "demasiado curtos ou truncados para se perceber o que aconteceu: NEUTRO.\n"
    "7. Um acontecimento com dois lados classifica-se pelo que domina o "
    "título; se estiverem equilibrados, neutro.\n"
    "8. Morte de pessoa: negativo. Homenagem ou legado de alguém já falecido: "
    "neutro.\n"
    "\n"
    "Classificas o acontecimento, e nunca o efeito político: um facto mau é "
    "negativo quer favoreça quer prejudique o Governo, a oposição ou "
    "qualquer outra parte. Não avalias a qualidade do texto nem a orientação "
    "do jornal. Notícias estrangeiras seguem as mesmas regras.\n"
    "Na dúvida entre dois valores, escolhe neutro.\n"
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


def sincronizar_versoes_arquivo(pasta, avaliacoes):
    """Leva ao arquivo permanente as marcas de versão que só existem no
    ficheiro de trabalho.

    O arquivo é escrito em acréscimo e nunca reescrito, pelo que avaliações
    guardadas antes de a marca existir ficaram lá sem ela. Ao serem relidas
    pareciam antigas e voltavam à fila — refeitas vezes sem conta, sem nunca
    convergir. Esta passagem reescreve os meses uma única vez, acrescentando a
    versão às entradas que a têm no ficheiro de trabalho. Não altera nenhuma
    classificação: só a etiqueta que diz com que regras foi feita.
    """
    import gzip
    if not os.path.isdir(pasta):
        return 0
    marcadas = 0
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.jsonl.gz"))):
        # DEDUPLICAR pelo caminho. O arquivo é escrito em acréscimo, pelo que
        # uma notícia reavaliada deixa lá as duas versões — e, ao fim de
        # algumas reavaliações, o ficheiro tem várias vezes o tamanho do que
        # representa. A leitura já ficava com a última de cada ligação, que é
        # a boa; aqui gravamos só essa e o ficheiro volta ao tamanho real.
        ultimo = {}
        ordem = []
        linhas = 0
        with gzip.open(caminho, "rt", encoding="utf-8") as origem:
            for linha in origem:
                try:
                    r = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                lig = r.get("lig")
                if not lig:
                    continue
                linhas += 1
                if lig not in ultimo:
                    ordem.append(lig)
                ultimo[lig] = r
        registos = []
        for lig in ordem:
            r = ultimo[lig]
            conhecida = avaliacoes.get(lig)
            if conhecida and conhecida.get("v") and not r.get("v"):
                r["v"] = conhecida["v"]
                marcadas += 1
            registos.append(r)
        if linhas > len(registos):
            print(f"  {os.path.basename(caminho)}: {linhas} linhas → "
                  f"{len(registos)} (retirados {linhas - len(registos)} repetidos)")
        temporario = caminho + ".novo"
        with gzip.open(temporario, "wt", encoding="utf-8") as destino:
            for r in registos:
                destino.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(temporario, caminho)
    if marcadas:
        print(f"arquivo permanente: {marcadas} avaliações passaram a levar a "
              f"marca da versão com que foram feitas")
    return marcadas


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
                        # A versão vem com ela: é o que distingue uma avaliação
                        # já refeita de uma que ainda espera a sua vez.
                        if r.get("v"):
                            arquivadas[lig]["v"] = r["v"]
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
        registo = {"lig": lig, "s": v["s"], "d": v.get("d", "")}
        # A VERSÃO das regras vai para o arquivo permanente. Sem ela, uma
        # avaliação recente perdia a marca ao ser arquivada e, se o dia
        # voltasse a ser repescado, reaparecia como se fosse antiga — a ser
        # refeita outra vez, indefinidamente. A marca só serve para alguma
        # coisa se sobreviver ao arquivo.
        if v.get("v"):
            registo["v"] = v["v"]
        por_mes.setdefault(mes, []).append(registo)
    total = 0
    for mes, registos in sorted(por_mes.items()):
        with gzip.open(caminho_sentimento_mensal(pasta, mes), "at",
                       encoding="utf-8") as destino:
            for r in registos:
                destino.write(json.dumps(r, ensure_ascii=False) + "\n")
        total += len(registos)
    print(f"arquivo de sentimento: +{total} avaliações guardadas para sempre")
    return total


PALAVRAS_VAZIAS = frozenset("""
    para com que dos das nos nas pelo pela pelos pelas este esta estes estas
    aquele aquela seu sua seus suas mais menos como sobre entre desde apos
    ainda apenas tambem porque quando onde depois antes contra sem uma uns
    umas nao foi ser tem ter vai vao diz disse hoje ontem novo nova
""".split())


def palavras(titulo):
    """Palavras significativas de um título, sem acentos nem gramática vazia."""
    limpo = unicodedata.normalize("NFD", (titulo or "").lower())
    limpo = "".join(c for c in limpo if unicodedata.category(c) != "Mn")
    return {p for p in re.findall(r"[a-z0-9]+", limpo)
            if len(p) > 3 and p not in PALAVRAS_VAZIAS}


def agrupar_por_acontecimento(noticias, limiar=0.6):
    """Junta as peças do mesmo dia que contam o mesmo acontecimento.

    Porquê: metade das notícias recolhidas são o mesmo facto contado por vários
    órgãos, e classificá-las uma a uma produzia contradições visíveis no painel
    — «Tempos de espera nas urgências ultrapassam as 11 horas» saiu positivo no
    Público e negativo na RTP, com o mesmo título e no mesmo dia. Medido no
    arquivo: de 249 pares quase idênticos, só 65% tinham a mesma classificação.

    Agrupando, o acontecimento é avaliado UMA vez e o resultado vale para todas
    as peças que o contam. Ganha-se coerência, apanham-se de caminho as
    republicações do mesmo órgão com o título reescrito, e o modelo passa a ter
    menos cerca de um terço do trabalho.

    A semelhança é a de Jaccard entre as palavras significativas do título, no
    mesmo dia. O limiar de 0,6 foi escolhido por medição: abaixo disso começam
    a juntar-se peças sobre assuntos diferentes que partilham o vocabulário.
    """
    por_dia = {}
    for n in noticias:
        por_dia.setdefault((n.get("data") or "")[:10], []).append(n)

    grupos = []
    for _, itens in sorted(por_dia.items()):
        pendentes_dia = [(n, palavras(n.get("titulo"))) for n in itens]
        usados = [False] * len(pendentes_dia)
        for i, (n, w) in enumerate(pendentes_dia):
            if usados[i]:
                continue
            usados[i] = True
            grupo = [n]
            if w:
                for j in range(i + 1, len(pendentes_dia)):
                    if usados[j]:
                        continue
                    outro, w2 = pendentes_dia[j]
                    if not w2:
                        continue
                    if len(w & w2) / len(w | w2) >= limiar:
                        usados[j] = True
                        grupo.append(outro)
            grupos.append(grupo)
    return grupos


def ligacao(n):
    return n.get("ligacao") or (n.get("titulo") or "").lower()


def pendentes(noticias, avaliacoes, origem_da_fonte, dias, datas_extra=frozenset()):
    """Notícias nacionais ainda sem avaliação, uma por ligação, recentes
    primeiro. A ligação é a identidade: a mesma notícia marcada em duas
    áreas classifica-se uma só vez. As datas em `datas_extra` entram mesmo
    estando fora da janela — é por aí que se repescam dias antigos."""
    limite = (agora_lisboa() - timedelta(days=dias)).strftime("%Y-%m-%d")
    elegiveis, vistas = [], set()
    for n in sorted(noticias, key=lambda x: x.get("data", ""), reverse=True):
        lig = ligacao(n)
        if not lig or lig in vistas:
            continue
        vistas.add(lig)
        dia = (n.get("data") or "")[:10]
        if dia < limite and dia not in datas_extra:
            continue
        if origem_da_fonte(n.get("dominio") or "") != "nacionais":
            continue
        elegiveis.append(n)

    # Um pedido por ACONTECIMENTO: se qualquer peça do grupo já está avaliada,
    # o grupo inteiro herda essa avaliação e não volta ao modelo.
    fila = []
    for grupo in agrupar_por_acontecimento(elegiveis):
        if any(ligacao(x) in avaliacoes for x in grupo):
            continue
        principal_do_grupo = grupo[0]
        principal_do_grupo["_grupo"] = [ligacao(x) for x in grupo]
        fila.append(principal_do_grupo)
    return fila


def compor_lote(lote):
    """Apresenta as notícias ao modelo. Usa «[N]» como marcador, distinto do
    formato de resposta pedido («N=valor»), para o modelo não ser tentado a
    ecoar a entrada e o parsing não confundir título com classificação."""
    linhas = []
    for i, n in enumerate(lote, start=1):
        resumo = (n.get("resumo") or "").strip()
        # 140 caracteres cortavam 93% dos resumos a meio (a mediana anda pelos
        # 198): o modelo via o princípio da frase e perdia a parte onde muitas
        # vezes está o que decide o tom. 280 cobrem a grande maioria inteira,
        # ao custo de umas centenas de tokens por lote. Um título sem resumo
        # continua a ser classificado só pelo título, e é bom lembrar que é o
        # caso de 29% das notícias — daí a ressalva de que o indicador lê o
        # que a notícia mostra à entrada, e não a peça toda.
        extra = f" — {resumo[:280]}" if resumo else ""
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
    # Além das áreas, um bloco "total" por dia com as notícias DISTINTAS: uma
    # peça que satisfaz três áreas conta em cada uma delas, pelo que somar as
    # áreas dá marcações e inflacionava a distribuição do painel. A identidade
    # é título+fonte, a mesma do arquivo e do reconstruir_series.py — sem este
    # bloco, os dias que o sentimento reescreve ficavam noutra base que os dias
    # fechados pelo reconstruir, e o mesmo gráfico misturava as duas contagens.
    distintas = {}
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

        chave = ((n.get("titulo") or "").strip().lower(),
                 (n.get("fonte") or n.get("dominio") or "").strip().lower())
        distintas.setdefault(dia, {})[chave] = (
            avaliacao.get("s") if avaliacao and avaliacao.get("s") in VALORES else None)

    recontados = set(por_dia)
    serie["dias"] = [d for d in serie["dias"] if d.get("data") not in recontados]
    for dia, areas in por_dia.items():
        total = {"nacionais": 0, "avaliadas": 0,
                 "positivo": 0, "neutro": 0, "negativo": 0}
        for tom in distintas.get(dia, {}).values():
            total["nacionais"] += 1
            if tom:
                total["avaliadas"] += 1
                total[tom] += 1
        serie["dias"].append({"data": dia, "total": total, "areas": areas})
    serie["dias"].sort(key=lambda d: d.get("data", ""))
    serie["atualizado"] = agora_lisboa().strftime("%Y-%m-%d %H:%M")

    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(serie, destino, ensure_ascii=False, indent=1)
    return len(serie["dias"])


def harmonizar(args, sintese, repo, ficheiro, noticias, avaliacoes,
               conhecidas, arquivadas, recolha):
    """Repõe a coerência no que já foi classificado.

    O agrupamento por acontecimento evita contradições NOVAS, mas não desfaz as
    antigas: um grupo cujas peças já estão todas avaliadas nunca volta à fila.
    Isto passa por esse passivo. Onde há maioria, aplica-se a maioria — não é
    preciso o modelo. Onde há empate (a maioria dos casos, porque quase todos
    os grupos são pares), pergunta-se uma vez e o resultado vale para o grupo.
    """
    nacionais = [n for n in noticias
                 if recolha.origem_da_fonte(n.get("dominio") or "") == "nacionais"]
    vistos, unicos = set(), []
    for n in nacionais:
        if ligacao(n) not in vistos:
            vistos.add(ligacao(n))
            unicos.append(n)

    divergentes, corrigidos, porModelo = [], 0, []
    for grupo in agrupar_por_acontecimento(unicos):
        toms = [conhecidas[ligacao(x)]["s"] for x in grupo if ligacao(x) in conhecidas]
        if len(set(toms)) <= 1:
            continue
        divergentes.append(grupo)
        contagem = {}
        for tom in toms:
            contagem[tom] = contagem.get(tom, 0) + 1
        ordenado = sorted(contagem.items(), key=lambda kv: -kv[1])
        if len(ordenado) > 1 and ordenado[0][1] > ordenado[1][1]:
            aplicar(grupo, ordenado[0][0], avaliacoes, conhecidas, arquivadas)
            corrigidos += 1
        else:
            porModelo.append(grupo)

    print(f"harmonizar: {len(divergentes)} acontecimentos com avaliações "
          f"divergentes; {corrigidos} resolvidos por maioria, "
          f"{len(porModelo)} empatados")

    for inicio in range(0, len(porModelo), args.lote):
        bloco = porModelo[inicio:inicio + args.lote]
        lote = [g[0] for g in bloco]
        try:
            resposta = perguntar_local(sintese, lote, repo, ficheiro) if args.local \
                else perguntar_servico(args.endereco, os.environ.get("AMALIA_CHAVE", ""),
                                       lote, sintese.MODELO)
        except Exception as erro:                              # noqa: BLE001
            print(f"  lote falhou ({type(erro).__name__}: {erro}) — fica como está")
            continue
        lidas = interpretar(resposta, len(lote))
        for i, grupo in enumerate(bloco, start=1):
            if i in lidas:
                aplicar(grupo, lidas[i], avaliacoes, conhecidas, arquivadas)
                corrigidos += 1

    if not corrigidos:
        print("harmonizar: nada a corrigir")
        return

    agora = agora_lisboa()
    with open(args.saida, "w", encoding="utf-8") as destino:
        json.dump({
            "gerado": agora.strftime("%Y-%m-%d %H:%M"),
            "modelo": sintese.MODELO,
            "estado": "em validação — avaliações automáticas, leitura humana em curso",
            "criterio": ("Tom do acontecimento noticiado (positivo, neutro, "
                         "negativo), comunicação social nacional apenas, uma avaliação "
                         "por acontecimento."),
            "avaliacoes": avaliacoes,
        }, destino, ensure_ascii=False, indent=1)

    # O arquivo é acrescentado, nunca reescrito: a linha nova fica depois da
    # antiga e a leitura fica com a última, que é a corrigida.
    if args.arquivo_sentimento:
        arquivar_sentimento(args.arquivo_sentimento, conhecidas, {})
    if args.serie:
        atualizar_serie(args.serie, noticias, conhecidas,
                        recolha.origem_da_fonte, args.dias)
    print(f"harmonizar: {corrigidos} acontecimentos passaram a ter uma só avaliação")


def aplicar(grupo, tom, avaliacoes, conhecidas, arquivadas, origem_versao=None):
    """Escreve o mesmo tom em todas as peças do acontecimento."""
    for x in grupo:
        lig = ligacao(x)
        # Herda também a VERSÃO: uma peça que recebe o tom de um acontecimento
        # já reavaliado conta como reavaliada, e uma que herde de uma avaliação
        # antiga fica marcada como antiga — senão a contagem do que falta
        # mentiria nos dois sentidos.
        valor = {"s": tom, "d": (x.get("data") or "")[:10]}
        if isinstance(origem_versao, int):
            valor["v"] = origem_versao
        avaliacoes[lig] = valor
        conhecidas[lig] = valor
        arquivadas.pop(lig, None)


def auditar(args, sintese, repo, ficheiro, noticias, conhecidas, recolha):
    """Mede quanto o modelo concorda CONSIGO PRÓPRIO.

    Sem isto não se sabe se as classificações divergentes vêm de o critério ser
    ambíguo ou de o modelo variar entre corridas — e são problemas diferentes:
    o primeiro corrige-se no prompt, o segundo só com uma segunda opinião ou
    com um modelo melhor. Reavalia uma amostra do que já está classificado, com
    o mesmo prompt e a mesma temperatura, e compara. Não grava nada.
    """
    amostra = [n for n in noticias
               if recolha.origem_da_fonte(n.get("dominio") or "") == "nacionais"
               and ligacao(n) in conhecidas]
    vistos, unicos = set(), []
    for n in sorted(amostra, key=lambda x: x.get("data", ""), reverse=True):
        if ligacao(n) in vistos:
            continue
        vistos.add(ligacao(n))
        unicos.append(n)
    amostra = unicos[:args.auditar]
    if not amostra:
        print("auditoria: nada classificado para reavaliar")
        return

    print(f"auditoria: a reavaliar {len(amostra)} notícias já classificadas, "
          f"em lotes de {args.lote}")
    iguais, diferentes, mudanca = 0, 0, {}
    for inicio in range(0, len(amostra), args.lote):
        lote = amostra[inicio:inicio + args.lote]
        try:
            resposta = perguntar_local(sintese, lote, repo, ficheiro) if args.local \
                else perguntar_servico(args.endereco, os.environ.get("AMALIA_CHAVE", ""),
                                       lote, sintese.MODELO)
        except Exception as erro:                              # noqa: BLE001
            print(f"  lote falhou ({type(erro).__name__}: {erro})")
            continue
        lidas = interpretar(resposta, len(lote))
        for i, n in enumerate(lote, start=1):
            if i not in lidas:
                continue
            antes = conhecidas[ligacao(n)]["s"]
            agora = lidas[i]
            if antes == agora:
                iguais += 1
            else:
                diferentes += 1
                mudanca[(antes, agora)] = mudanca.get((antes, agora), 0) + 1
                if diferentes <= 8:
                    print(f"    {antes} → {agora}: {(n.get('titulo') or '')[:66]}")

    total = iguais + diferentes
    if not total:
        print("auditoria: nenhuma resposta legível")
        return
    print(f"\nauditoria: {iguais} de {total} iguais "
          f"({100 * iguais / total:.0f}% de concordância consigo próprio)")
    for (a, b), q in sorted(mudanca.items(), key=lambda kv: -kv[1]):
        print(f"  {a} → {b}: {q}")
    print("Nada foi gravado.")


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
    ap.add_argument("--marcar-versao-desde", default=None, metavar="AAAA-MM-DD",
                    help="Marca como sendo da versão atual as avaliações do "
                         "ficheiro de trabalho a partir desta data, SEM as "
                         "reavaliar. Serve uma vez só: para não deitar fora o "
                         "trabalho de corridas feitas com as regras novas antes "
                         "de existir a marca de versão.")
    ap.add_argument("--refazer-desde", default=None, metavar="AAAA-MM-DD",
                    help="Descarta as avaliações a partir desta data e volta a "
                         "classificar com a instrução atual. Serve para aplicar "
                         "ao passado uma revisão das regras: sem isto, uma "
                         "notícia já avaliada nunca mais volta à fila, e a "
                         "correção só valeria daí para a frente.")
    ap.add_argument("--harmonizar", action="store_true",
                    help="repõe a coerência no que JÁ está classificado: "
                         "acontecimentos com avaliações divergentes passam a ter "
                         "uma só (a maioria; empates voltam ao modelo)")
    ap.add_argument("--auditar", type=int, default=0, metavar="N",
                    help="reavalia N notícias já classificadas e mede quanto o "
                         "modelo concorda consigo próprio; não grava nada")
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

    # Marcação retroativa da versão. Uma reavaliação feita antes de existir o
    # campo «v» produziu avaliações boas mas indistinguíveis das antigas: sem
    # isto, a corrida seguinte refá-las-ia — horas de computação deitadas fora.
    # Aplica-se uma vez, com a data a partir da qual se sabe que o ficheiro de
    # trabalho só tem avaliações já feitas com as regras atuais.
    if getattr(args, "marcar_versao_desde", None):
        marcadas = 0
        for lig, v in avaliacoes.items():
            if (v.get("d") or "") >= args.marcar_versao_desde and "v" not in v:
                v["v"] = INSTRUCAO_VERSAO
                marcadas += 1
        print(f"marcação: {marcadas} avaliações de {args.marcar_versao_desde} em "
              f"diante passam a contar como versão {INSTRUCAO_VERSAO} "
              f"(não foram reavaliadas — só marcadas)")
        # E leva-se a marca ao arquivo permanente, senão ela perde-se assim que
        # a avaliação sair da janela de trabalho.
        sincronizar_versoes_arquivo(args.arquivo_sentimento, avaliacoes)

    # Reavaliação retroativa: quando as REGRAS mudam, o que já foi classificado
    # continua a valer as regras antigas — e uma notícia avaliada nunca volta à
    # fila. Descartar as avaliações a partir de uma data devolve-as à fila e a
    # instrução atual aplica-se ao passado. É a única forma de uma revisão do
    # classificador alcançar a série já publicada, em vez de valer só daí para
    # a frente e deixar um degrau no meio dos dados.
    if getattr(args, "refazer_desde", None):
        desde = args.refazer_desde
        # SÓ se descarta o que se consegue voltar a avaliar. Uma notícia cuja
        # data já saiu da janela de trabalho e não foi repescada com
        # --recuperar não está aqui para ser reclassificada: apagar-lhe a
        # avaliação não a corrigiria, apagá-la-ia. O que fica de fora mantém a
        # avaliação antiga e o aviso di-lo, para não haver ilusão de que a
        # revisão alcançou tudo.
        disponiveis = {ligacao(n) for n in noticias if ligacao(n)}

        def refazer(lig, v):
            """Volta à fila? Só o que é do período, está disponível e ainda não
            foi classificado pela versão atual das regras.

            Esta última condição é o que torna a reavaliação RETOMÁVEL: correr
            outra vez continua de onde ia, em vez de deitar fora o que a corrida
            anterior já fez. Sem ela, uma reavaliação que não coubesse no tempo
            disponível nunca terminaria — cada tentativa apagaria a anterior."""
            return ((v.get("d") or "") >= desde
                    and lig in disponiveis
                    and v.get("v") != INSTRUCAO_VERSAO)

        doPeriodo = [lig for lig, v in avaliacoes.items()
                     if (v.get("d") or "") >= desde]
        jaFeitas = sum(1 for lig in doPeriodo
                       if avaliacoes[lig].get("v") == INSTRUCAO_VERSAO)
        avaliacoes = {lig: v for lig, v in avaliacoes.items() if not refazer(lig, v)}
        arquivadas = {lig: v for lig, v in arquivadas.items() if not refazer(lig, v)}
        volta = sum(1 for lig in doPeriodo
                    if lig in disponiveis and lig not in avaliacoes)
        print(f"refazer (regras v{INSTRUCAO_VERSAO}): {volta} avaliações voltam à "
              f"fila de {desde} em diante")
        if jaFeitas:
            print(f"  ({jaFeitas} já estavam classificadas pelas regras atuais "
                  f"e ficam como estão — a reavaliação continua de onde ia)")
        fora = len(doPeriodo) - jaFeitas - volta
        if fora > 0:
            print(f"  ({fora} não estão na janela de trabalho — use --recuperar "
                  f"para as trazer do arquivo mensal)")

    # Para saber o que falta e para reconstruir a série, vale tudo o que já se
    # sabe: a janela de trabalho mais o arquivo de sempre.
    conhecidas = dict(arquivadas)
    conhecidas.update(avaliacoes)

    if args.harmonizar:
        harmonizar(args, sintese, repo, ficheiro, noticias, avaliacoes,
                   conhecidas, arquivadas, recolha)
        return

    if args.auditar:
        auditar(args, sintese, repo, ficheiro, noticias, conhecidas, recolha)
        return

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

    # Peças que chegaram depois de o acontecimento já ter sido avaliado herdam
    # a avaliação sem passar pelo modelo — é a mesma coerência, aplicada ao que
    # a recolha traz mais tarde.
    herdadas = 0
    for grupo in agrupar_por_acontecimento(
            [n for n in noticias
             if recolha.origem_da_fonte(n.get("dominio") or "") == "nacionais"]):
        conhecido = next((conhecidas[ligacao(x)] for x in grupo
                          if ligacao(x) in conhecidas), None)
        if not conhecido:
            continue
        for x in grupo:
            if ligacao(x) not in conhecidas:
                avaliacoes[ligacao(x)] = conhecido
                conhecidas[ligacao(x)] = conhecido
                herdadas += 1
    if herdadas:
        print(f"  {herdadas} peças herdaram a avaliação do seu acontecimento")

    # O ficheiro de trabalho tem de ficar completo para os dias que mostra: é
    # dele que o RADAR lê o sentimento, e ele não conhece o arquivo permanente.
    # Numa reavaliação faseada isto é o que evita o pior dos mundos — a
    # evolução, que soma tudo o que se sabe, a dizer 100% avaliado enquanto o
    # radar, que só lê este ficheiro, diz 35%. As avaliações que ainda não
    # foram refeitas voltam com o valor antigo, e serão substituídas pelo novo
    # quando lhes chegar a vez.
    repostas = 0
    for n in noticias:
        lig = ligacao(n)
        if lig and lig not in avaliacoes and lig in conhecidas:
            avaliacoes[lig] = conhecidas[lig]
            repostas += 1
    if repostas:
        print(f"  {repostas} avaliações repostas do arquivo permanente para o "
              f"ficheiro de trabalho (aguardam a sua vez de serem refeitas)")

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
            valor = {"s": lidas[i], "d": (n.get("data") or "")[:10],
                     "v": INSTRUCAO_VERSAO}
            for lig in n.get("_grupo") or [ligacao(n)]:
                avaliacoes[lig] = valor
                conhecidas[lig] = valor
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
