import os
import json
import threading
import logging
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# -------------------------------------------------------------------
# CONFIGURAÇÃO DE SEGURANÇA E LOGS
# -------------------------------------------------------------------
TOKEN = os.getenv('TELEGRAM_TOKEN', '')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# -------------------------------------------------------------------
# CARREGAMENTO DO LIVRO A PARTIR DO JSON EXTERNO
# -------------------------------------------------------------------
def carregar_historia():
    try:
        with open('historia.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar o arquivo historia.json: {e}")
        return {}

HISTORIA = carregar_historia()

# -------------------------------------------------------------------
# SERVIDOR WEB FALSO PARA RENDER
# -------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot da Cidadela do Caos esta rodando!")

def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# -------------------------------------------------------------------
# ESTADO DOS JOGADORES E CONFIGURAÇÕES
# -------------------------------------------------------------------
jogadores = {}

LISTA_MAGIAS = [
    "🔥 Fogo", "🌀 Ilusão", "🕊️ Levitação", "🛡️ Escudo",
    "👥 Cópia de Criatura", "✨ Cura", "👁️ Adivinhação", "💪 Força",
    "⚡ Fraqueza", "🔇 Silêncio", "🧠 Telecinesia", "🙈 Cegueira"
]

TECLADO_PERMANENTE = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 Status"), KeyboardButton("🎒 Inventário")],
        [KeyboardButton("🪄 Grimório"), KeyboardButton("📜 História & Regras")]
    ],
    resize_keyboard=True
)

TEXTO_INTRODUCAO = (
    "📖 *A CIDADELA DO CAOS — INTRODUÇÃO*\n\n"
    "Nas profundezas da insalubre *Floresta dos Desesperados*, ergue-se uma fortress aterradora: "
    "a **Cidadela do Caos**. Dali, o tirano e feiticeiro **Balthus Dire** orquestra a conquista do pacífico Vale dos Vales.\n\n"
    "Como o mais talentoso discípulo da **Grande Ordem dos Magos**, uma missão solitária foi confiada a você: "
    "infiltrar-se na Cidadela do Caos, superar seus servos e armadilhas místicas, e **destruir Balthus Dire**!\n\n"
    "Sua jornada começa agora. Clique abaixo para gerar seu personagem!"
)

# -------------------------------------------------------------------
# HELPER DA INTERFACE DE SELEÇÃO DE MAGIAS
# -------------------------------------------------------------------
def gerar_menu_magias(p):
    keyboard = []
    for magia in LISTA_MAGIAS:
        qtd = p['magias'].count(magia)
        row = [
            InlineKeyboardButton("➖", callback_data=f"remove_magia:{magia}"),
            InlineKeyboardButton(f"{magia} ({qtd})", callback_data=f"info_magia:{magia}"),
            InlineKeyboardButton("➕", callback_data=f"add_magia:{magia}")
        ]
        keyboard.append(row)

    acoes = []
    if len(p['magias']) > 0:
        acoes.append(InlineKeyboardButton("🗑️ Limpar Grimório", callback_data="limpar_magias"))
    
    acoes.append(InlineKeyboardButton("🚀 Iniciar Aventura!", callback_data="node:1"))
    keyboard.append(acoes)

    pontos_restantes = p['magia_max'] - len(p['magias'])
    
    texto = (
        f"🪄 *GRIMÓRIO DE MAGIAS*\n\n"
        f"• *Pontos Disponíveis:* `{pontos_restantes}` / `{p['magia_max']}`\n"
        f"• *Total Escolhido:* `{len(p['magias'])}` magias\n\n"
        f"_Nota: Você pode repetir a mesma magia quantas vezes desejar, desde que tenha pontos suficientes._\n\n"
        f"Ajuste a quantidade de cada feitiço usando os botões **➖** e **➕**:"
    )

    return texto, InlineKeyboardMarkup(keyboard)

