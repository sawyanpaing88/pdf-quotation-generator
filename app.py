import streamlit as st
import pandas as pd
import PyPDF2
import re
import base64
from weasyprint import HTML

# Set page configuration
st.set_page_config(page_title="Advanced Quotation Builder", page_icon="📝", layout="wide")

# Initialize Session States for Dynamic Table
if "line_items" not in st.session_state:
    st.session_state.line_items = pd.DataFrame(columns=[
        "No", "Model/Part Number", "Description", "Qty", "Unit", "Unit Price", "Total Price"
    ])

st.title("📝 Enterprise Quotation Generator")
st.write("Upload a vendor sheet, set margins, customize line items, and export a beautiful client-facing PDF quote.")

# ==========================================
# SIDEBAR - BRANDING & FINANCIAL SETTINGS
# ==========================================
st.sidebar.header("🏢 Branding & Header Settings")
company_name = st.sidebar.text_input("Your Company Name", "Global Tech Solutions Ltd.")
company_address = st.sidebar.text_area("Company Address", "123 Business Road, Suite 400\nYangon, Myanmar")
client_name = st.sidebar.text_input("Client Name / Company", "Acme Corporation")
quote_number = st.sidebar.text_input("Quote Reference #", "QT-2026-001")

logo_file = st.sidebar.file_uploader("Upload Header Logo (PNG/JPG)", type=["png", "jpg", "jpeg"])

