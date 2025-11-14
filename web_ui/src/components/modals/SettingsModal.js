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
  Select,
  MenuItem,
  FormControl,
} from '@mui/material';
import {
  Close as CloseIcon,
  Notifications as NotificationsIcon,
  Palette as PaletteIcon,
  VolumeUp as VolumeUpIcon,
  Storage as StorageIcon,
  Security as SecurityIcon,
  Check as CheckIcon,
  Mic as MicIcon,
  RecordVoiceOver as RecordVoiceOverIcon,
} from '@mui/icons-material';
import { useSettings } from '../../hooks';
import { getAvailableThemes } from '../../styles/themes';

/**
 * Settings modal - app configuration and preferences
 * @param {boolean} isOpen - Whether modal is open
 * @param {function} onClose - Callback to close modal
 * @param {function} onThemeChange - Callback when theme changes
 */
function SettingsModal({ isOpen, onClose, onThemeChange }) {
  const [currentTab, setCurrentTab] = useState(0);
  const { settings, updateSetting } = useSettings();
  const availableThemes = getAvailableThemes();

  const handleSettingChange = (setting) => {
    const newValue = !settings[setting];
    updateSetting(setting, newValue);
    
    // Request notification permission if enabling notifications
    if (setting === 'notifications' && newValue) {
      requestNotificationPermission();
    }
  };

  const handleThemeChange = (themeName) => {
    updateSetting('theme', themeName);
    if (onThemeChange) {
      onThemeChange(themeName);
    }
  };

  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
      alert('Your browser does not support notifications');
      return;
    }

    if (Notification.permission !== 'granted') {
      await Notification.requestPermission();
    }
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
        <Box component="span" sx={{ fontWeight: 600, fontSize: '1.25rem' }}>
          Settings
        </Box>
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
                  secondaryTypographyProps={{ component: 'div' }}
                />
                {settings.notifications && (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={(e) => {
                      e.stopPropagation();
                      if ('Notification' in window) {
                        Notification.requestPermission().then(permission => {
                          if (permission === 'granted') {
                            new Notification('Sparky Studio', {
                              body: 'Notifications are working! 🎉',
                              icon: '/robot-logo.svg',
                            });
                          }
                        });
                      } else {
                        alert('Your browser does not support notifications');
                      }
                    }}
                    sx={{ minWidth: 'auto', px: 1, py: 0.5, fontSize: '0.75rem', mr: 1 }}
                  >
                    Test
                  </Button>
                )}
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
                  <VolumeUpIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Sound Effects"
                  secondary="Play sounds for messages and notifications"
                  secondaryTypographyProps={{ component: 'div' }}
                />
                {settings.soundEffects && (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={(e) => {
                      e.stopPropagation();
                      // Test sound using Web Audio API directly
                      try {
                        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                        const oscillator = audioContext.createOscillator();
                        const gainNode = audioContext.createGain();
                        oscillator.connect(gainNode);
                        gainNode.connect(audioContext.destination);
                        oscillator.frequency.value = 440;
                        oscillator.type = 'sine';
                        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
                        oscillator.start(audioContext.currentTime);
                        oscillator.stop(audioContext.currentTime + 0.2);
                      } catch (error) {
                        console.error('Error playing test sound:', error);
                      }
                    }}
                    sx={{ minWidth: 'auto', px: 1, py: 0.5, fontSize: '0.75rem', mr: 1 }}
                  >
                    Test
                  </Button>
                )}
                <Switch
                  checked={settings.soundEffects}
                  onChange={() => handleSettingChange('soundEffects')}
                />
              </ListItem>
            </List>

            <Divider sx={{ my: 2 }} />

            <Typography variant="h6" sx={{ mb: 2, mt: 2, fontWeight: 600 }}>
              Voice & Speech
            </Typography>

            <List>
              <ListItem>
                <ListItemIcon>
                  <RecordVoiceOverIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Auto-speak Responses"
                  secondary="Automatically read assistant responses aloud"
                />
                <Switch
                  checked={settings.speechEnabled}
                  onChange={() => handleSettingChange('speechEnabled')}
                />
              </ListItem>

              <Divider />

              <ListItem>
                <ListItemIcon>
                  <MicIcon sx={{ color: 'primary.main' }} />
                </ListItemIcon>
                <ListItemText
                  primary="Speech Language"
                  secondary={
                    <Box sx={{ mt: 1 }}>
                      <FormControl size="small" sx={{ minWidth: 200 }}>
                        <Select
                          value={settings.speechLanguage}
                          onChange={(e) => {
                            e.stopPropagation();
                            updateSetting('speechLanguage', e.target.value);
                          }}
                          sx={{
                            bgcolor: 'rgba(255, 255, 255, 0.05)',
                            '& .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255, 255, 255, 0.1)',
                            },
                          }}
                        >
                          <MenuItem value="en-US">English (US)</MenuItem>
                          <MenuItem value="en-GB">English (UK)</MenuItem>
                          <MenuItem value="es-ES">Spanish</MenuItem>
                          <MenuItem value="fr-FR">French</MenuItem>
                          <MenuItem value="de-DE">German</MenuItem>
                          <MenuItem value="it-IT">Italian</MenuItem>
                          <MenuItem value="pt-BR">Portuguese (Brazil)</MenuItem>
                          <MenuItem value="ja-JP">Japanese</MenuItem>
                          <MenuItem value="ko-KR">Korean</MenuItem>
                          <MenuItem value="zh-CN">Chinese (Simplified)</MenuItem>
                        </Select>
                      </FormControl>
                    </Box>
                  }
                  secondaryTypographyProps={{ component: 'div' }}
                />
              </ListItem>

              {settings.speechEnabled && (
                <>
                  <Divider />
                  <Box sx={{ p: 2, bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2, m: 2 }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                      🎤 Voice conversation enabled!
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.85rem' }}>
                      • Click the microphone icon to speak your message
                      <br />
                      • Assistant responses will be read aloud automatically
                      <br />
                      • Works best in Chrome, Edge, and Safari
                    </Typography>
                  </Box>
                </>
              )}
            </List>
          </Box>
        )}

        {/* Appearance Tab */}
        {currentTab === 1 && (
          <Box>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              Appearance
            </Typography>

            <Box sx={{ p: 2 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                🎨 Choose your theme color
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, 1fr)',
                  gap: 2,
                }}
              >
                {availableThemes.map((theme) => (
                  <Box
                    key={theme.name}
                    onClick={() => handleThemeChange(theme.name)}
                    sx={{
                      position: 'relative',
                      height: 80,
                      borderRadius: 2,
                      background: `linear-gradient(135deg, ${theme.color} 0%, ${theme.color}dd 100%)`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      border: settings.theme === theme.name ? `3px solid ${theme.color}` : '1px solid rgba(255, 255, 255, 0.1)',
                      transition: 'all 0.2s',
                      '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: `0 8px 16px ${theme.color}40`,
                      },
                    }}
                  >
                    {settings.theme === theme.name && (
                      <CheckIcon 
                        sx={{ 
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          color: 'white',
                          bgcolor: 'rgba(0, 0, 0, 0.3)',
                          borderRadius: '50%',
                          p: 0.5,
                        }} 
                      />
                    )}
                    <Typography variant="body1" sx={{ fontWeight: 600, color: 'white' }}>
                      {theme.label}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
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

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
            Settings are saved automatically
          </Typography>
          <Typography 
            variant="caption" 
            sx={{ 
              color: 'text.secondary',
              opacity: 0.5,
              fontSize: '0.7rem',
              fontFamily: 'monospace',
              cursor: 'pointer',
              '&:hover': { opacity: 1 },
            }}
            onClick={() => {
              if (window.location.pathname !== '/admin') {
                window.location.href = '/admin';
              }
            }}
          >
            Ctrl+Shift+A
          </Typography>
        </Box>
        <Button onClick={onClose} variant="contained">
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default SettingsModal;

