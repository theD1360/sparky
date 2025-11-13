import React, { useEffect, useRef } from 'react';
import './AutocompleteDropdown.css';

const AutocompleteDropdown = React.memo(({ items, selectedIndex, onSelect, onClose, type, position }) => {
  const dropdownRef = useRef(null);

  useEffect(() => {
    // Scroll selected item into view
    if (dropdownRef.current && selectedIndex >= 0) {
      const selectedElement = dropdownRef.current.children[selectedIndex];
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  if (!items || items.length === 0) {
    return null;
  }

  const getItemLabel = (item) => {
    if (type === 'prompt') {
      return `/${item.name}`;
    } else if (type === 'resource') {
      return `@${item.uri}`;
    }
    return item.name || item.uri;
  };

  const getItemDescription = (item) => {
    return item.description || '';
  };

  return (
    <div 
      className="autocomplete-dropdown" 
      ref={dropdownRef}
      style={{
        bottom: position?.showAbove ? `${position.bottom}px` : 'auto',
        top: position?.showAbove ? 'auto' : '100%',
        left: '0',
        right: '0',
      }}
    >
      {items.map((item, index) => (
        <div
          key={index}
          className={`autocomplete-item ${index === selectedIndex ? 'selected' : ''}`}
          onClick={() => onSelect(item)}
          onMouseEnter={() => {}}
        >
          <div className="autocomplete-item-label">
            {getItemLabel(item)}
          </div>
          <div className="autocomplete-item-description">
            {getItemDescription(item)}
          </div>
        </div>
      ))}
    </div>
  );
});

AutocompleteDropdown.displayName = 'AutocompleteDropdown';

export default AutocompleteDropdown;

