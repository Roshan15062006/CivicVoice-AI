!pip -q install -U gradio pandas plotly

import os
import uuid
import re
import pandas as pd
import plotly.express as px
import gradio as gr

from datetime import datetime
from difflib import SequenceMatcher
from google.colab import drive

# =========================================================
# 1. GOOGLE DRIVE DATABASE
# =========================================================

drive.mount("/content/drive")

FOLDER = "/content/drive/MyDrive/CivicVoice"
CSV_FILE = os.path.join(FOLDER, "civicvoice_complaints.csv")
AUDIT_FILE = os.path.join(FOLDER, "civicvoice_audit_log.csv")

os.makedirs(FOLDER, exist_ok=True)

COLUMNS = [
    "Complaint ID",
    "Complaint",
    "Category",
    "Priority",
    "Status",
    "Reported At",
    "Location"
]

STATUSES = ["Pending Review", "In Progress", "Resolved"]

CATEGORIES = [
    "Road Damage",
    "Traffic",
    "Streetlight",
    "Water Leakage",
    "Garbage",
    "Other Civic Issue"
]

AUDIT_COLUMNS = [
    "Timestamp",
    "Complaint ID",
    "Action",
    "Previous Status",
    "New Status",
    "Details"
]

# Migrate the existing local CSV if Drive has no database yet.
LOCAL_CSV = "/content/civicvoice_complaints.csv"

if not os.path.exists(CSV_FILE) and os.path.exists(LOCAL_CSV):
    import shutil
    shutil.copy2(LOCAL_CSV, CSV_FILE)

def load_database():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        try:
            df = pd.read_csv(CSV_FILE)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS].fillna("")

    return df

def save_database(df):
    df = df[COLUMNS].fillna("")
    df.to_csv(CSV_FILE, index=False)

def load_audit():
    if os.path.exists(AUDIT_FILE) and os.path.getsize(AUDIT_FILE) > 0:
        try:
            df = pd.read_csv(AUDIT_FILE)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    for col in AUDIT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[AUDIT_COLUMNS].fillna("")

def save_audit(df):
    df[AUDIT_COLUMNS].to_csv(AUDIT_FILE, index=False)

def log_action(complaint_id, action, old_status="",
               new_status="", details=""):
    audit = load_audit()

    record = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Complaint ID": complaint_id,
        "Action": action,
        "Previous Status": old_status,
        "New Status": new_status,
        "Details": details
    }

    audit = pd.concat(
        [audit, pd.DataFrame([record])],
        ignore_index=True
    )
    save_audit(audit)

# Initialize/migrate database without deleting existing records.
database = load_database()
save_database(database)

if not os.path.exists(AUDIT_FILE):
    save_audit(pd.DataFrame(columns=AUDIT_COLUMNS))

print("Database:", CSV_FILE)
print("Existing complaints:", len(database))

# =========================================================
# 2. SLA MONITORING
# =========================================================

def calculate_sla(df):
    result = df.copy()

    if result.empty:
        result["Hours Open"] = pd.Series(dtype=float)
        result["SLA Status"] = pd.Series(dtype=str)
        return result

    reported = pd.to_datetime(
        result["Reported At"],
        errors="coerce"
    )

    now = pd.Timestamp.now()
    hours = (now - reported).dt.total_seconds() / 3600

    result["Hours Open"] = hours.round(1)

    def sla_status(row):
        if row["Status"] == "Resolved":
            return "Resolved"

        if pd.isna(row["Hours Open"]):
            return "Unknown"

        if row["Status"] == "Pending Review":
            limit = 24
        elif row["Status"] == "In Progress":
            limit = 48
        else:
            return "Unknown"

        if row["Hours Open"] > limit:
            return "Overdue"

        return "Within SLA"

    result["SLA Status"] = result.apply(sla_status, axis=1)

    return result

# =========================================================
# 3. DUPLICATE COMPLAINT DETECTION
# =========================================================

def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(text.split())

