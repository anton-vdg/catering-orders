from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import db


def cent_zu_euro_text(cent: int) -> str:
    return f"{cent / 100:.2f}".replace(".", ",")


def text_umbrechen(text: str, max_len: int) -> list[str]:
    """Einfacher Umbruch nach Wortlänge (für Beschreibung)."""
    words = (text or "").split()
    lines, cur = [], []
    for w in words:
        if sum(len(x) for x in cur) + len(cur) + len(w) > max_len:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines or [""]


def rechnung_pdf_erzeugen(order_id: int, out_dir: str = "rechnungen") -> Path:
    order = db.get_order_with_customer(order_id)

    # Rechnungsnummer vergeben, falls noch keine existiert
    if not order.get("invoice_number"):
        db.assign_invoice_number(order_id)
        order = db.get_order_with_customer(order_id)

    items = db.get_order_items(order_id)
    totals = db.compute_totals(order_id)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pdf_path = out / f"Rechnung_{order['invoice_number']}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 50

    # ------------------------------------------------------------
    # Absender / Firmendaten (hier bitte deine Daten eintragen)
    # ------------------------------------------------------------
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "DEIN PARTY-SERVICE (bitte anpassen)")
    y -= 14
    c.drawString(50, y, "Straße 1, 12345 Ort")
    y -= 14
    c.drawString(50, y, "Telefon: 01234 56789 | E-Mail: info@...")
    y -= 14
    c.drawString(50, y, "USt-IdNr.: ... | IBAN: ...")
    y -= 26

    # ------------------------------------------------------------
    # Rechnungskopf
    # ------------------------------------------------------------
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Rechnung")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Rechnungsnummer: {order['invoice_number']}")
    y -= 14
    c.drawString(50, y, f"Rechnungsdatum: {order.get('invoice_date') or '-'}")
    y -= 14
    c.drawString(50, y, f"Auftragsnummer: {order['id']}")
    y -= 14
    c.drawString(50, y, f"Termin: {order['event_date']} {order['event_time']} | Art: {order['fulfilment_type']}")
    y -= 22

    # ------------------------------------------------------------
    # Empfänger (Kunde)
    # ------------------------------------------------------------
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Rechnung an:")
    y -= 14

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"{order.get('customer_name') or '-'}")
    y -= 14

    addr = (order.get("customer_address") or "").strip()
    if addr:
        for line in addr.splitlines():
            c.drawString(50, y, line)
            y -= 14

    phone = (order.get("customer_phone") or "").strip()
    if phone:
        c.drawString(50, y, f"Telefon: {phone}")
        y -= 14

    email = (order.get("customer_email") or "").strip()
    if email:
        c.drawString(50, y, f"E-Mail: {email}")
        y -= 14

    y -= 10

    # ------------------------------------------------------------
    # Positionen (Tabelle)
    # ------------------------------------------------------------
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Positionen")
    y -= 14

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Beschreibung")
    c.drawRightString(360, y, "Menge")
    c.drawRightString(450, y, "Einzel (Br.)")
    c.drawRightString(width - 50, y, "Gesamt (Br.)")
    y -= 8
    c.line(50, y, width - 50, y)
    y -= 14

    c.setFont("Helvetica", 9)
    for it in items:
        line_gross = int(round(float(it["quantity"]) * int(it["unit_price_cents"])))
        desc_lines = text_umbrechen(it["description"], 45)

        for j, part in enumerate(desc_lines):
            c.drawString(50, y, part)
            if j == 0:
                c.drawRightString(360, y, f"{float(it['quantity']):g} {it.get('unit') or ''}".strip())
                c.drawRightString(450, y, f"{cent_zu_euro_text(int(it['unit_price_cents']))} €")
                c.drawRightString(width - 50, y, f"{cent_zu_euro_text(line_gross)} €")
            y -= 12

            # Seitenumbruch
            if y < 120:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)

    y -= 6
    c.line(50, y, width - 50, y)
    y -= 18

    # Lieferung / Rabatt
    if totals["delivery_fee_cents"]:
        c.drawRightString(width - 50, y, f"Lieferpauschale: {cent_zu_euro_text(totals['delivery_fee_cents'])} €")
        y -= 14
    if totals["discount_cents"]:
        c.drawRightString(width - 50, y, f"Rabatt: -{cent_zu_euro_text(totals['discount_cents'])} €")
        y -= 14

    y -= 8

    # MwSt-Aufschlüsselung
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "MwSt-Aufschlüsselung")
    y -= 14

    c.setFont("Helvetica", 10)
    for vat_rate, vals in sorted(totals["by_vat"].items(), key=lambda x: x[0]):
        c.drawString(
            50,
            y,
            f"{int(vat_rate*100)}%: Netto {cent_zu_euro_text(vals['net'])} € / MwSt {cent_zu_euro_text(vals['vat'])} € / Brutto {cent_zu_euro_text(vals['gross'])} €",
        )
        y -= 14

    y -= 8
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - 50, y, f"Gesamtbetrag (brutto): {cent_zu_euro_text(totals['gross_total_cents'])} €")

    # Hinweise
    notes = (order.get("notes") or "").strip()
    if notes:
        y -= 28
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Hinweise")
        y -= 14
        c.setFont("Helvetica", 10)
        for line in notes.splitlines():
            c.drawString(50, y, line)
            y -= 14

    c.save()
    return pdf_path
