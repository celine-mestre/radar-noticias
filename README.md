# Radar de Notícias por Área Governativa

Painel de monitorização de comunicação social organizado pelas 16 áreas governativas
do XXV Governo Constitucional.

**Secretaria-Geral do Governo** · Direção de Serviços de Suporte à Decisão ·
Unidade de Pesquisa e Estatísticas

👉 **[Abrir o painel](https://celine-mestre.github.io/radar-noticias/)**

---

## O que faz

- Uma consulta por área governativa, construída a partir de expressões inequívocas
  — *alterações climáticas* e não *clima*, *preço da energia* e não *energia*.
- Seleção de várias palavras-chave em simultâneo, e pesquisa por termo livre.
- Filtros por agrupamento temático, janela temporal, origem das fontes (nacionais,
  internacionais ou todas) e exclusão de redes sociais.
- Leitura das notícias por ordem cronológica, agrupadas por dia.
- Síntese visual: distribuição por publicação, assuntos recorrentes, cobertura de
  cada palavra-chave, distribuição por dia e evolução da área ao longo do tempo.
- Exportação para Excel, com folha de notícias, folha de especificações da consulta
  e folha de evolução.
- Manual de utilização embutido no próprio painel.

---

## Ficheiros do repositório

| Ficheiro | Função |
|---|---|
| `index.html` | O painel. Ficheiro autónomo, sem dependências externas além do tipo de letra. |
| `extrair_noticias.py` | A recolha das 16 áreas. Produz o Excel do dia e os três ficheiros de dados. |
| `.github/workflows/radar-noticias.yml` | Tarefa agendada que corre a recolha nos servidores do GitHub. |
| `noticias.json` | **Retrato do dia.** As notícias das últimas 24 horas de cada área. É o que o painel lê na consulta predefinida — resposta imediata. |
| `arquivo.json` | **Arquivo de sete dias.** Acumula as recolhas diárias, sem repetições. Permite pesquisar por palavra-chave e usar janelas até uma semana sem depender de serviços externos. |
| `historico.json` | **Série diária.** Uma linha por dia e por área, com o número de notícias, de notícias novas e de publicações distintas. Alimenta o bloco *Evolução* e a folha homónima do Excel. |

Os três ficheiros de dados são gerados e atualizados pela recolha agendada. Não
devem ser editados à mão.

---

## Como funciona

O painel não guarda notícias. O navegador impede-o de ler diretamente respostas de
outro domínio, pelo que não pode interrogar o Google Notícias por si próprio. Daí a
arquitetura em duas peças:

1. **Recolha agendada.** Corre nos servidores do GitHub, de segunda a sexta de
   manhã, com janela de 24 horas. Grava o retrato do dia, atualiza o arquivo de
   sete dias e acrescenta o dia à série histórica.
2. **Painel publicado.** Alojado no GitHub Pages, ao lado desses ficheiros. Como os
   lê do mesmo endereço, nenhuma rede o bloqueia.

Ao carregar em *Recolher notícias*, o painel procura por esta ordem:

| Onde procura | Quando | Velocidade |
|---|---|---|
| `noticias.json` | Consulta predefinida da área, janela de 24 horas | Imediato |
| `arquivo.json` | Pesquisas por palavra-chave e janelas até sete dias | Imediato |
| Serviço de pesquisa | Só o que o arquivo não cobre | Lento, e pode falhar |

O serviço é consultado através de intermediários públicos, porque o acesso direto é
bloqueado pelo navegador. São gratuitos e partilhados, logo instáveis: falhando, o
painel apresenta o que tem em arquivo e assinala-o.

O ficheiro Excel é gerado no computador de quem usa o painel, sem passar por
servidor nenhum.

---

## Instalação

1. Colocar `index.html`, `extrair_noticias.py` e `README.md` na raiz do repositório,
   e `radar-noticias.yml` em `.github/workflows/`.
2. Em **Settings › Pages**, escolher *Deploy from a branch*, ramo `main`, pasta `/ (root)`.
3. Em **Settings › Actions › General › Workflow permissions**, escolher
   *Read and write permissions* — é o que permite ao fluxo gravar os ficheiros de dados.
4. Em **Actions**, correr *Radar de Noticias* uma primeira vez.

O painel fica em `https://<utilizador>.github.io/<repositório>/`.

### Usar o ficheiro guardado no computador

Abrir o `index.html` num editor de texto e preencher, no início do código:

```js
enderecoDados: "https://<utilizador>.github.io/<repositório>/",
```

Passa a ir buscar os ficheiros de dados ao repositório publicado.

---

## Recolha manual

Em **Actions › Radar de Noticias › Run workflow**. O Excel fica em *Artifacts*, na
página da execução, durante 30 dias.

Pela linha de comandos, com Python e `openpyxl`:

```bash
python extrair_noticias.py --periodo 24h
python extrair_noticias.py --periodo 30d --area saude --saida saude_julho.xlsx
python extrair_noticias.py --periodo 24h --json noticias.json \
    --arquivo arquivo.json --historico historico.json
```

---

## Limites conhecidos

Todos do serviço de origem, e todos documentados no manual do painel.

- **Teto de 100 artigos por consulta**, sem paginação. O período não altera quantas
  notícias vêm — altera quais: janelas curtas trazem o que é recente, janelas longas
  trazem as mesmas 100 espalhadas por mais tempo.
- **Contagens não comparáveis entre áreas.** Uma área muito noticiada é truncada no
  teto; uma área discreta não é. A comparação de uma área consigo própria ao longo
  do tempo é legítima, porque o método é constante.
- **Ordenação por relevância**, e o operador de tempo atua sobre a data de
  indexação. O painel corrige isto: ordena pela data de publicação e descarta o que
  cai fora da janela pedida.
- **Origem e redes sociais.** No painel, a classificação é feita pelo domínio de
  cada notícia, com exatidão. Na janela do Google seguem como exclusões de domínio,
  que o serviço honra para publicações concretas mas não para domínios de topo.
- **Sem resumos.** O serviço devolve título e fonte, não texto do artigo.
- **Ligações.** São reencaminhamentos do Google, convertidos no endereço do jornal
  sempre que a codificação o permite; a recolha agendada resolve mais casos, por
  trabalhar do lado do servidor.

---

## Segunda fase

A versão assente no corpus curado do Inoreader, com lista de fontes conhecida,
ordenação cronológica e sem truncatura — condição para que as contagens passem a ser
comparáveis entre áreas. A especificação dos feeds está no ficheiro
`inoreader_feeds_areas_governativas.xlsx`, fora deste repositório.

---

## Fonte e responsabilidade

Notícias do Google Notícias, edição portuguesa (`hl=pt-PT`, `gl=PT`, `ceid=PT:pt-150`).
O painel é um instrumento de acesso e triagem: a leitura, a verificação e a
responsabilidade editorial são de quem o usa.
