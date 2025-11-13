import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Switch,
  Divider,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Close as CloseIcon,
  Notifications as NotificationsIcon,
  Palette as PaletteIcon,
  Language as LanguageIcon,
  Storage as StorageIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';

/**
 * Settings modal - app configuration and preferences
 * @param {boolean} isOpen - Whether modal is open
 * @param {function} onClose - Callback to close modal
 */
function SettingsModal({ isOpen, onClose }) {
  const [currentTab, setCurrentTab] = useState(0);
  const [settings, setSettings] = useState({
    notifications: true,
    soundEffects: false,
    darkMode: true,
    autoSave: true,
    analytics: false,
  });

  const handleSettingChange = (setting) => {
    setSettings({
      ...settings,
      [setting]: !settings[setting],
    });
  };

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
  };

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#111827',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 3,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Settings
        </Typography>
        <IconButton onClick={onClose} size="small" sx={{ color: 'text.secondary' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
        <Tabs value={currentTab} onChange={handleTabChange}>
          <Tab label="General" />
          <Tab label="Appearance" />
          <Tab label="Privacy" />
        </Tabs>
      </Box>

      <DialogContent sx={{ minHeight: 400 }}>
        {/* General Tab */}
        {currentTab === 0 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              General Settings
            </Typography>

            <List>
              <ListItem>
                <ListItemIcon>
                  <NotificationsIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Enable Notifications"
                  secondary="Receive notifications for new messages and updates"
                />
                <Switch
                  checked={settings.notifications}
                  onChange={() => handleSettingChange('notifications')}
                />
              </ListItem>

              <Divider />

              <ListItem>
                <ListItemIcon>
                  <StorageIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Auto-save Chats"
                  secondary="Automatically save chat history"
                />
                <Switch
                  checked={settings.autoSave}
                  onChange={() => handleSettingChange('autoSave')}
                />
              </ListItem>

              <Divider />

              <ListItem>
                <ListItemIcon>
                  <LanguageIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Sound Effects"
                  secondary="Play sounds for messages and notifications"
                />
                <Switch
                  checked={settings.soundEffects}
                  onChange={() => handleSettingChange('soundEffects')}
                />
              </ListItem>
            </List>
          </Box>
        )}

        {/* Appearance Tab */}
        {currentTab === 1 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              Appearance
            </Typography>

            <List>
              <ListItem>
                <ListItemIcon>
                  <PaletteIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Dark Mode"
                  secondary="Use dark theme throughout the app"
                />
                <Switch
                  checked={settings.darkMode}
                  onChange={() => handleSettingChange('darkMode')}
                  disabled
                />
              </ListItem>

              <Divider />

              <Box sx={{ p: 2 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                  🎨 More theme customization options coming soon!
                </Typography>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))',
                    gap: 1,
                  }}
                >
                  {['Blue', 'Purple', 'Green', 'Orange'].map((color) => (
                    <Box
                      key={color}
                      sx={{
                        height: 60,
                        borderRadius: 2,
                        bgcolor: `${color.toLowerCase()}.500`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        opacity: 0.5,
                        cursor: 'not-allowed',
                      }}
                    >
                      <Typography variant="caption">{color}</Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            </List>
          </Box>
        )}

        {/* Privacy Tab */}
        {currentTab === 2 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              Privacy & Security
            </Typography>

            <List>
              <ListItem>
                <ListItemIcon>
                  <SecurityIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Usage Analytics"
                  secondary="Help improve Sparky by sharing anonymous usage data"
                />
                <Switch
                  checked={settings.analytics}
                  onChange={() => handleSettingChange('analytics')}
                />
              </ListItem>

              <Divider />

              <Box sx={{ p: 2 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                  🔒 Your privacy matters
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  • All chats are encrypted
                  <br />
                  • Data stored locally and on secure servers
                  <br />
                  • You control your data
                  <br />• No third-party tracking
                </Typography>
              </Box>
            </List>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3, gap: 1 }}>
        <Button onClick={onClose} variant="outlined" sx={{ flex: 1 }}>
          Cancel
        </Button>
        <Button onClick={onClose} variant="contained" sx={{ flex: 1 }}>
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default SettingsModal;

