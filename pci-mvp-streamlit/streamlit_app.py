import io
import json
from typing import List, Dict, Any
import pandas as pd
import streamlit as st
import requests
import streamlit_chat as st_chat
import google.generativeai as genai

# 👇 NEW: optional Neo4j driver & Streamlit components
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except Exception:
    NEO4J_AVAILABLE = False

import streamlit.components.v1 as components

# Configure Google's Generative AI with your API key
try:
    genai.configure(api_key="AIzaSyCPqUb-7j41amLpM4QkC0UEUI3r3jUBr6o")
    chat_model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Failed to configure Google Generative AI: {e}")
    st.info("Please add a valid Google API key to enable the chatbot functionality.")
    chat_model = None
# ------------------------------
# Page config
# ------------------------------
st.set_page_config(
    page_title="PCI DSS Compliance MVP",
    page_icon="✅",
    layout="wide",
)

st.title("PCI DSS Compliance MVP")
st.caption("Automates: Inventory → Scope → Controls → Remediation → Report")

# --- Initialize session state for uploaded files ---
if 'uploaded_files' not in st.session_state:
    st.session_state['uploaded_files'] = []

# ------------------------------
# Fetch inventory from MockAPI
# ------------------------------
def fetch_inventory_from_api() -> pd.DataFrame:
    url = "https://68ae8e19b91dfcdd62b97c34.mockapi.io/Inventory"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return pd.json_normalize(data)
        else:
            return pd.DataFrame([data])
    except Exception as e:
        st.error(f"❌ Could not fetch from API. Error: {e}")
    st.stop()

# --- Unified Uploads Dashboard Section ---
st.markdown("### 📂 Uploads — Inventory & DLP")

uploaded_file = st.file_uploader(
    "Drag and drop files here (CSV or JSON)",
    type=["csv", "json"],
    accept_multiple_files=True,
    help="You can upload multiple files at once. Each file will be processed based on its name (e.g., 'inventory' or 'dlp' in the filename)."
)

def parse_upload(upload) -> Dict[str, Any]:
    """Parses a single uploaded file and returns its data and metadata."""
    if upload is None:
        return {}
    
    name = upload.name.lower()
    
    # Heuristics to determine file type
    file_type = "Unknown"
    if "inv" in name or "inventory" in name:
        file_type = "Inventory"
    elif "dlp" in name:
        file_type = "DLP Findings"

    if file_type == "Unknown":
        st.error(f"Could not determine file type for '{upload.name}'. Please make sure the filename contains 'inventory' or 'dlp'.")
        return {}
        
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(upload)
        elif name.endswith(".json"):
            # Attempt to parse as a single JSON object
            try:
                raw = json.load(upload)
                df = pd.json_normalize(raw)
            except json.JSONDecodeError:
                # If it fails, try parsing line by line
                upload.seek(0)  # Rewind the file pointer
                data = [json.loads(line) for line in upload]
                df = pd.json_normalize(data)

        else:
            raise ValueError("Unsupported file type.")

        return {
            "name": upload.name,
            "type": file_type,
            "size": upload.size,
            "df": df,
            "uploaded_at": pd.Timestamp.now()
        }
    except Exception as e:
        st.error(f"Error parsing {upload.name}: {e}")
        return {}

def process_uploads(uploads: List[Any]):
    """Processes new uploads, adds them to session state, and identifies the latest of each type."""
    if not uploads:
        return None, None
    
    # Add new uploads to the list
    for upload in uploads:
        parsed_data = parse_upload(upload)
        if parsed_data:
            st.session_state.uploaded_files.append(parsed_data)
    
    # Find the latest inventory and DLP files
    latest_inv_upload = None
    latest_dlp_upload = None
    
    sorted_files = sorted(st.session_state.uploaded_files, key=lambda x: x['uploaded_at'], reverse=True)
    
    for f in sorted_files:
        if f['type'] == "Inventory" and latest_inv_upload is None:
            latest_inv_upload = f
        elif f['type'] == "DLP Findings" and latest_dlp_upload is None:
            latest_dlp_upload = f

    return latest_inv_upload, latest_dlp_upload

# Process uploads from the file uploader
latest_inv_upload, latest_dlp_upload = process_uploads(uploaded_file)

