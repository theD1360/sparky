import React, { useState, useEffect, useCallback } from 'react';
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
  LinearProgress,
  Chip,
  CircularProgress,
  TextField,
  Stack,
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
  Download as DownloadIcon,
  Delete as DeleteIcon,
  CheckCircle as CheckCircleIcon,
  Extension as ExtensionIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { useSettings } from '../../hooks';
import { getAvailableThemes } from '../../styles/themes';
import * as tts from '@diffusionstudio/vits-web';
import { useAuth } from '../auth/AuthProvider';
import {
  fetchUserMcpServers,
  createUserMcpServer,
  updateUserMcpServer,
  deleteUserMcpServer,
  reloadUserMcp,
} from '../../services/api';

/**
 * Settings modal - app configuration and preferences
 * @param {boolean} isOpen - Whether modal is open
 * @param {function} onClose - Callback to close modal
 * @param {function} onThemeChange - Callback when theme changes
 */
function SettingsModal({ isOpen, onClose, onThemeChange }) {
  const [currentTab, setCurrentTab] = useState(0);
  const { settings, updateSetting, updateSettings } = useSettings();
  const availableThemes = getAvailableThemes();
  const { user } = useAuth();

  // Voice management state
  const [availableVoices, setAvailableVoices] = useState({});
  const [storedVoices, setStoredVoices] = useState([]);
  const [downloadingVoice, setDownloadingVoice] = useState(null);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [voicesLoading, setVoicesLoading] = useState(true);

  // User MCP extras
  const [systemMcp, setSystemMcp] = useState([]);
  const [extraMcp, setExtraMcp] = useState([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [mcpSaving, setMcpSaving] = useState(false);
  const [mcpForm, setMcpForm] = useState({
    name: '',
    url: '',
    transport: 'streamable_http',
    bearerToken: '',
    description: '',
  });
  const [editingMcpName, setEditingMcpName] = useState(null);

  const loadUserMcp = useCallback(async () => {
    if (!user?.id) return;
    setMcpLoading(true);
    try {
      const data = await fetchUserMcpServers(user.id);
      setSystemMcp(data.system || []);
      setExtraMcp(data.extra || []);
    } catch (error) {
      console.error('Failed to load MCP servers:', error);
      alert(error.message || 'Failed to load MCP servers');
    } finally {
      setMcpLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (isOpen && currentTab === 2 && user?.id) {
      loadUserMcp();
    }
  }, [isOpen, currentTab, user?.id, loadUserMcp]);

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

  // Download a voice
  const handleDownloadVoice = useCallback(async (voiceId) => {
    try {
      setDownloadingVoice(voiceId);
      setDownloadProgress(0);

      console.log(`Starting download of voice: ${voiceId}`);
      
      await tts.download(voiceId, (progress) => {
        const percent = Math.round((progress.loaded * 100) / progress.total);
        setDownloadProgress(percent);
        console.log(`Downloading ${voiceId}: ${percent}%`);
      });

      console.log(`Voice ${voiceId} downloaded successfully`);

      // Update stored voices
      const stored = await tts.stored();
      setStoredVoices(stored);
      updateSetting('ttsDownloadedVoices', stored);
      
      // Set as default voice if this is the first voice
      if (stored.length === 1) {
        updateSetting('ttsVoiceId', voiceId);
      }

      setDownloadingVoice(null);
      setDownloadProgress(0);
    } catch (error) {
      console.error('Error downloading voice:', error);
      console.error('Error details:', error.message, error.stack);
      setDownloadingVoice(null);
      alert(`Failed to download voice: ${error.message}`);
    }
  }, [updateSetting]);

  // Load available and stored voices
  useEffect(() => {
    const loadVoices = async () => {
      try {
        setVoicesLoading(true);
        
        // Get available voices - returns an array of voice objects
        const voicesArray = await tts.voices();
        console.log('Available voices:', voicesArray);
        
        // Convert array to object for easier lookup: { voiceId: voiceMetadata }
        const voicesObj = {};
        if (Array.isArray(voicesArray)) {
          voicesArray.forEach(voice => {
            if (voice && voice.key) {
              voicesObj[voice.key] = voice;
            }
          });
        }
        
        console.log('Converted voices object:', voicesObj);
        setAvailableVoices(voicesObj);
        
        // Get stored (downloaded) voices
        const stored = await tts.stored();
        console.log('Stored voices:', stored);
        setStoredVoices(stored);
        
        // If no voices are downloaded, download the default voice automatically
        if (stored.length === 0) {
          console.log('No voices downloaded, downloading default voice...');
          const defaultVoiceId = settings.ttsVoiceId || 'en_US-hfc_female-medium';
          
          // Check if default voice exists in available voices
          if (voicesObj[defaultVoiceId]) {
            try {
              await handleDownloadVoice(defaultVoiceId);
            } catch (error) {
              console.error('Error auto-downloading default voice:', error);
            }
          } else {
            console.warn(`Default voice ${defaultVoiceId} not found in available voices`);
          }
        }
        
        // Update settings with stored voices
        updateSetting('ttsDownloadedVoices', stored);
        
        setVoicesLoading(false);
      } catch (error) {
        console.error('Error loading voices:', error);
        console.error('Error details:', error.message, error.stack);
        setVoicesLoading(false);
      }
    };

    if (isOpen) {
      loadVoices();
    }
  }, [isOpen, handleDownloadVoice, settings.ttsVoiceId, updateSetting]);

  // Remove a voice
  const handleRemoveVoice = async (voiceId) => {
    if (!window.confirm(`Remove voice "${voiceId}"? You can re-download it later.`)) {
      return;
    }

    try {
      await tts.remove(voiceId);
      
      // Update stored voices
      const stored = await tts.stored();
      setStoredVoices(stored);
      updateSetting('ttsDownloadedVoices', stored);

      // If this was the selected voice, switch to default
      if (settings.ttsVoiceId === voiceId && stored.length > 0) {
        updateSetting('ttsVoiceId', stored[0]);
      }
    } catch (error) {
      console.error('Error removing voice:', error);
      alert(`Failed to remove voice: ${error.message}`);
    }
  };

  // Get voice display name
  const getVoiceDisplayName = (voiceId) => {
    // Try to get name from voice metadata first
    if (availableVoices[voiceId] && availableVoices[voiceId].name) {
      return availableVoices[voiceId].name;
    }
    
    // Fallback: Format: en_US-hfc_female-medium -> English (US) - Female - Medium
    const parts = voiceId.split('-');
    if (parts.length < 2) return voiceId;

    const [locale, ...rest] = parts;
    const [lang, country] = locale.split('_');
    const quality = rest[rest.length - 1];
    const voiceType = rest.slice(0, -1).join(' ');

    const langNames = {
      en: 'English',
      es: 'Spanish',
      fr: 'French',
      de: 'German',
      it: 'Italian',
      pt: 'Portuguese',
      ja: 'Japanese',
      ko: 'Korean',
      zh: 'Chinese',
      ru: 'Russian',
      nl: 'Dutch',
      pl: 'Polish',
      tr: 'Turkish',
      sv: 'Swedish',
      da: 'Danish',
      no: 'Norwegian',
      fi: 'Finnish',
    };

    const langName = langNames[lang] || lang.toUpperCase();
    const countryName = country ? ` (${country})` : '';
    
    return `${langName}${countryName} - ${voiceType.charAt(0).toUpperCase() + voiceType.slice(1)} - ${quality.charAt(0).toUpperCase() + quality.slice(1)}`;
  };

  // Group voices by language
  const getVoicesByLanguage = () => {
    const grouped = {};
    
    Object.keys(availableVoices).forEach(voiceId => {
      const lang = voiceId.split('_')[0] || 'other';
      if (!grouped[lang]) {
        grouped[lang] = [];
      }
      grouped[lang].push(voiceId);
    });
    
    return grouped;
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
          <Tab label="Tools" />
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
                  secondary="Automatically read assistant responses aloud using VITS TTS"
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

              <Divider />

              {/* TTS Voice Selection */}
              <ListItem sx={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', mb: 1 }}>
                  <ListItemIcon>
                    <VolumeUpIcon sx={{ color: 'primary.main' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="TTS Voice"
                    secondary="Select and download voices for text-to-speech"
                  />
                </Box>

                {voicesLoading ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 7 }}>
                    <CircularProgress size={16} />
                    <Typography variant="caption" color="text.secondary">
                      Loading available voices...
                    </Typography>
                  </Box>
                ) : (
                  <Box sx={{ width: '100%', pl: 7 }}>
                    {/* Current Voice Selection */}
                    {storedVoices.length > 0 ? (
                      <FormControl size="small" fullWidth sx={{ mb: 2 }}>
                        <Select
                          value={settings.ttsVoiceId || storedVoices[0] || 'en_US-hfc_female-medium'}
                          onChange={(e) => {
                            updateSetting('ttsVoiceId', e.target.value);
                          }}
                          sx={{
                            bgcolor: 'rgba(255, 255, 255, 0.05)',
                            '& .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255, 255, 255, 0.1)',
                            },
                          }}
                        >
                          {storedVoices.map((voiceId) => (
                            <MenuItem key={voiceId} value={voiceId}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <CheckCircleIcon fontSize="small" sx={{ color: 'success.main' }} />
                                {getVoiceDisplayName(voiceId)}
                              </Box>
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : (
                      <Box sx={{ 
                        mb: 2, 
                        p: 2, 
                        bgcolor: 'rgba(59, 130, 246, 0.1)', 
                        borderRadius: 2,
                        border: '1px solid rgba(59, 130, 246, 0.3)',
                      }}>
                        <Typography variant="body2" sx={{ color: 'primary.main' }}>
                          No voices downloaded yet. Download a voice below to enable TTS.
                        </Typography>
                      </Box>
                    )}

                    {/* Download More Voices */}
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
                      {Object.keys(availableVoices).length > 0 
                        ? `Available voices (${storedVoices.length}/${Object.keys(availableVoices).length} downloaded):`
                        : 'Loading available voices...'
                      }
                    </Typography>

                    <Box sx={{ maxHeight: 200, overflowY: 'auto', pr: 1 }}>
                      {Object.keys(availableVoices).length > 0 ? (
                        // Show first 30 voices, prioritizing English voices
                        Object.keys(availableVoices)
                          .sort((a, b) => {
                            // Prioritize English voices
                            const aIsEn = a.startsWith('en_');
                            const bIsEn = b.startsWith('en_');
                            if (aIsEn && !bIsEn) return -1;
                            if (!aIsEn && bIsEn) return 1;
                            return a.localeCompare(b);
                          })
                          .slice(0, 30)
                          .map((voiceId) => {
                            const isDownloaded = storedVoices.includes(voiceId);
                            const isDownloading = downloadingVoice === voiceId;
                            const voiceData = availableVoices[voiceId];

                            return (
                              <Box
                                key={voiceId}
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  py: 0.5,
                                  borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                                }}
                              >
                                <Box sx={{ flex: 1 }}>
                                  <Typography variant="caption" sx={{ fontSize: '0.75rem', display: 'block' }}>
                                    {getVoiceDisplayName(voiceId)}
                                  </Typography>
                                  {voiceData && (
                                    <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                                      {voiceId}
                                    </Typography>
                                  )}
                                </Box>
                                
                                {isDownloading ? (
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 100 }}>
                                    <LinearProgress 
                                      variant="determinate" 
                                      value={downloadProgress} 
                                      sx={{ flex: 1, height: 4, borderRadius: 2 }}
                                    />
                                    <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                                      {downloadProgress}%
                                    </Typography>
                                  </Box>
                                ) : isDownloaded ? (
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <Chip 
                                      label="Downloaded" 
                                      size="small" 
                                      color="success"
                                      sx={{ fontSize: '0.7rem', height: 20 }}
                                    />
                                    <IconButton
                                      size="small"
                                      onClick={() => handleRemoveVoice(voiceId)}
                                      sx={{ p: 0.5 }}
                                    >
                                      <DeleteIcon fontSize="small" />
                                    </IconButton>
                                  </Box>
                                ) : (
                                  <IconButton
                                    size="small"
                                    onClick={() => handleDownloadVoice(voiceId)}
                                    sx={{ p: 0.5 }}
                                    title="Download voice"
                                  >
                                    <DownloadIcon fontSize="small" />
                                  </IconButton>
                                )}
                              </Box>
                            );
                          })
                      ) : (
                        <Box sx={{ 
                          p: 2, 
                          textAlign: 'center',
                          color: 'text.secondary',
                        }}>
                          <Typography variant="caption">
                            No voices available. Please check your internet connection.
                          </Typography>
                        </Box>
                      )}
                    </Box>

                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
                      Voice models are ~10-50MB each and stored locally in your browser
                    </Typography>
                  </Box>
                )}
              </ListItem>

              {settings.speechEnabled && (
                <>
                  <Divider />
                  <Box sx={{ p: 2, bgcolor: 'rgba(59, 130, 246, 0.1)', borderRadius: 2, m: 2 }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                      🎤 Advanced voice features enabled!
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.85rem' }}>
                      • High-quality VITS TTS (offline capable)
                      <br />
                      • Whisper STT for accurate transcription
                      <br />
                      • Click microphone icon to speak your message
                      <br />
                      • Responses will be read aloud automatically
                      <br />
                      • Works in all modern browsers
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

        {/* Tools Tab — system MCP read-only + personal remote extras */}
        {currentTab === 2 && (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Tools & MCP
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={loadUserMcp}
                  disabled={mcpLoading || !user?.id}
                >
                  Refresh
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  disabled={mcpSaving || !user?.id}
                  onClick={async () => {
                    if (!user?.id) return;
                    setMcpSaving(true);
                    try {
                      await reloadUserMcp(user.id);
                      await loadUserMcp();
                    } catch (error) {
                      alert(error.message || 'Failed to reload tools');
                    } finally {
                      setMcpSaving(false);
                    }
                  }}
                >
                  Reload tools
                </Button>
              </Stack>
            </Box>

            {!user?.id ? (
              <Typography color="text.secondary">Sign in to manage MCP servers.</Typography>
            ) : mcpLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={32} />
              </Box>
            ) : (
              <>
                <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
                  System servers (always available)
                </Typography>
                <List dense sx={{ mb: 3, bgcolor: 'rgba(255,255,255,0.02)', borderRadius: 1 }}>
                  {systemMcp.length === 0 && (
                    <ListItem>
                      <ListItemText primary="No system servers configured" />
                    </ListItem>
                  )}
                  {systemMcp.map((server) => (
                    <ListItem key={server.name} divider>
                      <ListItemIcon>
                        <ExtensionIcon color="primary" />
                      </ListItemIcon>
                      <ListItemText
                        primary={server.name}
                        secondary={
                          server.description ||
                          (server.transport === 'stdio' ? 'Built-in stdio server' : server.url || 'Remote')
                        }
                      />
                      <Chip size="small" label="Always on" color="success" variant="outlined" />
                    </ListItem>
                  ))}
                </List>

                <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
                  Your remote MCP servers
                </Typography>
                <List dense sx={{ mb: 2, bgcolor: 'rgba(255,255,255,0.02)', borderRadius: 1 }}>
                  {extraMcp.length === 0 && (
                    <ListItem>
                      <ListItemText
                        primary="No personal servers yet"
                        secondary="Add a remote HTTP/SSE MCP server below"
                      />
                    </ListItem>
                  )}
                  {extraMcp.map((server) => (
                    <ListItem
                      key={server.name}
                      divider
                      secondaryAction={
                        <Stack direction="row" spacing={0.5}>
                          <IconButton
                            edge="end"
                            size="small"
                            onClick={() => {
                              setEditingMcpName(server.name);
                              setMcpForm({
                                name: server.name,
                                url: server.url || '',
                                transport: server.transport || server.type || 'streamable_http',
                                bearerToken: server.bearerToken || '',
                                description: server.description || '',
                              });
                            }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <IconButton
                            edge="end"
                            size="small"
                            color="error"
                            onClick={async () => {
                              if (!window.confirm(`Remove MCP server "${server.name}"?`)) return;
                              setMcpSaving(true);
                              try {
                                await deleteUserMcpServer(user.id, server.name);
                                if (editingMcpName === server.name) {
                                  setEditingMcpName(null);
                                  setMcpForm({
                                    name: '',
                                    url: '',
                                    transport: 'streamable_http',
                                    bearerToken: '',
                                    description: '',
                                  });
                                }
                                await loadUserMcp();
                              } catch (error) {
                                alert(error.message || 'Failed to delete server');
                              } finally {
                                setMcpSaving(false);
                              }
                            }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Stack>
                      }
                    >
                      <ListItemIcon>
                        <ExtensionIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary={server.name}
                        secondary={server.description || server.url}
                        sx={{ pr: 8 }}
                      />
                    </ListItem>
                  ))}
                </List>

                <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                  {editingMcpName ? `Edit ${editingMcpName}` : 'Add remote MCP server'}
                </Typography>
                <Stack spacing={1.5}>
                  <TextField
                    label="Name"
                    size="small"
                    fullWidth
                    disabled={Boolean(editingMcpName)}
                    value={mcpForm.name}
                    onChange={(e) => setMcpForm({ ...mcpForm, name: e.target.value })}
                  />
                  <TextField
                    label="URL"
                    size="small"
                    fullWidth
                    required
                    value={mcpForm.url}
                    onChange={(e) => setMcpForm({ ...mcpForm, url: e.target.value })}
                    placeholder="https://example.com/mcp"
                  />
                  <FormControl size="small" fullWidth>
                    <Select
                      value={mcpForm.transport}
                      onChange={(e) => setMcpForm({ ...mcpForm, transport: e.target.value })}
                      displayEmpty
                    >
                      <MenuItem value="streamable_http">streamable_http</MenuItem>
                      <MenuItem value="sse">sse</MenuItem>
                      <MenuItem value="http">http</MenuItem>
                    </Select>
                  </FormControl>
                  <TextField
                    label="Bearer token (optional)"
                    size="small"
                    fullWidth
                    type="password"
                    value={mcpForm.bearerToken}
                    onChange={(e) => setMcpForm({ ...mcpForm, bearerToken: e.target.value })}
                  />
                  <TextField
                    label="Description (optional)"
                    size="small"
                    fullWidth
                    value={mcpForm.description}
                    onChange={(e) => setMcpForm({ ...mcpForm, description: e.target.value })}
                  />
                  <Stack direction="row" spacing={1}>
                    <Button
                      variant="contained"
                      startIcon={editingMcpName ? <CheckIcon /> : <AddIcon />}
                      disabled={mcpSaving || !mcpForm.url.trim() || (!editingMcpName && !mcpForm.name.trim())}
                      onClick={async () => {
                        setMcpSaving(true);
                        try {
                          const payload = {
                            url: mcpForm.url.trim(),
                            transport: mcpForm.transport,
                            bearerToken: mcpForm.bearerToken || undefined,
                            description: mcpForm.description || undefined,
                          };
                          if (editingMcpName) {
                            await updateUserMcpServer(user.id, editingMcpName, payload);
                          } else {
                            await createUserMcpServer(user.id, {
                              name: mcpForm.name.trim(),
                              ...payload,
                            });
                          }
                          setEditingMcpName(null);
                          setMcpForm({
                            name: '',
                            url: '',
                            transport: 'streamable_http',
                            bearerToken: '',
                            description: '',
                          });
                          await loadUserMcp();
                        } catch (error) {
                          alert(error.message || 'Failed to save MCP server');
                        } finally {
                          setMcpSaving(false);
                        }
                      }}
                    >
                      {editingMcpName ? 'Save' : 'Add server'}
                    </Button>
                    {editingMcpName && (
                      <Button
                        onClick={() => {
                          setEditingMcpName(null);
                          setMcpForm({
                            name: '',
                            url: '',
                            transport: 'streamable_http',
                            bearerToken: '',
                            description: '',
                          });
                        }}
                      >
                        Cancel
                      </Button>
                    )}
                  </Stack>
                </Stack>
              </>
            )}
          </Box>
        )}

        {/* Privacy Tab */}
        {currentTab === 3 && (
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

