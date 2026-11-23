#!/usr/bin/env python3
"""Gera o site a partir de data/noticias.json + src/template.html.

Saídas:
  index.html          documento completo (abre direto no navegador / GitHub Pages)
  dist/artifact.html  fragmento para publicar como Artifact no claude.ai

Uso: python3 build.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "noticias.json"
TEMPLATE = ROOT / "src" / "template.html"
IMGDIR = ROOT / "img"
CAMPOS = ("id", "categoria", "data", "simbolo", "titulo", "resumo", "fontes")


def validar(d):
    erros, avisos = [], []
    cats = {c["id"] for c in d["categorias"]}
    ini, fim = d["periodo"]["inicio"], d["periodo"]["fim"]
    vistos = set()
    for it in d["itens"]:
        ref = it.get("id", "?")
        for campo in CAMPOS:
            if not it.get(campo) and not (campo == "resumo" and it.get("fatos")):
                erros.append(f"{ref}: campo '{campo}' vazio")
        if ref in vistos:
            erros.append(f"{ref}: id repetido")
        vistos.add(ref)
        if it.get("categoria") not in cats:
            erros.append(f"{ref}: categoria '{it.get('categoria')}' não existe")
        if not (ini <= it.get("data", "") <= fim):
            avisos.append(f"{ref}: data {it.get('data')} fora do período {ini}..{fim}")
        for f in it.get("fontes", []):
            if not str(f.get("url", "")).startswith("https://"):
                erros.append(f"{ref}: fonte sem URL https ({f})")
    for a in d.get("agenda", []):
        if a.get("data", "") <= fim:
            avisos.append(f"agenda '{a.get('titulo')}': data {a.get('data')} já passou")
    for rid in d.get("resumo_ids", []):
        if rid not in vistos:
            erros.append(f"resumo_ids: '{rid}' não existe")
    for q in d.get("quiz", []):
        if not (0 <= q.get("certa", -1) < len(q.get("opcoes", []))):
            erros.append(f"quiz '{q.get('pergunta')}': índice 'certa' inválido")
        if q.get("id") and q["id"] not in vistos:
            erros.append(f"quiz '{q.get('pergunta')}': item '{q['id']}' não existe")
    return erros, avisos


def anexar_imagens(d):
    """Junta img/<id>.json (gerado pelo img.py) em cada item. Devolve a lista de arquivos usados."""
    usados = []
    for it in d["itens"]:
        it.pop("imagem", None)
        side = IMGDIR / f"{it['id']}.json"
        if not side.exists():
            continue
        meta = json.loads(side.read_text(encoding="utf-8"))
        if (ROOT / meta["arquivo"]).exists():
            it["imagem"] = meta
            usados.append(meta["arquivo"])
        else:
            print(f"aviso: {it['id']}: arquivo de imagem sumiu ({meta['arquivo']})")
    return usados


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    erros, avisos = validar(d)
    for a in avisos:
        print("aviso:", a)
    if erros:
        for e in erros:
            print("ERRO:", e)
        sys.exit(1)

    usados = anexar_imagens(d)
    payload = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    fragmento = tpl.replace("__DADOS__", payload)

    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist" / "artifact.html").write_text(fragmento, encoding="utf-8")
    (ROOT / "dist" / "imagens.json").write_text(json.dumps(sorted(usados), indent=0) + "\n", encoding="utf-8")

    head, body = fragmento.split("<!--/HEAD-->", 1)
    completo = (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head>\n<body>{body}</body>\n</html>\n"
    )
    (ROOT / "index.html").write_text(completo, encoding="utf-8")

    por_cat = {}
    for it in d["itens"]:
        por_cat[it["categoria"]] = por_cat.get(it["categoria"], 0) + 1
    print(f"ok: {len(d['itens'])} notícias, {len(usados)} com imagem, {len(d.get('quiz', []))} no quiz, {len(d.get('agenda', []))} na agenda")
    for c in d["categorias"]:
        print(f"  {c['nome']:<12} {por_cat.get(c['id'], 0)}")


if __name__ == "__main__":
    main()
