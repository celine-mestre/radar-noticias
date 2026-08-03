#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Notícias — relatório diário por email
Secretaria-Geral do Governo · Unidade de Pesquisa e Estatísticas

Lê o ficheiro de dados produzido pela recolha e escreve um relatório em HTML,
pronto a ser enviado como corpo de mensagem. Não envia nada: o envio é feito
pelo fluxo de trabalho, que tem as credenciais.

Utilização:
    python relatorio_email.py --area saude
    python relatorio_email.py --area saude --periodo 24h --saida relatorio.html
    python relatorio_email.py --areas saude,justica,financas
    python relatorio_email.py --todas --assunto-para assunto.txt
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta

VERDE, AZUL, DOURADO, TEAL, VERMELHO = "#0E7433", "#2B5683", "#BE9C54", "#266B73", "#D02117"

# Sem imagem no cabeçalho: em correio, as imagens são bloqueadas por
# predefinição na maioria dos clientes. A identidade faz-se com tipografia e
# com o azul institucional, que qualquer cliente apresenta sempre.
CINZA_TEXTO, CINZA_SUAVE, BORDA = "#171715", "#5b6068", "#e2e8f0"

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

ROTULO_PERIODO = {"24h": "últimas 24 horas", "48h": "últimas 48 horas",
                  "72h": "últimas 72 horas", "7d": "últimos 7 dias",
                  "30d": "últimos 30 dias"}
HORAS = {"24h": 24, "48h": 48, "72h": 72, "7d": 168, "30d": 720}

COR_GRUPO = {
    "Estado e soberania": AZUL,
    "Economia, finanças e território": DOURADO,
    "Sociedade e bem-estar": VERDE,
    "Ambiente, energia e recursos naturais": TEAL,
}

DOMINIOS_NACIONAIS = (
    "noticiasaominuto.com", "theportugalnews.com", "lusa.pt", "cnnportugal.iol.pt",
    "iol.pt", "eco.sapo.pt", "sapo.pt", "impresa.pt", "medialivre.pt",
)


def sem_acentos(t):
    return unicodedata.normalize("NFD", (t or "").lower()).encode("ascii", "ignore").decode()


DOMINIOS_LUSOFONOS = (".ao", ".mz", ".cv", ".st", ".gw", ".tl", ".br")

# Plataformas que não são publicações noticiosas. O corpus é de imprensa: se algo
# delas estiver no arquivo — de recolhas antigas, ou por engano —, não entra no
# relatório. O painel já as descartava; faltava fazer o mesmo aqui.
PLATAFORMAS = (
    "instagram.com", "facebook.com", "fb.com", "x.com", "twitter.com", "tiktok.com",
    "youtube.com", "youtu.be", "linkedin.com", "reddit.com", "threads.net", "threads.com",
    "bsky.app", "t.me", "telegram.me", "whatsapp.com", "pinterest.com", "tumblr.com",
    "flipboard.com", "medium.com", "substack.com", "blogspot.com", "wordpress.com",
)


def e_plataforma(n):
    d = (n.get("dominio") or "").lower().replace("www.", "")
    if not d:
        return False
    return any(d == p or d.endswith("." + p) or d.startswith(p) for p in PLATAFORMAS)

ETIQUETA_ORIGEM = {
    "nacionais": ("Portugal", "#0E7433"),
    "lusofonas": ("Lusofonia", "#BE9C54"),
    "internacionais": ("Internacional", "#266B73"),
}

# Uma síntese mais velha do que isto já não descreve o que a lista mostra. Oito
# horas cobrem folgadamente o intervalo entre a escrita da manhã, às 08h22, e o
# envio das 09h17 — e impedem que uma síntese da véspera à noite passe por atual.
MAX_IDADE_SINTESE = 8

ROTULO_ORIGENS = {
    frozenset({"nacionais"}): "imprensa de Portugal",
    frozenset({"lusofonas"}): "imprensa da lusofonia",
    frozenset({"internacionais"}): "imprensa internacional",
    frozenset({"nacionais", "lusofonas"}): "imprensa de Portugal e da lusofonia",
}


def origem_da_fonte(n):
    """Portugal, lusofonia ou internacional — as três origens do painel."""
    d = (n.get("dominio") or "").lower().replace("www.", "")
    if not d:
        return "nacionais"
    if d.endswith(".pt") or any(d == x or d.endswith("." + x) for x in DOMINIOS_NACIONAIS):
        return "nacionais"
    if any(d.endswith(t) for t in DOMINIOS_LUSOFONOS):
        return "lusofonas"
    return "internacionais"


