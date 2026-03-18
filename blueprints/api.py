from flask import Blueprint, jsonify, request
from supabase_client import get_supabase

api_bp = Blueprint("api", __name__)


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@api_bp.route("/api/approved-invoices", methods=["GET"])
def approved_invoices():
    sb = get_supabase()

    # Fetch all approved invoices with party and adda names
    invoices = (
        sb.table("approved_invoices")
        .select("*, parties(name), addas(name, number), warehouses(id)")
        .order("approved_at", desc=True)
        .execute()
        .data
    )

    results = []
    for inv in invoices:
        adda_name = inv["addas"]["name"] if inv.get("addas") else ""
        adda_number = inv["addas"].get("number") if inv.get("addas") else ""
        adda_number = adda_number or ""
        adda_display = f"{adda_name} - {adda_number}" if adda_name and adda_number else adda_name

        # Fetch line items for this approved invoice
        items = (
            sb.table("approved_invoice_items")
            .select("quantity, discount, items(item_code, name, box_qty, discount)")
            .eq("approved_invoice_id", inv["id"])
            .execute()
            .data
        )

        results.append(
            {
                "id": inv["id"],
                "invoice_number": inv["invoice_number"],
                "party": inv["parties"]["name"] if inv.get("parties") else "",
                "adda": adda_display,
                "adda_name": adda_name,
                "adda_number": adda_number,
                "warehouse": inv["warehouses"]["id"] if inv.get("warehouses") else inv.get("warehouse_id"),
                "delivery_paid": inv["delivery_paid"],
                "delivery_amount": float(inv["delivery_amount"]),
                "invoice_date": inv["invoice_date"],
                "approved_at": inv["approved_at"],
                "items": [
                    {
                        "item_code": it["items"]["item_code"],
                        "item_name": it["items"]["name"],
                        "box_qty": it["items"]["box_qty"],
                        "quantity": it["quantity"],
                        "discount": float(it.get("discount") or 0),
                        "default_item_discount": float((it.get("items") or {}).get("discount") or 0),
                    }
                    for it in items
                ],
            }
        )

    return jsonify(results)


@api_bp.route("/api/stock/add", methods=["POST"])
def add_stock():
    """Receive external stock payload and add quantities to warehouse stock.

    Expected JSON:
    {
      "invoiceNo": "123",
      "billNo": "ABC456",
      "items": [
        {"WH": "1", "Qty": "10", "Name": "Product A"}
      ]
    }
    """
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Invalid payload. 'items' must be a non-empty array."}), 400

    sb = get_supabase()
    results = []
    errors = []

    for idx, row in enumerate(items, start=1):
        wh_id = _as_int((row or {}).get("WH"))
        qty = _as_int((row or {}).get("Qty"))
        item_code = str((row or {}).get("Name") or "").strip()

        if not wh_id or not item_code or qty is None:
            errors.append({
                "row": idx,
                "error": "Each item must include valid WH (warehouse id), Qty, and Name (item code).",
            })
            continue

        if qty <= 0:
            errors.append({"row": idx, "error": "Qty must be greater than 0."})
            continue

        warehouse = sb.table("warehouses").select("id, name").eq("id", wh_id).limit(1).execute().data
        if not warehouse:
            errors.append({"row": idx, "error": f"Warehouse not found for WH={wh_id}."})
            continue

        item_row = (
            sb.table("items")
            .select("id, item_code, name")
            .ilike("item_code", item_code)
            .limit(1)
            .execute()
            .data
        )
        if not item_row:
            errors.append({"row": idx, "error": f"Item not found for item code='{item_code}'."})
            continue

        item_id = int(item_row[0]["id"])
        existing_stock = (
            sb.table("warehouse_stock")
            .select("id, stock")
            .eq("warehouse_id", wh_id)
            .eq("item_id", item_id)
            .limit(1)
            .execute()
            .data
        )

        if existing_stock:
            stock_id = existing_stock[0]["id"]
            prev_stock = int(existing_stock[0].get("stock") or 0)
            new_stock = prev_stock + qty
            sb.table("warehouse_stock").update({"stock": new_stock}).eq("id", stock_id).execute()
        else:
            prev_stock = 0
            new_stock = qty
            sb.table("warehouse_stock").insert(
                {"warehouse_id": wh_id, "item_id": item_id, "stock": new_stock}
            ).execute()

        results.append(
            {
                "row": idx,
                "warehouse_id": wh_id,
                "item_code": item_row[0]["item_code"],
                "item_name": item_row[0]["name"],
                "added_qty": qty,
                "previous_stock": prev_stock,
                "new_stock": new_stock,
            }
        )

    status_code = 200 if not errors else (207 if results else 400)
    return (
        jsonify(
            {
                "invoiceNo": payload.get("invoiceNo"),
                "billNo": payload.get("billNo"),
                "processed": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors,
            }
        ),
        status_code,
    )
