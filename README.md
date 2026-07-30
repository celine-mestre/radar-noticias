# Radar de Notícias por Área Governativa

Painel de monitorização de comunicação social organizado pelas 16 áreas governativas
do XXV Governo Constitucional.

**Secretaria-Geral do Governo** · Direção de Serviços de Suporte à Decisão ·
Unidade de Pesquisa e Estatísticas

👉 **[Abrir o painel](https://celine-mestre.github.io/radar-noticias/)**

---

## O que faz

- Uma consulta por área governativa, construída a partir de palavras-chave revistas
  para serem inequívocas — expressões como *alterações climáticas* ou *preço da
  energia*, e não palavras soltas como *clima* ou *energia*.
- Filtros por agrupamento temático, janela temporal entre 24 horas e um ano, e
  restrição a fontes nacionais.
- Pesquisa por palavra-chave isolada ou por termo livre dentro de cada área.
- Exportação para Excel, com uma folha de notícias e outra de especificações da
  consulta.
- Síntese visual da recolha: distribuição por publicação, assuntos recorrentes,
  cobertura das palavras-chave e distribuição por dia.
- Manual de utilização embutido no próprio painel.

---

## Ficheiros do repositório

| Ficheiro | Função |
|---|---|
| `index.html` | O painel. Ficheiro autónomo, sem dependências externas além do tipo de letra. |
| `extrair_noticias.py` | Recolha das 16 áreas. Produz o Excel do dia e o `noticias.json`. |
| `.github/workflows/radar-noticias.yml` | Tarefa agendada que corre a recolha nos servidores do GitHub. |
| `noticias.json` | Gerado pela recolha. É o que o painel lê quando carrega em *Recolher notícias*. |

---

## Como funciona

O painel não guarda notícias: constrói consultas ao Google Notícias, na edição
portuguesa, e abre os resultados no serviço.

Para exportar, precisa de as ler — e o navegador não pode ler diretamente respostas
de outro domínio. Daí a arquitetura em duas peças:

1. **Recolha agendada.** Corre no GitHub, de segunda a sexta às 7h00, e grava o
   `noticias.json` na raiz do repositório.
2. **Painel publicado.** Alojado no GitHub Pages, ao lado desse ficheiro. Como o lê
   do mesmo endereço, nenhuma rede o bloqueia. Se o ficheiro não existir, o painel
   tenta ainda a recolha em direto.

O Excel é gerado no computador de quem usa o painel, sem passar por nenhum servidor.

---

## Instalação

1. Colocar `index.html` e `extrair_noticias.py` na raiz do repositório, e
   `radar-noticias.yml` em `.github/workflows/`.
2. Em **Settings › Pages**, escolher *Deploy from a branch*, ramo `main`, pasta `/ (root)`.
3. Em **Settings › Actions › General › Workflow permissions**, escolher
   *Read and write permissions* — é o que permite ao fluxo gravar o `noticias.json`.
4. Em **Actions**, correr *Radar de Notícias por Área Governativa* uma primeira vez.

O painel fica em `https://<utilizador>.github.io/<repositório>/`.

### Usar o ficheiro guardado no computador

Abrir o `index.html` num editor de texto e preencher, no início do código:

```js
enderecoDados: "https://<utilizador>.github.io/<repositório>/",
```

Passa a ir buscar as notícias ao repositório publicado.

---

## Recolha manual

Em **Actions › Radar de Notícias por Área Governativa › Run workflow** é possível
escolher outra janela temporal. O Excel fica em *Artifacts*, na página da execução,
durante 30 dias.

Pela linha de comandos, com Python e `openpyxl`:

```bash
python extrair_noticias.py --periodo 24h
python extrair_noticias.py --periodo 30d --area saude --saida saude_julho.xlsx
python extrair_noticias.py --periodo 7d --json noticias.json
```

---

## Limites conhecidos

Todos do serviço de origem, e todos documentados na nota metodológica do painel.

- **Teto de 100 artigos por consulta**, sem paginação. Qualquer que seja o período
  escolhido, uma consulta não devolve mais do que isso: alargar a janela distribui
  as mesmas 100 notícias por mais tempo.
- **Contagens não comparáveis entre áreas.** Uma área muito noticiada é truncada no
  teto; uma área discreta não é.
- **Ordenação por relevância**, não por data. O operador de tempo atua sobre a data
  de indexação, que pode não coincidir com a da publicação.
- **Sem resumos.** O serviço devolve título e fonte, não texto do artigo.
- **Ligações.** São reencaminhamentos do Google. São convertidas no endereço do
  jornal sempre que a codificação o permite; a recolha agendada resolve mais casos,
  por seguir o reencaminhamento do lado do servidor.

---

## Síntese redigida por modelo de linguagem

O painel está preparado para gerar uma síntese redigida a partir dos títulos
recolhidos, através do **AMALIA**, o modelo de linguagem para português europeu
desenvolvido sob coordenação da ARTE e disponibilizado em código aberto.

Falta apenas um ponto de acesso. Existindo, preenche-se no início do código:

```js
amalia: {
  endereco: "https://<ponto-de-acesso>/v1/chat/completions",
  modelo:   "amalia-llm/AMALIA-9B-0626-DPO",
  chave:    ""
},
```

A interface esperada é a que a documentação do AMALIA indica para servir o modelo.
Sem configuração, o bloco não aparece e a síntese calculada no painel funciona na
mesma.

---

## Segunda fase

A versão assente no corpus curado do Inoreader, com lista de fontes conhecida,
ordenação cronológica e sem truncatura — condição para que as contagens passem a ser
comparáveis entre áreas. A especificação dos feeds e das regras está no ficheiro
`inoreader_criacao_feeds_radar.xlsx`, fora deste repositório.

---

## Fonte e responsabilidade

Notícias do Google Notícias, edição portuguesa (`hl=pt-PT`, `gl=PT`, `ceid=PT:pt-150`).
O painel é um instrumento de acesso e triagem: a leitura, a verificação e a
responsabilidade editorial são de quem o usa.