# Display a table of previously uploaded files
if st.session_state.uploaded_files:
    st.subheader("📝 Previously Uploaded Files")
    files_to_display = []
    for f in st.session_state.uploaded_files:
        files_to_display.append({
            "File Name": f["name"],
            "File Type": f["type"],
            "Size (KB)": round(f["size"] / 1024, 2),
            "Uploaded At": f["uploaded_at"].strftime("%Y-%m-%d %H:%M:%S")
        })
    st.dataframe(pd.DataFrame(files_to_display), use_container_width=True)

def parse_inventory_data(inv_data) -> pd.DataFrame:
    if inv_data is None:
        return fetch_inventory_from_api()
    return inv_data['df']

def merge_dlp_findings(inv_df: pd.DataFrame, dlp_data) -> pd.DataFrame:
    df = inv_df.copy()
    if "sensitive_found" not in df.columns:
        df["sensitive_found"] = False
    
    if dlp_data is None:
        return df
    
    dlp = dlp_data['df']
    if not {"asset_id", "sensitive_found"}.issubset(dlp.columns):
        st.warning("DLP file must have columns: asset_id, sensitive_found. Ignoring DLP upload.")
        return df
    df = df.merge(dlp[["asset_id", "sensitive_found"]],
                  on="asset_id", how="left", suffixes=("", "_dlp"))
    df["sensitive_found"] = df["sensitive_found_dlp"].fillna(df["sensitive_found"]).fillna(False)
    return df.drop(columns=[c for c in df.columns if c.endswith("_dlp")])

try:
    inv_df = parse_inventory_data(latest_inv_upload)
    inv_df = merge_dlp_findings(inv_df, latest_dlp_upload)
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
def build_control_matrix_from_api() -> pd.DataFrame:
    url = "https://68ae8e19b91dfcdd62b97c34.mockapi.io/ControlMapper"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Could not fetch controls from API. Error: {e}")
        return pd.DataFrame()

control_df = build_control_matrix_from_api()
# ------------------------------
# Remediation Planner
# ------------------------------
def remediation_suggestion(row: pd.Series) -> str:
    if row["req_id"] == "REQ-02" and not row["actual"]:
        return "Enable TLS 1.2+; enforce HTTPS; disable weak ciphers."
    if row["req_id"] == "REQ-03" and not row["actual"]:
        return "Enable DB/disk encryption with KMS."
    if row["req_id"] == "REQ-01" and not row["actual"]:
        return "Apply firewall rules: default deny; allowlist only."
    if row["req_id"] == "REQ-04" and not row["actual"]:
        return "Enable audit logging; centralize logs (SIEM)."
    return ""

def build_remediation(assets: pd.DataFrame, controls: pd.DataFrame) -> pd.DataFrame:
    if "status" not in controls.columns:
        return pd.DataFrame()
    gaps = controls[controls["status"] == "Gap"].copy()
    if gaps.empty:
        return pd.DataFrame()
    gaps["remediation"] = gaps["title"].apply(remediation_suggestion)
    return gaps


remediation_df = build_remediation(scoped_df, control_df)

# ------------------------------
# Report Generator
# ------------------------------
def build_excel_report(inventory, scoped, controls, remediation) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        inventory.to_excel(writer, index=False, sheet_name="Inventory")
        scoped.to_excel(writer, index=False, sheet_name="Scope")
        controls.to_excel(writer, index=False, sheet_name="Controls")
        remediation.to_excel(writer, index=False, sheet_name="Remediation")
    output.seek(0)
    return output.read()

# ------------------------------
# 🔌 NEW: Neo4j helpers
# ------------------------------
def get_neo4j_settings():
    uri = st.secrets.get("NEO4J_URI", "") if hasattr(st, "secrets") else ""
    user = st.secrets.get("NEO4J_USER", "") if hasattr(st, "secrets") else ""
    pwd = st.secrets.get("NEO4J_PASSWORD", "") if hasattr(st, "secrets") else ""
    db = st.secrets.get("NEO4J_DATABASE", "neo4j") if hasattr(st, "secrets") else "neo4j"
    return uri, user, pwd, db

