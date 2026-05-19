#!/usr/bin/env python3
import json, re, sys
import urllib.request
from datetime import datetime
from xml.etree import ElementTree as ET

FEEDS = [
    ("https://agenciabrasil.ebc.com.br/rss/saude/feed.xml",    "Agência Brasil / Saúde"),
    ("https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",  "Agência Brasil / Justiça"),
    ("https://agenciabrasil.ebc.com.br/rss/economia/feed.xml", "Agência Brasil / Economia"),
    ("https://agenciabrasil.ebc.com.br/rss/politica/feed.xml", "Agência Brasil / Política"),
]

LIMITE_DIAS = 30  # descarta notícias mais antigas que isso

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"}

def buscar(url):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read()

noticias = []

for url, fonte in FEEDS:
    print(f"\n[{fonte}] {url}")
    try:
        xml = buscar(url)
        print(f"  OK: {len(xml)} bytes")
    except Exception as e:
        print(f"  ERRO: {e}")
        continue

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        try:
            texto = xml.decode("iso-8859-1", errors="replace")
            texto = re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"', texto)
            root = ET.fromstring(texto.encode("utf-8"))
        except Exception as e2:
            print(f"  ERRO XML: {e2}")
            continue

    itens = root.findall(".//item")
    print(f"  {len(itens)} itens")

    for item in itens:
        t = item.find("title")
        l = item.find("link")
        d = item.find("description")
        titulo = (t.text or "").strip() if t is not None else ""
        if not titulo:
            continue
        link   = (l.text or "").strip() if l is not None else ""
        resumo = re.sub(r"<[^>]+>", " ", d.text or "").strip() if d is not None else ""

        # Data real da publicação
        p = item.find("pubDate")
        pub = (p.text or "").strip() if p is not None else ""
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub)
        except Exception:
            dt = datetime.now()

        # Tag baseada no título e fonte
        tl = titulo.lower()
        if "stf" in tl or fonte == "STF":          tag = "STF"
        elif "stj" in tl:                           tag = "STJ"
        elif "inss" in tl:                          tag = "INSS"
        elif "ans" in tl or fonte == "ANS":         tag = "ANS"
        elif "anvisa" in tl:                        tag = "Anvisa"
        elif "trf" in tl or fonte == "TRF-1":       tag = "TRF-1"
        elif "portaria" in tl:                      tag = "Portaria"
        elif "resolucao" in tl or "resolução" in tl: tag = "Resolução"
        elif "lei " in tl or "decreto" in tl:       tag = "Legislação"
        elif "ministério" in fonte.lower():         tag = fonte.split("/")[0].strip()
        else:                                       tag = fonte.split("/")[-1].strip()

        # Descarta itens muito antigos
        idade_dias = (datetime.now(dt.tzinfo) - dt).days if dt.tzinfo else (datetime.now() - dt).days
        if idade_dias > LIMITE_DIAS:
            continue

        # Descarta títulos inválidos (muito curtos, só números, categorias)
        if len(titulo) < 15 or titulo.strip().isdigit():
            continue

        print(f"  + {titulo[:60]}")
        noticias.append({
            "id":      f"{fonte}_{link or titulo}"[:120],
            "tag":     tag,
            "titulo":  titulo[:150],
            "fonte":   fonte,
            "resumo":  resumo[:300],
            "link":    link,
            "data":    dt.strftime("%d/%m/%Y"),
            "hora":    dt.strftime("%H:%M"),
            "ts":      int(dt.timestamp() * 1000),
            "favorito": False,
        })

print(f"\nTotal: {len(noticias)} notícias")

if not noticias:
    print("Zero notícias. Preservando news.json anterior.")
    sys.exit(0)

with open("news.json", "w", encoding="utf-8") as f:
    json.dump({
        "noticias":   noticias,
        "atualizado": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        "total":      len(noticias),
    }, f, ensure_ascii=False, indent=2)

print("Salvo: news.json")
