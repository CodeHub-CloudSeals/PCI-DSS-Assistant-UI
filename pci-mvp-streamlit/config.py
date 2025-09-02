# Configuration file for PCI DSS Assistant UI
import os

# Neo4j Database Connection
# Try different connection formats for Neo4j Aura
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://8871b289.databases.neo4j.io:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "vRksbVfn6v4HnvuqyhpQnUeK74edAAdaYKmvkxYCsR0")

# Alternative connection URIs to try if the main one fails
NEO4J_ALTERNATIVE_URIS = [
    "neo4j+ssc://8871b289.databases.neo4j.io:7687",
    "neo4j+s://8871b289.databases.neo4j.io:7687",
    "neo4j://8871b289.databases.neo4j.io:7687",
    "bolt://8871b289.databases.neo4j.io:7687",
    "bolt+ssc://8871b289.databases.neo4j.io:7687"
]

# Google Generative AI API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyCPqUb-7j41amLpM4QkC0UEUI3r3jUBr6o")

# Mock API endpoints
MOCK_API_INVENTORY = "https://68ae8e19b91dfcdd62b97c34.mockapi.io/Inventory"
MOCK_API_CONTROLS = "https://68ae8e19b91dfcdd62b97c34.mockapi.io/ControlMapper"

# Demo users for Neo4j login
DEMO_USERS = {
    "admin": "1234",
    "jithu": "pass123"
}
