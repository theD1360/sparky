import React from 'react';
import './HelpModal.css';

function HelpModal({ isOpen, onClose, resources, prompts, toolUses, toolResults }) {
  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    if (e.target.className === 'help-modal-backdrop') {
      onClose();
    }
  };

  return (
    <div className="help-modal-backdrop" onClick={handleBackdropClick}>
      <div className="help-modal">
        <div className="help-modal-header">
          <h2>Sparky Help</h2>
          <button className="help-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="help-modal-content">
          <section className="help-section">
            <h3>Keyboard Shortcuts</h3>
            <ul>
              <li><kbd>Ctrl+S</kbd> or <kbd>Enter</kbd> - Send message</li>
              <li><kbd>Ctrl+H</kbd> - Show this help</li>
              <li><kbd>Ctrl+Shift+A</kbd> - Admin dashboard</li>
              <li><kbd>Escape</kbd> - Close modal/dropdown</li>
              <li><kbd>↑/↓</kbd> - Navigate autocomplete</li>
            </ul>
          </section>

          <section className="help-section">
            <h3>Slash Commands</h3>
            <p>Type <code>/</code> to see available prompts:</p>
            {prompts && prompts.length > 0 ? (
              <ul>
                {prompts.slice(0, 5).map((prompt, index) => (
                  <li key={index}>
                    <strong>/{prompt.name}</strong> - {prompt.description}
                  </li>
                ))}
                {prompts.length > 5 && <li><em>...and {prompts.length - 5} more</em></li>}
              </ul>
            ) : (
              <p className="help-empty">No prompts available</p>
            )}
          </section>

          <section className="help-section">
            <h3>Resources (@-mentions)</h3>
            <p>Type <code>@</code> to reference resources:</p>
            {resources && resources.length > 0 ? (
              <ul>
                {resources.slice(0, 5).map((resource, index) => (
                  <li key={index}>
                    <strong>@{resource.uri}</strong> - {resource.description}
                  </li>
                ))}
                {resources.length > 5 && <li><em>...and {resources.length - 5} more</em></li>}
              </ul>
            ) : (
              <p className="help-empty">No resources available</p>
            )}
          </section>

          <section className="help-section">
            <h3>Recent Tool Activity</h3>
            {toolUses && toolUses.length > 0 ? (
              <ul>
                {toolUses.slice(-5).reverse().map((toolUse, index) => (
                  <li key={index}>
                    <strong>{toolUse.name}</strong>
                    {toolUse.args && <span className="help-args"> - {JSON.stringify(toolUse.args).substring(0, 50)}...</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="help-empty">No tool activity yet</p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default HelpModal;

