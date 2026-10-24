import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

output_dir = os.path.join(os.path.dirname(__file__), 'sample_invoices')
os.makedirs(output_dir, exist_ok=True)

invoices_data = [
    {
        "filename": "01_valid_standard_invoice",
        "title": "STANDARD VALID INVOICE",
        "invoice_number": "INV-2024-1001",
        "date": "2024-09-01",
        "due_date": "2024-09-30",
        "vendor": "Apex Cloud Systems LLC",
        "vendor_address": "500 Silicon Way, Tech Park, CA",
        "customer": "InvoShield Global Enterprise",
        "customer_address": "742 Evergreen Terrace, Sector 7",
        "gst": "27AAAPL1234C1ZV",
        "po": "PO-9001",
        "items": [
            ("Cloud Hosting Platform Subscription (Monthly)", "1", "1000.00", "1000.00"),
            ("Advanced DDoS Protection & WAF Gateway", "1", "200.00", "200.00")
        ],
        "subtotal": "1200.00",
        "tax": "120.00",
        "discount": "20.00",
        "total": "1300.00",
        "notes": "Standard approved vendor contract. Math verified: $1200 + $120 - $20 = $1300."
    },
    {
        "filename": "02_exact_duplicate_invoice",
        "title": "EXACT DUPLICATE INVOICE (Test Duplicate Engine)",
        "invoice_number": "INV-2024-1001",  # Same number
        "date": "2024-09-01",
        "due_date": "2024-09-30",
        "vendor": "Apex Cloud Systems LLC",  # Same vendor
        "vendor_address": "500 Silicon Way, Tech Park, CA",
        "customer": "InvoShield Global Enterprise",
        "customer_address": "742 Evergreen Terrace, Sector 7",
        "gst": "27AAAPL1234C1ZV",
        "po": "PO-9001",
        "items": [
            ("Cloud Hosting Platform Subscription (Monthly)", "1", "1000.00", "1000.00"),
            ("Advanced DDoS Protection & WAF Gateway", "1", "200.00", "200.00")
        ],
        "subtotal": "1200.00",
        "tax": "120.00",
        "discount": "20.00",
        "total": "1300.00",  # Same amount
        "notes": "CRITICAL: Exact duplicate of Invoice #INV-2024-1001. RapidFuzz should score 95-100% Highly Likely Duplicate."
    },
    {
        "filename": "03_near_duplicate_fuzzy_match",
        "title": "FUZZY NEAR-DUPLICATE INVOICE",
        "invoice_number": "INV-2024-1001-A",  # Near match
        "date": "2024-09-01",
        "due_date": "2024-09-30",
        "vendor": "Apex Cloud Systems International",  # Slight name variation
        "vendor_address": "500 Silicon Way, Tech Park, CA",
        "customer": "InvoShield Global",
        "customer_address": "742 Evergreen Terrace, Sector 7",
        "gst": "27AAAPL1234C1ZV",
        "po": "PO-9001",
        "items": [
            ("Cloud Infrastructure & Network Licensing", "1", "1200.00", "1200.00")
        ],
        "subtotal": "1200.00",
        "tax": "100.00",
        "discount": "0.00",
        "total": "1300.00",
        "notes": "Near-duplicate test. RapidFuzz token matching will detect high similarity (~80-88% Possible Duplicate)."
    },
    {
        "filename": "04_high_risk_fraud_anomaly",
        "title": "HIGH-RISK FRAUD ANOMALY INVOICE",
        "invoice_number": "INV-ANOMALY-999",
        "date": "2030-12-15",  # Future date anomaly!
        "due_date": "2030-12-31",
        "vendor": "Apex Cloud Systems LLC",
        "vendor_address": "Unknown Offshore Post Office Box 88",
        "customer": "InvoShield Global Enterprise",
        "customer_address": "742 Evergreen Terrace, Sector 7",
        "gst": "INVALID_GST_777",  # Format anomaly
        "po": "PO-UNAPPROVED",
        "items": [
            ("Enterprise High Frequency GPU Cluster Reservation", "1", "60000.00", "60000.00"),
            ("Expedited Offshore Server Deployment Fee", "1", "5000.00", "5000.00")
        ],
        "subtotal": "65000.00",
        "tax": "5000.00",
        "discount": "0.00",
        "total": "95000.00",  # Extreme math conflict: 65k + 5k = 70k != 95k! Over 50x vendor spend spike!
        "notes": "ANOMALIES: Abnormal spend spike ($95,000), calculation mismatch ($70,000 vs $95,000), future date (2030)."
    },
    {
        "filename": "05_math_calculation_mismatch",
        "title": "ARITHMETIC ERROR INVOICE",
        "invoice_number": "INV-MATH-ERROR-505",
        "date": "2024-09-02",
        "due_date": "2024-09-25",
        "vendor": "Global Hardware Supplies Co",
        "vendor_address": "88 Industrial Way, Austin, TX",
        "customer": "InvoShield Global Enterprise",
        "customer_address": "742 Evergreen Terrace, Sector 7",
        "gst": "33BBBPK9876D1Z1",
        "po": "PO-8822",
        "items": [
            ("High Performance Rack Server Model X", "2", "2000.00", "4000.00"),
            ("Network Switch 48-Port Gigabit", "1", "500.00", "500.00")
        ],
        "subtotal": "4500.00",
        "tax": "450.00",
        "discount": "50.00",
        "total": "6200.00",  # Math error! Expected: 4500 + 450 - 50 = 4900.00, Billed: 6200.00
        "notes": "Math mismatch test: Subtotal ($4,500) + Tax ($450) - Discount ($50) = $4,900 != Billed ($6,200)."
    }
]

