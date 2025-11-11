"""File service for handling file uploads and attachments.

Handles file storage, metadata management, and linking files to users,
sessions, and messages in the knowledge graph.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from database.models import Node
from database.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class FileService:
    """Service for managing file uploads and attachments.

    Provides methods for uploading files, creating file nodes in the knowledge graph,
    linking files to users/sessions/messages, and retrieving file information.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        upload_directory: str = "uploads",
    ):
        """Initialize the file service.

        Args:
            repository: Knowledge graph repository instance
            upload_directory: Directory path for storing uploaded files
        """
        self.repository = repository
        self.upload_directory = upload_directory
        self._ensure_upload_directory()

    def _ensure_upload_directory(self):
        """Ensure the upload directory exists."""
        if not os.path.exists(self.upload_directory):
            try:
                os.makedirs(self.upload_directory, mode=0o755)
                logger.info(f"Created upload directory: {self.upload_directory}")
            except Exception as e:
                logger.error(f"Failed to create upload directory: {e}", exc_info=True)

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        file_size: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ai_description_callback: Optional[Callable[[bytes, str], str]] = None,
    ) -> Optional[str]:
        """Upload a file and create corresponding knowledge graph node.

        Args:
            file_content: Binary file content
            filename: Original filename
            mime_type: MIME type of the file
            file_size: Size of the file in bytes
            user_id: Optional user ID who uploaded the file
            session_id: Optional session ID
            ai_description_callback: Optional async function to generate AI description

        Returns:
            File node ID if successful, None otherwise
        """
        try:
            # Generate unique filename to prevent collisions
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_filename = Path(filename).name  # Remove any path components
            unique_filename = f"{timestamp}_{safe_filename}"
            file_path = os.path.join(self.upload_directory, unique_filename)

            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(file_content)

            logger.info(f"Saved file to: {file_path}")

            # Create file node
            file_node_id = f"file:{unique_filename}"
            file_properties = {
                "filename": safe_filename,
                "unique_filename": unique_filename,
                "mime_type": mime_type,
                "file_size": file_size,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "file_path": file_path,
            }

            # Generate AI description if callback provided
            ai_description = None
            if ai_description_callback:
                try:
                    ai_description = await ai_description_callback(
                        file_content, mime_type
                    )
                    if ai_description:
                        file_properties["ai_description"] = ai_description
                        logger.info(f"Generated AI description for {safe_filename}")
                except Exception as e:
                    logger.warning(
                        f"Failed to generate AI description: {e}", exc_info=True
                    )

            # Create content string
            content = f"File uploaded to {file_path}"
            if ai_description:
                content += f". AI Analysis: {ai_description}"

            # Create file node in knowledge graph
            self.repository.add_node(
                node_id=file_node_id,
                node_type="File",
                label=safe_filename,
                content=content,
                properties=file_properties,
            )

            logger.info(f"Created file node: {file_node_id}")

            # Link to user if provided
            if user_id:
                self.link_file_to_user(file_node_id, user_id)

            # Link to session if provided
            if session_id:
                self.link_file_to_session(file_node_id, session_id)

            return file_node_id

        except Exception as e:
            logger.error(f"Failed to upload file {filename}: {e}", exc_info=True)
            return None

    def get_file(self, file_id: str) -> Optional[Node]:
        """Retrieve a file node from the knowledge graph.

        Args:
            file_id: File node identifier (e.g., "file:20241109_120000_example.pdf")

        Returns:
            File Node object, or None if not found
        """
        try:
            file_node = self.repository.get_node(file_id)
            if file_node:
                logger.debug(f"Retrieved file: {file_id}")
            else:
                logger.debug(f"File not found: {file_id}")
            return file_node

        except Exception as e:
            logger.error(f"Failed to retrieve file {file_id}: {e}", exc_info=True)
            return None

    def get_file_path(self, file_id: str) -> Optional[str]:
        """Get the filesystem path for a file.

        Args:
            file_id: File node identifier

        Returns:
            Filesystem path to the file, or None if not found
        """
        file_node = self.get_file(file_id)
        if not file_node:
            return None

        properties = file_node.properties or {}
        return properties.get("file_path")

    def link_file_to_user(self, file_id: str, user_id: str) -> bool:
        """Link a file to a user with an UPLOADED edge.

        Args:
            file_id: File node identifier
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        user_node_id = f"user:{user_id}" if not user_id.startswith("user:") else user_id

        try:
            self.repository.add_edge(
                source_id=user_node_id, target_id=file_id, edge_type="UPLOADED"
            )
            logger.info(f"Linked file {file_id} to user {user_node_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to link file {file_id} to user {user_id}: {e}", exc_info=True
            )
            return False

    def link_file_to_session(self, file_id: str, session_id: str) -> bool:
        """Link a file to a session with a CONTAINS edge.

        Args:
            file_id: File node identifier
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            self.repository.add_edge(
                source_id=session_id, target_id=file_id, edge_type="CONTAINS"
            )
            logger.info(f"Linked file {file_id} to session {session_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to link file {file_id} to session {session_id}: {e}",
                exc_info=True,
            )
            return False

    def link_file_to_message(self, file_id: str, message_node_id: str) -> bool:
        """Link a file to a message with a HAS_ATTACHMENT edge.

        Args:
            file_id: File node identifier
            message_node_id: Message node identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            self.repository.add_edge(
                source_id=message_node_id, target_id=file_id, edge_type="HAS_ATTACHMENT"
            )
            logger.info(f"Linked file {file_id} to message {message_node_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to link file {file_id} to message {message_node_id}: {e}",
                exc_info=True,
            )
            return False

    def get_message_attachments(self, message_node_id: str) -> List[Dict[str, Any]]:
        """Get all file attachments for a message.

        Args:
            message_node_id: Message node identifier

        Returns:
            List of attachment dictionaries with file_id and filename
        """
        try:
            # Get edges from message to files
            attachment_edges = self.repository.get_edges(
                source_id=message_node_id, edge_type="HAS_ATTACHMENT"
            )

            attachments = []
            for edge in attachment_edges:
                file_node = self.repository.get_node(edge.target_id)
                if file_node:
                    file_props = file_node.properties or {}
                    attachments.append(
                        {
                            "file_id": file_node.id,
                            "filename": file_props.get("filename", "Unknown"),
                            "mime_type": file_props.get("mime_type"),
                            "file_size": file_props.get("file_size"),
                        }
                    )

            logger.debug(
                f"Retrieved {len(attachments)} attachments for message {message_node_id}"
            )
            return attachments

        except Exception as e:
            logger.error(
                f"Failed to get attachments for message {message_node_id}: {e}",
                exc_info=True,
            )
            return []

    def get_user_files(self, user_id: str, limit: Optional[int] = None) -> List[Node]:
        """Get all files uploaded by a user.

        Args:
            user_id: User identifier
            limit: Optional limit on number of files to return

        Returns:
            List of file nodes
        """
        user_node_id = f"user:{user_id}" if not user_id.startswith("user:") else user_id

        try:
            # Get outgoing UPLOADED edges from user
            edges = self.repository.get_edges(
                source_id=user_node_id, edge_type="UPLOADED"
            )

            files = []
            for edge in edges:
                file_node = self.repository.get_node(edge.target_id)
                if file_node:
                    files.append(file_node)

                if limit and len(files) >= limit:
                    break

            logger.debug(f"Found {len(files)} files for user {user_id}")
            return files

        except Exception as e:
            logger.error(
                f"Failed to get files for user {user_id}: {e}", exc_info=True
            )
            return []

    def get_session_files(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Node]:
        """Get all files in a session.

        Args:
            session_id: Session identifier
            limit: Optional limit on number of files to return

        Returns:
            List of file nodes
        """
        try:
            # Get outgoing CONTAINS edges from session to files
            edges = self.repository.get_edges(source_id=session_id, edge_type="CONTAINS")

            files = []
            for edge in edges:
                # Only get File type nodes
                node = self.repository.get_node(edge.target_id)
                if node and node.node_type == "File":
                    files.append(node)

                if limit and len(files) >= limit:
                    break

            logger.debug(f"Found {len(files)} files for session {session_id}")
            return files

        except Exception as e:
            logger.error(
                f"Failed to get files for session {session_id}: {e}", exc_info=True
            )
            return []

    def delete_file(self, file_id: str, delete_from_disk: bool = True) -> bool:
        """Delete a file from the knowledge graph and optionally from disk.

        Args:
            file_id: File node identifier
            delete_from_disk: If True, also deletes the physical file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get file path before deleting node
            file_path = None
            if delete_from_disk:
                file_path = self.get_file_path(file_id)

            # Delete node from knowledge graph (cascade will delete edges)
            self.repository.delete_node(file_id)
            logger.info(f"Deleted file node: {file_id}")

            # Delete physical file if requested and path exists
            if delete_from_disk and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted physical file: {file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to delete physical file {file_path}: {e}",
                        exc_info=True,
                    )

            return True

        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}", exc_info=True)
            return False

    def update_file_metadata(self, file_id: str, **properties: Any) -> bool:
        """Update file metadata properties.

        Args:
            file_id: File node identifier
            **properties: Properties to update

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing file
            file_node = self.repository.get_node(file_id)
            if not file_node:
                logger.warning(f"File {file_id} not found, cannot update")
                return False

            # Update properties
            existing_properties = file_node.properties or {}
            existing_properties.update(properties)

            # Update node
            self.repository.update_node(node_id=file_id, properties=existing_properties)

            logger.info(f"Updated file {file_id} metadata: {properties}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to update file {file_id} metadata: {e}", exc_info=True
            )
            return False