def find_duplicates(df, threshold=0.65):
    matches = []

    records = df.to_dict("records")

    for i in range(len(records)):
        for j in range(i + 1, len(records)):

            a = records[i]
            b = records[j]

            if a["Category"] != b["Category"]:
                continue

            loc_a = normalize_text(a.get("Location", ""))
            loc_b = normalize_text(b.get("Location", ""))

            # Compare locations when both have been supplied.
            if loc_a and loc_b:
                if SequenceMatcher(None, loc_a, loc_b).ratio() < 0.7:
                    continue

            text_a = normalize_text(a["Complaint"])
            text_b = normalize_text(b["Complaint"])

            if not text_a or not text_b:
                continue

            score = SequenceMatcher(
                None, text_a, text_b
            ).ratio()

            if score >= threshold:
                matches.append({
                    "Complaint ID 1": a["Complaint ID"],
                    "Complaint ID 2": b["Complaint ID"],
                    "Category": a["Category"],
                    "Location": loc_a or loc_b or "Not provided",
                    "Similarity": round(score * 100, 1)
                })

    return pd.DataFrame(
        matches,
        columns=[
            "Complaint ID 1",
            "Complaint ID 2",
            "Category",
            "Location",
            "Similarity"
        ]
    )

# =========================================================
# 4. DASHBOARD DATA AND PLOTLY ANALYTICS
# =========================================================

def get_dashboard_data(search="", category="All", status="All"):

    df = load_database()
    filtered = df.copy()

    if category != "All":
        filtered = filtered[filtered["Category"] == category]

    if status != "All":
        filtered = filtered[filtered["Status"] == status]

    if str(search).strip():
        term = str(search).strip()

        mask = (
            filtered["Complaint ID"].astype(str).str.contains(
                term, case=False, na=False
            )
            |
            filtered["Complaint"].astype(str).str.contains(
                term, case=False, na=False
            )
            |
            filtered["Location"].astype(str).str.contains(
                term, case=False, na=False
            )
        )

        filtered = filtered[mask]

    total = len(df)
    high = int((df["Priority"] == "High").sum())
    normal = int((df["Priority"] == "Normal").sum())
    pending = int((df["Status"] == "Pending Review").sum())
    progress = int((df["Status"] == "In Progress").sum())
    resolved = int((df["Status"] == "Resolved").sum())

    # Category chart
    category_counts = (
        filtered["Category"]
        .value_counts()
        .rename_axis("Category")
        .reset_index(name="Count")
    )

    fig1 = px.bar(
        category_counts,
        x="Category",
        y="Count",
        text="Count",
        title="Complaints by Category"
    )

    fig1.update_layout(
        xaxis_title="Category",
        yaxis_title="Complaints",
        template="plotly_white"
    )

    # Priority chart
    priority_counts = (
        filtered["Priority"]
        .value_counts()
        .reindex(["High", "Normal"], fill_value=0)
        .rename_axis("Priority")
        .reset_index(name="Count")
    )

    fig2 = px.pie(
        priority_counts,
        names="Priority",
        values="Count",
        title="Priority Distribution",
        hole=0.35
    )

    fig2.update_layout(template="plotly_white")

    # Area analytics
    area_data = filtered.copy()
    area_data["Location"] = (
        area_data["Location"].replace("", "Location not provided")
    )

    area_counts = (
        area_data["Location"]
        .value_counts()
        .rename_axis("Location")
        .reset_index(name="Complaints")
    )

    fig3 = px.bar(
        area_counts,
        x="Location",
        y="Complaints",
        text="Complaints",
        title="Complaints by Area"
    )

    fig3.update_layout(
        template="plotly_white",
        xaxis_title="Area",
        yaxis_title="Complaints"
    )

    # SLA monitoring
    sla_df = calculate_sla(filtered)

    open_sla = sla_df[
        sla_df["Status"].isin(["Pending Review", "In Progress"])
    ]

    overdue = int((open_sla["SLA Status"] == "Overdue").sum())

    # Duplicate detection
    duplicate_df = find_duplicates(filtered)

    return (
        total, high, normal, pending, progress, resolved,
        overdue, fig1, fig2, fig3, filtered,
        sla_df, duplicate_df
    )

# =========================================================
# 5. REFRESH
# =========================================================

def refresh_dashboard(search, category, status):
    return get_dashboard_data(search, category, status)

