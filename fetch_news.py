#!/usr/bin/env python3
import json, re, sys, os, urllib.request, urllib.error
from datetime import datetime
from xml.etree import ElementTree as ET

# ═══════════════════════════════════════════════════════════════
# FONTES
# Para incluir o STF, complete o cadastro em https://portal.stf.jus.br/push/
# e substitua a URL abaixo pelo feed pessoal gerado no STF Push.
# ═══════════════════════════════════════════════════════════════
FEEDS = [
    ("https://agenciabrasil.ebc.com.br/rss/saude/feed.xml",    "Agência Brasil / Saúde"),
    ("https://agenciabrasil.ebc.com.br/rss/justica/feed.xml",  "Agência Brasil / Justiça"),
    ("https://agenciabrasil.ebc.com.br/rss/economia/feed.xml", "Agência Brasil / Economia"),
    ("https://agenciabrasil.ebc.com.br/rss/politica/feed.xml", "Agência Brasil / Política"),
    ("https://www.conjur.com.br/rss.xml",                      "Conjur"),
    ("https://res.stj.jus.br/hrestp-c-portalp/RSS.xml",        "STJ"),
    ("https://portal.stf.jus.br/push/api/pushRss.asp?usuario=1665454&email=izabelagoncalves.adv@gmail.com", "STF"),
]

import unicodedata

LIMITE_DIAS = 30  # descarta notícias mais antigas que isso
MAX_SELECIONADAS = 25  # teto de notícias curadas por execução

import ssl

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"}

CONTEXTO_SEM_VERIFICACAO = ssl._create_unverified_context()

# Palavras-chave usadas para pontuar a relevância de cada notícia.
# Quanto mais termos aparecerem no título/resumo, maior a pontuação.
PALAVRAS_CHAVE = [
    # Direito Previdenciário
    "aposentadoria", "aposentar", "inss", "tempo de contribuicao", "contribuicao",
    "beneficio", "beneficios", "bpc", "loas", "auxilio-doenca", "auxilio doenca",
    "pensao por morte", "previdenciario", "previdencia", "ec 103", "reforma da previdencia",
    "regra de transicao", "salario de beneficio", "fator previdenciario",
    "aposentadoria especial", "revisao de beneficio", "rpps", "regime proprio",
    "contagem de tempo", "carencia", "atividade rural", "atividade especial",
    "ppp", "ltcat", "invalidez", "incapacidade",
    # Direito em Saude
    "plano de saude", "ans ", "anvisa", "negativa de cobertura", "cobertura",
    "reajuste de plano", "saude suplementar", "paciente", "cirurgia", "tratamento",
    "medicamento", "home care", "internacao", "liminar saude", "operadora de saude",
    # Marcadores gerais de relevancia juridica
    "tema repetitivo", "sumula", "stj", "stf", "trf", "tnu", "jurisprudencia",
    "projeto de lei", "portaria", "resolucao", "decreto", "cnj", "recurso repetitivo",
]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def pontuar(noticia):
    texto = normalizar(noticia["titulo"] + " " + noticia["resumo"])
    return sum(1 for termo in PALAVRAS_CHAVE if termo in texto)


def buscar(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        return urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            print("  aviso: certificado não reconhecido, tentando sem verificação...")
            return urllib.request.urlopen(req, timeout=20, context=CONTEXTO_SEM_VERIFICACAO).read()
        raise


def parsear_feed(xml):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        texto = xml.decode("iso-8859-1", errors="replace")
        texto = re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"', texto)
        root = ET.fromstring(texto.encode("utf-8"))
    return root


def coletar_noticias():
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
            root = parsear_feed(xml)
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
            link = (l.text or "").strip() if l is not None else ""
            resumo = re.sub(r"<[^>]+>", " ", d.text or "").strip() if d is not None else ""

            p = item.find("pubDate")
            pub = (p.text or "").strip() if p is not None else ""
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub)
            except Exception:
                dt = datetime.now()

            tl = titulo.lower()
            if fonte == "STF" or "stf" in tl:            tag = "STF"
            elif fonte == "STJ" or "stj" in tl:          tag = "STJ"
            elif fonte == "Conjur":                       tag = "Conjur"
            elif "inss" in tl:                            tag = "INSS"
            elif "ans" in tl or fonte == "ANS":           tag = "ANS"
            elif "anvisa" in tl:                          tag = "Anvisa"
            elif "trf" in tl or fonte == "TRF-1":         tag = "TRF-1"
            elif "portaria" in tl:                        tag = "Portaria"
            elif "resolucao" in tl or "resolução" in tl:  tag = "Resolução"
            elif "lei " in tl or "decreto" in tl:         tag = "Legislação"
            elif "ministério" in fonte.lower():           tag = fonte.split("/")[0].strip()
            else:                                         tag = fonte.split("/")[-1].strip()

            idade_dias = (datetime.now(dt.tzinfo) - dt).days if dt.tzinfo else (datetime.now() - dt).days
            if idade_dias > LIMITE_DIAS:
                continue
            if len(titulo) < 15 or titulo.strip().isdigit():
                continue

            print(f"  + {titulo[:60]}")
            noticias.append({
                "id":       f"{fonte}_{link or titulo}"[:120],
                "tag":      tag,
                "titulo":   titulo[:150],
                "fonte":    fonte,
                "resumo":   resumo[:300],
                "link":     link,
                "data":     dt.strftime("%d/%m/%Y"),
                "hora":     dt.strftime("%H:%M"),
                "ts":       int(dt.timestamp() * 1000),
                "favorito": False,
            })
    return noticias


def curar_por_palavras_chave(noticias):
    """Pontua cada notícia pelo número de termos do perfil de atuação que
    aparecem no título/resumo e mantém apenas as mais relevantes.
    Não depende de API nem gera custo."""
    if not noticias:
        return noticias

    pontuadas = [(pontuar(n), n) for n in noticias]
    relevantes = [(p, n) for p, n in pontuadas if p > 0]
    relevantes.sort(key=lambda x: (-x[0], -x[1]["ts"]))

    curadas = [n for _, n in relevantes[:MAX_SELECIONADAS]]
    print(f"\nCuradoria por palavras-chave: {len(curadas)} de {len(noticias)} notícias selecionadas.")
    return curadas if curadas else noticias


noticias = coletar_noticias()
print(f"\nTotal coletado: {len(noticias)} notícias")

if not noticias:
    print("Zero notícias. Preservando news.json anterior.")
    sys.exit(0)

noticias_curadas = curar_por_palavras_chave(noticias)

with open("news.json", "w", encoding="utf-8") as f:
    json.dump({
        "noticias":   noticias_curadas,
        "atualizado": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        "total":      len(noticias_curadas),
    }, f, ensure_ascii=False, indent=2)

print("Salvo: news.json")
