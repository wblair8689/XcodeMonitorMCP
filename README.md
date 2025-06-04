# Xcode Monitor MCP Server

A comprehensive Model Context Protocol (MCP) server for monitoring Swift/Xcode projects, providing real-time diagnostics, build status, and project information to AI assistants like Claude Desktop and Windsurf.

## ✅ Current Status: WORKING

The MCP server is now fully operational and successfully connects to both Claude Desktop and Windsurf.

## Features

- **Real-time Xcode Project Monitoring**: Detect workspaces, projects, and schemes
- **Live Diagnostics**: Get Swift/Xcode build errors and warnings
- **SourceKit-LSP Integration**: Monitor Language Server Protocol status
- **Build Server Support**: Configure and monitor Xcode build servers
- **File Change Detection**: Monitor Swift, Objective-C, and C/C++ file changes
- **Multi-Platform Support**: Works with Claude Desktop and Windsurf
- **Comprehensive Logging**: Detailed error reporting and debugging

## Installation

### Prerequisites

- **macOS** (required for Xcode integration)
- **Python 3.10+** (tested with Python 3.13)
- **Xcode** and Xcode Command Line Tools
- **Node.js** (for some MCP features)

### 1. Install Dependencies

```bash
# Install MCP library
pip3 install --break-system-packages mcp

# Verify installation
python3 -c "import mcp; print('MCP installed successfully')"
```

### 2. Clone and Setup

```bash
git clone <repository-url> XcodeMonitorMCP
cd XcodeMonitorMCP
```

### 3. Configure Claude Desktop

Update `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "xcode_monitor": {
      "command": "/opt/homebrew/bin/python3",
      "args": [
        "/Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor/working_swift_mcp_server.py",
        "--swiftpath=/Users/williamblair/Desktop/XcodeMonitorMCP"
      ],
      "env": {
        "PYTHONPATH": "/Users/williamblair/Desktop/XcodeMonitorMCP/XcodeMonitor",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### 4. Configure Windsurf (Optional)

Update `~/Library/Application Support/Windsurf/User/settings.json`:

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
  }
}
```

## Available MCP Tools

Once connected, the following tools are available to AI assistants:

### Core Tools
- **`get_project_path()`** - Get the current monitored project path
- **`set_project_path(new_path)`** - Change the monitored project path
- **`get_project_status()`** - Get comprehensive project information

### Diagnostics Tools
- **`get_diagnostics()`** - Get current Swift/Xcode diagnostics and errors
- **`get_xcode_live_diagnostics()`** - Get live diagnostics directly from Xcode
- **`clear_diagnostics_queue()`** - Clear the diagnostics queue

### Build Tools
- **`get_build_server_status()`** - Check build server configuration
- **`get_recent_updates()`** - Get recent updates from the monitoring queue

## Usage Examples

### In Claude Desktop or Windsurf:

```
"What's the current status of my Xcode project?"
"Are there any build errors in my Swift code?"
"Can you check the SourceKit-LSP status?"
"Monitor my project for file changes"
"Get the latest diagnostics from Xcode"
```

## Project Structure

```
XcodeMonitorMCP/
├── XcodeMonitor/
│   ├── working_swift_mcp_server.py    # Main MCP server (WORKING)
│   ├── swift_mcp_monitor.py           # Core monitoring logic
│   ├── xcode_monitor_core.py          # Core utilities
│   ├── swift_mcp_monitor_inspector.py # GUI inspector
│   └── XcodeViewer.py                 # Legacy viewer
├── MCPGameTemplate.xcodeproj/         # Example Swift project
├── README_FIXED.md                    # Detailed fix documentation
├── WINDSURF_TROUBLESHOOTING.md        # Windsurf-specific setup
└── venv/                              # Python virtual environment
```

## Monitoring Capabilities

The server can monitor and report on:

- **Workspaces and Projects**: `.xcworkspace` and `.xcodeproj` files
- **Build Status**: Recent builds, success/failure status
- **File Changes**: Swift (`.swift`), Objective-C (`.m`, `.h`), C/C++ files
- **Diagnostics Sources**:
  - Xcode live diagnostics
  - Build logs via XCLogParser
  - SourceKit-LSP diagnostics
  - SwiftPM build logs
- **Build Server Configuration**: `buildServer.json` status

## Troubleshooting

### MCP Server Not Connecting

1. **Restart the application**: Completely quit and restart Claude Desktop/Windsurf
2. **Check logs**: 
   ```bash
   tail -f ~/Library/Application\ Support/Claude/logs/mcp-server-xcode_monitor.log
   ```
3. **Test manually**:
   ```bash
   /opt/homebrew/bin/python3 XcodeMonitor/working_swift_mcp_server.py --help
   ```

### Common Issues

- **"Module not found"**: Ensure MCP is installed with `pip3 install --break-system-packages mcp`
- **"Permission denied"**: Check file permissions with `ls -la XcodeMonitor/working_swift_mcp_server.py`
- **"No such file"**: Verify all paths in configuration are absolute and correct
- **JSON syntax errors**: Validate configuration with `python3 -m json.tool config.json`

### Windsurf-Specific Issues

- **"npx not found"**: Use full paths to executables in configuration
- **Process conflicts**: Restart both applications if they interfere with each other

## Development

### Testing the Server

```bash
# Test server startup
python3 XcodeMonitor/working_swift_mcp_server.py --help

# Test with specific project
python3 XcodeMonitor/working_swift_mcp_server.py --swiftpath="/path/to/your/project"

# Run the GUI inspector
python3 XcodeMonitor/swift_mcp_monitor_inspector.py
```

### Adding New Features

The server is built with a modular architecture:
- `SwiftMCPMonitorCore`: Core monitoring logic
- MCP tools are defined in `working_swift_mcp_server.py`
- Diagnostic sources can be extended in the `get_diagnostics()` method

## Log Files

- **Claude Desktop**: `~/Library/Application Support/Claude/logs/mcp-server-xcode_monitor.log`
- **Windsurf**: `~/Library/Application Support/Windsurf/logs/`

## Version History

- **v0.1.0**: Initial implementation with basic monitoring
- **v0.2.0**: Added comprehensive diagnostics and build server support
- **v1.0.0**: **CURRENT** - Fixed all import issues, added robust error handling, full Claude Desktop + Windsurf support

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test with both Claude Desktop and Windsurf
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review log files for error details
3. Test the server manually to isolate issues
4. Create an issue with diagnostic information

---

**Status**: ✅ **FULLY WORKING** - The MCP server successfully connects to Claude Desktop and provides comprehensive Xcode/Swift project monitoring capabilities.
