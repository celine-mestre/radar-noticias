#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Notícias — gestão de subscritores
Secretaria-Geral do Governo · Unidade de Pesquisa e Estatísticas

Acrescenta ou retira endereços do ficheiro de subscritores e prepara a mensagem
de confirmação. É chamado pelo fluxo de trabalho, que trata do envio e da gravação.

Utilização:
    python gerir_subscritores.py --acao subscrever \\
        --email nome@sggoverno.gov.pt --areas "Saúde,Justiça"
    python gerir_subscritores.py --acao subscrever --email nome@x.pt --todas
    python gerir_subscritores.py --acao cancelar --email nome@x.pt --todas
    python gerir_subscritores.py --acao listar
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

AZUL, VERDE, CINZA_TEXTO, CINZA_SUAVE, BORDA = "#2B5683", "#0E7433", "#171715", "#5b6068", "#e2e8f0"

# Sem imagem no cabeçalho: em correio, as imagens são bloqueadas por
# predefinição na maioria dos clientes, e uma marca que não aparece é pior do
# que marca nenhuma. A identidade faz-se com tipografia e com o azul
# institucional, que qualquer cliente apresenta sempre.

AREAS = [
    # Ordem protocolar do XXV Governo Constitucional, como no painel
    "Primeiro-Ministro",
    "Negócios Estrangeiros",
    "Finanças",
    "Presidência",
    "Reforma do Estado",
    "Assuntos Parlamentares",
    "Defesa Nacional",
    "Administração Interna",
    "Justiça",
    "Economia e Coesão Territorial",
    "Infraestruturas e Habitação",
    "Educação, Ciência e Inovação",
    "Saúde",
    "Trabalho, Solidariedade e Segurança Social",
    "Cultura, Juventude e Desporto",
    "Ambiente e Energia",
    "Agricultura e Mar",
]
VALIDO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def ocultar(email):
    """Mostra o suficiente para reconhecer o endereço, sem o revelar."""
    if "@" not in email:
        return email
    nome, dominio = email.split("@", 1)
    visivel = nome[:3] if len(nome) > 4 else nome[:1]
    return f"{visivel}{'*' * max(3, len(nome) - len(visivel))}@{dominio}"


def carregar(caminho):
    """Lê a lista de subscritores.

    Por predefinição vem da variável de ambiente SUBSCRITORES, alimentada por um
    segredo do repositório: os endereços não ficam visíveis para quem consulte o
    repositório. Não existindo, recorre-se ao ficheiro.
    """
    bruto = os.environ.get("SUBSCRITORES", "").strip()
    d = None
    if bruto:
        try:
            d = json.loads(bruto)
        except json.JSONDecodeError:
            sys.exit("O segredo SUBSCRITORES não contém JSON válido.")
    elif os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as origem:
            d = json.load(origem)

    if d is None:
        d = {"areas": {}}
    d.setdefault("areas", {})
    for a in AREAS:
        d["areas"].setdefault(a, [])
    return d


def gravar(caminho, dados):
    """Escreve a lista atualizada. O ficheiro é sempre local ao trabalho em curso:
    o fluxo grava-o no segredo e não o publica no repositório."""
    dados["atualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(dados, destino, ensure_ascii=False, indent=2)


def resolver_areas(pedidas, todas):
    """Aceita nomes aproximados: sem acentos, sem maiúsculas, parciais."""
    if todas:
        return list(AREAS)

    def simples(t):
        import unicodedata
        return unicodedata.normalize("NFD", t.lower()).encode("ascii", "ignore").decode().strip()

    escolhidas, desconhecidas = [], []
    for pedida in [p.strip() for p in pedidas.split(",") if p.strip()]:
        alvo = simples(pedida)
        achada = next((a for a in AREAS if simples(a) == alvo), None)
        if not achada:
            achada = next((a for a in AREAS if alvo in simples(a)), None)
        if achada:
            if achada not in escolhidas:
                escolhidas.append(achada)
        else:
            desconhecidas.append(pedida)

    if desconhecidas:
        print("Áreas não reconhecidas: " + "; ".join(desconhecidas))
    return escolhidas


DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]


def quando_recebe(agora=None):
    """Quando sai o primeiro relatório, contado a partir de agora.

    Os relatórios são enviados às 10h00 de Lisboa, de segunda a sexta. Quem
    subscreve a uma sexta-feira à tarde não recebe no dia seguinte — recebe na
    segunda —, e dizer-lhe "a partir de amanhã" seria faltar à verdade.
    """
    agora = agora or datetime.now()
    dia, hora = agora.weekday(), agora.hour

    # Ainda dá para apanhar o envio de hoje, se for dia útil e antes das 10h00
    if dia <= 4 and hora < 10:
        return "hoje", "ainda esta manhã, às 10h00"

    seguinte = agora + timedelta(days=1)
    while seguinte.weekday() > 4:
        seguinte += timedelta(days=1)

    dias_passados = (seguinte.date() - agora.date()).days
    if dias_passados == 1:
        return "amanhã", "a partir de amanhã, às 10h00"
    return (DIAS_SEMANA[seguinte.weekday()],
            f"a partir de {DIAS_SEMANA[seguinte.weekday()]}, às 10h00")


