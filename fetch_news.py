#!/usr/bin/env python3
"""
Busca notícias jurídicas nos feeds RSS e gera news.json.
Roda via GitHub Actions todo dia útil às 9h de Brasília.
"""

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

FEEDS = [
    {"url": "https://portal.stf.jus.br/noticias/rss.asp",   "fonte": "STF",      "juridico": True},
    {"url": "https://www.conjur.com.br/rss.xml",             "fonte": "Conjur",   "juridico": True},
    {"url": "https://www.migalhas.com.br/rss/quentes",       "fonte": "Migalhas", "juridico": True},
]

PALAVRAS_PREV = [
    "previdência", "previdenciário", "previdenciária",
    "previdenciario", "previdenciaria",
    "inss", "rgps", "rpps", "regime próprio", "regime geral",
    "aposentadoria", "aposentado", "aposentados",
    "auxílio-doença", "auxilio doença", "auxílio acidente",
    "pensão por morte", "pensao por morte",
    "salário de benefício", "salário-benefício",
    "tempo de contribuição", "carência previdenciária",
    "reforma da previdência", "ec 103",
    "segurado", "contribuinte individual",
    "revisão da vida toda", "superendividamento",
    "lei 14.181", "lei 8.213", "lei 8213",
    "benefício assistencial", "bpc", "loas",
    "incapacidade laborativa", "incapacidade permanente",
    "benefício previdenciário", "beneficio previdenciario",
    "perícia médica", "pericia medica",
]

PALAVRAS_SAUDE = [
    "plano de saúde", "plano de saude",
    "planos de saúde", "planos de saude",
    "ans", "agência nacional de saúde",
    "sus", "sistema único de saúde",
    "saúde suplementar", "saude suplementar",
    "cobertura médica", "cobertura hospitalar",
    "internação", "internacao", "cirurgia",
    "tratamento médico", "tratamento de saúde",
    "rol de procedimentos", "reajuste de plano",
    "lei 9.656", "lei 9656",
    "medicamento", "oncologia", "quimioterapia",
    "operadora de saúde", "operadora de plano",
    "saúde mental", "psicoterapia",
]

PALAVRAS_JURIDICO = [
    "stf", "stj", "trf", "tjpa", "tribunal", "ministério público",
    "advocacia", "advogado", "jurídico", "juridico",
    "decisão", "decisao", "acórdão", "acordao", "sentença", "sentenca",
    "processo", "ação", "acao", "recurso", "apelação", "apelacao",
    "lei ", "decreto", "portaria", "resolução", "resolucao",
    "direito", "código", "codigo", "constituição", "constituicao",
    "contrato", "responsabilidade civil", "dano moral",
    "trabalhista", "clt", "trabalho", "empregado", "empregador",
    "consumidor", "procon", "lgpd", "dado pessoal",
    "licitação", "licitacao", "concurso", "servidor público",
    "imposto", "tributo", "fiscal", "receita federal",
    "habeas corpus", "mandado", "injunção", "liminar",
]


def limpar_html(texto):
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    for ent, rep in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                     ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
        texto = texto.replace(ent, rep)
    return re.sub(r"\s+", " ", texto).strip()


def classificar(titulo, desc):
    texto = (titulo + " " + desc).lower()
    if any(p in texto for p in PALAVRAS_PREV):
        return "previdenciario"
    if any(p in texto for p in PALAVRAS_SAUDE):
        return "saude"
    return "geral"


def eh_relevante(titulo, desc, fonte_juridica):
    """Inclui o item se vier de fonte jurídica ou tiver termos jurídicos."""
    if fonte_juridica:
        return True
    texto = (titulo + " " + desc).lower()
    return any(p in texto for p in PALAVRAS_JURIDICO + PALAVRAS_PREV + PALAVRAS_SAUDE)


def detectar_tag(titulo, fonte):
    t = titulo.lower()
    if "stf" in t or fonte == "STF":   return "STF"
    if "stj" in t:                      return "STJ"
    if "inss" in t:                     return "INSS"
    if " ans " in t or "agência nacional de saúde" in t: return "ANS"
    if "trf" in t or "tribunal regional" in t:           return "TRF"
    if "portaria" in t or "instrução normativa" in t:    return "Normativa"
    if "lei " in t or "decreto" in t:                    return "Legislação"
    if "súmula" in t or "acórdão" in t:                  return "Jurisprudência"
    if "trabalhista" in t or "clt" in t:                 return "Trabalhista"
    if "tributário" in t or "fiscal" in t:               return "Tributário"
    return fonte


def buscar_feed(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parsear_feed(feed_cfg):
    print(f"  Buscando {feed_cfg['fonte']}...")
    try:
        xml_bytes = buscar_feed(feed_cfg["url"])
    except Exception as e:
        print(f"  ERRO: {feed_cfg['fonte']}: {e}")
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  ERRO XML: {feed_cfg['fonte']}: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    itens = root.findall(".//item") or root.findall(".//atom:entry", ns)

    resultado = []
    for item in itens:
        def txt(tag):
            el = item.find(tag) or item.find(f"atom:{tag}", ns)
            return (el.text or "").strip() if el is not None else ""

        titulo = limpar_html(txt("title"))
        link   = txt("link") or txt("guid")
        desc   = limpar_html(txt("description") or txt("summary") or txt("content"))
        pub    = txt("pubDate") or txt("published") or txt("updated")

        if not titulo:
            continue

        # Inclui todos os itens de fontes jurídicas, ou com termos relevantes
        if not eh_relevante(titulo, desc, feed_cfg["juridico"]):
            continue

        try:
            dt = parsedate_to_datetime(pub)
        except Exception:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now()

        area = classificar(titulo, desc)

        resultado.append({
            "id":      f"{feed_cfg['fonte']}_{(link or titulo)}"[:120],
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

    por_area = {}
    for n in resultado:
        por_area[n["area"]] = por_area.get(n["area"], 0) + 1
    print(f"  {feed_cfg['fonte']}: {len(resultado)} itens — {por_area}")
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
