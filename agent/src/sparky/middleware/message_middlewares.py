"""Message middleware implementations.

This module contains middleware that intercepts and processes user messages
before they are sent to the AI model.
"""

import json
import logging
import os
import re

from .base import BaseMiddleware, MessageContext, MiddlewareType, NextMessageMiddleware

logger = logging.getLogger(__name__)


class CommandPromptMiddleware(BaseMiddleware):
    """
    Intercepts messages in the format `/<command> <input>` and uses
    the appropriate MCP prompt instead of sending directly to the model.

    Example:
        User: "/discover_concept Python"
        -> Calls get_prompt("discover_concept", {"concept_name": "Python"})
        -> Sends the rendered prompt to the model
    """

    middleware_type = MiddlewareType.MESSAGE

    # Pattern to match /<command> with optional input
    # Captures: /command or /command with text
    COMMAND_PATTERN = re.compile(r"^/(\w+)(?:\s+(.+))?$", re.DOTALL)

    async def __call__(
        self, context: MessageContext, next_call: NextMessageMiddleware
    ) -> MessageContext:
        """Process command-style messages."""
        match = self.COMMAND_PATTERN.match(context.message.strip())

        if not match:
            # Not a command, continue normally
            return await next_call(context)

        command_name = match.group(1)
        command_input = match.group(2).strip() if match.group(2) else ""

        logger.info(
            f"Command detected: /{command_name} with input: {command_input[:50]}..."
        )

        # Try to get the prompt from MCP servers
        try:
            bot = context.bot_instance
            if not bot or not bot.toolchain:
                logger.warning("No toolchain available for command prompts")
                return await next_call(context)

            # List available prompts to check if this command exists
            available_prompts = await bot.list_prompts()
            prompt_names = [prompt.name for _, prompt in available_prompts]

            if command_name not in prompt_names:
                # Command not found, try to provide helpful feedback
                similar = [p for p in prompt_names if command_name.lower() in p.lower()]
                if similar:
                    context.modified_message = (
                        f"I noticed you tried to use the command '/{command_name}', "
                        f"but it doesn't exist. Did you mean one of these: {', '.join(similar)}?\n\n"
                        f"For now, I'll process your message normally: {command_input}"
                    )
                else:
                    context.modified_message = (
                        f"I noticed you tried to use the command '/{command_name}', "
                        f"but it doesn't exist. Available commands: {', '.join(prompt_names)}\n\n"
                        f"For now, I'll process your message normally: {command_input}"
                    )
                return await next_call(context)

            # Get the prompt schema to understand what arguments it expects
            prompt_result = None
            for client, prompt in available_prompts:
                if prompt.name == command_name:
                    # Try to parse arguments from the command_input
                    # For simple prompts, we'll pass the input as the first argument
                    arguments = {}

                    # Check if the prompt has arguments defined
                    if hasattr(prompt, "arguments") and prompt.arguments:
                        # Try to map the input to the first argument
                        arg_list = list(prompt.arguments)

                        # Check if first arg is required (no default value)
                        first_arg = arg_list[0]
                        is_required = (
                            not hasattr(first_arg, "required") or first_arg.required
                        )

                        if len(arg_list) == 1:
                            # Single argument
                            if command_input or is_required:
                                # Use the input (or empty string if required but no input)
                                arguments[first_arg.name] = command_input
                            # If not required and no input, don't pass the argument (use default)
                        else:
                            # Multiple arguments - try to parse them
                            # Format: /command arg1=value1 arg2=value2
                            # OR: /command value1 (for first arg only)
                            if command_input and "=" in command_input:
                                # Key=value format
                                for part in command_input.split():
                                    if "=" in part:
                                        key, value = part.split("=", 1)
                                        arguments[key.strip()] = value.strip()
                            elif command_input:
                                # Positional format - just use first arg
                                arguments[first_arg.name] = command_input
                            # If no input and arg has default, don't pass it
                    else:
                        # No arguments defined, pass empty dict or single input
                        arguments = {"input": command_input} if command_input else {}

                    # Get the rendered prompt
                    try:
                        logger.info(
                            f"Calling get_prompt('{command_name}', {arguments})"
                        )
                        prompt_result = await bot.get_prompt(command_name, arguments)
                        break
                    except Exception as e:
                        logger.error(f"Error rendering prompt '{command_name}': {e}")
                        context.modified_message = (
                            f"Error using command '/{command_name}': {str(e)}\n\n"
                            f"Processing your message normally: {command_input}"
                        )
                        return await next_call(context)

            if prompt_result:
                logger.info(
                    f"Successfully rendered prompt for command '/{command_name}'"
                )
                # Replace the original message with the rendered prompt
                context.modified_message = prompt_result
            else:
                logger.warning(f"Could not render prompt for command '{command_name}'")
                context.modified_message = command_input

            return await next_call(context)

        except Exception as e:
            logger.error(f"Error processing command '{command_name}': {e}")
            # Fall back to processing the input normally
            context.modified_message = command_input
            return await next_call(context)


