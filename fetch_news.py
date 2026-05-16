#!/usr/bin/env python3
"""
Busca noticias juridicas usando feeds governamentais abertos.
Usa apenas biblioteca padrao do Python.
"""

import json, os, re, sys
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

# Feeds governamentais e institucionais que nao bloqueiam acesso automatizado
FEEDS = [
    # Agencia Brasil (EBC) - servico publico federal
    {"url": "https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",   "fonte": "Agencia Brasil", "secao": "Justica"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/saude/feed.xml",     "fonte": "Agencia Brasil", "secao": "Saude"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",  "fonte": "Agencia Brasil", "secao": "Economia"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/politica/feed.xml",  "fonte": "Agencia Brasil", "secao": "Politica"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/geral/feed.xml",     "fonte": "Agencia Brasil", "secao": "Geral"},
    # TRF-1 (jurisdicao de Belem/PA)
    {"url": "https://www.trf1.jus.br/trf1/noticia/rss",                "fonte": "TRF-1", "secao": ""},
    # STF
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",              "fonte": "STF", "secao": ""},
    # Ministerio da Previdencia Social
    {"url": "https://www.gov.br/previdencia/pt-br/assuntos/noticias/noticias/@@rss.xml", "fonte": "MPS", "secao": ""},
    # INSS
    {"url": "https://www.inss.gov.br/noticias/feed/",                   "fonte": "INSS", "secao": ""},
    # ANS
    {"url": "https://www.gov.br/ans/pt-br/assuntos/noticias/@@rss.xml", "fonte": "ANS", "secao": ""},
]

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept":          "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

PALAVRAS_PREV = [
    "previdencia","previdenciario","previdenciaria",
    "inss","rgps","rpps","aposentadoria","aposentado",
    "beneficio previdenciario","auxilio doenca",
    "pensao por morte","salario de beneficio","tempo de contribuicao",
    "reforma da previdencia","ec 103","segurado","bpc","loas",
    "incapacidade","pericia medica","carencia previdenciaria",
    "previdência","previdenciário","previdenciária",
    "benefício previdenciário","auxílio-doença","auxílio doença",
    "pensão por morte","salário de benefício","tempo de contribuição",
    "reforma da previdência","perícia médica","carência previdenciária",
    "superendividamento","lei 14.181","lei 8.213",
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
    "sistema unico de saude","sistema único de saúde",
    "ubs","sus","hospital","cirurgia","vacina",
]

PALAVRAS_JURIDICO = [
    "stf","stj","trf","tjpa","tribunal","ministerio publico",
    "advocacia","advogado","juridico","processo","recurso",
    "lei ","decreto","portaria","resolucao","constituicao",
    "direito","trabalhista","consumidor","lgpd",
    "imposto","tributo","fiscal","receita federal",
    "habeas corpus","mandado","liminar","sentenca",
    "acordo","julgamento","decisao","condenacao",
]

def limpar(t):
    if not t: return ""
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),("&gt;",">"),
                 ("&quot;",'"'),("&#39;","'"),("&#8211;","-"),("&#8212;","—")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()

def classificar(titulo, desc):
    t = (titulo + " " + desc).lower()
    if any(p in t for p in PALAVRAS_PREV):  return "previdenciario"
    if any(p in t for p in PALAVRAS_SAUDE): return "saude"
    if any(p in t for p in PALAVRAS_JURIDICO): return "geral"
    return None  # irrelevante, descarta

def detectar_tag(titulo, fonte, secao):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":        return "STF"
    if "stj" in t:                           return "STJ"
    if "inss" in t or fonte == "INSS":      return "INSS"
    if "ans" in t or fonte == "ANS":        return "ANS"
    if "trf" in t or fonte == "TRF-1":      return "TRF-1"
    if "portaria" in t or "instrucao" in t: return "Normativa"
    if "lei " in t or "decreto" in t:       return "Legislacao"
    if secao == "Saude":                     return "Saude"
    if secao == "Justica":                   return "Justica"
    if secao == "Economia":                  return "Economia"
    return fonte

def parsear_feed(feed_cfg):
    fonte  = feed_cfg["fonte"]
    secao  = feed_cfg.get("secao", "")
    url    = feed_cfg["url"]
    print(f"\n[{fonte}{' / '+secao if secao else ''}] {url}")

    try:
        req  = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        dados = resp.read()
        print(f"  HTTP 200 | {len(dados)} bytes")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} - ignorado")
        return []
    except Exception as e:
        print(f"  ERRO: {e}")
        return []

    try:
        root = ET.fromstring(dados)
    except ET.ParseError as e:
        print(f"  ERRO XML: {e}")
        return []

    ns    = {"atom": "http://www.w3.org/2005/Atom"}
    itens = root.findall(".//item") or root.findall(".//atom:entry", ns)
    print(f"  {len(itens)} entradas encontradas")

    resultado = []
    for item in itens:
        def txt(tag):
            el = item.find(tag) or item.find(f"atom:{tag}", ns)
            return (el.text or "").strip() if el is not None else ""

        titulo = limpar(txt("title"))
        link   = txt("link") or txt("guid")
        desc   = limpar(txt("description") or txt("summary") or txt("content"))
        pub    = txt("pubDate") or txt("published") or txt("updated")
        if not titulo: continue

        area = classificar(titulo, desc)
        if area is None: continue  # descarta irrelevante

        try:
            dt = parsedate_to_datetime(pub)
        except Exception:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now()

        resultado.append({
            "id":      f"{fonte}_{(link or titulo)}"[:120],
            "area":    area,
            "tag":     detectar_tag(titulo, fonte, secao),
            "titulo":  titulo[:120],
            "fonte":   f"{fonte}{' / '+secao if secao else ''}",
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
    print(f"  Relevantes: {por_area}")
    return resultado

def main():
    print(f"=== Prev & Saude | {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")

    todas = []
    for feed in FEEDS:
        try:
            todas.extend(parsear_feed(feed))
        except Exception as e:
            print(f"ERRO {feed['fonte']}: {e}")

    vistos = set()
    unicas = []
    for n in todas:
        k = n["link"] or n["titulo"]
        if k not in vistos:
            vistos.add(k)
            unicas.append(n)
    unicas.sort(key=lambda x: x["ts"], reverse=True)
    print(f"\nTotal final: {len(unicas)} noticias relevantes")

    if not unicas:
        print("Nenhuma noticia. Preservando news.json anterior.")
        if os.path.exists("news.json"):
            with open("news.json", encoding="utf-8") as f:
                dados = json.load(f)
            dados["aviso"] = "Feeds indisponiveis agora. Exibindo ultima atualizacao bem-sucedida."
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
