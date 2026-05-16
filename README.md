# Prev & Saúde — Atualização Jurídica Diária

Aplicativo de atualização diária em **Direito Previdenciário** e **Direito da Saúde**, desenvolvido para uso da advogada Izabela Gonçalves Advocacia.

---

## Arquivos do projeto

| Arquivo | Descrição |
|---|---|
| `index.html` | Aplicativo completo (HTML + CSS + JS) |
| `manifest.json` | Configuração para instalação como app (PWA) |
| `sw.js` | Service Worker para funcionamento offline |
| `icon-192.png` | Ícone do app (192×192 px) — adicionar manualmente |
| `icon-512.png` | Ícone do app (512×512 px) — adicionar manualmente |

---

## Como publicar no GitHub Pages

### Passo 1 — Criar o repositório

1. Acesse [github.com](https://github.com) e faça login
2. Clique em **New repository**
3. Nomeie como `prev-saude` (ou outro nome de sua preferência)
4. Marque como **Public**
5. Clique em **Create repository**

### Passo 2 — Fazer upload dos arquivos

1. Na página do repositório, clique em **Add file → Upload files**
2. Arraste os arquivos `index.html`, `manifest.json` e `sw.js`
3. Adicione uma mensagem como "Primeiro envio" e clique em **Commit changes**

### Passo 3 — Ativar o GitHub Pages

1. Vá em **Settings** (engrenagem no topo do repositório)
2. No menu lateral, clique em **Pages**
3. Em **Source**, selecione **Deploy from a branch**
4. Em **Branch**, selecione **main** e a pasta **/ (root)**
5. Clique em **Save**

Após alguns minutos, o app estará disponível em:

```
https://SEU_USUARIO.github.io/prev-saude/
```

---

## Como instalar como app no celular (Android/Chrome)

1. Abra o endereço acima no Chrome
2. Toque nos três pontos no canto superior direito
3. Selecione **Adicionar à tela inicial** ou **Instalar aplicativo**
4. Confirme a instalação

O app abrirá como uma janela independente, sem barra de endereço.

---

## Como instalar como app no computador (Chrome)

1. Abra o endereço no Chrome
2. Clique no ícone de instalação (&#x2913;) na barra de endereços
3. Clique em **Instalar**

---

## Ícones do aplicativo

Para que o ícone apareça corretamente na tela inicial, adicione dois arquivos de imagem ao repositório:

- `icon-192.png` — 192×192 pixels
- `icon-512.png` — 512×512 pixels

Você pode criar ícones gratuitamente em [favicon.io](https://favicon.io) ou usar qualquer imagem redimensionada para essas dimensões.

---

## Fontes de notícias utilizadas

As notícias são buscadas diretamente dos feeds RSS públicos e gratuitos de:

- **STF** — Supremo Tribunal Federal
- **Conjur** — Consultor Jurídico
- **Migalhas**

A filtragem por área (Previdenciário ou Saúde) é feita automaticamente por correspondência de palavras-chave jurídicas no título e na descrição de cada notícia.

---

## Dados salvos localmente

Todos os dados pessoais (favoritos e banco de legislação) ficam armazenados **apenas no seu navegador**, sem envio a nenhum servidor externo.

---

*Izabela Gonçalves Advocacia — OAB/PA nº 20.541*