# =========================================================
# 6. STATUS MANAGEMENT + AUDIT TRAIL
# =========================================================

def update_status(complaint_id, new_status,
                  search, category, status_filter):

    complaint_id = str(complaint_id).strip()
    df = load_database()

    if not complaint_id:
        message = "Please enter a Complaint ID."

    elif new_status not in STATUSES:
        message = "Invalid status."

    else:
        matches = df["Complaint ID"].astype(str) == complaint_id

        if not matches.any():
            message = "Complaint ID not found."

        else:
            index = df.index[matches][0]
            old_status = df.loc[index, "Status"]

            df.loc[index, "Status"] = new_status
            save_database(df)

            log_action(
                complaint_id,
                "Status Updated",
                old_status,
                new_status,
                "Administrator changed complaint status"
            )

            message = (
                f"Updated {complaint_id}: "
                f"{old_status} -> {new_status}"
            )

    return (
        message,
        *get_dashboard_data(search, category, status_filter)
    )

# =========================================================
# 7. MANUAL COMPLAINT REGISTRATION
# =========================================================

def add_complaint(description, category, priority, location,
                  search, category_filter, status_filter):

    description = str(description).strip()
    location = str(location).strip()

    if not description:
        message = "Please enter a complaint description."

    else:
        df = load_database()

        candidate = {
            "Complaint ID": "NEW",
            "Complaint": description,
            "Category": category,
            "Priority": priority,
            "Status": "Pending Review",
            "Reported At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Location": location
        }

        # Check for similar existing complaints.
        check_df = pd.concat(
            [df, pd.DataFrame([candidate])],
            ignore_index=True
        )

        duplicate_matches = find_duplicates(check_df)
        duplicate_matches = duplicate_matches[
            (duplicate_matches["Complaint ID 1"] == "NEW")
            |
            (duplicate_matches["Complaint ID 2"] == "NEW")
        ]

        if not duplicate_matches.empty:
            possible_id = duplicate_matches.iloc[0]["Complaint ID 1"]
            if possible_id == "NEW":
                possible_id = duplicate_matches.iloc[0]["Complaint ID 2"]

            similarity = duplicate_matches.iloc[0]["Similarity"]

            message = (
                f"Possible duplicate detected ({similarity}% similarity). "
                f"Check existing complaint {possible_id} before adding."
            )

        else:
            complaint_id = (
                "CV-" + datetime.now().strftime("%Y%m%d%H%M%S")
                + "-" + uuid.uuid4().hex[:4].upper()
            )

            candidate["Complaint ID"] = complaint_id

            df = pd.concat(
                [df, pd.DataFrame([candidate])],
                ignore_index=True
            )

            save_database(df)

            log_action(
                complaint_id,
                "Complaint Created",
                "",
                "Pending Review",
                "Manually registered by administrator"
            )

            message = f"Complaint successfully added. ID: {complaint_id}"

    return (
        message,
        *get_dashboard_data(search, category_filter, status_filter)
    )

# =========================================================
# 8. DUPLICATE SCAN
# =========================================================

def scan_duplicates():
    df = load_database()
    duplicates = find_duplicates(df)

    if duplicates.empty:
        message = "No likely duplicate complaints found."
    else:
        message = f"Found {len(duplicates)} possible duplicate pairs."

    return message, duplicates

# =========================================================
# 9. AUDIT LOG DISPLAY
# =========================================================

def refresh_audit():
    return load_audit()

# =========================================================
# 10. CSV EXPORTS
# =========================================================

def export_complaints(search, category, status):
    result = get_dashboard_data(search, category, status)
    filtered_df = result[10]

    path = "/content/CivicVoice_Complaints_Report.csv"
    filtered_df.to_csv(path, index=False)

    return path

def export_audit():
    path = "/content/CivicVoice_Audit_Report.csv"
    load_audit().to_csv(path, index=False)
    return path

# =========================================================
# 11. AUTOMATED SELF-TESTS
# =========================================================

