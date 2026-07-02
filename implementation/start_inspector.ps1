$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python).Source
npx -y @modelcontextprotocol/inspector $Python (Join-Path $Root "mcp_server.py")
