#!/usr/bin/env python3
"""
Busca notícias jurídicas nos feeds RSS e gera news.json.
Roda via GitHub Actions toda segunda a sexta às 9h de Brasília.
"""

import json
import os
import re
import sys
from datetime import datetime

try:
    import requests
    import feedparser
except ImportError:
    print("ERRO: instale com  pip install requests feedparser")
    sys.exit(1)

# ─── FEEDS ───────────────────────────────────────────────────────────────────
FEEDS = [
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",                    "fonte": "STF"},
    {"url": "https://www.conjur.com.br/rss.xml",                              "fonte": "Conjur"},
    {"url": "https://www.migalhas.com.br/rss/quentes",                        "fonte": "Migalhas"},
    {"url": "https://www.jusbrasil.com.br/rss/noticias",                      "fonte": "JusBrasil"},
    {"url": "https://www.trf1.jus.br/trf1/noticia/rss",                       "fonte": "TRF-1"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",          "fonte": "Agência Brasil"},
    {"url": "https://www.gov.br/previdencia/pt-br/assuntos/noticias/@@rss.xml","fonte": "MPS"},
]

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Cache-Control":   "no-cache",
}

# ─── CLASSIFICAÇÃO ────────────────────────────────────────────────────────────
PALAVRAS_PREV = [
    "previdência","previdenciário","previdenciária","previdenciario","previdenciaria",
    "inss","rgps","rpps","regime próprio","regime geral",
    "aposentadoria","aposentado","benefício previdenciário","beneficio previdenciario",
    "auxílio-doença","auxilio doença","auxílio acidente","pensão por morte",
    "salário de benefício","salário-benefício","tempo de contribuição",
    "reforma da previdência","ec 103","segurado","contribuinte individual",
    "revisão da vida toda","lei 14.181","lei 8.213","lei 8213",
    "bpc","loas","incapacidade laborativa","perícia médica","pericia medica",
    "carência previdenciária",
]

PALAVRAS_SAUDE = [
    "plano de saúde","plano de saude","planos de saúde","planos de saude",
    "ans","agência nacional de saúde","sus","sistema único de saúde",
    "saúde suplementar","saude suplementar","cobertura médica","cobertura hospitalar",
    "internação","cirurgia","tratamento médico","rol de procedimentos",
    "reajuste de plano","lei 9.656","lei 9656","oncologia","quimioterapia",
    "operadora de saúde","saúde mental","psicoterapia","medicamento",
]


def limpar(texto):
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    for ent, rep in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),("&gt;",">"),("&quot;",'"'),("&#39;","'")]:
        texto = texto.replace(ent, rep)
    return re.sub(r"\s+", " ", texto).strip()


def classificar(titulo, desc):
    t = (titulo + " " + desc).lower()
    if any(p in t for p in PALAVRAS_PREV):  return "previdenciario"
    if any(p in t for p in PALAVRAS_SAUDE): return "saude"
    return "geral"


def detectar_tag(titulo, fonte):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":        return "STF"
    if "stj" in t:                           return "STJ"
    if "inss" in t:                          return "INSS"
    if " ans " in t or "agência nacional de saúde" in t: return "ANS"
    if "trf" in t or "tribunal regional" in t:           return "TRF"
    if "portaria" in t or "instrução normativa" in t:    return "Normativa"
    if "lei " in t or "decreto" in t:                    return "Legislação"
    if "súmula" in t or "acórdão" in t:                  return "Jurisprudência"
    return fonte


# ─── BUSCA ────────────────────────────────────────────────────────────────────
def buscar_feed(feed_cfg):
    url = feed_cfg["url"]
    fonte = feed_cfg["fonte"]
    print(f"\n  [{fonte}] Buscando: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        print(f"  [{fonte}] HTTP {resp.status_code} | {len(resp.content)} bytes")
        if resp.status_code != 200:
            print(f"  [{fonte}] IGNORADO (status {resp.status_code})")
            return []
        conteudo = resp.content
    except Exception as e:
        print(f"  [{fonte}] ERRO de conexão: {e}")
        return []

    feed = feedparser.parse(conteudo)
    entradas = feed.entries
    print(f"  [{fonte}] {len(entradas)} entradas no feed")

    resultado = []
    for entry in entradas:
        titulo = limpar(getattr(entry, "title", ""))
        link   = getattr(entry, "link", "") or getattr(entry, "id", "")
        desc   = limpar(getattr(entry, "summary", "") or getattr(entry, "description", ""))

        if not titulo:
            continue

        # Data de publicação
        pub = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if pub:
            try:
                dt = datetime(*pub[:6])
            except Exception:
                dt = datetime.now()
        else:
            dt = datetime.now()

        area = classificar(titulo, desc)
        resultado.append({
            "id":      f"{fonte}_{(link or titulo)}"[:120],
            "area":    area,
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
    print(f"  [{fonte}] Classificados: {por_area}")
    return resultado


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("=== Prev & Saúde — Atualização de Notícias ===")
    print(f"Horário: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")

    todas = []
    for feed in FEEDS:
        try:
            todas.extend(buscar_feed(feed))
        except Exception as e:
            print(f"  ERRO inesperado em {feed['fonte']}: {e}")

    # Remove duplicatas
    vistos = set()
    unicas = []
    for n in todas:
        chave = n["link"] or n["titulo"]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(n)

    unicas.sort(key=lambda x: x["ts"], reverse=True)

    print(f"\nTotal coletado: {len(unicas)} notícias")

    # Se não encontrou nada, preserva news.json anterior
    if not unicas:
        print("AVISO: nenhuma notícia encontrada. Preservando news.json anterior.")
        if os.path.exists("news.json"):
            with open("news.json", encoding="utf-8") as f:
                dados = json.load(f)
            dados["aviso"] = "Feeds indisponíveis temporariamente. Exibindo notícias da última atualização bem-sucedida."
            with open("news.json", "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        return

    agora = datetime.now()
    saida = {
        "noticias":   unicas,
        "atualizado": agora.strftime("%d/%m/%Y às %H:%M"),
        "total":      len(unicas),
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"Salvo: news.json com {len(unicas)} notícias")


if __name__ == "__main__":
    main()
