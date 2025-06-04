# Xcode Monitor MCP Server - Fixed Version

This is the working version of the Xcode Monitor MCP Server that successfully connects to Claude Desktop.

## What Was Fixed

The original `swift_mcp_server.py` had several issues:
1. **Missing imports**: Missing `threading` import in `xcode_monitor_core.py`
2. **Import path issues**: Python couldn't find the local modules
3. **Dependency issues**: MCP library not installed
4. **Wrong function calls**: Some functions were called with incorrect parameters

## Fixed Files

- `working_swift_mcp_server.py` - The new, working MCP server
- `xcode_monitor_core.py` - Fixed with proper threading import
- `swift_mcp_monitor.py` - Already working (unchanged)

## Installation

1. **Install MCP library**:
   ```bash
   pip3 install --break-system-packages mcp
   ```

2. **Update Claude Desktop configuration**:
   The file `/Users/williamblair/Library/Application Support/Claude/claude_desktop_config.json` has been updated to use:
   ```json
   {
     "mcpServers": {
       "xcode_monitor": {
         "command": "/opt/homebrew/bin/python3",
         "args": ["/Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor/working_swift_mcp_server.py", "--swiftpath=/Users/williamblair/Desktop/XcodeMonitorMCP"],
         "env": {}
       }
     }
   }
   ```

## Available Tools

The MCP server provides these tools to Claude:

1. **get_project_path()** - Get the current monitored project path
2. **set_project_path(new_path)** - Change the monitored project path
3. **get_diagnostics()** - Get current Swift/Xcode diagnostics
4. **get_project_status()** - Get comprehensive project status (workspaces, build server, LSP, etc.)
5. **get_build_server_status()** - Check build server configuration
6. **get_recent_updates()** - Get recent updates from the monitoring queue
7. **clear_diagnostics_queue()** - Clear the diagnostics queue
8. **get_xcode_live_diagnostics()** - Get live diagnostics from Xcode

## Usage

1. **Restart Claude Desktop** after updating the configuration
2. **In Claude**: The xcode_monitor tools should now be available
3. **Test**: Ask Claude to "check my Xcode project status" or "get diagnostics"

## Project Structure

The server monitors Swift/Xcode projects and can:
- Detect workspaces and projects (.xcworkspace, .xcodeproj)
- Monitor file changes in Swift, Objective-C, and C/C++ files
- Parse build logs and diagnostics
- Check build server configuration
- Integrate with SourceKit-LSP
- Monitor Xcode live diagnostics

## Error Logs

If the server fails to start, check the logs in:
```
~/Library/Application Support/Claude/logs/mcp-server-xcode_monitor.log
```

## Test Commands

You can test the server directly:
```bash
cd /Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor
python3 working_swift_mcp_server.py --help
python3 working_swift_mcp_server.py --swiftpath=/path/to/your/project
```

The server is now ready to use with Claude Desktop!
