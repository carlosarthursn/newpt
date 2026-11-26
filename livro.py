#!/usr/bin/env python3
"""Gera os fascículos impressos (PDF A4) da Tabela Periódica das Notícias.

Um fascículo por visita (cerca de um mês). Cada um traz:
  - notícias ainda não impressas (o 1º leva todas; os seguintes, as melhores de cada família);
  - um "Plano do mês" com as lições divididas em 4 semanas;
  - o quiz;
  - as lições do mês de cada trilha (ritmo: Iniciante 8, Intermediário 4, Avançado 1 por idioma);
  - fichas de vocabulário para dobrar e se testar;
  - gabarito e páginas de anotações.
A numeração de páginas continua de onde o fascículo anterior parou (livro/estado.json).

Uso:
  python3 livro.py gerar [--data AAAA-MM-DD] [--max-por-familia N]   gera e registra o próximo fascículo
  python3 livro.py rascunho [...]                                    gera livro/rascunho.pdf sem registrar
  python3 livro.py faltando                                          lições que faltam para o próximo fascículo
  python3 livro.py status                                            o que já foi impresso
  python3 livro.py desfazer                                          apaga o último fascículo registrado
"""
import argparse
import datetime as dt
import html
import json
import math
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "noticias.json"
IMG = ROOT / "img"
CURSO = ROOT / "curso"
LIVRO = ROOT / "livro"
BUILD = LIVRO / "build"
ESTADO = LIVRO / "estado.json"
TRILHAS = ["en-a1", "en-b1", "en-c1", "de-a1", "de-b1", "de-c1"]
RITMO = {"a1": 8, "b1": 4, "c1": 1}          # lições por fascículo (por idioma)
MAX_FAMILIA = 10                              # notícias por família a partir do 2º fascículo
NIVEL = {"a1": "Iniciante (A1→A2)", "b1": "Intermediário (B1)", "c1": "Avançado (C1)"}
NIVEL_CURTO = {"a1": "Iniciante", "b1": "Intermediário", "c1": "Avançado"}
IDIOMA = {"en": "Inglês", "de": "Alemão"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
FONTS = ("https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=IBM+Plex+Mono:wght@400;500"
         "&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap")
e = html.escape
H3 = 'style="font-family:var(--f-display);margin:0 0 2mm;letter-spacing:.08em;text-transform:uppercase;font-size:11pt"'


def carregar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"fasciculos": []}


def data_br(iso, com_dia=True):
    d = dt.date.fromisoformat(iso)
    s = f"{d.day} {MESES[d.month - 1]}"
    return f"{DIAS[d.weekday()]} {s}" if com_dia else s


def programas():
    p = {}
    for f in sorted(CURSO.glob("programa-*.json")):
        p.update(json.loads(f.read_text(encoding="utf-8")))
    return p


def sem_rotulo(t):
    return re.sub(r"^\s*Li[çc][ãa]o\s*\d+\s*[:.\-–—]\s*", "", t)


def anexar_imagem(it):
    side = IMG / f"{it['id']}.json"
    if side.exists():
        meta = json.loads(side.read_text(encoding="utf-8"))
        if (ROOT / meta["arquivo"]).exists():
            it["imagem"] = meta


def ultimas_licoes(estado):
    ultima = {t: 0 for t in TRILHAS}
    for f in estado["fasciculos"]:
        for t, n in f.get("licoes", {}).items():
            ultima[t] = max(ultima.get(t, 0), n)
    return ultima


def licoes_do_proximo(estado):
    """(trilha, número, arquivo) esperados no próximo fascículo, existam ou não."""
    ultima = ultimas_licoes(estado)
    out = []
    for t in TRILHAS:
        for k in range(ultima[t] + 1, ultima[t] + RITMO[t.split("-")[1]] + 1):
            out.append((t, k, CURSO / f"{t}-{k:02d}.html"))
    return out