def run_self_tests():

    results = []

    # Test database schema
    db = load_database()
    results.append((
        "Database schema",
        all(col in db.columns for col in COLUMNS)
    ))

    # Test SLA calculation
    sample = pd.DataFrame([{
        "Complaint ID": "TEST-SLA",
        "Complaint": "Test complaint",
        "Category": "Road Damage",
        "Priority": "High",
        "Status": "Pending Review",
        "Reported At": "2020-01-01 10:00:00",
        "Location": "Test Area"
    }])

    sla = calculate_sla(sample)
    results.append((
        "SLA overdue detection",
        sla.iloc[0]["SLA Status"] == "Overdue"
    ))

    # Test duplicate detection
    duplicate_sample = pd.DataFrame([
        {
            "Complaint ID": "TEST-1",
            "Complaint": "Large pothole on main road near college",
            "Category": "Road Damage",
            "Priority": "High",
            "Status": "Pending Review",
            "Reported At": "2026-11-08 10:00:00",
            "Location": "Test Area"
        },
        {
            "Complaint ID": "TEST-2",
            "Complaint": "Large pothole on main road near college",
            "Category": "Road Damage",
            "Priority": "Normal",
            "Status": "Pending Review",
            "Reported At": "2026-11-08 11:00:00",
            "Location": "Test Area"
        }
    ])

    duplicates = find_duplicates(duplicate_sample)

    results.append((
        "Duplicate detection",
        len(duplicates) > 0
    ))

    # Test Plotly analytics generation
    try:
        chart_data = get_dashboard_data()
        results.append((
            "Plotly chart generation",
            chart_data[7] is not None
            and chart_data[8] is not None
            and chart_data[9] is not None
        ))
    except Exception:
        results.append(("Plotly chart generation", False))

    # Test audit log schema
    audit = load_audit()
    results.append((
        "Audit log schema",
        all(col in audit.columns for col in AUDIT_COLUMNS)
    ))

    print("\n========== CIVICVOICE SELF-TEST ==========")

    for name, passed in results:
        print(("PASS" if passed else "FAIL") + " - " + name)

    print("------------------------------------------")
    print(f"Passed: {sum(x[1] for x in results)}/{len(results)}")
    print("Tests use sample data and do not modify real complaints.")
    print("==========================================\n")

    return results

run_self_tests()

# =========================================================
# 12. GRADIO ADMIN DASHBOARD
# =========================================================

