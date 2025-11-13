# Sparky Studio Web UI Documentation

Welcome to the Sparky Studio web UI documentation! This directory contains all the documentation you need to understand and work with the frontend codebase.

## 📚 Documentation Index

### Getting Started

1. **[QUICK_REFERENCE.md](./QUICK_REFERENCE.md)** - Start here!
   - Quick lookup for common patterns
   - Import examples
   - Component templates
   - Common utilities
   - Debugging tips

### Architecture & Design

2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Complete architecture guide
   - Project structure deep dive
   - Architecture principles
   - Component guidelines
   - State management
   - Testing strategy
   - Performance optimization
   - Accessibility

### Recent Changes

3. **[REORGANIZATION_SUMMARY.md](./REORGANIZATION_SUMMARY.md)** - Recent refactoring
   - What changed and why
   - Migration guide
   - Benefits of new structure
   - File organization details

## 🚀 Quick Links

### Most Common Tasks

- **Add a new component**: See [ARCHITECTURE.md#adding-new-features](./ARCHITECTURE.md#adding-new-features)
- **Make an API call**: See [QUICK_REFERENCE.md#adding-a-new-api-call](./QUICK_REFERENCE.md#adding-a-new-api-call)
- **Use utilities**: See [QUICK_REFERENCE.md#common-utilities](./QUICK_REFERENCE.md#common-utilities)
- **Import patterns**: See [QUICK_REFERENCE.md#common-import-patterns](./QUICK_REFERENCE.md#common-import-patterns)

## 📁 Project Structure

```
web_ui/src/
├── components/          # Reusable UI components
│   ├── chat/           # Chat-specific components
│   ├── activity/       # Tool activity components
│   ├── modals/         # Modal dialogs
│   └── common/         # Shared components
├── pages/              # Page-level components
├── services/           # API & external services
├── hooks/              # Custom React hooks (future)
├── utils/              # Helper functions
├── styles/             # Theme & global styles
└── App.js              # Main application
```

## 🎯 Key Concepts

### Component Organization
Components are organized by feature/domain for better maintainability and scalability.

### Barrel Exports
Each directory has an `index.js` file that exports all its contents for clean imports:
```javascript
// Instead of:
import ChatMessage from './components/chat/ChatMessage';

// Use:
import { ChatMessage } from './components/chat';
```

### Service Layer
All API calls go through the `services/` directory, keeping components clean and focused on UI.

### Utilities
Common helper functions live in `utils/` and are pure, testable functions.

## 🛠️ Development Workflow

1. **Start dev server**: `npm start`
2. **Make changes**: Edit files, live reload will update
3. **Check linting**: `npm run lint`
4. **Run tests**: `npm test`
5. **Build for production**: `npm run build`

## 📖 Coding Standards

- **Components**: PascalCase (`ChatMessage.js`)
- **Files**: Match component name
- **Functions**: camelCase (`getUserId`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_FILE_SIZE`)
- **Indentation**: 2 spaces
- **Quotes**: Single quotes
- **Semicolons**: Required

## 🧪 Testing

```javascript
// Component test example
import { render, screen } from '@testing-library/react';
import { ChatMessage } from './ChatMessage';

test('renders message', () => {
  render(<ChatMessage text="Hello" role="user" />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});
```

## 🎨 Styling

- Use MUI's `sx` prop for component styles
- Global theme in `styles/theme.js`
- Component-specific CSS files when needed

## 🔍 Common Patterns

### Data Fetching
```javascript
import { fetchUserChats } from './services';

const loadData = async () => {
  try {
    const data = await fetchUserChats(userId);
    setState(data);
  } catch (error) {
    console.error(error);
  }
};
```

### File Upload
```javascript
import { uploadFile } from './services';

const result = await uploadFile(file, sessionId, chatId, userId);
```

### Utilities
```javascript
import { getUserId, formatDate, copyToClipboard } from './utils';

const userId = getUserId();
const formatted = formatDate(new Date());
await copyToClipboard('Text');
```

## 🐛 Troubleshooting

### Import errors?
- Check file has moved to new location
- Use barrel exports: `import { X } from './components/chat'`

### Lint errors?
- Run `npm run lint`
- Fix formatting issues
- Check for missing dependencies in `useEffect`

### Component not rendering?
- Check React DevTools
- Log props/state
- Verify imports are correct

## 📚 External Resources

- [React Documentation](https://react.dev/)
- [Material-UI](https://mui.com/)
- [React Router](https://reactrouter.com/)
- [Testing Library](https://testing-library.com/)

## 🤝 Contributing

1. Follow the architecture guidelines
2. Write tests for new features
3. Document complex logic
4. Use consistent code style
5. Add JSDoc comments for services/utils

## 📞 Need Help?

1. Check **QUICK_REFERENCE.md** for common patterns
2. Review **ARCHITECTURE.md** for detailed explanations
3. Look at existing code for examples
4. Ask the team in discussions

## 🎓 Learning Path

**New to the project?**
1. Read **QUICK_REFERENCE.md** (15 min)
2. Skim **ARCHITECTURE.md** (30 min)
3. Review existing components (30 min)
4. Try adding a simple component (1 hour)

**Want to contribute?**
1. Understand the architecture
2. Follow the coding standards
3. Write tests
4. Document your changes

## 📝 Document Updates

These docs should be updated when:
- New patterns emerge
- Architecture changes
- New best practices adopted
- Common issues discovered

---

**Last Updated**: November 2025  
**Version**: 1.0.0  
**Maintained by**: BadRobot Team

