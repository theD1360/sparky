/**
 * API Service
 * Handles all HTTP API calls to the backend
 */

/**
 * Get auth headers from localStorage token
 * @returns {Object} Headers object with Authorization if token exists
 */
const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  if (token) {
    return {
      'Authorization': `Bearer ${token}`,
    };
  }
  return {};
};

/**
 * Fetch available resources from the server
 * @returns {Promise<Array>} List of resources
 */
export const fetchResources = async () => {
  try {
    const response = await fetch('/api/resources', {
      headers: getAuthHeaders(),
    });
    return await response.json();
  } catch (error) {
    console.error('Error fetching resources:', error);
    throw error;
  }
};

/**
 * Fetch available prompts from the server
 * @returns {Promise<Array>} List of prompts
 */
export const fetchPrompts = async () => {
  try {
    const response = await fetch('/api/prompts', {
      headers: getAuthHeaders(),
    });
    return await response.json();
  } catch (error) {
    console.error('Error fetching prompts:', error);
    throw error;
  }
};

/**
 * Fetch user chats
 * @param {string} userId - User identifier
 * @param {boolean} includeArchived - Whether to include archived chats
 * @returns {Promise<Object>} User chats data
 */
export const fetchUserChats = async (userId, includeArchived = false) => {
  try {
    const response = await fetch(`/api/user/${userId}/chats?include_archived=${includeArchived}`, {
      headers: getAuthHeaders(),
    });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching user chats:', error);
    throw error;
  }
};

/**
 * Load chat history/messages for a specific chat
 * @param {string} chatId - Chat identifier
 * @param {AbortSignal} signal - Optional abort signal for timeout
 * @returns {Promise<Object>} Chat messages data
 */
export const loadChatHistory = async (chatId, signal = null) => {
  try {
    const options = {
      headers: getAuthHeaders(),
      ...(signal ? { signal } : {}),
    };
    const response = await fetch(`/api/chats/${chatId}/messages`, options);
    
    if (response.ok) {
      return await response.json();
    } else {
      console.log('No history found for chat');
      return null;
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      console.error('Loading chat history timed out after 10 seconds');
    } else {
      console.error('Error loading chat history:', error);
    }
    throw error;
  }
};

/**
 * Update chat name
 * @param {string} userId - User identifier
 * @param {string} chatId - Chat identifier
 * @param {string} newName - New chat name
 * @returns {Promise<void>}
 */
export const updateChatName = async (userId, chatId, newName) => {
  try {
    await fetch(`/api/user/${userId}/chats/${chatId}`, {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ chat_name: newName })
    });
  } catch (error) {
    console.error('Error renaming chat:', error);
    throw error;
  }
};

/**
 * Delete a chat
 * @param {string} userId - User identifier
 * @param {string} chatId - Chat identifier
 * @returns {Promise<boolean>} Success status
 */
export const deleteChat = async (userId, chatId) => {
  try {
    const response = await fetch(`/api/user/${userId}/chats/${chatId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return response.ok;
  } catch (error) {
    console.error('Error deleting chat:', error);
    throw error;
  }
};

/**
 * Archive a chat
 * @param {string} userId - User identifier
 * @param {string} chatId - Chat identifier
 * @returns {Promise<boolean>} Success status
 */
export const archiveChat = async (userId, chatId) => {
  try {
    const response = await fetch(`/api/user/${userId}/chats/${chatId}/archive`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return response.ok;
  } catch (error) {
    console.error('Error archiving chat:', error);
    throw error;
  }
};

/**
 * Unarchive a chat
 * @param {string} userId - User identifier
 * @param {string} chatId - Chat identifier
 * @returns {Promise<boolean>} Success status
 */
export const unarchiveChat = async (userId, chatId) => {
  try {
    const response = await fetch(`/api/user/${userId}/chats/${chatId}/unarchive`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return response.ok;
  } catch (error) {
    console.error('Error unarchiving chat:', error);
    throw error;
  }
};

/**
 * Upload a file
 * @param {File} file - File to upload
 * @param {string} sessionId - Session identifier
 * @param {string} chatId - Chat identifier
 * @param {string} userId - User identifier
 * @returns {Promise<Object>} Upload result with file_id
 */
export const uploadFile = async (file, sessionId, chatId, userId) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const uploadUrl = `/upload_file?session_id=${sessionId}&chat_id=${chatId}&user_id=${userId}`;
    console.log('Upload URL:', uploadUrl);
    
    const response = await fetch(uploadUrl, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || error.detail || 'Upload failed');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error uploading file:', error);
    throw error;
  }
};

/**
 * Record tool usage (analytics/tracking)
 * @param {string} sessionId - Session identifier
 * @param {string} toolName - Tool name
 * @param {Object} toolArgs - Tool arguments
 * @param {any} result - Tool result
 * @returns {Promise<void>}
 */
export const recordToolUsage = async (sessionId, toolName, toolArgs, result) => {
  try {
    await fetch('/record_tool_usage', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        session_id: sessionId,
        tool_name: toolName,
        tool_args: toolArgs,
        result: result,
      })
    });
  } catch (error) {
    console.error('Error recording tool usage:', error);
    // Don't throw - this is non-critical
  }
};