def push_graph_to_neo4j(uri: str, user: str, pwd: str, database: str,
                        inv: pd.DataFrame, controls: pd.DataFrame):
    """
    Creates a minimal PCI knowledge graph:
    (:Asset {asset_id, name, in_scope, segment, sensitive_found})
    (:Control {req_id, title, status})
    (Asset)-[:HAS_CONTROL]->(Control) when applicable by req_id (best-effort).
    """
    if not NEO4J_AVAILABLE:
        st.error("neo4j driver not installed. Run: pip install neo4j")
        return False

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    def run_write(tx, query, params=None):
        tx.run(query, params or {})

    with driver.session(database=database) as session:
        # Basic schema (indexes)
        session.execute_write(
            run_write,
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Asset) REQUIRE a.asset_id IS UNIQUE"
        )
        session.execute_write(
            run_write,
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Control) REQUIRE c.req_id IS UNIQUE"
        )

        # Upsert Assets
        for _, r in inv.fillna("").iterrows():
            asset_id = str(r.get("asset_id", "")).strip()
            if not asset_id:
                continue
            session.execute_write(
                run_write,
                """
                MERGE (a:Asset {asset_id:$asset_id})
                SET a.name = COALESCE($name, a.name),
                    a.in_scope = $in_scope,
                    a.network_segment = $segment,
                    a.sensitive_found = $sensitive_found
                """,
                {
                    "asset_id": asset_id,
                    "name": str(r.get("name", ""))[:200],
                    "in_scope": bool(r.get("in_scope", False)),
                    "segment": str(r.get("network_segment", ""))[:60],
                    "sensitive_found": bool(r.get("sensitive_found", False)),
                }
            )

        # Upsert Controls
        for _, r in controls.fillna("").iterrows():
            req_id = str(r.get("req_id", "")).strip()
            if not req_id:
                continue
            session.execute_write(
                run_write,
                """
                MERGE (c:Control {req_id:$req_id})
                SET c.title = COALESCE($title, c.title),
                    c.status = $status
                """,
                {
                    "req_id": req_id,
                    "title": str(r.get("title", ""))[:300],
                    "status": str(r.get("status", ""))[:60],
                }
            )

        # Link Assets to Controls (best-effort: if inv has a column 'req_id' or 'controls')
        # 1) If inventory rows list a single req_id
        if "req_id" in inv.columns:
            for _, r in inv.fillna("").iterrows():
                asset_id = str(r.get("asset_id", "")).strip()
                req = str(r.get("req_id", "")).strip()
                if asset_id and req:
                    session.execute_write(
                        run_write,
                        """
                        MATCH (a:Asset {asset_id:$asset_id}), (c:Control {req_id:$req})
                        MERGE (a)-[:HAS_CONTROL]->(c)
                        """,
                        {"asset_id": asset_id, "req": req}
                    )

        # 2) If inventory rows list multiple controls in a 'controls' column (CSV or list)
        if "controls" in inv.columns:
            for _, r in inv.fillna("").iterrows():
                asset_id = str(r.get("asset_id", "")).strip()
                if not asset_id:
                    continue
                controls_cell = r.get("controls", "")
                if isinstance(controls_cell, str) and controls_cell:
                    reqs = [x.strip() for x in controls_cell.split(",") if x.strip()]
                elif isinstance(controls_cell, list):
                    reqs = [str(x).strip() for x in controls_cell if str(x).strip()]
                else:
                    reqs = []
                for req in reqs:
                    session.execute_write(
                        run_write,
                        """
                        MATCH (a:Asset {asset_id:$asset_id}), (c:Control {req_id:$req})
                        MERGE (a)-[:HAS_CONTROL]->(c)
                        """,
                        {"asset_id": asset_id, "req": req}
                    )

    driver.close()
    return True

