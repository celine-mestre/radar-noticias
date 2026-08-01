# Radar de Notícias por Área Governativa

Painel de monitorização de comunicação social organizado pelas 16 áreas governativas
do XXV Governo Constitucional.

**Secretaria-Geral do Governo** · Direção de Serviços de Suporte à Decisão ·
Unidade de Pesquisa e Estatísticas

👉 **[Abrir o painel](https://celine-mestre.github.io/radar-noticias/)**

---

## Como funciona

A recolha lê todas as manhãs os **feeds de 48 publicações de imprensa** — portuguesas,
lusófonas e internacionais — e marca cada artigo com as áreas governativas cujas
palavras-chave ele satisfaz. Um artigo é recolhido por ser de uma fonte conhecida, não
por corresponder a uma pesquisa.

É o método de um agregador de feeds, executado no próprio repositório.

As propriedades que daí resultam, e que uma pesquisa não dá:

| | |
|---|---|
| Resultados | Todos os artigos publicados pelas fontes subscritas |
| Ordenação | Data de publicação |
| Ligações | Endereço direto do artigo |
| Resumo | Lead escrito pela redação |
| Fontes | Lista conhecida e estável |

O botão de **pesquisa aberta** existe para o que os feeds não cobrem — uma publicação
não subscrita ou um período anterior ao arquivo — e abre uma consulta externa em
janela nova. É consulta pontual, sem as garantias acima.

### O percurso de uma notícia, passo a passo

1. **06h00 de cada dia útil.** O GitHub executa `extrair_noticias.py --fontes`.
   O programa está no repositório e é legível: a lista de publicações está na
   constante `FONTES`, as áreas e palavras-chave na constante `AREAS`, e a marcação
   na função `marcar_por_areas()`.
2. **Leitura dos feeds.** Cada publicação é lida pelo seu endereço RSS. Cada artigo
   traz título, resumo, data de publicação, fonte e ligação direta.
3. **Marcação.** Para cada artigo, o programa procura literalmente as expressões de
   cada área no título e no resumo. Encontrando, marca o artigo com essa área e com
   as expressões que a acionaram. Um artigo pode ficar em mais de uma área.
4. **Gravação.** Os artigos marcados são acumulados no `arquivo.json`, sem
   repetições, mantendo 30 dias. Gravam-se também o retrato do dia e a série.
5. **No painel.** Ao abrir uma área, o painel lê o `arquivo.json` e filtra-o pela
   área, pelas palavras-chave selecionadas, pelo período, pela origem das fontes e
   pelo tipo de fonte. Tudo local, em milissegundos.

Nada disto passa por serviços intermediários nem depende da rede de quem consulta.

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
| `relatorio_email.py` | Gera os relatórios diários em HTML a partir do arquivo. |
| `gerir_subscritores.py` | Acrescenta e retira endereços, e prepara a confirmação. |
| `.github/workflows/subscricao.yml` | Trata um pedido de subscrição de ponta a ponta. |
| `subscritores.json` | Destinatários de cada área governativa. É aqui que se subscreve e cancela. |
| `.github/workflows/relatorio-diario.yml` | Tarefa agendada que envia um relatório por área. |
| `noticias.json` | **Retrato do dia.** O que os feeds trouxeram na última recolha. |
| `arquivo.json` | **Arquivo de 30 dias.** Acumula as recolhas, sem repetições, com as palavras-chave de cada artigo. É o que responde às pesquisas no painel. |
| `historico.json` | **Série diária.** Notícias, notícias novas e publicações distintas, por dia e por área. Não contém notícias, apenas contagens. |

Os três ficheiros de dados são gerados pela recolha. Não devem ser editados à mão.

O `arquivo.json` e o `noticias.json` são substituídos a cada execução, mantendo
apenas a janela recente. O `historico.json` nunca é apagado: cresce cerca de dois
kilobytes por dia e é a memória do produto. É dele que sai o bloco **Evolução** da
síntese — a série de notícias por dia de cada área, a média dos dias anteriores e a
variação do último dia face a essa média — e a folha *Evolução* do ficheiro Excel.

Como todas as recolhas usam o mesmo método e a mesma janela, a comparação de uma
área consigo própria ao longo do tempo é metodologicamente válida. Ao fim de um mês
de dias úteis haverá vinte pontos por área, o suficiente para ver padrões; ao fim de
um trimestre, para os fundamentar.

---

## Fontes subscritas

**Portuguesas (25 feeds).** Público — geral, política, economia e sociedade —,
Expresso, Observador, Jornal de Notícias, Diário de Notícias, Correio da Manhã,
Jornal de Negócios, Jornal Económico, ECO, RTP Notícias, SIC Notícias, CNN Portugal,
TSF, Renascença, Notícias ao Minuto, Diário de Notícias da Madeira, Sábado, Visão,
Dinheiro Vivo, Executive Digest, Ambiente Magazine e Agroportal.

**Lusofonia (11 feeds).** Jornal de Angola, Novo Jornal, Angop, O País, Carta de
Moçambique, Expresso das Ilhas, Inforpress, Tatoli, STP-Press, Agência Brasil e Folha
de S.Paulo. Matéria de CPLP, cooperação e diáspora é frequentemente tratada primeiro
nestes títulos.

**Internacionais (12 feeds).** Euronews em português, Politico Europe, EURACTIV,
El País, Le Monde, BBC Mundo, Deutsche Welle, France 24, RFI, The Guardian (Europa) e
Lusa Internacional.

São 48 feeds ao todo. O seletor do painel tem três origens que não se sobrepõem —
**Portugal**, **Lusofonia** e **Resto do mundo** — mais a posição **Todas**, que é a
soma das três.

As listas estão no início do `extrair_noticias.py`, nas constantes `FONTES`,
`FONTES_LUSOFONAS` e `FONTES_INTERNACIONAIS`. Acrescenta-se uma publicação escrevendo uma linha com o nome,
o domínio e o endereço do feed. A recolha assinala as fontes que não respondem.

### O que o corpus não cobre

O âmbito é deliberadamente delimitado, e isso é uma escolha e não um defeito: um corpus
conhecido é o que permite datas fiáveis, ligações diretas, resumos e contagens
comparáveis entre áreas. Fica de fora:

- **Publicações não subscritas** — imprensa regional, especializada ou estrangeira
  fora da lista.
- **Redes sociais** — as plataformas sociais não publicam feeds e estão fora do
  âmbito da aplicação, que é a imprensa.
- **Períodos anteriores ao arquivo** — que guarda 30 dias, valor definido na recolha.

Para o que fica de fora há o botão de **pesquisa aberta**, que abre o Google Notícias
em janela nova. É consulta pontual, sem as garantias do corpus. Alargar o âmbito de
forma permanente é acrescentar feeds à lista.

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
    --arquivo arquivo.json --dias-arquivo 7 --historico historico.json

# apenas uma área
python extrair_noticias.py --fontes --area saude --saida saude.xlsx

# pesquisa no Google Notícias, para períodos anteriores ao arquivo
python extrair_noticias.py --periodo 30d --area saude --saida saude_mes.xlsx
```

---

## Ressalvas metodológicas

- **Cobertura.** O corpus são as 48 publicações subscritas e os últimos sete dias.
  Uma notícia de um título não subscrito, ou anterior a esse período, não está no
  corpus. A janela do arquivo define-se com `--dias-arquivo` e pode ser alargada
  quando houver espaço para isso.
- **Marcação literal.** Um artigo entra numa área por conter a expressão no título ou
  no resumo. Um artigo que trate do tema sem usar a expressão não é apanhado.
- **Comparação entre áreas.** Legítima dentro do corpus: nenhuma área é truncada e o
  método é o mesmo para todas. As contagens medem o que as publicações subscritas
  noticiaram, não o total do que foi noticiado.
- **Imprensa apenas.** As plataformas sociais não publicam feeds e estão fora do
  âmbito da aplicação.
- **Responsabilidade editorial.** O painel é um instrumento de acesso e triagem: a
  leitura e a verificação são de quem o usa.

---

## Relatório diário por email

Todas as manhãs, às 10h00 de Lisboa, é enviado **um relatório por área governativa**
para os destinatários dessa área. Cada mensagem traz as notícias das últimas 24 horas
agrupadas por dia, com hora, título, resumo, publicação e ligação — e termina com um
botão para abrir o painel, onde se pode refazer a pesquisa, alargar o período ou
exportar para Excel.

A recolha corre às 08h40 UTC, vinte minutos antes, para o relatório apanhar também
as notícias da própria manhã.

### Subscrever e cancelar

**No painel.** O botão *Receber por email* abre uma janela onde a pessoa indica o
endereço e escolhe as áreas. Ao confirmar, abre-se no seu programa de correio uma
mensagem já preenchida, dirigida à Unidade de Pesquisa e Estatísticas, que basta
enviar. Quem não tenha programa de correio configurado pode copiar o texto, que fica
visível no ecrã.

O painel é um ficheiro estático: não tem servidor para registar endereços nem para
enviar mensagens. Este desenho evita essa dependência e tem uma vantagem — o pedido
fica registado na caixa de enviados de quem subscreve e na caixa de entrada da
unidade, com rasto dos dois lados.

**Processamento automático.** Recebido o pedido, corre-se em **Actions › Subscricao
do relatorio › Run workflow** com o endereço e as áreas. O fluxo grava a alteração no
`subscritores.json`, envia a confirmação a quem pediu e deixa o registo no histórico
do repositório. Não é preciso editar ficheiros à mão.

Os nomes das áreas são tolerantes: aceitam-se sem acentos, em minúsculas e parciais —
`saude, agricultura` resolve para *Saúde* e *Agricultura e Mar*. Para todas, escrever
`todas`.

O ficheiro tem uma lista por área:

```json
{
  "areas": {
    "Saúde": ["nome@sggoverno.gov.pt", "gabinete@min-saude.gov.pt"],
    "Justiça": ["nome@sggoverno.gov.pt"]
  }
}
```

Acrescentar um endereço subscreve; retirá-lo cancela. A alteração entra em vigor no
envio seguinte, pelo que o primeiro relatório chega na manhã seguinte ao registo. Uma área sem endereços não gera mensagem, e uma
área sem notícias no período também não — não se enviam relatórios vazios.

Este desenho é deliberado: os destinatários ficam num ficheiro versionado, visível
e auditável, em vez de numa configuração escondida. Quem gere o produto altera a
lista sem depender de ninguém, e o histórico de alterações fica registado.

### Credenciais

Em **Settings › Secrets and variables › Actions**: `SMTP_SERVIDOR`, `SMTP_PORTA`,
`SMTP_UTILIZADOR` e `SMTP_SENHA`. Numa conta institucional, a senha de aplicação
costuma ter de ser pedida à área de sistemas.

Sem credenciais o fluxo corre na mesma e deixa os relatórios em *Artifacts*, na
página da execução.

### Gerar à mão

```bash
python relatorio_email.py --dados arquivo.json --area "Saúde" --periodo 24h
python relatorio_email.py --dados arquivo.json --todas --um-por-area \
    --painel "https://celine-mestre.github.io/radar-noticias/"
```

---

## Alargar o corpus

Acrescentar uma publicação é escrever uma linha nas listas `FONTES`,
`FONTES_LUSOFONAS` ou `FONTES_INTERNACIONAIS`, no início do `extrair_noticias.py`,
com o nome, o domínio e o endereço do feed. A recolha seguinte já a inclui.

Ajustar as áreas e as palavras-chave é editar a lista `AREAS`, no mesmo ficheiro.
O critério é o da expressão e não o da palavra solta — "alterações climáticas" e não
"clima" — e a correspondência aceita singular e plural.
