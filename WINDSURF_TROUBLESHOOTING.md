# MCP Server Troubleshooting Guide for Windsurf and Claude Desktop

## The Problem Fixed

**Original Error in Windsurf:**
```
Error: failed to create mcp stdio client: failed to start command: exec: "npx": executable file not found in $PATH
```

## Root Causes & Solutions

### 1. PATH Issues with npx
**Problem**: Windsurf couldn't find `npx` because it wasn't in the system PATH.
**Solution**: Updated Windsurf settings to use full paths to executables.

### 2. Different Configuration Formats
**Problem**: Windsurf and Claude Desktop use different configuration files and formats.
**Solution**: 
- **Claude Desktop**: Uses `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windsurf**: Uses `~/Library/Application Support/Windsurf/User/settings.json`

## Fixed Configuration Files

### Claude Desktop Configuration
**File**: `~/Library/Application Support/Claude/claude_desktop_config.json`
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

### Windsurf Configuration
**File**: `~/Library/Application Support/Windsurf/User/settings.json`
```json
{
  "mcp": {
    "servers": {
      "xcode-monitor": {
        "command": "/opt/homebrew/bin/python3",
        "args": [
          "/Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor/working_swift_mcp_server.py",
          "--swiftpath=/Users/williamblair/Desktop/XcodeMonitorMCP"
        ],
        "env": {}
      }
    }
  },
  "terminal.integrated.env.osx": {
    "PATH": "/Users/williamblair/.nvm/versions/node/v18.20.8/bin:${env:PATH}"
  }
}
```

## Key Changes Made

1. **Used Full Paths**: Instead of relying on PATH, used full paths to executables:
   - `/opt/homebrew/bin/python3` (instead of `python3`)
   - `/Users/williamblair/.nvm/versions/node/v18.20.8/bin/npx` (instead of `npx`)

2. **Fixed Python Environment**: Updated `cascade.mcp.pythonPath` to use the system Python with MCP installed

3. **Added PATH Extension**: Added Node.js bin directory to Windsurf's terminal PATH

4. **Direct Python Execution**: Changed from HTTP endpoint to direct Python script execution

## Testing the Fix

### Test the MCP Server Directly
```bash
cd /Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor
/opt/homebrew/bin/python3 working_swift_mcp_server.py --help
```

### Test with Specific Project Path
```bash
/opt/homebrew/bin/python3 working_swift_mcp_server.py --swiftpath=/Users/williamblair/Desktop/XcodeMonitorMCP
```

## Verification Steps

1. **Restart Windsurf** after updating the settings
2. **Check MCP Status** in Windsurf's output/terminal
3. **Test MCP Tools** by asking Windsurf to check project status
4. **Monitor Logs** if issues persist

## Available MCP Tools

Once connected, both Windsurf and Claude Desktop will have access to:
- `get_project_path()` - Get current monitored path
- `set_project_path(new_path)` - Change monitored path  
- `get_diagnostics()` - Get Swift/Xcode diagnostics
- `get_project_status()` - Get comprehensive project info
- `get_build_server_status()` - Check build server config
- `get_recent_updates()` - Get monitoring queue updates
- `clear_diagnostics_queue()` - Clear diagnostics queue
- `get_xcode_live_diagnostics()` - Get live Xcode diagnostics

## Common Issues & Solutions

### Issue: "Module not found" errors
**Solution**: Ensure MCP is installed with:
```bash
pip3 install --break-system-packages mcp
```

### Issue: "Permission denied" errors
**Solution**: Make sure the Python script is executable:
```bash
chmod +x /Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor/working_swift_mcp_server.py
```

### Issue: "No such file or directory"
**Solution**: Verify all paths in the configuration exist:
```bash
ls -la /opt/homebrew/bin/python3
ls -la /Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor/working_swift_mcp_server.py
```

### Issue: Node.js tools still fail
**Solution**: Verify npx path and update if needed:
```bash
which npx
# Update the path in Windsurf settings.json
```

## Log Locations

- **Windsurf Logs**: `~/Library/Application Support/Windsurf/logs/`
- **Claude Desktop Logs**: `~/Library/Application Support/Claude/logs/`

The configurations should now work for both Windsurf and Claude Desktop!
