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

FEEDS = [
    # area_default: todos os itens desta fonte recebem esta area por padrao
    {"url": "https://agenciabrasil.ebc.com.br/rss/saude/feed.xml",       "fonte": "Agência Brasil", "secao": "Saúde",    "area_default": "saude"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",     "fonte": "Agência Brasil", "secao": "Justiça",  "area_default": "geral"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",    "fonte": "Agência Brasil", "secao": "Economia", "area_default": "geral"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/politica/feed.xml",    "fonte": "Agência Brasil", "secao": "Política", "area_default": "geral"},
    {"url": "https://www.gov.br/ans/pt-br/assuntos/noticias/@@rss.xml",  "fonte": "ANS",            "secao": "",         "area_default": "saude"},
    {"url": "https://www.gov.br/saude/pt-br/assuntos/noticias/@@rss.xml","fonte": "Ministério da Saúde","secao": "",     "area_default": "saude"},
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",                "fonte": "STF",            "secao": "",         "area_default": "geral"},
    {"url": "https://www.trf1.jus.br/trf1/noticia/rss",                  "fonte": "TRF-1",          "secao": "",         "area_default": "geral"},
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
    "ec 103","segurado","bpc","loas","incapacidade laborativa",
    "pericia medica","perícia médica","carencia previdenciaria",
    "superendividamento","lei 14.181","lei 8.213",
    "beneficio por incapacidade","benefício por incapacidade",
    "tempo de contribuicao","tempo de contribuição",
]

PALAVRAS_SAUDE = [
    "plano de saude","plano de saúde","planos de saude","planos de saúde",
    "saude suplementar","saúde suplementar",
    "cobertura medica","cobertura médica","cobertura hospitalar",
    "internacao","internação","tratamento medico","tratamento médico",
    "rol de procedimentos","reajuste de plano",
    "lei 9.656","lei 9656","oncologia","quimioterapia",
    "operadora de saude","operadora de saúde",
    "saude mental","saúde mental","psicoterapia",
    "sistema unico de saude","sistema único de saúde",
]


def limpar(t):
    if not t:
        return ""
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),("&gt;",">"),
                 ("&quot;",'"'),("&#39;","'"),("&#8211;","-"),("&#8212;","—"),
                 ("&#160;"," ")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def refinar_area(titulo, desc, area_default):
    """Tenta classificar com precisão; se não conseguir, usa o default da fonte."""
    t = (titulo + " " + (desc or "")).lower()
    if any(p in t for p in PALAVRAS_PREV):
        return "previdenciario"
    if any(p in t for p in PALAVRAS_SAUDE):
        return "saude"
    return area_default  # Sempre retorna o default — nunca None


def detectar_tag(titulo, fonte, secao):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":         return "STF"
    if "stj" in t:                            return "STJ"
    if "inss" in t:                           return "INSS"
    if "ans" in t or fonte == "ANS":         return "ANS"
    if "trf" in t or fonte == "TRF-1":       return "TRF-1"
    if "portaria" in t:                       return "Portaria"
    if "resolucao" in t or "resolução" in t: return "Resolução"
    if "instrucao" in t or "instrução" in t: return "IN"
    if "lei " in t or "decreto" in t:        return "Legislação"
    if secao:                                 return secao
    return fonte


def http_get(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        return resp.read()


def parsear_xml(dados):
    for enc in ["utf-8", "iso-8859-1", "latin-1"]:
        try:
            texto = dados.decode(enc, errors="replace")
            texto = re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"', texto)
            return ET.fromstring(texto.encode("utf-8"))
        except ET.ParseError:
            continue
    return None


def parsear_feed(feed_cfg):
    fonte      = feed_cfg["fonte"]
    secao      = feed_cfg.get("secao", "")
    url        = feed_cfg["url"]
    area_def   = feed_cfg["area_default"]  # sempre definido
    nome_exib  = f"{fonte}{' / '+secao if secao else ''}"

    print(f"\n[{nome_exib}]")

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
        print(f"  ERRO: XML inválido")
        return []

    ns    = {"atom": "http://www.w3.org/2005/Atom"}
    itens = root.findall(".//item") or root.findall(".//atom:entry", ns)
    print(f"  {len(itens)} entradas")

    # Debug: mostra o primeiro item para inspecao
    if itens:
        item0 = itens[0]
        t0 = item0.find("title") or item0.find("{http://www.w3.org/2005/Atom}title")
        titulo0 = (t0.text or "").strip() if t0 is not None else "(sem titulo)"
        print(f"  Primeiro item: '{titulo0[:60]}'")

    resultado = []
    for item in itens:
        # Título
        tel = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
        titulo = limpar(tel.text if tel is not None else "")
        if not titulo:
            continue

        # Link
        lel = item.find("link")
        if lel is not None:
            link = (lel.text or "").strip() or lel.get("href", "")
        else:
            lel2 = item.find("{http://www.w3.org/2005/Atom}link")
            link = lel2.get("href", "") if lel2 is not None else ""

        # Descrição
        del_ = (item.find("description") or
                item.find("{http://www.w3.org/2005/Atom}summary") or
                item.find("{http://www.w3.org/2005/Atom}content"))
        desc = limpar(del_.text if del_ is not None else "")

        # Data
        pel = (item.find("pubDate") or
               item.find("{http://www.w3.org/2005/Atom}published") or
               item.find("{http://www.w3.org/2005/Atom}updated"))
        pub = (pel.text or "").strip() if pel is not None else ""
        try:
            dt = parsedate_to_datetime(pub)
        except Exception:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now()

        # Classificação — NUNCA descarta: usa area_default como fallback
        area = refinar_area(titulo, desc, area_def)

        resultado.append({
            "id":      f"{fonte}_{(link or titulo)}"[:120],
            "area":    area,
            "tag":     detectar_tag(titulo, fonte, secao),
            "titulo":  titulo[:120],
            "fonte":   nome_exib,
            "resumo":  desc[:280],
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
            print(f"ERRO {feed['fonte']}: {e}")

    # Remove duplicatas por link
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
            dados["aviso"] = "Feeds indisponíveis agora. Exibindo última atualização."
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
    print(f"Salvo: {len(unicas)} notícias em news.json")


if __name__ == "__main__":
    main()
