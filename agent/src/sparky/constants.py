# Constants
# Use /tmp for PID file in containers to avoid persistence issues
# Check if running in Docker by looking for /.dockerenv or checking cgroup
def _get_pid_file_path(filename: str):
    """Determine appropriate PID file location."""
    import os

    # If in Docker, use /tmp which doesn't persist across restarts
    if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
        return "/tmp/" + filename
    # Otherwise use current directory
    return filename


SPARKY_CHAT_PID_FILE = _get_pid_file_path("sparky-chat.pid")
