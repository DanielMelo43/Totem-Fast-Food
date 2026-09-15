import os
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["CPF_ENCRYPTION_KEY"] = "test-only-cpf-encryption-key-32-characters"

from fastapi.testclient import TestClient
from app.main import app
from app.database import connect


def test_catalog_order_and_payment():
    with TestClient(app) as client:
        products = client.get("/api/v1/products?category=burger")
        assert products.status_code == 200
        assert len(products.json()) == 3

        order = client.post("/api/v1/orders", json={
            "customer": {"name": "Ana Silva", "cpf": "52998224725"},
            "items": [{"product_id": 4, "quantity": 2, "size": "Grande", "meat_point": "Ao ponto"}],
        })
        assert order.status_code == 201
        assert order.json()["total"] == 53.8

        payment = client.post(f"/api/v1/orders/{order.json()['id']}/payments", json={"method": "pix"})
        assert payment.status_code == 201
        assert payment.json()["pix_code"]

        with connect() as db:
            customer = db.execute("SELECT cpf, cpf_hash FROM customers WHERE id = (SELECT customer_id FROM orders WHERE id = %s)", (order.json()["id"],)).fetchone()
        assert customer["cpf"] != "52998224725"
        assert "52998224725" not in customer["cpf"]
        assert len(customer["cpf_hash"]) == 64


def test_sql_injection_is_data_not_command():
    with TestClient(app) as client:
        response = client.get("/api/v1/products", params={"category": "burger' OR 1=1 --"})
        assert response.status_code == 200
        assert response.json() == []
        assert client.get("/api/v1/products").status_code == 200


def test_login_is_rate_limited_after_ten_attempts():
    with TestClient(app) as client:
        for _ in range(10):
            assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert response.status_code == 429
        assert response.headers["retry-after"]
