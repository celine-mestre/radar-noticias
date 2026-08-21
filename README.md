# Radar de Notícias por Área Governativa

Painel de monitorização de comunicação social organizado pelas 17 áreas governativas
do XXV Governo Constitucional.

**Secretaria-Geral do Governo** · Direção de Serviços de Suporte à Decisão ·
Unidade de Pesquisa e Estatísticas

👉 **[Abrir o painel](https://celine-mestre.github.io/radar-noticias/)**

---

## Como funciona

A recolha lê, de duas em duas horas, **64 órgãos de comunicação social** (66 entradas de leitura) — imprensa, rádio e
televisão, portugueses, lusófonos e internacionais, uns pelo feed próprio e outros via
Google Notícias — e marca cada artigo com as áreas governativas cujas
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
2. **Leitura das fontes, por duas vias.** A maioria das publicações é lida
   diretamente pelo seu endereço RSS. As que bloqueiam pedidos automáticos ou não
   publicam feed são lidas ao **Google Notícias, por pesquisa restrita ao domínio**
   (`site:expresso.pt`), com as ligações de reencaminhamento resolvidas para o
   endereço do jornal no fim da recolha. Em ambas as vias, cada artigo traz título,
   resumo, data de publicação, fonte e ligação direta.

   Um feed próprio mostra apenas as últimas notícias, e esse número varia muito: há
   feeds com setecentas e feeds com dez. Quando o feed de uma publicação **não cobre o
   tempo decorrido desde a recolha anterior** — que não é constante: duas horas de dia,
   oito entre a última recolha da noite e a primeira da manhã —, ou quando não responde,
   a leitura dessa publicação é completada, nessa passagem, pela mesma pesquisa ao
   Google. Sem isso, um jornal que publique mais notícias do que as que cabem no seu
   feed perde as mais antigas entre recolhas, sem deixar rasto.
3. **Marcação.** Para cada artigo, o programa procura literalmente as expressões de
   cada área no título e no resumo. Encontrando, marca o artigo com essa área e com
   as expressões que a acionaram. Um artigo pode ficar em mais de uma área.
4. **Gravação.** Os artigos marcados são acumulados no `arquivo.json`, sem
   repetições, mantendo sete dias. Gravam-se também o retrato do dia, o `corpus.json`
   (todos os artigos lidos, marcados ou não, para a pesquisa por termo), a série
   diária de contagens e o arquivo mensal permanente. Ainda na mesma execução,
   o `alertas.py` compara o volume do dia com o comportamento habitual de cada área
   e grava os picos noticiosos e o momentum.
5. **O sentimento, a cada recolha.** Cada recolha encadeia o Amália, que classifica
   o tom das notícias da comunicação social nacional ainda sem avaliação e grava o
   `sentimentos.json`. É incremental e só arranca havendo trabalho que o justifique
   (pelo menos quinze notícias por avaliar), pelo que as recolhas sem novidade não
   chegam a carregar o modelo. Corre à parte, sem atrasar a recolha nem o relatório.
6. **E o resumo dos picos.** Havendo picos noticiosos ainda por explicar, o Amália lê
   as notícias reais desse dia e dessa área no arquivo mensal e escreve, em três ou
   quatro frases, o que motivou o pico — para `picos-resumos.json`, que a evolução
   mostra ao clique.
7. **E o resumo dos dias muito negativos.** Depois de o tom estar avaliado, as áreas
   cuja cobertura do dia foi negativa em 75% ou mais recebem também um resumo do
   Amália, escrito a partir dos títulos das notícias negativas desse dia — para
   `matriz-resumos.json`, que a matriz do tom mostra ao passar o cursor.
8. **No painel.** O radar lê o `arquivo.json` e conta as notícias de cada área
   dentro do período e da origem escolhidos. Ao abrir uma área, o mesmo ficheiro é
   filtrado pelas palavras-chave selecionadas. As duas contagens seguem os mesmos
   critérios, pelo que dizem sempre o mesmo número. Tudo local, em milissegundos.

Nada disto passa por serviços intermediários nem depende da rede de quem consulta.

---

## O que o painel faz

**Entrada em radar.** As dezassete áreas dispostas em círculo, ordenadas por volume de
notícias, com a distância ao centro a significar quanto foi noticiado — quanto mais
perto do centro, mais notícias. Ao centro, o total do período e da origem escolhidos.
Em ecrãs estreitos o círculo dá lugar a uma grelha de cartões, que faz o mesmo trabalho.

**Predefinições.** Últimos sete dias e comunicação social de todas as origens. O período vai das
24 horas aos sete dias que o arquivo guarda; a origem escolhe entre Portugal, lusofonia,
internacional ou todas. Ambos valem para o radar e para as consultas.

**Uma área abre-se num clique**, já com as notícias recolhidas. Dentro da janela:

- As palavras-chave da área **recolhidas por defeito**, num botão que as mostra a pedido —
  para as notícias terem o espaço todo, sobretudo no telemóvel. Abertas, selecionam-se
  uma a uma ou em conjunto, com a consulta a refazer-se no momento; ao lado, uma caixa
  para pesquisa por termo livre.
- Seletores de período, OCS e **área**, este último para trocar de área sem fechar
  a janela — útil para comparar duas áreas com os mesmos critérios.
- Botão para **ampliar** a janela a quase todo o ecrã, e outro para voltar ao radar.
- Notícias por ordem cronológica, agrupadas por dia, com hora, imagem quando a
  publicação a fornece, resumo, publicação e etiqueta de origem.
- Síntese com indicadores: distribuição por publicação, assuntos recorrentes, cobertura
  de cada palavra-chave e evolução da área ao longo do período escolhido.
- Impressão em PDF com cabeçalho institucional, e exportação para Excel com folha de
  notícias — incluindo o tom de cada notícia, quando avaliado —, folha de especificações
  e folha de síntese, esta com o tom do conjunto, por assunto.

**Manual embutido, com a lista das fontes.** O painel traz um manual de dez capítulos,
o último dos quais lista **todas as publicações subscritas**, repartidas por origem e com
a via por que são lidas — feed próprio ou Google Notícias —, mais as três razões pelas
quais uma publicação da lista pode não aparecer nos quadros: escreve noutra língua, não
publicou nada da área, ou não respondeu à recolha. A lista acompanha a configuração, pelo
que não fica para trás quando uma fonte entra ou sai.

**Alertas de pico noticioso.** Quando uma área dispara — um volume de notícias muito
acima do seu comportamento habitual —, o painel abre com uma faixa de alerta, e o
relatório diário assinala-o. Abaixo, o *momentum* do dia: as cinco áreas mais acima da sua
mediana. O método está descrito na tabela de ficheiros (`alertas.json`) e no manual.

**Sentimento da cobertura, em validação.** O Amália classifica o tom (positivo, neutro,
negativo) das notícias da comunicação social nacional — e só dessas: as origens lusófona
e internacional servem outra leitura, a da reputação externa, que fica para depois. As
avaliações aparecem como um ponto junto a cada notícia e como distribuição agregada, mas
só quando há cobertura suficiente para a leitura ser fiável (ao menos 60% das notícias
nacionais do período avaliadas, e nunca menos de oito). Abaixo desse patamar o painel
diz que está à espera, em vez de mostrar proporções que enganam.

Na síntese de cada área há ainda duas leituras que a evolução não dá: o **tom por
publicação** — que órgãos escrevem em tom mais negativo sobre aquela área — e o **tom por
assunto**, que mostra quais as palavras-chave que carregam esse tom. Ambas assinalam quem
se afasta dez ou mais pontos percentuais da média da área, e exigem pelo menos cinco
notícias avaliadas por linha, porque abaixo disso uma proporção não diz nada. Enquanto a
leitura humana não estiver concluída, tudo isto mostra o rótulo «em validação».

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
| `historico.json` | **Série diária.** Por dia e por área: marcações, publicações distintas, repartição por origem e contagem de cada palavra-chave — e, por dia, quantas notícias DISTINTAS houve. A distinção importa: uma notícia que satisfaz três áreas deixa três marcações e é contada em cada uma delas, pelo que somar as áreas dá marcações e não notícias (cerca de 1,3 áreas por notícia). Cada notícia conta uma só vez, no dia em que foi publicada. Agregados, não notícias. (O ficheiro guarda ainda um campo `novas`, vestígio de quando a série era construída recolha a recolha; hoje é igual a `notícias` e não é usado.) |
| `alertas.json` | **Picos noticiosos e momentum.** Escrito pelo `alertas.py` após cada recolha: compara o volume do dia, por área, com a mediana dos últimos 28 dias *à mesma hora* (desvio robusto, mínimo de 8 notícias de subida, piso de 12). Guarda os picos do dia, o top 5 do momentum e o histórico acumulado. Depois de uma mudança de método de leitura, e enquanto a base de 28 dias ainda apanhar dias do método anterior, tanto o dia como a base são contados **apenas nas publicações cuja leitura não mudou** — as que já marcavam com regularidade antes da mudança —, e o ficheiro regista esse regime em `transicao_fontes`. É o que mantém os picos comparáveis sem os calar; ver as ressalvas metodológicas. |
| `corpus.json` | **Comunicação social em bruto, sete dias.** Todos os artigos lidos dos feeds, marcados ou não. Serve a pesquisa por termo livre; o painel só o carrega quando alguém pesquisa. |
| `sentimento_ia.py` + `.github/workflows/sentimento-amalia.yml` | **Sentimento em validação.** A cada recolha, o Amália classifica o tom (positivo, neutro, negativo) das notícias da comunicação social nacional ainda sem avaliação — e só dessas —, em lotes, e grava sentimentos.json e a série sentimento-serie.json (agregados por área e dia). O critério de arranque é o trabalho pendente, não a hora: sem pelo menos quinze notícias por avaliar, o modelo nem chega a ser carregado. As avaliações aparecem no radar (ponto junto a cada notícia, distribuição da consulta, e o tom por assunto na síntese), na evolução (barras por dia, semana ou mês) e no Excel (coluna própria e secções na folha de síntese), sempre com o rótulo «em validação» até a leitura humana estar concluída — a funcionalidade é definitiva; o rótulo é temporário. |
| `sentimento-meses/AAAA-MM.jsonl.gz` | **Arquivo permanente das avaliações.** Uma linha por notícia avaliada (ligação, tom, dia), acumulada por mês e nunca podada — ao contrário do `sentimentos.json`, que é o ficheiro de trabalho e guarda só a janela recente. Uma avaliação é um facto que não muda, pelo que fica guardada de vez: é isto que permitirá alargar a janela do painel, ou repescar meses inteiros, sem mandar o Amália reclassificar o que já classificou. Cerca de 70 KB por dois mil registos. |
| `resumo_picos.py` + `.github/workflows/resumo-picos.yml` | **Porquê de cada pico.** Para cada pico registado no alertas.json, recupera as notícias reais desse dia e dessa área do arquivo mensal — que guarda tudo, para lá dos sete dias do corpus — e pede ao Amália um resumo de três ou quatro frases do que aconteceu. Grava picos-resumos.json, que a evolução mostra ao clicar num pico. Incremental: um pico já resumido não volta a ser tratado, e o modelo só é carregado havendo picos por explicar. O resumo é sempre sobre notícias que existem; não havendo, o painel di-lo em vez de inventar. |
| `publicacoes.json` | **Publicações por dia e por área.** As doze que mais noticiaram cada área em cada dia, escritas pelo fecho dos dias. Cerca de 3,5 KB por dia, e só se guardam os últimos 120 dias. Guardam-se as **25 publicações** com mais volume em cada área e cada dia: com doze, que era o valor inicial, o alargamento da leitura fez a perda saltar de 1% para 17,5% das marcações, porque uma área passou a ser noticiada por dezanove publicações por dia em vez de nove. Com vinte e cinco, fica de fora cerca de 1%, sempre de quem teve pouco volume nesse dia. Alimenta dois quadros da evolução: as publicações especializadas e o peso de cada publicação no corpus. |
| `reconstruir_series.py` | **Fecho dos dias passados.** Corre a seguir a cada recolha e reconta todos os dias anteriores a hoje a partir do `meses/` e do `sentimento-meses/`, que são permanentes e refletem sempre as expressões em vigor. Sem isto, um dia que saísse da janela de sete dias ficava congelado com o número que tinha nesse momento: não acompanhava a revalidação das expressões nem as notícias do fim da noite, que só entram na recolha da manhã seguinte. Idempotente e não toca no dia em curso. |
| `retroativo_pm.py` + `.github/workflows/retroativo-pm.yml` | **Passo retroativo, execução única.** Revalida todas as marcações existentes sob as regras atuais (retirando pares de expressões entretanto removidas, como «empresas») e reclassifica o corpus de 7 dias com as áreas e expressões novas, injetando o resultado no arquivo, no retrato, no arquivo mensal, na série diária e nos alertas. Idempotente: correr duas vezes não duplica nem retira mais nada. |
| `meses/AAAA-MM.jsonl.gz` | **Arquivo permanente e integral.** Um ficheiro comprimido por mês com todas as notícias desse mês — as marcadas com a sua área, e as não marcadas com área vazia (guardadas para que os passos retroativos futuros tenham meses de profundidade, e não apenas os sete dias do corpus). A área vazia é ignorada por tudo o que conta por área. ~2–3 MB/mês. |
| `verificar_fontes.py` + `.github/workflows/verificar-fontes.yml` | **Estado das fontes, a pedido.** Testa as 66 entradas — as diretas pelo seu endereço, as da via Google pelo endereço da pesquisa — e, para as que falham, experimenta endereços alternativos conhecidos e a autodescoberta (os feeds que a própria página inicial anuncia). Grava `fontes-estado.json` e um quadro legível no Summary da execução. Nasceu da auditoria de agosto de 2026, em que 34 das então 73 entradas estavam em falha silenciosa; corre à mão, no botão *Run workflow*. |
| `fontes-estado.json` | **Resultado da última verificação de fontes**: entrada a entrada, se responde, com quantos artigos, e que endereço alternativo responde quando o configurado falha. |
| `fontes-recolha.json` | **Relatório de CADA recolha, fonte a fonte:** por que via foi lida (feed próprio, Google Notícias, ou feed completado pela pesquisa), quantos artigos deu, quantos marcou e que erro teve, mais o intervalo decorrido desde a passagem anterior. Nasceu de uma constatação incómoda: as falhas só existiam no registo da execução, que ninguém lê, e por isso uma publicação podia desaparecer durante semanas sem que nada o dissesse. É também daqui que o manual do painel monta a lista das fontes. |
| `resumo_matriz.py` + `.github/workflows/resumo-matriz.yml` | **Porquê dos dias marcantes.** Para cada célula da matriz do tom que passe os **75% de notícias negativas** ou os **50% de positivas** (com pelo menos oito avaliadas), reúne os títulos das notícias desse tom nesse dia e nessa área e pede ao Amália três ou quatro frases sobre o que aconteceu. Os limiares são diferentes porque a realidade também é: metade das notícias de uma área serem positivas já é um dia fora do comum. Grava `matriz-resumos.json`, que a matriz mostra ao passar o cursor. Corre a seguir ao sentimento — não à recolha —, porque só há coberturas negativas a explicar depois de o tom estar avaliado; é incremental e tem teto por passagem. Resume **por dia**, que é o átomo que nunca muda: nas vistas por semana ou por mês, o painel junta os resumos dos dias que compõem o período, sem gerar nada de novo. |
| `matriz-resumos.json` | Os resumos acima, indexados por dia e área, com a percentagem de negativas e o número de notícias que os sustentam. |

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

**Portugal — 31 entradas de 31 publicações.**
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

**Lusofonia — 11 entradas de 11 publicações.**
Angola: Jornal de Angola, Novo Jornal e Angop. Moçambique: O País e Carta de Moçambique.
Cabo Verde: Expresso das Ilhas e Inforpress. São Tomé e Príncipe: STP-Press.
Timor-Leste: Tatoli. Brasil: Agência Brasil e Folha de S.Paulo.

Matéria de CPLP, cooperação e diáspora é frequentemente tratada primeiro nestes títulos.

**Internacionais — 24 entradas de 22 publicações.**
Em português: Euronews, Deutsche Welle e RFI. Em inglês: France 24 (a edição
portuguesa não existe — é a RFI que a tem).
União Europeia: Politico Europe.
Espanha: El País (geral e internacional), El Mundo, La Vanguardia e ABC.
Reino Unido: BBC News, BBC Mundo e The Guardian (Europa e mundo).
França: Le Monde, Le Figaro e France Info.
Itália: ANSA, Corriere della Sera e La Repubblica.
Estados Unidos da América: The New York Times, The Washington Post e Politico.
Alemanha: Der Spiegel.

**São 66 entradas de 64 publicações.** A diferença são duas publicações com duas entradas
cada — o El País e o The Guardian, que publicam feeds separados para a secção internacional.
As repetições, quando as há, são descartadas na recolha.

### Duas vias de leitura

A verificação de agosto de 2026 (`verificar_fontes.py`) mostrou que nem todas as
publicações se deixam ler pelo feed: umas bloqueiam pedidos vindos de infraestruturas
de nuvem como a do GitHub, outras deixaram de publicar feed ou nunca o tiveram. A
recolha usa por isso duas vias:

- **Leitura direta do RSS** — a via principal, para a maioria das publicações.
- **Google Notícias, por pesquisa restrita ao domínio** (`site:expresso.pt`) — para as
  18 publicações da constante `VIA_GOOGLE` do `extrair_noticias.py`: Expresso,
  SIC Notícias, Jornal de Notícias, Diário de Notícias, TSF, Renascença, Diário de
  Notícias da Madeira, Jornal i, JM Madeira, Vida Económica, Construir, Executive
  Digest, Lusa, Jornal de Angola, Novo Jornal, Angop, Inforpress e
  Deutsche Welle. A janela é de um dia por consulta, para ficar aquém do teto de 100
  resultados do Google — acima disso a ordenação deixa de ser cronológica —, e com
  oito recolhas diárias nada se perde. O nome e o domínio vêm do próprio Google, a
  cauda « - Fonte» do título é retirada e as ligações são resolvidas para o endereço
  do jornal.

A 19 de agosto de 2026 saíram da lista sete entradas que não produziam uma única
notícia por via nenhuma: os **quatro feeds temáticos do Público** (descontinuados; o
feed geral continua a ser lido), a **Lusa · Internacional** (redundante com a Lusa via
Google), a **Associated Press** (retirou os feeds públicos — o hub responde 401) e o
**EURACTIV** (bloqueia a leitura direta e escreve em inglês, pelo que a pesquisa
portuguesa do Google não o alcança). Manter entradas mudas só inflacionava a contagem
das fontes.

O estado das fontes fica registado em dois sítios: o `fontes-recolha.json`, escrito por
**cada recolha**, diz por publicação quantos artigos deu, quantos marcou e por que via;
e o fluxo **Verificar fontes** (Actions), que se corre à mão, testa as 66 entradas e
grava o `fontes-estado.json` com endereços alternativos para as que falham.

### Quantas publicações marcam, de facto

Das **64 publicações**, só as que escrevem em português são classificadas por área — são
**45**. As outras 19 são a imprensa estrangeira em língua estrangeira, que entra apenas no
corpus da pesquisa por termo. Destas 45, num dia útil marcam tipicamente **35 a 40**: as
de nicho (Construir, Vida Económica, Ambiente Magazine) só marcam quando têm matéria da
sua área, e ao fim de semana o número desce. É por isso que o quadro das publicações do
painel de evolução mostra menos nomes do que a lista de fontes — e não porque falte
alguma.

As restantes entram no corpus da pesquisa por termo — ver a secção seguinte.

### Língua das fontes estrangeiras

As palavras-chave estão em português. A classificação por área funciona, portanto, sobre
as publicações que escrevem em português: as nacionais, as lusófonas e as edições
portuguesas da Euronews, da Deutsche Welle e da RFI.

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
  âmbito da aplicação, que é a comunicação social.
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

- **Cobertura.** O corpus são as 64 publicações subscritas e os últimos sete dias.
  Uma notícia de um título não subscrito, ou anterior a esse período, não está no
  corpus. A janela do arquivo define-se com `--dias-arquivo` e pode ser alargada
  quando houver espaço para isso.
- **Duas contagens diferentes, ambas certas: notícias e marcações.** Uma notícia que
  satisfaz três áreas deixa três marcações e conta em cada uma delas. Os quadros que
  respondem a «quanto se noticiou» usam notícias; os que respondem a «quanto pesou cada
  área» usam marcações. Cada quadro diz qual usa, e o rácio anda pelas 1,3 marcações por
  notícia.
- **Durante uma transição de método, os picos contam num universo mais estreito.** Quando
  o modo de leitura muda — mais publicações lidas, ou leitura mais funda —, comparar o dia
  de hoje com uma mediana de dias medidos de outra maneira produziria alarmes falsos. Por
  isso, enquanto a base de 28 dias ainda apanhar dias do método anterior, os picos são
  calculados apenas nas publicações cuja leitura não mudou: as que já marcavam com
  regularidade antes. **As contagens do quadro dos picos ficam assim menores do que as dos
  restantes quadros**, que contam tudo — no mesmo dia e na mesma área, um pico pode dizer
  52 notícias e o gráfico de volume dizer 109, sem que nenhum esteja errado. O painel
  assinala-o com a etiqueta «contagem restrita», e a restrição desaparece sozinha quando a
  base ficar toda no método novo.
- **O tom não se reparte por publicação.** A avaliação do Amália mede o tom do
  acontecimento noticiado, não a orientação editorial de quem o noticia, e é automática
  e ainda em validação. Por isso o painel mostra o tom da área e dos seus assuntos, e
  não uma ordenação de órgãos de comunicação social — que seria um juízo que o
  indicador não sustenta e que não cabe a um organismo do Estado produzir. A
  repartição por publicação existe nos dados para efeitos de análise interna; não é
  mostrada nem exportada. Pela mesma razão, os resumos dos dias muito negativos descrevem
  **acontecimentos** — que casos, decisões ou problemas estão por trás dos títulos — e
  nunca a atitude dos jornais ou a qualidade da cobertura.
- **Marcação literal.** Um artigo entra numa área por conter a expressão no título ou
  no resumo. Um artigo que trate do tema sem usar a expressão não é apanhado.
- **As expressões são curtas, como a imprensa escreve.** "política de imigração" quase
  nunca aparece num título; "imigração", "imigrantes" e "migrantes" aparecem sempre. Uma
  expressão longa é precisa e não apanha nada. São 276 expressões nas 17 áreas, incluindo os cargos governativos (ministro e secretários de Estado de cada pasta, com alternância automática de género).
- **O Primeiro-Ministro é a 17.ª área,** no topo da ordem protocolar. Como não tem
  matéria setorial própria — não há «assuntos do PM» com léxico específico —, a área
  assenta no titular e no cargo: «Luís Montenegro», «primeiro-ministro português»,
  «XXV Governo», com exclusões locativas para o país e a cidade homónimos. É a exceção
  à regra de que as áreas se definem pela matéria tutelada.
- **Áreas vizinhas separam-se pela tutela, não pelo tema.** Três áreas tratam de pessoas
  que atravessam fronteiras, e a fronteira entre elas é a das secretarias de Estado. A
  **Presidência** tem a política de imigração, a AIMA, as autorizações de residência, a
  nacionalidade e o acolhimento — é quem tem o Secretário de Estado Adjunto da
  Presidência e Imigração. A **Administração Interna** tem o controlo de fronteiras, os
  pedidos de asilo e os refugiados, que são matéria de segurança. Os **Negócios
  Estrangeiros** tratam do movimento inverso: emigrantes, comunidades portuguesas, rede
  consular e diplomacia.
- **A Administração Pública está nas Finanças**, e não na Reforma do Estado, porque é lá
  que está a respetiva Secretária de Estado. À Reforma do Estado cabem a digitalização e
  a simplificação: automatização de processos, interoperabilidade, identificação digital
  e dados abertos.
- **A ambiguidade trata-se por exclusão, não por precisão.** Sete áreas têm uma lista
  `excluir` que afasta o uso figurado: "ambiente de trabalho" não é Ambiente e Energia,
  "defesa do consumidor" não é Defesa Nacional, "fronteira entre o público e o privado"
  não é Administração Interna.
- **As expressões seguem as tutelas.** Cada área tem as palavras-chave das matérias que
  o respetivo ministério tutela, incluindo as das secretarias de Estado — é por isso que
  a política de imigração está na Presidência, que tem o Secretário de Estado Adjunto da
  Presidência e Imigração, e não na Administração Interna, a quem cabe o controlo de
  fronteiras. Os cargos entram pela função, não pelo nome — «ministro da Saúde», e não o
  titular do momento —, e a marcação alterna o género sozinha («ministra da Saúde» conta
  na mesma), pelo que uma troca de titular ou uma remodelação normal não obriga a mexer
  em nada; só uma mudança de orgânica (pastas criadas, extintas ou renomeadas) pede uma
  revisão da constante `AREAS`.
- **Comparação entre áreas.** Legítima dentro do corpus: nenhuma área é truncada e o
  método é o mesmo para todas. As contagens medem o que as publicações subscritas
  noticiaram, não o total do que foi noticiado.
- **Quebra de série a 17–19 de agosto de 2026.** Em três dias mudaram duas coisas na
  leitura. Primeiro, o conjunto de fontes: a correção dos endereços recuperou títulos
  que estavam em falha silenciosa (Correio da Manhã, Notícias ao Minuto, Sábado,
  Açoriano Oriental) e a via Google Notícias trouxe de volta o Expresso, a SIC, o JN, o
  DN, a TSF e a Lusa. Depois, a profundidade: os feeds curtos — o do Público mostra dez
  notícias, e o jornal publica mais de dez em duas horas nos dias movimentados — passaram
  a ser completados pela pesquisa ao domínio, deixando de se perder o que saía do feed
  entre recolhas. **O radar passou a ver mais; não houve mais notícias.** Comparações que
  atravessem esta data medem as duas coisas ao mesmo tempo. O painel de evolução assinala
  as duas datas no gráfico de volume, com a explicação no cursor. Os **alertas de pico**
  não são afetados: em vez de ficarem calados durante semanas, passam a medir no
  subconjunto de publicações cuja leitura não mudou — ver a ressalva sobre as transições
  de método, acima. A restrição levanta-se sozinha a 16 de setembro de 2026, quando a base
  de 28 dias estiver toda no método novo.

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

O dia corre assim. **Um único agendamento**, o da recolha; os outros dois arrancam
quando o anterior termina.

| Lisboa | O quê | Como arranca |
|---|---|---|
| 07h07 · 09h07 · 11h07 · 13h07 · 15h07 · 17h07 · 19h07 · 23h07 | Recolha | Agendada, todos os dias |
| a seguir à recolha das 09h07 | Síntese do Amália | Quando a recolha termina, em dias úteis |
| a seguir à síntese | Envio dos relatórios | Quando a síntese termina, em dias úteis |

São **oito recolhas por dia**: de duas em duas horas entre as 07h07 e as 19h07, mais uma
às 23h07, que apanha o que a comunicação social publica ao serão. Cada recolha demora cerca
de um minuto.

**Quando um dia fecha.** Não às 23h07: essa recolha não chega às 23h59, e o que sai depois
dela só é lido na manhã seguinte — cerca de 2% das marcações, com dias a chegar aos 5%. O dia
D fica selado na **primeira recolha de D+1**, quando o `reconstruir_series.py` o reconta do
arquivo mensal já com tudo o que foi publicado entre as 00h00 e as 24h00 desse dia. A
arrumação é sempre pela data de publicação, em hora de Lisboa, e nunca pela hora da recolha.

**Porque é encadeado e não agendado.** Com três horários independentes, bastava a
recolha atrasar-se dez minutos para a síntese trabalhar sobre as notícias da véspera, e
o relatório sair sem as da manhã. Pior: as execuções agendadas do GitHub são atrasadas
em períodos de muita procura e, por vezes, saltadas — foi o que sucedeu nos primeiros
dias, em que nem a síntese nem o relatório chegaram a disparar.

**Como está feito.** A síntese e o relatório são *fluxos chamáveis*: o
`radar-noticias.yml` chama-os como trabalhos seus, com `uses:`, logo a seguir à
recolha. Correm dentro da mesma execução — vê-se tudo numa página só — e não dependem
de qualquer gatilho entre fluxos. Experimentámos antes o `workflow_run`, que dispara um
fluxo quando outro termina, e não se mostrou fiável.

Há assim **um só agendamento** em toda a aplicação: o da recolha.

**Uma vez por dia, e na recolha certa.** A síntese e o relatório saltam a recolha das
07h07 — a essa hora a comunicação social ainda mal publicou e o relatório sairia com as notícias
da véspera. É a das 09h07 que os desencadeia.

A partir daí a verificação é "já se fez hoje?" e não "que horas são?". A síntese olha
para a data do `sinteses.json`; o relatório para o ficheiro `ultimo-relatorio.txt`. As
recolhas seguintes encontram o trabalho feito e desistem — mas se a das 09h07 falhar,
qualquer recolha posterior do mesmo dia assume o encargo. Há margem para atrasos sem
que o dia saia duplicado.

Assim o circuito não depende de uma hora certa, e pode ser ensaiado a qualquer momento —
basta correr a recolha à mão. Executadas manualmente, a síntese e o relatório seguem
sempre, sem estas verificações: um ensaio não deve ser recusado por serem quinze horas.

O relatório sai mesmo que a síntese falhe: nesse caso vai sem o parágrafo, que é
acessório. As notícias é que não podem faltar.

**O painel não é instantâneo.** Não vai buscar notícias enquanto o consulta: lê os
ficheiros da última recolha. Quem o abrir às 16h vê o que foi recolhido às 15h07, e a
hora dessa recolha está sempre indicada ao lado do título das áreas.

A recolha corre **todos os dias**, incluindo fim de semana: de outro modo o arquivo
ficaria com um buraco de dois dias e o que fosse notícia ao sábado nunca chegaria ao
painel.

Os relatórios são enviados apenas em dias úteis, mas **à segunda-feira a janela alarga
automaticamente para 72 horas**, cobrindo sábado e domingo. É o que faz o valor `auto`
do período, que é a predefinição das execuções agendadas.

### Enviar a um só endereço

Na execução manual do fluxo, o campo **destinatário** dirige o envio a um único endereço,
sem tocar na lista de subscritores. Serve para ensaiar, ou para mostrar a ferramenta a
alguém antes de a subscrever.

O campo **áreas** limita quais são enviadas — por vírgula, ou vazio para todas as que
tiverem notícias. Sem destinatário indicado, ambos os campos são ignorados e seguem os
subscritores de cada área, como sempre.

O endereço é ocultado nos registos da execução, como os restantes.

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

O ficheiro `subscritores.json` do repositório é apenas o modelo, com as dezassete
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

**Uma origem só gera parágrafo se tiver pelo menos três notícias no período.** Abaixo
disso, um resumo não acrescenta nada à leitura dos próprios títulos — e é por isso que
uma área pode ter parágrafo de Portugal e não ter de internacional, sem que haja falha
nenhuma. O mínimo altera-se com `--minimo`.

### Os dois países

Há dois países em jogo e o modelo confunde-os com facilidade. O de **quem publica** é
sempre conhecido: vem do domínio da publicação. O de **que a notícia trata** só se sabe
se o nome estiver escrito no título.

A instrução exige, por isso, que o parágrafo abra declarando a proveniência — "a
imprensa de Cabo Verde noticiou" — e que nenhum lugar seja nomeado sem constar do
título. Um jornal angolano noticia o mundo inteiro; escrever "Em Angola" por a fonte ser
angolana é o erro a evitar.

Sendo um modelo de 9 mil milhões de parâmetros a correr num processador, a distinção
nem sempre lhe sai bem. Não convencendo, há uma saída conservadora: limitar a síntese à
imprensa portuguesa, com `--origens nacionais` — ou, no fluxo, escrevendo `nacionais` no
campo das origens do `radar-noticias.yml`. Um parágrafo certo sobre Portugal vale mais
do que três parágrafos com países trocados.

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
vários minutos, e uma área com notícias nas três origens passa dos vinte. As dezassete
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

É, portanto, pesquisa livre sobre comunicação social em bruto, sem sair do corpus próprio: nenhum
serviço externo é consultado, e o que se encontra continua a ser das 48 publicações
subscritas.

O ficheiro ronda os 7 MB com o volume atual. O painel só o carrega à primeira pesquisa
da sessão, o que demora alguns segundos; daí em diante fica em memória.

Quando os resultados vêm daqui, a etiqueta ao lado da contagem diz **"comunicação social
recolhida"** em vez de "arquivo de 7 dias".

---

## Painel de evolução

`evolucao.html`, ao lado do painel principal e ligado a ele pelo ícone de gráfico. Lê o
`historico.json` e mostra a série ao longo do tempo. Os quadros estão pela ordem em que
a leitura se aprofunda — do agregado ao detalhe, e cada coisa primeiro vista e depois
explicada:

1. **Volume ao longo do tempo**, repartido por origem, em **notícias**. Clicar numa barra
   passa os quadros seguintes a mostrar apenas esse período. Riscas tracejadas assinalam
   as fronteiras de semana e as **mudanças de método de leitura**, cuja explicação está no
   cursor e na nota do quadro.
2. **Volume por área governativa**, em **marcações** — porque aqui uma notícia conta em
   cada área que satisfaz —, com a parte de cada área e o rácio entre marcações e notícias.
3. **Trajetória de cada área**: uma linha por área a percorrer o período todo, a cheia com
   o volume total e a tracejada só com a parte de Portugal. **Losangos vermelhos** marcam
   os dias de pico — vê-se a forma que cada pico fez na história da área, e o quadro
   seguinte diz o que o motivou. Com uma área escolhida, junta-se-lhe a **evolução do
   tom**: a percentagem de negativas período a período, com a linha interrompida onde
   faltam avaliações, em vez de cair a zero.
4. **Picos noticiosos registados**, com o volume do dia, a mediana da área e quantas vezes
   o dia esteve acima dela. Ordenam-se **por data** (do mais recente, agrupados por dia),
   **por intensidade** ou **por área**, conforme a pergunta seja o que houve ontem, quais
   foram os maiores ou como se tem comportado cada área. Clicar num pico abre o resumo do
   Amália sobre o que o motivou.
5. **Sentimento da cobertura**, em barras por dia, semana ou mês, apenas da comunicação
   social nacional e sujeito ao patamar de cobertura.
6. **Tom por área e período**: matriz com a percentagem de negativas — ou de positivas,
   à escolha — em cada área e cada período, numa escala sequencial: a cor carrega com o
   valor, e os dois lados mostram-se **à vez**, nunca juntos, porque não são
   complementares (18% de negativas não quer dizer 82% de positivas: pelo meio estão as
   neutras). As células que passam o limiar têm um canto dobrado e trazem o **resumo do
   Amália** sobre o que aconteceu nesse dia — no cursor, ou ao toque, num painel por baixo
   da matriz.
7. **De onde vêm as notícias**: quantas marcações vieram de cada publicação, em barras
   ordenadas. É a leitura de **dependência** e não de especialização: um órgão transversal,
   que não se destaca em área nenhuma, pode ser ainda assim a maior fonte do corpus. A nota
   diz quantas publicações chegam para metade de tudo o que o painel conta.
8. **Publicações especializadas**: que órgãos cobrem uma área **acima** da parte que têm no
   conjunto — escolha editorial, não volume. Vem depois do quadro anterior de propósito: o
   índice de especialização é calculado sobre esses pesos, e lê-se melhor com o denominador
   já sabido.
9. **Palavras do período**: nuvem com as expressões que trouxeram notícias — o tamanho vale
   pela quantidade, e as que ficaram a zero são candidatas a revisão.

10. **Duas áreas lado a lado**, escolhendo comparar: as duas linhas na mesma escala e um
   quadro com totais, médias, maior período, períodos em que cada uma esteve à frente,
   origem das notícias, picos, quem mais as cobre, os **assuntos que mais pesaram** em
   cada uma e o tom. Fecha o painel porque é uma síntese: usa o que os quadros anteriores
   estabeleceram — publicações, picos, tom — para responder a uma pergunta que nenhum
   deles faz sozinho.

- **As explicações vivem atrás de um «i»** ao lado do título de cada quadro, para não
  encherem o ecrã no telemóvel; na impressão voltam todas à vista.
- **Legibilidade com muitos dias**: acima de 45 dias na janela o gráfico passa sozinho a
  semanas, acima de 240 a meses, dizendo que o fez — quem carregar num botão de agregação
  passa a mandar.
- **Um período escolhido vale para tudo**: cada quadro escreve no título o período a que
  responde. As exceções dizem-no: a trajetória percorre sempre o intervalo inteiro e
  assinala o período com um ponto.
- Seletores de janela (30 dias, 90, um ano, tudo), de agregação (dia, semana, mês), de
  origem (Portugal, lusofonia, internacional, todas), de **agrupamento temático** e de
  **área governativa**, que reduzem todos os quadros ao que se escolheu.
- Modo claro e escuro, ecrã inteiro, impressão em PDF, exportação para Excel com oito
  folhas, e manual de leitura embutido.

Não precisa de servidor: é um ficheiro estático no mesmo GitHub Pages.

---

## Memória de longo prazo

O arquivo que o painel consulta guarda **sete dias** — é o que serve para trabalhar. A
memória do que foi noticiado guarda-se em duas camadas separadas, ambas cumulativas e
nunca apagadas.

### Série diária — `historico.json`

Escrita em cada recolha. Por dia e por área: quantas notícias foram **publicadas nesse
dia**, quantas publicações distintas as trouxeram, a repartição por origem (Portugal,
lusofonia, internacional) e a contagem de cada palavra-chave.

**A série é reconstruída do arquivo, não da recolha em curso.** Cada execução recalcula
os sete dias que o arquivo cobre e reescreve-os. É o que garante que a soma da série é
igual ao que o painel mostra: são o mesmo conjunto de notícias, contado da mesma maneira.

Contar pelo que cada recolha lê seria contar de menos — um feed só expõe os seus últimos
artigos, e o valor que ficasse seria o da última recolha do dia, não o que o dia trouxe.
Reconstruindo do arquivo, o dia anterior também é corrigido com o que foi publicado
depois da última recolha.

São agregados, não notícias. Cerca de **2 KB por dia**, menos de 1 MB por ano. Chega
para responder a perguntas de tendência: que áreas cresceram, que assuntos ganharam
peso, como se distribuiu a atenção da comunicação social ao longo de um semestre.

### O que fica e o que passa

| Ficheiro | Guarda | Por quanto tempo |
|---|---|---|
| `arquivo.json` | Notícias marcadas por área | 7 dias, sempre a deslizar |
| `corpus.json` | Comunicação social em bruto, marcada ou não | 7 dias, sempre a deslizar |
| `historico.json` | Contagens por dia e por área | **Para sempre** |
| `meses/AAAA-MM.jsonl.gz` | Notícias marcadas, com título e resumo | **Para sempre** |

Para analisar o passado, o que conta são as duas últimas linhas. O `meses/` guarda
todas as notícias de cada dia, uma a uma; o `historico.json` guarda as contagens. Os
dois primeiros são de trabalho e não têm memória.

O que **não** fica é a comunicação social não marcada: o `corpus.json` só existe para a pesquisa
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