def carregar(caminho):
    with open(caminho, encoding="utf-8") as origem:
        return json.load(origem).get("noticias", [])


def filtrar(noticias, area, periodo, origens):
    """`origens` é o conjunto de origens a manter, ou None para todas."""
    limite = None
    if periodo in HORAS:
        limite = datetime.now() - timedelta(hours=HORAS[periodo])

    saida = []
    for n in noticias:
        if area and n.get("area") != area:
            continue
        if e_plataforma(n):
            continue
        if origens and origem_da_fonte(n) not in origens:
            continue
        if limite and n.get("data"):
            try:
                if datetime.strptime(n["data"][:16], "%Y-%m-%d %H:%M") < limite:
                    continue
            except ValueError:
                pass
        saida.append(n)

    saida.sort(key=lambda n: n.get("data", ""), reverse=True)
    return saida


def endereco_seguro(u):
    """Só endereços web: um feed com "javascript:..." não deve chegar ao leitor."""
    limpo = str(u or "").strip()
    return limpo if re.match(r"^https?://", limpo, re.I) else ""


def esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def contar(noticias, chave):
    contagem = {}
    for n in noticias:
        v = n.get(chave) or "sem indicação"
        contagem[v] = contagem.get(v, 0) + 1
    return sorted(contagem.items(), key=lambda x: -x[1])


def bloco_sintese(sintese, escrita_em="", origens=None):
    """Síntese redigida pelo Amália: um parágrafo por origem de imprensa.

    Separar Portugal, lusofonia e imprensa internacional evita o efeito que se
    notava antes — o orçamento português e o cabo-verdiano descritos no mesmo
    texto, como se fossem a mesma matéria.

    A síntese é escrita mais cedo do que o relatório é enviado, pelo que se
    declara a hora: quem lê fica a saber que as notícias mais recentes da lista
    podem não estar refletidas nos parágrafos.
    """
    if not sintese:
        return ""

    hora = f" · escrita às {escrita_em[11:16]}" if len(escrita_em) >= 16 else ""

    # Ficheiros gerados antes da divisão por origem trazem um único texto.
    # Continuam a ser apresentados, sem etiqueta, até serem substituídos.
    if not sintese.get("origens"):
        if not sintese.get("texto"):
            return ""
        corpo = f"""
          <div style="font:400 14px Arial,sans-serif;color:{CINZA_TEXTO};line-height:1.6;
                      padding-top:6px">{esc(sintese['texto'])}</div>"""
        return f"""
    <tr><td style="padding:14px 24px 6px">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
             style="border-left:3px solid {DOURADO};background:#fdfbf6">
        <tr><td style="padding:12px 16px">
          <div style="font:600 10px Arial,sans-serif;color:{DOURADO};letter-spacing:1.2px;
                      text-transform:uppercase">Síntese redigida · Amália{hora}</div>
          {corpo}
          <div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:10px;line-height:1.5">
            Texto gerado automaticamente a partir dos títulos abaixo, sem acesso a outras
            fontes. Serve de primeira leitura e não dispensa a consulta das notícias.
          </div>
        </td></tr>
      </table>
    </td></tr>"""

    partes = []
    for chave in ("nacionais", "lusofonas", "internacionais"):
        if origens and chave not in origens:
            continue
        x = sintese["origens"].get(chave)
        if not x:
            continue
        rotulo, cor_o = ETIQUETA_ORIGEM[chave]
        partes.append(f"""
          <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
                 style="margin-top:10px"><tr>
            <td>
              <span style="font:600 9px Arial,sans-serif;color:{cor_o};letter-spacing:.6px;
                           text-transform:uppercase;border:1px solid {cor_o};border-radius:3px;
                           padding:1px 5px">{rotulo}</span>
              <span style="font:400 11px Arial,sans-serif;color:#8a9098;padding-left:6px">{x['noticias']} notícias</span>
              <div style="font:400 14px Arial,sans-serif;color:{CINZA_TEXTO};line-height:1.6;
                          padding-top:5px">{esc(x['texto'])}</div>
            </td>
          </tr></table>""")

    if not partes:
        return ""
    corpo = "".join(partes)
    return f"""
    <tr><td style="padding:14px 24px 6px">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
             style="border-left:3px solid {DOURADO};background:#fdfbf6">
        <tr><td style="padding:12px 16px">
          <div style="font:600 10px Arial,sans-serif;color:{DOURADO};letter-spacing:1.2px;
                      text-transform:uppercase">Síntese redigida · Amália{hora}</div>
          {corpo}
          <div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:10px;line-height:1.5">
            Textos gerados automaticamente a partir dos títulos abaixo, sem acesso a outras
            fontes, e separados pela origem da imprensa. Servem de primeira leitura e não
            dispensam a consulta das notícias.
          </div>
        </td></tr>
      </table>
    </td></tr>"""


