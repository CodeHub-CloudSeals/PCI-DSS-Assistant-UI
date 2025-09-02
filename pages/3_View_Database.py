import streamlit as st
from pyvis.network import Network
import tempfile

st.title("🌐 Neo4j Graph Visualization")

# --- Require login ---
if not st.session_state.get("neo4j_logged_in", False):
    st.error("❌ Please login first from the Neo4j Login page.")
    st.stop()

def run_cypher_query(query, params=None):
    with st.session_state.neo4j_driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]

# --- Load graph ---
if st.button("Load Graph"):
    try:
        # Fetch relationships and their connected nodes together to avoid dangling edges
        rel_rows = run_cypher_query("""
            MATCH (a)-[r]->(b)
            RETURN id(a) AS source_id,
                   labels(a) AS source_labels,
                   properties(a) AS source_props,
                   id(b) AS target_id,
                   labels(b) AS target_labels,
                   properties(b) AS target_props,
                   type(r) AS rel_type,
                   properties(r) AS rel_props
            LIMIT 200
        """)

        # Build Pyvis network
        net = Network(height="850px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

        added_nodes = set()

        def add_node_if_needed(node_id, labels, props):
            if node_id in added_nodes:
                return
            safe_props = props or {}
            label_text = ", ".join(labels) if labels else "Node"
            display_label = safe_props.get("name") or safe_props.get("id") or label_text
            tooltip = "<br>".join([f"{k}: {v}" for k, v in safe_props.items()]) if safe_props else ""
            net.add_node(node_id, label=str(display_label), title=tooltip)
            added_nodes.add(node_id)

        # Add nodes and edges
        for row in rel_rows:
            src_id = row["source_id"]
            tgt_id = row["target_id"]
            add_node_if_needed(src_id, row.get("source_labels"), row.get("source_props"))
            add_node_if_needed(tgt_id, row.get("target_labels"), row.get("target_props"))

            rel_type = row.get("rel_type")
            rel_props = row.get("rel_props") or {}
            rel_tooltip = "<br>".join([f"{k}: {v}" for k, v in rel_props.items()]) if rel_props else ""
            net.add_edge(src_id, tgt_id, label=rel_type, title=rel_tooltip)

        # Save and display inside Streamlit
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
            net.save_graph(tmp_file.name)
            html_content = open(tmp_file.name, "r", encoding="utf-8").read()
            st.components.v1.html(html_content, height=850)

    except Exception as e:
        st.error(f"❌ Query failed: {e}")
