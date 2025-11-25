import React, { useState, useEffect, useMemo, memo } from 'react';
import {
  IconButton,
  Tooltip,
  Box,
  Typography,
  Collapse,
  Alert,
  Snackbar,
  CircularProgress,
  Button,
} from '@mui/material';
import {
  Mic as MicIcon,
  MicOff as MicOffIcon,
  Stop as StopIcon,
  VolumeOff as VolumeOffIcon,
} from '@mui/icons-material';
import { useWhisperSTT } from '../../hooks/useWhisperSTT';
import { useSettings } from '../../hooks';

/**
 * SpeechInput Component
 * Provides voice input functionality with visual feedback
 * 
 * @param {Object} props
 * @param {Function} props.onTranscript - Callback when final transcript is ready
 * @param {Function} props.onInterimTranscript - Callback for interim transcripts (optional)
 * @param {boolean} props.disabled - Disable the microphone button
 * @param {string} props.language - Language code for recognition (default: 'en-US')
 * @param {boolean} props.pauseWhileAssistantSpeaks - Pause auto-submit while assistant is speaking
 * @param {Object} props.sx - Custom styles
 */
function SpeechInput({
  onTranscript,
  onInterimTranscript,
  disabled = false,
  language = 'en-US',
  pauseWhileAssistantSpeaks = false,
  sx = {},
}) {
  const [showError, setShowError] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [forceUpdate, setForceUpdate] = useState(0); // Force re-render for toggle

  // Get STT settings
  const { settings } = useSettings();
  const sttModel = settings.sttModel || 'Xenova/whisper-tiny';

  // Convert language code (e.g., 'en-US' to 'en')
  const whisperLanguage = language.split('-')[0];

  // Memoize callbacks to prevent unnecessary re-initialization
  const speechOptions = useMemo(() => ({
    model: sttModel,
    language: whisperLanguage,
    continuous: false, // Use manual mode - we control restarts ourselves
    onFinalTranscript: (finalText) => {
      // Don't trigger onTranscript here - we handle it in auto-submit
      // This prevents duplicate submissions
    },
    onInterimTranscript: (interimText) => {
      if (onInterimTranscript) {
        onInterimTranscript(interimText);
      }
    },
    onError: (errorCode, message) => {
      // Only show error to user for non-aborted errors
      if (errorCode !== 'aborted') {
        setErrorMessage(message);
        setShowError(true);
      }
    },
    onModelLoading: (status) => {
      // Model loading status handled by useWhisperSTT
    },
  }), [sttModel, whisperLanguage, onInterimTranscript]);

  const {
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    isModelLoaded,
    isModelLoading,
    isProcessing,
    error,
    audioLevel,
    startListening,
    stopListening,
    resetTranscript,
  } = useWhisperSTT(speechOptions);

  // Show error notification (but ignore aborted errors)
  useEffect(() => {
    if (error && !error.includes('aborted')) {
      setErrorMessage(error);
      setShowError(true);
    }
  }, [error]);

  // Timer for auto-submit after pause
  const autoSubmitTimerRef = React.useRef(null);
  // Flag to prevent restart during auto-submit
  const isAutoSubmittingRef = React.useRef(false);
  // Flag to indicate we want continuous conversation
  const wantsContinuousConversationRef = React.useRef(false);

  const handleToggle = () => {
    if (isListening) {
      stopListening();
      resetTranscript();
      wantsContinuousConversationRef.current = false;
      // Clear any pending auto-submit
      if (autoSubmitTimerRef.current) {
        clearTimeout(autoSubmitTimerRef.current);
        autoSubmitTimerRef.current = null;
      }
    } else {
      wantsContinuousConversationRef.current = true;
      startListening();
    }
  };

  // Track if we were listening when assistant started speaking
  const wasListeningRef = React.useRef(false);

  // Handle resume when assistant finishes speaking
  React.useEffect(() => {
    // When assistant finishes speaking and we want continuous conversation
    // Don't restart if we're in the middle of auto-submitting or have a pending timer
    if (!pauseWhileAssistantSpeaks && 
        wantsContinuousConversationRef.current && 
        !isListening && 
        !isAutoSubmittingRef.current &&
        !autoSubmitTimerRef.current) {  // Don't restart if timer is pending!
      // Clear tracking so we can accept new speech
      lastSubmittedTranscriptRef.current = '';
      wasListeningRef.current = false;
      // Small delay to ensure previous recognition fully ended
      setTimeout(() => {
        if (wantsContinuousConversationRef.current && 
            !isListening && 
            !isAutoSubmittingRef.current &&
            !autoSubmitTimerRef.current) {
          startListening();
        }
      }, 200);
    } else if (pauseWhileAssistantSpeaks && isListening) {
      // Assistant started speaking while we were listening
      wasListeningRef.current = true;
    }
  }, [pauseWhileAssistantSpeaks, isListening, startListening]);

  // Track the last transcript that was submitted
  const lastSubmittedTranscriptRef = React.useRef('');

  // Auto-submit after pause in speech
  // Only runs when we have speech input (isListening or has transcript from speech)
  React.useEffect(() => {
    // Early return: Only process if we're listening or have a transcript from speech
    // This prevents the effect from running on every render when user is typing text
    if (!isListening && !transcript.trim()) {
      return;
    }

    // Don't auto-submit while assistant is speaking
    if (pauseWhileAssistantSpeaks) {
      // Clear timer if assistant started speaking
      if (autoSubmitTimerRef.current) {
        clearTimeout(autoSubmitTimerRef.current);
        autoSubmitTimerRef.current = null;
      }
      return;
    }

    // Only process new transcripts that we haven't submitted yet
    const trimmedTranscript = transcript.trim();
    
    // Check if this is genuinely new content (different from what we last submitted)
    const hasNewContent = trimmedTranscript && 
                          trimmedTranscript !== lastSubmittedTranscriptRef.current &&
                          !isAutoSubmittingRef.current;
    
    // Always clear existing timer when transcript changes (will reset below if needed)
    if (autoSubmitTimerRef.current) {
      clearTimeout(autoSubmitTimerRef.current);
      autoSubmitTimerRef.current = null;
    }

    // If we have new content and want continuous conversation, set timer to auto-submit
    // Note: isListening might be false if recognition just ended (non-continuous mode)
    if (hasNewContent && wantsContinuousConversationRef.current && !isAutoSubmittingRef.current) {
      // Timer was already cleared above, now set new one
      autoSubmitTimerRef.current = setTimeout(() => {
        // Double-check conditions before submitting
        if (!wantsContinuousConversationRef.current || isAutoSubmittingRef.current) {
          autoSubmitTimerRef.current = null;
          return;
        }
        
        const currentTranscript = transcript.trim();
        if (!currentTranscript || currentTranscript === lastSubmittedTranscriptRef.current) {
          autoSubmitTimerRef.current = null;
          return;
        }
        
        isAutoSubmittingRef.current = true;
        lastSubmittedTranscriptRef.current = currentTranscript;
        
        // PAUSE listening before submitting to avoid picking up more speech
        stopListening();
        
        if (onTranscript && currentTranscript) {
          onTranscript(currentTranscript);
        }
        
        // Clear transcript immediately since we stopped listening
        resetTranscript();
        
        // Mark as ready for next input
        setTimeout(() => {
          isAutoSubmittingRef.current = false;
          autoSubmitTimerRef.current = null; // Clear timer ref
          // wantsContinuousConversationRef stays TRUE so we resume after assistant
        }, 500);
      }, 2000); // 2 second pause triggers submit
    }

    // DON'T clear timer in cleanup if it's pending to fire
    return () => {
      // Don't clear timer during re-renders - only on actual unmount
      // The timer will handle its own cleanup
    };
  }, [transcript, isListening, onTranscript, stopListening, resetTranscript, pauseWhileAssistantSpeaks]);

  const handleCloseError = () => {
    setShowError(false);
  };

  // Don't render if not supported
  if (!isSupported) {
    return (
      <Tooltip title="Speech recognition not supported in this browser">
        <span>
          <IconButton disabled sx={sx}>
            <MicOffIcon />
          </IconButton>
        </span>
      </Tooltip>
    );
  }

  // Show loading while model loads
  if (isModelLoading) {
    return (
      <Tooltip title="Loading Whisper model...">
        <span>
          <IconButton disabled sx={sx}>
            <CircularProgress size={20} />
          </IconButton>
        </span>
      </Tooltip>
    );
  }

  return (
    <Box sx={{ position: 'relative', ...sx }}>
      {/* Microphone Button */}
      <Tooltip
        title={
          !isModelLoaded
            ? 'Whisper model not loaded'
            : pauseWhileAssistantSpeaks
              ? 'Waiting for Sparky to finish...'
              : isListening
                ? 'Stop listening'
                : 'Start voice input (Whisper STT)'
        }
      >
        <span>
          <IconButton
            onClick={handleToggle}
            disabled={disabled || pauseWhileAssistantSpeaks || !isModelLoaded}
            sx={{
              color: pauseWhileAssistantSpeaks
                ? 'warning.main'  // Orange when assistant is speaking
                : isListening 
                  ? 'error.main'   // Red when actively listening
                  : 'inherit',     // Gray when not listening
              animation: isListening && !pauseWhileAssistantSpeaks 
                ? 'pulse 1.5s ease-in-out infinite' 
                : 'none',
              '@keyframes pulse': {
                '0%, 100%': {
                  opacity: 1,
                  transform: 'scale(1)',
                },
                '50%': {
                  opacity: 0.7,
                  transform: 'scale(1.1)',
                },
              },
            }}
          >
            {pauseWhileAssistantSpeaks
              ? <VolumeOffIcon />  // Muted while assistant speaks (mic OFF)
              : isListening 
                ? <StopIcon />     // Stop icon when actively listening
                : <MicIcon />      // Mic icon when not listening
            }
          </IconButton>
        </span>
      </Tooltip>

      {/* Live Transcription Display */}
      <Collapse in={isListening || isProcessing || (transcript && transcript.trim().length > 0)}>
        <Box
          sx={{
            position: 'absolute',
            bottom: '100%',
            right: 0, // Align to right edge of button
            mb: 1,
            p: 2,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            boxShadow: 3,
            maxWidth: 400,
            minWidth: 250,
            zIndex: 1000,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* Single element that changes based on state */}
            <Box sx={{ flex: 1, minHeight: 20, display: 'flex', alignItems: 'center' }}>
              {isProcessing ? (
                // Loading indicator: bouncing line (same width as waveform)
                <Box
                  sx={{
                    width: '100%',
                    height: 20,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                  }}
                >
                  <Box
                    sx={{
                      width: '80%',
                      height: 2,
                      bgcolor: 'primary.main',
                      borderRadius: 1,
                      position: 'relative',
                      overflow: 'hidden',
                      '&::before': {
                        content: '""',
                        position: 'absolute',
                        top: 0,
                        left: '-100%',
                        width: '100%',
                        height: '100%',
                        bgcolor: 'primary.light',
                        animation: 'bounce-loading 1.5s ease-in-out infinite',
                        '@keyframes bounce-loading': {
                          '0%': {
                            left: '-100%',
                          },
                          '50%': {
                            left: '100%',
                          },
                          '100%': {
                            left: '100%',
                          },
                        },
                      },
                    }}
                  />
                </Box>
              ) : (transcript || interimTranscript) ? (
                // Show transcript text
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'text.primary',
                    wordBreak: 'break-word',
                    flex: 1,
                  }}
                >
                  {transcript}
                  {interimTranscript && (
                    <span style={{ color: 'rgba(255,255,255,0.5)' }}>
                      {interimTranscript}
                    </span>
                  )}
                </Typography>
              ) : (
                // Waveform when listening
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 0.5,
                    height: 20,
                    width: '100%',
                  }}
                >
                  {[...Array(5)].map((_, i) => {
                    // Calculate height based on audio level and position (center bars taller)
                    const baseHeight = [6, 8, 10, 8, 6][i];
                    const maxHeight = [14, 16, 18, 16, 14][i];
                    const currentHeight = baseHeight + (audioLevel * (maxHeight - baseHeight));
                    
                    return (
                      <Box
                        key={i}
                        sx={{
                          width: 3,
                          bgcolor: audioLevel > 0.1 ? 'primary.main' : 'text.secondary',
                          borderRadius: 1.5,
                          transition: 'all 0.15s ease-out',
                          height: `${currentHeight}px`,
                          minHeight: 4,
                          opacity: audioLevel > 0.05 ? 1 : 0.4,
                          animation: audioLevel > 0.1 
                            ? `waveform-pulse 0.8s ease-in-out infinite`
                            : 'none',
                          animationDelay: `${i * 0.15}s`,
                          '@keyframes waveform-pulse': {
                            '0%, 100%': { 
                              transform: 'scaleY(0.7)',
                              opacity: 0.6,
                            },
                            '50%': { 
                              transform: 'scaleY(1.2)',
                              opacity: 1,
                            },
                          },
                        }}
                      />
                    );
                  })}
                </Box>
              )}
            </Box>
            
            {/* Cancel button - only show if we have transcript ready to send */}
            {(transcript && transcript.trim().length > 0 && !isProcessing) && (
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  
                  // Clear any pending auto-submit timer
                  if (autoSubmitTimerRef.current) {
                    clearTimeout(autoSubmitTimerRef.current);
                    autoSubmitTimerRef.current = null;
                  }
                  
                  // Clear transcript and continue listening
                  resetTranscript();
                }}
                sx={{
                  ml: 1,
                  color: 'text.secondary',
                  '&:hover': {
                    color: 'error.main',
                  },
                }}
              >
                <StopIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
        </Box>
      </Collapse>

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

// Memoize component to prevent re-renders when parent re-renders (e.g., on every keystroke)
// Only re-render when props actually change
// Note: We use shallow comparison for sx prop - if sx object reference changes but content is same,
// it will still re-render, but this is acceptable for performance
export default memo(SpeechInput);