def bloco_area(nome, noticias, cor, sintese=None, escrita_em="", origens=None):
    """Uma secção por área governativa, com as notícias agrupadas por dia."""
    if not noticias:
        return f"""
    <tr><td style="padding:18px 24px 6px">
      <div style="border-left:3px solid {cor};padding-left:12px">
        <div style="font:600 15px Arial,sans-serif;color:{CINZA_TEXTO}">{esc(nome)}</div>
        <div style="font:400 13px Arial,sans-serif;color:{CINZA_SUAVE};padding-top:4px">
          Sem notícias no período.</div>
      </div>
    </td></tr>"""

    por_dia = {}
    for n in noticias:
        dia = (n.get("data") or "")[:10] or "sem data"
        por_dia.setdefault(dia, []).append(n)

    hoje = datetime.now().strftime("%Y-%m-%d")

    def rotulo(d):
        if d == hoje:
            return "Hoje"
        if d == "sem data":
            return "Sem data"
        ano, mes, dia = d.split("-")
        return f"{int(dia)} de {MESES[int(mes) - 1]}"

    partes = [f"""
    <tr><td style="padding:20px 24px 4px">
      <div style="border-left:3px solid {cor};padding-left:12px">
        <div style="font:600 15px Arial,sans-serif;color:{CINZA_TEXTO}">{esc(nome)}</div>
        <div style="font:400 12px Arial,sans-serif;color:{CINZA_SUAVE};padding-top:3px">
          {len(noticias)} {'notícia' if len(noticias) == 1 else 'notícias'} ·
          {len(contar(noticias, 'fonte'))} {'publicação' if len(contar(noticias, 'fonte')) == 1 else 'publicações'}</div>
      </div>
    </td></tr>""", bloco_sintese(sintese, escrita_em, origens)]

    for dia in sorted(por_dia, reverse=True):
        partes.append(f"""
    <tr><td style="padding:14px 24px 4px">
      <div style="font:600 10px Arial,sans-serif;color:{CINZA_SUAVE};letter-spacing:1.2px;
                  text-transform:uppercase;border-bottom:1px solid {BORDA};padding-bottom:5px">
        {rotulo(dia)} · {len(por_dia[dia])}</div>
    </td></tr>""")

        for n in por_dia[dia]:
            hora = (n.get("data") or "")[11:16] or "—"
            resumo = n.get("resumo") or ""
            if len(resumo) > 190:
                resumo = resumo[:190].rsplit(" ", 1)[0] + "…"
            rotulo_origem, cor_origem = ETIQUETA_ORIGEM[origem_da_fonte(n)]
            miniatura = (f"""
        <td width="76" valign="top" style="padding-right:12px">
          <img src="{esc(endereco_seguro(n.get('imagem')))}" width="72" height="54" alt="" referrerpolicy="no-referrer"
               style="display:block;width:72px;height:54px;object-fit:cover;border-radius:4px">
        </td>""" if endereco_seguro(n.get("imagem")) else "")
            partes.append(f"""
    <tr><td style="padding:9px 24px;border-bottom:1px solid #f1f4f7">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>
        <td width="44" valign="top" style="font:400 12px Arial,sans-serif;color:{CINZA_SUAVE};padding-top:2px">{hora}</td>{miniatura}
        <td valign="top">
          <a href="{esc(endereco_seguro(n.get('ligacao')) or '#')}" style="font:400 14px Arial,sans-serif;color:{CINZA_TEXTO};
             text-decoration:none;line-height:1.4">{esc(n.get('titulo'))}</a>
          {f'<div style="font:400 12px Arial,sans-serif;color:{CINZA_SUAVE};padding-top:3px;line-height:1.45">{esc(resumo)}</div>' if resumo else ''}
          <div style="padding-top:5px">
            <span style="font:400 11px Arial,sans-serif;color:#8a9098">{esc(n.get('fonte'))}</span>
            <span style="font:600 9px Arial,sans-serif;color:{cor_origem};letter-spacing:.6px;
                         text-transform:uppercase;border:1px solid {cor_origem};border-radius:3px;
                         padding:1px 5px;margin-left:7px">{rotulo_origem}</span>
          </div>
        </td>
      </tr></table>
    </td></tr>""")

    return "".join(partes)


