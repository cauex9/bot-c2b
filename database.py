import sqlite3
import json
from config import DB_PATH

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            total_spent REAL DEFAULT 0.0,
            points REAL DEFAULT 0.0,
            referred_by INTEGER,
            notifications_enabled INTEGER DEFAULT 1, -- 1 for ON, 0 for OFF
            FOREIGN KEY (referred_by) REFERENCES users (user_id)
        )
    ''')

    # Create Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # Create Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock TEXT, -- JSON array of items or count
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')

    # Create Sales table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            amount REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Create Gifts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gifts (
            code TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            used_by INTEGER DEFAULT NULL,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_used TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (used_by) REFERENCES users (user_id)
        )
    ''')

    # Create Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Insert default welcome text if not exists
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('welcome_text', '💳 Bem vindo à central de vendas!\nExplore o bot pelos botões abaixo. Qualquer dúvida: @Guiadopelo171c2b.')")
    
    # Add missing columns to users table if they don't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN points REAL DEFAULT 0.0")
    except sqlite3.OperationalError: pass # Already exists
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN notifications_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError: pass

    conn.commit()
    conn.close()

def add_user(user_id: int, username: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username)
        VALUES (?, ?)
    ''', (user_id, username))
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories')
    categories = cursor.fetchall()
    conn.close()
    return categories

def get_products_by_category(category_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock FROM products WHERE category_id = ?', (category_id,))
    products = cursor.fetchall()
    conn.close()
    return products

def get_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def get_sales_history(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.name, s.amount, s.date 
        FROM sales s 
        JOIN products p ON s.product_id = p.id 
        WHERE s.user_id = ? 
        ORDER BY s.date DESC
    ''', (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history

def set_referral(user_id: int, referrer_id: int):
    if user_id == referrer_id: return
    conn = get_connection()
    cursor = conn.cursor()
    # Only set if not already referred
    cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ? AND referred_by IS NULL', (referrer_id, user_id))
    conn.commit()
    conn.close()

def add_balance(user_id: int, amount: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    
    # Check for affiliate bonus
    cursor.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0]:
        referrer_id = res[0]
        bonus = amount * 0.10
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, referrer_id))
        
    conn.commit()
    
    # Get and return new balance
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    new_balance = res[0] if res else 0.0
    conn.close()
    return new_balance

def toggle_notifications(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET notifications_enabled = 1 - notifications_enabled WHERE user_id = ?', (user_id,))
    cursor.execute('SELECT notifications_enabled FROM users WHERE user_id = ?', (user_id,))
    status = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return status

def deliver_product(user_id: int, product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get product stock
    cursor.execute('SELECT name, price, stock FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    if not product: 
        conn.close()
        return None
    
    name, price, stock_data = product
    
    try:
        # Check if stock_data is a JSON list
        stock = json.loads(stock_data)
        if isinstance(stock, list) and len(stock) > 0:
            item = stock.pop(0)
            new_stock_data = json.dumps(stock)
            
            # Update stock
            cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock_data, product_id))
            
            # Add to sales
            cursor.execute('INSERT INTO sales (user_id, product_id, amount) VALUES (?, ?, ?)', (user_id, product_id, price))
            
            # Update user total_spent
            cursor.execute('UPDATE users SET total_spent = total_spent + ?, points = points + ? WHERE user_id = ?', 
                           (price, price * 0.1, user_id)) # 10% points
            
            conn.commit()
            conn.close()
            return item
    except Exception as e:
        import logging
        logging.error(f"Delivery error: {e}")
    
    conn.close()
    return None

def buy_with_balance(user_id: int, product_id: int):
    """
    Attempts to buy a product using the user's wallet balance.
    Returns (success: bool, result: str)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get user balance
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return False, "Usuário não encontrado."
    
    balance = res[0]
    
    # Get product price
    cursor.execute('SELECT price FROM products WHERE id = ?', (product_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return False, "Produto não encontrado."
    
    price = res[0]
    
    if balance < price:
        conn.close()
        return False, "Saldo insuficiente."
    
    # Subtract balance
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (price, user_id))
    conn.commit()
    conn.close()
    
    item = deliver_product(user_id, product_id)
    if item:
        return True, item
    else:
        # Refund balance if delivery failed (e.g. out of stock)
        add_balance(user_id, price)
        return False, "Estoque vazio no momento."

def add_stock(product_id: int, new_items: list):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT stock FROM products WHERE id = ?', (product_id,))
    res = cursor.fetchone()
    if res:
        try:
            current_stock = json.loads(res[0])
            if not isinstance(current_stock, list): current_stock = []
        except:
            current_stock = []
        
        current_stock.extend(new_items)
        cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (json.dumps(current_stock), product_id))
        conn.commit()
    conn.close()

def update_product_details(product_id: int, description: str = None, price: float = None):
    conn = get_connection()
    cursor = conn.cursor()
    if description is not None:
        cursor.execute('UPDATE products SET description = ? WHERE id = ?', (description, product_id))
    if price is not None:
        cursor.execute('UPDATE products SET price = ? WHERE id = ?', (price, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()

def create_gift(code: str, amount: float):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO gifts (code, amount) VALUES (?, ?)', (code, amount))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def redeem_gift(user_id: int, code: str):
    """
    Attempts to redeem a gift code.
    Returns (success: bool, message: str, amount: float)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if gift exists and is not used
    cursor.execute('SELECT amount, used_by FROM gifts WHERE code = ?', (code,))
    res = cursor.fetchone()
    
    if not res:
        conn.close()
        return False, "Gift card não encontrado.", 0.0
    
    amount, used_by = res
    if used_by is not None:
        conn.close()
        return False, "Este gift card já foi resgatado.", 0.0
    
    # Mark as used and update user balance
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        cursor.execute('UPDATE gifts SET used_by = ?, date_used = ? WHERE code = ?', (user_id, now, code))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        return True, f"Sucesso! R$ {amount:.2f} foram adicionados ao seu saldo.", amount
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao resgatar: {e}", 0.0
    finally:
        conn.close()

def get_setting(key: str, default: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else default

def update_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
