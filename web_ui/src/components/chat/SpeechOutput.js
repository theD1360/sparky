import React, { useEffect, useCallback, useRef } from 'react';
import {
  IconButton,
  Tooltip,
  Box,
  Snackbar,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  VolumeUp as VolumeUpIcon,
  VolumeOff as VolumeOffIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { useVitsTTS } from '../../hooks/useVitsTTS';
import { useSettings } from '../../hooks';

/**
 * SpeechOutput Component
 * Provides text-to-speech output with playback controls
 * 
 * @param {Object} props
 * @param {boolean} props.enabled - Enable auto-speak for new messages
 * @param {string} props.textToSpeak - Text to speak (triggers speech when changed)
 * @param {Function} props.onSpeechEnd - Callback when speech ends
 * @param {Function} props.onSpeechStart - Callback when speech starts
 * @param {string} props.language - Language code for synthesis (default: 'en-US')
 * @param {number} props.rate - Speech rate 0.1-10 (default: 1)
 * @param {number} props.volume - Volume 0-1 (default: 1)
 * @param {boolean} props.showControls - Show manual control button (default: true)
 * @param {Object} props.sx - Custom styles
 */
function SpeechOutput({
  enabled = false,
  textToSpeak = '',
  onSpeechEnd,
  onSpeechStart,
  language = 'en-US',
  rate = 1,
  volume = 1,
  showControls = true,
  sx = {},
}) {
  const [showError, setShowError] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState('');
  const lastSpokenTextRef = useRef(''); // Track what we've already spoken
  const isInitialMountRef = useRef(true); // Track initial mount

  // Get voice settings
  const { settings } = useSettings();
  const voiceId = settings.ttsVoiceId || 'en_US-hfc_female-medium';

  const {
    isSpeaking,
    isSupported,
    isDownloading,
    isModelReady,
    error,
    speak,
    cancel,
  } = useVitsTTS({
    voiceId,
    onEnd: () => {
      if (onSpeechEnd) {
        onSpeechEnd();
      }
    },
    onError: (errorCode, message) => {
      setErrorMessage(message);
      setShowError(true);
    },
  });

  // Auto-speak when textToSpeak changes and enabled
  useEffect(() => {
    // Skip on initial mount
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      return;
    }

    // Only speak if enabled, has text, and it's different from last spoken
    if (enabled && textToSpeak && textToSpeak.trim() !== '' && textToSpeak !== lastSpokenTextRef.current) {
      console.log('Speaking new message:', textToSpeak.substring(0, 50));
      lastSpokenTextRef.current = textToSpeak;
      
      // Notify that speech is starting
      if (onSpeechStart) {
        onSpeechStart();
      }
      
      // Speak with VITS (no rate control needed)
      speak(textToSpeak);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textToSpeak, enabled, onSpeechStart]); // Intentionally omit 'speak' to prevent re-runs on re-render

  // Show error notification
  useEffect(() => {
    if (error) {
      setErrorMessage(error);
      setShowError(true);
    }
  }, [error]);

  const handleToggle = useCallback(() => {
    if (isSpeaking) {
      cancel();
    } else if (textToSpeak) {
      speak(textToSpeak);
    }
  }, [isSpeaking, textToSpeak, speak, cancel]);

  const handleCloseError = () => {
    setShowError(false);
  };

  // Don't render controls if not supported or controls disabled
  if (!isSupported || !showControls) {
    return null;
  }

  return (
    <Box sx={sx}>
      {/* Speaker Button */}
      <Tooltip
        title={
          isDownloading
            ? 'Downloading voice model...'
            : isSpeaking
              ? 'Stop speaking'
              : 'Speak text'
        }
      >
        <span>
          <IconButton
            onClick={handleToggle}
            size="small"
            disabled={(!textToSpeak && !isSpeaking) || isDownloading}
            sx={{
              color: isSpeaking ? 'primary.main' : 'inherit',
              animation: isSpeaking ? 'speaking 0.5s ease-in-out infinite' : 'none',
              '@keyframes speaking': {
                '0%, 100%': {
                  transform: 'scale(1)',
                },
                '50%': {
                  transform: 'scale(1.2)',
                },
              },
            }}
          >
            {isDownloading ? (
              <CircularProgress size={16} />
            ) : isSpeaking ? (
              <StopIcon fontSize="small" />
            ) : (
              <VolumeUpIcon fontSize="small" />
            )}
          </IconButton>
        </span>
      </Tooltip>

      {/* Error Notification */}
      <Snackbar
        open={showError}
        autoHideDuration={6000}
        onClose={handleCloseError}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseError} severity="error" sx={{ width: '100%' }}>
          {errorMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default SpeechOutput;

