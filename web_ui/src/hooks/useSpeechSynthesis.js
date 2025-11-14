import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook for Web Speech API - Speech Synthesis (TTS)
 * Provides text-to-speech functionality
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.lang - Language code (default: 'en-US')
 * @param {number} options.rate - Speech rate 0.1-10 (default: 1)
 * @param {number} options.pitch - Speech pitch 0-2 (default: 1)
 * @param {number} options.volume - Volume 0-1 (default: 1)
 * @param {string} options.voiceURI - Specific voice URI to use
 * @param {Function} options.onEnd - Callback when speech ends
 * @param {Function} options.onError - Error callback
 * 
 * @returns {Object} Speech synthesis state and controls
 */
export function useSpeechSynthesis(options = {}) {
  const {
    lang = 'en-US',
    rate = 1,
    pitch = 1,
    volume = 1,
    voiceURI = null,
    onEnd,
    onError,
  } = options;

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [voices, setVoices] = useState([]);
  const [error, setError] = useState(null);

  const synthRef = useRef(null);
  const utteranceQueueRef = useRef([]);

  // Initialize speech synthesis
  useEffect(() => {
    if ('speechSynthesis' in window) {
      setIsSupported(true);
      synthRef.current = window.speechSynthesis;

      // Load available voices
      const loadVoices = () => {
        const availableVoices = window.speechSynthesis.getVoices();
        setVoices(availableVoices);
      };

      // Voices might load asynchronously
      loadVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = loadVoices;
      }

      // Poll speaking state (Chrome bug workaround)
      const checkSpeaking = setInterval(() => {
        if (synthRef.current) {
          setIsSpeaking(synthRef.current.speaking);
          setIsPaused(synthRef.current.paused);
        }
      }, 100);

      return () => {
        clearInterval(checkSpeaking);
        if (synthRef.current) {
          synthRef.current.cancel();
        }
      };
    } else {
      console.warn('Speech Synthesis API not supported in this browser');
      setIsSupported(false);
      setError('Text-to-speech is not supported in this browser');
    }
  }, []);

  // Speak text
  const speak = useCallback((text, customOptions = {}) => {
    if (!synthRef.current || !isSupported) {
      console.warn('Cannot speak: synthesis not available');
      return;
    }

    if (!text || text.trim() === '') {
      console.warn('Cannot speak: empty text');
      return;
    }

    try {
      // Create utterance
      const utterance = new SpeechSynthesisUtterance(text);
      
      // Apply options
      utterance.lang = customOptions.lang || lang;
      utterance.rate = customOptions.rate || rate;
      utterance.pitch = customOptions.pitch || pitch;
      utterance.volume = customOptions.volume || volume;

      // Set voice if specified
      const selectedVoiceURI = customOptions.voiceURI || voiceURI;
      if (selectedVoiceURI) {
        const voice = voices.find(v => v.voiceURI === selectedVoiceURI);
        if (voice) {
          utterance.voice = voice;
        }
      } else {
        // Find a voice matching the language
        const voice = voices.find(v => v.lang === utterance.lang);
        if (voice) {
          utterance.voice = voice;
        }
      }

      // Event handlers
      utterance.onstart = () => {
        console.log('Speech synthesis started');
        setIsSpeaking(true);
        setError(null);
      };

      utterance.onend = () => {
        console.log('Speech synthesis ended');
        setIsSpeaking(false);
        
        // Process next in queue
        utteranceQueueRef.current.shift();
        if (utteranceQueueRef.current.length > 0) {
          synthRef.current.speak(utteranceQueueRef.current[0]);
        }
        
        if (onEnd) {
          onEnd();
        }
      };

      utterance.onerror = (event) => {
        console.error('Speech synthesis error:', event.error);
        
        const errorMessage = getSynthesisErrorMessage(event.error);
        setError(errorMessage);
        setIsSpeaking(false);
        
        // Clear queue on error
        utteranceQueueRef.current = [];
        
        if (onError) {
          onError(event.error, errorMessage);
        }
      };

      utterance.onpause = () => {
        console.log('Speech synthesis paused');
        setIsPaused(true);
      };

      utterance.onresume = () => {
        console.log('Speech synthesis resumed');
        setIsPaused(false);
      };

      // Add to queue and speak
      utteranceQueueRef.current.push(utterance);
      
      // If not currently speaking, start immediately
      if (!synthRef.current.speaking) {
        synthRef.current.speak(utterance);
      }
    } catch (err) {
      console.error('Failed to synthesize speech:', err);
      setError('Failed to synthesize speech');
      
      if (onError) {
        onError('synthesis-failed', 'Failed to synthesize speech');
      }
    }
  }, [isSupported, lang, rate, pitch, volume, voiceURI, voices, onEnd, onError]);

  // Cancel all speech
  const cancel = useCallback(() => {
    if (!synthRef.current) {
      return;
    }

    try {
      synthRef.current.cancel();
      utteranceQueueRef.current = [];
      setIsSpeaking(false);
      setIsPaused(false);
    } catch (err) {
      console.error('Failed to cancel speech:', err);
    }
  }, []);

  // Pause speech
  const pause = useCallback(() => {
    if (!synthRef.current || !isSpeaking) {
      return;
    }

    try {
      synthRef.current.pause();
      setIsPaused(true);
    } catch (err) {
      console.error('Failed to pause speech:', err);
    }
  }, [isSpeaking]);

  // Resume speech
  const resume = useCallback(() => {
    if (!synthRef.current || !isPaused) {
      return;
    }

    try {
      synthRef.current.resume();
      setIsPaused(false);
    } catch (err) {
      console.error('Failed to resume speech:', err);
    }
  }, [isPaused]);

  // Get voices by language
  const getVoicesByLanguage = useCallback((language) => {
    return voices.filter(voice => voice.lang.startsWith(language));
  }, [voices]);

  return {
    // State
    isSpeaking,
    isPaused,
    isSupported,
    voices,
    error,
    
    // Controls
    speak,
    cancel,
    pause,
    resume,
    getVoicesByLanguage,
  };
}

/**
 * Get user-friendly synthesis error message
 */
function getSynthesisErrorMessage(errorCode) {
  const errorMessages = {
    'canceled': 'Speech was canceled.',
    'interrupted': 'Speech was interrupted.',
    'audio-busy': 'Audio output is busy. Please try again.',
    'audio-hardware': 'Audio hardware error occurred.',
    'network': 'Network error occurred during speech synthesis.',
    'synthesis-unavailable': 'Speech synthesis is temporarily unavailable.',
    'synthesis-failed': 'Speech synthesis failed.',
    'language-unavailable': 'The selected language is not available for speech synthesis.',
    'voice-unavailable': 'The selected voice is not available.',
    'text-too-long': 'The text is too long to synthesize.',
    'invalid-argument': 'Invalid argument provided to speech synthesis.',
  };

  return errorMessages[errorCode] || 'An unknown error occurred during speech synthesis.';
}

export default useSpeechSynthesis;

