# Web UI Architecture

## Overview

The Sparky Studio web UI follows a modular, scalable architecture with clear separation of concerns. This document describes the project structure and guidelines for development.

## Directory Structure

```
web_ui/src/
├── components/          # Reusable UI components
│   ├── chat/           # Chat-specific components
│   │   ├── ChatMessage.js
│   │   ├── ChatMessage.css
│   │   ├── AutocompleteDropdown.js
│   │   ├── AutocompleteDropdown.css
│   │   └── index.js    # Barrel export
│   ├── activity/       # Tool activity components
│   │   ├── ToolActivityItem.js
│   │   ├── ToolActivityItem.css
│   │   └── index.js
│   ├── modals/         # Modal dialog components
│   │   ├── HelpModal.js
│   │   ├── HelpModal.css
│   │   └── index.js
│   └── common/         # Common shared components
│       ├── SplashScreen.js
│       └── index.js
├── pages/              # Page-level components
│   ├── Home.js         # Landing/home page
│   └── index.js
├── services/           # API and external services
│   ├── api.js          # HTTP API calls
│   └── index.js
├── hooks/              # Custom React hooks
│   └── (future hooks)
├── utils/              # Utility functions
│   ├── helpers.js      # General helpers
│   └── index.js
├── styles/             # Theme and global styles
│   └── theme.js        # MUI theme configuration
├── App.js              # Main application component
├── App.css             # App-level styles
├── index.js            # Application entry point
└── index.css           # Global CSS
```

## Architecture Principles

### 1. Component Organization

**Components** are organized by feature/domain:
- `chat/` - Chat-related UI components
- `activity/` - Tool activity display
- `modals/` - Reusable modal dialogs
- `common/` - Shared components used across features

**Guidelines:**
- Keep components small and focused
- Co-locate component-specific styles with the component
- Use barrel exports (`index.js`) for clean imports

### 2. Pages

**Pages** are top-level route components:
- `Home.js` - Landing page (`/`)
- Chat page logic is in `App.js` (`/chat`)

**Guidelines:**
- Pages compose multiple components
- Pages handle route-level logic
- Keep pages thin - delegate to components

### 3. Services

**Services** handle external communication:
- `api.js` - All HTTP API calls to backend

**Guidelines:**
- Pure functions that return promises
- Handle errors gracefully
- Add JSDoc comments for documentation
- Never import React or hooks in services

### 4. Utilities

**Utils** provide helper functions:
- `helpers.js` - General-purpose utilities (UUID, formatting, etc.)

**Guidelines:**
- Pure, testable functions
- No side effects
- Well-documented with JSDoc

### 5. Hooks (Future)

Custom React hooks for shared stateful logic:
- Follow React hooks conventions (`use*` naming)
- Extract reusable state logic from components

### 6. Styles

**Styles** centralize theming:
- `theme.js` - MUI theme configuration

**Guidelines:**
- Use MUI's `sx` prop for component-specific styles
- Use CSS modules for complex styling needs
- Keep theme consistent across app

## Import Patterns

### Using Barrel Exports

Instead of:
```javascript
import ChatMessage from './components/chat/ChatMessage';
import AutocompleteDropdown from './components/chat/AutocompleteDropdown';
```

Use:
```javascript
import { ChatMessage, AutocompleteDropdown } from './components/chat';
```

### Service Imports

```javascript
import { fetchUserChats, uploadFile } from './services';
```

### Utility Imports

```javascript
import { getUserId, generateUUID, formatDate } from './utils';
```

## Component Guidelines

### Component Structure

```javascript
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import './ComponentName.css';

/**
 * Brief description of component
 * @param {Object} props - Component props
 */
function ComponentName({ prop1, prop2 }) {
  // State
  const [state, setState] = useState(null);
  
  // Effects
  useEffect(() => {
    // ...
  }, []);
  
  // Handlers
  const handleClick = () => {
    // ...
  };
  
  // Render
  return (
    <div className="component-name">
      {/* JSX */}
    </div>
  );
}

ComponentName.propTypes = {
  prop1: PropTypes.string.isRequired,
  prop2: PropTypes.number,
};

ComponentName.defaultProps = {
  prop2: 0,
};

export default ComponentName;
```

### Naming Conventions

