import os
import signal
import sys

LOCK_FILE = '/tmp/xcode_mcp_server.lock'

# Check for existing lock file and kill any running process
if os.path.exists(LOCK_FILE):
    try:
        with open(LOCK_FILE, 'r') as f:
            old_pid = int(f.read().strip())
        # Check if process is running
        if old_pid != os.getpid():
            try:
                os.kill(old_pid, signal.SIGTERM)
                print(f"Stopped previous xcode_mcp_server.py process (PID {old_pid})")
            except ProcessLookupError:
                pass  # Process not running
    except Exception as e:
        print(f"Warning: Could not process lock file: {e}")
# Write current PID to the lock file
with open(LOCK_FILE, 'w') as f:
    f.write(str(os.getpid()))

from mcp.server.fastmcp import FastMCP
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from xcode_monitor_core import (
    XcodeMonitorCore,
    find_workspace_and_project,
    get_scheme_from_config,
    ensure_build_server_config,
    run_build,
    get_diagnostics
)

# Parse --xcodepath argument if present
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--xcodepath', type=str, default=None, help='Initial Xcode project path to monitor')
args, unknown = parser.parse_known_args()

# Initialize the core monitor with the provided path if available
monitor = XcodeMonitorCore(root_path=args.xcodepath)

# Create the MCP server
mcp = FastMCP("xcode_monitor")

@mcp.tool()
def get_project_info() -> dict:
    """Get workspace, project, and scheme info for the monitored path."""
    workspace, project = find_workspace_and_project(monitor.get_project_path())
    scheme = get_scheme_from_config()
    return {
        "workspace": str(workspace) if workspace else None,
        "project": str(project) if project else None,
        "scheme": scheme
    }

@mcp.tool()
def get_build_server_status() -> dict:
    """Check if build server config is present and valid."""
    status = ensure_build_server_config(monitor.get_project_path())
    return {"build_server_configured": status}

@mcp.tool()
def run_build_tool() -> dict:
    """Run a build and return its status and output."""
    success, output = run_build(monitor.get_project_path())
    return {"success": success, "output": output}

@mcp.tool()
def get_diagnostics_tool() -> list:
    """Get the latest diagnostics."""
    return get_diagnostics(monitor.get_project_path())

@mcp.tool()
def get_lsp_status() -> dict:
    """Stub: Returns LSP status (not yet implemented)."""
    return {"status": "not implemented"}



@mcp.tool()
def get_project_path() -> str:
    """Get the current monitored Xcode project path."""
    return monitor.get_project_path()

@mcp.tool()
def set_project_path(new_path: str) -> dict:
    """Set a new project path and restart monitoring."""
    updated_path = monitor.set_project_path(new_path)
    return {"success": True, "new_path": updated_path}

if __name__ == "__main__":
    mcp.run(transport='stdio')
