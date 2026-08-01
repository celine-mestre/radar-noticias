# Radar de Notícias por Área Governativa

Painel de monitorização de comunicação social organizado pelas 16 áreas governativas
do XXV Governo Constitucional.

**Secretaria-Geral do Governo** · Direção de Serviços de Suporte à Decisão ·
Unidade de Pesquisa e Estatísticas

👉 **[Abrir o painel](https://celine-mestre.github.io/radar-noticias/)**

---

## Como funciona

A recolha lê todas as manhãs os **feeds das publicações portuguesas de referência** —
jornais, rádios, televisões, agências e imprensa económica — e marca cada artigo com
as áreas governativas cujas palavras-chave ele satisfaz. Um artigo é recolhido por ser
de uma fonte conhecida, não por corresponder a uma pesquisa.

É o método de um agregador de feeds, executado no próprio repositório. Daí resultam
quatro propriedades que uma pesquisa não dá:

| | Corpus próprio | Pesquisa (complemento) |
|---|---|---|
| Resultados | Todos os artigos publicados | Teto de ~100 por consulta |
| Ordenação | Data de publicação | Relevância |
| Ligações | Endereço direto do artigo | Reencaminhamento |
| Resumo | Lead escrito pela redação | Inexistente |
| Fontes | Lista conhecida e estável | Variável, com entradas estrangeiras |

O **Google Notícias** mantém-se como complemento, para o que os feeds não cobrem:
publicações fora da lista e períodos anteriores ao arquivo. É também o destino do
botão *Abrir no Google Notícias*, para pesquisa aberta.

---

## O que o painel faz

- Cartões por área governativa, com filtros por agrupamento temático.
- Seleção de várias palavras-chave em simultâneo, e pesquisa por termo livre.
- Filtros por janela temporal, origem das fontes (nacionais, internacionais, todas) e
  tipo de fonte (imprensa, redes sociais, todas).
- Leitura das notícias por ordem cronológica, com resumo, agrupadas por dia.
- Síntese visual: distribuição por publicação, assuntos recorrentes, cobertura de cada
  palavra-chave, distribuição por dia e evolução da área ao longo do tempo.
- Exportação para Excel, com folha de notícias, folha de especificações e folha de
  evolução.
- Manual de utilização embutido no painel.

---

## Ficheiros do repositório

| Ficheiro | Função |
|---|---|
| `index.html` | O painel. Ficheiro autónomo, sem dependências além do tipo de letra. |
| `extrair_noticias.py` | A recolha. Lê os feeds, marca por área e produz o Excel e os três ficheiros de dados. |
| `.github/workflows/radar-noticias.yml` | Tarefa agendada que corre a recolha nos servidores do GitHub. |
| `noticias.json` | **Retrato do dia.** O que os feeds trouxeram na última recolha. |
| `arquivo.json` | **Arquivo de sete dias.** Acumula as recolhas, sem repetições, com as palavras-chave de cada artigo. É o que responde às pesquisas no painel. |
| `historico.json` | **Série diária.** Notícias, notícias novas e publicações distintas, por dia e por área. Alimenta o bloco *Evolução*. |

Os três ficheiros de dados são gerados pela recolha. Não devem ser editados à mão.

---

## Fontes subscritas

Público (geral, política, economia e sociedade), Expresso, Observador, Jornal de
Notícias, Diário de Notícias, Correio da Manhã, Jornal de Negócios, Jornal Económico,
ECO, RTP Notícias, SIC Notícias, CNN Portugal, TSF, Renascença, Notícias ao Minuto,
Diário de Notícias da Madeira, Sábado, Visão, Dinheiro Vivo, Executive Digest, Ambiente
Magazine e Agroportal.

A lista está no início do `extrair_noticias.py`, na constante `FONTES`, e acrescenta-se
uma publicação escrevendo uma linha com o nome, o domínio e o endereço do feed. A
recolha assinala as fontes que não respondem.

---

## Instalação

1. Colocar `index.html`, `extrair_noticias.py` e `README.md` na raiz do repositório, e
   `radar-noticias.yml` em `.github/workflows/`.
2. Em **Settings › Pages**, escolher *Deploy from a branch*, ramo `main`, pasta `/ (root)`.
3. Em **Settings › Actions › General › Workflow permissions**, escolher
   *Read and write permissions*.
4. Em **Actions**, correr *Radar de Noticias* uma primeira vez.

O painel fica em `https://<utilizador>.github.io/<repositório>/`.

Para usar o ficheiro guardado no computador, abrir o `index.html` num editor de texto e
preencher `enderecoDados` com o endereço do painel publicado.

---

## Recolha manual

Em **Actions › Radar de Noticias › Run workflow**. O Excel fica em *Artifacts*, na
página da execução, durante 30 dias.

Pela linha de comandos, com Python e `openpyxl`:

```bash
# leitura dos feeds das publicações (método principal)
python extrair_noticias.py --fontes --json noticias.json \
    --arquivo arquivo.json --historico historico.json

# apenas uma área
python extrair_noticias.py --fontes --area saude --saida saude.xlsx

# pesquisa no Google Notícias, para períodos anteriores ao arquivo
python extrair_noticias.py --periodo 30d --area saude --saida saude_mes.xlsx
```

---

## Ressalvas metodológicas

- **Cobertura.** O corpus são as publicações subscritas e os últimos sete dias. Uma
  notícia fora dessa lista ou desse período só aparece pelo complemento.
- **Marcação literal.** Um artigo entra numa área por conter a expressão no título ou
  no resumo. Um artigo que trate do tema sem usar a expressão não é apanhado.
- **Comparação entre áreas.** Passa a ser legítima dentro do corpus próprio, porque
  nenhuma área é truncada. Nos resultados vindos da pesquisa, mantém-se o teto e a
  ressalva de não comparabilidade.
- **Responsabilidade editorial.** O painel é um instrumento de acesso e triagem: a
  leitura e a verificação são de quem o usa.

---

## Segunda fase

A versão assente no corpus curado do Inoreader, que substitui as duas dezenas de feeds
por toda a pasta 03_MED, com curadoria da equipa. O método é o mesmo — muda a
qualidade e a amplitude do corpus. A especificação está no ficheiro
`inoreader_feeds_areas_governativas.xlsx`, fora deste repositório.
