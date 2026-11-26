# Tabela Periódica das Notícias

Retrospectiva de notícias (desde 28/10/2026) para o meu irmão, organizada como uma tabela periódica:
cada tema é uma "família" com um elemento real.

| Família    | Elemento | Por quê                                         |
|------------|----------|-------------------------------------------------|
| Química    | Cm (96)  | Cúrio, homenagem a Marie e Pierre Curie         |
| Espaço     | Es (99)  | Einstênio                                       |
| Games      | Ga (31)  | Gálio, derrete na mão                           |
| Tecnologia | Tc (43)  | Tecnécio, primeiro elemento artificial          |
| Mistérios  | Xe (54)  | Xenônio, do grego *xénos* = "estranho"          |
| Rock       | Rn (86)  | Radônio, o gás que sai da rocha                 |
| Brasil     | Br (35)  | Bromo                                           |
| Mundo      | Mo (42)  | Molibdênio, Z = 42                              |

## Estrutura

```
data/noticias.json   todas as notícias, agenda e textos (fonte única de verdade)
src/template.html    layout, estilo e lógica da página
build.py             valida o JSON, junta as imagens e gera as páginas
merge.py             mescla novas pesquisas (JSON com "itens"/"agenda") no noticias.json
img.py               busca e baixa imagens de licença livre (Wikimedia Commons, NASA)
img/                 imagens (<id>.webp) + crédito/licença (<id>.json)
index.html           site completo (gerado) - abre direto no navegador
dist/artifact.html   versão para publicar no claude.ai (gerada)
```

## Como atualizar

1. Edite `data/noticias.json`:
   - adicione itens em `itens` (campos: `id`, `categoria`, `data`, `simbolo`, `titulo`, `resumo`, `fontes`;
     opcionais: `nome`, `angulo_quimico`, `relevancia` 1-5, `corpo` (espaço), `teoria`/`fatos` (mistérios), `ouvir` (rock),
     `adicionado_em` (AAAA-MM-DD; itens com a mesma data de `atualizado_em` ganham a marca "novo"));
   - ajuste `periodo.fim` e `atualizado_em`;
   - `resumo_ids` define a capa (o 1º é a manchete, os outros 5 vão na lista ao lado);
   - `quiz` traz as perguntas (`pergunta`, `opcoes`, `certa` = índice da correta, `id` da notícia).
2. Imagens (opcional, por notícia): `python3 img.py busca "termo"` ou `python3 img.py nasa-busca "termo"`,
   depois `python3 img.py commons <id> "File:...jpg" --legenda "..."` ou `python3 img.py nasa <id> <nasa_id> --legenda "..."`.
   Sem imagem, o site desenha uma arte automática da família.
3. Rode `python3 build.py` (ele avisa sobre campos faltando, ids repetidos, datas fora do período e agenda vencida).
4. Abra `index.html` ou republique `dist/artifact.html` junto com os arquivos listados em `dist/imagens.json`.

Regras: toda notícia precisa de fonte com link real; toda imagem precisa de licença livre e crédito (o img.py cuida disso).

## Livro impresso (fascículos)

Como ele está sem celular, o conteúdo também sai em **fascículos impressos em A4**, com numeração de
páginas contínua: cada fascículo começa na página seguinte à do anterior, é só encaixar na pasta.

Cada fascículo traz as notícias ainda não impressas (duas colunas), o quiz, a próxima lição de cada
trilha de idioma e o gabarito no fim.

```
livro.py                 gera os fascículos
livro/estilo.css         visual de impressão (claro, econômico em tinta)
livro/render.js          HTML -> PDF (Chromium) + página de cada seção para o sumário
livro/estado.json        o que já foi impresso (notícias, lições, quiz, páginas)
livro/fasciculo-NN.pdf   colorido      | livro/fasciculo-NN-pb.pdf  preto e branco
curso/programa-*.json    programa de 12 lições por nível
curso/<trilha>-NN.html   lições (trilhas: en-a1, en-b1, en-c1, de-a1, de-b1, de-c1)
```

Comandos:

- `python3 livro.py rascunho` — gera `livro/rascunho.pdf` para conferir, sem registrar nada.
- `python3 livro.py gerar` — gera e registra o próximo fascículo (antes de cada visita).
- `python3 livro.py status` — lista os fascículos já impressos e as páginas.
- `python3 livro.py desfazer` — remove o último fascículo do registro (para gerar de novo).

Antes de gerar um fascículo novo, crie a próxima lição de cada trilha em `curso/<trilha>-NN.html`
seguindo o formato das lições existentes (vocabulário com pronúncia aproximada, gramática, leitura
baseada em notícias do fascículo, exercícios com linhas e `<section class="gabarito">`).
