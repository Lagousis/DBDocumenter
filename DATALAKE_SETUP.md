# Datalake Synchronization Setup Guide

## Overview
DBDocumenter now supports synchronizing projects with Azure Blob Storage datalakes. This feature allows you to:
- **Download** projects from Azure Storage to work locally
- **Upload** local projects to Azure Storage with version control
- **Manage** multiple datalakes with conflict resolution

## Configuration

### 1. Runtime Configuration (Recommended)

Datalakes can be added through the UI (Manage tab) and are **automatically persisted** to `datalakes.config.json` in the project root. These datalakes will be loaded on server startup.

**Advantages:**
- ✅ User-friendly interface with connection testing
- ✅ Automatically persisted across server restarts
- ✅ Easy to add/remove without editing files
- ✅ Container selection from existing containers

### 2. Environment Variable Setup (Optional)

For read-only datalakes that should not be modified at runtime, use the `DBDOC_DATALAKES` environment variable:

```bash
# Windows (cmd.exe)
set DBDOC_DATALAKES=[{"name":"production","type":"azure_storage","connection_string":"DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...","container_name":"dbdocumenter"}]

# Windows (PowerShell)
$env:DBDOC_DATALAKES='[{"name":"production","type":"azure_storage","connection_string":"DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...","container_name":"dbdocumenter"}]'

# Linux/Mac
export DBDOC_DATALAKES='[{"name":"production","type":"azure_storage","connection_string":"DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...","container_name":"dbdocumenter"}]'
```

**Note:** Datalakes from environment variables cannot be removed through the UI and are treated as read-only.

### 3. Datalake Configuration Schema

Each datalake object requires:
- **name**: Unique identifier (e.g., "production", "staging")
- **type**: Storage type (currently only "azure_storage" supported)
- **connection_string**: Azure Storage account connection string
- **container_name**: Blob container name (default: "dbdocumenter")

### 3. Multiple Datalakes Example

```json
[
  {
    "name": "production",
    "type": "azure_storage",
    "connection_string": "DefaultEndpointsProtocol=https;AccountName=prod;AccountKey=...;EndpointSuffix=core.windows.net",
    "container_name": "dbdocumenter"
  },
  {
    "name": "staging",
    "type": "azure_storage",
    "connection_string": "DefaultEndpointsProtocol=https;AccountName=stage;AccountKey=...;EndpointSuffix=core.windows.net",
    "container_name": "dbdocumenter-staging"
  }
]
```

## Azure Blob Storage Structure

Projects are stored with the following hierarchy:
```
{container_name}/
  {project_name}/
    {version}/
      {project_name}.duckdb
      {project_name}.schema.json
```

**Example:**
```
dbdocumenter/
  sales/
    1.0.0/
      sales.duckdb
      sales.schema.json
    1.1.0/
      sales.duckdb
      sales.schema.json
```

## Using the Sync Feature

### 1. Access Sync Dialog
Click the **Sync** button (circular arrows icon) in the header toolbar.

### 2. Download Tab
- **Select Datalake**: Choose from configured datalakes
- **View Projects**: Browse available projects with versions
- **Conflict Resolution**:
  - **Overwrite**: Replace local files with downloaded version
  - **Keep Both**: Rename existing files with version suffix (e.g., `sales-1.0.0.duckdb`)

### 3. Upload Tab
- **Select Datalake**: Choose destination datalake
- **Select Project**: Pick local project to upload
- **New Version** (optional): Specify semantic version (e.g., "1.1.0")
  - Leave empty to use current project version
  - Incremented version is recommended for new uploads

### 4. Manage Tab
- **Add Datalake**: Create new datalake connections with:
  - Storage type selection (Azure Storage)
  - Connection string testing
  - Container selection from available containers
  - **Automatic persistence** to `datalakes.config.json`
- **Remove Datalake**: Delete datalake configurations (automatically saved)
- **View Configured**: See all active datalakes with:
  - Storage account name
  - Container name
  - Storage type