def ligacao_painel(endereco, areas):
    """Convite a abrir o painel, para refazer a pesquisa ou alargar o período."""
    if not endereco:
        return ""
    uma = len(areas) == 1
    return f"""
  <tr><td style="padding:18px 24px 22px;background:#fbfcfd;border-top:1px solid {BORDA}">
    <div style="font:400 13px Arial,sans-serif;color:{CINZA_SUAVE};line-height:1.55;padding-bottom:12px">
      Para refazer esta pesquisa com outras palavras-chave, alargar o período, comparar
      com {"outras áreas" if uma else "outros períodos"} ou exportar para Excel, abra o painel:
    </div>
    <a href="{esc(endereco)}" style="display:inline-block;background:{VERDE};color:#ffffff;
       font:600 14px Arial,sans-serif;text-decoration:none;padding:11px 22px;border-radius:6px">
       Abrir o Radar de Notícias</a>
    <div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:10px">{esc(endereco)}</div>
  </td></tr>"""


def carregar_sinteses(caminho="sinteses.json", periodo=""):
    """Sínteses do Amália, se existirem e se ainda descreverem este período.

    Uma síntese escrita ontem, ou sobre outra janela temporal, fala de notícias
    que não estão na lista — e quem lê fica com a impressão de que o relatório
    se contradiz. Nesses casos é preferível não a apresentar.
    """
    if not os.path.exists(caminho):
        print(f"Síntese: ficheiro {caminho} não existe — relatório sai sem parágrafo.")
        return {}, ""
    try:
        with open(caminho, encoding="utf-8") as origem:
            d = json.load(origem)
    except (json.JSONDecodeError, OSError) as erro:
        print(f"Síntese: {caminho} ilegível ({erro}).")
        return {}, ""

    print(f"Síntese: ficheiro de {d.get('gerado', '?')}, janela {d.get('periodo', '?')}, "
          f"{len(d.get('areas', {}))} área(s).")

    gerado = d.get("gerado", "")
    if periodo and d.get("periodo") and d["periodo"] != periodo:
        print(f"Síntese ignorada: foi escrita sobre {d['periodo']}, o relatório é de {periodo}.")
        return {}, ""

    # A idade conta-se em horas, não em dias de calendário: uma síntese escrita
    # às 23h e um relatório enviado à 01h estão a duas horas de distância, mas
    # em dias diferentes — e a regra anterior descartava-a por isso.
    try:
        idade = (datetime.now() - datetime.strptime(gerado[:16], "%Y-%m-%d %H:%M"))
        horas = idade.total_seconds() / 3600
    except (ValueError, TypeError):
        print("Síntese ignorada: data de geração ilegível.")
        return {}, ""

    if horas > MAX_IDADE_SINTESE:
        print(f"Síntese ignorada: foi escrita há {horas:.0f} horas, "
              f"acima do limite de {MAX_IDADE_SINTESE}.")
        return {}, ""

    print(f"Síntese aceite: escrita há {horas:.0f} hora(s), "
          f"{len(d.get('areas', {}))} área(s) com parágrafo.")
    return d.get("areas", {}), gerado


