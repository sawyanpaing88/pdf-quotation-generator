import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import random
import re
import json
import base64
from datetime import datetime
from weasyprint import HTML

# --- PAGE SETUP & THEME INITIALIZATION ---
st.set_page_config(
    page_title="ARK Premium Solutions - Quotation Portal", 
    page_icon="🌐", 
    layout="wide"
)

st.markdown("""
<style>
    :root { --main-color: #00a8e8; }
    .stButton>button { background-color: #00a8e8 !important; color: white !important; font-weight: bold; }
    .reportview-container { background: #f4f7f6; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE ARCHITECTURE INITIALIZATION ---
DB_FILE = "ark_enterprise.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                name TEXT DEFAULT '',
                designation TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                signature_b64 TEXT DEFAULT '',
                is_verified INTEGER DEFAULT 0,
                verification_code TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                director_id INTEGER,
                manager_id INTEGER,
                status TEXT DEFAULT 'PENDING',
                FOREIGN KEY(director_id) REFERENCES users(id),
                FOREIGN KEY(manager_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_number TEXT UNIQUE NOT NULL,
                creator_id INTEGER,
                customer_name TEXT,
                project_name TEXT,
                attention_person TEXT,
                attention_email TEXT,
                attention_phone TEXT,
                status TEXT,
                issue_date TEXT,
                validity TEXT,
                lead_time TEXT,
                payment_term TEXT,
                terms_conditions TEXT,
                subtotal REAL,
                discount REAL,
                tax_type TEXT DEFAULT 'Both Taxes',
                commercial_tax_rate REAL DEFAULT 5.0,
                wht_tax_rate REAL DEFAULT 2.0,
                grand_total REAL,
                currency_unit TEXT,
                exchange_rate REAL,
                items_json TEXT,
                FOREIGN KEY(creator_id) REFERENCES users(id)
            )
        """)
        conn.commit()

init_db()

def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- PARSING HEURISTICS ENGINE ---
def parse_uploaded_document(df_raw):
    structured_items = []
    if df_raw.empty:
        return structured_items

    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    sample_rows = df_raw.head(10).astype(str)
    desc_col = sample_rows.apply(lambda x: x.str.len().max()).idxmax()
    
    qty_col = None
    price_col = None
    for col in df_raw.columns:
        col_lower = col.lower()
        if 'qty' in col_lower or 'quant' in col_lower:
            qty_col = col
        elif 'price' in col_lower or 'rate' in col_lower or 'unit' in col_lower:
            price_col = col

    for idx, row in df_raw.iterrows():
        desc_val = str(row[desc_col]) if desc_col in df_raw.columns else ""
        if pd.isna(row[desc_col]) or desc_val.strip() == "" or "total" in desc_val.lower():
            continue
            
        row_no_raw = str(row.get("No", idx + 1)).strip()
        row_no = row_no_raw.split(".")[0] if row_no_raw.endswith(".0") else row_no_raw
        is_sub_row = "." in row_no
        p_idx = row_no.split(".")[0]
            
        qty_val = 1 if is_sub_row else 0
        if qty_col and is_sub_row:
            try: qty_val = int(float(str(row[qty_col]).replace(',', '')))
            except: pass
            
        price_val = 0.0
        if price_col and is_sub_row:
            try: price_val = float(re.sub(r'[^\d\.]', '', str(row[price_col])))
            except: pass
            
        part_no = "ARK-PART" if is_sub_row else ""

        structured_items.append({
            "No": row_no, "is_sub": is_sub_row, "parent_idx": p_idx,
            "Part Number": part_no if is_sub_row else "", "Description": desc_val,
            "Qty": qty_val, "Unit Price": price_val, "Margin": 20.0 if is_sub_row else 0.0, "Total Price": 0.0
        })
    return structured_items

if "user" not in st.session_state: st.session_state.user = None
if "default_logo_base64" not in st.session_state: st.session_state.default_logo_base64 = None

