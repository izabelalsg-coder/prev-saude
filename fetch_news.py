#!/usr/bin/env python3
"""
Busca notícias jurídicas nos feeds RSS e gera news.json
Roda via GitHub Actions todo dia útil às 9h de Brasília.
"""

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

FEEDS = [
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",   "fonte": "STF"},
    {"url": "https://www.conjur.com.br/rss.xml",             "fonte": "Conjur"},
    {"url": "https://www.migalhas.com.br/rss/quentes",       "fonte": "Migalhas"},
]

PALAVRAS_PREV = [
    "previdência", "previdenciário", "previdenciária",
    "previdenciario", "previdenciaria",
    "inss", "rgps", "rpps", "regime próprio", "regime geral",
    "aposentadoria", "aposentado", "aposentados",
    "auxílio-doença", "auxilio-doença", "auxílio doença",
    "auxílio-acidente", "pensão por morte", "pensao por morte",
    "salário de benefício", "salario de beneficio", "salário-benefício",
    "tempo de contribuição", "carência previdenciária",
    "reforma da previdência", "ec 103", "emenda constitucional 103",
    "segurado", "contribuinte individual",
    "revisão da vida toda", "revisao da vida toda",
    "superendividamento", "lei 14.181", "lei 8.213", "lei 8213",
    "benefício assistencial", "bpc", "loas",
    "incapacidade laborativa", "incapacidade permanente",
]

PALAVRAS_SAUDE = [
    "plano de saúde", "plano de saude",
    "planos de saúde", "planos de saude",
    "ans", "agência nacional de saúde", "agencia nacional de saude",
    "sus", "sistema único de saúde", "sistema unico de saude",
    "saúde suplementar", "saude suplementar",
    "cobertura médica", "cobertura hospitalar", "cobertura obrigatória",
    "internação", "internacao", "cirurgia",
    "tratamento médico", "tratamento de saúde",
    "rol de procedimentos", "reajuste de plano",
    "portabilidade de carência", "lei 9.656", "lei 9656",
    "medicamento", "oncologia", "quimioterapia",
    "plano hospitalar", "operadora de saúde",
]


def limpar_html(texto):
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = texto.replace("&lt;", "<").replace("&gt;", ">")
    texto = texto.replace("&quot;", '"').replace("&#39;", "'")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def classificar(titulo, desc):
    texto = (titulo + " " + desc).lower()
    eh_prev  = any(p in texto for p in PALAVRAS_PREV)
    eh_saude = any(p in texto for p in PALAVRAS_SAUDE)
    if eh_prev:
        return "previdenciario"
    if eh_saude:
        return "saude"
    return None


def detectar_tag(titulo, fonte):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":
        return "STF"
    if "stj" in t:
        return "STJ"
    if "inss" in t:
        return "INSS"
    if " ans " in t or "agência nacional de saúde" in t:
        return "ANS"
    if "trf" in t or "tribunal regional" in t:
        return "TRF"
    if "portaria" in t or "instrução normativa" in t or "resolução normativa" in t:
        return "Normativa"
    if "lei " in t or "decreto" in t:
        return "Legislação"
    if "súmula" in t or "acórdão" in t:
        return "Jurisprudência"
    return fonte


def buscar_feed(feed_cfg):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PrevSaudeBot/1.0)"}
    req = urllib.request.Request(feed_cfg["url"], headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        conteudo = resp.read()
    return conteudo


def parsear_feed(feed_cfg):
    print(f"  Buscando {feed_cfg['fonte']}...")
    try:
        xml_bytes = buscar_feed(feed_cfg)
    except Exception as e:
        print(f"  ERRO ao buscar {feed_cfg['fonte']}: {e}")
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  ERRO ao parsear XML de {feed_cfg['fonte']}: {e}")
        return []

    # Suporte a RSS 2.0 e Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    itens = root.findall(".//item") or root.findall(".//atom:entry", ns)

    resultado = []
    for item in itens:
        def txt(tag):
            el = item.find(tag) or item.find(f"atom:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        titulo  = limpar_html(txt("title"))
        link    = txt("link") or txt("guid")
        desc    = limpar_html(txt("description") or txt("summary") or txt("content"))
        pub_raw = txt("pubDate") or txt("published") or txt("updated")

        if not titulo:
            continue

        area = classificar(titulo, desc)
        if not area:
            continue

        # Parse de data
        try:
            dt = parsedate_to_datetime(pub_raw)
        except Exception:
            try:
                dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now()

        resultado.append({
            "id":      f"{feed_cfg['fonte']}_{link or titulo}"[:120],
            "area":    area,
            "tag":     detectar_tag(titulo, feed_cfg["fonte"]),
            "titulo":  titulo[:120],
            "fonte":   feed_cfg["fonte"],
            "resumo":  desc[:280] if desc else "",
            "link":    link,
            "data":    dt.strftime("%d/%m/%Y"),
            "hora":    dt.strftime("%H:%M"),
            "ts":      int(dt.timestamp() * 1000),
            "favorito": False,
        })

    print(f"  {feed_cfg['fonte']}: {len(resultado)} notícias relevantes")
    return resultado


def main():
    print("=== Prev & Saúde — Atualização de Notícias ===")
    todas = []
    for feed in FEEDS:
        todas.extend(parsear_feed(feed))

    # Remove duplicatas por link
    vistos = set()
    unicas = []
    for n in todas:
        chave = n["link"] or n["titulo"]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(n)

    # Ordena por mais recente
    unicas.sort(key=lambda x: x["ts"], reverse=True)

    agora = datetime.now()
    saida = {
        "noticias":   unicas,
        "atualizado": agora.strftime("%d/%m/%Y às %H:%M"),
        "total":      len(unicas),
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"\nTotal: {len(unicas)} notícias salvas em news.json")
    print(f"Atualizado em: {saida['atualizado']}")


if __name__ == "__main__":
    main()
