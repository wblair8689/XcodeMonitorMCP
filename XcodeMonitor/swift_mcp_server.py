import os
import sys
import argparse
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import Resource
from swift_mcp_monitor import SwiftMCPMonitorCore
from xcode_monitor_core import ensure_build_server_config
from pydantic import PrivateAttr

parser = argparse.ArgumentParser()
parser.add_argument('--swiftpath', type=str, default=None, help='Initial Swift project path to monitor')
args, unknown = parser.parse_known_args()

monitor = SwiftMCPMonitorCore(root_path=args.swiftpath)
mcp = FastMCP("swift_mcp_server")



@mcp.tool()
def get_build_server_status() -> dict:
    """Check if build server config is present and valid."""
    status = ensure_build_server_config(monitor.root_path)
    return {"build_server_configured": status}



@mcp.tool()
def get_diagnostics_tool() -> list:
    """Get the latest diagnostics."""
    return monitor.get_diagnostics(monitor.root_path)

@mcp.tool()
def get_lsp_status() -> dict:
    """Returns LSP status (if implemented)."""
    # If you have LSP status logic, implement here
    return {"status": "not implemented"}

@mcp.tool()
def get_project_path() -> str:
    """Get the current monitored Swift project path."""
    return monitor.root_path

@mcp.tool()
def set_project_path(new_path: str) -> dict:
    """Set a new project path and restart monitoring."""
    monitor.root_path = os.path.abspath(new_path)
    return {"success": True, "new_path": monitor.root_path}

class DiagnosticsResource(Resource):
    _monitor: SwiftMCPMonitorCore = PrivateAttr()

    def __init__(self, monitor, **data):
        super().__init__(**data)
        self._monitor = monitor

    def list(self):
        return [{
            "id": "current",
            "type": "diagnostics",
            "label": "Diagnostics for current project",
            "project_path": self._monitor.root_path
        }]

    def get(self, resource_id):
        if resource_id == "current":
            return {
                "id": "current",
                "diagnostics": self._monitor.get_diagnostics(self._monitor.root_path)
            }
        raise KeyError("Resource not found")

    def read(self, resource_id):
        # Required by FastMCP Resource: returns resource content
        if resource_id == "current":
            return {
                "id": "current",
                "diagnostics": self._monitor.get_diagnostics(self._monitor.root_path)
            }
        raise KeyError("Resource not found")

    def watch(self, resource_id, notify):
        def watcher():
            last_sent = None
            while True:
                try:
                    update_type, *data = self._monitor.update_queue.get(timeout=10)
                    if update_type == "diagnostics":
                        diagnostics = data[0]
                        if diagnostics != last_sent:
                            notify({
                                "event": "diagnostics_updated",
                                "diagnostics": diagnostics
                            })
                            last_sent = diagnostics
                except Exception:
                    continue
        threading.Thread(target=watcher, daemon=True).start()

mcp.add_resource(DiagnosticsResource(monitor, uri="resource://diagnostics"))

if __name__ == "__main__":
    mcp.run(transport='stdio')
