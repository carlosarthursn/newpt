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
build.py             valida o JSON e gera as páginas
index.html           site completo (gerado) - abre direto no navegador
dist/artifact.html   versão para publicar no claude.ai (gerada)
```

## Como atualizar

1. Edite `data/noticias.json`:
   - adicione itens em `itens` (campos: `id`, `categoria`, `data`, `simbolo`, `titulo`, `resumo`, `fontes`;
     opcionais: `nome`, `angulo_quimico`, `relevancia` 1-5, `corpo` (espaço), `teoria`/`fatos` (mistérios), `ouvir` (rock));
   - ajuste `periodo.fim` e `atualizado_em`;
   - `resumo_ids` define os 6 itens do "Se der pra ler só 6 coisas".
2. Rode `python3 build.py` (ele avisa sobre campos faltando, ids repetidos, datas fora do período e agenda vencida).
3. Abra `index.html` ou republique `dist/artifact.html`.

Regra: toda notícia precisa de fonte com link real.
