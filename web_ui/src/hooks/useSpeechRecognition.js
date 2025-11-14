import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for Web Speech API - Speech Recognition (STT)
 * Provides speech-to-text functionality with real-time transcription
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.language - Language code (default: 'en-US')
 * @param {boolean} options.continuous - Enable continuous recognition (default: true)
 * @param {boolean} options.interimResults - Return interim results (default: true)
 * @param {Function} options.onFinalTranscript - Callback when final transcript is ready
 * @param {Function} options.onInterimTranscript - Callback for interim transcripts
 * @param {Function} options.onError - Error callback
 * 
 * @returns {Object} Speech recognition state and controls
 */
export function useSpeechRecognition(options = {}) {
  const {
    language = 'en-US',
    continuous = true,
    interimResults = true,
    onFinalTranscript,
    onInterimTranscript,
    onError,
  } = options;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const [error, setError] = useState(null);

  const recognitionRef = useRef(null);
  const isListeningRef = useRef(false);
  const shouldBeListeningRef = useRef(false); // Track user's intent to listen
  const errorCountRef = useRef(0); // Track consecutive errors
  const lastErrorTypeRef = useRef(null); // Track last error type
  const isResettingRef = useRef(false); // Track when transcript is being reset
  const MAX_RETRIES = 3; // Maximum retry attempts

  // Check browser support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (SpeechRecognition) {
      setIsSupported(true);
      
      // Initialize recognition
      const recognition = new SpeechRecognition();
      recognition.continuous = continuous;
      recognition.interimResults = interimResults;
      recognition.lang = language;
      recognition.maxAlternatives = 1;

      // Handle results
      recognition.onresult = (event) => {
        let interim = '';
        let final = '';

        // Reset error count on successful speech detection
        errorCountRef.current = 0;
        lastErrorTypeRef.current = null;
        
        console.log('[STT] Got result, isListening:', isListeningRef.current, 'shouldBeListen:', shouldBeListeningRef.current, 'isResetting:', isResettingRef.current);

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcriptPart = event.results[i][0].transcript;
          
          if (event.results[i].isFinal) {
            final += transcriptPart;
          } else {
            interim += transcriptPart;
          }
        }

        if (final) {
          setTranscript(prev => prev + final + ' ');
          setInterimTranscript('');
          
          if (onFinalTranscript) {
            onFinalTranscript(final);
          }
        }

        if (interim) {
          setInterimTranscript(interim);
          
          if (onInterimTranscript) {
            onInterimTranscript(interim);
          }
        }
      };

      // Handle start
      recognition.onstart = () => {
        console.log('[STT] Recognition started - shouldBeListen:', shouldBeListeningRef.current, 'isResetting:', isResettingRef.current);
        setIsListening(true);
        isListeningRef.current = true;
        setError(null);
        // Don't reset error count here - only reset on actual success (result) or user action
      };

      // Handle end
      recognition.onend = () => {
        console.log('[STT] Recognition ended - shouldBeListen:', shouldBeListeningRef.current, 'isResetting:', isResettingRef.current, 'continuous:', continuous);
        setIsListening(false);
        isListeningRef.current = false;
        setInterimTranscript('');
        
        // Don't auto-restart if we're just resetting the transcript
        if (isResettingRef.current) {
          console.log('[STT] Skipping auto-restart during transcript reset');
          return;
        }
        
        // Auto-restart if continuous mode and user still wants to listen
        if (continuous && shouldBeListeningRef.current) {
          console.log('[STT] Auto-restarting recognition in continuous mode');
          setTimeout(() => {
            if (shouldBeListeningRef.current && recognitionRef.current && !isResettingRef.current) {
              try {
                console.log('[STT] Actually restarting now...');
                recognitionRef.current.start();
              } catch (err) {
                console.error('[STT] Failed to restart recognition:', err);
              }
            } else {
              console.log('[STT] Restart cancelled - shouldBeListen:', shouldBeListeningRef.current, 'isResetting:', isResettingRef.current);
            }
          }, 100); // Small delay to prevent immediate restart issues
        } else {
          console.log('[STT] NOT restarting - continuous:', continuous, 'shouldBeListen:', shouldBeListeningRef.current);
        }
      };

      // Handle errors
      recognition.onerror = (event) => {
        console.error('[STT] Speech recognition error:', event.error);
        
        // Ignore 'aborted' errors - they can happen during React re-renders
        if (event.error === 'aborted') {
          console.log('[STT] Recognition aborted (ignoring, keeping shouldBeListen state)');
          // DON'T set shouldBeListeningRef to false - abort might be unintentional
          // Let the onend handler decide whether to restart based on shouldBeListeningRef
          errorCountRef.current = 0;
          return;
        }
        
        // Track consecutive errors of the same type
        if (lastErrorTypeRef.current === event.error) {
          errorCountRef.current++;
        } else {
          errorCountRef.current = 1;
          lastErrorTypeRef.current = event.error;
        }
        
        console.log(`Error count for '${event.error}': ${errorCountRef.current}/${MAX_RETRIES}`);
        
        const errorMessage = getErrorMessage(event.error);
        setError(errorMessage);
        setIsListening(false);
        isListeningRef.current = false;
        
        if (onError) {
          onError(event.error, errorMessage);
        }

        // Stop trying to listen on serious errors or too many retries
        const isSeriousError = ['audio-capture', 'not-allowed', 'service-not-allowed'].includes(event.error);
        const tooManyRetries = errorCountRef.current >= MAX_RETRIES;
        const shouldStopRetrying = isSeriousError || tooManyRetries;
        
        if (shouldStopRetrying) {
          console.warn(`Stopping recognition after ${errorCountRef.current} consecutive '${event.error}' errors`);
          shouldBeListeningRef.current = false;
          errorCountRef.current = 0;
          lastErrorTypeRef.current = null;
          
          // Show user-friendly message for retry limit
          if (tooManyRetries) {
            const retryMessage = `Speech recognition failed after ${MAX_RETRIES} attempts. Please check your internet connection and try again.`;
            setError(retryMessage);
            if (onError) {
              onError('max-retries', retryMessage);
            }
          }
        }
      };

      recognitionRef.current = recognition;
    } else {
      console.warn('Speech Recognition API not supported in this browser');
      setIsSupported(false);
      setError('Speech recognition is not supported in this browser');
    }

    // Cleanup
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (err) {
          console.error('Error aborting recognition:', err);
        }
      }
    };
  }, [language, continuous, interimResults, onFinalTranscript, onInterimTranscript, onError]);

  // Start listening
  const startListening = useCallback(() => {
    if (!recognitionRef.current || !isSupported) {
      console.warn('Cannot start listening: recognition not available');
      return;
    }

    if (isListeningRef.current) {
      console.warn('Already listening');
      return;
    }

    try {
      setTranscript('');
      setInterimTranscript('');
      setError(null);
      // Reset error tracking on manual start
      errorCountRef.current = 0;
      lastErrorTypeRef.current = null;
      shouldBeListeningRef.current = true;
      recognitionRef.current.start();
    } catch (err) {
      console.error('Failed to start recognition:', err);
      setError('Failed to start speech recognition');
      shouldBeListeningRef.current = false;
      
      if (onError) {
        onError('start-failed', 'Failed to start speech recognition');
      }
    }
  }, [isSupported, onError]);

  // Stop listening
  const stopListening = useCallback(() => {
    if (!recognitionRef.current) {
      return;
    }

    try {
      shouldBeListeningRef.current = false;
      recognitionRef.current.stop();
    } catch (err) {
      console.error('Failed to stop recognition:', err);
    }
  }, []);

  // Abort listening (immediate stop)
  const abortListening = useCallback(() => {
    if (!recognitionRef.current) {
      return;
    }

    try {
      shouldBeListeningRef.current = false;
      isListeningRef.current = false;
      errorCountRef.current = 0;
      lastErrorTypeRef.current = null;
      recognitionRef.current.abort();
      setIsListening(false);
      setInterimTranscript('');
    } catch (err) {
      console.error('Failed to abort recognition:', err);
    }
  }, []);

  // Reset transcript (doesn't stop recognition, just clears text)
  const resetTranscript = useCallback(() => {
    console.log('[STT] Resetting transcript (keeping recognition active) - shouldBeListen:', shouldBeListeningRef.current);
    isResettingRef.current = true;
    setTranscript('');
    setInterimTranscript('');
    // Clear the resetting flag after a brief moment
    setTimeout(() => {
      console.log('[STT] Reset complete, clearing isResetting flag');
      isResettingRef.current = false;
    }, 200);
    // Don't abort or stop - just clear the state
  }, []);

  return {
    // State
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    error,
    
    // Controls
    startListening,
    stopListening,
    abortListening,
    resetTranscript,
  };
}

/**
 * Get user-friendly error message
 */
function getErrorMessage(errorCode) {
  const errorMessages = {
    'no-speech': 'No speech detected. Please try again.',
    'aborted': 'Speech recognition was aborted.',
    'audio-capture': 'No microphone was found or microphone access was denied.',
    'not-allowed': 'Microphone permission was denied. Please enable microphone access.',
    'network': 'Network error: Unable to connect to speech recognition service. Check your internet connection.',
    'service-not-allowed': 'Speech recognition service is not allowed.',
    'bad-grammar': 'Grammar error occurred.',
    'language-not-supported': 'The selected language is not supported.',
    'max-retries': 'Speech recognition failed after multiple attempts. Please try again later.',
    'start-failed': 'Failed to start speech recognition. Please refresh the page.',
  };

  return errorMessages[errorCode] || 'An unknown error occurred during speech recognition.';
}

export default useSpeechRecognition;