- **Components**: PascalCase (e.g., `ChatMessage.js`)
- **Files**: Match component name (e.g., `ChatMessage.js`)
- **CSS**: Match component name (e.g., `ChatMessage.css`)
- **Services**: camelCase functions (e.g., `fetchUserChats`)
- **Utils**: camelCase functions (e.g., `getUserId`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_FILE_SIZE`)

## State Management

Currently using React's built-in state management:
- `useState` for local component state
- `useEffect` for side effects
- Props for parent-child communication
- Context API for global state (future)

### Future Considerations

As the app grows, consider:
- **Redux** or **Zustand** for complex global state
- **React Query** for server state management
- **Custom hooks** for reusable state logic

## API Integration

All API calls go through the `services/api.js` module:

```javascript
// In a component
import { fetchUserChats } from './services';

const MyComponent = () => {
  useEffect(() => {
    const loadChats = async () => {
      try {
        const data = await fetchUserChats(userId);
        // Handle data
      } catch (error) {
        // Handle error
      }
    };
    loadChats();
  }, [userId]);
};
```

## WebSocket Management

WebSocket logic is currently in `App.js`. Future improvement:
- Extract to `services/websocket.js`
- Create `useWebSocket` custom hook
- Centralize connection management

## Testing

### Component Tests

```javascript
// ComponentName.test.js
import { render, screen } from '@testing-library/react';
import ComponentName from './ComponentName';

test('renders component', () => {
  render(<ComponentName prop1="test" />);
  expect(screen.getByText(/test/i)).toBeInTheDocument();
});
```

### Service Tests

```javascript
// api.test.js
import { fetchUserChats } from './api';

test('fetches user chats', async () => {
  const chats = await fetchUserChats('user123');
  expect(Array.isArray(chats.chats)).toBe(true);
});
```

## Performance Optimization

### Current Optimizations

1. **React.memo** for expensive components
2. **useCallback** for memoized callbacks
3. **useMemo** for computed values
4. **Lazy loading** for routes (future)

### Best Practices

- Avoid inline object/array creation in render
- Use `key` prop correctly in lists
- Debounce expensive operations
- Virtualize long lists (future)

## Accessibility

- Use semantic HTML
- Add ARIA labels where needed
- Ensure keyboard navigation
- Maintain color contrast ratios
- Test with screen readers

## Adding New Features

### Adding a New Component

1. Create component file in appropriate directory:
   ```
   src/components/[domain]/NewComponent.js
   src/components/[domain]/NewComponent.css
   ```

2. Add to barrel export:
   ```javascript
   // src/components/[domain]/index.js
   export { default as NewComponent } from './NewComponent';
   ```

3. Import and use:
   ```javascript
   import { NewComponent } from './components/[domain]';
   ```

### Adding a New Page

1. Create page component:
   ```
   src/pages/NewPage.js
   ```

2. Add to barrel export:
   ```javascript
   // src/pages/index.js
   export { default as NewPage } from './NewPage';
   ```

3. Add route in `App.js` or `index.js`

### Adding a New Service

1. Add function to appropriate service file:
   ```javascript
   // src/services/api.js
   export const newApiCall = async (params) => {
     // Implementation
   };
   ```

2. Import and use:
   ```javascript
   import { newApiCall } from './services';
   ```

## Code Quality

### Linting

```bash
npm run lint
```

### Formatting

Follow existing code style. Key points:
- 2 spaces for indentation
- Single quotes for strings
- Semicolons required
- Trailing commas in objects/arrays

### Pre-commit Checks

- Linting passes
- Tests pass
- No console errors
- Components documented

## Migration from Old Structure

The project was recently reorganized. If you have old imports:

**Old:**
```javascript
import ChatMessage from './ChatMessage';
import { getUserId } from './App';
```

**New:**
```javascript
import { ChatMessage } from './components/chat';
import { getUserId } from './utils';
```

## Future Improvements

1. **Extract WebSocket Service**: Move WebSocket logic from `App.js` to `services/websocket.js`
2. **Custom Hooks**: Create `useChat`, `useWebSocket`, `useFileUpload` hooks
3. **State Management**: Consider Redux/Zustand for complex state
4. **Route Management**: Create dedicated `routes.js` configuration
5. **Error Boundaries**: Add error boundaries for graceful error handling
6. **Lazy Loading**: Implement code splitting for better performance
7. **Internationalization**: Add i18n support for multiple languages

## Resources

- [React Documentation](https://react.dev/)
- [Material-UI](https://mui.com/)
- [React Router](https://reactrouter.com/)
- [Project README](../README.md)

## Questions?

For questions about the architecture or how to implement features:
1. Check this documentation
2. Review existing code for patterns
3. Ask the team in discussions

