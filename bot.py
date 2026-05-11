import telebot
import logging
import config
import os
import uuid
import database as db
import keyboards as kb
import payment as pay
import requests
import time
from flask import Flask, request
from threading import Thread

# Flask app for health checks
app = Flask('')

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        logging.info(f"POST request received on root: {request.data}")
        return "Webhook on root? Use /webhook/poseidon", 200
    return "Bot is running!", 200

@app.route('/webhook/poseidon/', methods=['GET', 'POST'])
@app.route('/webhook/poseidon', methods=['GET', 'POST'])
def poseidon_webhook():
    try:
        logging.info(f"Webhook request: {request.method} {request.path}")
        if request.method == 'GET':
            return "Webhook active. Send a POST request with transaction data.", 200
            
        data = request.json
        logging.info(f"Webhook received from PoseidonPay: {data}")
        
        if not data:
            # Try to get data from form if json is empty
            data = request.form.to_dict()
            if not data:
                logging.warning("No data found in webhook request body.")
                return "No data", 400
            
        status = str(data.get('status', '')).upper()
        identifier = data.get('identifier', '')
        
        # Log specifically what we found
        logging.info(f"Processing webhook: status={status}, identifier={identifier}")
        
        if status in ['OK', 'PAID', 'SUCCESS', 'APPROVED', 'CONCLUIDO', 'FINALIZADO', 'COMPLETED']:
            # Caso seja Depósito de Saldo
            if identifier.startswith('dep_'):
                # Formato: dep_userId_random
                parts = identifier.split('_')
                if len(parts) >= 2:
                    user_id = int(parts[1])
                    amount = float(data.get('amount', 0))
                    
                    new_balance = db.add_balance(user_id, amount)
                    
                    text = (
                        "🚀 <b>Depósito Confirmado Automaticamente!</b>\n\n"
                        f"💰 <b>Saldo adicionado:</b> R$ {amount:.2f}\n"
                        f"🏛 <b>Saldo atual:</b> R$ {new_balance:.2f}"
                    )
                    bot.send_message(user_id, text, reply_markup=kb.main_menu_keyboard())
            
            # Caso seja Compra Direta de Produto
            elif identifier.startswith('buy_'):
                # Formato: buy_userId_productId_random
                parts = identifier.split('_')
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    product_id = int(parts[2])
                    
                    # Mensagens de carregamento solicitadas pelo usuário
                    # Nota: No webhook não usamos edit_message pois é uma mensagem nova ou disparada por evento externo
                    # Mas para manter a experiência, podemos enviar a mensagem de carregamento antes do produto
                    load_msg = bot.send_message(user_id, "🔍 <b>Buscando cartões...</b>")
                    time.sleep(1.5)
                    bot.edit_message_text("🔍 <b>Buscando cartões...</b>\n\n⌛ <b>Aguarde, consultando estoque...</b>", 
                                          chat_id=user_id, message_id=load_msg.message_id)
                    time.sleep(1.5)
                    
                    item = db.deliver_product(user_id, product_id)
                    if item:
                        user = db.get_user(user_id)
                        new_balance = user[2] if user else 0.0
                        text = (
                            "🎉 <b>Pagamento Confirmado Automaticamente!</b>\n\n"
                            "Aqui está o seu produto:\n"
                            f"<code>{item}</code>\n\n"
                            f"💰 <b>Saldo Atual:</b> R$ {new_balance:.2f}\n\n"
                            "Obrigado pela compra! 💎"
                        )
                        bot.edit_message_text(text, chat_id=user_id, message_id=load_msg.message_id, reply_markup=kb.main_menu_keyboard())
        
        return "OK", 200
    except Exception as e:
        logging.error(f"Error in webhook handler: {e}")
        return "Error", 500

def run():
    # Render uses the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def self_ping():
    # URL do seu bot no Render
    url = "https://bot-vendar-11.onrender.com/"
    while True:
        try:
            # Espera 5 minutos (300 segundos)
            time.sleep(300)
            response = requests.get(url)
            logging.info(f"Self-ping status: {response.status_code}")
        except Exception as e:
            logging.error(f"Self-ping failed: {e}")

def keep_alive():
    t_flask = Thread(target=run)
    t_flask.start()
    
    t_ping = Thread(target=self_ping)
    t_ping.daemon = True # Garante que a thread morra se o processo principal parar
    t_ping.start()

logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode='HTML')


PHOTO_PATH = "foto/menu.jpg"

def edit_message(call, text, reply_markup):
    try:
        if call.message.content_type == 'photo':
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                     caption=text, reply_markup=reply_markup)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Error editing message: {e}")
        # Fallback: if edit fails (e.g. message not modified), send a new message
        try:
            bot.send_message(call.message.chat.id, text, reply_markup=reply_markup)
        except: pass

def get_welcome_text(user_id):
    user = db.get_user(user_id)
    balance = 0.0
    points = 0.0
    if user:
        balance = user[2]
        points = user[4] if len(user) > 4 else 0.0
    
    points_value = points * 0.5
    
    # Busca o texto configurável do banco de dados
    custom_text = db.get_setting('welcome_text', '💳 Bem vindo à central de vendas!')
    
    text = (
        f"{custom_text}\n\n"
        "🏛 <b>Sua Carteira:</b>\n"
        f"┣ 🆔 Seu ID: <code>{user_id}</code>\n"
        f"┣ 💰 Saldo: <b>R$ {balance:.2f}</b>\n"
        f"┗ 💎 Pontos: {points:.2f} (~R${points_value:.2f})"
    )
    return text

user_checkout = {}

@bot.message_handler(commands=['start'])
def command_start(message):
    db.add_user(message.from_user.id, message.from_user.username)
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            db.set_referral(message.from_user.id, referrer_id)
        except ValueError:
            pass
            
    welcome_text = get_welcome_text(message.from_user.id)
    
    if os.path.exists(PHOTO_PATH):
        with open(PHOTO_PATH, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=welcome_text, reply_markup=kb.main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, welcome_text, reply_markup=kb.main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def callback_main_menu(call):
    bot.answer_callback_query(call.id)
    text = get_welcome_text(call.from_user.id)
    edit_message(call, text, kb.main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "shop")
def callback_shop(call):
    bot.answer_callback_query(call.id)
    user = db.get_user(call.from_user.id)
    balance = user[2] if user else 0.0
    text = f"🛒 <b>Loja</b>\n💰 Seu Saldo: <b>R$ {balance:.2f}</b>\n\nEscolha uma categoria:"
    edit_message(call, text, kb.categories_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def callback_category(call):
    bot.answer_callback_query(call.id)
    category_id = int(call.data.split("_")[1])
    user = db.get_user(call.from_user.id)
    balance = user[2] if user else 0.0
    text = f"📦 <b>Produtos</b>\n💰 Seu Saldo: <b>R$ {balance:.2f}</b>\n\nSelecione o produto desejado:"
    edit_message(call, text, kb.products_keyboard(category_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("prod_"))
def callback_product(call):
    bot.answer_callback_query(call.id)
    product_id = int(call.data.split("_")[1])
    product = db.get_product(product_id)
    
    if not product:
        bot.answer_callback_query(call.id, "Produto não encontrado!", show_alert=True)
        return
        
    _, category_id, name, description, price, stock_data = product
    
    # Verificação de estoque vazio
    import json
    try:
        stock_list = json.loads(stock_data) if stock_data else []
        if not stock_list or len(stock_list) == 0:
            if category_id == 2: # Categoria de CC
                bot.answer_callback_query(call.id, "❌ Não temos cartões live neste nível de cc, aguarde o Reabastecido dessa categoria", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ Este produto está esgotado no momento.", show_alert=True)
            return
    except Exception as e:
        logging.error(f"Error checking stock in callback_product: {e}")
    
    user = db.get_user(call.from_user.id)
    balance = user[2] if user else 0.0
        
    text = (
        f"📦 <b>Produto:</b> {name}\n\n"
        f"📝 <b>Descrição:</b>\n{description}\n\n"
        f"💵 <b>Preço:</b> R$ {price:.2f}\n"
        f"💰 <b>Seu Saldo:</b> R$ {balance:.2f}"
    )
    edit_message(call, text, kb.product_detail_keyboard(product_id, call.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data == "profile")
def callback_profile(call):
    bot.answer_callback_query(call.id)
    user = db.get_user(call.from_user.id)
    if user:
        # (user_id, username, balance, total_spent, points)
        balance = user[2]
        total_spent = user[3]
        points = user[4] if len(user) > 4 else 0.0
        text = (
            f"👤 <b>Seu Perfil</b>\n\n"
            f"🆔 <b>ID:</b> <code>{call.from_user.id}</code>\n"
            f"💰 <b>Saldo:</b> R$ {balance:.2f}\n"
            f"🛍 <b>Total Gasto:</b> R$ {total_spent:.2f}\n"
            f"💎 <b>Pontos:</b> {points:.2f}"
        )
        edit_message(call, text, kb.profile_keyboard())
    else:
        bot.answer_callback_query(call.id, "Erro ao carregar perfil.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "cc")
def callback_cc(call):
    text = (
        "💳 <b>Comprar CC</b>\n\n"
        "<i>(A funcionalidade de geração de PIX dinâmico está em desenvolvimento no módulo de pagamento)</i>\n"
        "Em breve você poderá gerar seu QR Code aqui."
    )
    edit_message(call, text, kb.back_to_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "support")
def callback_support(call):
    text = "🆘 <b>Suporte</b>\n\nPara dúvidas ou problemas, contate o administrador: <a href='https://t.me/Guiadopelo171c2b'>@Guiadopelo171c2b</a>"
    edit_message(call, text, kb.support_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "add_balance")
def callback_add_balance(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💰 <b>Adicionar Saldo</b>\n\nQual valor você deseja adicionar?\n\nMínimo: <b>R$ 15,00</b>\n\nDigite apenas o número (Ex: 25):")
    bot.register_next_step_handler(msg, process_add_balance_amount)

@bot.callback_query_handler(func=lambda call: call.data == "redeem_gift")
def callback_redeem_gift(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🎁 <b>Resgatar Gift Card</b>\n\nEnvie o código do seu Gift Card abaixo:")
    bot.register_next_step_handler(msg, process_redeem_gift)

def process_redeem_gift(message):
    code = message.text.strip()
    if not code:
        bot.send_message(message.chat.id, "❌ Código inválido.")
        return
        
    success, result_msg, amount = db.redeem_gift(message.from_user.id, code)
    
    if success:
        bot.send_message(message.chat.id, f"✅ {result_msg}", reply_markup=kb.main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, f"❌ {result_msg}", reply_markup=kb.main_menu_keyboard())

def process_add_balance_amount(message):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < 15.0:
            bot.send_message(message.chat.id, "❌ O valor mínimo de depósito é <b>R$ 15,00</b>. Tente novamente.")
            return
        
        user_id = message.from_user.id
        client_data = {
            'name': message.from_user.full_name or message.from_user.first_name,
            'email': f"user{user_id}@telegram.com", # Default email for balance top-up
            'document': "12345678909" # Placeholder document
        }
        
        identifier = f"dep_{user_id}_{str(uuid.uuid4())[:6]}"
        bot.send_message(message.chat.id, "⏳ Gerando seu Pix para depósito... Aguarde.")
        
        user = db.get_user(user_id)
        current_balance = user[2] if user else 0.0
        
        pix_data = pay.generate_pix(amount, client_data, identifier)
        
        if pix_data:
            text = (
                f"✅ <b>Pix de Depósito Gerado!</b>\n\n"
                f"💵 <b>Valor a Adicionar:</b> R$ {amount:.2f}\n"
                f"💰 <b>Saldo Atual:</b> R$ {current_balance:.2f}\n\n"
                f"📱 <b>Copia e Cola:</b>\n<code>{pix_data['pix_code']}</code>\n\n"
                f"💡 <i>Seu saldo será creditado assim que o pagamento for confirmado.</i>"
            )
            # We use a different callback prefix for deposits: checkdep_
            bot.send_message(message.chat.id, text, reply_markup=kb.check_deposit_keyboard(pix_data['transaction_id'], amount))
        else:
            bot.send_message(message.chat.id, "❌ Erro ao gerar Pix. Verifique suas chaves.")
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Valor inválido. Digite apenas números.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("paybal_"))
def callback_pay_balance(call):
    product_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id, "Processando pagamento...")
    
    # Mensagens de carregamento solicitadas pelo usuário
    loading_text1 = "🔍 <b>Buscando cartões...</b>"
    loading_text2 = "🔍 <b>Buscando cartões...</b>\n\n⌛ <b>Aguarde, consultando estoque...</b>"
    
    edit_message(call, loading_text1, None)
    time.sleep(1.5)
    edit_message(call, loading_text2, None)
    time.sleep(1.5)
    
    success, result = db.buy_with_balance(call.from_user.id, product_id)
    
    if success:
        user = db.get_user(call.from_user.id)
        new_balance = user[2] if user else 0.0
        text = (
            "🎉 <b>Pagamento com Saldo Confirmado!</b>\n\n"
            "Aqui está o seu produto:\n"
            f"<code>{result}</code>\n\n"
            f"💰 <b>Saldo Restante:</b> R$ {new_balance:.2f}\n\n"
            "Obrigado pela compra! 💎"
        )
        edit_message(call, text, kb.main_menu_keyboard())
    else:
        # Mensagem específica para CC se o erro for estoque vazio
        error_msg = result
        if "estoque" in result.lower() or "vazio" in result.lower():
            product = db.get_product(product_id)
            if product and product[1] == 2:
                error_msg = "Não temos cartões live neste nível de cc, aguarde o Reabastecido dessa categoria"
        
        edit_message(call, f"❌ <b>Erro na compra:</b> {error_msg}", kb.main_menu_keyboard())
        bot.answer_callback_query(call.id, f"❌ {error_msg}", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "history")
def callback_history(call):
    bot.answer_callback_query(call.id)
    history = db.get_sales_history(call.from_user.id)
    if not history:
        text = "📜 <b>Seu Histórico</b>\n\nVocê ainda não realizou nenhuma compra."
    else:
        text = "📜 <b>Seu Histórico de Compras</b>\n\n"
        for name, amount, date in history:
            text += f"📦 {name} - R$ {amount:.2f} ({date})\n"
    
    edit_message(call, text, kb.profile_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "affiliates")
def callback_affiliates(call):
    bot.answer_callback_query(call.id)
    bot_info = bot.get_me()
    aff_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    
    text = (
        "👥 <b>Sistema de Afiliados</b>\n\n"
        "Convide seus amigos e ganhe <b>10%</b> de comissão sobre todos os depósitos que eles realizarem!\n\n"
        f"🔗 <b>Seu Link de Afiliado:</b>\n<code>{aff_link}</code>"
    )
    edit_message(call, text, kb.profile_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "toggle_notifs")
def callback_toggle_notifs(call):
    status = db.toggle_notifications(call.from_user.id)
    text = f"🔔 <b>Notificações</b>\n\nStatus atual: {'✅ Ativadas' if status == 1 else '❌ Desativadas'}"
    bot.answer_callback_query(call.id, f"Notificações {'ativadas' if status == 1 else 'desativadas'}")
    edit_message(call, text, kb.profile_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def callback_buy(call):
    product_id = int(call.data.split("_")[1])
    product = db.get_product(product_id)
    
    if not product:
        bot.answer_callback_query(call.id, "Produto não encontrado!", show_alert=True)
        return
    
    user_id = call.from_user.id
    amount = product[4]
    product_name = product[2]
    
    # Using placeholders instead of asking user
    client_data = {
        'name': call.from_user.full_name or call.from_user.first_name,
        'email': f"user{user_id}@telegram.com",
        'document': "12345678909"
    }
    
    identifier = f"buy_{user_id}_{product_id}_{str(uuid.uuid4())[:6]}"
    
    bot.answer_callback_query(call.id, "Gerando Pix...")
    
    user = db.get_user(user_id)
    balance = user[2] if user else 0.0
    
    # Logic for paying with balance could be added here if requested, 
    # but for now we just show the balance on the Pix screen as requested.
    
    bot.send_message(call.message.chat.id, "⏳ Gerando seu Pix... Aguarde um momento.")
    
    pix_data = pay.generate_pix(amount, client_data, identifier)
    
    if pix_data:
        text = (
            f"✅ <b>Pix Gerado com Sucesso!</b>\n\n"
            f"📦 <b>Produto:</b> {product_name}\n"
            f"💵 <b>Valor:</b> R$ {amount:.2f}\n"
            f"💰 <b>Seu Saldo:</b> R$ {balance:.2f}\n\n"
            f"📱 <b>Copia e Cola:</b>\n<code>{pix_data['pix_code']}</code>\n\n"
            f"💡 <i>Após o pagamento, clique no botão abaixo para receber seu produto.</i>"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=kb.check_payment_keyboard(pix_data['transaction_id'], product_id))
    else:
        bot.send_message(call.message.chat.id, "❌ Erro ao gerar o Pix. Verifique suas chaves API.", reply_markup=kb.main_menu_keyboard())

# --- DELETED STEPS ---
    
    if user_id in user_checkout:
        del user_checkout[user_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("checkdep_"))
def callback_check_deposit(call):
    try:
        # Format: checkdep_transactionId_amount
        parts = call.data.split("_")
        amount = float(parts[-1])
        transaction_id = "_".join(parts[1:-1])
        
        bot.answer_callback_query(call.id, "Verificando depósito...")
        
        status_data = pay.check_status(transaction_id)
        logging.info(f"Deposit check for {transaction_id}: {status_data}")
        
        status = 'PENDING'
        if status_data:
            # Tenta pegar o status de diferentes formas (raiz ou dentro de 'data')
            status = status_data.get('status') or status_data.get('data', {}).get('status') or 'PENDING'
            status = str(status).upper()
        
        if status in ['OK', 'PAID', 'SUCCESS', 'APPROVED', 'CONCLUIDO', 'FINALIZADO', 'COMPLETED']:
            new_balance = db.add_balance(call.from_user.id, amount)
            text = (
                "✅ <b>Depósito recebido</b>\n\n"
                f"<b>Saldo adicionado:</b> R$ {amount:.2f}\n"
                f"<b>Saldo atual:</b> R$ {new_balance:.2f}"
            )
            edit_message(call, text, kb.main_menu_keyboard())
        else:
            bot.answer_callback_query(call.id, f"Depósito não detectado. Status: {status}", show_alert=True)
    except Exception as e:
        logging.error(f"Error in callback_check_deposit: {e}")
        bot.answer_callback_query(call.id, "❌ Erro interno ao verificar depósito.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_") and not call.data.startswith("checkdep_"))
def callback_check_payment(call):
    try:
        # Format: check_transactionId_productId
        # Usando rsplit para pegar o productId do final, caso o transactionId tenha "_"
        parts = call.data.split("_")
        product_id = int(parts[-1])
        transaction_id = "_".join(parts[1:-1])
        
        bot.answer_callback_query(call.id, "Verificando pagamento...")
        
        status_data = pay.check_status(transaction_id)
        logging.info(f"Status check for {transaction_id}: {status_data}")
        
        status = 'PENDING'
        if status_data:
            # Tenta pegar o status de diferentes formas (raiz ou dentro de 'data')
            status = status_data.get('status') or status_data.get('data', {}).get('status') or 'PENDING'
            status = str(status).upper()
        
        if status in ['OK', 'PAID', 'SUCCESS', 'APPROVED', 'CONCLUIDO', 'FINALIZADO', 'COMPLETED']:
            # Mensagens de carregamento solicitadas pelo usuário
            loading_text1 = "🔍 <b>Buscando cartões...</b>"
            loading_text2 = "🔍 <b>Buscando cartões...</b>\n\n⌛ <b>Aguarde, consultando estoque...</b>"
            
            edit_message(call, loading_text1, None)
            time.sleep(1.5)
            edit_message(call, loading_text2, None)
            time.sleep(1.5)
            
            item = db.deliver_product(call.from_user.id, product_id)
            if item:
                user = db.get_user(call.from_user.id)
                new_balance = user[2] if user else 0.0
                text = (
                    "🎉 <b>Pagamento Confirmado!</b>\n\n"
                    "Aqui está o seu produto:\n"
                    f"<code>{item}</code>\n\n"
                    f"💰 <b>Saldo Atual:</b> R$ {new_balance:.2f}\n\n"
                    "Obrigado pela compra! 💎"
                )
                edit_message(call, text, kb.main_menu_keyboard())
            else:
                # Mensagem específica para CC se o estoque estiver vazio
                product = db.get_product(product_id)
                error_msg = "Estoque vazio ou falha na entrega."
                if product and product[1] == 2:
                    error_msg = "Não temos cartões live neste nível de cc, aguarde o Reabastecido dessa categoria"
                
                edit_message(call, f"❌ <b>Erro:</b> {error_msg}", kb.main_menu_keyboard())
                bot.answer_callback_query(call.id, f"❌ {error_msg}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"Pagamento ainda não detectado. Status: {status}", show_alert=True)
    except Exception as e:
        logging.error(f"Error in callback_check_payment: {e}")
        bot.answer_callback_query(call.id, "❌ Erro interno ao verificar pagamento.", show_alert=True)

# --- ADMIN PANEL ---

@bot.message_handler(commands=['adm'])
def command_adm(message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "🛠 <b>Painel Administrativo</b>\nEscolha uma opção:", reply_markup=kb.admin_keyboard())

@bot.message_handler(commands=['saldo'])
def command_set_balance(message):
    if message.from_user.id not in config.ADMIN_IDS: return
    try:
        # Format: /saldo user_id amount
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(message, "❌ Use: /saldo [ID] [VALOR]")
            return
        
        target_id = int(args[1])
        amount = float(args[2])
        
        db.add_balance(target_id, amount)
        bot.reply_to(message, f"✅ Adicionado R$ {amount:.2f} ao saldo do usuário <code>{target_id}</code>.")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "adm_panel")
def callback_adm_panel(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    text = "🛠 <b>Painel Administrativo</b>\nEscolha uma opção:"
    edit_message(call, text, kb.admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "adm_add_stock")
def callback_adm_add_stock(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    text = "➕ <b>Adicionar Estoque</b>\nSelecione a categoria do produto:"
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup()
    for cat_id, cat_name in db.get_categories():
        markup.add(InlineKeyboardButton(cat_name, callback_data=f"admcat_{cat_id}"))
    markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="adm_panel"))
    edit_message(call, text, markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admcat_"))
def callback_adm_cat(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    cat_id = int(call.data.split("_")[1])
    text = "📦 <b>Selecione o Produto</b> para adicionar estoque:"
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup()
    products = db.get_products_by_category(cat_id)
    for product in products:
        prod_id, prod_name = product[0], product[1]
        markup.add(InlineKeyboardButton(prod_name, callback_data=f"admprod_{prod_id}"))
    markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="adm_add_stock"))
    edit_message(call, text, markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admprod_"))
def callback_adm_prod(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    prod_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📝 <b>Adicionar Estoque</b>\n\nEnvie os itens abaixo. Você pode usar várias linhas para um mesmo item.\n\n⚠️ <b>IMPORTANTE:</b> Para separar um item do outro, pule uma linha (deixe uma linha em branco).")
    bot.register_next_step_handler(msg, process_add_stock, prod_id)

def process_add_stock(message, prod_id):
    if message.from_user.id not in config.ADMIN_IDS: return
    # Agora separa por linha em branco (\n\n) para permitir itens com múltiplas linhas
    items = [item.strip() for item in message.text.split("\n\n") if item.strip()]
    if not items:
        bot.send_message(message.chat.id, "❌ Nenhum item enviado. Operação cancelada.")
        return
    
    db.add_stock(prod_id, items)
    bot.send_message(message.chat.id, f"✅ {len(items)} itens adicionados ao estoque!", reply_markup=kb.admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "adm_manage_products")
def callback_adm_manage_products(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    text = "📦 <b>Gerenciar Produtos</b>\nSelecione a categoria:"
    edit_message(call, text, kb.admin_manage_categories_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_mcat_"))
def callback_adm_mcat(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    cat_id = int(call.data.split("_")[2])
    text = "📦 <b>Selecione o Produto</b> para editar:"
    edit_message(call, text, kb.admin_manage_products_keyboard(cat_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_mprod_"))
def callback_adm_mprod(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    prod_id = int(call.data.split("_")[2])
    product = db.get_product(prod_id)
    if product:
        text = (
            f"🛠 <b>Editando:</b> {product[2]}\n\n"
            f"📝 <b>Descrição Atual:</b>\n{product[3]}\n\n"
            f"💵 <b>Preço Atual:</b> R$ {product[4]:.2f}\n\n"
            "O que você deseja alterar?"
        )
        edit_message(call, text, kb.admin_product_edit_keyboard(prod_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_edit_desc_"))
def callback_adm_edit_desc(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    prod_id = int(call.data.split("_")[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📝 <b>Nova Descrição</b>\n\nEnvie a nova descrição para este produto:")
    bot.register_next_step_handler(msg, process_update_description, prod_id)

def process_update_description(message, prod_id):
    if message.from_user.id not in config.ADMIN_IDS: return
    new_desc = message.text
    db.update_product_details(prod_id, description=new_desc)
    bot.send_message(message.chat.id, "✅ Descrição atualizada com sucesso!", reply_markup=kb.admin_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_edit_price_"))
def callback_adm_edit_price(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    prod_id = int(call.data.split("_")[3])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "💵 <b>Novo Preço</b>\n\nEnvie o novo preço (Ex: 25.50):")
    bot.register_next_step_handler(msg, process_update_price, prod_id)

def process_update_price(message, prod_id):
    if message.from_user.id not in config.ADMIN_IDS: return
    try:
        new_price = float(message.text.replace(",", "."))
        db.update_product_details(prod_id, price=new_price)
        bot.send_message(message.chat.id, f"✅ Preço atualizado para R$ {new_price:.2f}!", reply_markup=kb.admin_keyboard())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Valor inválido. Use apenas números e ponto.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_delete_prod_"))
def callback_adm_delete_prod(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    prod_id = int(call.data.split("_")[3])
    db.delete_product(prod_id)
    bot.answer_callback_query(call.id, "✅ Produto removido com sucesso!")
    # Volta para a lista de produtos
    text = "📦 <b>Gerenciar Produtos</b>\nSelecione a categoria:"
    edit_message(call, text, kb.admin_manage_categories_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "adm_create_gift")
def callback_adm_create_gift(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🎁 <b>Criar Gift Card</b>\n\nEnvie o valor e o código no formato: <code>VALOR CODIGO</code>\n(Ex: 25.50 NATAL2024)")
    bot.register_next_step_handler(msg, process_admin_create_gift)

def process_admin_create_gift(message):
    if message.from_user.id not in config.ADMIN_IDS: return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Formato inválido. Use: VALOR CODIGO")
            return
            
        amount = float(parts[0].replace(",", "."))
        code = parts[1]
        
        if db.create_gift(code, amount):
            bot.send_message(message.chat.id, f"✅ Gift Card criado com sucesso!\n\n🎫 <b>Código:</b> <code>{code}</code>\n💵 <b>Valor:</b> R$ {amount:.2f}", reply_markup=kb.admin_keyboard())
        else:
            bot.send_message(message.chat.id, "❌ Este código já existe. Tente outro.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Valor inválido. Use apenas números.")

@bot.callback_query_handler(func=lambda call: call.data == "adm_edit_welcome")
def callback_adm_edit_welcome(call):
    if call.from_user.id not in config.ADMIN_IDS: return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "📝 <b>Editar Mensagem de Boas-vindas</b>\n\nEnvie o novo texto que aparecerá no início do bot (você pode usar emojis e HTML):")
    bot.register_next_step_handler(msg, process_update_welcome)

def process_update_welcome(message):
    if message.from_user.id not in config.ADMIN_IDS: return
    new_text = message.text
    if not new_text:
        bot.send_message(message.chat.id, "❌ Mensagem vazia. Operação cancelada.")
        return
        
    db.update_setting('welcome_text', new_text)
    bot.send_message(message.chat.id, "✅ Mensagem de boas-vindas atualizada com sucesso!", reply_markup=kb.admin_keyboard())

# --- BROADCAST COMMAND ---

@bot.message_handler(commands=['avisar', 'avisa', 'broadcast'])
def command_broadcast(message):
    if message.from_user.id != 6835516470:
        bot.reply_to(message, f"❌ Seu ID (<code>{message.from_user.id}</code>) não tem permissão para usar este comando.")
        return
    
    msg = bot.send_message(message.chat.id, "📝 <b>Broadcast</b>\n\nEnvie a mensagem que você deseja transmitir para TODOS os usuários (pode conter texto, emojis e formatação HTML):")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.from_user.id != 6835516470:
        return
    
    broadcast_text = message.text
    if not broadcast_text:
        bot.send_message(message.chat.id, "❌ Mensagem vazia. Operação cancelada.")
        return
    
    users = db.get_all_users()
    bot.send_message(message.chat.id, f"🚀 Iniciando transmissão para {len(users)} usuários...")
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            bot.send_message(user_id, broadcast_text)
            success += 1
        except Exception:
            failed += 1
            
    bot.send_message(message.chat.id, f"✅ <b>Transmissão Concluída!</b>\n\n🟢 Sucesso: {success}\n🔴 Falha: {failed}")

if __name__ == "__main__":
    db.init_db()
    logging.info("Database initialized.")
    keep_alive()
    logging.info("Bot is running...")
    bot.infinity_polling()
