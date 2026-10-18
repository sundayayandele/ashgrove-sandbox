"""Orders: Ashgrove's 15-year-old order system.

It has a modern REST facade and the original XML endpoint that older tools still
use. Refunds above REFUND_AUTO_LIMIT_EUR need an approval created by a support
lead: the system enforces the gate, not the caller's prompt.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import timedelta
from xml.etree import ElementTree as ET

from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .common import Caller, Store, audit, create_app, get_caller, require_roles
from .crm import N_CUSTOMERS
from .synth import PRODUCTS, days_ago, iso

SCHEMA = """
CREATE TABLE orders (
  id TEXT PRIMARY KEY, customer_id TEXT, items TEXT, amount_eur REAL, status TEXT,
  shipping_city TEXT, placed_at TEXT, delivered_at TEXT
);
CREATE TABLE refunds (
  id TEXT PRIMARY KEY, order_id TEXT, amount_eur REAL, reason TEXT, approval_id TEXT,
  created_by TEXT, on_behalf_of TEXT, created_at TEXT
);
CREATE TABLE approvals (
  id TEXT PRIMARY KEY, order_id TEXT, max_amount_eur REAL, approved_by TEXT, created_at TEXT, used INTEGER DEFAULT 0
);
"""

CITIES = ["Amsterdam", "Utrecht", "Lagos", "Abuja", "Johannesburg", "Cape Town", "London", "Manchester", "Berlin", "Munich"]
N_ORDERS = 600


def seed(conn, rng):
    for i in range(N_ORDERS):
        n_items = rng.choice([1, 1, 1, 2, 2, 3])
        items = [rng.choice(PRODUCTS) for _ in range(n_items)]
        amount = round(sum(p[2] for p in items), 2)
        placed = days_ago(rng, 1, 400)
        status = rng.choices(["placed", "shipped", "delivered", "returned", "cancelled"], [5, 10, 70, 8, 7])[0]
        delivered = placed + timedelta(days=rng.randint(2, 7)) if status in ("delivered", "returned") else None
        conn.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
            (
                f"A-{10001 + i}",
                f"C-{1001 + rng.randrange(N_CUSTOMERS)}",
                json.dumps([{"sku": s, "name": n, "price_eur": p} for s, n, p in items]),
                amount,
                status,
                rng.choice(CITIES),
                iso(placed),
                iso(delivered),
            ),
        )


store = Store("orders", SCHEMA, seed)
app = create_app("orders", "Ashgrove Orders (legacy)", "Orders and refunds. Refunds above the limit need an approval.", store)


def _order(order_id: str) -> dict:
    row = store.one("SELECT * FROM orders WHERE id = ?", (order_id.strip().upper(),))
    if not row:
        raise HTTPException(404, f"No order {order_id}")
    row["items"] = json.loads(row["items"])
    return row


def refund_limit() -> float:
    return float(os.getenv("REFUND_AUTO_LIMIT_EUR", "100"))


@app.get("/v1/orders", tags=["orders"])
def list_orders(customer_id: str | None = None, status: str | None = None, limit: int = 20, caller: Caller = Depends(get_caller)):
    sql, args = "SELECT id, customer_id, amount_eur, status, placed_at, delivered_at FROM orders WHERE 1=1", []
    if customer_id:
        sql += " AND customer_id = ?"
        args.append(customer_id)
    if status:
        sql += " AND status = ?"
        args.append(status)
    return store.all(sql + " ORDER BY placed_at DESC LIMIT ?", [*args, min(limit, 100)])


@app.get("/v1/orders/{order_id}", tags=["orders"])
def get_order(order_id: str, caller: Caller = Depends(get_caller)):
    order = _order(order_id)
    order["refunds"] = store.all("SELECT id, amount_eur, reason, created_at FROM refunds WHERE order_id = ?", (order["id"],))
    return order


class ApprovalIn(BaseModel):
    order_id: str
    max_amount_eur: float = Field(gt=0)


@app.post("/v1/approvals", tags=["refunds"], status_code=201)
def create_approval(body: ApprovalIn, request: Request, caller: Caller = Depends(require_roles("support_lead"))):
    """A support lead approves a refund above the automatic limit. Single use."""
    _order(body.order_id)
    approval_id = f"APR-{uuid.uuid4().hex[:8]}"
    with store.connect() as c:
        c.execute(
            "INSERT INTO approvals VALUES (?,?,?,?,datetime('now'),0)",
            (approval_id, body.order_id.upper(), body.max_amount_eur, caller.on_behalf_of or caller.actor),
        )
    audit(store, request, caller, "approve_refund", body.order_id, {"max_amount_eur": body.max_amount_eur})
    return {"approval_id": approval_id}


class RefundIn(BaseModel):
    amount_eur: float = Field(gt=0)
    reason: str = "customer request"
    approval_id: str | None = None


@app.post("/v1/orders/{order_id}/refunds", tags=["refunds"], status_code=201)
def create_refund(
    order_id: str, body: RefundIn, request: Request, caller: Caller = Depends(require_roles("support_agent", "support_lead"))
):
    order = _order(order_id)
    if order["status"] != "delivered":
        raise HTTPException(409, f"Order {order['id']} is {order['status']}; only delivered orders can be refunded")
    already = sum(r["amount_eur"] for r in store.all("SELECT amount_eur FROM refunds WHERE order_id = ?", (order["id"],)))
    if body.amount_eur + already > order["amount_eur"] + 0.001:
        raise HTTPException(409, f"Refund exceeds order value ({order['amount_eur']:.2f} EUR, {already:.2f} already refunded)")
    if body.amount_eur > refund_limit():
        approval = store.one(
            "SELECT * FROM approvals WHERE id = ? AND order_id = ? AND used = 0", (body.approval_id or "", order["id"])
        )
        if not approval or approval["max_amount_eur"] < body.amount_eur:
            raise HTTPException(
                403, f"Refunds above {refund_limit():.2f} EUR need a valid approval_id from a support lead (POST /v1/approvals)"
            )
        with store.connect() as c:
            c.execute("UPDATE approvals SET used = 1 WHERE id = ?", (approval["id"],))
    refund_id = f"R-{uuid.uuid4().hex[:8]}"
    with store.connect() as c:
        c.execute(
            "INSERT INTO refunds VALUES (?,?,?,?,?,?,?,datetime('now'))",
            (refund_id, order["id"], body.amount_eur, body.reason, body.approval_id, caller.actor, caller.on_behalf_of),
        )
    audit(store, request, caller, "refund", order["id"], {"amount_eur": body.amount_eur, "approval_id": body.approval_id})
    return {"refund_id": refund_id, "order_id": order["id"], "amount_eur": body.amount_eur}


@app.post("/v1/customers/{customer_id}/erase", tags=["privacy"])
def erase_customer(customer_id: str, request: Request, caller: Caller = Depends(require_roles("support_lead", "it_admin"))):
    with store.connect() as c:
        n = c.execute("UPDATE orders SET shipping_city = '[erased]' WHERE customer_id = ?", (customer_id,)).rowcount
    audit(store, request, caller, "erase_customer", customer_id, {"orders": n})
    return {"status": "erased", "orders_updated": n}


# --------------------------------------------------------------------------- legacy XML endpoint


@app.post("/legacy/OrderService", tags=["legacy"], response_class=Response)
async def legacy_order_service(request: Request, caller: Caller = Depends(get_caller)):
    """The original XML interface. Send <GetOrderRequest><OrderId>A-10001</OrderId></GetOrderRequest>."""
    try:
        root = ET.fromstring(await request.body())
    except ET.ParseError:
        return Response("<Fault><Code>Client</Code><Message>Malformed XML</Message></Fault>", 400, media_type="application/xml")
    if root.tag != "GetOrderRequest" or root.findtext("OrderId") is None:
        return Response(
            "<Fault><Code>Client</Code><Message>Unsupported operation</Message></Fault>", 400, media_type="application/xml"
        )
    try:
        order = _order(root.findtext("OrderId"))
    except HTTPException:
        return Response("<Fault><Code>NotFound</Code><Message>Unknown order</Message></Fault>", 404, media_type="application/xml")
    resp = ET.Element("GetOrderResponse")
    for key in ("id", "customer_id", "status", "amount_eur", "placed_at", "delivered_at"):
        ET.SubElement(resp, "".join(p.capitalize() for p in key.split("_"))).text = "" if order[key] is None else str(order[key])
    items = ET.SubElement(resp, "Items")
    for it in order["items"]:
        ET.SubElement(items, "Item", sku=it["sku"], priceEur=f"{it['price_eur']:.2f}").text = it["name"]
    return Response(ET.tostring(resp, encoding="unicode"), media_type="application/xml")
