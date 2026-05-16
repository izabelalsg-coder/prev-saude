#!/usr/bin/env python3
"""
Busca noticias juridicas nos feeds RSS e gera news.json.
Usa apenas biblioteca padrao do Python - sem dependencias externas.
"""

import json, os, re, sys
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

FEEDS = [
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",           "fonte": "STF"},
    {"url": "https://www.conjur.com.br/rss.xml",                     "fonte": "Conjur"},
    {"url": "https://www.migalhas.com.br/rss/quentes",               "fonte": "Migalhas"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/justica/feed.xml", "fonte": "Agencia Brasil"},
    {"url": "https://www.trf1.jus.br/trf1/noticia/rss",              "fonte": "TRF-1"},
]

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept":          "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Cache-Control":   "no-cache",
}

PALAVRAS_PREV = [
    "previdencia","previdenciario","previdenciaria",
    "inss","rgps","rpps","aposentadoria","aposentado",
    "beneficio previdenciario","auxilio doenca","auxilio-doenca",
    "pensao por morte","salario de beneficio","tempo de contribuicao",
    "reforma da previdencia","ec 103","segurado","bpc","loas",
    "incapacidade","pericia medica","carencia previdenciaria",
    "previdência","previdenciário","previdenciária",
    "benefício previdenciário","auxílio-doença","auxílio doença",
    "pensão por morte","salário de benefício","tempo de contribuição",
    "reforma da previdência","perícia médica","carência previdenciária",
]

PALAVRAS_SAUDE = [
    "plano de saude","planos de saude","ans","sus",
    "saude suplementar","cobertura medica","cobertura hospitalar",
    "internacao","tratamento medico","rol de procedimentos",
    "reajuste de plano","lei 9656","oncologia",
    "operadora de saude","saude mental","psicoterapia","medicamento",
    "plano de saúde","planos de saúde","saúde suplementar",
    "cobertura médica","internação","tratamento médico",
    "operadora de saúde","saúde mental",
]

def limpar(t):
    if not t: return ""
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),("&gt;",">"),
                 ("&quot;",'"'),("&#39;","'"),("&#8211;","-"),("&#8212;","-")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()

def classificar(titulo, desc):
    t = (titulo + " " + desc).lower()
    if any(p in t for p in PALAVRAS_PREV):  return "previdenciario"
    if any(p in t for p in PALAVRAS_SAUDE): return "saude"
    return "geral"

def detectar_tag(titulo, fonte):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":     return "STF"
    if "stj" in t:                        return "STJ"
    if "inss" in t:                       return "INSS"
    if "ans" in t:                        return "ANS"
    if "trf" in t:                        return "TRF"
    if "portaria" in t or "instru" in t:  return "Normativa"
    if "lei " in t or "decreto" in t:     return "Legislacao"
    if "sumula" in t or "acordao" in t:   return "Jurisprudencia"
    return fonte

def parsear_feed(feed_cfg):
    fonte = feed_cfg["fonte"]
    url   = feed_cfg["url"]
    print(f"\n[{fonte}] {url}")

    try:
        req  = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        codigo = resp.status
        dados  = resp.read()
        print(f"[{fonte}] HTTP {codigo} | {len(dados)} bytes")
    except urllib.error.HTTPError as e:
        print(f"[{fonte}] HTTP {e.code}: {e.reason}")
        return []
    except Exception as e:
        print(f"[{fonte}] ERRO: {e}")
        return []

    try:
        root = ET.fromstring(dados)
    except ET.ParseError as e:
        print(f"[{fonte}] ERRO XML: {e}")
        return []

    ns   = {"atom": "http://www.w3.org/2005/Atom"}
    itens = root.findall(".//item") or root.findall(".//atom:entry", ns)
    print(f"[{fonte}] {len(itens)} entradas no feed")

    resultado = []
    for item in itens:
        def txt(tag):
            el = item.find(tag) or item.find(f"atom:{tag}", ns)
            return (el.text or "").strip() if el is not None else ""

        titulo = limpar(txt("title"))
        link   = txt("link") or txt("guid")
        desc   = limpar(txt("description") or txt("summary") or txt("content"))
        pub    = txt("pubDate") or txt("published") or txt("updated")

        if not titulo:
            continue

        try:
            dt = parsedate_to_datetime(pub)
        except Exception:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now()

        resultado.append({
            "id":      f"{fonte}_{(link or titulo)}"[:120],
            "area":    classificar(titulo, desc),
            "tag":     detectar_tag(titulo, fonte),
            "titulo":  titulo[:120],
            "fonte":   fonte,
            "resumo":  desc[:280] if desc else "",
            "link":    link,
            "data":    dt.strftime("%d/%m/%Y"),
            "hora":    dt.strftime("%H:%M"),
            "ts":      int(dt.timestamp() * 1000),
            "favorito": False,
        })

    por_area = {}
    for n in resultado:
        por_area[n["area"]] = por_area.get(n["area"], 0) + 1
    print(f"[{fonte}] Classificados: {por_area}")
    return resultado

def main():
    print(f"=== Prev & Saude | {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")

    todas = []
    for feed in FEEDS:
        try:
            todas.extend(parsear_feed(feed))
        except Exception as e:
            print(f"ERRO inesperado {feed['fonte']}: {e}")

    vistos = set()
    unicas = []
    for n in todas:
        k = n["link"] or n["titulo"]
        if k not in vistos:
            vistos.add(k)
            unicas.append(n)
    unicas.sort(key=lambda x: x["ts"], reverse=True)
    print(f"\nTotal: {len(unicas)} noticias")

    if not unicas:
        print("Nenhuma noticia encontrada. Preservando news.json anterior.")
        if os.path.exists("news.json"):
            with open("news.json", encoding="utf-8") as f:
                dados = json.load(f)
            dados["aviso"] = "Feeds temporariamente indisponiveis. Exibindo ultima atualizacao bem-sucedida."
            with open("news.json", "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        sys.exit(0)

    saida = {
        "noticias":   unicas,
        "atualizado": datetime.now().strftime("%d/%m/%Y as %H:%M"),
        "total":      len(unicas),
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print(f"Salvo: news.json com {len(unicas)} noticias")

if __name__ == "__main__":
    main()