st.sidebar.header("💰 Financial Controls")
currency = st.sidebar.selectbox("Currency Option", ["USD", "MMK"])
currency_symbol = "$" if currency == "USD" else "Ks "
margin_pct = st.sidebar.number_input("Default Margin Percentage (%)", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
tax_pct = st.sidebar.number_input("Tax / VAT Percentage (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.5)

# ==========================================
# MAIN LAYOUT - SPLIT WORKSPACE
# ==========================================
col1, col2 = st.columns([1, 1])

# --- LEFT COLUMN: DATA INGESTION ---
with col1:
    st.header("1. Data Ingestion & Extraction")
    uploaded_file = st.file_uploader("Upload Vendor PDF Cost Sheet", type=["pdf"])
    
    if uploaded_file is not None and st.button("Extract & Populate Line Items"):
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            extracted_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
            
            # Simple line parsing heuristic to look for prices/parts
            lines = extracted_text.split('\n')
            new_rows = []
            row_idx = 1
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Look for lines containing numeric cost patterns
                prices = re.findall(r'\b\d+[,\.]\d{2}\b|\b\d{3,}\b', line)
                if prices and len(line) > 10:
                    part_no = line.split()[0] if len(line.split()) > 0 else f"PART-{row_idx:03d}"
                    desc = line[len(part_no):].strip()
                    try:
                        cost = float(prices[-1].replace(',', ''))
                    except:
                        cost = 100.0
                    
                    # Cost / (1 - Margin) Formula
                    margin_dec = margin_pct / 100.0
                    unit_price = cost / (1 - margin_dec) if margin_dec < 1 else cost
                    
                    new_rows.append({
                        "No": str(row_idx),
                        "Model/Part Number": part_no,
                        "Description": desc[:60] if desc else "Vendor Extracted Item",
                        "Qty": 1,
                        "Unit": "Pcs",
                        "Unit Price": round(unit_price, 2),
                        "Total Price": round(unit_price, 2)
                    })
                    row_idx += 1
            
            if new_rows:
                st.session_state.line_items = pd.DataFrame(new_rows)
                st.success(f"Successfully extracted {len(new_rows)} items from PDF!")
            else:
                st.warning("Could not automatically structure lines. Added a template row.")
                st.session_state.line_items = pd.DataFrame([{
                    "No": "1", "Model/Part Number": "MOD-001", "Description": "Sample Item", "Qty": 1, "Unit": "Pcs", "Unit Price": 100.0, "Total Price": 100.0
                }])
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    # Section for Service Additions
    st.subheader("🛠️ Add Standard Service Adjustments")
    prof_desc = st.text_input("Professional Service Description", "Professional Implementation & Configuration Services")
    prof_price = st.number_input("Professional Service Price", min_value=0.0, value=0.0)
    
    maint_desc = st.text_input("Maintenance Service Description", "Annual Maintenance & SLA Agreement")
    maint_price = st.number_input("Maintenance Service Price", min_value=0.0, value=0.0)
    
    if st.button("Append Adjustments to Table"):
        df = st.session_state.line_items
        next_no = str(len(df) + 1)
        
        new_items = []
        if prof_price > 0:
            new_items.append({"No": next_no, "Model/Part Number": "SRV-PROF", "Description": prof_desc, "Qty": 1, "Unit": "Lot", "Unit Price": prof_price, "Total Price": prof_price})
            next_no = str(int(next_no) + 1)
        if maint_price > 0:
            new_items.append({"No": next_no, "Model/Part Number": "SRV-MAINT", "Description": maint_desc, "Qty": 1, "Unit": "Yr", "Unit Price": maint_price, "Total Price": maint_price})
            
        if new_items:
            st.session_state.line_items = pd.concat([df, pd.DataFrame(new_items)], ignore_index=True)
            st.success("Adjustments appended!")

# --- RIGHT COLUMN: INTERACTIVE MODIFICATION ---
with col2:
    st.header("2. Modify Line Items Line-by-Line")
    st.write("You can directly edit any cell in the table below:")
    
    # Editable Data Grid Configured with User Columns
    edited_df = st.data_editor(
        st.session_state.line_items,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "No": st.column_config.TextColumn("No", width="small"),
            "Model/Part Number": st.column_config.TextColumn("Model/Part Number"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Qty": st.column_config.NumberColumn("Qty", min_value=1, default=1),
            "Unit": st.column_config.TextColumn("Unit", default="Pcs"),
            "Unit Price": st.column_config.NumberColumn("Unit Price", format=f"{currency_symbol}%.2f"),
            "Total Price": st.column_config.NumberColumn("Total Price", format=f"{currency_symbol}%.2f", disabled=True),
        }
    )
    
    # Auto-calculate Totals when changes occur
    if not edited_df.empty:
        edited_df["Qty"] = pd.to_numeric(edited_df["Qty"]).fillna(1)
        edited_df["Unit Price"] = pd.to_numeric(edited_df["Unit Price"]).fillna(0)
        edited_df["Total Price"] = edited_df["Qty"] * edited_df["Unit Price"]
        st.session_state.line_items = edited_df

    # Financial Summary Blocks
    subtotal = edited_df["Total Price"].sum() if not edited_df.empty else 0.0
    tax_amt = subtotal * (tax_pct / 100.0)
    grand_total = subtotal + tax_amt
    
    st.markdown("---")
    st.markdown(f"### **Subtotal:** {currency_symbol}{subtotal:,.2f}")
    st.markdown(f"### **Tax ({tax_pct}%):** {currency_symbol}{tax_amt:,.2f}")
    st.markdown(f"## **Grand Total:** {currency_symbol}{grand_total:,.2f}")

# ==========================================
# EXPORT AND PDF COMPILATION ENGINE
# ==========================================
st.header("🖨️ Export & Download Quote")

if st.button("Generate Official PDF Document"):
    if edited_df.empty:
        st.error("No data available to print. Please add at least one line item.")
    else:
        # Logo handling inside HTML environment via base64 encoding
        logo_html = ""
        if logo_file is not None:
            bytes_data = logo_file.getvalue()
            base64_img = base64.b64encode(bytes_data).decode("utf-8")
            logo_html = f'<img src="data:image/png;base64,{base64_img}" style="max-height: 80px; max-width: 250px; object-fit: contain;">'
        else:
            logo_html = f'<h1 style="color:#1e3a8a; margin:0; font-size: 24pt;">{company_name}</h1>'

        # Compile HTML Document Rows Dynamically
        table_rows_html = ""
        for _, r in edited_df.iterrows():
            table_rows_html += f'''
            <tr>
                <td style="text-align: center;">{r["No"]}</td>
                <td>{r["Model/Part Number"]}</td>
                <td>{r["Description"]}</td>
                <td style="text-align: center;">{r["Qty"]}</td>
                <td style="text-align: center;">{r["Unit"]}</td>
                <td style="text-align: right;">{currency_symbol}{r["Unit Price"]:,.2f}</td>
                <td style="text-align: right; font-weight: bold;">{currency_symbol}{r["Total Price"]:,.2f}</td>
            </tr>
            '''

        # Premium CSS Printable Page Formatting Definition
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4;
                    margin: 20mm 15mm;
                    background-color: #ffffff;
                    @bottom-right {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        font-size: 9pt;
                        color: #6b7280;
                    }}
                }}
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #1f2937;
                    margin: 0;
                    padding: 0;
                    font-size: 10pt;
                    line-height: 1.5;
                }}
                .header-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 30px;
                }}
                .header-table td {{
                    vertical-align: top;
                    border: none;
                    padding: 0;
                }}
                .company-details {{
                    text-align: right;
                    font-size: 9pt;
                    color: #4b5563;
                }}
                .quote-title-container {{
                    border-bottom: 3px solid #1e3a8a;
                    padding-bottom: 10px;
                    margin-bottom: 25px;
                }}
                .quote-title {{
                    font-size: 22pt;
                    color: #1e3a8a;
                    font-weight: bold;
                    text-transform: uppercase;
                    margin: 0;
                }}
                .metadata-table {{
                    width: 100%;
                    margin-bottom: 30px;
                }}
                .metadata-table td {{
                    width: 50%;
                    vertical-align: top;
                    padding: 0;
                }}
                .meta-box {{
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    padding: 12px;
                    margin-right: 10px;
                    min-height: 80px;
                }}
                .meta-box-right {{
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 12px;
                    margin-left: 10px;
                    min-height: 80px;
                }}
                .section-heading {{
                    font-size: 10pt;
                    font-weight: bold;
                    color: #475569;
                    text-transform: uppercase;
                    margin-bottom: 5px;
                    margin-top: 0;
                }}
                .items-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 30px;
                }}
                .items-table th {{
                    background-color: #1e3a8a;
                    color: #ffffff;
                    font-weight: bold;
                    text-transform: uppercase;
                    font-size: 9pt;
                    padding: 10px 8px;
                    border: 1px solid #1e3a8a;
                }}
                .items-table td {{
                    padding: 9px 8px;
                    border-bottom: 1px solid #e2e8f0;
                    font-size: 9.5pt;
                }}
                .items-table tr:nth-child(even) {{
                    background-color: #f8fafc;
                }}
                .totals-container {{
                    width: 100%;
                    margin-top: 20px;
                }}
                .totals-table {{
                    width: 45%;
                    margin-left: auto;
                    border-collapse: collapse;
                }}
                .totals-table td {{
                    padding: 8px;
                    font-size: 10pt;
                }}
                .grand-total-row {{
                    background-color: #1e3a8a;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12pt;
                }}
                .grand-total-row td {{
                    padding: 12px 8px;
                }}
                .terms {{
                    margin-top: 50px;
                    font-size: 8.5pt;
                    color: #64748b;
                    border-top: 1px solid #e2e8f0;
                    padding-top: 15px;
                }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td>{logo_html}</td>
                    <td class="company-details">
                        <strong style="font-size: 11pt; color: #1e3a8a;">{company_name}</strong><br>
                        {company_address.replace('\n', '<br>')}
                    </td>
                </tr>
            </table>

            <div class="quote-title-container">
                <h1 class="quote-title">Commercial Quotation</h1>
            </div>

            <table class="metadata-table">
                <tr>
                    <td>
                        <div class="meta-box">
                            <div class="section-heading">Prepared For</div>
                            <strong>{client_name}</strong>
                        </div>
                    </td>
                    <td>
                        <div class="meta-box-right">
                            <div class="section-heading">Quotation Metadata</div>
                            <strong>Quote Ref:</strong> {quote_number}<br>
                            <strong>Date:</strong> 2026-06-24<br>
                            <strong>Currency:</strong> {currency}
                        </div>
                    </td>
                </tr>
            </table>

            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width: 5%; text-align: center;">No</th>
                        <th style="width: 20%;">Model/Part Number</th>
                        <th style="width: 35%;">Description</th>
                        <th style="width: 8%; text-align: center;">Qty</th>
                        <th style="width: 8%; text-align: center;">Unit</th>
                        <th style="width: 12%; text-align: right;">Unit Price</th>
                        <th style="width: 12%; text-align: right;">Total Price</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>

            <div class="totals-container">
                <table class="totals-table">
                    <tr>
                        <td style="text-align: left; color: #475569;">Subtotal:</td>
                        <td style="text-align: right; font-weight: bold;">{currency_symbol}{subtotal:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="text-align: left; color: #475569;">Tax/VAT ({tax_pct}%):</td>
                        <td style="text-align: right; font-weight: bold;">{currency_symbol}{tax_amt:,.2f}</td>
                    </tr>
                    <tr class="grand-total-row">
                        <td style="text-align: left;">Grand Total:</td>
                        <td style="text-align: right;">{currency_symbol}{grand_total:,.2f}</td>
                    </tr>
                </table>
            </div>

            <div class="terms">
                <strong>Terms & Conditions:</strong><br>
                1. Prices are valid for 30 days from the date of issuance.<br>
                2. Delivery schedules will be finalized upon confirmation of order.<br>
                3. Payment terms are subject to standard corporate agreement terms.
            </div>
        </body>
        </html>
        """
        
        output_pdf_path = "generated_quotation.pdf"
        HTML(string=html_content).write_pdf(output_pdf_path)
        
        with open(output_pdf_path, "rb") as f:
            pdf_bytes = f.read()
            
        st.download_button(
            label="📥 Download Official Quotation PDF",
            data=pdf_bytes,
            file_name=f"Quotation_{quote_number}.pdf",
            mime="application/pdf"
        )
        st.success("PDF successfully constructed! Click the download button above.")