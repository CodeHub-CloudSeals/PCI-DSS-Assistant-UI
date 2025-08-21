import io
import json
from typing import List
import pandas as pd
import streamlit as st

# ------------------------------
# Page config
# ------------------------------
st.set_page_config(
    page_title="PCI DSS Compliance MVP (Single Screen)",
    page_icon="✅",
    layout="wide",
)

st.title("PCI DSS Compliance MVP — Single Screen Demo")
st.caption("Automates: Inventory → Scope → Controls → Remediation → Report")

# ------------------------------
# Demo inventory (used if no upload)
# ------------------------------
def demo_inventory_df() -> pd.DataFrame:
    data = [
        {
            "asset_id": "vm-001", "name": "checkout-api", "type": "vm",
            "environment": "prod", "region": "us-east1",
            "chd_present": True, "stores_chd": False, "processes_chd": True, "transmits_chd": True,
            "network_segment": "cde",
            "encryption_at_rest": True, "encryption_in_transit": False,
            "firewall_enabled": True, "logging_enabled": True, "owner": "payments-team",
        },
        {
            "asset_id": "sql-002", "name": "card-db", "type": "sql",
            "environment": "prod", "region": "us-central1",
            "chd_present": True, "stores_chd": True, "processes_chd": False, "transmits_chd": False,
            "network_segment": "cde",
            "encryption_at_rest": False, "encryption_in_transit": True,
            "firewall_enabled": True, "logging_enabled": True, "owner": "dba",
        },
        {
            "asset_id": "lb-003", "name": "edge-lb", "type": "load_balancer",
            "environment": "prod", "region": "europe-west1",
            "chd_present": False, "stores_chd": False, "processes_chd": False, "transmits_chd": True,
            "network_segment": "dmz",
            "encryption_at_rest": True, "encryption_in_transit": True,
            "firewall_enabled": False, "logging_enabled": False, "owner": "platform",
        },
        {
            "asset_id": "vm-004", "name": "marketing-site", "type": "vm",
            "environment": "prod", "region": "us-east1",
            "chd_present": False, "stores_chd": False, "processes_chd": False, "transmits_chd": False,
            "network_segment": "public",
            "encryption_at_rest": True, "encryption_in_transit": True,
            "firewall_enabled": True, "logging_enabled": True, "owner": "marketing",
        },
    ]
    return pd.DataFrame(data)

