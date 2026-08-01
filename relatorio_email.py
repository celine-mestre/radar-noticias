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


def fonte_nacional(n):
    d = (n.get("dominio") or "").lower().replace("www.", "")
    if not d:
        return True
    return d.endswith(".pt") or any(d == x or d.endswith("." + x) for x in DOMINIOS_NACIONAIS)


def carregar(caminho):
    with open(caminho, encoding="utf-8") as origem:
        return json.load(origem).get("noticias", [])


def filtrar(noticias, area, periodo, so_nacionais):
    limite = None
    if periodo in HORAS:
        limite = datetime.now() - timedelta(hours=HORAS[periodo])

    saida = []
    for n in noticias:
        if area and n.get("area") != area:
            continue
        if so_nacionais and not fonte_nacional(n):
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


def esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def contar(noticias, chave):
    contagem = {}
    for n in noticias:
        v = n.get(chave) or "sem indicação"
        contagem[v] = contagem.get(v, 0) + 1
    return sorted(contagem.items(), key=lambda x: -x[1])


def bloco_area(nome, noticias, cor):
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
    </td></tr>"""]

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
            partes.append(f"""
    <tr><td style="padding:9px 24px;border-bottom:1px solid #f1f4f7">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>
        <td width="44" valign="top" style="font:400 12px Arial,sans-serif;color:{CINZA_SUAVE};padding-top:2px">{hora}</td>
        <td valign="top">
          <a href="{esc(n.get('ligacao'))}" style="font:400 14px Arial,sans-serif;color:{CINZA_TEXTO};
             text-decoration:none;line-height:1.4">{esc(n.get('titulo'))}</a>
          {f'<div style="font:400 12px Arial,sans-serif;color:{CINZA_SUAVE};padding-top:3px;line-height:1.45">{esc(resumo)}</div>' if resumo else ''}
          <div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:4px">{esc(n.get('fonte'))}</div>
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


def construir(dados, areas, periodo, so_nacionais, endereco_painel=""):
    agora = datetime.now()
    data_extenso = f"{agora.day} de {MESES[agora.month - 1]} de {agora.year}"

    seccoes, total = [], 0
    for nome in areas:
        noticias = filtrar(dados, nome, periodo, so_nacionais)
        total += len(noticias)
        grupo = next((n.get("grupo") for n in dados if n.get("area") == nome), "")
        seccoes.append(bloco_area(nome, noticias, COR_GRUPO.get(grupo, AZUL)))

    criterios = f"{ROTULO_PERIODO.get(periodo, periodo)}"
    if so_nacionais:
        criterios += " · imprensa nacional"

    return f"""<!DOCTYPE html>
<html lang="pt-PT"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f8">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f6f8">
<tr><td align="center" style="padding:24px 12px">

<table width="640" cellpadding="0" cellspacing="0" role="presentation"
       style="max-width:640px;background:#ffffff;border-radius:12px;overflow:hidden;
              box-shadow:0 1px 3px rgba(23,23,21,.08)">

  <tr><td style="background:{AZUL};padding:22px 24px">
    <div style="font:600 10px Arial,sans-serif;color:#ffffff;opacity:.8;letter-spacing:1.4px;
                text-transform:uppercase">Secretaria-Geral do Governo</div>
    <div style="font:600 20px Arial,sans-serif;color:#ffffff;padding-top:6px">Radar de Notícias</div>
    <div style="font:400 13px Arial,sans-serif;color:#ffffff;opacity:.85;padding-top:4px">
      {data_extenso} · {criterios}</div>
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


def um_por_area(dados, areas, args, so_nacionais):
    """Escreve um relatório por área e um manifesto com os destinatários.

    O manifesto é lido pelo fluxo de trabalho, que envia uma mensagem por área.
    Áreas sem destinatários ou sem notícias não geram mensagem.
    """
    subscritores = {}
    if os.path.exists(args.subscritores):
        with open(args.subscritores, encoding="utf-8") as origem:
            subscritores = json.load(origem).get("areas", {})

    os.makedirs(args.pasta, exist_ok=True)
    agora = datetime.now()
    manifesto = []

    for nome in areas:
        destinos = subscritores.get(nome, [])
        if not destinos:
            print(f"  {nome}: sem destinatários, ignorada")
            continue

        noticias = filtrar(dados, nome, args.periodo, so_nacionais)
        if not noticias:
            print(f"  {nome}: sem notícias no período, não é enviada")
            continue

        ficheiro = os.path.join(
            args.pasta,
            re.sub(r"[^a-z0-9]+", "_", sem_acentos(nome)).strip("_") + ".html")
        with open(ficheiro, "w", encoding="utf-8") as destino:
            destino.write(construir(dados, [nome], args.periodo, so_nacionais, args.painel))

        manifesto.append({
            "area": nome,
            "ficheiro": ficheiro,
            "destinatarios": ",".join(destinos),
            "assunto": (f"Radar de Notícias · {nome} · "
                        f"{agora.day} de {MESES[agora.month - 1]} · "
                        f"{len(noticias)} {'notícia' if len(noticias) == 1 else 'notícias'}"),
            "noticias": len(noticias),
        })
        print(f"  {nome}: {len(noticias)} notícias → {len(destinos)} destinatário(s)")

    with open(os.path.join(args.pasta, "manifesto.json"), "w", encoding="utf-8") as destino:
        json.dump(manifesto, destino, ensure_ascii=False)

    print(f"\n{len(manifesto)} mensagens a enviar")


def principal():
    ap = argparse.ArgumentParser(description="Relatório diário do Radar de Notícias.")
    ap.add_argument("--dados", default="arquivo.json", help="ficheiro de dados da recolha")
    ap.add_argument("--area", default=None, help="nome exato de uma área governativa")
    ap.add_argument("--areas", default=None, help="várias áreas, separadas por vírgula")
    ap.add_argument("--todas", action="store_true", help="todas as áreas com notícias")
    ap.add_argument("--periodo", default="24h", choices=list(HORAS))
    ap.add_argument("--todas-as-fontes", action="store_true",
                    help="não restringir à imprensa nacional")
    ap.add_argument("--saida", default="relatorio.html")
    ap.add_argument("--assunto-para", default=None,
                    help="ficheiro onde escrever o assunto da mensagem")
    ap.add_argument("--painel", default="",
                    help="endereço do painel, para a ligação no fim da mensagem")
    ap.add_argument("--um-por-area", action="store_true",
                    help="um relatório por área, com o mapa de destinatários")
    ap.add_argument("--subscritores", default="subscritores.json",
                    help="ficheiro com os destinatários de cada área")
    ap.add_argument("--pasta", default="relatorios",
                    help="pasta onde escrever os relatórios, com --um-por-area")
    args = ap.parse_args()

    if not os.path.exists(args.dados):
        sys.exit(f"Ficheiro de dados não encontrado: {args.dados}")

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

    so_nacionais = not args.todas_as_fontes

    if args.um_por_area:
        um_por_area(dados, areas, args, so_nacionais)
        return

    html = construir(dados, areas, args.periodo, so_nacionais, args.painel)

    with open(args.saida, "w", encoding="utf-8") as destino:
        destino.write(html)

    total = sum(len(filtrar(dados, a, args.periodo, so_nacionais)) for a in areas)
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
