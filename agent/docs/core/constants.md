# Constants (`constants.py`)

This module contains fundamental, hard-coded constants that are used across the system.

## `PID_FILE`

*   **Value:** `"bot.pid"`
*   **Purpose:** Defines the filename for the process ID (PID) file. This file is used to store the main process ID of the application, which allows other processes or scripts to interact with it (e.g., to send signals for shutdown or restart).
