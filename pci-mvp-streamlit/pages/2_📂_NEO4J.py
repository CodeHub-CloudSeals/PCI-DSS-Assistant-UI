import streamlit as st
from neo4j import GraphDatabase 
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import configuration with fallback values
try:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASS, DEMO_USERS, NEO4J_ALTERNATIVE_URIS
except ImportError as e:
    st.error(f"Failed to import config: {e}")
    # Fallback values
    NEO4J_URI = "neo4j+ssc://8871b289.databases.neo4j.io:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASS = "vRksbVfn6v4HnvuqyhpQnUeK74edAAdaYKmvkxYCsR0"
    DEMO_USERS = {"admin": "1234", "jithu": "pass123"}
    NEO4J_ALTERNATIVE_URIS = [
        "neo4j+ssc://8871b289.databases.neo4j.io:7687",
        "neo4j+s://8871b289.databases.neo4j.io:7687",
        "neo4j://8871b289.databases.neo4j.io:7687",
        "bolt://8871b289.databases.neo4j.io:7687",
        "bolt+ssc://8871b289.databases.neo4j.io:7687"
    ]

def test_neo4j_connection(uri=None):
    """Test Neo4j connection with given URI or default"""
    if uri is None:
        uri = NEO4J_URI
    
    try:
        driver = GraphDatabase.driver(uri, auth=(NEO4J_USER, NEO4J_PASS))
        with driver.session() as session:
            result = session.run("RETURN 'Connection Test Successful!' AS msg")
            msg = result.single()["msg"]
        driver.close()
        return True, msg
    except Exception as e:
        return False, str(e)

def find_working_connection():
    """Try multiple connection URIs to find one that works"""
    st.info("🔌 Testing multiple connection methods...")
    
    # Try the main URI first
    success, msg = test_neo4j_connection(NEO4J_URI)
    if success:
        st.success(f"✅ Main URI works: {NEO4J_URI}")
        return NEO4J_URI, True
    
    # Try alternative URIs
    for alt_uri in NEO4J_ALTERNATIVE_URIS:
        if alt_uri != NEO4J_URI:
            st.info(f"🔄 Trying: {alt_uri}")
            success, msg = test_neo4j_connection(alt_uri)
            if success:
                st.success(f"✅ Alternative URI works: {alt_uri}")
                return alt_uri, True
            else:
                st.warning(f"❌ {alt_uri} failed: {msg}")
    
    return None, False

def create_neo4j_driver(uri=None):
    """Create and return a Neo4j driver"""
    if uri is None:
        uri = NEO4J_URI
    
    try:
        return GraphDatabase.driver(uri, auth=(NEO4J_USER, NEO4J_PASS))
    except Exception as e:
        st.error(f"Failed to create Neo4j driver with {uri}: {e}")
        return None

# --- Demo users (replace with a proper DB or Auth later) ---
USERS = DEMO_USERS

# --- Session state for login ---
if "neo4j_logged_in" not in st.session_state:
    st.session_state.neo4j_logged_in = False
if "neo4j_driver" not in st.session_state:
    st.session_state.neo4j_driver = None
if "working_uri" not in st.session_state:
    st.session_state.working_uri = None

# --- Page content ---
st.title("🔐 Neo4j Login Page")

# Connection status display
st.markdown("### 📡 Connection Status")
if st.session_state.neo4j_driver:
    st.success("✅ Connected to Neo4j")
    if st.session_state.working_uri:
        st.info(f"Using URI: {st.session_state.working_uri}")
else:
    st.warning("❌ Not connected to Neo4j")

# Manual connection test button
if st.button("🔌 Test Neo4j Connection"):
    st.info("Testing connection...")
    working_uri, success = find_working_connection()
    
    if success:
        st.success("✅ Connection test successful!")
        st.info(f"Working URI: {working_uri}")
        # Store the working URI for future use
        if "working_uri" not in st.session_state:
            st.session_state.working_uri = working_uri
    else:
        st.error("❌ All connection methods failed")
        st.info("💡 Check your Neo4j database settings or try again later")

if not st.session_state.neo4j_logged_in:
    with st.form("login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password", value="1234")
        
        if st.form_submit_button("Login"):
            if username in USERS and USERS[username] == password:
                st.info("🔌 Attempting to connect to Neo4j...")
                
                # Find a working connection
                working_uri, success = find_working_connection()
                
                if success:
                    # Create driver with working URI
                    driver = create_neo4j_driver(working_uri)
                    if driver:
                        st.session_state.neo4j_logged_in = True
                        st.session_state.neo4j_driver = driver
                        st.session_state.working_uri = working_uri
                        st.success(f"✅ Welcome {username}! Connected to Neo4j successfully!")
                        st.info("✅ Login successful! Now go to the **View Database** page from the sidebar 👉")
                        st.rerun()
                    else:
                        st.error("❌ Failed to create Neo4j driver")
                else:
                    st.error("❌ All connection methods failed")
                    st.info("💡 Please check your Neo4j database settings or try again later")
            else:
                st.error("❌ Invalid username or password")

# Display connection info for debugging
with st.expander("🔍 Connection Details"):
    st.info(f"Main URI: {NEO4J_URI}")
    st.info(f"User: {NEO4J_USER}")
    st.info(f"Password: {'*' * len(NEO4J_PASS) if NEO4J_PASS else 'Not set'}")
    st.info(f"Alternative URIs: {len(NEO4J_ALTERNATIVE_URIS)} available")
    
    if st.session_state.working_uri:
        st.success(f"Working URI: {st.session_state.working_uri}")
    
    # Show connection test results
    st.markdown("**Connection Test:**")
    if st.button("🔄 Test Connection Now"):
        working_uri, success = find_working_connection()
        if success:
            st.success("✅ Connection successful!")
            st.info(f"Working URI: {working_uri}")
        else:
            st.error("❌ All connection methods failed")

# Troubleshooting tips
with st.expander("💡 Troubleshooting Tips"):
    st.markdown("""
    **Common Neo4j Connection Issues:**
    
    1. **Database not running**: Ensure your Neo4j database is active
    2. **Network connectivity**: Check if you can reach the database server
    3. **Authentication**: Verify username and password are correct
    4. **SSL/TLS**: The app tries multiple connection protocols
    5. **Firewall**: Ensure port 7687 is open
    6. **For Neo4j Aura**: Check if your IP is whitelisted in Aura settings
    
    **Quick Fixes:**
    - Try the "Test Neo4j Connection" button above
    - The app automatically tries multiple connection methods
    - Check the Connection Details section for current settings
    - Verify your Neo4j Aura database is running and accessible
    
    **"Unable to retrieve routing information" Error:**
    - This usually means the database is not accessible or credentials are wrong
    - Try the connection test button to find a working method
    - Check if your Neo4j Aura database is still active
    """)