def mensagem_confirmacao(email, areas, acao, painel):
    """Mensagem enviada a quem subscreve ou cancela."""
    agora = datetime.now()
    subscreveu = acao == "subscrever"

    titulo = "Subscrição confirmada" if subscreveu else "Subscrição cancelada"
    _, quando = quando_recebe()
    corpo = (
        f"Receberá {quando}, e em todos os dias úteis, um relatório por cada área "
        f"abaixo, com as notícias das últimas 24 horas. À segunda-feira a janela "
        f"alarga para 72 horas, para cobrir o fim de semana."
        if subscreveu else
        "Deixará de receber os relatórios das áreas abaixo. Pode voltar a subscrever "
        "a qualquer momento, no painel."
    )

    lista = "".join(f"""
        <tr><td style="padding:5px 0;font:400 14px Arial,sans-serif;color:{CINZA_TEXTO}">
          &bull;&nbsp;&nbsp;{a}</td></tr>""" for a in areas)

    botao = f"""
  <tr><td style="padding:4px 24px 24px">
    <a href="{painel}" style="display:inline-block;background:{VERDE};color:#ffffff;
       font:600 14px Arial,sans-serif;text-decoration:none;padding:11px 22px;border-radius:6px">
       Abrir o Radar de Notícias</a>
    <div style="font:400 11px Arial,sans-serif;color:#8a9098;padding-top:10px">{painel}</div>
  </td></tr>""" if painel else ""

    return f"""<!DOCTYPE html>
<html lang="pt-PT"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f8">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f6f8">
<tr><td align="center" style="padding:24px 12px">
<table width="600" cellpadding="0" cellspacing="0" role="presentation"
       style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden">

  <tr><td style="background:{AZUL};padding:20px 24px">
    <table cellpadding="0" cellspacing="0" role="presentation"><tr>
      <td valign="middle">
        <div style="font:600 10px Arial,sans-serif;color:#ffffff;opacity:.8;letter-spacing:1.4px;
                    text-transform:uppercase">Secretaria-Geral do Governo</div>
        <div style="font:600 20px Arial,sans-serif;color:#ffffff;padding-top:5px">{titulo}</div>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:22px 24px 6px">
    <div style="font:400 14px Arial,sans-serif;color:{CINZA_TEXTO};line-height:1.6">{corpo}</div>
  </td></tr>

  <tr><td style="padding:10px 24px 6px">
    <div style="font:600 10px Arial,sans-serif;color:{CINZA_SUAVE};letter-spacing:1.2px;
                text-transform:uppercase;border-bottom:1px solid {BORDA};padding-bottom:6px">
      {len(areas)} {'área' if len(areas) == 1 else 'áreas'}</div>
    <table cellpadding="0" cellspacing="0" role="presentation" style="padding-top:8px">{lista}</table>
  </td></tr>

  <tr><td style="padding:18px 24px 6px">
    <div style="font:400 13px Arial,sans-serif;color:{CINZA_SUAVE};line-height:1.6">
      Para alterar as áreas ou cancelar, responda a esta mensagem ou a qualquer relatório.
      Áreas sem notícias no período não geram mensagem.
    </div>
  </td></tr>
  {botao}

  <tr><td style="padding:16px 24px;background:{CINZA_TEXTO}">
    <div style="font:400 11px Arial,sans-serif;color:#ffffff;opacity:.85;line-height:1.6">
      Direção de Serviços de Suporte à Decisão · Unidade de Pesquisa e Estatísticas<br>
      Registo processado em {agora.strftime('%d/%m/%Y às %H:%M')}.
    </div>
  </td></tr>

</table></td></tr></table>
</body></html>"""


