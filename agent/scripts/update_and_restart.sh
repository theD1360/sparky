#!/bin/bash
# A script to gracefully update the application from git and restart it.

set -e

PID_FILE="/tmp/badrobot.pid"
LOG_FILE="logs/badrobot.log"

# --- Cleanup function to be called on script exit ---
cleanup() {
    echo "Restart script finished."
}
trap cleanup EXIT

echo "Starting self-update and restart process..."

# --- 1. Stop the currently running application ---
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p $OLD_PID > /dev/null; then
        echo "Found running application with PID $OLD_PID. Attempting graceful shutdown..."
        kill -TERM $OLD_PID
        
        # Wait for up to 10 seconds for the process to terminate
        for i in {1..10}; do
            if ! ps -p $OLD_PID > /dev/null; then
                echo "Application stopped successfully."
                break
            fi
            sleep 1
        done

        # If it's still running, force kill it
        if ps -p $OLD_PID > /dev/null; then
            echo "Application did not stop gracefully. Forcing termination..."
            kill -KILL $OLD_PID
        fi
    else
        echo "Found stale PID file for PID $OLD_PID, but process is not running. Removing."
    fi
    rm -f "$PID_FILE"
else
    echo "No PID file found. Assuming application is not running."
fi

# --- 2. Pull latest changes (optional, uncomment to enable) ---
# echo "Fetching latest code from Git..."
# git fetch origin
# git reset --hard origin/main
# poetry install --no-root

# --- 3. Restart the application ---
echo "Starting the new application instance..."

# The application should be responsible for creating its own PID file on startup.
# We pass the --daemon flag to indicate it should run in the background.
# The PID file location is passed as an argument.
nohup poetry run badrobot chat --daemon --pidfile "$PID_FILE" > "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "New application instance started with PID $NEW_PID."
echo "You can monitor the logs at: $LOG_FILE"

exit 0
