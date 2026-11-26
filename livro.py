#!/usr/bin/env python3
"""Gera os fascículos impressos (PDF A4) da Tabela Periódica das Notícias.

Cada fascículo traz as notícias ainda não impressas, a próxima lição de cada
trilha de idioma (curso/<trilha>-NN.html), o quiz e o gabarito. A numeração
de páginas continua de onde o fascículo anterior parou (livro/estado.json).

Uso:
  python3 livro.py gerar [--data AAAA-MM-DD]   gera e registra o próximo fascículo
  python3 livro.py rascunho                    gera livro/rascunho.pdf sem registrar nada
  python3 livro.py status                      mostra o que já foi impresso
  python3 livro.py desfazer                    apaga o último fascículo registrado
"""
import argparse
import datetime as dt
import html
import json
import pathlib
import re
import shutil
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
NIVEL = {"a1": "Iniciante (A1)", "b1": "Intermediário (B1)", "c1": "Avançado (C1)"}
IDIOMA = {"en": "Inglês", "de": "Alemão"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
FONTS = ("https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=IBM+Plex+Mono:wght@400;500"
         "&family=IBM+Plex+Sans:wght@400;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap")
e = html.escape


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


def anexar_imagem(it):
    side = IMG / f"{it['id']}.json"
    if side.exists():
        meta = json.loads(side.read_text(encoding="utf-8"))
        if (ROOT / meta["arquivo"]).exists():
            it["imagem"] = meta


def selecionar(d, estado):
    impressos = {i for f in estado["fasciculos"] for i in f["itens"]}
    perg_impressas = {q for f in estado["fasciculos"] for q in f.get("quiz", [])}
    ordem = [c["id"] for c in d["categorias"]]
    itens = [it for it in d["itens"] if it["id"] not in impressos and it["categoria"] in ordem]
    itens.sort(key=lambda it: (ordem.index(it["categoria"]), -(it.get("relevancia") or 0), it["data"]))
    for it in itens:
        anexar_imagem(it)
    ultima = {t: 0 for t in TRILHAS}
    for f in estado["fasciculos"]:
        for t, n in f.get("licoes", {}).items():
            ultima[t] = max(ultima.get(t, 0), n)
    licoes = []
    for t in TRILHAS:
        arq = CURSO / f"{t}-{ultima[t] + 1:02d}.html"
        if arq.exists():
            licoes.append((t, ultima[t] + 1, arq.read_text(encoding="utf-8")))
    ids_ok = impressos | {it["id"] for it in itens}
    quiz = [q for q in d.get("quiz", []) if q["pergunta"] not in perg_impressas and q.get("id") in ids_ok]
    return itens, licoes, quiz, ultima


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


def preparar_licao(t, n, raw):
    gab = re.search(r'<section class="gabarito">(.*?)</section>', raw, re.S)
    corpo = re.sub(r'<section class="gabarito">.*?</section>', "", raw, flags=re.S)
    corpo = re.sub(r'<div class="linhas" data-n="(\d+)"></div>',
                   lambda m: '<div class="linhas">' + '<div class="ln"></div>' * int(m.group(1)) + "</div>", corpo)
    lang, nivel = t.split("-")
    tile = f'<div class="el" data-cat="{lang}"><small>{nivel.upper()}</small><b>{lang.capitalize()}</b></div>'
    corpo = corpo.replace('<header class="l-head">', f'<header class="l-head">{tile}', 1)
    corpo = corpo.replace('<article class="licao"', f'<article data-cat="{lang}" class="licao sec"', 1)
    corpo = corpo.replace("</header>", f'<span class="mk">@@l-{t}@@</span></header>', 1)
    titulo = f"{IDIOMA[lang]} {nivel.upper()} · Lição {n}"
    m = re.search(r"<h2>(.*?)</h2>", raw, re.S)
    nome = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
    return corpo, (titulo, gab.group(1) if gab else ""), nome


def montar_html(d, n, inicio, data_iso, itens, licoes, quiz, ultima, paginas_toc=None):
    cats = {c["id"]: c for c in d["categorias"]}
    ordem = [c["id"] for c in d["categorias"]]
    porcat = {c: [it for it in itens if it["categoria"] == c] for c in ordem}
    prog = programas()
    pg = paginas_toc or {}

    def p(mid):
        v = pg.get(mid)
        return "000" if v is None else str(v)

    toc = []
    for c in ordem:
        if porcat[c]:
            toc.append((f"n-{c}", f"Notícias · {cats[c]['nome']} ({len(porcat[c])})", c))
    if quiz:
        toc.append(("quiz", f"Quiz ({len(quiz)} perguntas)", None))
    lic_html, gabs, nomes = [], [], {}
    for t, num, raw in licoes:
        corpo, gab, nome = preparar_licao(t, num, raw)
        lic_html.append(corpo)
        gabs.append(gab)
        lang, nivel = t.split("-")
        toc.append((f"l-{t}", f"{IDIOMA[lang]} {nivel.upper()} · Lição {num}: {nome}", lang))
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
        f'<li{f" data-cat={chr(34)}{cat}{chr(34)}" if cat else ""}><span class="sw"></span><span>{e(txt)}</span><span class="d"></span><span class="p">{p(mid)}</span></li>'
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
<li>Notícias primeiro, depois o quiz e as lições de inglês e alemão. As respostas ficam no gabarito, no fim.</li>
<li>Pode escrever à vontade nas linhas dos exercícios. A pronúncia vem escrita do jeito que se fala em português.</li>
<li>O número no canto de cada bloco da tabela é quantas notícias daquela família vieram neste fascículo.</li></ul></div></div>
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

    if quiz:
        qs = "".join(f'<li><p>{e(q["pergunta"])}</p><ol class="opts" type="a">{"".join(f"<li>{e(o)}</li>" for o in q["opcoes"])}</ol></li>' for q in quiz)
        out.append(f'<section class="quiz sec break"><header class="sec-h"><div class="el"><small>?</small><b>Qz</b></div><div><h2>Quiz: leu mesmo?</h2>'
                   f'<p>Marque uma opção. As respostas estão no gabarito, no fim do fascículo.</p></div><span class="mk">@@quiz@@</span></header><ol class="qs">{qs}</ol></section>')

    out.extend(lic_html)

    letras = "abcdefgh"
    gq = "".join(f"<li>{letras[q['certa']]}) {e(q['opcoes'][q['certa']])}</li>" for q in quiz)
    gl = "".join(f"<h4>{e(t)}</h4>{body}" for t, body in gabs)
    out.append(f'<section class="gab sec"><header class="sec-h"><div class="el"><small>✓</small><b>Gb</b></div><div><h2>Gabarito</h2><p>Confira só depois de tentar.</p></div><span class="mk">@@gab@@</span></header>'
               f'<div class="gab-cols">{"<h4>Quiz</h4><ol>" + gq + "</ol>" if quiz else ""}{gl}</div></section>')

    prox = []
    for t in TRILHAS:
        nxt = ultima[t] + (1 if any(x[0] == t for x in licoes) else 0) + 1
        tit = prog.get(t, {}).get("licoes", [])
        if nxt <= len(tit):
            lang, nivel = t.split("-")
            prox.append(f"<li><b>{IDIOMA[lang]} {nivel.upper()}, lição {nxt}:</b> {e(tit[nxt - 1])}</li>")
    out.append(f'<section class="fim sec"><header class="sec-h"><div class="el"><small>→</small><b>Px</b></div><div><h2>No próximo fascículo</h2><p>Mais notícias desde {data_br(d["periodo"]["fim"], False)} e as próximas lições.</p></div><span class="mk">@@fim@@</span></header>'
               f'<ul class="proximas">{"".join(prox)}</ul><h3 style="font-family:var(--f-display);margin:8mm 0 2mm;letter-spacing:.08em;text-transform:uppercase;font-size:11pt">Anotações</h3>'
               f'<div class="notas">{"<div class=ln></div>" * 18}</div></section>')
    out.append("</body></html>")
    return "".join(out), [m for m, _, _ in toc]


def render(html_path, pdf_path, modo=""):
    args = ["node", str(LIVRO / "render.js"), str(html_path), str(pdf_path)] + ([modo] if modo else [])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("falha ao gerar PDF:\n" + r.stderr[-2000:])
    return json.loads(r.stdout)


def construir(n, inicio, data_iso, destino_base, registrar):
    d = json.loads(DATA.read_text(encoding="utf-8"))
    estado = carregar_estado()
    itens, licoes, quiz, ultima = selecionar(d, estado)
    BUILD.mkdir(parents=True, exist_ok=True)
    hp = BUILD / f"fasciculo-{n:02d}.html"
    tmp = BUILD / "passo1.pdf"
    html1, marcadores = montar_html(d, n, inicio, data_iso, itens, licoes, quiz, ultima)
    hp.write_text(html1, encoding="utf-8")
    r1 = render(hp, tmp)
    pag = {m: inicio + r1["marks"][m] - 1 for m in marcadores if m in r1["marks"]}
    html2, _ = montar_html(d, n, inicio, data_iso, itens, licoes, quiz, ultima, pag)
    hp.write_text(html2, encoding="utf-8")
    cor = destino_base.with_suffix(".pdf")
    pb = destino_base.parent / (destino_base.name + "-pb.pdf")
    r2 = render(hp, cor)
    render(hp, pb, "pb")
    tmp.unlink(missing_ok=True)
    total = r2["pages"]
    fim = inicio + total - 1
    print(f"fascículo {n:02d}: páginas {inicio}–{fim} ({total} folhas de impressão)")
    print(f"  notícias: {len(itens)} | lições: {', '.join(f'{t} nº{k}' for t, k, _ in licoes) or 'nenhuma'} | quiz: {len(quiz)}")
    print(f"  arquivos: {cor.relative_to(ROOT)} (colorido) e {pb.relative_to(ROOT)} (preto e branco)")
    faltando = [t for t in TRILHAS if not any(x[0] == t for x in licoes)]
    if faltando:
        print(f"  aviso: sem lição nova para {', '.join(faltando)} (crie curso/<trilha>-NN.html)")
    if registrar:
        estado["fasciculos"].append({
            "n": n, "data": data_iso, "pag_ini": inicio, "pag_fim": fim,
            "itens": [it["id"] for it in itens], "licoes": {t: k for t, k, _ in licoes},
            "quiz": [q["pergunta"] for q in quiz],
        })
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("gerar"); g.add_argument("--data", default=dt.date.today().isoformat())
    r = sp.add_parser("rascunho"); r.add_argument("--data", default=dt.date.today().isoformat())
    sp.add_parser("status")
    sp.add_parser("desfazer")
    a = ap.parse_args()
    estado = carregar_estado()
    ult = estado["fasciculos"][-1] if estado["fasciculos"] else None
    n = (ult["n"] + 1) if ult else 1
    inicio = (ult["pag_fim"] + 1) if ult else 1
    if a.cmd == "gerar":
        construir(n, inicio, a.data, LIVRO / f"fasciculo-{n:02d}", True)
    elif a.cmd == "rascunho":
        construir(n, inicio, a.data, LIVRO / "rascunho", False)
    elif a.cmd == "status":
        if not estado["fasciculos"]:
            print("nenhum fascículo registrado ainda")
        for f in estado["fasciculos"]:
            print(f"fascículo {f['n']:02d} ({f['data']}): páginas {f['pag_ini']}–{f['pag_fim']}, {len(f['itens'])} notícias, lições {f['licoes']}")
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
