# Logging Configuration (`logging_config.py`)

This module is responsible for setting up the entire logging framework for the Sparky application. It uses Python's built-in `logging` module and integrates with the `rich` library to provide clear, colorized console output.

## Key Features

*   **Centralized Setup:** The `setup_logging()` function is the single entry point for configuring all logging behavior.
*   **Environment-Driven Configuration:** Logging behavior can be controlled via environment variables, which is ideal for deploying the application in different environments (e.g., development vs. production) without code changes.
*   **Dual Output:** Logs are sent to both a rotating file and the console.
    *   **File Logging:** Provides a persistent record of events, which is critical for debugging and auditing. The logs are rotated to prevent them from growing indefinitely.
    *   **Console Logging:** Uses the `rich` library to provide an enhanced, human-readable view of logs in real-time.
*   **Graceful Defaults:** If environment variables are not set, the system defaults to sensible values (`INFO` level, `logs` directory).

## The `setup_logging()` Function

This is the main function in the module. When called at application startup, it performs the following steps:

1.  **Loads Environment Variables:** It uses `dotenv` to load variables from a `.env` file.
2.  **Reads `LOG_DIR`:** It checks for the `LOG_DIR` environment variable. If not found, it defaults to a directory named `logs/`. It then creates this directory if it doesn't already exist.
3.  **Reads `LOG_LEVEL`:** It checks for the `LOG_LEVEL` environment variable and maps it to a Python `logging` constant (e.g., "INFO" -> `logging.INFO`). It defaults to `INFO` and warns the user if an invalid level is provided.
4.  **Defines Configuration Dictionary:** It constructs a dictionary that defines formatters, handlers, and the root logger.
    *   **`formatters`**: Defines how log messages are structured. `default` is a simple format for the console, while `detailed` includes a timestamp and log level for the file.
    *   **`handlers`**: Defines where logs are sent.
        *   `file`: A `RotatingFileHandler` that writes to `sparky.log` within the `LOG_DIR`, with a max size of 5 MB and up to 5 backup files.
        *   `rich`: A `RichHandler` that prints formatted logs to the standard error console.
    *   **`root`**: The root logger is configured to use both the `file` and `rich` handlers and to process all messages at or above the configured `log_level`.
5.  **Applies Configuration:** Finally, it applies this entire configuration using `logging.config.dictConfig()`.

## Environment Variables

*   `LOG_DIR`: The directory where log files will be stored.
    *   **Default:** `logs`
*   `LOG_LEVEL`: The minimum level of log messages to capture.
    *   **Default:** `INFO`
    *   **Valid Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive)