# ==========================================
# AUTHENTICATION HUB
# ==========================================
if not st.session_state.user:
    st.subheader("🔒 ARK Premium Solutions Portal Authentication")
    auth_tab1, auth_tab2 = st.tabs(["Sign In System", "Register New Profile"])
    
    with auth_tab1:
        login_email = st.text_input("Corporate Email Address", key="login_em").strip()
        login_pwd = st.text_input("Password Secure Vector", type="password", key="login_pw")
        if st.button("Sign In"):
            with get_db() as conn:
                res = conn.execute("SELECT * FROM users WHERE LOWER(email)=LOWER(?) AND password_hash=?", (login_email, hash_pwd(login_pwd))).fetchone()
                if res:
                    st.session_state.user = dict(res)
                    st.success("Access Granted!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with auth_tab2:
        reg_email = st.text_input("Corporate Email Address", key="reg_em").strip()
        reg_pwd = st.text_input("Create Security Password", type="password", key="reg_pw")
        reg_role = st.selectbox("Requested Core Profile", ["Account Manager", "Account Director", "Admin"])
        if st.button("Identity Activation Request"):
            with get_db() as conn:
                conn.execute("INSERT INTO users (email, password_hash, role, is_verified) VALUES (?, ?, ?, 1)", (reg_email, hash_pwd(reg_pwd), reg_role))
                conn.commit()
            st.success("Registration completed!")
    st.stop()

current_user = st.session_state.user

# Sync User Profiling
with get_db() as conn:
    db_u = conn.execute("SELECT * FROM users WHERE id=?", (current_user["id"],)).fetchone()
    if db_u: current_user = dict(db_u)

st.sidebar.markdown(f"**Entity:** `{current_user['email']}` | **Clearance:** `{current_user['role']}`")
if st.sidebar.button("Logout Session"):
    st.session_state.user = None
    st.rerun()

nav_options = ["🏠 Dashboard Console", "➕ Build New Quotation Module", "👤 User Profile Management"]
page_selection = st.sidebar.radio("Navigation Directives", nav_options)

# ==========================================
# 👤 USER PROFILE MANAGEMENT
# ==========================================
if page_selection == "👤 User Profile Management":
    st.header("👤 User Account Profile Configuration")
    prof_name = st.text_input("Full Professional Name", current_user.get("name", ""))
    prof_desig = st.text_input("Corporate Designation / Title", current_user.get("designation", ""))
    prof_phone = st.text_input("Direct Phone Line", current_user.get("phone", ""))
    
    if current_user.get("signature_b64"):
        st.markdown("**Active Signature:**")
        st.markdown(f'<img src="{current_user["signature_b64"]}" style="max-height: 80px; background: white;">', unsafe_allow_html=True)
    
    uploaded_sig = st.file_uploader("Upload New Signature Image (PNG/JPG)", type=["png", "jpg", "jpeg"])
    
    if st.button("💾 Save Profile Changes"):
        sig_payload = current_user.get("signature_b64", "")
        if uploaded_sig is not None:
            sig_payload = f"data:{uploaded_sig.type};base64,{base64.b64encode(uploaded_sig.getvalue()).decode('utf-8')}"
            
        with get_db() as conn:
            conn.execute("UPDATE users SET name=?, designation=?, phone=?, signature_b64=? WHERE id=?", (prof_name, prof_desig, prof_phone, sig_payload, current_user["id"]))
            conn.commit()
        st.success("Profile records saved successfully.")
        st.rerun()

# ==========================================
# 🏠 DASHBOARD ENGINE
# ==========================================
elif page_selection == "🏠 Dashboard Console":
    st.header("📊 Activity Metrics Control Dashboard")
    with get_db() as conn:
        quotes = conn.execute("SELECT * FROM quotations").fetchall()
    if quotes:
        for row in quotes:
            st.markdown(f"**Quotation #:** `{row['po_number']}` | **Customer:** {row['customer_name']} | **Total:** {row['currency_unit']} {row['grand_total']:,.2f} | **Status:** `{row['status']}`")
    else:
        st.info("No documents found.")

# ==========================================
# ➕ BUILD NEW QUOTATION MODULE
# ==========================================
elif page_selection == "➕ Build New Quotation Module":
    st.header("➕ Document Generation Sandbox")
    quotation_auto_gen = f"ARK-QT-{datetime.now().strftime('%Y%m')}-{random.randint(100000, 999999)}"
    
    currency_selection = st.sidebar.selectbox("Currency Mode", ["USD", "MMK"])
    exchange_rate = st.sidebar.number_input("Exchange Rate (1 USD to MMK)", min_value=1.0, value=3250.0)
    currency_symbol = "USD " if currency_selection == "USD" else "MMK "
    conversion_multiplier = exchange_rate if currency_selection == "MMK" else 1.0
    
    st.sidebar.markdown("### 🖼️ Corporate Branding")
    uploaded_logo_file = st.sidebar.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"])
    if uploaded_logo_file:
        st.session_state.default_logo_base64 = f"data:{uploaded_logo_file.type};base64,{base64.b64encode(uploaded_logo_file.getvalue()).decode('utf-8')}"

    client_company = st.text_input("Client Corporate Entity Name", "Acme Enterprise Corp")
    attn_person = st.text_input("Attention Person", "John Doe")
    attn_email = st.text_input("Contact Email", "johndoe@client.com")
    attn_phone = st.text_input("Contact Phone", "+959xxxxxxxxx")
    project_title = st.text_input("Project Title", "Network Overhaul")
    issue_date = st.date_input("Issue Date")
    validity_bound = st.text_input("Validity Frame", "30 Days")
    lead_time_frame = st.text_input("Lead Time", "4-6 Weeks")
    payment_terms_desc = st.text_input("Payment Terms", "50% Advance, 50% Upon Delivery")
    terms_and_cond = st.text_area("Custom Terms", "1. Standard ARK Warranty applies.\n2. Prices exclude deployment unless itemized below.")

    if "working_items" not in st.session_state:
        st.session_state.working_items = [
            {"No": "1", "is_sub": False, "parent_idx": "1", "Part Number": "", "Description": "Main Route Hardware System Cluster", "Qty": 0, "Unit Price": 0.0, "Margin": 0.0, "Total Price": 0.0},
            {"No": "1.1", "is_sub": True, "parent_idx": "1", "Part Number": "C9300-48TX-E", "Description": "Catalyst 9300 48-port Node", "Qty": 1, "Unit Price": 4500.0, "Margin": 10.0, "Total Price": 0.0},
            {"No": "1.2", "is_sub": True, "parent_idx": "1", "Part Number": "FOC-SVC", "Description": "Free Engineering Deployment Onsite", "Qty": 1, "Unit Price": 0.0, "Margin": 0.0, "Total Price": 0.0}
        ]

    # Recalculate Live Table (Static Input isolation logic)
    for item in st.session_state.working_items:
        if item.get("is_sub", False):
            qty = float(item.get("Qty") or 0)
            u_p = float(item.get("Unit Price") or 0.0)
            m_pct = float(item.get("Margin") or 0.0) / 100.0
            final_unit_price = u_p / (1 - m_pct) if m_pct < 1.0 else u_p
            item["Calculated Unit Price Base"] = round(final_unit_price, 2)
            item["Total Price"] = round((final_unit_price * qty) * conversion_multiplier, 2)

    df_display = pd.DataFrame(st.session_state.working_items)
    edited_df = st.data_editor(
        df_display[["No", "Part Number", "Description", "Qty", "Unit Price", "Margin", "Total Price"]],
        num_rows="dynamic", width="stretch", key="quotation_grid"
    )

    # Save changes from manual data grid edits
    if not edited_df.equals(df_display[["No", "Part Number", "Description", "Qty", "Unit Price", "Margin", "Total Price"]]):
        updated_records = []
        for idx, row in edited_df.iterrows():
            r_no = str(row["No"] or "")
            is_sub = "." in r_no
            updated_records.append({
                "No": r_no, "is_sub": is_sub, "parent_idx": r_no.split(".")[0],
                "Part Number": "" if not is_sub else (row["Part Number"] or ""),
                "Description": row["Description"] or "Structural Node",
                "Qty": 0 if not is_sub else int(row.get("Qty") or 0),
                "Unit Price": 0.0 if not is_sub else float(row.get("Unit Price") or 0.0),
                "Margin": 0.0 if not is_sub else float(row.get("Margin") or 0.0),
                "Total Price": 0.0
            })
        st.session_state.working_items = updated_records
        st.rerun()

    # --- TAX CHOICES MATRIX (Allows Multi-Selection Option) ---
    st.sidebar.markdown("### 🏛️ Tax Configuration Options")
    tax_options_chosen = st.sidebar.multiselect("Select Tax Frameworks to Apply", ["Commercial Tax", "Withholding Tax (WHT)"], default=["Commercial Tax"])
    
    comm_tax_pct = st.sidebar.number_input("Commercial Tax (%)", min_value=0.0, value=5.0) if "Commercial Tax" in tax_options_chosen else 0.0
    wht_tax_pct = st.sidebar.number_input("Withholding Tax (%)", min_value=0.0, value=2.0) if "Withholding Tax (WHT)" in tax_options_chosen else 0.0

    # Calculate Totals
    gross_subtotal = sum([float(item.get("Total Price") or 0.0) for item in st.session_state.working_items if item.get("is_sub")])
    
    calculated_comm_tax = gross_subtotal * (comm_tax_pct / 100.0)
    calculated_wht_tax = gross_subtotal * (wht_tax_pct / 100.0)
    
    # Combined calculations: Comm tax adds up liability, WHT reduces payment retention lines
    grand_total_calculated = gross_subtotal + calculated_comm_tax - calculated_wht_tax

    st.sidebar.markdown(f"**Subtotal:** {currency_symbol}{gross_subtotal:,.2f}")
    if comm_tax_pct > 0: st.sidebar.markdown(f"**Comm Tax:** {currency_symbol}{calculated_comm_tax:,.2f}")
    if wht_tax_pct > 0: st.sidebar.markdown(f"**WHT Drawdown:** -{currency_symbol}{calculated_wht_tax:,.2f}")
    st.sidebar.markdown(f"### **Grand Total:** {currency_symbol}{grand_total_calculated:,.2f}")

    if st.button("🖨️ Compile Official Corporate PDF Engine Asset"):
        logo_html = f'<img src="{st.session_state.default_logo_base64}" style="max-height:65px;">' if st.session_state.default_logo_base64 else '<h2>ARK PREMIUM SOLUTION</h2>'

        # Build dynamic HTML Table Rows
        table_rows_html = ""
        for item in st.session_state.working_items:
            if not item.get("is_sub", False):
                table_rows_html += f'''
                <tr style="background-color: #f8fafc; font-weight: 600; border-top: 1px solid #e2e8f0;">
                    <td style="text-align: center; padding: 8px;">{item.get("No", "")}</td>
                    <td colspan="5" style="padding: 8px; color:#1e293b;">{item.get("Description", "")}</td>
                </tr>
                '''
            else:
                raw_price = float(item.get("Unit Price") or 0.0)
                qty = float(item.get("Qty") or 0)
                
                # Check for FOC logic inclusion
                if raw_price == 0.0:
                    unit_p_str = '<span style="color:#059669; font-weight:bold; background:#ecfdf5; padding:2px 5px; border-radius:3px;">FOC</span>'
                    total_p_str = '<span style="color:#059669; font-weight:bold; background:#ecfdf5; padding:2px 5px; border-radius:3px;">FOC</span>'
                else:
                    calc_unit = (float(item.get("Calculated Unit Price Base") or 0.0)) * conversion_multiplier
                    calc_total = float(item.get("Total Price") or 0.0)
                    unit_p_str = f"{currency_symbol}{calc_unit:,.2f}"
                    total_p_str = f"{currency_symbol}{calc_total:,.2f}"

                table_rows_html += f'''
                <tr>
                    <td style="text-align: center; padding: 8px;">{item.get("No", "")}</td>
                    <td style="font-family: monospace; padding: 8px;">{item.get("Part Number", "")}</td>
                    <td style="padding: 8px; font-style: italic;">{item.get("Description", "")}</td>
                    <td style="text-align: center; padding: 8px;">{qty:,.0f}</td>
                    <td style="text-align: right; padding: 8px;">{unit_p_str}</td>
                    <td style="text-align: right; padding: 8px; font-weight: 600;">{total_p_str}</td>
                </tr>
                '''

        # Dynamic Tax rows rendering for calculation details
        tax_rows_markup = ""
        if comm_tax_pct > 0:
            tax_rows_markup += f'<tr><td style="padding:4px 0; color:#475569;">Commercial Tax ({comm_tax_pct}%):</td><td style="text-align:right; padding:4px 0; font-weight:600;">{currency_symbol}{calculated_comm_tax:,.2f}</td></tr>'
        if wht_tax_pct > 0:
            tax_rows_markup += f'<tr><td style="padding:4px 0; color:#475569;">Withholding Tax (WHT {wht_tax_pct}%):</td><td style="text-align:right; padding:4px 0; font-weight:600; color:#b91c1c;">-{currency_symbol}{calculated_wht_tax:,.2f}</td></tr>'

        sig_img_markup = f'<img src="{current_user["signature_b64"]}" style="max-height:55px; display:block; margin-top:5px;">' if current_user.get("signature_b64") else '<div style="height:45px; color:#cbd5e1; font-style:italic;">Signature Pending</div>'

        html_document = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4; margin: 15mm;
                    @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-family: Arial; font-size: 8pt; color: #64748b; }}
                }}
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1e293b; font-size: 9pt; line-height: 1.5; }}
                .header-container {{ text-align: center; margin-bottom: 15px; }}
                .header-address {{ font-size: 8pt; color: #475569; line-height: 1.4; }}
                .brand-title {{ font-weight: bold; color: #00a8e8; font-size: 12pt; margin-bottom: 2px; }}
                .divider {{ border-bottom: 2px solid #00a8e8; margin: 10px 0; }}
                
                .meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
                .card-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px; font-size: 8.5pt; vertical-align: top; width: 50%; }}
                
                /* CHANGED HEADER COLOR TO MILD DARK BLUE */
                .data-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                .data-table th {{ background-color: #1e293b; color: white; font-weight: 500; font-size: 8pt; padding: 8px; text-transform: uppercase; text-align: left; }}
                .data-table td {{ font-size: 8.5pt; border-bottom: 1px solid #f1f5f9; }}
                
                .breakdown-container {{ display: table; width: 100%; margin-top: 15px; page-break-inside: avoid; }}
                .terms-box {{ display: table-cell; width: 55%; vertical-align: top; padding-right: 20px; }}
                .totals-box {{ display: table-cell; width: 45%; vertical-align: top; }}
                
                .totals-table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
                .grand-total-tr {{ background-color: #00a8e8; color: white; font-weight: bold; font-size: 10pt; }}
                
                .footer-terms {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 7.5pt; color: #475569; }}
                
                /* MOVED SIGNATORY SECTION TO LEFT SIDES OF THE DOCUMENT */
                .signatory-left-container {{ margin-top: 30px; text-align: left; page-break-inside: avoid; width: 260px; float: left; }}
                .sig-line {{ border-bottom: 1px dashed #cbd5e1; padding-bottom: 5px; margin-bottom: 5px; }}
            </style>
        </head>
        <body>
            <div class="header-container">
                <div class="header-logo">{logo_html}</div>
                <div class="header-address">
                    <div class="brand-title">ARK Premium Solution Limited</div>
                    <strong>ARK Corporate Office:</strong> 18th floor, Times City(office tower-2), Kamayut, Yangon, Myanmar.<br>
                    <strong>ARK Headquarters Office:</strong> 91, Shwe Taung Kyar 1st Street, Golden Valley 1, Bahan, Yangon, Myanmar.<br>
                    <strong>ARK Thailand Office:</strong> 1, Soi Ramkhamhaeng 118 Yaek 33-3, Saphan Sung 10240, Bangkok, Thailand.<br>
                    <strong>Web:</strong> www.arktechsolutions.net | <strong>Tel:</strong> +95 9 445830101
                </div>
            </div>

            <div class="divider"></div>
            <h2 style="font-size:16pt; font-weight:normal; margin:0 0 10px 0;">Commercial Quotation</h2>

            <table class="meta-table">
                <tr>
                    <td class="card-box" style="margin-right:10px;">
                        <strong style="color:#64748b; text-transform:uppercase; font-size:7.5pt;">Prepared For</strong><br>
                        <strong>{client_company}</strong><br>
                        Attn: {attn_person}<br>
                        Email: {attn_email} | Phone: {attn_phone}
                    </td>
                    <td class="card-box">
                        <strong style="color:#64748b; text-transform:uppercase; font-size:7.5pt;">Quotation References</strong><br>
                        <strong>Ref:</strong> {quotation_auto_gen}<br>
                        <strong>Project Name:</strong> {project_title}<br>
                        <strong>Date:</strong> {issue_date.strftime('%Y-%m-%d')} | <strong>Validity:</strong> {validity_bound}
                    </td>
                </tr>
            </table>

            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 6%; text-align: center;">No</th>
                        <th style="width: 20%;">Part Number</th>
                        <th style="width: 44%;">Functional Itemization /SPECIFICATIONS</th>
                        <th style="width: 6%; text-align: center;">Qty</th>
                        <th style="width: 12%; text-align: right;">Unit Price</th>
                        <th style="width: 12%; text-align: right;">Total Price</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>

            <div class="breakdown-container">
                <div class="terms-box">
                    <div class="footer-terms">
                        <strong style="font-size:8.5pt; color:#0f172a; display:block; margin-bottom:5px;">Commercial Logistics Terms & Governance Conditions:</strong>
                        <table style="width:100%; border-collapse:collapse; line-height:1.5;">
                            <tr><td style="width:15px; vertical-align:top; color:#00a8e8; font-weight:bold;">1.</td><td><strong>Delivery Lead-Time Windows:</strong> Equipment delivery windows are anticipated at approximately <strong>{lead_time_frame}</strong> following official project sign-off matrix rules.</td></tr>
                            <tr><td style="width:15px; vertical-align:top; color:#00a8e8; font-weight:bold;">2.</td><td><strong>Explicit Milestone Commitments:</strong> All relative monetary settlement routes must maintain strict compliance with: <strong>{payment_terms_desc}</strong>.</td></tr>
                            <tr><td style="width:15px; vertical-align:top; color:#00a8e8; font-weight:bold;">3.</td><td><strong>Additional Execution Scope and Framework Matrix Parameters:</strong><br>
                                <div style="margin-top:4px; padding-left:8px; border-left:2px solid #00a8e8; font-style:italic; color:#334155;">
                                    {terms_and_cond.replace('\n', '<br>')}
                                </div>
                            </td></tr>
                        </table>
                    </div>
                </div>
                
                <div class="totals-box">
                    <table class="totals-table">
                        <tr>
                            <td style="padding:4px 0; color:#64748b;">Gross Subtotal:</td>
                            <td style="text-align:right; padding:4px 0; font-weight:600;">{currency_symbol}{gross_subtotal:,.2f}</td>
                        </tr>
                        {tax_rows_markup}
                        <tr class="grand-total-tr">
                            <td style="padding:7px; color:white;">Grand Total:</td>
                            <td style="text-align:right; padding:7px; color:white; white-space:nowrap;">{currency_symbol}{grand_total_calculated:,.2f}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <div class="signatory-left-container">
                <div class="sig-line">
                    <span style="font-size:7.5pt; font-weight:bold; color:#64748b; text-transform:uppercase;">Issued & Authorized By:</span>
                    {sig_img_markup}
                </div>
                <div style="font-weight:bold; color:#0f172a; margin-top:3px;">{current_user.get("name", "Authorized Signatory")}</div>
                <div style="color:#475569; font-size:8pt;">{current_user.get("designation", "Account Operations Manager")}</div>
                <div style="color:#64748b; font-size:7.5pt;">
                    Email: {current_user["email"]}<br>
                    Phone: {current_user.get("phone", "N/A")}
                </div>
            </div>
            <div style="clear:both;"></div>
        </body>
        </html>
        """
        
        pdf_filename = f"ARK_Quotation_{quotation_auto_gen}.pdf"
        try:
            HTML(string=html_document).write_pdf(pdf_filename)
            with open(pdf_filename, "rb") as f:
                st.sidebar.download_button("📥 Download Finalized PDF Quote Asset", data=f.read(), file_name=pdf_filename, mime="application/pdf")
            st.sidebar.success("🎉 PDF Compiled Successfully!")
        except Exception as e:
            st.error(f"Engine compilation failure: {e}")
