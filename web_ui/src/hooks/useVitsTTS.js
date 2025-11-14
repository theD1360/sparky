import { useState, useEffect, useCallback, useRef } from 'react';
import * as tts from '@diffusionstudio/vits-web';

/**
 * Custom hook for VITS-based Text-to-Speech
 * Provides high-quality, offline-capable TTS using VITS models
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.voiceId - Voice ID to use (default: 'en_US-hfc_female-medium')
 * @param {Function} options.onEnd - Callback when speech ends
 * @param {Function} options.onError - Error callback
 * @param {Function} options.onDownloadProgress - Progress callback for voice downloads
 * 
 * @returns {Object} TTS state and controls
 */
export function useVitsTTS(options = {}) {
  const {
    voiceId = 'en_US-hfc_female-medium',
    onEnd,
    onError,
    onDownloadProgress,
  } = options;

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isSupported, setIsSupported] = useState(true); // VITS works in all modern browsers
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [isModelReady, setIsModelReady] = useState(false);
  const [availableVoices, setAvailableVoices] = useState({});
  const [storedVoices, setStoredVoices] = useState([]);
  const [error, setError] = useState(null);

  const audioRef = useRef(null);
  const currentVoiceIdRef = useRef(voiceId);

  // Check browser support
  useEffect(() => {
    const checkSupport = async () => {
      try {
        // Check for required APIs
        if (!('AudioContext' in window || 'webkitAudioContext' in window)) {
          setIsSupported(false);
          setError('Web Audio API not supported in this browser');
          return;
        }

        // Check IndexedDB support (required for VITS storage)
        if (!('indexedDB' in window)) {
          console.warn('IndexedDB not available - VITS TTS may have limited functionality');
        }

        // Fetch available voices - returns array of voice objects
        const voicesArray = await tts.voices();
        console.log('VITS voices() returned:', Array.isArray(voicesArray) ? `array of ${voicesArray.length} items` : typeof voicesArray);
        
        // Convert to object if it's an array
        let voicesObj = voicesArray;
        if (Array.isArray(voicesArray)) {
          voicesObj = {};
          voicesArray.forEach(voice => {
            if (voice && voice.key) {
              voicesObj[voice.key] = voice;
            }
          });
          console.log('Converted array to object with', Object.keys(voicesObj).length, 'voices');
        }
        
        setAvailableVoices(voicesObj);
        console.log('Available VITS voices:', Object.keys(voicesObj).length, 'voices');

        // Check stored (downloaded) voices
        const stored = await tts.stored();
        setStoredVoices(stored);
        console.log('Stored VITS voices:', stored.length, 'voices -', stored);

        if (stored.length === 0) {
          console.log('No voices downloaded yet. Voices will be downloaded automatically on first use.');
        }

        setIsSupported(true);
      } catch (err) {
        console.error('Error checking VITS support:', err);
        console.error('VITS error details:', {
          message: err.message,
          stack: err.stack,
        });
        setError(`Failed to initialize VITS TTS: ${err.message}`);
        setIsSupported(false);
      }
    };

    checkSupport();
  }, []);

  // Download voice model if not already stored
  const downloadVoice = useCallback(async (targetVoiceId) => {
    try {
      setIsDownloading(true);
      setDownloadProgress(0);
      setError(null);

      console.log(`Downloading VITS voice: ${targetVoiceId}`);

      await tts.download(targetVoiceId, (progress) => {
        const percent = Math.round((progress.loaded * 100) / progress.total);
        setDownloadProgress(percent);
        console.log(`Downloading ${progress.url} - ${percent}%`);
        
        if (onDownloadProgress) {
          onDownloadProgress(percent, progress);
        }
      });

      // Update stored voices list
      const stored = await tts.stored();
      setStoredVoices(stored);
      
      setIsDownloading(false);
      setDownloadProgress(100);
      console.log(`Voice ${targetVoiceId} downloaded successfully`);
      
      return true;
    } catch (err) {
      console.error('Error downloading voice:', err);
      setError(`Failed to download voice: ${err.message}`);
      setIsDownloading(false);
      
      if (onError) {
        onError('download-failed', `Failed to download voice: ${err.message}`);
      }
      
      return false;
    }
  }, [onDownloadProgress, onError]);

  // Ensure voice model is ready
  const ensureVoiceReady = useCallback(async (targetVoiceId) => {
    try {
      const stored = await tts.stored();
      
      if (!stored.includes(targetVoiceId)) {
        console.log(`Voice ${targetVoiceId} not stored, downloading...`);
        const success = await downloadVoice(targetVoiceId);
        if (!success) {
          return false;
        }
      }
      
      setIsModelReady(true);
      return true;
    } catch (err) {
      console.error('Error ensuring voice ready:', err);
      setError(`Failed to prepare voice: ${err.message}`);
      return false;
    }
  }, [downloadVoice]);

  // Update current voice ID when prop changes
  useEffect(() => {
    currentVoiceIdRef.current = voiceId;
  }, [voiceId]);

  // Speak text using VITS
  const speak = useCallback(async (text, customOptions = {}) => {
    if (!isSupported) {
      console.warn('Cannot speak: VITS not supported');
      return;
    }

    if (!text || text.trim() === '') {
      console.warn('Cannot speak: empty text');
      return;
    }

    // Stop any current speech
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    try {
      setIsSpeaking(true);
      setError(null);

      const targetVoiceId = customOptions.voiceId || currentVoiceIdRef.current;

      // Ensure voice is downloaded
      const ready = await ensureVoiceReady(targetVoiceId);
      if (!ready) {
        setIsSpeaking(false);
        return;
      }

      console.log(`Generating speech with voice: ${targetVoiceId}`);

      // Generate speech
      const wav = await tts.predict({
        text: text,
        voiceId: targetVoiceId,
      });

      // Create audio element and play
      const audio = new Audio();
      audioRef.current = audio;
      
      audio.src = URL.createObjectURL(wav);
      
      audio.onended = () => {
        console.log('Speech synthesis ended');
        setIsSpeaking(false);
        URL.revokeObjectURL(audio.src); // Clean up blob URL
        audioRef.current = null;
        
        if (onEnd) {
          onEnd();
        }
      };

      audio.onerror = (err) => {
        console.error('Audio playback error:', err);
        setIsSpeaking(false);
        setError('Failed to play audio');
        URL.revokeObjectURL(audio.src);
        audioRef.current = null;
        
        if (onError) {
          onError('playback-failed', 'Failed to play audio');
        }
      };

      await audio.play();
      console.log('Playing generated speech');
    } catch (err) {
      console.error('Failed to synthesize speech:', err);
      setIsSpeaking(false);
      setError(`Speech synthesis failed: ${err.message}`);
      
      if (onError) {
        onError('synthesis-failed', `Speech synthesis failed: ${err.message}`);
      }
    }
  }, [isSupported, ensureVoiceReady, onEnd, onError]);

  // Cancel speech
  const cancel = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      URL.revokeObjectURL(audioRef.current.src);
      audioRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  // Remove a voice from storage
  const removeVoice = useCallback(async (targetVoiceId) => {
    try {
      await tts.remove(targetVoiceId);
      const stored = await tts.stored();
      setStoredVoices(stored);
      console.log(`Removed voice: ${targetVoiceId}`);
      return true;
    } catch (err) {
      console.error('Error removing voice:', err);
      setError(`Failed to remove voice: ${err.message}`);
      return false;
    }
  }, []);

  // Clear all stored voices
  const clearAllVoices = useCallback(async () => {
    try {
      await tts.flush();
      setStoredVoices([]);
      console.log('Cleared all stored voices');
      return true;
    } catch (err) {
      console.error('Error clearing voices:', err);
      setError(`Failed to clear voices: ${err.message}`);
      return false;
    }
  }, []);

  // Get voices by language
  const getVoicesByLanguage = useCallback((language) => {
    const langPrefix = language.split('-')[0]; // e.g., 'en' from 'en-US'
    return Object.keys(availableVoices).filter(voiceId => 
      voiceId.toLowerCase().startsWith(langPrefix.toLowerCase())
    );
  }, [availableVoices]);

  return {
    // State
    isSpeaking,
    isSupported,
    isDownloading,
    downloadProgress,
    isModelReady,
    availableVoices,
    storedVoices,
    error,
    
    // Controls
    speak,
    cancel,
    downloadVoice,
    removeVoice,
    clearAllVoices,
    getVoicesByLanguage,
  };
}

export default useVitsTTS;


