import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ToolActivityItem.css';

const ToolActivityItem = React.memo(({ kind, text }) => {
  const getKindClass = () => {
    switch (kind) {
      case 'tool_use':
        return 'activity-tool-use';
      case 'tool_result':
        return 'activity-tool-result';
      case 'thought':
        return 'activity-thought';
      default:
        return 'activity-default';
    }
  };

  const getKindPrefix = () => {
    switch (kind) {
      case 'tool_use':
        return '[Tool]';
      case 'tool_result':
        return '[Result]';
      case 'thought':
        return '[Thinking] 💭';
      default:
        return kind;
    }
  };

  return (
    <div className={`tool-activity-item ${getKindClass()}`}>
      <span className="activity-prefix">{getKindPrefix()}</span>
      <div className="activity-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {text}
        </ReactMarkdown>
      </div>
    </div>
  );
});

ToolActivityItem.displayName = 'ToolActivityItem';

export default ToolActivityItem;

