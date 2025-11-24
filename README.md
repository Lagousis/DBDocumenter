# DBDocumenter

DBDocumenter is a DuckDB-first documentation assistant that combines a Python agent, a FastAPI backend, and a Vue/Tailwind front end. The agent (and server) reason over your DuckDB workspaces with Azure OpenAI, while the web UI offers an interactive way to explore schemas, run queries, and curate field metadata.

## Prerequisites
- Python 3.10+ with `pip`
- Node.js 18+ (for Vite) and `npm`
- Azure OpenAI credentials and access to a compatible deployment
- (Optional) Azure Blob Storage account for datalake synchronization
- (Optional) Azure Synapse SQL credentials for data import

## Python Environment
1. Create and activate a virtual environment.
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
2. Install Python dependencies.
   ```powershell
   pip install -r requirements.txt
   ```
3. Create a `.env` file (or reuse the provided one) in the project root with the secrets and workspace settings you need. At minimum, set:
   ```env
   AZURE_OPENAI_API_KEY=...
   AZURE_OPENAI_ENDPOINT=...
   AZURE_OPENAI_DEPLOYMENT=...
   AZURE_OPENAI_API_VERSION=2025-01-01-preview
   # Optional DuckDB tweaks
   DUCKDB_SEARCH_ROOTS=C:\Projects\DBDocumenter\databases
   DUCKDB_PATH=C:\Projects\DBDocumenter\databases\example.duckdb
   # Optional Datalake configuration (can also use datalakes.config.json)
   DBDOC_DATALAKES=[{"name":"My Datalake","storage_type":"azure","connection_string":"...","container_name":"dbdocumenter"}]
   ```
   Any DuckDB files placed under `databases/` are discovered automatically; you can add more directories via `DUCKDB_SEARCH_ROOTS` (use the OS path separator to list multiple roots).

## Running the CLI Agent
The agent works both interactively and in single-shot mode. Activate your virtual environment and run:
```powershell
python -m src.agent
```
You will be dropped into a chat loop that remembers the current DuckDB project selection. Use `exit` or `quit` to leave.

For a one-off prompt (useful for scripting):
```powershell
python -m src.agent --prompt "List all tables in the default database."
```
Helpful flags:
- `--model`, `--endpoint`, `--api-key`, `--api-version` override the Azure OpenAI settings from the environment.
- `--search-root` can be supplied multiple times to append extra DuckDB locations.
- `--default-db` pre-selects a specific `.duckdb` file when several are available.

## Running the FastAPI Server
The backend reuses the same agent tooling and configuration. After the virtual environment is active:
```powershell
python -m src.server
```
By default the API listens on `http://127.0.0.1:8000`. Configure it with environment variables:
- `DBDOC_API_HOST` / `DBDOC_API_PORT` change the bind address.
- `DBDOC_CORS_ORIGINS` is a comma-separated list of allowed origins for the front end (defaults to `http://localhost:5173`).
- `DBDOC_QUERY_LIMIT` caps result size for `/query` responses (default 200 rows).
- `DBDOC_AGENT_MAX_STEPS` adjusts the reasoning depth of the embedded agent.

You can also launch with Uvicorn directly if you prefer:
```powershell
uvicorn src.server.app:create_app --factory --host 0.0.0.0 --port 8000
```
During development you can enable hot reloading so the server restarts on code changes:
```powershell
uvicorn src.server.app:create_app --factory --host 0.0.0.0 --port 8000 --reload --reload-dir src --reload-dir web
```
> ⚠️ `--reload` is meant for local development only; disable it for production deployments.

## Running the Web Front End
The `web/` directory contains a Vite + Vue 3 application.
```powershell
cd web
npm install
npm run dev
```
Vite serves the site at `http://localhost:5173` by default. The frontend expects the backend API under `VITE_API_BASE_URL` (defaults to `http://localhost:8000`). Override it by creating `web/.env.local`:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Copying Data from Azure Synapse to DuckDB
DBDocumenter includes a utility script to copy tables and views from Azure Synapse SQL into a local DuckDB database. This is useful for creating local copies of cloud data for analysis and documentation.

### Prerequisites
Install the required dependencies:
```powershell
pip install pyodbc
```
Ensure you have the appropriate ODBC driver installed (e.g., "ODBC Driver 18 for SQL Server").