# -------------------------------------------------------------------
# HANDLERS DO TELEGRAM
# -------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    jogadores[user_id] = {
        "criado": False,
        "habilidade_max": 0, "habilidade": 0,
        "energia_max": 0, "energia": 0,
        "sorte_max": 0, "sorte": 0,
        "magia_max": 0, "magia": 0,
        "magias": [],
        "inventario": ["Espada", "Lanternas", "Provisões (2 refeições)"],
        "node_atual": "intro_portoes"
    }

    keyboard = [
        [InlineKeyboardButton("🎲 Gerar Atributos do Personagem", callback_data='menu_gerar_personagem')]
    ]

    await update.message.reply_text(
        TEXTO_INTRODUCAO,
        reply_markup=TECLADO_PERMANENTE,
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "⚡ *PREPARAÇÃO DA AVENTURA*\nClique no botão abaixo para rolar seus dados iniciais:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data

    if user_id not in jogadores:
        await query.answer("Sessão expirada. Envie /start para reiniciar.")
        return

    p = jogadores[user_id]

    if data == 'menu_gerar_personagem':
        await query.answer()
        hab = random.randint(1, 6) + 6
        ene = random.randint(2, 12) + 12
        sor = random.randint(1, 6) + 6
        mag = random.randint(2, 12) + 6

        p["habilidade_max"] = p["habilidade"] = hab
        p["energia_max"] = p["energia"] = ene
        p["sorte_max"] = p["sorte"] = sor
        p["magia_max"] = p["magia"] = mag
        p["magias"].clear()

        texto_atributos = (
            "🎲 *SEUS ATRIBUTOS FORAM SORTEADOS!*\n\n"
            f"🎯 *Habilidade:* {hab}\n"
            f"❤️ *Energia:* {ene}\n"
            f"🍀 *Sorte:* {sor}\n"
            f"🪄 *Pontos de Magia:* {mag}\n\n"
            "Agora ajuste suas magias no grimório!"
        )

        keyboard = [
            [InlineKeyboardButton("🎲 Rolar Novamente", callback_data='menu_gerar_personagem')],
            [InlineKeyboardButton("🪄 Montar Grimório", callback_data='menu_escolher_magias')]
        ]
        
        await query.edit_message_text(texto_atributos, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    if data == 'menu_escolher_magias':
        await query.answer()
        texto, markup = gerar_menu_magias(p)
        await query.edit_message_text(texto, reply_markup=markup, parse_mode='Markdown')
        return

    if data.startswith('add_magia:'):
        magia_nome = data.split(':')[1]
        if len(p['magias']) < p['magia_max']:
            p['magias'].append(magia_nome)
            await query.answer(f"➕ 1x {magia_nome}")
            texto, markup = gerar_menu_magias(p)
            try:
                await query.edit_message_text(texto, reply_markup=markup, parse_mode='Markdown')
            except Exception:
                pass
        else:
            await query.answer("⚠️ Limite de pontos de magia atingido!", show_alert=True)
        return

    if data.startswith('remove_magia:'):
        magia_nome = data.split(':')[1]
        if magia_nome in p['magias']:
            p['magias'].remove(magia_nome)
            await query.answer(f"➖ 1x {magia_nome}")
            texto, markup = gerar_menu_magias(p)
            try:
                await query.edit_message_text(texto, reply_markup=markup, parse_mode='Markdown')
            except Exception:
                pass
        else:
            await query.answer("Você não possui esta magia no grimório.")
        return

    if data.startswith('info_magia:'):
        magia_nome = data.split(':')[1]
        qtd = p['magias'].count(magia_nome)
        await query.answer(f"{magia_nome}: {qtd} unidade(s) selecionada(s).")
        return

    if data == 'limpar_magias':
        p['magias'].clear()
        await query.answer("Grimório limpo!")
        texto, markup = gerar_menu_magias(p)
        await query.edit_message_text(texto, reply_markup=markup, parse_mode='Markdown')
        return

    if data.startswith('node:'):
        await query.answer()
        p['criado'] = True
        node_id = data.split(':')[1]

        # Recarrega ou consulta a história do JSON
        historia_atual = carregar_historia()
        if node_id in historia_atual:
            p['node_atual'] = node_id
            node = historia_atual[node_id]
            
            keyboard = []
            for opt in node['opcoes']:
                keyboard.append([InlineKeyboardButton(opt['texto'], callback_data=f"node:{opt['next']}")])
            
            await query.edit_message_text(
                node['texto'],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

async def menu_permanente_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto_botao = update.message.text

    if user_id not in jogadores or not jogadores[user_id]["criado"]:
        await update.message.reply_text(
            "⚠️ Você precisa criar o seu personagem primeiro! Envie /start para iniciar.",
            reply_markup=TECLADO_PERMANENTE
        )
        return

    p = jogadores[user_id]

    if texto_botao == "📊 Status":
        msg = (
            "📊 *FICHA DE PERSONAGEM*\n\n"
            f"🎯 *Habilidade:* {p['habilidade']}/{p['habilidade_max']}\n"
            f"❤️ *Energia:* {p['energia']}/{p['energia_max']}\n"
            f"🍀 *Sorte:* {p['sorte']}/{p['sorte_max']}\n"
            f"🪄 *Pontos de Magia Restantes:* {p['magia']}/{p['magia_max']}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif texto_botao == "🎒 Inventário":
        inv_str = "\n• ".join(p['inventario'])
        msg = f"🎒 *SEU INVENTÁRIO*\n\n• {inv_str}"
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif texto_botao == "🪄 Grimório":
        if p['magias']:
            magias_unicas = set(p['magias'])
            linhas = [f"• {magia} (x{p['magias'].count(magia)})" for magia in magias_unicas]
            magias_str = "\n".join(linhas)
        else:
            magias_str = "Nenhuma magia no grimório."
            
        msg = f"🪄 *SEU GRIMÓRIO DE COMBATE*\n\n{magias_str}"
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif texto_botao == "📜 História & Regras":
        msg = (
            "📜 *REGRAS & RESUMO DA MISSÃO*\n\n"
            "• **Objetivo:** Infiltrar-se na Cidadela do Caos e derrotar Balthus Dire.\n"
            "• **Combates:** Resolvidos com base na sua Habilidade e rolagens de dados.\n"
            "• **Magias:** Podem ser usadas em momentos específicos do livro."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

# -------------------------------------------------------------------
# INICIALIZAÇÃO
# -------------------------------------------------------------------
if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_permanente_handler))
    
    print("🏰 Bot iniciado e lendo historia.json!")
    app.run_polling()
