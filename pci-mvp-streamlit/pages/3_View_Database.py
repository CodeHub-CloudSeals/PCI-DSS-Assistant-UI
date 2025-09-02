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
        # Get nodes with properties
        nodes = run_cypher_query("""
            MATCH (n) 
            RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props 
            LIMIT 50
        """)

        # Get relationships
        rels = run_cypher_query("""
            MATCH (a)-[r]->(b) 
            RETURN id(a) AS source, id(b) AS target, type(r) AS type, properties(r) AS props 
            LIMIT 50
        """)

        # Build Pyvis network
        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

        # Add nodes with labels + properties
        for node in nodes:
            node_id = node["id"]
            label = ", ".join(node["labels"])  # Node labels
            props = node["props"]

            # Display one main property as node label (e.g., name/id if exists)
            display_label = props.get("name") or props.get("id") or label

            # Tooltip shows all properties
            tooltip = "<br>".join([f"{k}: {v}" for k, v in props.items()])

            net.add_node(node_id, label=str(display_label), title=tooltip)

        # Add relationships with type + properties
        for rel in rels:
            rel_type = rel["type"]
            rel_props = rel["props"]

            # Tooltip for relationships
            rel_tooltip = "<br>".join([f"{k}: {v}" for k, v in rel_props.items()]) if rel_props else ""

            net.add_edge(rel["source"], rel["target"], label=rel_type, title=rel_tooltip)

        # Save and display inside Streamlit
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
            net.save_graph(tmp_file.name)
            html_content = open(tmp_file.name, "r", encoding="utf-8").read()
            st.components.v1.html(html_content, height=850)

    except Exception as e:
        st.error(f"❌ Query failed: {e}")
