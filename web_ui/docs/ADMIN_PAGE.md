# Admin Dashboard

## Overview

The Admin Dashboard is a hidden administrative interface for managing MCP servers, environment variables, and monitoring system health.

## Access

### Hidden Access Methods

1. **Keyboard Shortcut**: `Ctrl+Shift+A` (from anywhere in the app)
2. **Settings Modal**: Click the tiny "Ctrl+Shift+A" text at bottom
3. **Direct URL**: Navigate to `/admin`

**Note**: This is intentionally hidden from normal UI - no visible links in navigation.

## Features

### 1. MCP Servers Tab 🔧

**Display:**
- Server name
- Status (active/expired)
- Age (how long cached)
- TTL (time-to-live in minutes)
- Load count (number of times loaded)

**Actions:**
- **Refresh Status** - Reload cache status from backend
- **Reload Server** - Force reload a specific server
- **Stop Server** - Stop a running server (placeholder)

**Use Cases:**
- Monitor which servers are cached vs expired
- See cache age distribution
- Force reload a problematic server
- Verify staggered TTL is working

### 2. Environment Variables Tab ⚙️

**Features:**
- View all environment variables
- Edit variable values (runtime only)
- Add new variables
- Delete variables

**Variables Include:**
- `AGENT_MODEL` - LLM model name
- `SPARKY_ENABLE_AGENT_LOOP` - Enable background tasks
- `SPARKY_TOOL_CACHE_TTL` - Cache duration
- And more...

**Important Notes:**
- Changes are **runtime-only**
- Won't persist across server restarts
- Requires backend API implementation (currently placeholder)

### 3. System Info Tab 📊

**Metrics (Planned):**
- Memory usage
- Disk storage
- Server uptime
- Active sessions
- Python version
- FastAPI version
- Database status

**Current Status:** Placeholder UI ready for backend integration

### 4. Cache Management Tab 💾

**Display:**
- Cache initialization status
- Total servers cached
- Expired server count
- Full JSON cache status

**Features:**
- Real-time cache status from `/api/admin/tool_cache_status`
- Detailed view of cache internals
- Useful for debugging cache issues

## UI Design

### Layout
```
┌─────────────────────────────────────────┐
│  🔧 Admin Dashboard        [Back to Home]│
├─────────────────────────────────────────┤
│ ⚠️ Administrator Access Warning          │
├─────────────────────────────────────────┤
│ [MCP Servers] [Env Vars] [System] [Cache]│
├─────────────────────────────────────────┤
│                                          │
│  [Tab Content]                           │
│                                          │
└─────────────────────────────────────────┘
```

### Color Coding
- 🟢 **Active/Success** - Green chips
- 🟡 **Warning/Expired** - Yellow chips
- 🔴 **Error/Stopped** - Red chips
- 🔵 **Info** - Blue highlights

## Backend Integration

### Existing APIs

1. **Tool Cache Status**
   ```
   GET /api/admin/tool_cache_status
   ```
   Returns cache status for all MCP servers.

### Needed APIs (Placeholders)

2. **Reload Server**
   ```
   POST /api/admin/servers/{server_name}/reload
   ```
   Force reload a specific MCP server.

3. **Environment Variables**
   ```
   GET /api/admin/env
   POST /api/admin/env
   PUT /api/admin/env/{key}
   DELETE /api/admin/env/{key}
   ```
   Manage environment variables.

4. **System Info**
   ```
   GET /api/admin/system
   ```
   Get system metrics and information.

## Security Considerations

### Current Implementation
- ⚠️ **No authentication** - Anyone with URL can access
- ⚠️ **Hidden but not secure** - Relies on obscurity

### Recommended Future Additions

1. **Authentication**
   - Admin password/token
   - Session-based auth
   - Role-based access control

2. **Rate Limiting**
   - Limit API calls
   - Prevent abuse

3. **Audit Logging**
   - Log all admin actions
   - Track who changed what

4. **Read-Only Mode**
   - View-only for non-admins
   - Require elevated permissions for changes

## Usage Examples

### Monitoring Cache Health

1. Navigate to `/admin`
2. Click "MCP Servers" tab
3. Check server ages and TTLs
4. Verify staggered expiration working

### Forcing Server Reload

1. Find problematic server in table
2. Click refresh icon
3. Wait for reload
4. Verify status updated

### Viewing Cache Details

1. Click "Cache Management" tab
2. View JSON dump of cache state
3. Check for issues or anomalies

### Editing Environment Variables

1. Click "Environment Variables" tab
2. Find variable to edit
3. Click edit icon
4. Change value
5. Press Enter to save

## Development

### Adding New Features

**Add new metric:**
1. Add to System Info tab
2. Fetch from backend API
3. Display in grid card

**Add new server action:**
1. Add button to MCP Servers table
2. Create backend API endpoint
3. Call API on button click
4. Refresh status

### Testing

```javascript
// Manual test
1. Press Ctrl+Shift+A → should navigate to /admin
2. Click each tab → should show content
3. Click "Back to Home" → should return to /
```

## Troubleshooting

### Can't access admin page

**Solution**: Use keyboard shortcut `Ctrl+Shift+A` or navigate to `/admin`

### No servers showing

**Solution**: Connect to chat first to initialize toolchain cache

### Cache status shows empty

**Solution**: Backend not running or API endpoint failing

## Future Enhancements

1. **Real-time Updates**
   - WebSocket for live cache updates
   - Auto-refresh cache status

2. **Server Logs**
   - View MCP server logs
   - Filter and search logs

3. **Performance Metrics**
   - Request latency
   - Cache hit/miss rates
   - Tool usage statistics

4. **Configuration Management**
   - Edit MCP config files
   - Validate configurations
   - Apply changes without restart

5. **Database Management**
   - View database stats
   - Run maintenance tasks
   - Backup/restore

6. **User Management**
   - View active users
   - Session management
   - Usage quotas

## Files

### Created
- `src/pages/Admin.js` - Main admin component
- `docs/ADMIN_PAGE.md` - This documentation

### Modified
- `src/pages/index.js` - Export Admin
- `src/index.js` - Add /admin route
- `src/App.js` - Add Ctrl+Shift+A shortcut
- `src/components/modals/SettingsModal.js` - Add hidden access link
- `src/components/modals/HelpModal.js` - Document shortcut

## Summary

✅ **Hidden Admin Page** - Accessible via Ctrl+Shift+A or /admin  
✅ **MCP Server Management** - View status, reload servers  
✅ **Environment Variables** - Edit runtime configuration  
✅ **System Monitoring** - View system metrics (wireframe)  
✅ **Cache Management** - Detailed cache status view  
✅ **Professional UI** - Material-UI components, responsive  
✅ **Ready for Backend** - API integration points defined  

The admin dashboard is wireframed and ready for full backend integration! 🔒