**Note:** Environment-based datalakes appear in the list but cannot be removed through the UI.

## Version Control

### Schema Version Field
Each project's `schema.json` now includes a `version` field:
```json
{
  "version": "1.0.0",
  "display_name": "Sales Database",
  "description": "Company sales data",
  ...
}
```

### Version Update on Upload
When uploading, you can:
1. **Keep current version**: Upload as-is
2. **Specify new version**: Provide semantic version string (e.g., "2.0.0")
   - Version is updated in schema.json before upload

### Semantic Versioning
Follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

## Local-Only Mode

The application works **without datalakes configured**:
- All features remain functional locally
- Sync button is always visible (manages datalakes dynamically)
- No cloud dependencies required

## Persistence and Configuration Files

### datalakes.config.json
Runtime-added datalakes are automatically saved to `datalakes.config.json` in the project root:

```json
[
  {
    "name": "production",
    "type": "azure_storage",
    "connection_string": "DefaultEndpointsProtocol=https;AccountName=...",
    "container_name": "dbdocumenter"
  }
]
```

**Important:**
- ✅ Automatically created when you add a datalake through the UI
- ✅ Loaded on server startup
- ✅ Updated when you add/remove datalakes
- ⚠️ **Not committed to git** (included in `.gitignore` for security)
- ⚠️ Contains sensitive connection strings - keep secure

### Environment vs File Configuration
- **Environment variables** (`DBDOC_DATALAKES`): Read-only, cannot be modified through UI
- **Config file** (`datalakes.config.json`): Managed through UI, automatically persisted
- **Priority**: Both are loaded and merged (environment datalakes take precedence for duplicate names)

## Azure Storage Requirements

### 1. Storage Account
- Create Azure Storage Account (General Purpose v2)
- Note connection string from Azure Portal

### 2. Container
- Create blob container (e.g., "dbdocumenter")
- Public access: Private (recommended)

### 3. Connection String Location
Azure Portal → Storage Account → Access Keys → Connection String

**Format:**
```
DefaultEndpointsProtocol=https;
AccountName=<account_name>;
AccountKey=<account_key>;
EndpointSuffix=core.windows.net
```

## Security Best Practices

1. **Never commit connection strings** to version control
2. **Use environment variables** for sensitive configuration
3. **Rotate access keys** regularly in Azure Portal
4. **Consider Azure Key Vault** for production environments
5. **Use SAS tokens** instead of account keys (future enhancement)

## Troubleshooting

### "No datalakes configured"
- Check `DBDOC_DATALAKES` environment variable is set
- Verify JSON syntax is valid
- Restart application after setting environment variable

### "Failed to connect to Azure Storage"
- Verify connection string is correct
- Check container exists
- Ensure storage account is accessible
- Review Azure Storage firewall rules

### "Project already exists" (Download)
- Choose conflict resolution strategy:
  - Overwrite to replace
  - Keep Both to preserve existing files

### "Version format invalid"
- Use semantic versioning: `X.Y.Z` (e.g., "1.0.0")
- Avoid non-numeric characters except dots

## API Endpoints

If integrating programmatically:

- `GET /datalakes` - List configured datalakes
- `GET /datalakes/{name}/projects` - List projects in datalake
- `POST /sync/download` - Download project from datalake
- `POST /sync/upload` - Upload project to datalake
- `POST /datalakes` - Add new datalake
- `DELETE /datalakes/{name}` - Remove datalake
- `DELETE /datalakes/{name}/projects/{project}/{version}` - Delete project version

## Dependencies

**Backend:**
```
azure-storage-blob>=12.19.0
```

Install with:
```bash
pip install -r requirements.txt
```

**Frontend:**
- No additional dependencies (uses existing axios)

## Future Enhancements

Potential improvements:
- Support for AWS S3, Google Cloud Storage
- SAS token authentication
- Automatic version increment UI
- Batch operations (multi-project sync)
- Sync scheduling/automation
- Conflict merge UI
- Project comparison between versions