### Configuration
Add your Synapse credentials to `.env`:
```env
# Required Synapse connection settings
SYNAPSE_SERVER=your-server.sql.azuresynapse.net
SYNAPSE_DATABASE=your_database
SYNAPSE_USERNAME=your_username
SYNAPSE_PASSWORD=your_password

# Optional connection settings
SYNAPSE_DRIVER=ODBC Driver 18 for SQL Server
SYNAPSE_PORT=1433
SYNAPSE_ENCRYPT=true
SYNAPSE_TRUST_SERVER_CERTIFICATE=false
SYNAPSE_TIMEOUT=30

# Objects to copy (comma-separated view names)
SYNAPSE_VIEWS=dbo.SalesView,dbo.CustomerView

# Or specify views with row limits and ordering
# Format: view_name:limit:order_by_clause
# Example: SYNAPSE_VIEWS=dbo.SalesView:1000:OrderDate DESC,dbo.CustomerView:500

# For custom queries, use JSON format
SYNAPSE_QUERIES_JSON=[{"query": "SELECT * FROM dbo.CustomTable WHERE Year = 2024", "table_name": "CustomTable2024"}]

# Control overwrite behavior (default: false - keeps existing tables)
SYNAPSE_OVERWRITE_EXISTING=false

# Optional: Specify target DuckDB path (default: local.duckdb)
DUCKDB_PATH=databases/synapse_copy.duckdb
```

### Running the Script
With your virtual environment activated:
```powershell
python -m src.tools.synapse_to_duckdb.run
```

Or specify a custom DuckDB target path:
```powershell
python -m src.tools.synapse_to_duckdb.run --duckdb-path databases/my_data.duckdb
```

### View Specification Formats
The `SYNAPSE_VIEWS` environment variable accepts several formats:
- **Simple view name**: `dbo.MyView` (copies all rows)
- **With row limit**: `dbo.MyView:1000` (copies first 1000 rows)
- **With limit and ordering**: `dbo.MyView:1000:OrderDate DESC` (copies 1000 rows ordered by OrderDate)
- **All rows explicitly**: `dbo.MyView:all` (same as omitting the limit)

Multiple views can be comma-separated:
```env
SYNAPSE_VIEWS=dbo.Sales:5000:SaleDate DESC,dbo.Customers:all,dbo.Products:10000
```

### Custom Queries
For more complex scenarios, use `SYNAPSE_QUERIES_JSON` with a JSON array:
```env
SYNAPSE_QUERIES_JSON=[
  {
    "query": "SELECT * FROM dbo.Sales WHERE Year = 2024",
    "table_name": "Sales2024"
  },
  {
    "query": "SELECT CustomerID, SUM(Amount) as Total FROM dbo.Orders GROUP BY CustomerID",
    "table_name": "CustomerTotals"
  }
]
```

### Script Behavior
- The script verifies the Synapse connection before starting the copy process.
- By default, existing DuckDB tables are **skipped** to avoid overwriting data. Set `SYNAPSE_OVERWRITE_EXISTING=true` to replace them.
- Progress is reported to the console as each object is processed.
- The resulting DuckDB file can be used with the agent and web UI for exploration and documentation.

## Datalake Synchronization
DBDocumenter supports synchronizing DuckDB databases with Azure Blob Storage datalakes, allowing teams to share database schemas and data across environments.

### Configuration
Add datalake configuration to `.env`:
```env
# Datalake configuration (JSON format)
DBDOC_DATALAKES=[
  {
    "name": "Production Datalake",
    "type": "azure_storage",
    "connection_string": "DefaultEndpointsProtocol=https;AccountName=...",
    "container_name": "dbdocumenter"
  }
]
```

Or create a `datalakes.config.json` file in the project root (git-ignored by default):
```json
[
  {
    "name": "Production Datalake",
    "type": "azure_storage",
    "connection_string": "DefaultEndpointsProtocol=https;AccountName=...",
    "container_name": "dbdocumenter"
  }
]
```

For a detailed setup guide, see [DATALAKE_SETUP.md](DATALAKE_SETUP.md).

### Using the Web UI
1. Click the **Sync** button in the header (circular arrows icon)
2. Use the **Manage** tab to add, test, or remove datalakes
3. Use the **Upload** tab to push your local database to a datalake
4. Use the **Download** tab to pull databases from a datalake

### Storage Structure
Files are stored in Azure Blob Storage with the following structure:
```
container/dbdocumenter/{project_name}/{version}/{filename}
```

Each project can have multiple versions, and both the `.duckdb` file and `.schema.json` are synchronized.

## Typical Workflow
1. Ensure your DuckDB databases live under `databases/` (or update `DUCKDB_SEARCH_ROOTS`).
2. Start the FastAPI server (`python -m src.server`).
3. Serve the frontend (`npm run dev`) and open the reported URL.
4. Optionally run the CLI agent in parallel for ad-hoc prompts or schema housekeeping.
5. Use the Sync dialog to share databases with your team via datalakes.

## Additional Notes
- The agent and server both load the same `.env`, so keep secrets in one place.
- The DuckDB query tool can export results to CSV when invoked by the agent (see `src/tools/duckdb_query_tool.py` for parameters).
- Datalakes added through the web UI are automatically persisted to `datalakes.config.json`.
- Bring your own authentication or TLS termination if exposing the API publicly; no auth is implemented out of the box.