def selecionar(d, estado, max_familia):
    vistos = {i for f in estado["fasciculos"] for i in f.get("considerados", f["itens"])}
    impressos = {i for f in estado["fasciculos"] for i in f["itens"]}
    perg_impressas = {q for f in estado["fasciculos"] for q in f.get("quiz", [])}
    ordem = [c["id"] for c in d["categorias"]]
    cand = [it for it in d["itens"] if it["id"] not in vistos and it["categoria"] in ordem]
    itens = []
    for c in ordem:
        doc = [it for it in cand if it["categoria"] == c]
        doc.sort(key=lambda it: it["data"], reverse=True)
        doc.sort(key=lambda it: it.get("relevancia") or 0, reverse=True)
        itens.extend(doc[:max_familia] if max_familia else doc)
    for it in itens:
        anexar_imagem(it)
    ultima = ultimas_licoes(estado)
    licoes = []
    for t in TRILHAS:
        for k in range(ultima[t] + 1, ultima[t] + RITMO[t.split("-")[1]] + 1):
            arq = CURSO / f"{t}-{k:02d}.html"
            if not arq.exists():
                break
            licoes.append((t, k, arq.read_text(encoding="utf-8")))
    ids_ok = impressos | {it["id"] for it in itens}
    quiz = [q for q in d.get("quiz", []) if q["pergunta"] not in perg_impressas and q.get("id") in ids_ok]
    return itens, [it["id"] for it in cand], licoes, quiz


# ---------- HTML ----------

def miniatura(arquivo, item_id):
    """JPEG pequeno para impressão (o PDF fica leve; 28 mm a 300 dpi ≈ 330 px)."""
    from PIL import Image
    dest = BUILD / "img" / f"{item_id}.jpg"
    src = ROOT / arquivo
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        im.thumbnail((420, 420))
        im.save(dest, "JPEG", quality=74, optimize=True, progressive=True)
        im.convert("L").save(dest.with_name(f"{item_id}-pb.jpg"), "JPEG", quality=74, optimize=True, progressive=True)
    return f"img/{item_id}.jpg"


def item_html(it, cat):
    meta = [f"<b>{e(cat['nome'])}</b>", data_br(it["data"])]
    if it.get("corpo"):
        meta.append(e(it["corpo"]))
    partes = [f'<article class="it" data-cat="{it["categoria"]}">']
    im = it.get("imagem")
    if im:
        cred = ", ".join(x for x in [im.get("credito"), im.get("licenca")] if x)
        partes.append(f'<div class="it-img"><img src="{e(miniatura(im["arquivo"], it["id"]))}" alt=""><div class="cr">{e(im.get("legenda") or "")}{". " if im.get("legenda") else ""}Imagem: {e(cred)}</div></div>')
    partes.append(f'<p class="it-meta">{" · ".join(meta)}</p>')
    partes.append(f'<h3><span class="sym">{e(it["simbolo"])}</span>{e(it["titulo"])}</h3>')
    if it.get("resumo"):
        partes.append(f"<p>{e(it['resumo'])}</p>")
    if it.get("teoria") or it.get("fatos"):
        partes.append('<div class="tf">' + (f"<div><b>A teoria</b>{e(it['teoria'])}</div>" if it.get("teoria") else "")
                      + (f"<div><b>O que se sabe</b>{e(it['fatos'])}</div>" if it.get("fatos") else "") + "</div>")
    if it.get("angulo_quimico"):
        partes.append(f'<div class="chem"><b>Ângulo químico</b>{e(it["angulo_quimico"])}</div>')
    if it.get("ouvir"):
        partes.append(f'<p class="listen"><b>Pra ouvir</b>{e(it["ouvir"])}</p>')
    fontes = ", ".join(e(f["nome"]) for f in it.get("fontes", []))
    partes.append(f'<p class="src">Fonte: {fontes}</p></article>')
    return "".join(partes)


