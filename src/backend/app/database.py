from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import settings
from .privacy import cpf_lookup_hash, decrypt_cpf, encrypt_cpf


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


@contextmanager
def transaction():
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize() -> None:
    with transaction() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, cpf TEXT NOT NULL UNIQUE, cpf_hash TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS products (
                id BIGINT PRIMARY KEY, category TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                emoji TEXT NOT NULL, tag TEXT, tone TEXT NOT NULL,
                customizable BOOLEAN NOT NULL DEFAULT FALSE, active BOOLEAN NOT NULL DEFAULT TRUE
            );
            CREATE TABLE IF NOT EXISTS orders (
                id BIGSERIAL PRIMARY KEY, customer_id BIGINT NOT NULL REFERENCES customers(id),
                number INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending_payment',
                total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id BIGINT NOT NULL REFERENCES products(id), product_name TEXT NOT NULL,
                unit_price_cents INTEGER NOT NULL, quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 99),
                size TEXT, meat_point TEXT
            );
            CREATE TABLE IF NOT EXISTS payments (
                id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL UNIQUE REFERENCES orders(id),
                method TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting', pix_code TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, paid_at TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS auth_tokens (token_hash TEXT PRIMARY KEY, expires_at BIGINT NOT NULL);
        """)
        db.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS cpf_hash TEXT")
        customers = db.execute("SELECT id, cpf, cpf_hash FROM customers").fetchall()
        for customer in customers:
            if customer["cpf_hash"]:
                continue
            stored_cpf = customer["cpf"]
            plain_cpf = stored_cpf if stored_cpf.isdigit() and len(stored_cpf) == 11 else decrypt_cpf(stored_cpf)
            db.execute(
                "UPDATE customers SET cpf = %s, cpf_hash = %s WHERE id = %s",
                (encrypt_cpf(plain_cpf), cpf_lookup_hash(plain_cpf), customer["id"]),
            )
        db.execute("ALTER TABLE customers ALTER COLUMN cpf_hash SET NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS customers_cpf_hash_key ON customers (cpf_hash)")
        products = [
            (1,'combos','Combo Smash','Smash bacon, fritas crocantes e refrigerante',3290,'🍔','Mais pedido','orange',True),
            (2,'combos','Combo Duplo','Burger duplo, fritas médias e refrigerante',3890,'🍔',None,'red',True),
            (3,'combos','Combo Chicken','Chicken crispy, fritas e refrigerante',3450,'🍗','Novidade','yellow',True),
            (4,'burger','Classic Burger','Carne 120g, queijo, salada e molho da casa',2290,'🍔',None,'green',True),
            (5,'burger','Bacon Melt','Carne 150g, bacon, cheddar e cebola crispy',2890,'🥓','Favorito','red',True),
            (6,'burger','Veggie Fresh','Burger vegetal, queijo, rúcula e tomate',2590,'🥬',None,'green',True),
            (7,'fries','Fritas da Casa','Sequinhas, crocantes e com sal na medida',1190,'🍟',None,'yellow',True),
            (8,'fries','Fritas Cheddar','Fritas com cheddar cremoso e bacon',1790,'🍟',None,'orange',True),
            (9,'drinks','Refrigerante','Escolha o seu sabor favorito',890,'🥤',None,'red',True),
            (10,'drinks','Limonada Fresh','Limão fresco, gelo e hortelã',1090,'🍋',None,'green',False),
            (11,'sweets','Shake de Chocolate','Cremoso, gelado e irresistível',1590,'🥤',None,'brown',False),
            (12,'sweets','Sundae Caramelo','Sorvete de baunilha com calda de caramelo',1090,'🍦',None,'blue',False),
        ]
        with db.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO products (id,category,name,description,price_cents,emoji,tag,tone,customizable) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                products,
            )
