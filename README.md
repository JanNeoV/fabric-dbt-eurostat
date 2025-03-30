# Fabric Eurostat DBT Project

This repo demonstrates using [dbt](https://www.getdbt.com/) with Microsoft Fabric to transform data from Eurostat. It draws heavily on:

- [dbt-labs/jaffle-shop-classic](https://github.com/dbt-labs/jaffle-shop-classic)  
- Microsoft’s tutorial: [Set up dbt with Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/data-warehouse/tutorial-setup-dbt)

While some configurations have been updated to reflect local environment needs and Eurostat data ingestion, the core structure remains similar to the Jaffle Shop and Fabric tutorial examples.

## Project Overview

1. **Data Source**: Data is fetched from [Eurostat](https://ec.europa.eu/eurostat/web/main) APIs or Lakehouse tables containing Eurostat data.  
2. **Three Schemas**:
   - **Source**: Stores raw or lightly processed data from Eurostat.  
   - **Staging**: Refines and cleans the Source data for easier use.  
   - **Mart**: Final presentation or reporting tables.  
3. **dbt** handles all transformations, orchestrated within Microsoft Fabric’s Data Warehouse.

## Requirements

1. **Python 3.7+**  
   Make sure Python is installed. You can check with `python --version` or `python3 --version`.

2. **Microsoft ODBC Driver for SQL Server**  
   On Windows, install via [Microsoft Docs](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).  
   On macOS or Linux, follow the [respective installation instructions](https://learn.microsoft.com/sql/connect/odbc/).

3. **dbt-fabric** (latest version)  
   - Install with `pip install dbt-fabric`.  
   - This adapter allows dbt to communicate with Microsoft Fabric’s data warehouses.

4. **Azure CLI**  
   - Needed if you use `authentication: CLI` in your dbt profile.  
   - [Installation instructions](https://learn.microsoft.com/cli/azure/install-azure-cli).  
   - After installation, run `az login` before using dbt so credentials are available.

Once installed, verify you can run:
```bash
dbt --version
az --version
```
and that your Python environment is up-to-date.

> **Note**: In the future, these dependencies could potentially be packaged into a combined environment (e.g., a Docker image or Conda environment) to simplify installation.

## Setup

1. **Clone this repository**:
   ```bash
   git clone https://github.com/YourOrg/fabric-eurostat-dbt.git
   cd fabric-eurostat-dbt
   ```

2. **Configure `profiles.yml`** (in `~/.dbt/` or your chosen location).  
   Make sure you set:
   - `database` to your Fabric Data Warehouse name (e.g., `DWH_Eurostat`).  
   - `host` to the Fabric warehouse endpoint (e.g., `<yourserver>.datawarehouse.fabric.microsoft.com`).  
   - `schema` to an empty string or your default schema, depending on your approach.  
   - `authentication` to `CLI`, `interactive`, or another method.

3. **Edit `dbt_project.yml`** as needed to match your model folders and schema naming conventions (e.g., `Source`, `Staging`, `Mart`).

## Running the Project

1. **Test your connection**:
   ```bash
   dbt debug
   ```
   This confirms dbt can connect to Fabric via your selected authentication method.

2. **Execute models**:
   ```bash
   dbt run
   ```
   Models in `models/` (and their subfolders) will run. The final tables land in the schemas defined in your `dbt_project.yml`.

3. **Check for test assertions** (if any are defined):
   ```bash
   dbt test
   ```

## Contributing / Issues

- If you have questions or encounter issues, please open an issue or submit a pull request on this repo.
- PRs for improved example models, additional transformations, or environment setup instructions are welcome.

## Credits

- **dbt-labs** for the [jaffle-shop-classic](https://github.com/dbt-labs/jaffle-shop-classic) starter project.
- **Microsoft** for the [Fabric dbt tutorial](https://learn.microsoft.com/en-us/fabric/data-warehouse/tutorial-setup-dbt).
- **Eurostat** for publicly available datasets.

---

**Enjoy exploring Eurostat data in Microsoft Fabric with dbt!**