class ResourceFetchingMiddleware(BaseMiddleware):
    """
    Intercepts messages containing `@<resource>` patterns and appends
    the actual content from MCP resources to the end of the message.

    Example:
        User: "Show me @knowledge://stats"
        -> Fetches content from knowledge://stats resource
        -> Keeps "@knowledge://stats" in message
        -> Appends resource content at the end

        User: "What do we know about Python? @memories"
        -> Fetches content from a resource matching "memories"
        -> Keeps "@memories" in message
        -> Appends resource content at the end

    Note: Patterns that look like decorators (@decorator_name()) or are followed
    by parentheses are automatically ignored.
    """

    middleware_type = MiddlewareType.MESSAGE

    # Pattern to match @<resource> where resource can be a URI or simple name
    # But not followed by '(' which would indicate a decorator
    RESOURCE_PATTERN = re.compile(r"@([\w:/\-\.]+)(?!\()")

    async def __call__(
        self, context: MessageContext, next_call: NextMessageMiddleware
    ) -> MessageContext:
        """Process messages with resource references."""
        message = context.modified_message or context.message
        matches = list(self.RESOURCE_PATTERN.finditer(message))

        if not matches:
            # No resource references, continue normally
            return await next_call(context)

        try:
            bot = context.bot_instance
            if not bot or not bot.toolchain:
                logger.warning("No toolchain available for resource fetching")
                return await next_call(context)

            # Get all available resources
            available_resources = await bot.list_resources()

            # Build a mapping of URIs and names to resources
            resource_map = {}
            for client, resource in available_resources:
                # Convert URI to string (it may be an AnyUrl object)
                uri_str = str(resource.uri)

                # Map by full URI
                resource_map[uri_str] = (client, resource)

                # Also map by URI without scheme (e.g., "stats" for "knowledge://stats")
                if "://" in uri_str:
                    _, path = uri_str.split("://", 1)
                    # Map the full path after scheme
                    resource_map[path] = (client, resource)
                    # Also map just the last part (e.g., "stats")
                    if "/" in path:
                        last_part = path.split("/")[-1]
                        if last_part and last_part not in resource_map:
                            resource_map[last_part] = (client, resource)
                    else:
                        resource_map[path] = (client, resource)

            # Process each match and collect resources to append
            resources_to_append = []
            processed_refs = set()

            for match in matches:
                resource_ref = match.group(1)
                full_match = match.group(0)  # Includes the @ symbol

                if full_match in processed_refs:
                    # Already processed this reference
                    continue

                processed_refs.add(full_match)

                # Try to find the resource
                if resource_ref in resource_map:
                    _, resource = resource_map[resource_ref]
                    # Convert URI to string for consistent handling
                    resource_uri = str(resource.uri)

                    try:
                        logger.info("Fetching resource: %s", resource_uri)
                        content = await bot.read_resource(resource_uri)

                        # Try to parse as JSON for pretty formatting
                        try:
                            parsed = json.loads(content)
                            # Format as pretty JSON for better readability
                            formatted_content = json.dumps(parsed, indent=2)
                            resource_text = (
                                f"---\n"
                                f"[Resource: {resource_uri}]\n"
                                f"```json\n{formatted_content}\n```"
                            )
                        except (json.JSONDecodeError, TypeError):
                            # Not JSON, use as-is
                            resource_text = (
                                f"---\n" f"[Resource: {resource_uri}]\n" f"{content}"
                            )

                        resources_to_append.append(resource_text)
                        logger.info("Successfully fetched resource: %s", resource_uri)
                    except Exception as e:  # noqa: BLE001
                        logger.error("Error reading resource '%s': %s", resource_uri, e)
                        error_text = (
                            f"---\n"
                            f"[Error fetching resource '{resource_uri}': {str(e)}]"
                        )
                        resources_to_append.append(error_text)
                else:
                    # Resource not found - log at debug level (user might not be referencing a resource)
                    available_names = sorted(set(resource_map.keys()))
                    logger.debug(
                        "Pattern '@%s' matched but resource not found. Available: %s...",
                        resource_ref,
                        ", ".join(available_names[:5]),
                    )
                    # Don't append anything if resource doesn't exist
                    # This allows users to naturally use @ symbols without triggering errors
                    continue

            # Append all fetched resources to the end of the message
            if resources_to_append:
                modified_message = message + "\n\n" + "\n\n".join(resources_to_append)
                context.modified_message = modified_message
                logger.info(
                    "Message modified with %d appended resource(s)",
                    len(resources_to_append),
                )

            return await next_call(context)

        except Exception as e:  # noqa: BLE001
            logger.error("Error in ResourceFetchingMiddleware: %s", e)
            # Continue with original message on error
            return await next_call(context)