# ------------------------------
# Uploads + parsing
# ------------------------------
with st.expander("Uploads (optional) — Inventory & DLP", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        inv_file = st.file_uploader("Inventory (CSV or JSON)", type=["csv", "json"])
        st.caption("Expected cols (min): asset_id, name, type, environment, region, "
                   "chd_present, stores_chd, processes_chd, transmits_chd, network_segment, "
                   "encryption_at_rest, encryption_in_transit, firewall_enabled, logging_enabled, owner")
    with c2:
        dlp_file = st.file_uploader("DLP findings CSV (asset_id, sensitive_found)", type=["csv"])

def parse_inventory_upload(upload) -> pd.DataFrame:
    if upload is None:
        return demo_inventory_df()
    name = upload.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(upload)
    if name.endswith(".json"):
        raw = json.load(upload)
        return pd.json_normalize(raw)
    raise ValueError("Unsupported file type. Upload CSV or JSON.")

def merge_dlp_findings(inv_df: pd.DataFrame, dlp_upload) -> pd.DataFrame:
    df = inv_df.copy()
    if "sensitive_found" not in df.columns:
        df["sensitive_found"] = False
    if dlp_upload is None:
        return df
    dlp = pd.read_csv(dlp_upload)
    if not {"asset_id", "sensitive_found"}.issubset(dlp.columns):
        st.warning("DLP file must have columns: asset_id, sensitive_found. Ignoring DLP upload.")
        return df
    df = df.merge(dlp[["asset_id", "sensitive_found"]],
                  on="asset_id", how="left", suffixes=("", "_dlp"))
    df["sensitive_found"] = df["sensitive_found_dlp"].fillna(df["sensitive_found"]).fillna(False)
    return df.drop(columns=[c for c in df.columns if c.endswith("_dlp")])

try:
    inv_df = parse_inventory_upload(inv_file)
    inv_df = merge_dlp_findings(inv_df, dlp_file)
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# ------------------------------
# Scope Classifier
# ------------------------------
PCI_SCOPE_NOTE = (
    "Scoping rule (simplified): Systems that store, process, or transmit CHD, "
    "and systems that can impact the security of the CDE, are in scope."
)

def classify_scope(inv_df: pd.DataFrame) -> pd.DataFrame:
    df = inv_df.copy()
    # in-scope if any CHD flags OR in CDE/DMZ OR DLP found CHD
    in_scope = (
        df.get("stores_chd", False).fillna(False)
        | df.get("processes_chd", False).fillna(False)
        | df.get("transmits_chd", False).fillna(False)
        | df.get("chd_present", False).fillna(False)
        | df.get("sensitive_found", False).fillna(False)
        | df.get("network_segment", "").astype(str).str.lower().isin(["cde", "dmz"])
    )
    df["in_scope"] = in_scope

    def reason(row) -> str:
        r = []
        if row.get("stores_chd"): r.append("stores CHD")
        if row.get("processes_chd"): r.append("processes CHD")
        if row.get("transmits_chd"): r.append("transmits CHD")
        if row.get("chd_present"): r.append("CHD present")
        seg = str(row.get("network_segment", "")).lower()
        if seg in ["cde", "dmz"]: r.append(f"in {seg} segment")
        if row.get("sensitive_found"): r.append("DLP: sensitive data found")
        return "In scope because " + ", ".join(r) + "." if r else "Out of scope based on available data."

    df["scope_reason"] = df.apply(reason, axis=1)
    df["pci_scope_note"] = PCI_SCOPE_NOTE
    return df

scoped_df = classify_scope(inv_df)

# ------------------------------
# Control Mapper
# ------------------------------
CONTROL_LIBRARY = [
    {
        "req_id": "REQ-01",
        "title": "Firewall controls",
        "text": "Restrict inbound/outbound traffic with firewall/ACL at network boundaries.",
        "field": "firewall_enabled",
        "expected": True,
    },
    {
        "req_id": "REQ-02",
        "title": "Encryption in transit",
        "text": "Encrypt CHD transmissions over open/public networks.",
        "field": "encryption_in_transit",
        "expected": True,
    },
    {
        "req_id": "REQ-03",
        "title": "Encryption at rest",
        "text": "Render CHD unreadable wherever it is stored.",
        "field": "encryption_at_rest",
        "expected": True,
    },
    {
        "req_id": "REQ-04",
        "title": "Logging & monitoring",
        "text": "Enable logging to support security monitoring and forensics.",
        "field": "logging_enabled",
        "expected": True,
    },
]

def build_control_matrix(scoped: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, a in scoped.iterrows():
        for ctrl in CONTROL_LIBRARY:
            actual = bool(a.get(ctrl["field"], False))
            met = (actual == ctrl["expected"])
            rows.append({
                "asset_id": a["asset_id"],
                "asset_name": a.get("name"),
                "in_scope": bool(a.get("in_scope", False)),
                "req_id": ctrl["req_id"],
                "requirement": ctrl["title"],
                "requirement_text": ctrl["text"],
                "evidence_field": ctrl["field"],
                "expected": ctrl["expected"],
                "actual": actual,
                "status": "Met" if met else "Gap",
            })
    return pd.DataFrame(rows)

control_df = build_control_matrix(scoped_df)

# ------------------------------
# Remediation Planner
# ------------------------------
def remediation_suggestion(row: pd.Series) -> str:
    if row["req_id"] == "REQ-02" and not row["actual"]:
        return "Enable TLS 1.2+; enforce HTTPS; disable weak ciphers."
    if row["req_id"] == "REQ-03" and not row["actual"]:
        return "Enable disk/DB encryption (KMS); rotate keys; document key mgmt."
    if row["req_id"] == "REQ-01" and not row["actual"]:
        return "Apply perimeter/CDE firewall rules; default deny; allowlist only."
    if row["req_id"] == "REQ-04" and not row["actual"]:
        return "Enable audit logging; centralize logs (SIEM); set retention & alerts."
    return ""

def scope_reduction_tips(asset_row: pd.Series) -> List[str]:
    tips = []
    if asset_row.get("in_scope"):
        if asset_row.get("stores_chd"):
            tips.append("Tokenize PANs to remove CHD at rest.")
        if asset_row.get("processes_chd") or asset_row.get("transmits_chd"):
            tips.append("Outsource payment processing to a PCI-compliant PSP.")
        if str(asset_row.get("network_segment", "")).lower() != "cde":
            tips.append("Segment the CDE; restrict routes.")
    return tips

def build_remediation(scoped: pd.DataFrame, controls: pd.DataFrame) -> pd.DataFrame:
    gaps = controls[(controls["in_scope"]) & (controls["status"] == "Gap")].copy()
    if gaps.empty:
        return pd.DataFrame(columns=["asset_id","asset","req_id","requirement","gap","remediation","scope_reduction"])
    gaps["remediation"] = gaps.apply(remediation_suggestion, axis=1)
    merged = gaps.merge(
        scoped[["asset_id","name","in_scope","stores_chd","processes_chd","transmits_chd","network_segment"]],
        on="asset_id", how="left"
    )
    merged["scope_reduction"] = merged.apply(lambda r: "; ".join(scope_reduction_tips(r)), axis=1)
    merged.rename(columns={"name":"asset", "status":"gap"}, inplace=True)
    return merged[["asset_id","asset","req_id","requirement","gap","remediation","scope_reduction"]]

remediation_df = build_remediation(scoped_df, control_df)

# ------------------------------
# Report (Excel) generator
# ------------------------------
def build_excel_report(inventory: pd.DataFrame, scoped: pd.DataFrame,
                       controls: pd.DataFrame, remediation: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        inventory.to_excel(writer, index=False, sheet_name="Inventory")
        scoped.to_excel(writer, index=False, sheet_name="Scope")
        controls.to_excel(writer, index=False, sheet_name="Controls")
        remediation.to_excel(writer, index=False, sheet_name="Remediation")
    output.seek(0)
    return output.read()

# ------------------------------
# SINGLE SCREEN LAYOUT
# ------------------------------
st.markdown("### 1) Inventory Scanner")
st.dataframe(inv_df, use_container_width=True)

st.markdown("### 2) Scope Classifier")
st.info(PCI_SCOPE_NOTE)
st.dataframe(
    scoped_df[["asset_id","name","in_scope","scope_reason","network_segment","stores_chd","processes_chd","transmits_chd","chd_present","sensitive_found"]],
    use_container_width=True
)

st.markdown("### 3) Control Mapper")
st.dataframe(control_df, use_container_width=True)

st.markdown("### 4) Remediation Planner")
if remediation_df.empty:
    st.success("No gaps found for in-scope assets. 🎉")
else:
    st.dataframe(remediation_df, use_container_width=True)

st.markdown("### 5) Audit Report Generator")
c1, c2 = st.columns(2)
with c1:
    st.subheader("Scope Summary")
    scope_summary = scoped_df["in_scope"].value_counts(dropna=False).rename_axis("in_scope").reset_index(name="count")
    st.dataframe(scope_summary, use_container_width=True)
with c2:
    st.subheader("Control Status (in-scope only)")
    in_scope_controls = control_df[control_df["in_scope"]]
    status_summary = in_scope_controls["status"].value_counts().rename_axis("status").reset_index(name="count")
    st.dataframe(status_summary, use_container_width=True)

excel_bytes = build_excel_report(inv_df, scoped_df, control_df, remediation_df)
st.download_button(
    label="⬇️ Download Auditor-Ready Excel",
    data=excel_bytes,
    file_name="pci_dss_mvp_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
