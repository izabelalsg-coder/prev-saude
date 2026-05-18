#!/usr/bin/env python3
"""
Busca noticias juridicas nos feeds RSS e gera news.json.
Usa apenas biblioteca padrao do Python.
"""

import json, os, re, ssl, sys
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

# area_default: classifica todos os itens da fonte nessa area sem precisar de palavra-chave
# area_default None = exige palavra-chave para classificar
FEEDS = [
    {"url": "https://agenciabrasil.ebc.com.br/rss/saude/feed.xml",      "fonte": "Agência Brasil", "secao": "Saúde",      "area_default": "saude"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",    "fonte": "Agência Brasil", "secao": "Justiça",    "area_default": None},
    {"url": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",   "fonte": "Agência Brasil", "secao": "Economia",   "area_default": None},
    {"url": "https://agenciabrasil.ebc.com.br/rss/politica/feed.xml",   "fonte": "Agência Brasil", "secao": "Política",   "area_default": None},
    {"url": "https://www.gov.br/ans/pt-br/assuntos/noticias/@@rss.xml", "fonte": "ANS",            "secao": "",           "area_default": "saude"},
    {"url": "https://www.gov.br/saude/pt-br/assuntos/noticias/@@rss.xml","fonte":"Ministério da Saúde","secao":"",        "area_default": "saude"},
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",               "fonte": "STF",            "secao": "",           "area_default": None},
    {"url": "https://www.trf1.jus.br/trf1/noticia/rss",                 "fonte": "TRF-1",          "secao": "",           "area_default": None},
]

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept":          "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

PALAVRAS_PREV = [
    "previdencia","previdenciario","previdenciaria",
    "previdência","previdenciário","previdenciária",
    "inss","rgps","rpps","aposentadoria","aposentado",
    "beneficio previdenciario","benefício previdenciário",
    "auxilio doenca","auxílio-doença","pensao por morte","pensão por morte",
    "salario de beneficio","salário de benefício",
    "reforma da previdencia","reforma da previdência",
    "ec 103","segurado","bpc","loas","incapacidade",
    "pericia medica","perícia médica","carencia previdenciaria",
    "superendividamento","lei 14.181","lei 8.213",
    "beneficio por incapacidade","benefício por incapacidade",
    "tempo de contribuicao","tempo de contribuição",
]

PALAVRAS_SAUDE = [
    "plano de saude","plano de saúde","planos de saude","planos de saúde",
    "saude suplementar","saúde suplementar",
    "cobertura medica","cobertura médica","cobertura hospitalar",
    "internacao","internação","cirurgia","tratamento medico","tratamento médico",
    "rol de procedimentos","reajuste de plano",
    "lei 9.656","lei 9656","oncologia","quimioterapia",
    "operadora de saude","operadora de saúde",
    "saude mental","saúde mental","psicoterapia","medicamento",
    "sistema unico de saude","sistema único de saúde",
    "ubs","hospitalar","vacina","sus ",
]

PALAVRAS_JURIDICO_PREV_SAUDE = [
    "stf","stj","trf","tribunal","ministerio publico","ministério público",
    "inss","ans","previdenci","saude","saúde","beneficio","benefício",
    "trabalhist","aposentad","segurado","plano de saude","plano de saúde",
]


def limpar(t):
    if not t: return ""
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),("&gt;",">"),
                 ("&quot;",'"'),("&#39;","'"),("&#8211;","-"),("&#8212;","—")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def classificar(titulo, desc, area_default):
    t = (titulo + " " + desc).lower()
    if any(p in t for p in PALAVRAS_PREV):  return "previdenciario"
    if any(p in t for p in PALAVRAS_SAUDE): return "saude"
    if area_default:                         return area_default
    # Para fontes sem default, aceita se tiver qualquer termo juridico relevante
    if any(p in t for p in PALAVRAS_JURIDICO_PREV_SAUDE): return "geral"
    return None


def detectar_tag(titulo, fonte, secao):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":         return "STF"
    if "stj" in t:                            return "STJ"
    if "inss" in t or fonte == "INSS":       return "INSS"
    if " ans " in t or fonte == "ANS":       return "ANS"
    if "trf" in t or fonte == "TRF-1":       return "TRF-1"
    if "portaria" in t:                       return "Portaria"
    if "resolucao" in t or "resolução" in t: return "Resolução"
    if "instrucao" in t or "instrução" in t: return "Instrução"
    if "lei " in t or "decreto" in t:        return "Legislação"
    if secao:                                 return secao
    return fonte


def http_get(url):
    # Contexto SSL tolerante para sites com certificado problemático
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        return resp.read()


def parsear_xml(dados):
    """Tenta parsear XML, tratando erros de encoding comuns."""
    try:
        return ET.fromstring(dados)
    except ET.ParseError:
        pass
    # Tenta UTF-8 explícito
    try:
        texto = dados.decode("utf-8", errors="replace")
        texto = re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"', texto)
        return ET.fromstring(texto.encode("utf-8"))
    except ET.ParseError:
        pass
    # Tenta ISO-8859-1
    try:
        texto = dados.decode("iso-8859-1", errors="replace")
        return ET.fromstring(texto.encode("utf-8"))
    except ET.ParseError:
        return None


def parsear_feed(feed_cfg):
    fonte       = feed_cfg["fonte"]
    secao       = feed_cfg.get("secao", "")
    url         = feed_cfg["url"]
    area_def    = feed_cfg.get("area_default")
    nome_exib   = f"{fonte}{' / '+secao if secao else ''}"

    print(f"\n[{nome_exib}] {url}")
    try:
        dados = http_get(url)
        print(f"  HTTP 200 | {len(dados)} bytes")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} — ignorado")
        return []
    except Exception as e:
        print(f"  ERRO: {e}")
        return []

    root = parsear_xml(dados)
    if root is None:
        print(f"  ERRO: não foi possível parsear XML")
        return []

    ns    = {"atom": "http://www.w3.org/2005/Atom"}
    itens = root.findall(".//item") or root.findall(".//atom:entry", ns)
    print(f"  {len(itens)} entradas no feed")

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

        area = classificar(titulo, desc, area_def)
        if area is None: continue

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
            "fonte":   nome_exib,
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
    print(f"  Classificados: {por_area}")
    return resultado


def main():
    print(f"=== Prev & Saúde | {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")

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

    print(f"\nTotal final: {len(unicas)} notícias")

    if not unicas:
        print("Nenhuma notícia. Preservando news.json anterior.")
        if os.path.exists("news.json"):
            with open("news.json", encoding="utf-8") as f:
                dados = json.load(f)
            dados["aviso"] = "Feeds indisponíveis agora. Exibindo última atualização bem-sucedida."
            with open("news.json", "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        sys.exit(0)

    saida = {
        "noticias":   unicas,
        "atualizado": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        "total":      len(unicas),
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print(f"Salvo: news.json com {len(unicas)} notícias")


if __name__ == "__main__":
    main()
