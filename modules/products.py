"""
SN Gym Management System - Products / Supplements
Developed by SN Softech Solutions
"""

from datetime import date

import streamlit as st

import database as db
import utils

CATEGORIES = ["Supplement", "Accessory", "Beverage", "Apparel", "Equipment", "Other"]
STATUSES = ["Active", "Inactive"]


def page():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Products / Supplements", "Manage inventory and sell over the counter.",
                      "\U0001F4E6")

    tab_list, tab_sell, tab_add, tab_moves = st.tabs(
        ["Inventory", "Sell Product", "Add / Edit Product", "Stock Movements"])

    with tab_list:
        _inventory(gym_id)
    with tab_sell:
        _sell(gym_id)
    with tab_add:
        _form(gym_id)
    with tab_moves:
        _movements(gym_id)


def _inventory(gym_id):
    rows = db.fetch_all("SELECT * FROM products WHERE gym_id=? ORDER BY id DESC", (gym_id,))
    if not rows:
        utils.empty_state("No products yet", "Add your first product in the 'Add / Edit Product' tab.")
        return

    low = [r for r in rows if r["stock"] <= r["low_stock_limit"] and r["status"] == "Active"]
    if low:
        st.warning(f"⚠️ {len(low)} product(s) are low on stock: " +
                  ", ".join(r["product_name"] for r in low))

    for p in rows:
        c = st.columns([3, 2, 2, 2, 2, 1])
        c[0].markdown(f"**{p['product_name']}**  \n<span style='color:#64748B;font-size:.8rem'>"
                     f"{p['category'] or ''}</span>", unsafe_allow_html=True)
        c[1].write(utils.money(p["selling_price"]))
        stock_colour = "#D93025" if p["stock"] <= p["low_stock_limit"] else "#0F2A4A"
        c[2].markdown(f"<span style='color:{stock_colour};font-weight:700'>{p['stock']:.0f} in stock</span>",
                     unsafe_allow_html=True)
        c[3].write(p["supplier"] or "-")
        c[4].markdown(utils.status_badge(p["status"]) if p["status"] == "Active" else
                     f"<span style='color:#94A3B8'>{p['status']}</span>", unsafe_allow_html=True)
        if c[5].button("Edit", key=f"prod_edit_{p['id']}"):
            st.session_state["editing_product"] = p["id"]
            st.rerun()


def _form(gym_id):
    editing_id = st.session_state.get("editing_product")
    product = db.fetch_one("SELECT * FROM products WHERE id=?", (editing_id,)) if editing_id else None
    if product:
        st.info(f"Editing **{product['product_name']}**")
        if st.button("Cancel edit / add new instead", key="cancel_prod_edit"):
            st.session_state["editing_product"] = None
            st.rerun()

    with st.form("product_form", clear_on_submit=not product):
        c1, c2 = st.columns(2)
        name = c1.text_input("Product Name *", value=(product or {}).get("product_name", ""))
        category = c2.selectbox("Category", CATEGORIES,
                                index=CATEGORIES.index(product["category"])
                                if product and product.get("category") in CATEGORIES else 0)
        barcode = c1.text_input("Barcode / SKU", value=(product or {}).get("barcode", ""))
        supplier = c2.text_input("Supplier", value=(product or {}).get("supplier", ""))
        purchase_price = c1.number_input("Purchase Price", min_value=0.0, step=10.0,
                                         value=float((product or {}).get("purchase_price", 0)))
        selling_price = c2.number_input("Selling Price", min_value=0.0, step=10.0,
                                        value=float((product or {}).get("selling_price", 0)))
        stock = c1.number_input("Current Stock", min_value=0.0, step=1.0,
                                value=float((product or {}).get("stock", 0)))
        low_stock_limit = c2.number_input("Low Stock Alert Below", min_value=0.0, step=1.0,
                                          value=float((product or {}).get("low_stock_limit", 5)))
        status = st.selectbox("Status", STATUSES,
                              index=STATUSES.index(product["status"]) if product and product.get("status") in STATUSES else 0)
        submitted = st.form_submit_button("Update Product" if product else "Save Product",
                                          type="primary", use_container_width=True)

    if not submitted:
        return
    errors = utils.require({"Product Name": name})
    if errors:
        utils.toast_err("  \n".join(errors))
        return
    if product:
        db.execute(
            """UPDATE products SET product_name=?, category=?, barcode=?, purchase_price=?,
                   selling_price=?, stock=?, low_stock_limit=?, supplier=?, status=? WHERE id=?""",
            (name.strip(), category, barcode, purchase_price, selling_price, stock,
             low_stock_limit, supplier, status, product["id"]))
        st.session_state["editing_product"] = None
        utils.toast_ok("Product updated.")
    else:
        db.execute(
            """INSERT INTO products (gym_id, product_name, category, barcode, purchase_price,
                   selling_price, stock, low_stock_limit, supplier) VALUES (?,?,?,?,?,?,?,?,?)""",
            (gym_id, name.strip(), category, barcode, purchase_price, selling_price, stock,
             low_stock_limit, supplier))
        utils.toast_ok(f"Product {name} added.")
    st.rerun()