def construir(dados, areas, periodo, origens, endereco_painel="", sinteses=None, escrita_em=""):
    agora = datetime.now()
    data_extenso = f"{agora.day} de {MESES[agora.month - 1]} de {agora.year}"

    seccoes, total = [], 0
    for nome in areas:
        noticias = filtrar(dados, nome, periodo, origens)
        total += len(noticias)
        grupo = next((n.get("grupo") for n in dados if n.get("area") == nome), "")
        sintese = (sinteses or {}).get(nome)
        seccoes.append(bloco_area(nome, noticias, COR_GRUPO.get(grupo, AZUL),
                                  sintese, escrita_em, origens))

    criterios = f"{ROTULO_PERIODO.get(periodo, periodo)} · " + (
        ROTULO_ORIGENS.get(frozenset(origens), "imprensa selecionada")
        if origens else "imprensa de todas as origens")

    return f"""<!DOCTYPE html>
<html lang="pt-PT"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f8">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f6f8">
<tr><td align="center" style="padding:24px 12px">

<table width="640" cellpadding="0" cellspacing="0" role="presentation"
       style="max-width:640px;background:#ffffff;border-radius:12px;overflow:hidden;
              box-shadow:0 1px 3px rgba(23,23,21,.08)">

  <tr><td style="background:{AZUL};padding:20px 24px">
    <table cellpadding="0" cellspacing="0" role="presentation"><tr>
      <td valign="middle">
        <div style="font:600 10px Arial,sans-serif;color:#ffffff;opacity:.8;letter-spacing:1.4px;
                    text-transform:uppercase">Secretaria-Geral do Governo</div>
        <div style="font:600 20px Arial,sans-serif;color:#ffffff;padding-top:5px">Radar de Notícias</div>
        <div style="font:400 13px Arial,sans-serif;color:#ffffff;opacity:.85;padding-top:4px">
          {data_extenso} · {criterios}</div>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:16px 24px 4px;background:#fbfcfd;border-bottom:1px solid {BORDA}">
    <span style="font:600 24px Arial,sans-serif;color:{VERDE}">{total}</span>
    <span style="font:400 13px Arial,sans-serif;color:{CINZA_SUAVE}">
      {'notícia recolhida' if total == 1 else 'notícias recolhidas'} em
      {len(areas)} {'área' if len(areas) == 1 else 'áreas'}</span>
  </td></tr>

  {''.join(seccoes)}

  {ligacao_painel(endereco_painel, areas)}

  <tr><td style="padding:18px 24px;background:{CINZA_TEXTO}">
    <div style="font:400 11px Arial,sans-serif;color:#ffffff;opacity:.85;line-height:1.6">
      Direção de Serviços de Suporte à Decisão · Unidade de Pesquisa e Estatísticas<br>
      Recolha automática a partir dos feeds das publicações subscritas.
      A leitura e a verificação são de quem recebe.
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def um_por_area(dados, areas, args, origens):
    """Escreve um relatório por área e um manifesto para o fluxo.

    Sem informação de subscritores — que é o caso quando o fluxo não recebe o
    segredo —, geram-se relatórios para todas as áreas com notícias. Os
    destinatários são apurados mais tarde, já no envio: assim o manifesto não
    tem contacto com o segredo, e o GitHub não recusa passá-lo adiante.
    """
    sinteses, escrita_em = carregar_sinteses(args.sinteses, args.periodo)
    """Escreve um relatório por área e um manifesto com os destinatários.

    O manifesto é lido pelo fluxo de trabalho, que envia uma mensagem por área.
    Áreas sem destinatários ou sem notícias não geram mensagem.
    """
    # Os destinatários vêm do segredo SUBSCRITORES quando existe, para não
    # ficarem visíveis no repositório. Não existindo, recorre-se ao ficheiro.
    subscritores = {}
    bruto = os.environ.get("SUBSCRITORES", "").strip()
    if bruto:
        try:
            subscritores = json.loads(bruto).get("areas", {})
        except json.JSONDecodeError:
            sys.exit("O segredo SUBSCRITORES não contém JSON válido.")
    elif os.path.exists(args.subscritores):
        with open(args.subscritores, encoding="utf-8") as origem:
            subscritores = json.load(origem).get("areas", {})

    os.makedirs(args.pasta, exist_ok=True)
    agora = datetime.now()
    manifesto = []

    # O modelo do repositório traz as áreas todas com listas vazias: só se
    # considera que há informação de destinatários se algum endereço existir.
    sabe_destinos = any(subscritores.get(a) for a in subscritores)
    for nome in areas:
        destinos = subscritores.get(nome, [])
        if sabe_destinos and not destinos:
            print(f"  {nome}: sem destinatários, ignorada")
            continue

        noticias = filtrar(dados, nome, args.periodo, origens)
        if not noticias:
            print(f"  {nome}: sem notícias no período, não é enviada")
            continue

        base = os.path.join(
            args.pasta,
            re.sub(r"[^a-z0-9]+", "_", sem_acentos(nome)).strip("_"))
        ficheiro = base + ".html"
        with open(ficheiro, "w", encoding="utf-8") as destino:
            destino.write(construir(dados, [nome], args.periodo, origens, args.painel,
                                    sinteses, escrita_em))
        with open(base + ".txt", "w", encoding="utf-8") as destino:
            destino.write(versao_texto(dados, [nome], args.periodo, origens,
                                       args.painel, sinteses))

        # Sem endereços: o manifesto alimenta a matriz do fluxo, e os valores da
        # matriz aparecem nos nomes dos trabalhos, que num repositório público
        # são visíveis para qualquer pessoa. Os destinatários são apurados no
        # momento do envio, a partir do segredo.
        manifesto.append({
            "area": nome,
            "ficheiro": ficheiro,
            "texto": base + ".txt",
            "assunto": (f"Radar de Notícias · {nome} · "
                        f"{agora.day} de {MESES[agora.month - 1]} · "
                        f"{len(noticias)} {'notícia' if len(noticias) == 1 else 'notícias'}"),
            "noticias": len(noticias),
        })
        print(f"  {nome}: {len(noticias)} notícias"
              + (f" → {len(destinos)} destinatário(s)" if sabe_destinos else ""))

    with open(os.path.join(args.pasta, "manifesto.json"), "w", encoding="utf-8") as destino:
        json.dump(manifesto, destino, ensure_ascii=False)

    print(f"\n{len(manifesto)} mensagens a enviar")


def versao_texto(dados, areas, periodo, origens, painel, sinteses=None):
    """A mesma informação em texto simples, para clientes que bloqueiam HTML."""
    agora = datetime.now()
    linhas = ["SECRETARIA-GERAL DO GOVERNO",
              "Radar de Notícias por Área Governativa",
              f"{agora.day} de {MESES[agora.month - 1]} de {agora.year} · "
              f"{ROTULO_PERIODO.get(periodo, periodo)}", ""]

    for nome in areas:
        noticias = filtrar(dados, nome, periodo, origens)
        linhas += ["=" * 62, nome.upper(),
                   f"{len(noticias)} {'notícia' if len(noticias) == 1 else 'notícias'}", ""]

        sintese = (sinteses or {}).get(nome) or {}
        if sintese.get("texto") and not sintese.get("origens"):
            linhas += ["SÍNTESE REDIGIDA · AMÁLIA", sintese["texto"], ""]
        elif sintese.get("origens"):
            linhas.append("SÍNTESE REDIGIDA · AMÁLIA")
            for chave in ("nacionais", "lusofonas", "internacionais"):
                if origens and chave not in origens:
                    continue
                x = sintese["origens"].get(chave)
                if x:
                    linhas += [f"[{x['rotulo'].upper()}] {x['noticias']} notícias",
                               x["texto"], ""]

        if not noticias:
            linhas += ["Sem notícias no período.", ""]
            continue

        for n in noticias:
            hora = (n.get("data") or "")[11:16] or "--:--"
            linhas.append(f"[{hora}] {n.get('titulo')}")
            if n.get("resumo"):
                linhas.append(f"        {n['resumo'][:150]}")
            linhas.append(f"        {n.get('fonte')} · {ETIQUETA_ORIGEM[origem_da_fonte(n)][0]}")
            if endereco_seguro(n.get("ligacao")):
                linhas.append(f"        {n['ligacao']}")
            linhas.append("")

    if painel:
        linhas += ["Abrir o painel: " + painel, ""]
    linhas += ["--",
               "Direção de Serviços de Suporte à Decisão",
               "Unidade de Pesquisa e Estatísticas",
               "Recolha automática a partir dos feeds das publicações subscritas."]
    return "\n".join(linhas)


def destinatarios_de(area, caminho="subscritores.json"):
    """Endereços de uma área. Devolvido para consumo do fluxo, nunca impresso."""
    bruto = os.environ.get("SUBSCRITORES", "").strip()
    if bruto:
        areas = json.loads(bruto).get("areas", {})
    elif os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as origem:
            areas = json.load(origem).get("areas", {})
    else:
        areas = {}
    return [e for e in areas.get(area, []) if e]


def principal():
    ap = argparse.ArgumentParser(description="Relatório diário do Radar de Notícias.")
    ap.add_argument("--dados", default="arquivo.json", help="ficheiro de dados da recolha")
    ap.add_argument("--area", default=None, help="nome exato de uma área governativa")
    ap.add_argument("--areas", default=None, help="várias áreas, separadas por vírgula")
    ap.add_argument("--todas", action="store_true", help="todas as áreas com notícias")
    ap.add_argument("--periodo", default="24h", choices=list(HORAS) + ["auto"],
                    help="'auto' alarga a janela à segunda-feira, para cobrir o fim de semana")
    ap.add_argument("--origens", default="",
                    help="origens a incluir: nacionais, lusofonas, internacionais — "
                         "separadas por vírgula. Vazio inclui todas.")
    ap.add_argument("--saida", default="relatorio.html")
    ap.add_argument("--assunto-para", default=None,
                    help="ficheiro onde escrever o assunto da mensagem")
    ap.add_argument("--sinteses", default="sinteses.json",
                    help="ficheiro com as sínteses redigidas pelo Amália")
    ap.add_argument("--painel", default="",
                    help="endereço do painel, para a ligação no fim da mensagem")
    ap.add_argument("--destinatarios-de", default=None,
                    help="escreve em GITHUB_OUTPUT os destinatários desta área")
    ap.add_argument("--um-por-area", action="store_true",
                    help="um relatório por área, com o mapa de destinatários")
    ap.add_argument("--subscritores", default="subscritores.json",
                    help="ficheiro com os destinatários de cada área")
    ap.add_argument("--pasta", default="relatorios",
                    help="pasta onde escrever os relatórios, com --um-por-area")
    args = ap.parse_args()

    # Apuramento dos destinatários para o fluxo. O valor vai para o ficheiro de
    # saída do GitHub, que não é escrito nos registos; e pede-se ao GitHub que
    # oculte cada endereço, caso algo o imprima por engano.
    if args.destinatarios_de:
        enderecos = destinatarios_de(args.destinatarios_de, args.subscritores)
        for e in enderecos:
            print(f"::add-mask::{e}")
        saida = os.environ.get("GITHUB_OUTPUT")
        if saida:
            with open(saida, "a", encoding="utf-8") as destino:
                destino.write(f"para={','.join(enderecos)}\n")
        print(f"{len(enderecos)} destinatário(s) apurado(s).")
        return

    if not os.path.exists(args.dados):
        sys.exit(f"Ficheiro de dados não encontrado: {args.dados}")

    # À segunda-feira a janela alarga para 72 horas: de outro modo, o que foi
    # notícia ao sábado e ao domingo nunca chegaria a ser relatado.
    if args.periodo == "auto":
        args.periodo = "72h" if datetime.now().weekday() == 0 else "24h"
        print(f"Janela automática: {ROTULO_PERIODO[args.periodo]}")

    dados = carregar(args.dados)
    if not dados:
        sys.exit("O ficheiro de dados não tem notícias.")

    if args.todas:
        areas = sorted({n.get("area") for n in dados if n.get("area")})
    elif args.areas:
        areas = [a.strip() for a in args.areas.split(",") if a.strip()]
    elif args.area:
        areas = [args.area]
    else:
        sys.exit("Indique --area, --areas ou --todas.")

    origens = {o.strip() for o in args.origens.split(",") if o.strip()} or None

    if args.um_por_area:
        um_por_area(dados, areas, args, origens)
        return

    sinteses, escrita_em = carregar_sinteses(args.sinteses, args.periodo)
    html = construir(dados, areas, args.periodo, origens, args.painel, sinteses, escrita_em)

    with open(args.saida, "w", encoding="utf-8") as destino:
        destino.write(html)

    total = sum(len(filtrar(dados, a, args.periodo, origens)) for a in areas)
    agora = datetime.now()
    rotulo_areas = areas[0] if len(areas) == 1 else f"{len(areas)} áreas"
    assunto = (f"Radar de Notícias · {rotulo_areas} · "
               f"{agora.day} de {MESES[agora.month - 1]} · {total} notícias")

    if args.assunto_para:
        with open(args.assunto_para, "w", encoding="utf-8") as destino:
            destino.write(assunto)

    print(f"{total} notícias em {len(areas)} área(s)")
    print(f"relatório: {args.saida}")
    print(f"assunto: {assunto}")


if __name__ == "__main__":
    principal()
