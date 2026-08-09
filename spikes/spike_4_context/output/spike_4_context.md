## Platform Intelligence Engine (PIE) - Verified Asset Context

**Target Entity:** `DataLakeCsv` | **Type:** `Dataset`

### Executive Summary
- **Asset:** `DataLakeCsv` (Type: `Dataset`)
- **Folder:** `DataLake`
- **Description:** Azure Data Factory Enterprise Asset

### Minute Activity Execution Sequence
*None recorded.*

### Input / Output Datasets & Schemas
- **`DataLakeCsv`** *[DelimitedText]* (LinkedService: `DataLake`, Folder: `DataLake`)
  - Columns: *Dynamic / Schema-on-Read*

### Upstream Lineage & Downstream Blast Radius
- **Systemic Risk Level:** `CRITICAL` (Risk Score: `100/100`)
- **Total Downstream Blast Radius:** `20` affected entities
- **Impacted Downstream Pipelines:** `Pre Release`
- **Upstream Inflow Feeds:** `Get VendorSet` (Activity), `RailCarRx_VendorLoad` (Pipeline), `Lookup VendorSet` (Activity), `ForEach Vendor` (Activity)

### Connected Compute & Storage Services
- **`DataLake`** *[AzureBlobFS]* -> Host/Endpoint: `Configured via Key Vault` *(Secrets Redacted)*