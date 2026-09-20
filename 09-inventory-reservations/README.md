# 09 — Inventory reservations

Transactional stock with all-or-nothing multi-item reservations, idempotency keys,
explicit states and an append-only application audit trail. It prevents
overselling under concurrent tool calls.

## Run with Docker

Set up `.env` once using the [Docker quick start](../README.md#start-with-docker).
Then run these commands from the repository root:

```bash
docker compose up -d --build inventory-reservations
docker compose exec inventory-reservations python clients/08-inventory-client.py
```

The client connects over HTTP and inherits the container's authentication token.
For a host Python setup, see [MANUAL.md](../MANUAL.md).

The demo creates a unique SKU, receives stock, retries a reservation and releases
it. It intentionally leaves sample stock and audit records in the test instance.

## Tool sequence

Use the interactive client against port 8109:

```text
receive_stock {"request_key":"delivery-a","sku":"BOOK","quantity":10}
receive_stock {"request_key":"delivery-b","sku":"PEN","quantity":5}
reserve_stock {"request_key":"order-1","items":[{"sku":"BOOK","quantity":2},{"sku":"PEN","quantity":1}]}
list_inventory {}
audit_log {}
```

Repeat reserve_stock with the same key and arguments: it returns the original
reservation without deducting stock again. A reused key with different arguments
fails. Keys are global across mutation tools. Retried responses are the original
snapshot; get_reservation reports current state.

With the returned ID, call one of:

```text
settle_reservation {"request_key":"order-1-confirm","reservation_id":"RETURNED_ID","action":"confirm"}
settle_reservation {"request_key":"order-1-release","reservation_id":"RETURNED_ID","action":"release"}
```

Confirmation finalizes the sale; release returns units to available stock.
Final states cannot be reversed or changed into each other. Repeating the same
final action with a new key is harmless and logged.

A BEGIN IMMEDIATE transaction covers deductions, reservation creation, stored
idempotency responses and audit insertion. Insufficient stock for one SKU rolls
back all earlier deductions. Eight clients competing for ten units cannot all
reserve three units successfully.

SKUs use uppercase letters, digits, underscores and hyphens. Quantities are strict
integers from 1 to 1,000,000; reservations allow 1–50 distinct SKUs. Inventory and
audit tools support keyset pagination. Compose persists `/app/data/inventory.db`
in a dedicated named volume.

This is a single-tenant example, not a payment service. Reservations do not expire
automatically; callers explicitly confirm or release them. Idempotency and audit
history are retained indefinitely. The service token grants all tools; add tenant
authorization before serving independent customers.