with gr.Blocks() as admin:

    gr.Markdown("""
    # CivicVoice AI
    ## Advanced Administrator Dashboard

    Monitor, analyse and manage citizen complaints.
    """)

    gr.Markdown("### Complaint Overview")

    with gr.Row():
        total_box = gr.Number(label="Total Complaints", interactive=False)
        high_box = gr.Number(label="High Priority", interactive=False)
        normal_box = gr.Number(label="Normal Priority", interactive=False)

    with gr.Row():
        pending_box = gr.Number(label="Pending Review", interactive=False)
        progress_box = gr.Number(label="In Progress", interactive=False)
        resolved_box = gr.Number(label="Resolved", interactive=False)

    overdue_box = gr.Number(
        label="Overdue Complaints",
        interactive=False
    )

    gr.Markdown("### Complaint Analytics")

    with gr.Row():
        category_plot = gr.Plot(label="Complaints by Category")
        priority_plot = gr.Plot(label="Priority Distribution")

    area_plot = gr.Plot(label="Area-wise Complaint Analytics")

    gr.Markdown("### Search and Filter")

    with gr.Row():
        search_box = gr.Textbox(
            label="Search Complaint ID, Description or Location"
        )

        category_filter = gr.Dropdown(
            choices=["All"] + CATEGORIES,
            value="All",
            label="Category"
        )

        status_filter = gr.Dropdown(
            choices=["All"] + STATUSES,
            value="All",
            label="Status"
        )

    refresh_btn = gr.Button("Refresh Dashboard", variant="primary")

    gr.Markdown("### SLA Monitoring")

    sla_table = gr.Dataframe(
        label="Complaint SLA Status",
        interactive=False
    )

    gr.Markdown("### Duplicate Complaint Detection")

    duplicate_message = gr.Textbox(
        label="Duplicate Scan Result",
        interactive=False
    )

    duplicate_table = gr.Dataframe(
        label="Possible Duplicate Complaints",
        interactive=False
    )

    duplicate_scan_btn = gr.Button("Scan for Duplicate Complaints")

    gr.Markdown("### Complaint Status Management")

    with gr.Row():
        complaint_id_box = gr.Textbox(
            label="Complaint ID",
            placeholder="Enter exact complaint ID"
        )

        new_status_box = gr.Dropdown(
            choices=STATUSES,
            value="In Progress",
            label="New Status"
        )

    update_btn = gr.Button("Update Complaint Status")
    update_message = gr.Textbox(
        label="Status Update Result",
        interactive=False
    )

    gr.Markdown("### Manual Complaint Registration")

    manual_description = gr.Textbox(
        label="Complaint Description",
        lines=3
    )

    with gr.Row():
        manual_category = gr.Dropdown(
            choices=CATEGORIES,
            value="Other Civic Issue",
            label="Category"
        )

        manual_priority = gr.Dropdown(
            choices=["Normal", "High"],
            value="Normal",
            label="Priority"
        )

        manual_location = gr.Textbox(
            label="Area / Landmark",
            placeholder="Example: Jayanagar 4th Block"
        )

    add_btn = gr.Button("Register Complaint", variant="primary")

    add_message = gr.Textbox(
        label="Registration Result",
        interactive=False
    )

    gr.Markdown("### Citizen Complaint Records")

    complaint_table = gr.Dataframe(
        value=load_database(),
        interactive=False
    )

    gr.Markdown("### Complaint Audit Trail")

    audit_table = gr.Dataframe(
        value=load_audit(),
        interactive=False
    )

    audit_refresh_btn = gr.Button("Refresh Audit Trail")

    with gr.Row():
        export_btn = gr.Button("Export Complaints CSV")
        export_audit_btn = gr.Button("Export Audit Log CSV")

    complaint_download = gr.File(label="Complaint Report Download")
    audit_download = gr.File(label="Audit Report Download")

    # Dashboard output order
    dashboard_outputs = [
        total_box, high_box, normal_box,
        pending_box, progress_box, resolved_box,
        overdue_box,
        category_plot, priority_plot, area_plot,
        complaint_table, sla_table, duplicate_table
    ]

    filter_inputs = [
        search_box, category_filter, status_filter
    ]

    # Refresh events
    refresh_btn.click(
        refresh_dashboard,
        inputs=filter_inputs,
        outputs=dashboard_outputs
    )

    search_box.submit(
        refresh_dashboard,
        inputs=filter_inputs,
        outputs=dashboard_outputs
    )

    category_filter.change(
        refresh_dashboard,
        inputs=filter_inputs,
        outputs=dashboard_outputs
    )

    status_filter.change(
        refresh_dashboard,
        inputs=filter_inputs,
        outputs=dashboard_outputs
    )

    # Update status
    update_btn.click(
        update_status,
        inputs=[
            complaint_id_box,
            new_status_box,
            search_box,
            category_filter,
            status_filter
        ],
        outputs=[update_message] + dashboard_outputs
    )

    # Register manual complaint
    add_btn.click(
        add_complaint,
        inputs=[
            manual_description,
            manual_category,
            manual_priority,
            manual_location,
            search_box,
            category_filter,
            status_filter
        ],
        outputs=[add_message] + dashboard_outputs
    )

    # Duplicate scan
    duplicate_scan_btn.click(
        scan_duplicates,
        inputs=[],
        outputs=[duplicate_message, duplicate_table]
    )

    # Audit
    audit_refresh_btn.click(
        refresh_audit,
        inputs=[],
        outputs=[audit_table]
    )

    # Export
    export_btn.click(
        export_complaints,
        inputs=filter_inputs,
        outputs=[complaint_download]
    )

    export_audit_btn.click(
        export_audit,
        inputs=[],
        outputs=[audit_download]
    )

    # Initial dashboard load
    admin.load(
        refresh_dashboard,
        inputs=filter_inputs,
        outputs=dashboard_outputs
    )

    admin.load(
        refresh_audit,
        inputs=[],
        outputs=[audit_table]
    )

print("CivicVoice Advanced Dashboard starting...")

admin.launch(
    share=True,
    debug=True,
    theme=gr.themes.Soft()
)
