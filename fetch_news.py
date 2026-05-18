#!/usr/bin/env python3
"""
Busca todas as noticias juridicas dos feeds configurados e gera news.json.
Sem filtro por palavras-chave — traz tudo das fontes selecionadas.
"""

import json, os, re, ssl, sys
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

FEEDS = [
    {"url": "https://agenciabrasil.ebc.com.br/rss/saude/feed.xml",        "fonte": "Agência Brasil", "secao": "Saúde"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",      "fonte": "Agência Brasil", "secao": "Justiça"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",     "fonte": "Agência Brasil", "secao": "Economia"},
    {"url": "https://agenciabrasil.ebc.com.br/rss/politica/feed.xml",     "fonte": "Agência Brasil", "secao": "Política"},
    {"url": "https://www.gov.br/ans/pt-br/assuntos/noticias/@@rss.xml",   "fonte": "ANS",            "secao": ""},
    {"url": "https://www.gov.br/saude/pt-br/assuntos/noticias/@@rss.xml", "fonte": "Ministério da Saúde", "secao": ""},
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",                 "fonte": "STF",            "secao": ""},
    {"url": "https://www.trf1.jus.br/trf1/noticia/rss",                   "fonte": "TRF-1",          "secao": ""},
]

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept":          "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def limpar(t):
    if not t: return ""
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),("&gt;",">"),
                 ("&quot;",'"'),("&#39;","'"),("&#8211;","-"),("&#160;"," ")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


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
    fonte     = feed_cfg["fonte"]
    secao     = feed_cfg.get("secao", "")
    url       = feed_cfg["url"]
    nome_exib = f"{fonte}{' / '+secao if secao else ''}"

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

    resultado = []
    for item in itens:
        # Título
        tel = (item.find("title") or
               item.find("{http://www.w3.org/2005/Atom}title"))
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

        resultado.append({
            "id":      f"{fonte}_{(link or titulo)}"[:120],
            "fonte":   nome_exib,
            "titulo":  titulo[:150],
            "resumo":  desc[:300],
            "link":    link,
            "data":    dt.strftime("%d/%m/%Y"),
            "hora":    dt.strftime("%H:%M"),
            "ts":      int(dt.timestamp() * 1000),
            "favorito": False,
        })

    print(f"  {len(resultado)} itens coletados")
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
    print(f"\nTotal: {len(unicas)} notícias")

    if not unicas:
        print("Nenhuma notícia. Preservando news.json anterior.")
        if os.path.exists("news.json"):
            with open("news.json", encoding="utf-8") as f:
                dados = json.load(f)
            dados["aviso"] = "Feeds indisponíveis. Exibindo última atualização."
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
