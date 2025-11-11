import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ChatMessage.css';

const ChatMessage = React.memo(({ role, text, attachments }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [shouldShowToggle, setShouldShowToggle] = useState(false);
  const contentRef = useRef(null);

  const getRoleClass = () => {
    switch (role) {
      case 'user':
        return 'message-user';
      case 'bot':
        return 'message-bot';
      case 'status':
        return 'message-status';
      case 'error':
        return 'message-error';
      case 'thought':
        return 'message-thought';
      case 'tool_use':
        return 'message-tool-use';
      case 'tool_result':
        return 'message-tool-result';
      default:
        return 'message-bot';
    }
  };

  const getRolePrefix = () => {
    switch (role) {
      case 'thought':
        return '💭 Thinking';
      case 'tool_use':
        return '🔧 Tool Use';
      case 'tool_result':
        return '✓ Result';
      default:
        return null;
    }
  };

  const isCollapsible = role === 'tool_use' || role === 'tool_result' || role === 'thought';

  // Check if content is tall enough to need collapsing
  useEffect(() => {
    if (contentRef.current && isCollapsible) {
      const height = contentRef.current.scrollHeight;
      // Show toggle if content is taller than ~4 lines (assuming ~24px per line)
      setShouldShowToggle(height > 100);
    }
  }, [text, isCollapsible]);

  // Status messages don't get bubbles
  if (role === 'status') {
    return (
      <div className="chat-message message-status">
        <div className="status-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {text}
          </ReactMarkdown>
        </div>
      </div>
    );
  }

  const prefix = getRolePrefix();

  return (
    <div className={`chat-message ${getRoleClass()}`}>
      <div className={`message-content ${isCollapsible && !isExpanded && shouldShowToggle ? 'message-collapsed' : ''}`}>
        {prefix && (
          <div className="message-prefix">
            {prefix}
          </div>
        )}
        {attachments && attachments.length > 0 && (
          <div className="message-attachments">
            {attachments.map((file, index) => {
              const isImage = file.name && /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(file.name);
              const thumbnailUrl = file.file_id && isImage ? `/file_thumbnail/${file.file_id}` : null;
              
              return (
                <div key={index} className={`attachment-badge ${isImage ? 'attachment-image' : ''}`}>
                  {thumbnailUrl ? (
                    <div className="attachment-thumbnail">
                      <img src={thumbnailUrl} alt={file.name} />
                    </div>
                  ) : (
                    <span className="attachment-icon">📎</span>
                  )}
                  <div className="attachment-info">
                    <span className="attachment-name">{file.name}</span>
                    {file.description && (
                      <span className="attachment-description" title={file.description}>
                        {file.description.substring(0, 100)}{file.description.length > 100 ? '...' : ''}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div ref={contentRef} className="message-text">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {text}
          </ReactMarkdown>
        </div>
        {isCollapsible && shouldShowToggle && (
          <button 
            className="expand-toggle" 
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? "Show less" : "Show more"}
          >
            {isExpanded ? '▲ Show less' : '▼ Show more'}
          </button>
        )}
      </div>
    </div>
  );
});

ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;

