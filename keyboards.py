from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import json

def main_menu_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💳 Comprar CC", callback_data="cat_2"))
    markup.add(
        InlineKeyboardButton("👤 Minha conta", callback_data="profile"),
        InlineKeyboardButton("💰 Adicionar saldo", callback_data="add_balance")
    )
    markup.add(
        InlineKeyboardButton("🎁 Resgatar Gift", callback_data="redeem_gift")
    )
    markup.add(
        InlineKeyboardButton("🆘 Suporte", url="https://t.me/Guiadopelo171c2b")
    )
    return markup

def categories_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    categories = db.get_categories()
    for cat_id, cat_name in categories:
        markup.add(InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_id}"))
    markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="main_menu"))
    return markup

def products_keyboard(category_id: int):
    markup = InlineKeyboardMarkup(row_width=2)
    products = db.get_products_by_category(category_id)
    buttons = []
    for product in products:
        prod_id, prod_name, prod_price = product[0], product[1], product[2]
        buttons.append(InlineKeyboardButton(f"{prod_name} - R$ {prod_price:.2f}", callback_data=f"prod_{prod_id}"))
    
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="shop"))
    return markup

def product_detail_keyboard(product_id: int, user_id: int):
    markup = InlineKeyboardMarkup(row_width=1)
    
    product = db.get_product(product_id)
    user = db.get_user(user_id)
    
    if product and user:
        price = product[4]
        balance = user[2]
        if balance >= price:
            markup.add(InlineKeyboardButton(f"💰 Pagar com Saldo (R$ {price:.2f})", callback_data=f"paybal_{product_id}"))
    
    markup.add(
        InlineKeyboardButton("⚡ Gerar Pix (Copia e Cola)", callback_data=f"buy_{product_id}"),
        InlineKeyboardButton("🔙 Voltar", callback_data="shop")
    )
    return markup

def profile_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📜 Histórico", callback_data="history"),
        InlineKeyboardButton("👥 Afiliados", callback_data="affiliates")
    )
    markup.add(
        InlineKeyboardButton("🔔 Notificações", callback_data="toggle_notifs")
    )
    markup.add(InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="main_menu"))
    return markup

def check_payment_keyboard(transaction_id: str, product_id: int):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔄 Verificar Pagamento", callback_data=f"check_{transaction_id}_{product_id}"))
    markup.add(InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="main_menu"))
    return markup

def check_deposit_keyboard(transaction_id: str, amount: float):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔄 Verificar Depósito", callback_data=f"checkdep_{transaction_id}_{amount}"))
    markup.add(InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="main_menu"))
    return markup

def admin_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ Adicionar Estoque", callback_data="adm_add_stock"),
        InlineKeyboardButton("📦 Gerenciar Produtos", callback_data="adm_manage_products"),
        InlineKeyboardButton("🎁 Criar Gift Card", callback_data="adm_create_gift"),
        InlineKeyboardButton("📝 Editar Boas-vindas", callback_data="adm_edit_welcome"),
        InlineKeyboardButton("🔙 Sair do Painel", callback_data="main_menu")
    )
    return markup

def back_to_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="main_menu"))
    return markup

def support_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("👑 Falar com o Dono", url="https://t.me/Guiadopelo171c2b"))
    markup.add(InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="main_menu"))
    return markup

def admin_manage_categories_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    categories = db.get_categories()
    for cat_id, cat_name in categories:
        markup.add(InlineKeyboardButton(cat_name, callback_data=f"adm_mcat_{cat_id}"))
    markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="adm_panel"))
    return markup

def admin_manage_products_keyboard(category_id: int):
    markup = InlineKeyboardMarkup(row_width=1)
    products = db.get_products_by_category(category_id)
    for prod_id, prod_name, _, stock_data in products:
        try:
            stock = json.loads(stock_data)
            count = len(stock) if isinstance(stock, list) else 0
        except:
            count = 0
        markup.add(InlineKeyboardButton(f"{prod_name} ({count} em estoque)", callback_data=f"adm_mprod_{prod_id}"))
    markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="adm_manage_products"))
    return markup

def admin_product_edit_keyboard(product_id: int):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📝 Alterar Descrição", callback_data=f"adm_edit_desc_{product_id}"),
        InlineKeyboardButton("💵 Alterar Preço", callback_data=f"adm_edit_price_{product_id}"),
        InlineKeyboardButton("🗑️ Remover Produto", callback_data=f"adm_delete_prod_{product_id}"),
        InlineKeyboardButton("🔙 Voltar", callback_data="adm_manage_products")
    )
    return markup
