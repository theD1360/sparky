import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  TextField,
  Chip,
  Divider,
  Tabs,
  Tab,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Edit as EditIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/auth/AuthProvider';

function Admin() {
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  const [currentTab, setCurrentTab] = useState(0);
  const [mcpServers, setMcpServers] = useState([]);
  const [envVars, setEnvVars] = useState([]);
  const [systemInfo, setSystemInfo] = useState(null);
  const [cacheStatus, setCacheStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [envLoading, setEnvLoading] = useState(false);
  const [systemLoading, setSystemLoading] = useState(false);
  const [editingVar, setEditingVar] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [showAddVar, setShowAddVar] = useState(false);
  const [newVarKey, setNewVarKey] = useState('');
  const [newVarValue, setNewVarValue] = useState('');
  
  // User management state
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showUserDialog, setShowUserDialog] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [userForm, setUserForm] = useState({
    username: '',
    email: '',
    password: '',
    is_active: true,
    is_verified: false,
    roles: ['user'],
  });

  // Load data on mount
  useEffect(() => {
    loadToolCacheStatus();
    loadEnvVars();
    loadSystemInfo();
    if (currentTab === 4) {
      loadUsers();
    }
  }, [currentTab]);
  
  // Load users when tab is selected
  const loadUsers = async () => {
    try {
      setUsersLoading(true);
      const response = await fetch('/api/admin/users', {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (error) {
      console.error('Error loading users:', error);
    } finally {
      setUsersLoading(false);
    }
  };
  
  const handleCreateUser = () => {
    setEditingUser(null);
    setUserForm({
      username: '',
      email: '',
      password: '',
      is_active: true,
      is_verified: false,
      roles: ['user'],
    });
    setShowUserDialog(true);
  };
  
  const handleEditUser = (user) => {
    setEditingUser(user);
    setUserForm({
      username: user.username,
      email: user.email,
      password: '',
      is_active: user.is_active,
      is_verified: user.is_verified,
      roles: user.roles || [],
    });
    setShowUserDialog(true);
  };
  
  const handleSaveUser = async () => {
    try {
      const url = editingUser 
        ? `/api/admin/users/${editingUser.id}`
        : '/api/admin/users';
      const method = editingUser ? 'PUT' : 'POST';
      
      const body = { ...userForm };
      if (!body.password && editingUser) {
        delete body.password; // Don't update password if empty
      }
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify(body),
      });
      
      if (response.ok) {
        setShowUserDialog(false);
        loadUsers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to save user'}`);
      }
    } catch (error) {
      console.error('Error saving user:', error);
      alert('Failed to save user');
    }
  };
  
  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Are you sure you want to delete this user?')) {
      return;
    }
    
    try {
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      
      if (response.ok) {
        loadUsers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to delete user'}`);
      }
    } catch (error) {
      console.error('Error deleting user:', error);
      alert('Failed to delete user');
    }
  };
  
  const handleAssignRole = async (userId, role) => {
    try {
      const response = await fetch(`/api/admin/users/${userId}/roles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ role }),
      });
      
      if (response.ok) {
        loadUsers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to assign role'}`);
      }
    } catch (error) {
      console.error('Error assigning role:', error);
      alert('Failed to assign role');
    }
  };
  
  const handleRemoveRole = async (userId, role) => {
    try {
      const response = await fetch(`/api/admin/users/${userId}/roles/${role}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      
      if (response.ok) {
        loadUsers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to remove role'}`);
      }
    } catch (error) {
      console.error('Error removing role:', error);
      alert('Failed to remove role');
    }
  };

  const loadToolCacheStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/tool_cache_status');
      const data = await response.json();
      setCacheStatus(data);
      
      // Transform cache data into server list
      if (data.servers) {
        const servers = Object.entries(data.servers).map(([name, info]) => ({
          name,
          ...info,
          status: info.expired ? 'expired' : 'active',
        }));
        setMcpServers(servers);
      }
    } catch (error) {
      console.error('Error loading cache status:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadEnvVars = async () => {
    try {
      setEnvLoading(true);
      const url = '/api/admin/env';
      console.log('Fetching env vars from:', url);
      console.log('Full URL would be:', window.location.origin + url);
      const response = await fetch(url);
      console.log('Env vars response status:', response.status);
      console.log('Env vars response URL:', response.url);
      console.log('Env vars response headers:', response.headers.get('content-type'));
      
      const responseText = await response.text();
      console.log('Env vars response body (first 200 chars):', responseText.substring(0, 200));
      
      if (!response.ok) {
        console.error('Env vars API error:', response.status, responseText);
        throw new Error(`API returned ${response.status}`);
      }
      
      const data = JSON.parse(responseText);
      setEnvVars(data);
      console.log('Environment variables loaded:', data);
    } catch (error) {
      console.error('Error loading env vars:', error);
      alert(`Failed to load environment variables: ${error.message}`);
    } finally {
      setEnvLoading(false);
    }
  };

  const loadSystemInfo = async () => {
    try {
      setSystemLoading(true);
      console.log('Fetching system info from /api/admin/system...');
      const response = await fetch('/api/admin/system');
      console.log('System info response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('System info API error:', response.status, errorText);
        throw new Error(`API returned ${response.status}: ${errorText}`);
      }
      
      const data = await response.json();
      setSystemInfo(data);
      console.log('System info loaded:', data);
    } catch (error) {
      console.error('Error loading system info:', error);
      alert(`Failed to load system info: ${error.message}`);
    } finally {
      setSystemLoading(false);
    }
  };

  const handleRefreshServer = async (serverName) => {
    try {
      const response = await fetch(`/api/admin/servers/${serverName}/reload`, {
        method: 'POST',
      });
      const data = await response.json();
      
      if (data.success) {
        console.log('Server reloaded:', serverName);
        // Reload cache status
        await loadToolCacheStatus();
      } else {
        console.error('Failed to reload server:', data.message);
        alert(`Failed to reload server: ${data.message}`);
      }
    } catch (error) {
      console.error('Error reloading server:', error);
      alert(`Error reloading server: ${error.message}`);
    }
  };

  const handleUpdateEnvVar = async (key, value) => {
    try {
      const response = await fetch(`/api/admin/env/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      });
      const data = await response.json();
      
      if (data.success) {
        console.log('Env var updated:', key, '=', value);
        await loadEnvVars(); // Reload to show updated value
      } else {
        alert(`Failed to update: ${data.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating env var:', error);
      alert(`Error updating variable: ${error.message}`);
    }
  };


  const formatAge = (ageMinutes) => {
    if (ageMinutes < 1) return '< 1 min';
    if (ageMinutes < 60) return `${Math.round(ageMinutes)} min`;
    const hours = Math.floor(ageMinutes / 60);
    const mins = Math.round(ageMinutes % 60);
    return `${hours}h ${mins}m`;
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', py: 4 }}>
      <Container maxWidth="xl">
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
              🔧 Admin Dashboard
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Manage MCP servers, environment variables, and system settings
            </Typography>
          </Box>
          <Button
            variant="outlined"
            onClick={() => navigate('/')}
            sx={{ borderColor: 'text.secondary', color: 'text.secondary' }}
          >
            ← Back to Home
          </Button>
        </Box>

        {/* Warning Banner */}
        <Alert severity="warning" sx={{ mb: 3 }}>
          <strong>⚠️ Administrator Access</strong> - Changes here can affect system behavior. Proceed with caution.
        </Alert>

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs value={currentTab} onChange={(e, v) => setCurrentTab(v)}>
            <Tab label="MCP Servers" />
            <Tab label="Environment Variables" />
            <Tab label="System Info" />
            <Tab label="Cache Management" />
            <Tab label="Users" />
          </Tabs>
        </Paper>

        {/* MCP Servers Tab */}
        {currentTab === 0 && (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                MCP Tool Servers
              </Typography>
              <Button
                startIcon={<RefreshIcon />}
                onClick={loadToolCacheStatus}
                disabled={loading}
              >
                Refresh Status
              </Button>
            </Box>

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : (
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell><strong>Server Name</strong></TableCell>
                      <TableCell><strong>Status</strong></TableCell>
                      <TableCell><strong>Age</strong></TableCell>
                      <TableCell><strong>TTL</strong></TableCell>
                      <TableCell><strong>Load Count</strong></TableCell>
                      <TableCell align="right"><strong>Actions</strong></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {mcpServers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} align="center">
                          <Typography variant="body2" sx={{ color: 'text.secondary', py: 2 }}>
                            No MCP servers loaded. Connect to chat to initialize servers.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      mcpServers.map((server) => (
                        <TableRow key={server.name}>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {server.name}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={server.status}
                              size="small"
                              color={server.expired ? 'warning' : 'success'}
                              sx={{ textTransform: 'capitalize' }}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {formatAge(server.age_minutes)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {server.ttl_minutes} min
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {server.load_count}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Tooltip title="Reload Server">
                              <IconButton
                                size="small"
                                onClick={() => handleRefreshServer(server.name)}
                                sx={{ color: 'primary.main' }}
                              >
                                <RefreshIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* MCP Server Info Card */}
            <Card sx={{ mt: 3, bgcolor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  📘 MCP Server Management
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                  • MCP servers are loaded lazily when the first client connects
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                  • Each server has a unique TTL to prevent simultaneous reloads
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                  • Expired servers are automatically reloaded on next connection
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  • Use Refresh to force reload a specific server
                </Typography>
              </CardContent>
            </Card>
          </Box>
        )}

        {/* Environment Variables Tab */}
        {currentTab === 1 && (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Environment Variables
              </Typography>
              <Button
                startIcon={<AddIcon />}
                onClick={() => setShowAddVar(true)}
                variant="contained"
              >
                Add Variable
              </Button>
            </Box>

            <Alert severity="info" sx={{ mb: 2 }}>
              Environment variables are loaded from .env files and system environment. Changes here are runtime-only and won't persist on restart.
            </Alert>

            {envLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : (
              <Paper>
                <List>
                  {envVars.length === 0 ? (
                    <ListItem>
                      <ListItemText
                        primary="No environment variables loaded"
                        secondary="Check backend connection"
                      />
                    </ListItem>
                  ) : (
                    envVars.map((envVar, index) => (
                  <React.Fragment key={envVar.key}>
                    {index > 0 && <Divider />}
                    <ListItem>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                              {envVar.key}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                              {envVar.description}
                            </Typography>
                            {editingVar === envVar.key ? (
                              <TextField
                                size="small"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleUpdateEnvVar(envVar.key, editValue);
                                    setEditingVar(null);
                                  } else if (e.key === 'Escape') {
                                    setEditingVar(null);
                                  }
                                }}
                                autoFocus
                                sx={{ fontFamily: 'monospace' }}
                              />
                            ) : (
                              <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'primary.main' }}>
                                {envVar.value}
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        {editingVar === envVar.key ? (
                          <Box>
                            <IconButton
                              size="small"
                              onClick={() => {
                                handleUpdateEnvVar(envVar.key, editValue);
                                setEditingVar(null);
                              }}
                              sx={{ color: 'success.main' }}
                            >
                              <CheckIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                              size="small"
                              onClick={() => setEditingVar(null)}
                              sx={{ color: 'text.secondary' }}
                            >
                              <CloseIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        ) : (
                          <IconButton
                            size="small"
                            onClick={() => {
                              setEditingVar(envVar.key);
                              setEditValue(envVar.value);
                            }}
                            sx={{ color: 'text.secondary' }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        )}
                      </ListItemSecondaryAction>
                    </ListItem>
                  </React.Fragment>
                )))}
                </List>
              </Paper>
            )}

            {/* Add Variable Dialog */}
            <Dialog
              open={showAddVar}
              onClose={() => {
                setShowAddVar(false);
                setNewVarKey('');
                setNewVarValue('');
              }}
              maxWidth="sm"
              fullWidth
            >
              <DialogTitle>Add Environment Variable</DialogTitle>
              <DialogContent>
                <TextField
                  label="Variable Name"
                  value={newVarKey}
                  onChange={(e) => setNewVarKey(e.target.value)}
                  fullWidth
                  margin="normal"
                  placeholder="VARIABLE_NAME"
                  sx={{ fontFamily: 'monospace' }}
                />
                <TextField
                  label="Value"
                  value={newVarValue}
                  onChange={(e) => setNewVarValue(e.target.value)}
                  fullWidth
                  margin="normal"
                  multiline
                  rows={3}
                  placeholder="value"
                />
              </DialogContent>
              <DialogActions>
                <Button onClick={() => {
                  setShowAddVar(false);
                  setNewVarKey('');
                  setNewVarValue('');
                }}>
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  onClick={() => {
                    console.log('Add env var:', newVarKey, '=', newVarValue);
                    setShowAddVar(false);
                    setNewVarKey('');
                    setNewVarValue('');
                  }}
                  disabled={!newVarKey || !newVarValue}
                >
                  Add Variable
                </Button>
              </DialogActions>
            </Dialog>
          </Box>
        )}

        {/* System Info Tab */}
        {currentTab === 2 && (
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              System Information
            </Typography>

            {systemLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : systemInfo ? (
              <Grid container spacing={3}>
                {/* Memory Usage */}
                <Grid item xs={12} md={6} lg={3}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <MemoryIcon sx={{ color: 'primary.main' }} />
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                          Memory
                        </Typography>
                      </Box>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main' }}>
                        {systemInfo.memory_percent.toFixed(1)}%
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {systemInfo.memory_used_mb.toFixed(0)} / {systemInfo.memory_total_mb.toFixed(0)} MB
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Disk Storage */}
                <Grid item xs={12} md={6} lg={3}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <StorageIcon sx={{ color: 'success.main' }} />
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                          Storage
                        </Typography>
                      </Box>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'success.main' }}>
                        {systemInfo.disk_percent.toFixed(1)}%
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {systemInfo.disk_used_gb.toFixed(1)} / {systemInfo.disk_total_gb.toFixed(1)} GB
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Uptime */}
                <Grid item xs={12} md={6} lg={3}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <SpeedIcon sx={{ color: 'warning.main' }} />
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                          Uptime
                        </Typography>
                      </Box>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'warning.main' }}>
                        {Math.floor(systemInfo.uptime_seconds / 3600)}h
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {Math.floor((systemInfo.uptime_seconds % 3600) / 60)} minutes
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Active Sessions */}
                <Grid item xs={12} md={6} lg={3}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <SettingsIcon sx={{ color: 'info.main' }} />
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                          Sessions
                        </Typography>
                      </Box>
                      <Typography variant="h4" sx={{ fontWeight: 700, color: 'info.main' }}>
                        {systemInfo.active_sessions}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {systemInfo.total_connections} active connections
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            ) : (
              <Alert severity="info">Loading system information...</Alert>
            )}

            {/* System Details */}
            {systemInfo && (
              <Card sx={{ mt: 3 }}>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                    System Details
                  </Typography>
                  <List dense>
                    <ListItem>
                      <ListItemText
                        primary="Python Version"
                        secondary={systemInfo.python_version}
                      />
                    </ListItem>
                    <Divider />
                    <ListItem>
                      <ListItemText
                        primary="Platform"
                        secondary={systemInfo.platform}
                      />
                    </ListItem>
                    <Divider />
                    <ListItem>
                      <ListItemText
                        primary="Server Uptime"
                        secondary={`${Math.floor(systemInfo.uptime_seconds / 3600)} hours ${Math.floor((systemInfo.uptime_seconds % 3600) / 60)} minutes`}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            )}
          </Box>
        )}

        {/* Cache Management Tab */}
        {currentTab === 3 && (
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              Tool Chain Cache Status
            </Typography>

            {cacheStatus ? (
              <>
                <Grid container spacing={2} sx={{ mb: 3 }}>
                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
                          Cache Initialized
                        </Typography>
                        <Typography variant="h5" sx={{ fontWeight: 600 }}>
                          {cacheStatus.cache_initialized ? 'Yes' : 'No'}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
                          Total Servers
                        </Typography>
                        <Typography variant="h5" sx={{ fontWeight: 600 }}>
                          {cacheStatus.total_servers}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1 }}>
                          Expired Servers
                        </Typography>
                        <Typography variant="h5" sx={{ fontWeight: 600, color: 'warning.main' }}>
                          {mcpServers.filter(s => s.expired).length}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                </Grid>

                <Paper>
                  <Box sx={{ p: 2 }}>
                    <pre style={{ 
                      overflow: 'auto', 
                      fontSize: '0.85rem',
                      backgroundColor: '#0a0e1a',
                      padding: '16px',
                      borderRadius: '8px',
                    }}>
                      {JSON.stringify(cacheStatus, null, 2)}
                    </pre>
                  </Box>
                </Paper>
              </>
            ) : (
              <Alert severity="info">
                Connect to chat to initialize the tool cache.
              </Alert>
            )}
          </Box>
        )}

        {/* Users Tab */}
        {currentTab === 4 && (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                User Management
              </Typography>
              <Button
                startIcon={<AddIcon />}
                variant="contained"
                onClick={handleCreateUser}
              >
                Create User
              </Button>
            </Box>

            {usersLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : (
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell><strong>Username</strong></TableCell>
                      <TableCell><strong>Email</strong></TableCell>
                      <TableCell><strong>Roles</strong></TableCell>
                      <TableCell><strong>Status</strong></TableCell>
                      <TableCell><strong>Created</strong></TableCell>
                      <TableCell align="right"><strong>Actions</strong></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {users.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} align="center">
                          <Typography variant="body2" sx={{ color: 'text.secondary', py: 2 }}>
                            No users found.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      users.map((user) => (
                        <TableRow key={user.id}>
                          <TableCell>{user.username}</TableCell>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                              {user.roles.map((role) => (
                                <Chip
                                  key={role}
                                  label={role}
                                  size="small"
                                  color={role === 'admin' ? 'primary' : 'default'}
                                  onDelete={() => handleRemoveRole(user.id, role)}
                                />
                              ))}
                              <Chip
                                label="+"
                                size="small"
                                onClick={() => {
                                  const role = prompt('Enter role name:');
                                  if (role) handleAssignRole(user.id, role);
                                }}
                              />
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={user.is_active ? 'Active' : 'Inactive'}
                              size="small"
                              color={user.is_active ? 'success' : 'default'}
                            />
                          </TableCell>
                          <TableCell>
                            {new Date(user.created_at).toLocaleDateString()}
                          </TableCell>
                          <TableCell align="right">
                            <IconButton
                              size="small"
                              onClick={() => handleEditUser(user)}
                            >
                              <EditIcon />
                            </IconButton>
                            <IconButton
                              size="small"
                              onClick={() => handleDeleteUser(user.id)}
                              color="error"
                            >
                              <DeleteIcon />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* User Dialog */}
            <Dialog
              open={showUserDialog}
              onClose={() => setShowUserDialog(false)}
              maxWidth="sm"
              fullWidth
            >
              <DialogTitle>
                {editingUser ? 'Edit User' : 'Create User'}
              </DialogTitle>
              <DialogContent>
                <TextField
                  fullWidth
                  label="Username"
                  margin="normal"
                  value={userForm.username}
                  onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
                  required
                />
                <TextField
                  fullWidth
                  label="Email"
                  type="email"
                  margin="normal"
                  value={userForm.email}
                  onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                  required
                />
                <TextField
                  fullWidth
                  label={editingUser ? 'New Password (leave empty to keep current)' : 'Password'}
                  type="password"
                  margin="normal"
                  value={userForm.password}
                  onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                  required={!editingUser}
                />
                <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Switch
                      checked={userForm.is_active}
                      onChange={(e) => setUserForm({ ...userForm, is_active: e.target.checked })}
                    />
                    <Typography>Active</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Switch
                      checked={userForm.is_verified}
                      onChange={(e) => setUserForm({ ...userForm, is_verified: e.target.checked })}
                    />
                    <Typography>Verified</Typography>
                  </Box>
                </Box>
              </DialogContent>
              <DialogActions>
                <Button onClick={() => setShowUserDialog(false)}>Cancel</Button>
                <Button onClick={handleSaveUser} variant="contained">
                  {editingUser ? 'Update' : 'Create'}
                </Button>
              </DialogActions>
            </Dialog>
          </Box>
        )}
      </Container>
    </Box>
  );
}

export default Admin;

