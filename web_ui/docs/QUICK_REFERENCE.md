# Web UI Quick Reference

## Project Structure at a Glance

```
src/
├── components/     # Reusable UI pieces
├── pages/          # Full page components  
├── services/       # API & external calls
├── hooks/          # Custom React hooks
├── utils/          # Helper functions
├── styles/         # Theme & global styles
└── App.js          # Main app logic
```

## Common Import Patterns

```javascript
// Components
import { ChatMessage, AutocompleteDropdown } from './components/chat';
import { ToolActivityItem } from './components/activity';
import { HelpModal } from './components/modals';
import { SplashScreen } from './components/common';

// Pages
import { Home } from './pages';

// Services  
import { fetchUserChats, uploadFile, archiveChat } from './services';

// Utils
import { getUserId, generateUUID, formatDate, copyToClipboard } from './utils';

// Styles
import { theme } from './styles/theme';
```

## Quick Commands

```bash
# Start development server
npm start

# Run tests
npm test

# Build for production
npm run build

# Run linter
npm run lint

# Format code (if configured)
npm run format
```

## Component Template

```javascript
import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import './MyComponent.css';

function MyComponent({ title, onAction }) {
  const [state, setState] = useState(null);
  
  useEffect(() => {
    // Side effects
  }, []);
  
  const handleClick = () => {
    onAction?.();
  };
  
  return (
    <div className="my-component">
      <h2>{title}</h2>
      <button onClick={handleClick}>Action</button>
    </div>
  );
}

MyComponent.propTypes = {
  title: PropTypes.string.isRequired,
  onAction: PropTypes.func,
};

export default MyComponent;
```

## Adding a New Component

1. **Create file**: `src/components/[category]/NewComponent.js`
2. **Export**: Add to `src/components/[category]/index.js`
3. **Use**: `import { NewComponent } from './components/[category]'`

## Adding a New API Call

1. **Add function** to `src/services/api.js`:
```javascript
export const myNewApi = async (params) => {
  const response = await fetch('/api/endpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return await response.json();
};
```

2. **Use in component**:
```javascript
import { myNewApi } from './services';

const result = await myNewApi({ data: 'value' });
```

## Common Utilities

```javascript
// Generate UUID
const id = generateUUID();

// Get/create user ID
const userId = getUserId();

// Format date
const formatted = formatDate(new Date());
const relative = getRelativeTime(new Date());

// Format file size
const size = formatFileSize(1024000); // "1 MB"

// Truncate text
const short = truncateText("Long text...", 20);

// Copy to clipboard
const success = await copyToClipboard("Text to copy");

// Debounce function
const debouncedFn = debounce(myFunction, 500);
```

## MUI Theme Access

```javascript
import { useTheme } from '@mui/material/styles';

function MyComponent() {
  const theme = useTheme();
  
  return (
    <Box sx={{ 
      color: theme.palette.primary.main,
      bgcolor: theme.palette.background.paper,
    }}>
      Content
    </Box>
  );
}
```

## Responsive Design

```javascript
import { useMediaQuery, useTheme } from '@mui/material';

function MyComponent() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isSmallMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  return (
    <Box>
      {isMobile ? <MobileView /> : <DesktopView />}
    </Box>
  );
}
```

## Common Patterns

### Async Data Loading

```javascript
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  const loadData = async () => {
    try {
      setLoading(true);
      const result = await fetchData();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  loadData();
}, []);
```

### Form Handling

```javascript
const [formData, setFormData] = useState({ name: '', email: '' });

const handleChange = (event) => {
  setFormData({
    ...formData,
    [event.target.name]: event.target.value
  });
};

const handleSubmit = async (event) => {
  event.preventDefault();
  await submitForm(formData);
};
```

### File Upload

```javascript
import { uploadFile } from './services';

const handleFileChange = async (event) => {
  const file = event.target.files[0];
  if (file) {
    try {
      const result = await uploadFile(file, sessionId, chatId, userId);
      console.log('Uploaded:', result.file_id);
    } catch (error) {
      console.error('Upload failed:', error);
    }
  }
};
```

## Debugging Tips

```javascript
// React DevTools
// Install: React Developer Tools browser extension

// Log render count
const renderCount = useRef(0);
useEffect(() => {
  renderCount.current++;
  console.log(`Rendered ${renderCount.current} times`);
});

// Debug props/state
useEffect(() => {
  console.log('Props:', props);
  console.log('State:', state);
}, [props, state]);
```

## Common Issues

### Import Errors

❌ **Wrong:**
```javascript
import ChatMessage from './ChatMessage';  // Old path
```

✅ **Correct:**
```javascript
import { ChatMessage } from './components/chat';  // New organized path
```

### Missing Dependencies

❌ **Wrong:**
```javascript
useEffect(() => {
  fetchData(userId);
}, []);  // Missing userId dependency
```

✅ **Correct:**
```javascript
useEffect(() => {
  fetchData(userId);
}, [userId]);  // Include all dependencies
```

### Async in useEffect

❌ **Wrong:**
```javascript
useEffect(async () => {
  await fetchData();  // Can't make useEffect async
}, []);
```

✅ **Correct:**
```javascript
useEffect(() => {
  const loadData = async () => {
    await fetchData();
  };
  loadData();
}, []);
```

## Need Help?

- 📖 [Full Architecture Docs](./ARCHITECTURE.md)
- 📚 [React Docs](https://react.dev/)
- 🎨 [MUI Docs](https://mui.com/)
- 🔀 [React Router Docs](https://reactrouter.com/)