class FileAttachmentMiddleware(BaseMiddleware):
    """
    Intercepts messages with file attachments and injects the file content
    into the message so the AI can see and process the files.

    The middleware:
    1. Checks if there's a file_id stored in the bot instance
    2. Looks up the file metadata in the knowledge graph
    3. Reads the file content from disk
    4. Appends the file content to the message with appropriate formatting

    Example:
        User uploads image.png and sends: "What's in this image?"
        -> Middleware reads file metadata from knowledge graph
        -> Reads file from uploads/uuid.png
        -> Appends: "---\n[File: image.png (12.5 KB)]\n[Binary file: image/png]"
    """

    middleware_type = MiddlewareType.MESSAGE

    # File size limits for reading content (10MB)
    MAX_TEXT_FILE_SIZE = 10 * 1024 * 1024

    # Text file extensions we'll try to read
    TEXT_EXTENSIONS = {
        "txt",
        "md",
        "json",
        "xml",
        "html",
        "css",
        "js",
        "ts",
        "py",
        "java",
        "c",
        "cpp",
        "h",
        "hpp",
        "go",
        "rs",
        "rb",
        "php",
        "yaml",
        "yml",
        "toml",
        "ini",
        "cfg",
        "conf",
        "sh",
        "bash",
        "sql",
        "csv",
        "log",
    }

    async def __call__(
        self, context: MessageContext, next_call: NextMessageMiddleware
    ) -> MessageContext:
        """Process messages with file attachments."""
        try:
            bot = context.bot_instance
            if not bot:
                return await next_call(context)

            # Check if there's a file_id stored from send_message
            file_id = getattr(bot, "_current_file_id", None)
            if not file_id:
                return await next_call(context)

            # Check if file content was already injected (from history replay)
            # If the message already contains "[File Attachment:", skip injection
            message_text = context.modified_message or context.message
            if "[File Attachment:" in message_text:
                logger.info("File content already in message, skipping injection")
                return await next_call(context)

            # Get knowledge repository
            if not bot.knowledge or not bot.knowledge.repository:
                logger.warning("No knowledge repository available for file attachment")
                return await next_call(context)

            repository = bot.knowledge.repository

            try:
                # Look up file node in knowledge graph
                file_node = await repository.get_node(file_id)
                if not file_node:
                    logger.warning(f"File node not found: {file_id}")
                    return await next_call(context)

                # Extract file metadata
                props = file_node.properties or {}
                file_name = props.get("file_name", "unknown")
                file_size = props.get("file_size", 0)
                file_type = props.get("file_type", "unknown")
                storage_path = props.get("storage_path")
                ai_description = props.get("ai_description")

                if not storage_path or not os.path.exists(storage_path):
                    logger.error(f"File not found on disk: {storage_path}")
                    context.modified_message = (
                        context.modified_message or context.message
                    ) + f"\n\n---\n[Error: File '{file_name}' not found on disk]"
                    return await next_call(context)

                # Format file size for display
                size_display = self._format_file_size(file_size)

                # Determine if we should try to read the file content
                file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
                is_text_file = file_ext in self.TEXT_EXTENSIONS

                message = context.modified_message or context.message
                file_content_section = (
                    f"\n\n---\n[File Attachment: {file_name} ({size_display})]\n"
                )

                # Add AI description if available
                if ai_description:
                    file_content_section += f"[AI Analysis: {ai_description}]\n\n"

                if is_text_file and file_size <= self.MAX_TEXT_FILE_SIZE:
                    # Try to read text file content
                    try:
                        with open(storage_path, "r", encoding="utf-8") as f:
                            file_content = f.read()

                        # Determine formatting based on extension
                        if file_ext in {"json", "xml", "html", "css", "yaml", "yml"}:
                            file_content_section += (
                                f"```{file_ext}\n{file_content}\n```"
                            )
                        elif file_ext in {
                            "py",
                            "js",
                            "ts",
                            "java",
                            "c",
                            "cpp",
                            "go",
                            "rs",
                            "rb",
                        }:
                            file_content_section += (
                                f"```{file_ext}\n{file_content}\n```"
                            )
                        else:
                            file_content_section += f"```\n{file_content}\n```"

                        logger.info(
                            f"Appended text file content for {file_name} ({len(file_content)} chars)"
                        )
                    except UnicodeDecodeError:
                        # File looks like text but isn't UTF-8
                        file_content_section += (
                            f"[Binary file detected, type: {file_type}]\n"
                        )
                        file_content_section += f"[File path: {storage_path}]"
                        logger.info(
                            f"File {file_name} is binary despite text extension"
                        )
                    except Exception as e:
                        logger.error(f"Error reading file {file_name}: {e}")
                        file_content_section += f"[Error reading file: {str(e)}]"
                else:
                    # Binary file or too large
                    file_content_section += f"[Binary/media file, type: {file_type}]\n"
                    file_content_section += (
                        f"[File path available at: {storage_path}]\n"
                    )

                    # Add note about what the AI can do
                    if file_type and file_type.startswith("image/"):
                        file_content_section += "[Note: This is an image file. I cannot directly view images, but you can describe it to me or use an image analysis tool.]"
                    elif file_type and file_type.startswith("audio/"):
                        file_content_section += "[Note: This is an audio file. I cannot directly process audio.]"
                    elif file_type and file_type.startswith("video/"):
                        file_content_section += "[Note: This is a video file. I cannot directly process video.]"
                    else:
                        file_content_section += f"[Note: This is a {file_type} file which I cannot directly read.]"

                    logger.info(f"File {file_name} is binary/media type: {file_type}")

                # Append file information to message
                context.modified_message = message + file_content_section
                logger.info(f"Successfully processed file attachment: {file_name}")

            except Exception as e:
                logger.error(f"Error processing file attachment {file_id}: {e}")
                # Continue with original message if file processing fails
                context.modified_message = (
                    context.modified_message or context.message
                ) + f"\n\n---\n[Error processing file attachment: {str(e)}]"

            return await next_call(context)

        except Exception as e:
            logger.error(f"Error in FileAttachmentMiddleware: {e}")
            # Continue with original message on error
            return await next_call(context)

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