def generate_txt(inv, txt_path):
    content = f"""================================================================================
{inv['title']}
================================================================================
Invoice Number: {inv['invoice_number']}
Invoice Date:   {inv['date']}
Due Date:       {inv['due_date']}
PO Number:      {inv['po']}

VENDOR INFORMATION:
Vendor:         {inv['vendor']}
Address:        {inv['vendor_address']}
GST/Tax ID:     {inv['gst']}

CUSTOMER INFORMATION:
Customer:       {inv['customer']}
Address:        {inv['customer_address']}

LINE ITEMS:
--------------------------------------------------------------------------------
Description                                    Qty      Unit Price        Total
--------------------------------------------------------------------------------
"""
    for desc, qty, unit_p, tot_p in inv['items']:
        content += f"{desc:<45} {qty:>4}   ${unit_p:>10}   ${tot_p:>10}\n"
    
    content += f"""--------------------------------------------------------------------------------
Subtotal:       ${inv['subtotal']}
Tax Amount:     ${inv['tax']}
Discount:       ${inv['discount']}
Total Amount:   ${inv['total']}
================================================================================
Audit Notes: {inv['notes']}
================================================================================
"""
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(content)

def generate_pdf(inv, pdf_path):
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=12
    )
    normal_style = ParagraphStyle(
        'InvoiceNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )
    bold_style = ParagraphStyle(
        'InvoiceBold',
        parent=normal_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0f172a')
    )

    story = []
    
    # Title & Header
    story.append(Paragraph(f"<b>{inv['title']}</b>", title_style))
    story.append(Spacer(1, 10))

    # Meta Info Table
    meta_data = [
        [Paragraph(f"<b>Invoice Number:</b> {inv['invoice_number']}", normal_style),
         Paragraph(f"<b>Vendor:</b> {inv['vendor']}", normal_style)],
        [Paragraph(f"<b>Invoice Date:</b> {inv['date']}", normal_style),
         Paragraph(f"<b>Address:</b> {inv['vendor_address']}", normal_style)],
        [Paragraph(f"<b>Due Date:</b> {inv['due_date']}", normal_style),
         Paragraph(f"<b>GST / Tax ID:</b> {inv['gst']}", normal_style)],
        [Paragraph(f"<b>PO Number:</b> {inv['po']}", normal_style),
         Paragraph(f"<b>Customer:</b> {inv['customer']}", normal_style)],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # Items Table
    items_header = [
        Paragraph("<b>Description</b>", bold_style),
        Paragraph("<b>Qty</b>", bold_style),
        Paragraph("<b>Unit Price</b>", bold_style),
        Paragraph("<b>Total</b>", bold_style)
    ]
    items_rows = [items_header]
    for desc, qty, unit_p, tot_p in inv['items']:
        items_rows.append([
            Paragraph(desc, normal_style),
            Paragraph(qty, normal_style),
            Paragraph(f"${unit_p}", normal_style),
            Paragraph(f"${tot_p}", normal_style)
        ])

    items_table = Table(items_rows, colWidths=[300, 50, 95, 95])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # Financial Summary Table
    fin_data = [
        [Paragraph("<b>Subtotal:</b>", normal_style), Paragraph(f"${inv['subtotal']}", normal_style)],
        [Paragraph("<b>Tax Amount:</b>", normal_style), Paragraph(f"${inv['tax']}", normal_style)],
        [Paragraph("<b>Discount:</b>", normal_style), Paragraph(f"${inv['discount']}", normal_style)],
        [Paragraph("<b>Total Amount:</b>", bold_style), Paragraph(f"<b>${inv['total']}</b>", bold_style)],
    ]
    fin_table = Table(fin_data, colWidths=[120, 100])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
    ]))
    
    # Wrap in right-aligned container
    container = Table([[Paragraph(f"<i>Notes: {inv['notes']}</i>", normal_style), fin_table]], colWidths=[320, 220])
    container.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(container)

    doc.build(story)

# Generate all individual and master files
all_invoices_text = ""
for inv in invoices_data:
    txt_file = os.path.join(output_dir, f"{inv['filename']}.txt")
    pdf_file = os.path.join(output_dir, f"{inv['filename']}.pdf")
    
    generate_txt(inv, txt_file)
    generate_pdf(inv, pdf_file)
    
    with open(txt_file, 'r', encoding='utf-8') as f:
        all_invoices_text += f.read() + "\n\n" + ("="*80) + "\n\n"

# Write master combined file
master_path = os.path.join(output_dir, "ALL_INVOICE_TYPES_COMBINED.txt")
with open(master_path, 'w', encoding='utf-8') as f:
    f.write(all_invoices_text)

print(f"Successfully generated {len(invoices_data)} PDF and TXT invoice test sets in {output_dir}")
print(f"Master combined file written to {master_path}")
