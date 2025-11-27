import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ToolMessage.css';

const ToolMessage = React.memo(({ toolName, args = {}, result = '', status = 'success', toolData }) => {
  const [paramsExpanded, setParamsExpanded] = useState(true);
  const [resultExpanded, setResultExpanded] = useState(false);
  const [messagesExpanded, setMessagesExpanded] = useState(false);
  const [shouldShowResultToggle, setShouldShowResultToggle] = useState(false);
  const resultRef = useRef(null);

  // Extract structured data from toolData
  // Parse the result to extract just the "result" field from the JSON
  let resultContent = null;
  try {
    // Try to parse the result as JSON
    const parsedResult = typeof result === 'string' ? JSON.parse(result) : result;
    if (typeof parsedResult === 'object' && parsedResult !== null) {
      // Extract just the "result" field if it exists, otherwise use the whole object
      resultContent = parsedResult.result !== undefined ? parsedResult.result : parsedResult;
    } else {
      resultContent = result;
    }
  } catch {
    // If parsing fails, check for result_content field or use result as-is
    resultContent = toolData?.result?.result_content || toolData?.result_content || result;
  }
  
  // Get content_type from toolData
  const contentType = toolData?.result?.content_type || toolData?.content_type || null;
  
  const messages = toolData?.result?.messages || toolData?.messages || null;
  const statusInfo = toolData?.result?.status || status;

  // Auto-collapse parameters after 1 second
  useEffect(() => {
    const timer = setTimeout(() => {
      setParamsExpanded(false);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  // Check if result content is tall enough to need collapsing
  useEffect(() => {
    if (resultRef.current) {
      const height = resultRef.current.scrollHeight;
      setShouldShowResultToggle(height > 100);
    }
  }, [resultContent]);

  const statusClass = statusInfo === 'error' ? 'tool-status-error' : 'tool-status-success';
  const statusText = statusInfo === 'error' ? 'error' : 'success';
  
  // Format result content for display with code block if content_type is available
  const formatResultContent = (content, type) => {
    if (content === null || content === undefined) return 'No result';
    
    // If we have a content type, wrap in markdown code block
    if (type) {
      if (typeof content === 'object') {
        content = JSON.stringify(content, null, 2);
      }
      const contentStr = String(content);
      // Use the type as the language identifier (ReactMarkdown will render it as a code block)
      // For text/plaintext, still use "text" as language to ensure code block rendering
      const lang = (type === 'plaintext') ? 'text' : type;
      return `\`\`\`${lang}\n${contentStr}\n\`\`\``;
    }
    
    // Otherwise format normally (but still wrap in code block for consistency)
    if (typeof content === 'string') {
      return `\`\`\`text\n${content}\n\`\`\``;
    }
    if (typeof content === 'object') {
      return `\`\`\`json\n${JSON.stringify(content, null, 2)}\n\`\`\``;
    }
    return `\`\`\`text\n${String(content)}\n\`\`\``;
  };

  return (
    <div className="chat-message message-tool">
      <div className="message-content tool-message-content">
        {/* Tool name as title */}
        <div className="tool-message-header">
          <span className="tool-name">{toolName}</span>
        </div>

        {/* Parameters section - auto-collapses after 1 second */}
        <div className="tool-params-section">
          <button
            className="tool-params-toggle"
            onClick={() => setParamsExpanded(!paramsExpanded)}
            aria-label={paramsExpanded ? "Hide parameters" : "Show parameters"}
          >
            <span className="tool-params-label">Parameters</span>
            <span className="tool-params-icon">{paramsExpanded ? '▼' : '▶'}</span>
          </button>
          {paramsExpanded && (
            <div className="tool-params-content">
              <pre className="tool-params-json">
                {JSON.stringify(args, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Results section - collapsible markdown */}
        <div className="tool-result-section">
          <div 
            ref={resultRef}
            className={`tool-result-content ${!resultExpanded && shouldShowResultToggle ? 'tool-result-collapsed' : ''}`}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {formatResultContent(resultContent, contentType)}
            </ReactMarkdown>
          </div>
          {shouldShowResultToggle && (
            <button 
              className="tool-result-toggle" 
              onClick={() => setResultExpanded(!resultExpanded)}
              aria-label={resultExpanded ? "Show less" : "Show more"}
            >
              {resultExpanded ? '▲ Show less' : '▼ Show more'}
            </button>
          )}
        </div>

        {/* Messages section - if available */}
        {messages && messages.length > 0 && (
          <div className="tool-messages-section">
            <button
              className="tool-messages-toggle"
              onClick={() => setMessagesExpanded(!messagesExpanded)}
              aria-label={messagesExpanded ? "Hide messages" : "Show messages"}
            >
              <span className="tool-messages-label">Messages ({messages.length})</span>
              <span className="tool-messages-icon">{messagesExpanded ? '▼' : '▶'}</span>
            </button>
            {messagesExpanded && (
              <div className="tool-messages-content">
                {messages.map((msg, index) => (
                  <div key={index} className="tool-message-item">
                    {typeof msg === 'string' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg}</ReactMarkdown>
                    ) : (
                      <pre className="tool-message-json">
                        {JSON.stringify(msg, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Status tag - bottom right */}
        <div className={`tool-status-tag ${statusClass}`}>
          {statusText}
        </div>
      </div>
    </div>
  );
});

ToolMessage.displayName = 'ToolMessage';

export default ToolMessage;

