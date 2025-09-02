# PCI DSS Compliance MVP - Streamlit UI

A comprehensive PCI DSS compliance management application built with Streamlit, featuring inventory management, scope classification, control mapping, remediation planning, and Neo4j graph database integration.

## 🚀 Features

- **Inventory Scanner**: Upload and manage asset inventory data
- **Scope Classifier**: Automatically classify assets as in/out of scope
- **Control Mapper**: Map PCI DSS controls to assets
- **Remediation Planner**: Generate remediation recommendations
- **Knowledge Graph**: Neo4j integration for graph-based data visualization
- **Audit Report Generator**: Export compliance reports to Excel
- **AI Chatbot**: PCI DSS guidance using Google's Generative AI

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pci-mvp-streamlit
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Neo4j connection** (optional)
   - Create a `.env` file with your Neo4j credentials:
     ```
     NEO4J_URI=your_neo4j_connection_string
     NEO4J_USER=your_username
     NEO4J_PASS=your_password
     ```
   - Or modify `config.py` directly

## 🚀 Usage

1. **Start the application**
   ```bash
   streamlit run streamlit_app.py
   ```

2. **Navigate through the sidebar menu**
   - Use the "NEO4J" page to connect to your database
   - Upload inventory and DLP files
   - View scope classification and control mapping
   - Generate compliance reports

## 🔐 Neo4j Connection

The application uses a stable Neo4j connection protocol:

- **Connection**: `neo4j+ssc://` (self-signed certificate)
- **Port**: 7687 (standard Neo4j port)

### Connection Troubleshooting

If you encounter connection issues:

1. **Test the connection** using the test button on the NEO4J page
2. **Check your credentials** in the config file
3. **Verify network connectivity** to your Neo4j database
4. **For Neo4j Aura**: Ensure your IP is whitelisted

### Demo Login

Use these credentials for testing:
- **Username**: `admin`
- **Password**: `1234`

## 📁 File Structure

```
pci-mvp-streamlit/
├── streamlit_app.py          # Main application
├── pages/                    # Streamlit pages
│   ├── 2_📂_NEO4J.py        # Neo4j connection page
│   └── 3_View_Database.py   # Database viewer
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── test_neo4j_connection.py # Connection test script
└── README.md                # This file
```

## 🛠️ Configuration

Key configuration options in `config.py`:

- **Neo4j Connection**: Database URI, username, and password
- **API Endpoints**: Mock API URLs for testing
- **Demo Users**: Test account credentials

## 🔍 Testing

Test your Neo4j connection:
```bash
python test_neo4j_connection.py
```

## 📊 Data Sources

The application can work with:
- **Uploaded files**: CSV and JSON formats
- **Mock APIs**: Pre-configured endpoints for testing
- **Neo4j Database**: Graph database for advanced queries

## 🚨 Known Issues & Fixes

### Connection Error: "Unable to retrieve routing information"
- **Cause**: Incorrect Neo4j connection URI format
- **Fix**: Use `neo4j+ssc://` instead of `neo4j+s://` for self-signed certificates
- **Solution**: The app now uses the correct connection protocol by default

### Import Errors
- **Cause**: Missing dependencies or incorrect Python path
- **Fix**: Ensure all requirements are installed and check import paths

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the error messages in the application
3. Test your Neo4j connection using the test script
4. Open an issue in the repository

