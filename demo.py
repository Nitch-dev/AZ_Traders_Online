from flask import Flask, jsonify
from supabase_client import get_supabase

app = Flask(__name__)


@app.route("/api/approved-invoices", methods=["GET"])
def approved_invoices():
    sb = get_supabase()

    # Fetch all approved invoices with party and adda names
    invoices = (
        sb.table("approved_invoices")
        .select("*, parties(name), addas(name, number), warehouses(name)")
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
                "warehouse": inv["warehouses"]["name"] if inv.get("warehouses") else "",
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
