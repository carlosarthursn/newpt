#!/usr/bin/env python3
"""Mescla resultados de pesquisa (JSON com "itens", "agenda" e "quiz") em data/noticias.json.

Uso:
  python3 merge.py novos1.json [novos2.json ...] [--novo AAAA-MM-DD] [--fim AAAA-MM-DD]

  --novo  marca os itens acrescentados com adicionado_em e define atualizado_em
  --fim   define periodo.fim (data da última notícia coberta)

Itens com id já existente ou título igual são ignorados. Itens da agenda
cuja data já passou (<= periodo.fim) são removidos. Depois rode: python3 build.py
"""
import argparse
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "noticias.json"
BASE = ROOT / "data" / "base.json"


def chave(texto):
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivos", nargs="+")
    ap.add_argument("--novo")
    ap.add_argument("--fim")
    a = ap.parse_args()

    d = json.loads((DATA if DATA.exists() else BASE).read_text(encoding="utf-8"))
    ids = {it["id"] for it in d["itens"]}
    titulos = {chave(it["titulo"]) for it in d["itens"]}
    agenda = {(x["data"], chave(x["titulo"])) for x in d.get("agenda", [])}
    perguntas = {chave(q["pergunta"]) for q in d.get("quiz", [])}
    novos = pulados = 0

    for arq in a.arquivos:
        r = json.loads(pathlib.Path(arq).read_text(encoding="utf-8"))
        for it in r.get("itens", []):
            if it["id"] in ids or chave(it["titulo"]) in titulos:
                pulados += 1
                continue
            it = {k: v for k, v in it.items() if v not in (None, "")}
            if a.novo:
                it["adicionado_em"] = a.novo
            d["itens"].append(it)
            ids.add(it["id"])
            titulos.add(chave(it["titulo"]))
            novos += 1
        for q in r.get("quiz", []):
            if q.get("id") in ids and chave(q["pergunta"]) not in perguntas and 0 <= q.get("certa", -1) < len(q.get("opcoes", [])):
                d.setdefault("quiz", []).append(q)
                perguntas.add(chave(q["pergunta"]))
        for x in r.get("agenda", []):
            k = (x["data"], chave(x["titulo"]))
            if k not in agenda:
                d.setdefault("agenda", []).append(x)
                agenda.add(k)

    if a.novo:
        d["atualizado_em"] = a.novo
    if a.fim:
        d["periodo"]["fim"] = a.fim
    fim = d["periodo"]["fim"]
    d["agenda"] = sorted((x for x in d.get("agenda", []) if x["data"] > fim), key=lambda x: x["data"])

    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"acrescentados: {novos}, ignorados (repetidos): {pulados}, total: {len(d['itens'])}, agenda: {len(d['agenda'])}")


if __name__ == "__main__":
    main()
