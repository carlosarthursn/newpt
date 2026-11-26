#!/usr/bin/env python3
"""Busca e baixa imagens de licença livre (Wikimedia Commons e NASA) para as notícias.

Comandos:
  python3 img.py busca "termo" [-n 8]        procura arquivos no Commons (mostra licença e tamanho)
  python3 img.py nasa-busca "termo" [-n 8]   procura no acervo de imagens da NASA (domínio público)
  python3 img.py commons ITEM_ID "File:Nome.jpg" --legenda "o que a imagem mostra"
  python3 img.py nasa ITEM_ID NASA_ID --legenda "o que a imagem mostra"
  python3 img.py remover ITEM_ID

Cada download vira img/ITEM_ID.webp (até 960 px) + img/ITEM_ID.json com crédito, licença e legenda.
O build.py junta esses metadados nos itens. Só entram arquivos com licença livre.
"""
import argparse
import html
import io
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
IMG = ROOT / "img"
UA = "TabelaPeriodicaNoticias/1.0 (projeto pessoal; imagens de licenca livre)"
COMMONS = "https://commons.wikimedia.org/w/api.php"
LIVRES = ("cc0", "cc by", "cc-by", "public domain", "pd", "domínio público", "attribution", "gfdl", "no restrictions")
PROIBIDAS = ("nc", "nd", "non-free", "fair use")


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for tentativa in range(8):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            return data if binary else json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or tentativa == 7:
                raise
            espera = min(int(e.headers.get("Retry-After") or 20), 60) + 2
            print(f"(limite do servidor, esperando {espera}s)", file=sys.stderr)
            time.sleep(espera)


def limpa(s):
    s = re.sub(r"<[^>]+>", "", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def licenca_livre(lic):
    low = lic.lower()
    tokens = set(re.split(r"[^a-z]+", low))
    return any(low.startswith(x) or x in low for x in LIVRES) and not (tokens & {"nc", "nd"}) and "non-free" not in low and "fair use" not in low


def commons_info(params):
    q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", **params}
    return get(COMMONS + "?" + urllib.parse.urlencode(q))


def meta_commons(ii):
    em = ii.get("extmetadata", {})
    v = lambda k: limpa(em.get(k, {}).get("value", ""))
    return {"licenca": v("LicenseShortName") or v("UsageTerms"), "credito": v("Artist") or v("Credit"), "descricao": v("ImageDescription")[:140]}


def cmd_busca(a):
    r = commons_info({"generator": "search", "gsrsearch": a.termo, "gsrnamespace": 6, "gsrlimit": a.n, "iiurlwidth": 320})
    pages = sorted(r.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    if not pages:
        print("nada encontrado")
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii.get("mime", "").startswith("image/"):
            continue
        m = meta_commons(ii)
        ok = "LIVRE" if licenca_livre(m["licenca"]) else "??"
        print(f"{p['title']} | {ii.get('width')}x{ii.get('height')} | {m['licenca']} [{ok}] | {m['credito'][:50]} | {m['descricao'][:90]}")


def cmd_nasa_busca(a):
    r = get("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": a.termo, "media_type": "image"}))
    for it in r.get("collection", {}).get("items", [])[: a.n]:
        d = it["data"][0]
        print(f"{d['nasa_id']} | {d.get('date_created', '')[:10]} | {d.get('center', '')} | {d.get('title', '')[:90]}")


def salvar(item_id, raw, meta):
    im = Image.open(io.BytesIO(raw))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        fundo = Image.new("RGB", im.size, (255, 255, 255))
        fundo.paste(im, mask=im.split()[-1])
        im = fundo
    else:
        im = im.convert("RGB")
    im.thumbnail((960, 960))
    IMG.mkdir(exist_ok=True)
    arq = IMG / f"{item_id}.webp"
    im.save(arq, "WEBP", quality=72, method=6)
    meta.update({"arquivo": f"img/{item_id}.webp", "largura": im.width, "altura": im.height})
    (IMG / f"{item_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok: {arq.relative_to(ROOT)} {im.width}x{im.height} {arq.stat().st_size // 1024} KB | {meta['credito'][:40]} | {meta['licenca']}")


def checa_existente(a):
    if (IMG / f"{a.item}.webp").exists() and not a.forcar:
        sys.exit(f"img/{a.item}.webp já existe (é de outra notícia?). Use outro id, ou --forcar para substituir de propósito.")


def cmd_commons(a):
    checa_existente(a)
    titulo = a.arquivo if a.arquivo.startswith("File:") else "File:" + a.arquivo
    r = commons_info({"titles": titulo, "iiurlwidth": 960})
    page = next(iter(r["query"]["pages"].values()))
    if "imageinfo" not in page:
        sys.exit(f"arquivo não encontrado: {titulo}")
    ii = page["imageinfo"][0]
    m = meta_commons(ii)
    if not licenca_livre(m["licenca"]):
        sys.exit(f"licença não aceita: {m['licenca']!r}")
    raw = get(ii.get("thumburl") or ii["url"], binary=True)
    salvar(a.item, raw, {"credito": m["credito"] or "Wikimedia Commons", "licenca": m["licenca"], "fonte": ii["descriptionurl"], "legenda": a.legenda})


def cmd_nasa(a):
    checa_existente(a)
    r = get("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"nasa_id": a.nasa_id}))
    items = r.get("collection", {}).get("items", [])
    if not items:
        sys.exit("nasa_id não encontrado")
    d = items[0]["data"][0]
    hrefs = [x["href"] for x in get(f"https://images-api.nasa.gov/asset/{urllib.parse.quote(a.nasa_id)}")["collection"]["items"]]
    escolha = next((h for suf in ("~large.jpg", "~medium.jpg", "~orig.jpg", "~large.png", "~orig.png") for h in hrefs if h.endswith(suf)), None)
    if not escolha:
        sys.exit("sem arquivo de imagem utilizável")
    credito = " / ".join(x for x in ["NASA", d.get("center", ""), limpa(d.get("photographer", "")) or limpa(d.get("secondary_creator", ""))] if x)
    raw = get(escolha.replace("http://", "https://"), binary=True)
    salvar(a.item, raw, {"credito": credito, "licenca": "Domínio público (NASA)", "fonte": f"https://images.nasa.gov/details/{urllib.parse.quote(a.nasa_id)}", "legenda": a.legenda})


def cmd_remover(a):
    for ext in (".webp", ".json"):
        (IMG / f"{a.item}{ext}").unlink(missing_ok=True)
    print("removido:", a.item)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("busca"); b.add_argument("termo"); b.add_argument("-n", type=int, default=8); b.set_defaults(f=cmd_busca)
    nb = sp.add_parser("nasa-busca"); nb.add_argument("termo"); nb.add_argument("-n", type=int, default=8); nb.set_defaults(f=cmd_nasa_busca)
    c = sp.add_parser("commons"); c.add_argument("item"); c.add_argument("arquivo"); c.add_argument("--legenda", required=True); c.add_argument("--forcar", action="store_true"); c.set_defaults(f=cmd_commons)
    n = sp.add_parser("nasa"); n.add_argument("item"); n.add_argument("nasa_id"); n.add_argument("--legenda", required=True); n.add_argument("--forcar", action="store_true"); n.set_defaults(f=cmd_nasa)
    r = sp.add_parser("remover"); r.add_argument("item"); r.set_defaults(f=cmd_remover)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