def _sell(gym_id):
    products = db.fetch_all("SELECT * FROM products WHERE gym_id=? AND status='Active' AND stock>0 "
                            "ORDER BY product_name", (gym_id,))
    if not products:
        utils.empty_state("Nothing in stock to sell.", "Add stock from the Inventory tab.")
        return
    product_map = {f"{p['product_name']} ({p['stock']:.0f} in stock)": p for p in products}
    member_map = {"Walk-in Customer": None, **utils.member_options(gym_id)}

    with st.form("sell_form"):
        c1, c2 = st.columns(2)
        product_choice = c1.selectbox("Product *", list(product_map.keys()))
        member_choice = c2.selectbox("Sold To", list(member_map.keys()))
        product = product_map[product_choice]
        quantity = c1.number_input("Quantity", min_value=1.0, max_value=float(product["stock"]),
                                   step=1.0, value=1.0)
        rate = c2.number_input("Rate", min_value=0.0, value=float(product["selling_price"]))
        amount = round(quantity * rate, 2)
        st.markdown(f"**Total: {utils.money(amount)}**")
        paid_amount = c1.number_input("Paid Amount", min_value=0.0, value=amount)
        payment_mode = c2.selectbox("Payment Mode", db.PAYMENT_MODES)
        submitted = st.form_submit_button("Confirm Sale", type="primary", use_container_width=True)

    if not submitted:
        return
    due_amount = round(amount - paid_amount, 2)
    invoice_no = utils.next_invoice(gym_id, "PRD")
    member_id = member_map[member_choice]
    db.execute(
        """INSERT INTO product_sales (gym_id, product_id, member_id, sale_date, quantity, rate,
               amount, paid_amount, due_amount, payment_mode, invoice_no)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (gym_id, product["id"], member_id, date.today().strftime("%Y-%m-%d"), quantity, rate,
         amount, paid_amount, due_amount, payment_mode, invoice_no))
    db.execute("UPDATE products SET stock = stock - ? WHERE id=?", (quantity, product["id"]))
    db.execute(
        "INSERT INTO stock_movements (gym_id, product_id, move_date, move_type, quantity, notes) "
        "VALUES (?,?,?, 'Sale', ?, ?)",
        (gym_id, product["id"], date.today().strftime("%Y-%m-%d"), quantity, f"Invoice {invoice_no}"))
    if member_id:
        db.execute(
            """INSERT INTO payments (gym_id, member_id, invoice_no, pay_date, category, ref_table,
                   ref_id, amount, paid_amount, due_amount, payment_mode, status, created_by)
               VALUES (?,?,?,?, 'Product', 'product_sales', ?,?,?,?,?,?,?)""",
            (gym_id, member_id, invoice_no, date.today().strftime("%Y-%m-%d"), product["id"], amount,
             paid_amount, due_amount, payment_mode, "Paid" if due_amount <= 0 else "Partial",
             st.session_state.user["id"]))
    db.log_action(gym_id, st.session_state.user, "PRODUCT_SALE", f"{product['product_name']} x{quantity}")
    utils.toast_ok(f"Sale recorded. Invoice {invoice_no}.")
    st.rerun()


def _movements(gym_id):
    with st.expander("Add stock (restock a product)"):
        products = db.fetch_all("SELECT id, product_name FROM products WHERE gym_id=? "
                                "ORDER BY product_name", (gym_id,))
        if products:
            product_map = {p["product_name"]: p["id"] for p in products}
            with st.form("restock_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                product_choice = c1.selectbox("Product", list(product_map.keys()))
                quantity = c2.number_input("Quantity to add", min_value=1.0, step=1.0, value=1.0)
                notes = st.text_input("Notes", value="Restock")
                if st.form_submit_button("Add Stock", type="primary"):
                    product_id = product_map[product_choice]
                    db.execute("UPDATE products SET stock = stock + ? WHERE id=?", (quantity, product_id))
                    db.execute("INSERT INTO stock_movements (gym_id, product_id, move_date, "
                              "move_type, quantity, notes) VALUES (?,?,?, 'Restock', ?, ?)",
                              (gym_id, product_id, date.today().strftime("%Y-%m-%d"), quantity, notes))
                    utils.toast_ok("Stock updated.")
                    st.rerun()

    df = db.fetch_df(
        """SELECT sm.move_date AS Date, p.product_name AS Product, sm.move_type AS Type,
                  sm.quantity AS Quantity, sm.notes AS Notes
           FROM stock_movements sm JOIN products p ON p.id = sm.product_id
           WHERE sm.gym_id=? ORDER BY sm.id DESC LIMIT 200""", (gym_id,))
    if df.empty:
        utils.empty_state("No stock movements yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
