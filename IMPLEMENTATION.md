# Submission Implementation

This repository includes a working FastMCP + SQLite implementation in `implementation/`.

## Project Structure

- `implementation/db.py`: SQLite adapter, validation, safe SQL construction.
- `implementation/init_db.py`: reproducible schema and seed data.
- `implementation/mcp_server.py`: FastMCP tools and schema resources.
- `implementation/verify_server.py`: repeatable smoke/demo script.
- `implementation/requirements.txt`: FastMCP dependency.
- `implementation/start_inspector.ps1`: MCP Inspector helper for Windows PowerShell.
- `implementation/tests/test_db.py`: unit tests for database behavior and validation.

## Setup

```powershell
cd D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation
py -3.11 -m pip install -r requirements.txt
py -3.11 init_db.py
```

The database is created at `implementation/data/school.db`. Running `init_db.py` is reproducible and resets the sample `students`, `courses`, and `enrollments` tables.

## Run The MCP Server

```powershell
cd D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation
py -3.11 mcp_server.py
```

The server exposes exactly three tools:

- `search`: filter rows, select columns, order results, and paginate.
- `insert`: insert one validated row and return the inserted payload.
- `aggregate`: run `count`, `avg`, `sum`, `min`, or `max`, optionally with filters and `group_by`.

The server exposes these resources:

- `schema://database`
- `schema://table/{table_name}`

## Validation And Safety

The implementation rejects unknown tables, unknown columns, unsupported operators, invalid aggregate metrics, invalid pagination values, and empty inserts. SQL values are bound as parameters; table and column identifiers are checked against SQLite schema metadata before they are quoted into SQL.

Supported filter examples:

```json
{ "cohort": "A1" }
```

```json
[{ "column": "score", "op": ">=", "value": 85 }]
```

Supported operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `like`, `in`, plus symbolic forms such as `=`, `!=`, and `>=`.

## Repeatable Verification

```powershell
cd D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation
py -3.11 verify_server.py
py -3.11 -m unittest discover -s tests -v
```

`verify_server.py` demonstrates full schema discovery, searching students in cohort `A1`, inserting a student, counting students, averaging score by cohort, and a clear invalid-table error.

## MCP Inspector

```powershell
cd D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation
./start_inspector.ps1
```

In Inspector, confirm that `search`, `insert`, and `aggregate` are discoverable, then read `schema://database` and `schema://table/students`.

## Example MCP Client Configurations

Claude Code `.mcp.json`:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "py",
      "args": [
        "-3.11",
        "D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation/mcp_server.py"
      ]
    }
  }
}
```

Codex `~/.codex/config.toml`:

```toml
[mcp_servers.sqlite_lab]
command = "py"
args = ["-3.11", "D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation/mcp_server.py"]
```

Gemini CLI:

```powershell
gemini mcp add sqlite-lab py -3.11 D:/vin-ai-thuc-chien/Day26-Track3-2A202600582-ThanVanHoang/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

## Demo Prompts

- Search all students in cohort A1, ordered by score descending.
- Insert a student named Than Van Hoang in cohort A1 with score 93.5.
- Count rows in the students table.
- Compute average student score by cohort.
- Read `schema://table/students`.
- Try searching table `missing_table` and show the error.