def render_popoto_html(uri: str, user: str, pwd: str, database: str = "neo4j") -> str:
    """
    Returns an HTML page embedding Popoto.js and connecting with the Neo4j JS driver.
    Taxonomy: start from Asset; you can expand to Control via HAS_CONTROL.
    """
    # Minimal safe escaping
    uri_js = uri.replace('"', '\\"')
    user_js = user.replace('"', '\\"')
    pwd_js = pwd.replace('"', '\\"')
    db_js = database.replace('"', '\\"')

    # Popoto expects D3 and Neo4j JS Driver; we use UMD bundles from unpkg
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Popoto Graph</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body {{ height: 100%; margin: 0; }}
    #root {{ height: 100%; display:flex; flex-direction:column; font-family: sans-serif; }}
    #toolbar {{ padding:8px 12px; border-bottom:1px solid #eee; }}
    #graph {{ flex:1; }}
    .pp-toolbar {{ background:#fafafa; }}
  </style>
  <script src="https://unpkg.com/d3@7"></script>
  <script src="https://unpkg.com/neo4j-driver"></script>
  <link rel="stylesheet" href="https://unpkg.com/popoto/dist/popoto.min.css"/>
  <script src="https://unpkg.com/popoto/dist/popoto.min.js"></script>
</head>
<body>
<div id="root">
  <div id="toolbar">
    <strong>Popoto.js • PCI Knowledge Graph</strong>
    <span style="margin-left:10px;color:#666;">Start with Assets → expand to Controls</span>
  </div>
  <div id="graph" class="pp-graph"></div>
</div>

<script>
(async function() {{
  try {{
    const driver = neo4j.driver("{uri_js}", neo4j.auth.basic("{user_js}", "{pwd_js}"));
    const session = driver.session({{ database: "{db_js}" }});
    // Give Popoto the Neo4j driver instance (Popoto 3+)
    popoto.rest.DRIVER = driver;
    popoto.rest.SESSION_OPTS = {{ database: "{db_js}" }};

    // Define simple label provider: Asset and Control
    popoto.provider.node.Provider = {{
      "Asset": {{
        "returnProperties": ["asset_id","name","in_scope","network_segment","sensitive_found"],
        "constraintAttribute": "asset_id",
        "autoExpandRelations": true
      }},
      "Control": {{
        "returnProperties": ["req_id","title","status"],
        "constraintAttribute": "req_id"
      }}
    }};

    popoto.provider.link.Provider = [
      {{
        "link" : "HAS_CONTROL",
        "range" : "Control",
        "domain" : "Asset",
        "direction": "out"
      }}
    ];

    // Start from Asset label
    popoto.tools.CONFIG.SHOW_QUERY = true;
    popoto.start("graph", ["Asset"]);

    // Clean up on page unload
    window.addEventListener("beforeunload", async () => {{ await driver.close(); }});
  }} catch (e) {{
    document.body.innerHTML = "<pre style='padding:16px'>Popoto init error:\\n"+ (e && e.message ? e.message : e) +"</pre>";
  }}
}})();
</script>
</body>
</html>
"""
    return html

# ------------------------------
# Sidebar Menu
# ------------------------------
with st.sidebar.expander("🔎 Agents"):
    menu = st.selectbox(
        "Choose an Agent",
        [
            "Inventory Scanner",
            "Scope Classifier",
            "Control Mapper",
            "Remediation Planner",
            "Audit Report Generator",
            "Knowledge"  # 👈 NEW option
        ]
    )

# 👇 NEW: explicit Knowledge button in sidebar (sets the same `menu`)
if st.sidebar.button("Knowledge"):
    menu = "Knowledge"

st.write(f"👉 You selected: {menu}")

# ------------------------------
# Pages based on menu
# ------------------------------

if menu == "Inventory Scanner":
    st.subheader("1️⃣ Inventory Scanner")
    st.dataframe(inv_df, use_container_width=True)

elif menu == "Scope Classifier":
    st.subheader("2️⃣ Scope Classifier")
    st.info(PCI_SCOPE_NOTE)
    st.dataframe(
        scoped_df[["asset_id","name","in_scope","scope_reason","network_segment","stores_chd","processes_chd","transmits_chd","chd_present","sensitive_found"]],
        use_container_width=True
    )

elif menu == "Control Mapper":
    st.subheader("3️⃣ Control Mapper")
    st.dataframe(control_df, use_container_width=True)

elif menu == "Remediation Planner":
    st.subheader("4️⃣ Remediation Planner")
    if remediation_df.empty:
        st.success("No gaps found for in-scope assets. 🎉")
    else:
        st.dataframe(remediation_df, use_container_width=True)

elif menu == "Audit Report Generator":
    st.subheader("5️⃣ Audit Report Generator")
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

# ------------------------------
# 📚 NEW: Knowledge (Neo4j + Popoto.js)
# ------------------------------
elif menu == "Knowledge":
    st.subheader("6️ Knowledge — Neo4j + Popoto.js")

    with st.sidebar:
        st.markdown("### 🔌 Neo4j Connection")
        default_uri, default_user, default_pwd, default_db = get_neo4j_settings()
        neo4j_uri = st.text_input("URI", value=default_uri, placeholder="neo4j+s://<host>:7687")
        neo4j_user = st.text_input("User", value=default_user or "neo4j")
        neo4j_pwd = st.text_input("Password", value=default_pwd, type="password")
        neo4j_db = st.text_input("Database", value=default_db or "neo4j")
        st.caption("Tip: Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE in st.secrets to avoid typing.")

        push_btn = st.button("🚀 Build / Update Knowledge Graph in Neo4j")

    # Show what will be pushed
    with st.expander("Preview data to push (first 50 rows)"):
        st.write("**Assets (inventory + scope)**")
        try:
            preview_assets = scoped_df[["asset_id","name","in_scope","network_segment","sensitive_found"]].head(50)
        except Exception:
            preview_assets = inv_df.head(50)
        st.dataframe(preview_assets, use_container_width=True)
        st.write("**Controls**")
        st.dataframe(control_df.head(50), use_container_width=True)

    # Push data to Neo4j
    if push_btn:
        if not neo4j_uri or not neo4j_user or not neo4j_pwd:
            st.error("Please provide Neo4j URI, username and password.")
        else:
            try:
                ok = push_graph_to_neo4j(neo4j_uri, neo4j_user, neo4j_pwd, neo4j_db, scoped_df, control_df)
                if ok:
                    st.success("✅ Data pushed to Neo4j successfully.")
                else:
                    st.error("❌ Could not push data to Neo4j (driver missing or connection issue).")
            except Exception as e:
                st.error(f"Neo4j push error: {e}")

    st.markdown("---")
    st.markdown("#### 📈 Popoto.js Graph Viewer")
    st.caption("Interactive graph backed by your Neo4j DB. Start from **Asset**; expand relationships to **Control**.")
    if neo4j_uri and neo4j_user and neo4j_pwd:
        html = render_popoto_html(neo4j_uri, neo4j_user, neo4j_pwd, neo4j_db)
        components.html(html, height=800, scrolling=True)
    else:
        st.info("Enter Neo4j connection details in the sidebar to load the Popoto viewer.")

# --- Chatbot Logic with UI Fixes ---

# Initialize session state for chatbot
if "chatbot_open" not in st.session_state:
    st.session_state.chatbot_open = False
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- CSS to create a fixed-position button ---
st.markdown(
    """
    <style>
    .fixed-button-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1000;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
# --- Chatbot Button and UI ---

# Chatbot button
if not st.session_state.chatbot_open:
    with st.container():
        st.markdown('<div class="fixed-button-container">', unsafe_allow_html=True)
        if st.button("💬 PCI DSS Chatbot", key="chatbot_toggle_open"):
            st.session_state.chatbot_open = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# Chatbot UI
if st.session_state.chatbot_open:
    # Use a single container for the entire chat window with a border and height
    chat_window = st.container(height=550, border=True)

    with chat_window:
        # Chat Header
        c1, c2 = st.columns([0.8, 0.2])
        with c1:
            st.markdown("### PCI DSS Chatbot")
        with c2:
            if st.button("Close ❌", key="chatbot_toggle_close"):
                st.session_state.chatbot_open = False
                st.rerun()
                
        # Chat history container with scrollbar
        chat_history = st.container(height=380)
        with chat_history:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # The chat input
        if prompt := st.chat_input("Ask me about PCI DSS..."):
            st.session_state.messages.append({"role": "user", "content": prompt})

            with chat_history:
                with st.chat_message("user"):
                    st.markdown(prompt)

            # Generate and display assistant response
            if chat_model:
                try:
                    with chat_history:
                        with st.chat_message("assistant"):
                            response_stream = chat_model.generate_content(
                                prompt,
                                stream=True
                            )
                            full_response = ""
                            for chunk in response_stream:
                                full_response += chunk.text
                                st.markdown(full_response + " ")
                            st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"Error generating response: {e}")
            else:
                st.session_state.messages.append({"role": "assistant", "content": "Chatbot is not configured. Please add a valid API key."})
