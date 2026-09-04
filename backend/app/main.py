import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from psycopg.errors import UniqueViolation

from .config import settings
from .database import connect, initialize, transaction
from .privacy import cpf_lookup_hash, encrypt_cpf
from .schemas import LoginIn, OrderIn, OrderStatusUpdate, PaymentIn, PaymentUpdate
from .security import authenticate, check_login_limit, clear_login_attempts, client_ip, create_token, require_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("smashgo.api")
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    yield


app = FastAPI(title="SmashGo API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    error_id = secrets.token_hex(6)
    logger.exception("unexpected_error id=%s path=%s", error_id, request.url.path, exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "Não foi possível concluir a operação.", "error_id": error_id})


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/categories")
def categories():
    return [
        {"id": "combos", "name": "Todos os combos", "emoji": "🍔"},
        {"id": "burger", "name": "Hambúrgueres", "emoji": "🍔"},
        {"id": "fries", "name": "Batata frita", "emoji": "🍟"},
        {"id": "drinks", "name": "Bebidas", "emoji": "🥤"},
        {"id": "sweets", "name": "Sobremesas", "emoji": "🍦"},
    ]


@app.get("/api/v1/products")
def products(category: str | None = Query(default=None, max_length=30)):
    sql = "SELECT * FROM products WHERE active = TRUE"
    params: tuple[object, ...] = ()
    if category:
        sql += " AND category = %s"
        params = (category,)
    sql += " ORDER BY id"
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
    return [
        {
            "id": row["id"], "category": row["category"], "name": row["name"],
            "description": row["description"], "price": row["price_cents"] / 100,
            "emoji": row["emoji"], "tag": row["tag"], "tone": row["tone"],
            "customizable": bool(row["customizable"]),
        }
        for row in rows
    ]


@app.post("/api/v1/orders", status_code=201)
def create_order(payload: OrderIn):
    with transaction() as db:
        cpf_hash = cpf_lookup_hash(payload.customer.cpf)
        customer = db.execute("SELECT id FROM customers WHERE cpf_hash = %s", (cpf_hash,)).fetchone()
        if customer:
            customer_id = customer["id"]
            db.execute("UPDATE customers SET name = %s WHERE id = %s", (payload.customer.name, customer_id))
        else:
            customer_id = db.execute(
                "INSERT INTO customers (name, cpf, cpf_hash) VALUES (%s, %s, %s) RETURNING id",
                (payload.customer.name, encrypt_cpf(payload.customer.cpf), cpf_hash),
            ).fetchone()["id"]

        product_ids = list({item.product_id for item in payload.items})
        placeholders = ",".join("%s" for _ in product_ids)
        rows = db.execute(f"SELECT * FROM products WHERE active = TRUE AND id IN ({placeholders})", tuple(product_ids)).fetchall()
        found = {row["id"]: row for row in rows}
        if len(found) != len(product_ids):
            raise HTTPException(422, "Um ou mais produtos não estão disponíveis")

        priced_items = []
        total_cents = 0
        for item in payload.items:
            product = found[item.product_id]
            if (item.size or item.meat_point) and not product["customizable"]:
                raise HTTPException(422, f"O produto {product['name']} não aceita personalização")
            adjustment = {"Pequeno": -200, "Médio": 0, "Grande": 400}.get(item.size, 0)
            unit_price = product["price_cents"] + adjustment
            total_cents += unit_price * item.quantity
            priced_items.append((product, item, unit_price))

        number = (db.execute("SELECT COALESCE(MAX(number), 0) + 1 AS next FROM orders").fetchone()["next"] - 1) % 999 + 1
        order_id = db.execute(
            "INSERT INTO orders (customer_id, number, total_cents) VALUES (%s, %s, %s) RETURNING id",
            (customer_id, number, total_cents),
        ).fetchone()["id"]
        with db.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO order_items (order_id,product_id,product_name,unit_price_cents,quantity,size,meat_point) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [(order_id, product["id"], product["name"], price, item.quantity, item.size, item.meat_point) for product, item, price in priced_items],
            )
    return {"id": order_id, "number": f"{number:03d}", "status": "pending_payment", "total": total_cents / 100}


@app.get("/api/v1/orders/{order_id}")
def get_order(order_id: int):
    with connect() as db:
        order = db.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
        if not order:
            raise HTTPException(404, "Pedido não encontrado")
        items = db.execute("SELECT product_id,product_name,unit_price_cents,quantity,size,meat_point FROM order_items WHERE order_id = %s", (order_id,)).fetchall()
        payment = db.execute("SELECT method,status,pix_code FROM payments WHERE order_id = %s", (order_id,)).fetchone()
    return {
        "id": order["id"], "number": f"{order['number']:03d}", "status": order["status"],
        "total": order["total_cents"] / 100, "created_at": order["created_at"],
        "items": [{**dict(item), "unit_price": item["unit_price_cents"] / 100} for item in items],
        "payment": dict(payment) if payment else None,
    }


@app.post("/api/v1/orders/{order_id}/payments", status_code=201)
def start_payment(order_id: int, payload: PaymentIn):
    with transaction() as db:
        order = db.execute("SELECT status FROM orders WHERE id = %s", (order_id,)).fetchone()
        if not order:
            raise HTTPException(404, "Pedido não encontrado")
        if order["status"] != "pending_payment":
            raise HTTPException(409, "O pedido não está aguardando pagamento")
        pix_code = f"smashgo-order-{order_id}-{secrets.token_urlsafe(12)}" if payload.method == "pix" else None
        try:
            payment_id = db.execute(
                "INSERT INTO payments (order_id, method, pix_code) VALUES (%s, %s, %s) RETURNING id",
                (order_id, payload.method, pix_code),
            ).fetchone()["id"]
        except UniqueViolation:
            raise HTTPException(409, "Já existe um pagamento para este pedido")
    return {"id": payment_id, "order_id": order_id, "method": payload.method, "status": "waiting", "pix_code": pix_code}


@app.patch("/api/v1/payments/{payment_id}", dependencies=[Depends(require_admin)])
def update_payment(payment_id: int, payload: PaymentUpdate):
    with transaction() as db:
        payment = db.execute("SELECT order_id FROM payments WHERE id = %s", (payment_id,)).fetchone()
        if not payment:
            raise HTTPException(404, "Pagamento não encontrado")
        paid_at = datetime.now(timezone.utc).isoformat() if payload.status == "approved" else None
        db.execute("UPDATE payments SET status = %s, paid_at = %s WHERE id = %s", (payload.status, paid_at, payment_id))
        if payload.status == "approved":
            db.execute("UPDATE orders SET status = 'preparing' WHERE id = %s", (payment["order_id"],))
    return {"id": payment_id, "status": payload.status}


@app.patch("/api/v1/orders/{order_id}/status", dependencies=[Depends(require_admin)])
def update_order_status(order_id: int, payload: OrderStatusUpdate):
    with transaction() as db:
        result = db.execute("UPDATE orders SET status = %s WHERE id = %s", (payload.status, order_id))
        if result.rowcount == 0:
            raise HTTPException(404, "Pedido não encontrado")
    return {"id": order_id, "status": payload.status}


@app.post("/api/v1/auth/login")
def login(payload: LoginIn, request: Request):
    ip = client_ip(request)
    check_login_limit(ip)
    if not authenticate(payload.username, payload.password):
        raise HTTPException(401, "Usuário ou senha inválidos")
    clear_login_attempts(ip)
    return {"access_token": create_token(), "token_type": "bearer", "expires_in": 28800}


if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def frontend():
        return FileResponse(frontend_dist / "index.html")