def texto(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def preparar_licao(t, n, raw):
    gab = re.search(r'<section class="gabarito">(.*?)</section>', raw, re.S)
    corpo = re.sub(r'<section class="gabarito">.*?</section>', "", raw, flags=re.S)
    corpo = re.sub(r'<div class="linhas" data-n="(\d+)"></div>',
                   lambda m: '<div class="linhas">' + '<div class="ln"></div>' * int(m.group(1)) + "</div>", corpo)
    lang, nivel = t.split("-")
    tile = f'<div class="el" data-cat="{lang}"><small>{nivel.upper()} · {n}</small><b>{lang.capitalize()}</b></div>'
    corpo = corpo.replace('<header class="l-head">', f'<header class="l-head">{tile}', 1)
    corpo = corpo.replace('<article class="licao"', f'<article data-cat="{lang}" class="licao sec"', 1)
    corpo = corpo.replace("</header>", f'<span class="mk">@@l-{t}-{n}@@</span></header>', 1)
    corpo = re.sub(r'(<p class="l-nivel">)(.*?)(</p>)', lambda m: f"{m.group(1)}{IDIOMA[lang]} · {NIVEL[nivel]} · Lição {n}{m.group(3)}", corpo, count=1)
    m = re.search(r"<h2>(.*?)</h2>", raw, re.S)
    nome = texto(m.group(1)) if m else ""
    vocab = []
    v = re.search(r'<section class="l-vocab">(.*?)</section>', raw, re.S)
    if v:
        for tr in re.findall(r"<tr>(.*?)</tr>", re.sub(r"<thead>.*?</thead>", "", v.group(1), flags=re.S), re.S):
            tds = [texto(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) >= 3:
                vocab.append((tds[0], tds[1], tds[2]))
    return corpo, (f"{IDIOMA[lang]} {NIVEL_CURTO[nivel]} · Lição {n}", gab.group(1) if gab else ""), nome, vocab


def faixas(nums):
    return f"lição {nums[0]}" if len(nums) == 1 else f"lições {nums[0]} a {nums[-1]}"


def montar_html(d, n, inicio, data_iso, itens, licoes, quiz, pg=None, extra_notas=False):
    cats = {c["id"]: c for c in d["categorias"]}
    ordem = [c["id"] for c in d["categorias"]]
    porcat = {c: [it for it in itens if it["categoria"] == c] for c in ordem}
    prog = programas()
    pg = pg or {}

    def p(mid):
        v = pg.get(mid)
        return "000" if v is None else str(v)

    prep = [(t, k, *preparar_licao(t, k, raw)) for t, k, raw in licoes]
    por_trilha = {t: [x for x in prep if x[0] == t] for t in TRILHAS}

    toc = []
    for c in ordem:
        if porcat[c]:
            toc.append((f"n-{c}", f"Notícias · {cats[c]['nome']} ({len(porcat[c])})", c))
    if prep:
        toc.append(("plano", "Plano do mês: o que estudar em cada semana", None))
    if quiz:
        toc.append(("quiz", f"Quiz ({len(quiz)} perguntas)", None))
    for t in TRILHAS:
        if por_trilha[t]:
            lang, nivel = t.split("-")
            nums = [x[1] for x in por_trilha[t]]
            toc.append((f"l-{t}-{nums[0]}", f"{IDIOMA[lang]} {NIVEL_CURTO[nivel]} · {faixas(nums)}", lang))
    if prep:
        toc.append(("fichas", "Fichas de vocabulário (dobre e teste)", None))
    toc.append(("gab", "Gabarito", None))
    toc.append(("fim", "Próximo fascículo e anotações", None))

    if itens:
        datas = sorted(it["data"] for it in itens)
        periodo = f"Notícias de {data_br(datas[0], False)} a {data_br(datas[-1], False)} de {datas[-1][:4]}"
    else:
        periodo = "Sem notícias novas neste fascículo"
    hoje = dt.date.fromisoformat(data_iso)
    tiles = "".join(
        f'<div class="tile" data-cat="{c["id"]}"><span class="z"><span>{c["z"]}</span><span>{len(porcat[c["id"]])}</span></span>'
        f'<span class="s">{e(c["simbolo"])}</span><span class="nm">{e(c["nome"])}</span></div>' for c in d["categorias"])
    toc_li = "".join(
        f'<li{" data-cat=" + chr(34) + cat + chr(34) if cat else ""}><span class="sw"></span><span>{e(txt)}</span><span class="d"></span><span class="p">{p(mid)}</span></li>'
        for mid, txt, cat in toc)

    out = [f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Fascículo {n:02d}</title>',
           f'<link rel="stylesheet" href="{FONTS}"><link rel="stylesheet" href="../estilo.css"><style>',
           "@page { size: A4; margin: 15mm 14mm 16mm; ",
           '@top-left { content: "Tabela Periódica das Notícias"; font: 7.5pt "IBM Plex Mono", monospace; color: #5A6372; } ',
           f'@top-right {{ content: "Fascículo {n:02d} · {hoje.day:02d}/{hoje.month:02d}/{hoje.year}"; font: 7.5pt "IBM Plex Mono", monospace; color: #5A6372; }} ',
           '@bottom-center { content: counter(page); font: 600 9pt "Chakra Petch", sans-serif; } } ',
           f"@page :first {{ counter-increment: page {inicio}; @top-left {{ content: none; }} @top-right {{ content: none; }} }}",
           "</style></head><body>"]

    out.append(f'''<section class="capa">
<div class="capa-top"><div><h1>Tabela Periódica das Notícias</h1><p class="sub">{e(periodo)} · impresso em {hoje.day:02d}/{hoje.month:02d}/{hoje.year}</p></div>
<div class="fasc"><span class="t"><span>FASC.</span><span>p. {inicio}+</span></span><span class="n">{n:02d}</span><span class="b">Fascículo</span></div></div>
<div class="tiles">{tiles}</div>
<div class="info"><div class="box"><p class="msg">{e(d.get("mensagem", ""))}</p></div>
<div class="box"><h3>Como usar</h3><ul><li>As páginas continuam a numeração do fascículo anterior: é só encaixar na pasta, em ordem.</li>
<li>Este fascículo foi feito para durar até a próxima visita. Comece pelo Plano do mês.</li>
<li>Pode escrever à vontade nas linhas dos exercícios. A pronúncia vem escrita do jeito que se fala em português. As respostas ficam no gabarito.</li>
<li>O número no canto de cada bloco da tabela é quantas notícias daquela família vieram aqui.</li></ul></div></div>
<div class="toc box"><h3>Neste fascículo</h3><ol>{toc_li}</ol></div>
</section>''')

    primeira = True
    for c in ordem:
        if not porcat[c]:
            continue
        cat = cats[c]
        out.append(f'<section class="fam sec{" break" if primeira else ""}" data-cat="{c}"><header class="sec-h"><div class="el"><small>{cat["z"]}</small><b>{e(cat["simbolo"])}</b></div>'
                   f'<div><h2>{e(cat["nome"])}</h2><p>{e(cat["descricao"])} {e(cat["elemento"])}</p></div><span class="mk">@@n-{c}@@</span></header>'
                   f'<div class="cols">{"".join(item_html(it, cat) for it in porcat[c])}</div></section>')
        primeira = False

    if prep:
        semanas = [[] for _ in range(4)]
        for t in TRILHAS:
            xs = por_trilha[t]
            if not xs:
                continue
            tam = math.ceil(len(xs) / 4)
            for i, x in enumerate(xs):
                w = min(i // tam, 3) if len(xs) >= 4 else (3 if t.endswith("c1") else min(i, 3))
                semanas[w].append(x)
        linhas = []
        for w, xs in enumerate(semanas, 1):
            cel = {"en": [], "de": []}
            for t, k, corpo, gab, nome, vocab in xs:
                lang, nivel = t.split("-")
                cel[lang].append(f'<li><span class="chk"></span><b>{NIVEL_CURTO[nivel]} {k}</b> {e(nome)} <span class="pg">p. {p(f"l-{t}-{k}")}</span></li>')
            linhas.append(f'<tr><th>Semana {w}</th><td><ul>{"".join(cel["en"])}</ul></td><td><ul>{"".join(cel["de"])}</ul></td></tr>')
        out.append(f'''<section class="plano sec break"><header class="sec-h"><div class="el"><small>4 sem.</small><b>Pl</b></div><div><h2>Plano do mês</h2>
<p>As lições deste fascículo divididas em quatro semanas. Marque o quadradinho quando terminar.</p></div><span class="mk">@@plano@@</span></header>
<table class="plano-t"><thead><tr><th></th><th>Inglês</th><th>Alemão</th></tr></thead><tbody>{"".join(linhas)}</tbody></table>
<div class="info" style="margin-top:6mm"><div class="box"><h3>Rotina sugerida</h3><ul>
<li><b>Dia 1:</b> vocabulário e gramática da lição nova. Leia em voz alta, seguindo a pronúncia escrita.</li>
<li><b>Dia 2:</b> leitura e exercícios. Só depois confira no gabarito.</li>
<li><b>Dia 3:</b> prática extra e fichas de vocabulário (dobre a folha e teste-se).</li>
<li><b>Dia 4:</b> próxima lição. <b>Dia 5:</b> refaça o que errou e repasse as fichas.</li>
<li>Nas revisões, faça tudo sem olhar as lições anteriores; depois confira.</li></ul></div>
<div class="box"><h3>Dicas</h3><ul>
<li>Uns 30 a 40 minutos por idioma, 5 dias por semana, rendem mais do que horas num dia só.</li>
<li>Se travar no intermediário, siga só no iniciante. Ele está aqui pra ser feito no seu ritmo.</li>
<li>Escreva frases sobre você e sobre o que leu nas notícias. É o melhor treino sem áudio.</li>
<li>O avançado vem devagar de propósito: uma lição por mês, pra ir sentindo o nível.</li></ul></div></div>
</section>''')

    if quiz:
        qs = "".join(f'<li><p>{e(q["pergunta"])}</p><ol class="opts" type="a">{"".join(f"<li>{e(o)}</li>" for o in q["opcoes"])}</ol></li>' for q in quiz)
        out.append(f'<section class="quiz sec break"><header class="sec-h"><div class="el"><small>?</small><b>Qz</b></div><div><h2>Quiz: leu mesmo?</h2>'
                   f'<p>Marque uma opção. As respostas estão no gabarito, no fim do fascículo.</p></div><span class="mk">@@quiz@@</span></header><ol class="qs">{qs}</ol></section>')

    out.extend(x[2] for x in prep)

    if prep:
        blocos = []
        for lang in ("en", "de"):
            linhas = []
            for t, k, corpo, gab, nome, vocab in prep:
                if not t.startswith(lang) or not vocab:
                    continue
                nivel = t.split("-")[1]
                linhas.append(f'<tr class="fx-h"><td colspan="3">{NIVEL_CURTO[nivel]} · Lição {k}</td></tr>')
                linhas.extend(f'<tr><td><b>{e(w)}</b><br><span class="pr">{e(pr)}</span></td><td class="dob"></td><td>{e(pt)}</td></tr>' for w, pr, pt in vocab)
            if linhas:
                blocos.append(f'<h3 class="fx-t" data-cat="{lang}">{IDIOMA[lang]}</h3><table class="fichas"><thead><tr><th>{IDIOMA[lang]}</th><th class="dob">✂ dobre aqui</th><th>Português</th></tr></thead><tbody>{"".join(linhas)}</tbody></table>')
        out.append(f'<section class="fichas-sec sec break"><header class="sec-h"><div class="el"><small>voc.</small><b>Fx</b></div><div><h2>Fichas de vocabulário</h2>'
                   f'<p>Todas as palavras das lições deste mês. Dobre a folha na linha pontilhada, olhe só um lado e tente lembrar o outro.</p></div><span class="mk">@@fichas@@</span></header>{"".join(blocos)}</section>')

    letras = "abcdefgh"
    gq = "".join(f"<li>{letras[q['certa']]}) {e(q['opcoes'][q['certa']])}</li>" for q in quiz)
    gl = "".join(f"<h4>{e(x[3][0])}</h4>{x[3][1]}" for x in prep)
    out.append(f'<section class="gab sec"><header class="sec-h"><div class="el"><small>✓</small><b>Gb</b></div><div><h2>Gabarito</h2><p>Confira só depois de tentar.</p></div><span class="mk">@@gab@@</span></header>'
               f'<div class="gab-cols">{"<h4>Quiz</h4><ol>" + gq + "</ol>" if quiz else ""}{gl}</div></section>')

    prox = []
    ult = {t: (por_trilha[t][-1][1] if por_trilha[t] else None) for t in TRILHAS}
    for t in TRILHAS:
        tit = prog.get(t, {}).get("licoes", [])
        base = ult[t] if ult[t] is not None else 0
        k0, k1 = base + 1, min(base + RITMO[t.split("-")[1]], len(tit))
        if k0 <= k1:
            lang, nivel = t.split("-")
            prox.append(f"<li><b>{IDIOMA[lang]} {NIVEL_CURTO[nivel]}, {faixas(list(range(k0, k1 + 1)))}:</b> começa com “{e(sem_rotulo(tit[k0 - 1]))}”</li>")
    out.append(f'<section class="fim sec"><header class="sec-h"><div class="el"><small>→</small><b>Px</b></div><div><h2>No próximo fascículo</h2><p>Mais notícias e as próximas lições, continuando a numeração das páginas.</p></div><span class="mk">@@fim@@</span></header>'
               f'<ul class="proximas">{"".join(prox)}</ul><h3 {H3[:-1]};margin-top:8mm">Anotações</h3>'
               f'<div class="notas">{"<div class=ln></div>" * 16}</div></section>')
    if extra_notas:
        out.append(f'<section class="fim sec"><h3 {H3}>Mais anotações</h3><div class="notas">{"<div class=ln></div>" * 27}</div></section>')
    out.append("</body></html>")
    return "".join(out)


def render(html_path, pdf_path, modo=""):
    args = ["node", str(LIVRO / "render.js"), str(html_path), str(pdf_path)] + ([modo] if modo else [])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("falha ao gerar PDF:\n" + r.stderr[-2000:])
    return json.loads(r.stdout)


def construir(n, inicio, data_iso, destino_base, registrar, max_familia):
    d = json.loads(DATA.read_text(encoding="utf-8"))
    estado = carregar_estado()
    itens, considerados, licoes, quiz = selecionar(d, estado, max_familia)
    BUILD.mkdir(parents=True, exist_ok=True)
    hp = BUILD / f"fasciculo-{n:02d}.html"
    tmp = BUILD / "passo1.pdf"
    hp.write_text(montar_html(d, n, inicio, data_iso, itens, licoes, quiz), encoding="utf-8")
    r1 = render(hp, tmp)
    pag = {m: inicio + i - 1 for m, i in r1["marks"].items()}
    extra = r1["pages"] % 2 == 1  # fecha em número par de páginas (frente e verso)
    hp.write_text(montar_html(d, n, inicio, data_iso, itens, licoes, quiz, pag, extra), encoding="utf-8")
    cor = destino_base.with_suffix(".pdf")
    pb = destino_base.parent / (destino_base.name + "-pb.pdf")
    r2 = render(hp, cor)
    render(hp, pb, "pb")
    tmp.unlink(missing_ok=True)
    total = r2["pages"]
    fim = inicio + total - 1
    resumo_lic = {}
    for t, k, _ in licoes:
        resumo_lic.setdefault(t, []).append(k)
    print(f"fascículo {n:02d}: páginas {inicio}–{fim} ({total} páginas = {total // 2} folhas em frente e verso)")
    print(f"  notícias: {len(itens)} de {len(considerados)} novas | quiz: {len(quiz)}")
    print("  lições: " + (", ".join(f"{t} {faixas(v)}" for t, v in resumo_lic.items()) or "nenhuma"))
    print(f"  arquivos: {cor.relative_to(ROOT)} (colorido) e {pb.relative_to(ROOT)} (preto e branco)")
    falt = [f"{t}-{k:02d}" for t, k, arq in licoes_do_proximo(estado) if not arq.exists()]
    if falt:
        print(f"  aviso: faltam lições para completar o mês: {', '.join(falt)}")
    if registrar:
        estado["fasciculos"].append({
            "n": n, "data": data_iso, "pag_ini": inicio, "pag_fim": fim,
            "itens": [it["id"] for it in itens], "considerados": considerados,
            "licoes": {t: max(v) for t, v in resumo_lic.items()},
            "quiz": [q["pergunta"] for q in quiz],
        })
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("gerar", "rascunho"):
        g = sp.add_parser(nome)
        g.add_argument("--data", default=dt.date.today().isoformat())
        g.add_argument("--max-por-familia", type=int, default=None, help="padrão: todas no 1º fascículo, 10 nos seguintes; 0 = todas")
    sp.add_parser("status")
    sp.add_parser("faltando")
    sp.add_parser("desfazer")
    a = ap.parse_args()
    estado = carregar_estado()
    ult = estado["fasciculos"][-1] if estado["fasciculos"] else None
    n = (ult["n"] + 1) if ult else 1
    inicio = (ult["pag_fim"] + 1) if ult else 1
    if a.cmd in ("gerar", "rascunho"):
        mf = a.max_por_familia if a.max_por_familia is not None else (0 if n == 1 else MAX_FAMILIA)
        destino = LIVRO / (f"fasciculo-{n:02d}" if a.cmd == "gerar" else "rascunho")
        construir(n, inicio, a.data, destino, a.cmd == "gerar", mf)
    elif a.cmd == "faltando":
        falt = [f"curso/{t}-{k:02d}.html" for t, k, arq in licoes_do_proximo(estado) if not arq.exists()]
        print("\n".join(falt) if falt else "todas as lições do próximo fascículo já existem")
    elif a.cmd == "status":
        if not estado["fasciculos"]:
            print("nenhum fascículo registrado ainda")
        for f in estado["fasciculos"]:
            print(f"fascículo {f['n']:02d} ({f['data']}): páginas {f['pag_ini']}–{f['pag_fim']}, {len(f['itens'])} notícias, lições até {f['licoes']}")
    elif a.cmd == "desfazer":
        if not ult:
            sys.exit("nada para desfazer")
        estado["fasciculos"].pop()
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for suf in (".pdf", "-pb.pdf"):
            (LIVRO / f"fasciculo-{ult['n']:02d}{suf}").unlink(missing_ok=True)
        print(f"fascículo {ult['n']:02d} removido do registro")


if __name__ == "__main__":
    main()
