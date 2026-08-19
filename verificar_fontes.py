# -*- coding: utf-8 -*-
"""Verificação do estado das fontes do Radar de Notícias.

Testa cada um dos feeds configurados no extrair_noticias.py e diz, feed a
feed, se responde e quantos artigos traz. Para os que falham, experimenta uma
lista de endereços alternativos conhecidos e indica qual responde — a correção
no extrair_noticias.py fica então por evidência, e não por adivinha.

Nasceu da auditoria de agosto de 2026: 34 dos então 73 feeds não tinham produzido
uma única linha no arquivo mensal, em silêncio, porque a recolha regista as
falhas apenas no registo da execução, que ninguém lê. Este verificador corre
à mão (workflow verificar-fontes.yml) e grava o resultado em
fontes-estado.json, para o estado das fontes deixar de ser invisível.

Uso:
    python verificar_fontes.py                  # testa tudo
    python verificar_fontes.py --so-falhas      # mostra só o que falha
    python verificar_fontes.py --saida fontes-estado.json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

from extrair_noticias import (FONTES, FONTES_LUSOFONAS, FONTES_INTERNACIONAIS,
                              VIA_GOOGLE, url_via_google,
                              ler_feed, extrair_itens)

# ---------------------------------------------------------------------------
# Endereços alternativos, por publicação, para os feeds que a auditoria de
# agosto de 2026 encontrou mortos. Experimentam-se por ordem; o primeiro que
# responder com artigos é o candidato a substituir o configurado.
# ---------------------------------------------------------------------------
ALTERNATIVAS = {
    "Expresso": ["https://expresso.pt/rss",
                 "https://expresso.pt/rss/feed"],
    "SIC Notícias": ["https://sicnoticias.pt/rss",
                     "https://sicnoticias.pt/rss/feed"],
    "Jornal de Notícias": ["https://www.jn.pt/rss.xml",
                           "https://feeds.jn.pt/JN-Ultimas",
                           "https://www.jn.pt/arc/outboundfeeds/rss/?outputType=xml"],
    "Diário de Notícias": ["https://www.dn.pt/rss.xml",
                           "https://feeds.dn.pt/DN-Ultimas",
                           "https://www.dn.pt/arc/outboundfeeds/rss/?outputType=xml"],
    "Correio da Manhã": ["https://www.cmjornal.pt/rss/ultimas",
                         "https://www.cmjornal.pt/rss/portugal"],
    "TSF": ["https://www.tsf.pt/rss.xml",
            "https://feeds.tsf.pt/TSF-Ultimas",
            "https://www.tsf.pt/arc/outboundfeeds/rss/?outputType=xml"],
    "Renascença": ["https://rr.sapo.pt/rss/noticias",
                   "https://rr.sapo.pt/rss/rssfeed.aspx",
                   "https://rr.sapo.pt/feed"],
    "Notícias ao Minuto": ["https://www.noticiasaominuto.com/rss",
                           "https://www.noticiasaominuto.com/rss/politica"],
    "Diário de Notícias da Madeira": ["https://www.dnoticias.pt/feed",
                                      "https://www.dnoticias.pt/rss/ultimas"],
    "Sábado": ["https://www.sabado.pt/rss/ultimas",
               "https://www.sabado.pt/rss/portugal"],
    "Dinheiro Vivo": ["https://www.dinheirovivo.pt/rss/",
                      "https://www.dinheirovivo.pt/rss.xml"],
    "Executive Digest": ["https://executivedigest.sapo.pt/feed"],
    "Lusa": ["https://www.lusa.pt/rss/geral",
             "https://www.lusa.pt/Services/Rss"],
    "Jornal i": ["https://ionline.sapo.pt/feed",
                 "https://ionline.sapo.pt/rss"],
    "Açoriano Oriental": ["https://www.acorianooriental.pt/rss/ultimas",
                          "https://www.acorianooriental.pt/feed"],
    "JM Madeira": ["https://www.jm-madeira.pt/feed",
                   "https://jm-madeira.pt/rss"],
    "Vida Económica": ["https://www.vidaeconomica.pt/rss",
                       "https://www.vidaeconomica.pt/feed/"],
    "Construir": ["https://www.construir.pt/feed"],
    "Ambiente Magazine": ["https://www.ambientemagazine.com/feed"],
    "Jornal de Angola": ["https://www.jornaldeangola.ao/rss",
                         "https://www.jornaldeangola.ao/feed"],
    "Novo Jornal (Angola)": ["https://novojornal.co.ao/rss",
                             "https://www.novojornal.co.ao/feed"],
    "Angop": ["https://www.angop.ao/feed/",
              "https://www.angop.ao/rss",
              "https://www.angop.ao/noticias/feed/"],
    "Carta de Moçambique": ["https://cartamz.com/?format=feed&type=rss",
                            "https://cartamz.com/index.php?format=feed&type=rss"],
    "Inforpress (Cabo Verde)": ["https://inforpress.cv/feed"],
    "Tatoli (Timor-Leste)": ["https://tatoli.tl/pt/feed/"],
    "Deutsche Welle (português)": ["https://rss.dw.com/rdf/rss-br-all",
                                   "https://rss.dw.com/atom/rss-br-all",
                                   "https://rss.dw.com/xml/rss-pt-all"],
    "France 24 (inglês)": ["https://www.france24.com/en/rss"],
    "Corriere della Sera": ["https://xml2.corriereobjects.it/rss/homepage.xml",
                            "https://www.corriere.it/rss/ultimora.xml"],
}

# Notas de contexto que o quadro deve mostrar mesmo antes de qualquer teste.
NOTAS = {
    "Angop": "A ligação direta cai sem resposta (bloqueio de IPs de centros "
             "de dados); recolhida via Google Notícias.",
    "Renascença": "Domínio corrigido para rr.pt em agosto de 2026; se a "
                  "pesquisa continuar a não devolver nada, a entrada deve sair.",
    "Jornal i": "Domínio corrigido para ionline.pt em agosto de 2026; mesma "
                "reserva da Renascença.",
    "Construir": "Publicação de nicho e baixo volume: uma pesquisa de um dia "
                 "pode legitimamente não devolver nada.",
    "Vida Económica": "Mesma reserva do Construir.",
}



def testar(url, tempo_limite):
    """Devolve (estado, itens, detalhe): ok / vazio / falha."""
    try:
        bruto = ler_feed(url, tempo_limite=tempo_limite)
    except Exception as erro:                                  # noqa: BLE001
        return "falha", 0, f"{type(erro).__name__}: {erro}"[:160]
    try:
        itens = extrair_itens(bruto)
    except Exception as erro:                                  # noqa: BLE001
        return "falha", 0, f"resposta não é um feed ({type(erro).__name__})"
    if not itens:
        return "vazio", 0, "feed lido mas sem artigos"
    return "ok", len(itens), ""


TRANSITORIOS = ("500", "502", "503", "RemoteDisconnected", "timed out",
                "ConnectionReset", "IncompleteRead")


def testar_com_repeticao(url, tempo_limite):
    """Como testar(), mas repete uma vez os erros com ar de transitórios.

    Na 1.ª ronda o ABC respondeu 500 — e o arquivo mostra que recolhe
    normalmente todos os dias. Um servidor engasgado num segundo não é um
    feed morto, e uma repetição espaçada distingue as duas coisas.
    """
    estado, itens, detalhe = testar(url, tempo_limite)
    if estado == "falha" and any(t in detalhe for t in TRANSITORIOS):
        time.sleep(4)
        estado2, itens2, detalhe2 = testar(url, tempo_limite)
        if estado2 == "ok":
            return "ok", itens2, "respondeu à 2.ª tentativa (erro transitório)"
        return estado2, itens2, detalhe2
    return estado, itens, detalhe


def descobrir_feeds(dominio, tempo_limite, bases=None):
    """Autodescoberta: os feeds que a própria publicação anuncia.

    A norma manda os sítios declararem os seus feeds na página inicial, em
    <link rel="alternate" type="application/rss+xml" href="…">. Quando todos
    os endereços que conhecemos falham, perguntar ao próprio sítio é mais
    fiável do que continuar a adivinhar caminhos.
    """
    candidatos = []
    for base in bases or (f"https://www.{dominio}/", f"https://{dominio}/"):
        try:
            texto = ler_feed(base, tempo_limite=tempo_limite).decode("utf-8", "replace")
        except Exception:                                      # noqa: BLE001
            continue
        for etiqueta in re.findall(r"<link\b[^>]*>", texto, re.IGNORECASE):
            if "alternate" not in etiqueta.lower():
                continue
            if not re.search(r"application/(rss|atom)\+xml", etiqueta, re.IGNORECASE):
                continue
            achado = re.search(r'href=["\']([^"\']+)["\']', etiqueta, re.IGNORECASE)
            if not achado:
                continue
            url = achado.group(1).strip()
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = base.rstrip("/") + url
            elif not url.startswith("http"):
                continue
            if url not in candidatos:
                candidatos.append(url)
        if candidatos:
            break
    return candidatos[:6]


def principal():
    ap = argparse.ArgumentParser(description="Verifica o estado das fontes do radar.")
    ap.add_argument("--saida", default="fontes-estado.json",
                    help="Ficheiro JSON com o resultado (omissão: fontes-estado.json).")
    ap.add_argument("--tempo-limite", type=int, default=25)
    ap.add_argument("--so-falhas", action="store_true",
                    help="No ecrã, mostra apenas os feeds que falham.")
    ap.add_argument("--pausa", type=float, default=0.3,
                    help="Pausa entre pedidos, por cortesia para os servidores.")
    args = ap.parse_args()

    lista = ([("nacionais", n, d, u) for n, d, u in FONTES] +
             [("lusofonas", n, d, u) for n, d, u in FONTES_LUSOFONAS] +
             [("internacionais", n, d, u) for n, d, u in FONTES_INTERNACIONAIS])

    resultados = []
    for i, (origem, nome, dominio, url) in enumerate(lista, 1):
        via_google = nome in VIA_GOOGLE
        if via_google:
            url = url_via_google(dominio)
        print(f"[{i}/{len(lista)}] {nome}"
              f"{' (via Google Notícias)' if via_google else ''}…",
              end=" ", flush=True)
        estado, itens, detalhe = testar_com_repeticao(url, args.tempo_limite)
        registo = {"nome": nome, "origem": origem, "dominio": dominio,
                   "url": url, "estado": estado, "itens": itens,
                   "detalhe": detalhe}
        if via_google:
            registo["via"] = "google-noticias"
        if nome in NOTAS:
            registo["nota"] = NOTAS[nome]

        if estado == "ok":
            print(f"OK ({itens} artigos)" + (f" — {detalhe}" if detalhe else ""))
        else:
            print(f"{estado.upper()} — {detalhe}")
            # Falhando o configurado, experimentam-se as alternativas por ordem.
            # Nas publicações via Google não há alternativas: o endereço é um só.
            for alternativa in [] if via_google else ALTERNATIVAS.get(nome, []):
                time.sleep(args.pausa)
                e2, n2, d2 = testar(alternativa, args.tempo_limite)
                print(f"    alternativa {alternativa} → "
                      f"{'OK (' + str(n2) + ' artigos)' if e2 == 'ok' else e2.upper()}")
                if e2 == "ok":
                    registo["alternativa_ok"] = alternativa
                    registo["alternativa_itens"] = n2
                    break
            # Sem alternativa viva, pergunta-se ao próprio sítio que feeds anuncia
            # — exceto na via Google, onde não há página a consultar.
            if not registo.get("alternativa_ok") and not via_google:
                descobertos = descobrir_feeds(dominio, args.tempo_limite)
                if descobertos:
                    registo["descobertos"] = descobertos
                for candidato in descobertos:
                    time.sleep(args.pausa)
                    e3, n3, d3 = testar(candidato, args.tempo_limite)
                    print(f"    descoberto {candidato} → "
                          f"{'OK (' + str(n3) + ' artigos)' if e3 == 'ok' else e3.upper()}")
                    if e3 == "ok":
                        registo["alternativa_ok"] = candidato
                        registo["alternativa_itens"] = n3
                        registo["alternativa_origem"] = "autodescoberta"
                        break
        resultados.append(registo)
        time.sleep(args.pausa)

    ok = [r for r in resultados if r["estado"] == "ok"]
    recuperaveis = [r for r in resultados if r["estado"] != "ok" and r.get("alternativa_ok")]
    mortos = [r for r in resultados if r["estado"] != "ok" and not r.get("alternativa_ok")]

    print("\n" + "═" * 66)
    print(f"RESUMO: {len(ok)} a responder · {len(recuperaveis)} recuperáveis "
          f"por endereço alternativo · {len(mortos)} sem resposta em nenhum endereço")
    if recuperaveis:
        print("\nSubstituições a fazer no extrair_noticias.py:")
        for r in recuperaveis:
            print(f'  {r["nome"]}: {r["url"]}')
            print(f'    → {r["alternativa_ok"]}  ({r["alternativa_itens"]} artigos)')
    if mortos:
        print("\nSem resposta em nenhum endereço testado:")
        for r in mortos:
            print(f'  {r["nome"]} — {r["detalhe"]}'
                  + (f'  [{r["nota"]}]' if r.get("nota") else ""))

    with open(args.saida, "w", encoding="utf-8") as saida:
        json.dump({"gerado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "a_responder": len(ok), "recuperaveis": len(recuperaveis),
                   "sem_resposta": len(mortos), "resultados": resultados},
                  saida, ensure_ascii=False, indent=1)
    print(f"\nEstado gravado em {args.saida}.")

    # Resumo legível na página da execução do GitHub, quando corre em Actions.
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(f"## Estado das fontes — {len(ok)} OK · "
                    f"{len(recuperaveis)} recuperáveis · {len(mortos)} sem resposta\n\n")
            f.write("| Publicação | Origem | Estado | Artigos | Endereço que responde |\n")
            f.write("|---|---|---|---:|---|\n")
            for r in resultados:
                if args.so_falhas and r["estado"] == "ok":
                    continue
                estado = ("✅ OK" if r["estado"] == "ok"
                          else "🔁 alternativa" if r.get("alternativa_ok")
                          else "❌ " + r["estado"])
                endereco = (r["url"] if r["estado"] == "ok"
                            else r.get("alternativa_ok", "—"))
                artigos = r["itens"] if r["estado"] == "ok" else r.get("alternativa_itens", 0)
                f.write(f'| {r["nome"]} | {r["origem"]} | {estado} '
                        f'| {artigos or ""} | {endereco} |\n')
            f.write("\nAs linhas «🔁 alternativa» dizem o endereço a colocar no "
                    "`extrair_noticias.py`; as «❌» não responderam em nenhum "
                    "endereço testado.\n")

    # O código de saída não assinala falhas de feeds: o objetivo é o relatório.
    return 0


if __name__ == "__main__":
    sys.exit(principal())
