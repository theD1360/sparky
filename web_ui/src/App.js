import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import ReconnectingWebSocket from 'reconnecting-websocket';
import {
  Box,
  TextField,
  IconButton,
  Drawer,
  Typography,
  Stack,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Avatar,
  Toolbar,
  AppBar,
  InputAdornment,
  Chip,
  CircularProgress,
  useMediaQuery,
  useTheme,
  Menu,
  MenuItem,
  Collapse,
} from '@mui/material';
import {
  Help as HelpIcon,
  Close as CloseIcon,
  Home as HomeIcon,
  Chat as ChatIcon,
  Settings as SettingsIcon,
  Person as PersonIcon,
  Code as CodeIcon,
  Send as SendIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  AttachFile as AttachFileIcon,
  Cancel as CancelIcon,
  Error as ErrorIcon,
  InsertDriveFile as FileIcon,
  Menu as MenuIcon,
  MoreVert as MoreVertIcon,
  Archive as ArchiveIcon,
  Unarchive as UnarchiveIcon,
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';
import ChatMessage from './ChatMessage';
import ToolActivityItem from './ToolActivityItem';
import AutocompleteDropdown from './AutocompleteDropdown';
import HelpModal from './HelpModal';
import SplashScreen from './SplashScreen';

const SIDEBAR_WIDTH = 280;

function App() {
  // Router hooks
  const navigate = useNavigate();
  const { chatId: urlChatId } = useParams();
  
  // Responsive design
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md')); // md = 900px
  const isSmallMobile = useMediaQuery(theme.breakpoints.down('sm')); // sm = 600px
  const [mobileLeftDrawerOpen, setMobileLeftDrawerOpen] = useState(false);
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true); // Desktop sidebar state

  // Chat and activity state
  const [chatMessages, setChatMessages] = useState([]);
  const [toolActivity, setToolActivity] = useState([]);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [pendingMessage, setPendingMessage] = useState(null);
  
  // Tool loading state
  const [toolsLoading, setToolsLoading] = useState([]);
  const [toolsReady, setToolsReady] = useState(false);
  const [totalTools, setTotalTools] = useState(0);
  
  // Chat readiness state - prevents message loss
  const [chatReady, setChatReady] = useState(false);
  const [messageQueue, setMessageQueue] = useState([]);
  
  // Input state
  const [inputValue, setInputValue] = useState('');
  const [cursorPosition, setCursorPosition] = useState(0);
  
  // Data from server
  const [resources, setResources] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [toolUses, setToolUses] = useState([]);
  const [toolResults, setToolResults] = useState([]);
  const [sessionId, setSessionId] = useState(() => {
    // Try to restore session from localStorage
    const savedSession = localStorage.getItem('session_id');
    if (savedSession) {
      console.log('Restoring session from localStorage:', savedSession);
      return savedSession;
    }
    return null;
  });
  const [userChats, setUserChats] = useState([]);
  const [archivedChats, setArchivedChats] = useState([]);
  const [showArchivedChats, setShowArchivedChats] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [renamingChatId, setRenamingChatId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [actionMenuAnchor, setActionMenuAnchor] = useState(null);
  const [actionMenuChatId, setActionMenuChatId] = useState(null);

  // UI state
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  
  // Token usage state
  const [tokenUsage, setTokenUsage] = useState({ input_tokens: 0, output_tokens: 0, total_tokens: 0 });
  const [estimatedTokens, setEstimatedTokens] = useState(0); // Cumulative estimated tokens
  const [maxTokens] = useState(1000000); // 1M token context window

  const uploadFile = async (file) => {
    console.log('Uploading file immediately:', file.name, 'type:', file.type, 'size:', file.size);
    
    // Add file to list with uploading status
    const fileId = `temp-${Date.now()}-${Math.random()}`;
    const fileEntry = { id: fileId, name: file.name, size: file.size, uploading: true, error: null, file_id: null };
    setAttachedFiles(prev => [...prev, fileEntry]);

    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const userId = getUserId();
      const uploadUrl = `/upload_file?session_id=${sessionId}&chat_id=${currentChatId}&user_id=${userId}`;
      console.log('Upload URL:', uploadUrl);
      
      const uploadResponse = await fetch(uploadUrl, {
        method: 'POST',
        body: formData
      });
      
      console.log('Upload response status:', uploadResponse.status);
      
      if (!uploadResponse.ok) {
        const error = await uploadResponse.json();
        console.error('File upload failed:', error);
        // Update file entry with error
        setAttachedFiles(prev => prev.map(f => 
          f.id === fileId ? { ...f, uploading: false, error: error.error || error.detail || 'Upload failed' } : f
        ));
        return;
      }
      
      const uploadResult = await uploadResponse.json();
      console.log('File uploaded successfully:', uploadResult);
      
      // Update file entry with success
      setAttachedFiles(prev => prev.map(f => 
        f.id === fileId ? { 
          ...f, 
          uploading: false, 
          file_id: uploadResult.file_id,
          description: uploadResult.description
        } : f
      ));
    } catch (error) {
      console.error('Error uploading file:', error);
      setAttachedFiles(prev => prev.map(f => 
        f.id === fileId ? { ...f, uploading: false, error: error.message } : f
      ));
    }
  };

  const handleFileChange = (event) => {
    const files = Array.from(event.target.files);
    files.forEach(file => {
      console.log('File selected via button:', file.name, 'type:', file.type, 'size:', file.size);
      uploadFile(file);
    });
    // Clear input so same file can be selected again
    event.target.value = '';
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    const files = Array.from(event.dataTransfer.files);
    files.forEach(file => {
      console.log('File dropped:', file.name, 'type:', file.type, 'size:', file.size);
      uploadFile(file);
    });
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const removeAttachment = (fileId) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const fetchUserChats = useCallback(async (userId) => {
    try {
      const response = await fetch(`/api/user/${userId}/chats?include_archived=false`);
      const data = await response.json();
      // Filter out any archived chats on client side as extra safety
      const activeChats = (data.chats || []).filter(chat => !chat.archived);
      setUserChats(activeChats);
      console.log('Fetched active chats:', activeChats.length);
    } catch (error) {
      console.error("Error fetching user chats:", error);
    }
  }, []);

  const fetchArchivedChats = useCallback(async (userId) => {
    try {
      const response = await fetch(`/api/user/${userId}/chats?include_archived=true`);
      const data = await response.json();
      // Filter to only get archived chats
      const archived = (data.chats || []).filter(chat => chat.archived);
      setArchivedChats(archived);
      console.log('Fetched archived chats:', archived.length);
    } catch (error) {
      console.error("Error fetching archived chats:", error);
    }
  }, []);

  const handleNewChat = async () => {
    console.log('Creating new chat - generating chat_id');
    
    // Generate a new chat_id on the client side
    const newChatId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
    
    console.log('Generated new chat_id:', newChatId);
    
    // Clear current chat state
    setChatMessages([]);
    setToolActivity([]);
    setChatReady(false); // Mark chat as NOT ready until server confirms
    setMessageQueue([]); // Clear message queue for new chat
    setEstimatedTokens(0); // Reset estimated tokens for new chat
    
    // Set the new chat ID immediately (optimistic)
    setCurrentChatId(newChatId);
    
    // Navigate to the new chat URL immediately (optimistic)
    navigate(`/chat/${newChatId}`);
    
    // Close mobile drawer after creating new chat
    if (isMobile) {
      setMobileLeftDrawerOpen(false);
    }
    
    // Send start_chat message to server
    if (socket.current && socket.current.readyState === WebSocket.OPEN && toolsReady) {
      const startChatMessage = {
        type: 'start_chat',
        data: {
          chat_id: newChatId,
          chat_name: `Chat ${newChatId.substring(0, 8)}`
        },
      };
      console.log('Sending start_chat message:', startChatMessage);
      socket.current.send(JSON.stringify(startChatMessage));
    }
  };

  const loadChatHistory = async (chatId) => {
    try {
      setIsLoadingChat(true);
      
      // Add timeout to prevent infinite hang
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      const response = await fetch(`/api/chats/${chatId}/messages`, {
        signal: controller.signal
      });
      clearTimeout(timeout);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Loaded chat history:', data);
        
        // Transform backend messages to UI format and populate tool activity
        const loadedMessages = [];
        const loadedToolActivity = [];
        
        data.messages.forEach(msg => {
          const message_type = msg.message_type || 'message';
          
          // Handle different message types
          if (message_type === 'tool_use') {
            // Format tool use text consistently
            const toolUseText = msg.tool_name && msg.tool_args 
              ? `${msg.tool_name}(${JSON.stringify(msg.tool_args)})`
              : msg.text;
            // Add to chat messages with special role
            loadedMessages.push({
              role: 'tool_use',
              text: toolUseText,
              toolData: { name: msg.tool_name, args: msg.tool_args }
            });
            // Add to tool activity
            loadedToolActivity.push({ kind: 'tool_use', text: toolUseText });
          } else if (message_type === 'tool_result') {
            // Add to chat messages with special role
            loadedMessages.push({
              role: 'tool_result',
              text: msg.text,
              toolData: { result: msg.text }
            });
            // Add to tool activity
            loadedToolActivity.push({ kind: 'tool_result', text: msg.text });
          } else if (message_type === 'thought') {
            // Thoughts get special role for styling
            loadedMessages.push({
              role: 'thought',
              text: msg.text
            });
            // Also add to tool activity
            loadedToolActivity.push({ kind: 'thought', text: msg.text });
          } else {
            // Regular messages (user or model)
            loadedMessages.push({
              role: msg.role,
              text: msg.text,
              attachments: msg.attachments || null
            });
          }
        });
        
        setChatMessages(loadedMessages);
        setToolActivity(loadedToolActivity);
        console.log(`Loaded ${loadedMessages.length} messages and ${loadedToolActivity.length} tool activity items`);
      } else {
        console.log('No history found for chat, starting fresh');
        setChatMessages([]);
        setToolActivity([]);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Loading chat history timed out after 10 seconds');
        setChatMessages(prev => [...prev, { 
          role: 'error', 
          text: 'Failed to load chat history (timeout). Please try again.' 
        }]);
      } else {
        console.error('Error loading chat history:', error);
      }
      setChatMessages([]);
      setToolActivity([]);
    } finally {
      setIsLoadingChat(false);
    }
  };

  const handleSwitchChat = async (chatId) => {
    // Don't switch if already on this chat
    if (currentChatId === chatId) {
      console.log('Already on this chat');
      return;
    }
    
    console.log('Switching to chat:', chatId);
    setCurrentChatId(chatId);
    setToolActivity([]);
    setChatReady(false); // Mark chat as NOT ready until server confirms
    setMessageQueue([]); // Clear message queue when switching chats
    setEstimatedTokens(0); // Reset estimated tokens (will be set by history estimate)
    
    // Navigate to the chat URL
    navigate(`/chat/${chatId}`);
    
    // Load chat history for existing chat
    await loadChatHistory(chatId);
    
    // Close mobile drawer after switching chat
    if (isMobile) {
      setMobileLeftDrawerOpen(false);
    }
    
    // Send switch_chat message to server
    if (socket.current && socket.current.readyState === WebSocket.OPEN && toolsReady) {
      const switchChatMessage = {
        type: 'switch_chat',
        data: {
          chat_id: chatId
        },
      };
      console.log('Sending switch_chat message:', switchChatMessage);
      socket.current.send(JSON.stringify(switchChatMessage));
    }
  };

  const handleRenameChat = async (chatId, newName) => {
    const userId = getUserId();
    try {
      await fetch(`/api/user/${userId}/chats/${chatId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_name: newName })
      });
      
      // Update local state
      setUserChats(prevChats => 
        prevChats.map(chat => 
          chat.chat_id === chatId ? { ...chat, chat_name: newName } : chat
        )
      );
      
      setRenamingChatId(null);
      setRenameValue('');
    } catch (error) {
      console.error('Error renaming chat:', error);
    }
  };

  const handleDeleteChat = async (chatId) => {
    const userId = getUserId();
    
    if (!window.confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
      return;
    }
    
    try {
      const response = await fetch(`/api/user/${userId}/chats/${chatId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        // Refresh both lists from server
        await fetchUserChats(userId);
        if (showArchivedChats) {
          await fetchArchivedChats(userId);
        }
        
        // If we deleted the current chat, start a new one
        if (currentChatId === chatId) {
          handleNewChat();
        }
        
        console.log('Chat deleted successfully');
      } else {
        console.error('Failed to delete chat');
      }
    } catch (error) {
      console.error('Error deleting chat:', error);
    }
  };

  const handleArchiveChat = async (chatId) => {
    const userId = getUserId();
    
    try {
      const response = await fetch(`/api/user/${userId}/chats/${chatId}/archive`, {
        method: 'POST'
      });
      
      if (response.ok) {
        // Refresh both lists from server to ensure consistency
        await fetchUserChats(userId);
        if (showArchivedChats) {
          await fetchArchivedChats(userId);
        }
        
        // If we archived the current chat, start a new one
        if (currentChatId === chatId) {
          handleNewChat();
        }
        
        console.log('Chat archived successfully');
      } else {
        console.error('Failed to archive chat');
      }
    } catch (error) {
      console.error('Error archiving chat:', error);
    }
  };

  const handleUnarchiveChat = async (chatId) => {
    const userId = getUserId();
    
    try {
      const response = await fetch(`/api/user/${userId}/chats/${chatId}/unarchive`, {
        method: 'POST'
      });
      
      if (response.ok) {
        // Refresh both lists from server to ensure consistency
        await fetchUserChats(userId);
        await fetchArchivedChats(userId);
        
        console.log('Chat unarchived successfully');
      } else {
        console.error('Failed to unarchive chat');
      }
    } catch (error) {
      console.error('Error unarchiving chat:', error);
    }
  };

  const [showToolActivity, setShowToolActivity] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [autocompleteType, setAutocompleteType] = useState(null);
  const [autocompleteItems, setAutocompleteItems] = useState([]);
  const [autocompleteSelectedIndex, setAutocompleteSelectedIndex] = useState(0);
  const [autocompletePosition, setAutocompletePosition] = useState(null);
  
  // Refs
  const socket = useRef(null);
  const [connectionStatus, setConnectionStatus] = useState('Connecting...');
  const [reconnectionAttempts, setReconnectionAttempts] = useState(0);
  const [reconnectionError, setReconnectionError] = useState(null);
  const chatScrollRef = useRef(null);
  const inputRef = useRef(null);
  const autocompleteDebounceRef = useRef(null);

  // Scroll chat to bottom - optimized with debouncing to avoid blocking UI
  const scrollToBottom = useCallback(() => {
    if (chatScrollRef.current) {
      const scrollElement = chatScrollRef.current;
      // Use requestAnimationFrame for smoother scrolling without blocking the UI
      requestAnimationFrame(() => {
        scrollElement.scrollTop = scrollElement.scrollHeight;
      });
    }
  }, []);

  useEffect(() => {
    // Debounce scrolling to avoid excessive operations during rapid message updates
    const scrollTimer = setTimeout(() => {
      scrollToBottom();
    }, 50); // 50ms debounce
    
    return () => clearTimeout(scrollTimer);
  }, [chatMessages.length, scrollToBottom]); // Only re-run when message count changes

  // Get or generate user ID stored in localStorage
  const getUserId = () => {
    let userId = localStorage.getItem('user_id');
    if (!userId) {
      // Generate a UUID v4
      userId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
      localStorage.setItem('user_id', userId);
      console.log('Generated new user ID:', userId);
    } else {
      console.log('Retrieved existing user ID:', userId);
    }
    return userId;
  };

  // WebSocket setup - connect on mount
  useEffect(() => {
    const fetchResourcesAndPrompts = async () => {
      try {
        const resourcesResponse = await fetch('/api/resources');
        const resourcesData = await resourcesResponse.json();
        setResources(resourcesData);

        const promptsResponse = await fetch('/api/prompts');
        const promptsData = await promptsResponse.json();
        setPrompts(promptsData);
      } catch (error) {
        console.error('Error fetching resources/prompts:', error);
      }
    };

    fetchResourcesAndPrompts();

    // Connect immediately on mount (not waiting for chat selection)
    // Use WebSocket URL from environment variables or fall back to current page host
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = process.env.REACT_APP_WS_HOST || window.location.hostname;
    const wsPort = process.env.REACT_APP_WS_PORT || window.location.port || '8000';
    const wsUrl = `${wsProtocol}//${wsHost}:${wsPort}/ws/chat`;
    
    console.log('Connecting to WebSocket on mount:', wsUrl);
    socket.current = new ReconnectingWebSocket(wsUrl, null, {reconnectInterval: 3000});

    socket.current.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('Connected');
      setReconnectionAttempts(0);
      setReconnectionError(null);

      const userId = getUserId();
      // Send connect with user_id and session_id (if resuming a session)
      const connectMessage = {
        type: 'connect',
        data: {
          session_id: sessionId, // Will be null for new sessions, or existing ID for reconnects
          user_id: userId,
        },
      };
      console.log('Sending connect message with user_id:', userId, 'session_id:', sessionId);
      socket.current.send(JSON.stringify(connectMessage));
      
      // If we have a current chat ID when reconnecting, we need to re-establish it
      // This handles the case when the socket disconnects (e.g., screen sleep on mobile)
      if (currentChatId) {
        console.log('Reconnected with active chat, will re-establish chat:', currentChatId);
        // Set a flag to switch chat after tools are ready
        // We can't send switch_chat immediately because the server needs to process connect first
        const recheckInterval = setInterval(() => {
          if (toolsReady && socket.current.readyState === WebSocket.OPEN) {
            clearInterval(recheckInterval);
            console.log('Tools ready after reconnect, re-establishing chat:', currentChatId);
            setChatReady(false); // Mark as not ready until server confirms
            const switchChatMessage = {
              type: 'switch_chat',
              data: {
                chat_id: currentChatId
              },
            };
            socket.current.send(JSON.stringify(switchChatMessage));
          }
        }, 100); // Check every 100ms
        
        // Clear interval after 10 seconds to avoid memory leak
        setTimeout(() => clearInterval(recheckInterval), 10000);
      }
    };

    socket.current.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('Disconnected');
    };

    socket.current.onconnecting = () => {
      console.log('WebSocket connecting');
      setConnectionStatus('Connecting...');
    };

    socket.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("Received message:", data);
      
      // Validate message metadata for chat-specific messages
      const messageChatId = data.chat_id;
      const isGlobalMessage = ['session_info', 'ready', 'chat_ready', 'tool_loading_progress'].includes(data.type);
      
      // If message has chat_id and we have a current chat, validate they match
      if (messageChatId && currentChatId && messageChatId !== currentChatId && !isGlobalMessage) {
        console.warn(`Ignoring message for chat ${messageChatId}, current chat is ${currentChatId}`);
        return;
      }
      
      switch (data.type) {
        case 'session_info':
          const newSessionId = data.data.session_id;
          setSessionId(newSessionId);
          // Persist session to localStorage for reconnection
          localStorage.setItem('session_id', newSessionId);
          console.log('Session established:', newSessionId);
          break;
        
        case 'tool_loading_progress':
          // Update tool loading progress
          console.log('Tool loading progress:', data.data);
          setToolsLoading(prev => {
            const existing = prev.find(t => t.tool_name === data.data.tool_name);
            if (existing) {
              return prev.map(t => 
                t.tool_name === data.data.tool_name 
                  ? { ...t, status: data.data.status, message: data.data.message }
                  : t
              );
            } else {
              return [...prev, data.data];
            }
          });
          break;
        
        case 'ready':
          // Tools are ready, hide splash screen
          console.log('Tools ready, session ready for chats');
          setToolsReady(true);
          setTotalTools(data.data.tools_loaded);
          
          // If there's a pending message, create a chat and send it
          if (pendingMessage && !currentChatId) {
            console.log('Tools ready, creating chat for pending message');
            handleNewChat();
          }
          break;
        
        case 'chat_ready':
          // Chat is ready for messages
          console.log('Chat ready:', data.data.chat_id);
          setChatReady(true); // Mark chat as ready - messages can now be sent
          setIsLoadingChat(false); // Clear loading state
          
          // Refresh chat list to show the new/updated chat
          const userId = getUserId();
          setTimeout(() => fetchUserChats(userId), 1000);
          
          // If there's a pending message, send it now
          if (pendingMessage) {
            console.log('Sending pending message:', pendingMessage);
            setChatMessages(prev => [...prev, { role: 'user', text: pendingMessage }]);
            socket.current.send(JSON.stringify({ type: 'message', data: { text: pendingMessage } }));
            setIsTyping(true);
            setPendingMessage(null);
          }
          
          // Process any queued messages
          if (messageQueue.length > 0) {
            console.log('Processing queued messages:', messageQueue.length);
            messageQueue.forEach((queuedMsg) => {
              console.log('Sending queued message:', queuedMsg.text.substring(0, 50));
              setChatMessages(prev => [...prev, { role: 'user', text: queuedMsg.text, attachments: queuedMsg.attachments }]);
              socket.current.send(JSON.stringify({ type: 'message', data: queuedMsg.data }));
            });
            setMessageQueue([]); // Clear the queue
            setIsTyping(true);
          }
          break;
          
        case 'message':
          setIsTyping(false); // Stop typing on actual message
          setChatMessages(prev => [...prev, { role: 'bot', text: data.data.text }]);
          break;
          
        case 'tool_use':
          const toolUseText = `${data.data.name}(${JSON.stringify(data.data.args)})`;
          // Add to main chat with special role
          setChatMessages(prev => [...prev, { role: 'tool_use', text: toolUseText, toolData: data.data }]);
          // Also add to tool activity sidebar
          setToolActivity(prev => [...prev, { kind: 'tool_use', text: toolUseText }]);
          setToolUses(prev => [...prev, data.data]);
          break;
          
        case 'tool_result':
          const toolResultText = `${data.data.result}`;
          // Add to main chat with special role
          setChatMessages(prev => [...prev, { role: 'tool_result', text: toolResultText, toolData: data.data }]);
          // Also add to tool activity sidebar
          setToolActivity(prev => [...prev, { kind: 'tool_result', text: `${data.data.name} → ${toolResultText}` }]);
          setToolResults(prev => [...prev, data.data]);
          break;
          
        case 'thought':
          setChatMessages(prev => [...prev, { role: 'thought', text: data.data.text }]);
          setToolActivity(prev => [...prev, { kind: 'thought', text: data.data.text }]);
          break;
          
        case 'status':
          setIsTyping(false); // Stop typing on status
          setChatMessages(prev => [...prev, { role: 'status', text: data.data.message }]);
          break;
          
        case 'error':
          setIsTyping(false); // Stop typing on error
          setChatMessages(prev => [...prev, { role: 'error', text: data.data.message }]);
          break;
        
        case 'token_usage':
          // Update token usage display
          console.log('Received token usage:', data.data);
          setTokenUsage({
            input_tokens: data.data.input_tokens || 0,
            output_tokens: data.data.output_tokens || 0,
            total_tokens: data.data.total_tokens || 0,
            cached_tokens: data.data.cached_tokens
          });
          break;
        
        case 'token_estimate':
          // Accumulate estimated tokens
          console.log('Received token estimate:', data.data);
          const { estimated_tokens, source } = data.data;
          
          if (source === 'history') {
            // For history, set the baseline estimate
            setEstimatedTokens(estimated_tokens);
          } else {
            // For incremental estimates (message, thought, tool_call, etc.), accumulate
            setEstimatedTokens(prev => prev + estimated_tokens);
          }
          break;
          
        default:
          console.log("Unknown message type:", data.type);
          setChatMessages(prev => [...prev, { role: 'status', text: `Unknown: ${JSON.stringify(data)}` }]);
          break;
      }
    };

    socket.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setReconnectionAttempts(prevAttempts => prevAttempts + 1);
      setConnectionStatus('Error');
      if (reconnectionAttempts > 5) {
        setReconnectionError('Failed to reconnect after multiple attempts. Please check your connection.');
      }
    };

    return () => {
      socket.current.close();
    };
  }, []); // Connect once on mount, not when chat changes

  // Fetch chats on mount
  useEffect(() => {
    const userId = getUserId();
    fetchUserChats(userId);
  }, []);
  
  // Handle URL changes - load chat from URL if different from current
  useEffect(() => {
    if (urlChatId && urlChatId !== currentChatId && toolsReady) {
      console.log('URL chat ID changed, loading chat:', urlChatId);
      handleSwitchChat(urlChatId);
    }
  }, [urlChatId, toolsReady]); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh chats after sending a message (to get auto-named chats)
  // Only trigger on first few messages to avoid constant refetching
  useEffect(() => {
    if (chatMessages.length > 0 && chatMessages.length <= 5 && currentChatId) {
      const userId = getUserId();
      // Debounce the fetch to avoid too many requests
      const timer = setTimeout(() => {
        fetchUserChats(userId);
      }, 3000); // Increased delay
      return () => clearTimeout(timer);
    }
  }, [chatMessages.length, currentChatId, fetchUserChats]);

  // Autocomplete logic - memoized to prevent re-creation
  const updateAutocomplete = useCallback((text, cursorPos) => {
    // Ensure text is a string
    if (typeof text !== 'string') {
      setAutocompleteType(null);
      setAutocompleteItems([]);
      return;
    }
    
    if (text.startsWith('/')) {
      const query = text.substring(1).toLowerCase();
      const filtered = (prompts || []).filter(p => 
        p && p.name && (
          p.name.toLowerCase().includes(query) || 
          (p.description && p.description.toLowerCase().includes(query))
        )
      );
      setAutocompleteType('prompt');
      setAutocompleteItems(filtered);
      setAutocompleteSelectedIndex(0);
      return;
    }
    
    const beforeCursor = text.substring(0, cursorPos);
    const atIndex = beforeCursor.lastIndexOf('@');
    if (atIndex !== -1) {
      const query = beforeCursor.substring(atIndex + 1).toLowerCase();
      const filtered = (resources || []).filter(r => 
        r && r.uri && (
          r.uri.toLowerCase().includes(query) || 
          (r.description && r.description.toLowerCase().includes(query))
        )
      );
      setAutocompleteType('resource');
      setAutocompleteItems(filtered);
      setAutocompleteSelectedIndex(0);
      return;
    }
    
    setAutocompleteType(null);
    setAutocompleteItems([]);
  }, [prompts, resources]);

  const handleInputChange = (event) => {
    const value = event.target.value;
    const cursor = event.target.selectionStart || 0;
    setInputValue(value);
    setCursorPosition(cursor);
    
    // Debounce autocomplete to reduce lag
    if (autocompleteDebounceRef.current) {
      clearTimeout(autocompleteDebounceRef.current);
    }
    
    autocompleteDebounceRef.current = setTimeout(() => {
      try {
        updateAutocomplete(value, cursor);
        
        if (inputRef.current) {
          const rect = inputRef.current.getBoundingClientRect();
          const spaceBelow = window.innerHeight - rect.bottom;
          const spaceAbove = rect.top;
          
          if (spaceBelow < 320 && spaceAbove > spaceBelow) {
            setAutocompletePosition({ 
              bottom: window.innerHeight - rect.top + 8,
              showAbove: true 
            });
          } else {
            setAutocompletePosition({ 
              bottom: null,
              showAbove: false 
            });
          }
        }
      } catch (error) {
        console.error('Error updating autocomplete:', error);
      }
    }, 150); // 150ms debounce
  };

  const insertAutocompleteItem = (item) => {
    if (autocompleteType === 'prompt') {
      setInputValue(`/${item.name} `);
      setCursorPosition(`/${item.name} `.length);
    } else if (autocompleteType === 'resource') {
      const beforeCursor = inputValue.substring(0, cursorPosition);
      const atIndex = beforeCursor.lastIndexOf('@');
      const beforeAt = inputValue.substring(0, atIndex);
      const afterCursor = inputValue.substring(cursorPosition);
      const newValue = `${beforeAt}@${item.uri} ${afterCursor}`;
      setInputValue(newValue);
      setCursorPosition(`${beforeAt}@${item.uri} `.length);
    }
    setAutocompleteType(null);
    setAutocompleteItems([]);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const sendMessage = async () => {
    const messageToSend = inputValue.trim();
    
    // Get successfully uploaded files
    const uploadedFiles = attachedFiles.filter(f => !f.uploading && !f.error && f.file_id);
    
    // Require either a message or successfully uploaded files
    if (!messageToSend && uploadedFiles.length === 0) return;

    // Check if any files are still uploading
    const stillUploading = attachedFiles.some(f => f.uploading);
    if (stillUploading) {
      console.log('Waiting for files to finish uploading...');
      setChatMessages(prev => [...prev, { 
        role: 'system', 
        text: 'Please wait for files to finish uploading...' 
      }]);
      return;
    }

    // If no chat is selected, create a new chat first
    if (!currentChatId) {
      console.log('No chat selected, creating new chat with first message');
      setPendingMessage(messageToSend);
      setInputValue('');
      
      // Check if tools are ready before creating chat
      if (toolsReady) {
        handleNewChat();
      } else {
        console.log('Waiting for tools to be ready...');
      }
      return;
    }

    // Build message text - include file names if no text provided
    let finalText = messageToSend;
    if (!finalText && uploadedFiles.length > 0) {
      finalText = `[Attached ${uploadedFiles.length} file${uploadedFiles.length > 1 ? 's' : ''}: ${uploadedFiles.map(f => f.name).join(', ')}]`;
    }

    let messageData = { text: finalText };

    // Add file IDs if we have uploaded files
    if (uploadedFiles.length > 0) {
      // For now, send the first file_id (backend currently supports one)
      // TODO: Update backend to support multiple file_ids
      messageData.file_id = uploadedFiles[0].file_id;
      console.log('Sending message with file attachments:', uploadedFiles.map(f => f.file_id));
    }

    // Store message with attachment info
    const userMessage = { 
      role: 'user', 
      text: finalText,
      attachments: uploadedFiles.map(f => ({ 
        name: f.name, 
        file_id: f.file_id,
        description: f.description,
        size: f.size
      }))
    };

    // CRITICAL FIX: Check if chat is ready before sending
    if (!chatReady) {
      console.log('Chat not ready yet, queuing message:', finalText.substring(0, 50));
      // Queue the message to be sent when chat_ready is received
      setMessageQueue(prev => [...prev, { text: finalText, data: messageData, attachments: userMessage.attachments }]);
      // Still show the message in the UI optimistically
      setChatMessages(prev => [...prev, userMessage]);
      
      // Clear input and attachments
      setInputValue('');
      setAutocompleteType(null);
      setAutocompleteItems([]);
      setAttachedFiles([]);
      return;
    }

    // Chat is ready, send immediately
    setChatMessages(prev => [...prev, userMessage]);
    
    // Reset estimated tokens to current actual usage (starting point for new estimates)
    setEstimatedTokens(tokenUsage.total_tokens);
    
    socket.current.send(JSON.stringify({ type: 'message', data: messageData }));
    
    // Show typing indicator
    setIsTyping(true);

    if (sessionId) {
      fetch('/record_tool_usage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          tool_name: 'sendMessage',
          tool_args: { message: messageToSend },
          result: null,
        })
      }).catch((err) => console.error('Error recording tool usage:', err));
    }

    setInputValue('');
    setAutocompleteType(null);
    setAutocompleteItems([]);
    setAttachedFiles([]);  // Clear attachments after sending
  };

  const handleKeyDown = (event) => {
    if (autocompleteType && autocompleteItems.length > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setAutocompleteSelectedIndex(prev => 
          prev < autocompleteItems.length - 1 ? prev + 1 : 0
        );
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setAutocompleteSelectedIndex(prev => 
          prev > 0 ? prev - 1 : autocompleteItems.length - 1
        );
        return;
      }
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        insertAutocompleteItem(autocompleteItems[autocompleteSelectedIndex]);
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        setAutocompleteType(null);
        setAutocompleteItems([]);
        return;
      }
    }

    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
      return;
    }

    if (event.key === 's' && event.ctrlKey) {
      event.preventDefault();
      sendMessage();
      return;
    }

    if (event.key === 'h' && event.ctrlKey) {
      event.preventDefault();
      setShowHelpModal(true);
      return;
    }
  };

  return (
    <>
      {/* Splash Screen - shown while tools are loading */}
      {!toolsReady && <SplashScreen toolsLoading={toolsLoading} totalTools={totalTools} />}
      
      <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
        {/* Top App Bar */}
        <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          bgcolor: '#0f1419',
          boxShadow: 'none',
          borderBottom: '1px solid rgba(31, 41, 55, 0.5)',
        }}
      >
        {/* Token Usage Progress Bar */}
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '3px',
            bgcolor: 'rgba(255, 255, 255, 0.05)',
            cursor: 'pointer',
            transition: 'height 0.2s',
            '&:hover': {
              height: '4px',
            },
          }}
          title={`Token Usage: ${tokenUsage.total_tokens.toLocaleString()} / ${maxTokens.toLocaleString()} (${((tokenUsage.total_tokens / maxTokens) * 100).toFixed(2)}%)\nEstimated: ${estimatedTokens.toLocaleString()}\nInput: ${tokenUsage.input_tokens.toLocaleString()} | Output: ${tokenUsage.output_tokens.toLocaleString()}${tokenUsage.cached_tokens ? ` | Cached: ${tokenUsage.cached_tokens.toLocaleString()}` : ''}`}
        >
          {/* Estimated tokens outline (extends ahead) */}
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              height: '100%',
              width: `${Math.min((estimatedTokens / maxTokens) * 100, 100)}%`,
              border: '1px solid',
              borderColor: estimatedTokens / maxTokens > 0.9 ? 'rgba(239, 68, 68, 0.4)' : estimatedTokens / maxTokens > 0.7 ? 'rgba(245, 158, 11, 0.4)' : 'rgba(59, 130, 246, 0.4)',
              boxSizing: 'border-box',
              transition: 'width 0.3s ease-in-out, border-color 0.3s',
              pointerEvents: 'none',
            }}
          />
          {/* Actual tokens filled (solid) */}
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              height: '100%',
              width: `${Math.min((tokenUsage.total_tokens / maxTokens) * 100, 100)}%`,
              bgcolor: tokenUsage.total_tokens / maxTokens > 0.9 ? '#ef4444' : tokenUsage.total_tokens / maxTokens > 0.7 ? '#f59e0b' : '#3b82f6',
              transition: 'width 0.3s ease-in-out, background-color 0.3s',
              boxShadow: tokenUsage.total_tokens > 0 ? '0 0 8px rgba(59, 130, 246, 0.6)' : 'none',
              pointerEvents: 'none',
            }}
          />
        </Box>
        <Toolbar>
          {/* Sidebar toggle button - always visible */}
          <IconButton
            color="inherit"
            aria-label="toggle sidebar"
            edge="start"
            onClick={() => isMobile ? setMobileLeftDrawerOpen(!mobileLeftDrawerOpen) : setLeftSidebarOpen(!leftSidebarOpen)}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Box
            component="img"
            src="/robot-logo.svg"
            alt="Sparky"
            sx={{
              height: 32,
              width: 32,
              mr: 2,
            }}
          />
          <Typography 
            variant={isSmallMobile ? "body1" : "h6"} 
            noWrap 
            component="div" 
            sx={{ flexGrow: 1, fontWeight: 600 }}
          >
            {isSmallMobile ? "Sparky" : "Sparky Studio"}
          </Typography>
          <Stack direction="row" spacing={isSmallMobile ? 0.5 : 1}>
            <IconButton
              onClick={() => setShowHelpModal(true)}
              title="Help (Ctrl+H)"
              size="small"
              sx={{ color: 'text.primary' }}
            >
              <HelpIcon fontSize={isSmallMobile ? "small" : "medium"} />
            </IconButton>
            <IconButton
              onClick={() => setShowToolActivity(!showToolActivity)}
              title="Toggle Tool Activity"
              size="small"
              sx={{ color: 'primary.main' }}
            >
              <CodeIcon fontSize={isSmallMobile ? "small" : "medium"} />
            </IconButton>
          </Stack>
        </Toolbar>
      </AppBar>

      {/* Left Sidebar */}
      <Drawer
        variant={isMobile ? "temporary" : "persistent"}
        open={isMobile ? mobileLeftDrawerOpen : leftSidebarOpen}
        onClose={() => setMobileLeftDrawerOpen(false)}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
        sx={{
          width: SIDEBAR_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: SIDEBAR_WIDTH,
            boxSizing: 'border-box',
            bgcolor: '#0f1419',
            borderRight: '1px solid rgba(31, 41, 55, 0.3)',
          },
        }}
      >
        <Toolbar /> {/* Spacer for AppBar */}
        
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          {/* Top Section - Navigation */}
          <Box>
            <List>
              <ListItem disablePadding>
                <ListItemButton selected>
                  <ListItemIcon>
                    <HomeIcon sx={{ color: 'text.primary' }} />
                  </ListItemIcon>
                  <ListItemText primary="Home" />
                </ListItemButton>
              </ListItem>
              
              <ListItem disablePadding>
                <ListItemButton>
                  <ListItemIcon>
                    <ChatIcon sx={{ color: 'text.primary' }} />
                  </ListItemIcon>
                  <ListItemText primary="Chat" />
                </ListItemButton>
              </ListItem>
            </List>

            <Divider sx={{ my: 2 }} />
          </Box>

          {/* Middle Section - Chat History (Scrollable) */}
          <Box sx={{ flex: 1, overflowY: 'auto', px: 2, py: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                RECENT CHATS
              </Typography>
              <IconButton 
                size="small" 
                onClick={handleNewChat}
                title="New Chat"
                sx={{ color: 'primary.main' }}
              >
                <ChatIcon fontSize="small" />
              </IconButton>
            </Box>
            <List dense sx={{ mt: 1 }}>
                {userChats.map((chat) => (
                  <ListItem 
                    key={chat.chat_id} 
                    disablePadding
                    secondaryAction={
                      renamingChatId === chat.chat_id ? (
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <IconButton 
                            size="small"
                            onClick={() => handleRenameChat(chat.chat_id, renameValue)}
                            sx={{ color: 'primary.main' }}
                            title="Save"
                          >
                            <SendIcon fontSize="small" />
                          </IconButton>
                          <IconButton 
                            size="small"
                            onClick={() => {
                              setRenamingChatId(null);
                              setRenameValue('');
                            }}
                            sx={{ color: 'text.secondary' }}
                            title="Cancel"
                          >
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        </Box>
                      ) : (
                        <IconButton 
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActionMenuAnchor(e.currentTarget);
                            setActionMenuChatId(chat.chat_id);
                          }}
                          sx={{ color: 'text.secondary' }}
                          title="More actions"
                          disabled={isLoadingChat}
                        >
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      )
                    }
                  >
                    <ListItemButton 
                      sx={{ borderRadius: 1, fontSize: '0.875rem' }}
                      selected={currentChatId === chat.chat_id}
                      onClick={() => handleSwitchChat(chat.chat_id)}
                      disabled={isLoadingChat}
                    >
                      {renamingChatId === chat.chat_id ? (
                        <TextField
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleRenameChat(chat.chat_id, renameValue);
                            } else if (e.key === 'Escape') {
                              setRenamingChatId(null);
                              setRenameValue('');
                            }
                          }}
                          size="small"
                          fullWidth
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <ListItemText 
                          primary={chat.chat_name} 
                          secondary={`Updated: ${new Date(chat.updated_at).toLocaleDateString()}`}
                          primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                          secondaryTypographyProps={{ variant: 'caption' }}
                        />
                      )}
                    </ListItemButton>
                  </ListItem>
                ))}
                {userChats.length === 0 && (
                  <ListItem>
                    <ListItemText 
                      primary="No chats yet" 
                      secondary="Click + to start a new chat"
                      primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                )}
              </List>

            {/* Archived Chats Section */}
            <Box sx={{ mt: 2 }}>
              <Box 
                sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center', 
                  mb: 1,
                  cursor: 'pointer',
                  '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' },
                  borderRadius: 1,
                  px: 1,
                  py: 0.5,
                }}
                onClick={() => {
                  setShowArchivedChats(!showArchivedChats);
                  if (!showArchivedChats) {
                    const userId = getUserId();
                    fetchArchivedChats(userId);
                  }
                }}
              >
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                  ARCHIVED CHATS
                </Typography>
                <IconButton size="small" sx={{ color: 'text.secondary' }}>
                  {showArchivedChats ? <ExpandMoreIcon fontSize="small" /> : <ChevronRightIcon fontSize="small" />}
                </IconButton>
              </Box>
              <Collapse in={showArchivedChats}>
                <List dense>
                  {archivedChats.map((chat) => (
                    <ListItem 
                      key={chat.chat_id} 
                      disablePadding
                      secondaryAction={
                        <IconButton 
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            setActionMenuAnchor(e.currentTarget);
                            setActionMenuChatId(chat.chat_id);
                          }}
                          sx={{ color: 'text.secondary' }}
                          title="More actions"
                        >
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      }
                    >
                      <ListItemButton 
                        sx={{ borderRadius: 1, fontSize: '0.875rem', opacity: 0.7 }}
                        selected={currentChatId === chat.chat_id}
                        onClick={() => handleSwitchChat(chat.chat_id)}
                      >
                        <ListItemText 
                          primary={chat.chat_name} 
                          secondary={`Archived: ${new Date(chat.updated_at).toLocaleDateString()}`}
                          primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                          secondaryTypographyProps={{ variant: 'caption' }}
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                  {archivedChats.length === 0 && (
                    <ListItem>
                      <ListItemText 
                        primary="No archived chats" 
                        primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
                      />
                    </ListItem>
                  )}
                </List>
              </Collapse>
            </Box>
          </Box>

          {/* Bottom Section - Settings & Profile */}
          <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
            <List>
              <ListItem disablePadding>
                <ListItemButton>
                  <ListItemIcon>
                    <SettingsIcon sx={{ color: 'text.secondary' }} />
                  </ListItemIcon>
                  <ListItemText primary="Settings" />
                </ListItemButton>
              </ListItem>
              
              <ListItem disablePadding>
                <ListItemButton>
                  <ListItemIcon>
                    <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
                      <PersonIcon fontSize="small" />
                    </Avatar>
                  </ListItemIcon>
                  <ListItemText 
                    primary="User Profile" 
                    secondary="badrobot.user"
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItemButton>
              </ListItem>
            </List>
          </Box>
        </Box>
      </Drawer>

      {/* Main Content Area */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          overflow: 'hidden',
          position: 'relative',
          width: isMobile ? '100%' : leftSidebarOpen ? `calc(100% - ${SIDEBAR_WIDTH}px)` : '100%',
          marginLeft: isMobile ? 0 : leftSidebarOpen ? 0 : 0,
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar /> {/* Spacer for AppBar */}

        {/* Loading Overlay - covers entire chat panel including prompt */}
        {(isLoadingChat || (currentChatId && !chatReady)) && (
          <Box
            sx={{
              position: 'absolute',
              top: 64,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'rgba(10, 14, 26, 0.9)',
              backdropFilter: 'blur(8px)',
              zIndex: 1500,
            }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  borderRadius: '50%',
                  border: '4px solid rgba(59, 130, 246, 0.2)',
                  borderTopColor: '#3b82f6',
                  animation: 'spin 1s linear infinite',
                  mx: 'auto',
                  mb: 2,
                  '@keyframes spin': {
                    '0%': { transform: 'rotate(0deg)' },
                    '100%': { transform: 'rotate(360deg)' },
                  },
                }}
              />
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {isLoadingChat ? 'Loading chat...' : 'Connecting to chat...'}
              </Typography>
            </Box>
          </Box>
        )}

        {/* Chat Messages */}
        <Box
          ref={chatScrollRef}
          sx={{
            flex: 1,
            overflowY: 'auto',
            p: isSmallMobile ? 1.5 : isMobile ? 2 : 3,
            pb: isMobile ? '180px' : isSmallMobile ? 1.5 : isMobile ? 2 : 3,
            maxWidth: '900px',
            width: '100%',
            mx: 'auto',
          }}
        >
          <Stack spacing={1.5}>
            {chatMessages.map((message, index) => (
              <ChatMessage 
                key={`msg-${index}-${message.text.substring(0, 20)}`}
                role={message.role} 
                text={message.text} 
                attachments={message.attachments}
              />
            ))}
            
            {/* Typing Indicator */}
            {isTyping && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  p: 2,
                  maxWidth: '200px',
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    gap: 0.5,
                    alignItems: 'center',
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: 'primary.main',
                      animation: 'pulse 1.4s ease-in-out infinite',
                      '@keyframes pulse': {
                        '0%, 80%, 100%': {
                          opacity: 0.3,
                          transform: 'scale(0.8)',
                        },
                        '40%': {
                          opacity: 1,
                          transform: 'scale(1)',
                        },
                      },
                    }}
                  />
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: 'primary.main',
                      animation: 'pulse 1.4s ease-in-out 0.2s infinite',
                      '@keyframes pulse': {
                        '0%, 80%, 100%': {
                          opacity: 0.3,
                          transform: 'scale(0.8)',
                        },
                        '40%': {
                          opacity: 1,
                          transform: 'scale(1)',
                        },
                      },
                    }}
                  />
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: 'primary.main',
                      animation: 'pulse 1.4s ease-in-out 0.4s infinite',
                      '@keyframes pulse': {
                        '0%, 80%, 100%': {
                          opacity: 0.3,
                          transform: 'scale(0.8)',
                        },
                        '40%': {
                          opacity: 1,
                          transform: 'scale(1)',
                        },
                      },
                    }}
                  />
                </Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
                  Sparky is thinking...
                </Typography>
              </Box>
            )}
          </Stack>
        </Box>

        {/* Input Area - Sleeker design */}
        <Box
          sx={{
            p: isSmallMobile ? 1 : isMobile ? 1.5 : 3,
            pb: isMobile ? 'max(env(safe-area-inset-bottom), 8px)' : isSmallMobile ? 1 : isMobile ? 1.5 : 3,
            maxWidth: isMobile ? '100%' : '900px',
            width: '100%',
            mx: 'auto',
            position: isMobile ? 'fixed' : 'relative',
            bottom: isMobile ? 0 : 'auto',
            left: isMobile ? 0 : 'auto',
            right: isMobile ? 0 : 'auto',
            bgcolor: isMobile ? 'background.default' : 'transparent',
            zIndex: isMobile ? 1000 : 'auto',
            borderTop: isMobile ? '1px solid rgba(31, 41, 55, 0.5)' : 'none',
            boxShadow: isMobile ? '0 -4px 12px rgba(0, 0, 0, 0.3)' : 'none',
          }}
        >
          {/* Connection Status Indicator */}
          <Box
            sx={{
              position: 'absolute',
              bottom: 'calc(100% + 8px)',
              right: isSmallMobile ? 4 : 12,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              zIndex: 1000,
              transition: 'all 0.3s ease',
              '&:hover .status-text': {
                opacity: isSmallMobile ? 0 : 1,
                maxWidth: isSmallMobile ? 0 : '200px',
              }
            }}
          >
            <Box
              className="status-text"
              sx={{
                opacity: 0,
                maxWidth: 0,
                overflow: 'hidden',
                transition: 'all 0.3s ease',
                whiteSpace: 'nowrap',
                fontSize: '0.875rem',
                color: 'text.secondary',
                bgcolor: 'rgba(15, 20, 25, 0.95)',
                backdropFilter: 'blur(10px)',
                px: 2,
                py: 1,
                borderRadius: 2,
                border: '1px solid rgba(255, 255, 255, 0.1)',
              }}
            >
              {connectionStatus}
              {reconnectionError && (
                <Box component="span" sx={{ color: 'error.main', display: 'block', mt: 0.5 }}>
                  {reconnectionError}
                </Box>
              )}
            </Box>
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                backgroundColor: 
                  connectionStatus === 'Connected' ? '#10b981' : 
                  connectionStatus === 'Disconnected' ? '#ef4444' : 
                  '#f59e0b',
                boxShadow: connectionStatus === 'Connected' 
                  ? '0 0 12px rgba(16, 185, 129, 0.8)' 
                  : connectionStatus === 'Disconnected'
                  ? '0 0 12px rgba(239, 68, 68, 0.8)'
                  : '0 0 12px rgba(245, 158, 11, 0.8)',
                animation: connectionStatus === 'Connecting...' ? 'pulse 2s ease-in-out infinite' : 'none',
                '@keyframes pulse': {
                  '0%, 100%': {
                    opacity: 1,
                    transform: 'scale(1)',
                  },
                  '50%': {
                    opacity: 0.5,
                    transform: 'scale(1.2)',
                  },
                },
              }}
            />
          </Box>
          
          <Box sx={{ position: 'relative' }}>
            {/* File Attachments Display */}
            {attachedFiles.length > 0 && (
              <Box sx={{ 
                mb: 1, 
                display: 'flex', 
                flexWrap: 'wrap', 
                gap: 1,
                p: 1,
                bgcolor: 'rgba(17, 24, 39, 0.4)',
                borderRadius: 2,
              }}>
                {attachedFiles.map((file) => (
                  <Chip
                    key={file.id}
                    icon={file.uploading ? <CircularProgress size={16} /> : file.error ? <ErrorIcon /> : <FileIcon />}
                    label={`${file.name} ${file.error ? '(Failed)' : ''}`}
                    onDelete={() => removeAttachment(file.id)}
                    size="small"
                    color={file.error ? 'error' : file.uploading ? 'default' : 'success'}
                    variant={file.uploading ? 'outlined' : 'filled'}
                    sx={{ 
                      maxWidth: 200,
                      '& .MuiChip-label': {
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }
                    }}
                  />
                ))}
              </Box>
            )}

            <TextField
              inputRef={inputRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragEnter={handleDragOver}
              onDragLeave={handleDragLeave}
              placeholder={
                isDragging 
                  ? "Drop files here..." 
                  : isSmallMobile 
                    ? "Type a message..." 
                    : "Start typing a prompt... (/ for commands, @ for resources, Ctrl+H for help)"
              }
              multiline
              minRows={1}
              maxRows={isSmallMobile ? 4 : 8}
              fullWidth
              variant="outlined"
              size={isSmallMobile ? "small" : "medium"}
              InputProps={{
                startAdornment: !isSmallMobile && (
                  <InputAdornment position="start">
                    <IconButton
                      onClick={() => document.getElementById('file-upload').click()}
                      size="small"
                      sx={{ color: attachedFiles.length > 0 ? 'success.main' : 'text.secondary' }}
                      title="Attach files"
                    >
                      <AttachFileIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    {isSmallMobile && (
                      <IconButton
                        onClick={() => document.getElementById('file-upload').click()}
                        size="small"
                        sx={{ 
                          color: attachedFiles.length > 0 ? 'success.main' : 'text.secondary',
                          mr: 0.5
                        }}
                        title="Attach files"
                      >
                        <AttachFileIcon fontSize="small" />
                      </IconButton>
                    )}
                    <IconButton
                      onClick={sendMessage}
                      disabled={(!inputValue.trim() && attachedFiles.filter(f => f.file_id).length === 0) || connectionStatus !== 'Connected'}
                      edge="end"
                      size={isSmallMobile ? "small" : "medium"}
                      sx={{
                        color: (inputValue.trim() || attachedFiles.some(f => f.file_id)) && connectionStatus === 'Connected' ? 'primary.main' : 'text.disabled',
                        '&:hover': {
                          bgcolor: 'action.hover',
                        },
                      }}
                    >
                      <SendIcon fontSize={isSmallMobile ? "small" : "medium"} />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: isDragging ? 'rgba(59, 130, 246, 0.1)' : 'rgba(17, 24, 39, 0.6)',
                  backdropFilter: 'blur(10px)',
                  borderRadius: 4,
                  border: isDragging 
                    ? '2px dashed rgba(59, 130, 246, 0.8)' 
                    : attachedFiles.length > 0 
                      ? '1px solid rgba(34, 197, 94, 0.5)' 
                      : '1px solid rgba(255, 255, 255, 0.1)',
                  transition: 'all 0.2s',
                  '&:hover': {
                    border: isDragging 
                      ? '2px dashed rgba(59, 130, 246, 1)' 
                      : attachedFiles.length > 0 
                        ? '1px solid rgba(34, 197, 94, 0.7)' 
                        : '1px solid rgba(255, 255, 255, 0.2)',
                  },
                  '&.Mui-focused': {
                    border: '1px solid',
                    borderColor: attachedFiles.length > 0 ? 'success.main' : 'primary.main',
                    boxShadow: attachedFiles.length > 0 ? '0 0 0 2px rgba(34, 197, 94, 0.1)' : '0 0 0 2px rgba(59, 130, 246, 0.1)',
                  },
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  border: 'none',
                },
              }}
            />
            {autocompleteType && autocompleteItems.length > 0 && (
              <AutocompleteDropdown
                items={autocompleteItems}
                selectedIndex={autocompleteSelectedIndex}
                onSelect={insertAutocompleteItem}
                onClose={() => {
                  setAutocompleteType(null);
                  setAutocompleteItems([]);
                }}
                type={autocompleteType}
                position={autocompletePosition}
              />
            )}
          </Box>
          <input
            type="file"
            id="file-upload"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </Box>
      </Box>

      {/* Right Sidebar - Tool Activity */}
      <Drawer
        anchor="right"
        open={showToolActivity}
        onClose={() => setShowToolActivity(false)}
        variant={isMobile ? "temporary" : "persistent"}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
        sx={{
          width: showToolActivity ? (isMobile ? '100%' : 400) : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: isMobile ? '100%' : 400,
            boxSizing: 'border-box',
            bgcolor: '#0f1419',
            borderLeft: '1px solid rgba(31, 41, 55, 0.3)',
          },
        }}
      >
        <Toolbar /> {/* Spacer for AppBar */}
        
        <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100% - 64px)' }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              p: 2,
              borderBottom: '1px solid rgba(31, 41, 55, 0.5)',
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Tool Activity
            </Typography>
            <IconButton
              onClick={() => setShowToolActivity(false)}
              size="small"
              sx={{ color: 'text.secondary' }}
            >
              <CloseIcon />
            </IconButton>
          </Box>
          <Box sx={{ flex: 1, overflowY: 'auto', p: 3 }}>
            <Stack spacing={1.5}>
              {toolActivity.map((activity, index) => (
                <ToolActivityItem key={index} kind={activity.kind} text={activity.text} />
              ))}
            </Stack>
          </Box>
        </Box>
      </Drawer>

      {/* Action Menu for Chat Actions */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={() => {
          setActionMenuAnchor(null);
          setActionMenuChatId(null);
        }}
        PaperProps={{
          sx: {
            bgcolor: '#1e293b',
            border: '1px solid rgba(255, 255, 255, 0.1)',
          }
        }}
      >
        {/* Show different actions based on whether chat is archived */}
        {archivedChats.some(chat => chat.chat_id === actionMenuChatId) ? (
          <>
            <MenuItem 
              onClick={() => {
                handleUnarchiveChat(actionMenuChatId);
                setActionMenuAnchor(null);
                setActionMenuChatId(null);
              }}
              sx={{ gap: 1 }}
            >
              <UnarchiveIcon fontSize="small" />
              Unarchive
            </MenuItem>
            <MenuItem 
              onClick={() => {
                handleDeleteChat(actionMenuChatId);
                setActionMenuAnchor(null);
                setActionMenuChatId(null);
              }}
              sx={{ gap: 1, color: 'error.main' }}
            >
              <DeleteIcon fontSize="small" />
              Delete
            </MenuItem>
          </>
        ) : (
          <>
            <MenuItem 
              onClick={() => {
                const chat = userChats.find(c => c.chat_id === actionMenuChatId);
                if (chat) {
                  setRenamingChatId(chat.chat_id);
                  setRenameValue(chat.chat_name);
                }
                setActionMenuAnchor(null);
                setActionMenuChatId(null);
              }}
              sx={{ gap: 1 }}
            >
              <EditIcon fontSize="small" />
              Rename
            </MenuItem>
            <MenuItem 
              onClick={() => {
                handleArchiveChat(actionMenuChatId);
                setActionMenuAnchor(null);
                setActionMenuChatId(null);
              }}
              sx={{ gap: 1 }}
            >
              <ArchiveIcon fontSize="small" />
              Archive
            </MenuItem>
            <MenuItem 
              onClick={() => {
                handleDeleteChat(actionMenuChatId);
                setActionMenuAnchor(null);
                setActionMenuChatId(null);
              }}
              sx={{ gap: 1, color: 'error.main' }}
            >
              <DeleteIcon fontSize="small" />
              Delete
            </MenuItem>
          </>
        )}
      </Menu>

      {/* Help Modal */}
      <HelpModal
        isOpen={showHelpModal}
        onClose={() => setShowHelpModal(false)}
        resources={resources}
        prompts={prompts}
        toolUses={toolUses}
        toolResults={toolResults}
      />
      </Box>
    </>
  );
}

export default App;
