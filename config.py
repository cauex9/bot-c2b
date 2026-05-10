import os
from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # Can be empty initially
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
POSEIDON_PUBLIC_KEY = os.getenv("POSEIDON_PUBLIC_KEY")
POSEIDON_SECRET_KEY = os.getenv("POSEIDON_SECRET_KEY")

ADMIN_IDS = [6835516470] # Apenas este ID tem acesso ao /adm

DB_PATH = "vending_bot.db"
