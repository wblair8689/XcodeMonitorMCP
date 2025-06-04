#!/usr/bin/env python3
"""
Working Swift MCP Server - Fixed version with proper imports
"""
import os
import sys
import argparse
import threading

# Add the current directory to Python path to ensure imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from mcp.server.fastmcp import FastMCP
    from swift_mcp_monitor import SwiftMCPMonitorCore
    from xcode_monitor_core import ensure_build_server_config
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--swiftpath', type=str, default=None, help='Initial Swift project path to monitor')
args, unknown = parser.parse_known_args()

# Initialize the monitor
try:
    monitor = SwiftMCPMonitorCore(root_path=args.swiftpath)
    mcp = FastMCP("swift_mcp_server")
    print(f"Initialized monitor for path: {monitor.root_path}", file=sys.stderr)
except Exception as e:
    print(f"Failed to initialize monitor: {e}", file=sys.stderr)
    sys.exit(1)

@mcp.tool()
def get_project_path() -> str:
    """Get the current monitored Swift project path."""
    return monitor.root_path

@mcp.tool()
def set_project_path(new_path: str) -> dict:
    """Set a new project path and restart monitoring."""
    try:
        if not os.path.exists(new_path):
            return {"success": False, "error": f"Path does not exist: {new_path}"}
        
        old_path = monitor.root_path
        
        # Stop current monitoring
        monitor.stop()
        monitor.join_threads()
        
        # Update path
        monitor.root_path = os.path.abspath(new_path)
        
        # Restart monitoring
        monitor.monitoring = True
        monitor.monitor_thread = threading.Thread(target=monitor.monitor_loop, daemon=True)
        monitor.monitor_thread.start()
        monitor.file_monitor_thread = threading.Thread(target=monitor.file_monitor_loop, daemon=True)
        monitor.file_monitor_thread.start()
        
        return {
            "success": True, 
            "old_path": old_path, 
            "new_path": monitor.root_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def get_diagnostics() -> list:
    """Get the latest diagnostics from the Swift project."""
    try:
        return monitor.get_diagnostics()
    except Exception as e:
        return [{"severity": "error", "message": f"Error getting diagnostics: {str(e)}"}]

@mcp.tool()
def get_project_status() -> dict:
    """Get comprehensive project status including workspaces, projects, and build info."""
    try:
        status = {
            "project_path": monitor.root_path,
            "project_info": monitor.check_project_status(),
            "build_server": monitor.check_build_server(),
            "lsp_status": monitor.check_lsp_status(),
            "recent_builds": monitor.check_recent_builds(),
            "build_details": monitor.get_build_details()
        }
        return status
    except Exception as e:
        return {"error": f"Error getting project status: {str(e)}"}

@mcp.tool()
def get_build_server_status() -> dict:
    """Check if build server config is present and valid."""
    try:
        # Change to the monitor's directory for the check
        original_cwd = os.getcwd()
        os.chdir(monitor.root_path)
        try:
            status = ensure_build_server_config(monitor.root_path)
            return {"build_server_configured": status, "path": monitor.root_path}
        finally:
            os.chdir(original_cwd)
    except Exception as e:
        return {"build_server_configured": False, "error": str(e)}

@mcp.tool()
def get_recent_updates() -> list:
    """Get recent updates from the monitoring queue."""
    updates = []
    try:
        # Get up to 10 recent updates from the queue
        for _ in range(10):
            if not monitor.update_queue.empty():
                update = monitor.update_queue.get_nowait()
                updates.append({
                    "type": update[0],
                    "data": update[1:] if len(update) > 1 else [],
                    "timestamp": str(threading.current_thread().ident)
                })
            else:
                break
    except Exception as e:
        updates.append({"error": f"Error getting updates: {str(e)}"})
    return updates

@mcp.tool()
def clear_diagnostics_queue() -> dict:
    """Clear the diagnostics update queue."""
    try:
        count = 0
        while not monitor.update_queue.empty():
            monitor.update_queue.get_nowait()
            count += 1
        return {"success": True, "cleared_items": count}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def get_xcode_live_diagnostics() -> list:
    """Get live diagnostics directly from Xcode."""
    try:
        return monitor.get_xcode_live_diagnostics()
    except Exception as e:
        return [{"severity": "error", "message": f"Error getting live diagnostics: {str(e)}"}]

if __name__ == "__main__":
    try:
        print(f"Starting Swift MCP Server monitoring: {monitor.root_path}", file=sys.stderr)
        print(f"Monitor status - monitoring: {monitor.monitoring}", file=sys.stderr)
        print(f"Available tools: {[tool.__name__ for tool in [get_project_path, set_project_path, get_diagnostics, get_project_status, get_build_server_status, get_recent_updates, clear_diagnostics_queue, get_xcode_live_diagnostics]]}", file=sys.stderr)
        mcp.run(transport='stdio')
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr)
        sys.exit(1)