def texto_confirmacao(email, areas, acao, painel):
    """Versão em texto simples, para clientes que bloqueiam o formato HTML.

    Enviada em paralelo com a versão formatada: o cliente escolhe a que sabe
    apresentar, e nenhuma mensagem fica ilegível.
    """
    subscreveu = acao == "subscrever"
    agora = datetime.now()
    linhas = [
        "SECRETARIA-GERAL DO GOVERNO",
        "Radar de Notícias por Área Governativa",
        "",
        "SUBSCRIÇÃO CONFIRMADA" if subscreveu else "SUBSCRIÇÃO CANCELADA",
        "",
    ]
    if subscreveu:
        _, quando = quando_recebe()
        linhas += [f"Receberá {quando}, e em todos os dias úteis, um relatório por",
                   "cada área abaixo, com as notícias das últimas 24 horas. À",
                   "segunda-feira a janela alarga para 72 horas, para cobrir o fim",
                   "de semana.", ""]
    else:
        linhas += ["Deixará de receber os relatórios das áreas abaixo. Pode voltar",
                   "a subscrever a qualquer momento, no painel.", ""]

    linhas.append(f"{len(areas)} {'área' if len(areas) == 1 else 'áreas'}:")
    linhas += [f"  - {a}" for a in areas]
    linhas += ["",
               "Para alterar as áreas ou cancelar, responda a esta mensagem ou a",
               "qualquer relatório.",
               ""]
    if painel:
        linhas += ["Painel: " + painel, ""]
    linhas += ["--",
               "Direção de Serviços de Suporte à Decisão",
               "Unidade de Pesquisa e Estatísticas",
               f"Registo processado em {agora.strftime('%d/%m/%Y às %H:%M')}."]
    return "\n".join(linhas)


def principal():
    ap = argparse.ArgumentParser(description="Gestão de subscritores do Radar de Notícias.")
    ap.add_argument("--acao", choices=["subscrever", "cancelar", "listar"], default="listar")
    ap.add_argument("--email", default=None)
    ap.add_argument("--areas", default="", help="nomes separados por vírgula")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--ficheiro", default="subscritores.json",
                    help="ficheiro a usar quando o segredo SUBSCRITORES não existe")
    ap.add_argument("--gravar-em", default=None,
                    help="ficheiro onde escrever a lista atualizada")
    ap.add_argument("--painel", default="")
    ap.add_argument("--confirmacao-para", default=None,
                    help="ficheiro HTML da mensagem de confirmação")
    ap.add_argument("--texto-para", default=None,
                    help="ficheiro com a mesma mensagem em texto simples")
    ap.add_argument("--assunto-para", default=None)
    args = ap.parse_args()

    dados = carregar(args.ficheiro)

    if args.acao == "listar":
        # Os registos das execuções são públicos num repositório público: os
        # endereços saem parcialmente ocultos, o suficiente para se reconhecer
        # quem está subscrito sem os expor.
        total = {}
        for area in AREAS:
            enderecos = dados["areas"].get(area, [])
            for e in enderecos:
                total.setdefault(e, []).append(area)
            print(f"  {area:46} {len(enderecos)}")

        print(f"\n{len(total)} {'endereço' if len(total) == 1 else 'endereços'} distintos:")
        for e in sorted(total):
            print(f"  {ocultar(e):34} {len(total[e])} área(s)")
        return

    email = (args.email or "").strip().lower()
    if not VALIDO.match(email):
        sys.exit(f"Endereço inválido: {args.email}")

    areas = resolver_areas(args.areas, args.todas)
    if not areas:
        sys.exit("Indique --areas ou --todas.")

    mexidas = []
    for area in areas:
        atuais = [e.lower() for e in dados["areas"][area]]
        if args.acao == "subscrever" and email not in atuais:
            dados["areas"][area].append(email)
            mexidas.append(area)
        elif args.acao == "cancelar" and email in atuais:
            dados["areas"][area] = [e for e in dados["areas"][area] if e.lower() != email]
            mexidas.append(area)

    destino_lista = args.gravar_em or args.ficheiro
    if not mexidas:
        estado = "já estava subscrito" if args.acao == "subscrever" else "não estava subscrito"
        print(f"Nada a alterar: {ocultar(email)} {estado} em todas as áreas indicadas.")
        gravar(destino_lista, dados)      # devolve a lista tal como está
    else:
        gravar(destino_lista, dados)
        verbo = "subscrito em" if args.acao == "subscrever" else "retirado de"
        print(f"{ocultar(email)} {verbo} {len(mexidas)} área(s):")
        for a in mexidas:
            print(f"  - {a}")

    if args.confirmacao_para:
        with open(args.confirmacao_para, "w", encoding="utf-8") as destino:
            destino.write(mensagem_confirmacao(email, areas, args.acao, args.painel))

    if args.texto_para:
        with open(args.texto_para, "w", encoding="utf-8") as destino:
            destino.write(texto_confirmacao(email, areas, args.acao, args.painel))

    if args.assunto_para:
        titulo = ("Radar de Notícias · subscrição confirmada"
                  if args.acao == "subscrever" else
                  "Radar de Notícias · subscrição cancelada")
        with open(args.assunto_para, "w", encoding="utf-8") as destino:
            destino.write(titulo)


if __name__ == "__main__":
    principal()
