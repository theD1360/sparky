import React, { useState, useEffect, useMemo } from 'react';
import {
  IconButton,
  Tooltip,
  Box,
  Typography,
  Collapse,
  Alert,
  Snackbar,
} from '@mui/material';
import {
  Mic as MicIcon,
  MicOff as MicOffIcon,
  Stop as StopIcon,
  VolumeOff as VolumeOffIcon,
} from '@mui/icons-material';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';

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

  // Memoize callbacks to prevent unnecessary re-initialization
  const speechOptions = useMemo(() => ({
    language,
    continuous: false, // Use manual mode - we control restarts ourselves
    interimResults: true,
    onFinalTranscript: (finalText) => {
      // Don't trigger onTranscript here - we handle it in auto-submit
      // This prevents duplicate submissions
      console.log('[SpeechInput] Final transcript received:', finalText.substring(0, 50));
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
  }), [language, onTranscript, onInterimTranscript]);

  const {
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    error,
    startListening,
    stopListening,
    resetTranscript,
  } = useSpeechRecognition(speechOptions);

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
      console.log('[SpeechInput] User clicked stop - ending conversation');
      stopListening();
      resetTranscript();
      wantsContinuousConversationRef.current = false;
      // Clear any pending auto-submit
      if (autoSubmitTimerRef.current) {
        clearTimeout(autoSubmitTimerRef.current);
        autoSubmitTimerRef.current = null;
      }
    } else {
      console.log('[SpeechInput] User clicked start - beginning continuous conversation');
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
      console.log('[SpeechInput] Resuming listening after assistant finished');
      // Clear tracking so we can accept new speech
      lastSubmittedTranscriptRef.current = '';
      wasListeningRef.current = false;
      // Small delay to ensure previous recognition fully ended
      setTimeout(() => {
        if (wantsContinuousConversationRef.current && 
            !isListening && 
            !isAutoSubmittingRef.current &&
            !autoSubmitTimerRef.current) {
          console.log('[SpeechInput] Actually restarting now');
          startListening();
        } else {
          console.log('[SpeechInput] Skipping restart - autoSubmitting:', isAutoSubmittingRef.current, 'timer pending:', !!autoSubmitTimerRef.current);
        }
      }, 200);
    } else if (pauseWhileAssistantSpeaks && isListening) {
      // Assistant started speaking while we were listening
      wasListeningRef.current = true;
      console.log('[SpeechInput] Marking pause - assistant speaking');
    }
  }, [pauseWhileAssistantSpeaks, isListening, startListening]);

  // Track the last transcript that was submitted
  const lastSubmittedTranscriptRef = React.useRef('');

  // Auto-submit after pause in speech
  React.useEffect(() => {
    // Clear existing timer
    if (autoSubmitTimerRef.current) {
      clearTimeout(autoSubmitTimerRef.current);
    }

    // Don't auto-submit while assistant is speaking
    if (pauseWhileAssistantSpeaks) {
      console.log('[SpeechInput] Auto-submit paused while assistant speaks');
      return;
    }

    // Only process new transcripts that we haven't submitted yet
    const trimmedTranscript = transcript.trim();
    
    // Check if this is genuinely new content (different from what we last submitted)
    const hasNewContent = trimmedTranscript && 
                          trimmedTranscript !== lastSubmittedTranscriptRef.current &&
                          !isAutoSubmittingRef.current;

    // Debug logging
    if (trimmedTranscript && trimmedTranscript !== lastSubmittedTranscriptRef.current) {
      console.log('[SpeechInput] New transcript detected:', {
        current: trimmedTranscript.substring(0, 30),
        lastSubmitted: lastSubmittedTranscriptRef.current.substring(0, 30),
        isAutoSubmitting: isAutoSubmittingRef.current,
        hasNewContent,
      });
    }

    // If we have new content and want continuous conversation, set timer to auto-submit
    // Note: isListening might be false if recognition just ended (non-continuous mode)
    if (hasNewContent && wantsContinuousConversationRef.current) {
      console.log('[SpeechInput] ✅ Setting auto-submit timer for:', trimmedTranscript.substring(0, 50));
      console.log('[SpeechInput] Timer will fire in 2000ms');
      
      autoSubmitTimerRef.current = setTimeout(() => {
        console.log('[SpeechInput] ⏰ TIMER FIRED! Auto-submitting now:', trimmedTranscript.substring(0, 50));
        
        isAutoSubmittingRef.current = true;
        lastSubmittedTranscriptRef.current = trimmedTranscript;
        
        // PAUSE listening before submitting to avoid picking up more speech
        console.log('[SpeechInput] Stopping listening before submit (will resume after assistant)');
        stopListening();
        
        console.log('[SpeechInput] About to call onTranscript with:', trimmedTranscript.substring(0, 50));
        if (onTranscript && trimmedTranscript) {
          console.log('[SpeechInput] ➡️ Calling onTranscript NOW');
          onTranscript(trimmedTranscript);
          console.log('[SpeechInput] ✅ onTranscript called successfully');
        } else {
          console.error('[SpeechInput] ❌ onTranscript not available or no transcript!', {
            hasCallback: !!onTranscript,
            hasTranscript: !!trimmedTranscript
          });
        }
        
        // Clear transcript immediately since we stopped listening
        resetTranscript();
        
        // Mark as ready for next input
        setTimeout(() => {
          console.log('[SpeechInput] Ready for next input (waiting for assistant to finish)');
          isAutoSubmittingRef.current = false;
          autoSubmitTimerRef.current = null; // Clear timer ref
          // wantsContinuousConversationRef stays TRUE so we resume after assistant
        }, 500);
      }, 2000); // 2 second pause triggers submit
      
      console.log('[SpeechInput] Timer ID:', autoSubmitTimerRef.current);
    } else {
      console.log('[SpeechInput] NOT setting timer - hasNewContent:', hasNewContent, 'wantsContinuous:', wantsContinuousConversationRef.current);
    }

    // DON'T clear timer in cleanup if it's pending to fire
    return () => {
      // Don't clear timer during re-renders - only on actual unmount
      // The timer will handle its own cleanup
    };
  }, [transcript, onTranscript, stopListening, resetTranscript, pauseWhileAssistantSpeaks]);

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

  return (
    <Box sx={{ position: 'relative', ...sx }}>
      {/* Microphone Button */}
      <Tooltip
        title={
          pauseWhileAssistantSpeaks
            ? 'Waiting for Sparky to finish...'
            : isListening
              ? 'Stop listening'
              : 'Start voice input'
        }
      >
        <span>
          <IconButton
            onClick={handleToggle}
            disabled={disabled || pauseWhileAssistantSpeaks}
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
      <Collapse in={isListening && (transcript || interimTranscript)}>
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
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            {pauseWhileAssistantSpeaks 
              ? '⏸️ Paused - Waiting for Sparky to finish...' 
              : isListening && !transcript
                ? '🎤 Ready - Start speaking...'
                : '🎤 Listening... (auto-submit after 2s pause)'}
          </Typography>
          <Typography 
            variant="body2" 
            sx={{ 
              color: 'text.primary',
              maxHeight: 120,
              overflow: 'auto',
              wordBreak: 'break-word',
              '&::-webkit-scrollbar': {
                width: '4px',
              },
              '&::-webkit-scrollbar-thumb': {
                backgroundColor: 'rgba(255,255,255,0.2)',
                borderRadius: '4px',
              },
            }}
          >
            {transcript}
            <span style={{ color: 'rgba(255,255,255,0.5)' }}>
              {interimTranscript}
            </span>
          </Typography>
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

export default SpeechInput;

