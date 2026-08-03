# Radar de Notícias por Área Governativa

Painel de monitorização de comunicação social organizado pelas 16 áreas governativas
do XXV Governo Constitucional.

**Secretaria-Geral do Governo** · Direção de Serviços de Suporte à Decisão ·
Unidade de Pesquisa e Estatísticas

👉 **[Abrir o painel](https://celine-mestre.github.io/radar-noticias/)**

---

## Como funciona

A recolha lê, de duas em duas horas, **73 feeds de 66 publicações de imprensa** — portuguesas,
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

Nenhuma listagem, síntese ou exportação depende de serviços externos: tudo o que o
painel mostra vem deste corpus. O que não estiver nas publicações subscritas, ou for
anterior ao arquivo, não aparece — e alargar o âmbito é acrescentar feeds à lista.

### O percurso de uma notícia, passo a passo

1. **06h07 e 08h07 UTC, todos os dias.** O GitHub executa `extrair_noticias.py --fontes`.
   O programa está no repositório e é legível: a lista de publicações está na
   constante `FONTES`, as áreas e palavras-chave na constante `AREAS`, e a marcação
   na função `marcar_por_areas()`.
2. **Leitura dos feeds.** Cada publicação é lida pelo seu endereço RSS. Cada artigo
   traz título, resumo, data de publicação, fonte e ligação direta.
3. **Marcação.** Para cada artigo, o programa procura literalmente as expressões de
   cada área no título e no resumo. Encontrando, marca o artigo com essa área e com
   as expressões que a acionaram. Um artigo pode ficar em mais de uma área.
4. **Gravação.** Os artigos marcados são acumulados no `arquivo.json`, sem
   repetições, mantendo sete dias. Gravam-se também o retrato do dia e a série
   diária de contagens.
5. **No painel.** O radar lê o `arquivo.json` e conta as notícias de cada área
   dentro do período e da origem escolhidos. Ao abrir uma área, o mesmo ficheiro é
   filtrado pelas palavras-chave selecionadas. As duas contagens seguem os mesmos
   critérios, pelo que dizem sempre o mesmo número. Tudo local, em milissegundos.

Nada disto passa por serviços intermediários nem depende da rede de quem consulta.

---

## O que o painel faz

**Entrada em radar.** As dezasseis áreas dispostas em círculo, ordenadas por volume de
notícias, com a distância ao centro a significar quanto foi noticiado — quanto mais
perto do centro, mais notícias. Ao centro, o total do período e da origem escolhidos.
Em ecrãs estreitos o círculo dá lugar a uma grelha de cartões, que faz o mesmo trabalho.

**Predefinições.** Últimos sete dias e imprensa de todas as origens. O período vai das
24 horas aos sete dias que o arquivo guarda; a origem escolhe entre Portugal, lusofonia,
internacional ou todas. Ambos valem para o radar e para as consultas.

**Uma área abre-se num clique**, já com as notícias recolhidas. Dentro da janela:

- Todas as palavras-chave da área à cabeça, selecionáveis uma a uma ou em conjunto, com
  a consulta a refazer-se no momento; e uma caixa para pesquisa por termo livre.
- Seletores de período, imprensa e **área**, este último para trocar de área sem fechar
  a janela — útil para comparar duas áreas com os mesmos critérios.
- Botão para **ampliar** a janela a quase todo o ecrã, e outro para voltar ao radar.
- Notícias por ordem cronológica, agrupadas por dia, com hora, imagem quando a
  publicação a fornece, resumo, publicação e etiqueta de origem.
- Síntese com indicadores: distribuição por publicação, assuntos recorrentes, cobertura
  de cada palavra-chave e evolução da área ao longo do tempo.
- Impressão em PDF com cabeçalho institucional, e exportação para Excel com folha de
  notícias, folha de especificações e folha de síntese.

**Nada reduz sem explicar.** Sempre que a consulta deixa notícias de fora, o painel diz
quantas e porquê: com outras palavras-chave da área, de outra origem, ou no arquivo mas
fora do período.

**Botão de ecrã inteiro** no canto superior direito, para apresentar em reunião, e
**manual de utilização** embutido no próprio painel.

---

## Ficheiros do repositório

| Ficheiro | Função |
|---|---|
| `index.html` | O painel. Ficheiro autónomo, sem dependências além do tipo de letra. |
| `extrair_noticias.py` | A recolha. Lê os feeds, marca por área e produz o Excel e os três ficheiros de dados. |
| `.github/workflows/radar-noticias.yml` | Tarefa agendada que corre a recolha nos servidores do GitHub. |
| `sintese_ia.py` | Escreve, com o Amália, uma síntese diária por área. Opcional. |
| `.github/workflows/sintese-amalia.yml` | Corre o Amália e grava as sínteses. |
| `sinteses.json` | As sínteses redigidas, quando existem. |
| `relatorio_email.py` | Gera os relatórios diários em HTML a partir do arquivo. |
| `gerir_subscritores.py` | Acrescenta e retira endereços, e prepara a confirmação. |
| `.github/workflows/subscricao.yml` | Trata um pedido de subscrição de ponta a ponta. |
| `subscritores.json` | Destinatários de cada área governativa. É aqui que se subscreve e cancela. |
| `.github/workflows/relatorio-diario.yml` | Tarefa agendada que envia um relatório por área. |
| `noticias.json` | **Retrato do dia.** O que os feeds trouxeram na última recolha. |
| `arquivo.json` | **Arquivo de sete dias.** Acumula as recolhas, sem repetições, com as palavras-chave de cada artigo. É o que responde às pesquisas no painel. |
| `historico.json` | **Série diária.** Por dia e por área: notícias, notícias novas, publicações distintas, repartição por origem e contagem de cada palavra-chave. Agregados, não notícias. |
| `corpus.json` | **Imprensa em bruto, sete dias.** Todos os artigos lidos dos feeds, marcados ou não. Serve a pesquisa por termo livre; o painel só o carrega quando alguém pesquisa. |
| `meses/AAAA-MM.jsonl.gz` | **Arquivo permanente.** Um ficheiro comprimido por mês, com todas as notícias desse mês. Nada o lê no dia a dia. |

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

**Portugal — 35 feeds de 31 publicações.**
Agência: Lusa (geral e internacional).
Diários e semanários: Público (geral, política, economia, sociedade e ciência), Expresso,
Observador, Jornal de Notícias, Diário de Notícias, Correio da Manhã, Nascer do SOL,
Jornal i, Sábado e Visão.
Economia: Jornal de Negócios, Jornal Económico, ECO, Dinheiro Vivo, Vida Económica e
Executive Digest.
Rádio e televisão: RTP Notícias, SIC Notícias, CNN Portugal, TSF e Renascença.
Digitais e regionais: Notícias ao Minuto, Diário de Notícias da Madeira, JM Madeira e
Açoriano Oriental.
Especializadas, por matéria de tutela: Agroportal (agricultura), Ambiente Magazine
(ambiente), Construir (obras e habitação), Healthnews (saúde) e SAPO Tek (digital).

**Lusofonia — 11 feeds de 11 publicações.**
Angola: Jornal de Angola, Novo Jornal e Angop. Moçambique: O País e Carta de Moçambique.
Cabo Verde: Expresso das Ilhas e Inforpress. São Tomé e Príncipe: STP-Press.
Timor-Leste: Tatoli. Brasil: Agência Brasil e Folha de S.Paulo.

Matéria de CPLP, cooperação e diáspora é frequentemente tratada primeiro nestes títulos.

**Internacionais — 27 feeds de 25 publicações.**
Em português: Euronews, Deutsche Welle, France 24, RFI e Lusa Internacional.
União Europeia: Politico Europe e EURACTIV.
Espanha: El País (geral e internacional), El Mundo, La Vanguardia e ABC.
Reino Unido: BBC News, BBC Mundo e The Guardian (Europa e mundo).
França: Le Monde, Le Figaro e France Info.
Itália: ANSA, Corriere della Sera e La Repubblica.
Estados Unidos da América: Associated Press, The New York Times, The Washington Post e
Politico.
Alemanha: Der Spiegel.

**São 73 feeds de 66 publicações.** A diferença são sete publicações com mais do que um
feed — o Público tem cinco, a Lusa, o El País e o The Guardian têm dois cada. O feed
geral de um jornal tem teto de itens, e as secções trazem peças que ele já empurrou para
fora; as repetições são descartadas na recolha.

Só as publicações que escrevem em português são classificadas por área. As restantes
entram no corpus da pesquisa por termo — ver a secção seguinte.

### Língua das fontes estrangeiras

As palavras-chave estão em português. A classificação por área funciona, portanto, sobre
as publicações que escrevem em português: as nacionais, as lusófonas e as edições
portuguesas da Euronews, da Deutsche Welle, da France 24 e da RFI.

As restantes estrangeiras — britânicas, francesas, espanholas, italianas, norte-americanas
e alemãs — **não são classificadas por área**, e entram apenas no corpus da **pesquisa por
termo**. Aplicar palavras-chave portuguesas a outra língua produz coincidências falsas:
"bolsas" apanhava "la bolsa española", que é a bolsa de valores, e punha notícias
financeiras espanholas na Educação. Escrevendo "Ceuta",
"NATO" ou o nome de uma pessoa, encontram-se; por palavras-chave portuguesas, não são
classificadas. Foram acrescentadas por isso mesmo: para que a pesquisa livre alcance a
imprensa de referência internacional, que é o que um serviço de *clipping* faz.

### O que o corpus não cobre

O âmbito é deliberadamente delimitado, e isso é uma escolha e não um defeito: um corpus
conhecido é o que permite datas fiáveis, ligações diretas, resumos e contagens
comparáveis entre áreas. Fica de fora:

- **Publicações não subscritas** — imprensa regional, especializada ou estrangeira
  fora da lista.
- **Redes sociais** — as plataformas sociais não publicam feeds e estão fora do
  âmbito da aplicação, que é a imprensa.
- **Períodos anteriores ao arquivo** — que guarda sete dias, valor definido na recolha.

Alargar o âmbito é acrescentar feeds à lista — e passa a valer na recolha seguinte.

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
    --arquivo arquivo.json --dias-arquivo 7 --mensal meses \
    --historico historico.json

# apenas uma área
python extrair_noticias.py --fontes --area saude --saida saude.xlsx
```

---

## Horas

Tudo o que a aplicação escreve e apresenta está na **hora de Lisboa**.

Há duas conversões a fazer, e ambas davam incoerências antes de existirem. O servidor
do GitHub corre em UTC, pelo que a hora da recolha saía uma hora atrasada no horário de
verão. E os feeds datam os artigos no fuso de cada publicação: o mesmo instante vem como
16h40 num jornal alemão, 15h40 num português e 10h40 num norte-americano.

A recolha converte cada data para Lisboa antes de a gravar, e usa a hora de Lisboa para
as suas próprias comparações. Assim a hora da recolha, as horas das notícias e as janelas
temporais dizem respeito ao mesmo relógio — e deixa de haver notícias com hora posterior
à atual.

---

## Ressalvas metodológicas

- **Cobertura.** O corpus são as 66 publicações subscritas e os últimos sete dias.
  Uma notícia de um título não subscrito, ou anterior a esse período, não está no
  corpus. A janela do arquivo define-se com `--dias-arquivo` e pode ser alargada
  quando houver espaço para isso.
- **Marcação literal.** Um artigo entra numa área por conter a expressão no título ou
  no resumo. Um artigo que trate do tema sem usar a expressão não é apanhado.
- **As expressões são curtas, como a imprensa escreve.** "política de imigração" quase
  nunca aparece num título; "imigração", "imigrantes" e "migrantes" aparecem sempre. Uma
  expressão longa é precisa e não apanha nada. São 185 expressões nas 16 áreas.
- **A ambiguidade trata-se por exclusão, não por precisão.** Seis áreas têm uma lista
  `excluir` que afasta o uso figurado: "ambiente de trabalho" não é Ambiente e Energia,
  "defesa do consumidor" não é Defesa Nacional, "fronteira entre o público e o privado"
  não é Administração Interna.
- **As expressões seguem as tutelas.** Cada área tem as palavras-chave das matérias que
  o respetivo ministério tutela, incluindo as das secretarias de Estado — é por isso que
  a política de imigração está na Presidência, que tem o Secretário de Estado Adjunto da
  Presidência e Imigração, e não na Administração Interna, a quem cabe o controlo de
  fronteiras. Uma remodelação governamental obriga a rever a lista, na constante `AREAS`.
- **Comparação entre áreas.** Legítima dentro do corpus: nenhuma área é truncada e o
  método é o mesmo para todas. As contagens medem o que as publicações subscritas
  noticiaram, não o total do que foi noticiado.
- **Imprensa apenas.** As plataformas sociais não publicam feeds e estão fora do
  âmbito da aplicação.
- **Responsabilidade editorial.** O painel é um instrumento de acesso e triagem: a
  leitura e a verificação são de quem o usa.

---

## Relatório diário por email

Todas as manhãs de dias úteis, às 10h17 de Lisboa, é enviado **um relatório por área governativa**
para os destinatários dessa área. Cada mensagem traz as notícias das últimas 24 horas
agrupadas por dia, com hora, título, resumo, publicação e ligação — e termina com um
botão para abrir o painel, onde se pode refazer a pesquisa, alargar o período ou
exportar para Excel.

O dia corre assim. As horas estão na **hora de Lisboa**, que é a que o painel e os
relatórios apresentam; entre parênteses fica a hora UTC, que é a que o GitHub usa nos
agendamentos e a única que aparece nos registos das execuções.

| Lisboa | UTC | O quê | Dias |
|---|---|---|---|
| 07h07 | 06h07 | 1.ª recolha | Todos |
| 09h07 | 08h07 | 2.ª recolha — é sobre esta que o Amália trabalha | Todos |
| 09h22 | 08h22 | Síntese do Amália | Seg a sex |
| 10h17 | 09h17 | Envio dos relatórios | Seg a sex |
| 11h07 · 13h07 · 15h07 · 17h07 · 19h07 | 10h07 · 12h07 · 14h07 · 16h07 · 18h07 | Recolhas do resto do dia | Todos |

São **sete recolhas por dia**, de duas em duas horas entre as 07h07 e as 19h07 de
Lisboa. Cada uma demora cerca de um minuto.

A sequência da manhã é encadeada de propósito: a recolha das 09h07 traz as notícias da
manhã, o Amália escreve as sínteses às 09h22 sobre essa recolha, e os relatórios saem
às 10h17 já com elas. As restantes recolhas não têm síntese nem envio — servem o painel.

**O painel não é instantâneo.** Não vai buscar notícias enquanto o consulta: lê os
ficheiros da última recolha. Quem o abrir às 16h vê o que foi recolhido às 15h07, e a
hora dessa recolha está sempre indicada ao lado do título das áreas.

Os minutos estão deslocados de propósito. Às horas certas o GitHub tem picos de
procura e as execuções agendadas são atrasadas — por vezes saltadas. Um minuto
qualquer a meio da hora é mais fiável.

A recolha corre **todos os dias**, incluindo fim de semana: de outro modo o arquivo
ficaria com um buraco de dois dias e o que fosse notícia ao sábado nunca chegaria ao
painel.

Os relatórios são enviados apenas em dias úteis, mas **à segunda-feira a janela alarga
automaticamente para 72 horas**, cobrindo sábado e domingo. É o que faz o valor `auto`
do período, que é a predefinição das execuções agendadas.

### Subscrever e cancelar

**No painel.** O botão *Receber por email* abre uma janela onde a pessoa indica o
endereço e escolhe as áreas. Ao confirmar, abre-se no seu programa de correio uma
mensagem já preenchida, dirigida à Unidade de Pesquisa e Estatísticas, que basta
enviar.

**Onde ficam os destinatários.** No segredo **`SUBSCRITORES`** do repositório, e não
num ficheiro. O repositório é público e os endereços são dados de contacto de
terceiros: num segredo não são legíveis por quem consulte o repositório, nem aparecem
nos registos das execuções.

O conteúdo é JSON, uma lista por área:

```json
{
  "areas": {
    "Saúde": ["nome@sggoverno.gov.pt", "gabinete@min-saude.gov.pt"],
    "Justiça": []
  }
}
```

O ficheiro `subscritores.json` do repositório é apenas o modelo, com as dezasseis
áreas e sem endereços. Serve para copiar a estrutura e para trabalho local.

**Processamento.** Em **Actions › Subscricao do relatorio › Run workflow**, com o
endereço e as áreas. O fluxo atualiza a lista, envia a confirmação e não deixa
qualquer endereço à vista.

Para o fluxo poder gravar no segredo é preciso um segundo segredo,
**`SUBSCRITORES_PAT`**, com um token de acesso pessoal de âmbito restrito — apenas
este repositório, apenas a permissão *Secrets: read and write*. Sem esse token o
fluxo corre na mesma e deixa a lista atualizada em *Artifacts*, para se colar à mão
no segredo.

Os nomes das áreas são tolerantes: aceitam-se sem acentos, em minúsculas e parciais —
`saude, agricultura` resolve para *Saúde* e *Agricultura e Mar*. Para todas, escrever
`todas`.

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

## Síntese redigida pelo Amália

No topo de cada relatório por correio eletrónico, um parágrafo por **origem de
imprensa** — Portugal, lusofonia e internacional —, com o que foi notícia na janela
do relatório. Não aparece no painel: aí a leitura é feita sobre os dados, com filtros
que a síntese não acompanharia.

A separação por origem existe porque a mistura confundia: o orçamento português e o
cabo-verdiano descritos no mesmo texto, como se fossem a mesma matéria. Cada parágrafo
leva a etiqueta da origem e o número de notícias que resume.

Uma origem só gera parágrafo se tiver pelo menos três notícias no período — abaixo
disso, um resumo não acrescenta nada à leitura dos próprios títulos.

A extensão acompanha o volume: até quinze notícias pedem-se três a cinco frases; até
quarenta, cinco a sete; acima disso, sete a dez. Resumir cento e trinta títulos em duas
frases não é síntese, é omissão.

### Como corre

O **Amália** é o modelo de linguagem do Estado, desenvolvido por um consórcio de
universidades portuguesas com coordenação da ARTE. Tem pesos abertos sob licença
Apache 2.0, pelo que corre **no próprio fluxo de trabalho**, sem serviço, credencial
ou contrato. Usa-se a conversão quantizada de 4 bits, com cerca de 5,5 GB, que dispensa
placa gráfica.

**Corre em paralelo, uma área por trabalho.** Sem placa gráfica, um parágrafo demora
vários minutos, e uma área com notícias nas três origens passa dos vinte. As dezasseis
em sequência levariam horas. Cada área tem por isso o seu próprio trabalho — o GitHub
corre até vinte em simultâneo em repositórios públicos — e um passo final junta as
partes num só `sinteses.json`. O tempo total passa a ser o da área mais demorada, não a
soma de todas.

Se alguma área falhar, as restantes seguem: mais vale um ficheiro com quinze áreas do
que nenhum.

O fluxo `sintese-amalia.yml` corre às 09h22 de Lisboa, entre a recolha das 09h07 e o
envio das 10h17, para que a síntese e a lista digam respeito ao mesmo momento. É
deliberadamente separado da recolha: se falhar ou demorar, as notícias do dia já estão
publicadas e o painel funciona na mesma. O modelo fica em cache entre execuções.

### Ensaiar sem esperar

O fluxo aceita o campo **"Ensaio: tratar só esta área"**. Preenchido, trata apenas essa
área e não grava — o texto fica visível no registo, para se avaliar a qualidade em
minutos em vez de uma hora.

O registo mostra, por área e por origem, quantas notícias foram encontradas, quantos
caracteres o modelo devolveu e quanto tempo demorou, e termina com um resumo das
sínteses escritas, das que ficaram por falta de notícias e das que falharam.

### Salvaguardas

O modelo recebe apenas os títulos já recolhidos, de uma origem de cada vez. Não acede à
internet, não é fonte de factos, e cada parágrafo é apresentado junto das notícias que o
originaram — a verificação continua do lado de quem lê. As instruções estão à vista no
`sintese_ia.py`, na constante `INSTRUCAO`, e proíbem juízos, recomendações e qualquer
facto que não esteja nos títulos.

O relatório recusa sínteses com mais de doze horas ou escritas sobre outra janela
temporal: uma síntese desfasada descreveria notícias que não estão na lista.

### Alternativa: serviço já instalado

Havendo um ponto de acesso ao Amália na infraestrutura do Estado, usa-se em vez do modo
local, com os segredos `AMALIA_ENDERECO` e `AMALIA_CHAVE`. É mais rápido; o resultado é
o mesmo.

```bash
python sintese_ia.py --local --dados arquivo.json --periodo 24h
python sintese_ia.py --local --dados arquivo.json --apenas "Finanças"   # ensaio
```

Sem modo local nem ponto de acesso, o programa não faz nada e a aplicação funciona como
antes, apenas sem os parágrafos.

---

## Pesquisa por termo livre

As palavras-chave definem o que cada área **classifica**. Um acontecimento que a
imprensa noticie sem usar nenhuma dessas expressões não entra na área — foi o que
sucedeu com a crise de Ceuta, noticiada em força sem que as expressões da Presidência a
cobrissem.

Para isso existe a caixa de **pesquisa por termo**, dentro da janela de uma área. Ao
contrário da seleção de palavras-chave, procura no `corpus.json` — **todos os artigos
lidos dos feeds nos últimos sete dias**, marcados ou não por qualquer área.

É, portanto, pesquisa livre sobre imprensa em bruto, sem sair do corpus próprio: nenhum
serviço externo é consultado, e o que se encontra continua a ser das 48 publicações
subscritas.

O ficheiro ronda os 7 MB com o volume atual. O painel só o carrega à primeira pesquisa
da sessão, o que demora alguns segundos; daí em diante fica em memória.

Quando os resultados vêm daqui, a etiqueta ao lado da contagem diz **"imprensa
recolhida"** em vez de "arquivo de 7 dias".

---

## Memória de longo prazo

O arquivo que o painel consulta guarda **sete dias** — é o que serve para trabalhar. A
memória do que foi noticiado guarda-se em duas camadas separadas, ambas cumulativas e
nunca apagadas.

### Série diária — `historico.json`

Escrita em cada recolha. Por dia e por área: quantas notícias, quantas eram novas face
à recolha anterior, quantas publicações distintas, a repartição por origem (Portugal,
lusofonia, internacional) e a contagem de cada palavra-chave.

São agregados, não notícias. Cerca de **2 KB por dia**, menos de 1 MB por ano. Chega
para responder a perguntas de tendência: que áreas cresceram, que assuntos ganharam
peso, como se distribuiu a atenção da imprensa ao longo de um semestre.

### O que fica e o que passa

| Ficheiro | Guarda | Por quanto tempo |
|---|---|---|
| `arquivo.json` | Notícias marcadas por área | 7 dias, sempre a deslizar |
| `corpus.json` | Imprensa em bruto, marcada ou não | 7 dias, sempre a deslizar |
| `historico.json` | Contagens por dia e por área | **Para sempre** |
| `meses/AAAA-MM.jsonl.gz` | Notícias marcadas, com título e resumo | **Para sempre** |

Para analisar o passado, o que conta são as duas últimas linhas. O `meses/` guarda
todas as notícias de cada dia, uma a uma; o `historico.json` guarda as contagens. Os
dois primeiros são de trabalho e não têm memória.

O que **não** fica é a imprensa não marcada: o `corpus.json` só existe para a pesquisa
por termo e não se acumula. Guardá-lo seria multiplicar por dez o espaço para conservar
artigos que nenhuma área classificou.

### Arquivo permanente — `meses/AAAA-MM.jsonl.gz`

Um ficheiro comprimido por mês, com **as notícias todas** desse mês: área, data,
publicação, título, resumo, ligação e palavras-chave que a marcaram. Sem repetições.

Uma linha por notícia, o que permite lê-lo de forma incremental sem carregar tudo em
memória. Com o volume atual, cerca de **110 KB por mês** — 1,3 MB por ano e menos de
7 MB em cinco anos, irrelevante para o repositório.

Nada o lê no dia a dia: existe para que daqui a um ano se possa voltar atrás e produzir
um relatório sobre o que foi noticiado, com os títulos e não apenas com as contagens.

```python
import gzip, json
with gzip.open("meses/2026-08.jsonl.gz", "rt", encoding="utf-8") as f:
    noticias = [json.loads(linha) for linha in f]
```

### O que isto permite mais tarde

Comparar semestres ou anos por área. Medir a concentração da cobertura em poucas
publicações. Ver que palavras-chave deixaram de render e quais surgiram. Reconstituir a
cobertura de um acontecimento passado com os títulos originais.

Uma ressalva metodológica: as palavras-chave mudam com as remodelações governamentais,
e as notícias ficam guardadas com a marcação do dia em que foram recolhidas. Comparar
períodos longos exige saber isso — a marcação de agosto de 2026 não é a mesma de um
Governo seguinte.

---

## Alargar o corpus

Acrescentar uma publicação é escrever uma linha nas listas `FONTES`,
`FONTES_LUSOFONAS` ou `FONTES_INTERNACIONAIS`, no início do `extrair_noticias.py`,
com o nome, o domínio e o endereço do feed. A recolha seguinte já a inclui.

Ajustar as áreas e as palavras-chave é editar a lista `AREAS`, no mesmo ficheiro.
O critério é o da expressão e não o da palavra solta — "alterações climáticas" e não
"clima" — e a correspondência aceita singular e plural.
