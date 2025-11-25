import { useState, useEffect, useCallback, useRef } from 'react';
// Lazy-load VITS module to prevent blocking browser on initial load
// This is especially important when TTS is disabled
let ttsModule = null;
let ttsLoadPromise = null;

const loadVITSModule = async () => {
  if (ttsModule) return ttsModule;
  if (ttsLoadPromise) return ttsLoadPromise;
  
  ttsLoadPromise = import('@diffusionstudio/vits-web').then(module => {
    ttsModule = module;
    return ttsModule;
  });
  
  return ttsLoadPromise;
};

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
  const audioQueueRef = useRef([]);
  const isCancelledRef = useRef(false);
  const isInitializedRef = useRef(false);
  
  // Helper to ensure VITS module is loaded before use
  const ensureVITSLoaded = useCallback(async () => {
    if (!ttsModule) {
      await loadVITSModule();
    }
    return ttsModule;
  }, []);

  // Initialize VITS and check browser support
  useEffect(() => {
    // Check basic browser support
    if (!('AudioContext' in window || 'webkitAudioContext' in window)) {
      setIsSupported(false);
      setError('Web Audio API not supported in this browser');
      return;
    }

    // Check for SharedArrayBuffer support (required for multi-threaded WASM)
    const hasSharedArrayBuffer = typeof SharedArrayBuffer !== 'undefined';
    if (hasSharedArrayBuffer) {
      console.log('✓ SharedArrayBuffer available - multi-threaded WASM enabled');
    } else {
      console.warn('⚠ SharedArrayBuffer not available - VITS will use single-threaded mode. Enable COOP/COEP headers for better performance.');
    }

    // Check IndexedDB support (required for VITS storage)
    if (!('indexedDB' in window)) {
      console.warn('IndexedDB not available - VITS TTS may have limited functionality');
    }

    // Lazy-load VITS TTS module only when needed (not on mount)
    // This prevents blocking the browser when TTS is disabled
    // Note: VITS cannot be loaded in workers due to ES module bare specifier limitations
    // (VITS requires import maps to resolve 'onnxruntime-web', which workers don't support)
    // We'll load voices on-demand when first needed (e.g., when getting available voices)
    // For now, just mark as ready to accept speak() calls
    const initializeVoices = async () => {
      if (isInitializedRef.current) return;
      try {
        const tts = await ensureVITSLoaded();
        const voices = await tts.voices();
        const voicesObj = {};
        if (Array.isArray(voices)) {
          voices.forEach(voice => {
            voicesObj[voice.id] = voice;
          });
        } else {
          Object.assign(voicesObj, voices);
        }
        setAvailableVoices(voicesObj);
        console.log('Available VITS voices:', Object.keys(voicesObj).length, 'voices');

        const stored = await tts.stored();
        setStoredVoices(stored);
        console.log('Stored VITS voices:', stored.length, 'voices');
        
        isInitializedRef.current = true;
      } catch (err) {
        console.error('Failed to initialize VITS voices:', err);
        setError(`Failed to initialize VITS: ${err.message}`);
      }
    };
    
    // Initialize voices in background (non-blocking)
    initializeVoices();

    // Cleanup
    return () => {
      // Clear audio queue on unmount
      audioQueueRef.current.forEach((audio) => {
        if (audio && audio.src) {
          URL.revokeObjectURL(audio.src);
        }
      });
      audioQueueRef.current = [];
      isCancelledRef.current = false;
    };
  }, []);

  // Download voice model if not already stored
  const downloadVoice = useCallback(async (targetVoiceId) => {
    try {
      setIsDownloading(true);
      setDownloadProgress(0);
      setError(null);

      console.log(`Downloading VITS voice: ${targetVoiceId}`);
      
      const tts = await ensureVITSLoaded();

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
      const tts = await ensureVITSLoaded();
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
  }, [downloadVoice, ensureVITSLoaded]);

  // Update current voice ID when prop changes
  useEffect(() => {
    currentVoiceIdRef.current = voiceId;
  }, [voiceId]);

  // Split text into chunks for streaming TTS
  const splitTextIntoChunks = useCallback((text, maxChunkLength = 200) => {
    // Split by sentences first (periods, exclamation, question marks)
    const sentences = text.split(/([.!?]+\s+)/).filter(s => s.trim().length > 0);
    const chunks = [];
    let currentChunk = '';

    for (let i = 0; i < sentences.length; i++) {
      const sentence = sentences[i];
      // If adding this sentence would exceed max length, start a new chunk
      if (currentChunk.length + sentence.length > maxChunkLength && currentChunk.length > 0) {
        chunks.push(currentChunk.trim());
        currentChunk = sentence;
      } else {
        currentChunk += sentence;
      }
    }

    // Add remaining chunk
    if (currentChunk.trim().length > 0) {
      chunks.push(currentChunk.trim());
    }

    // If no chunks (very short text), return the whole text
    return chunks.length > 0 ? chunks : [text];
  }, []);

  // Speak text using VITS with streaming (chunked processing)
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

      console.log(`Generating speech with voice: ${targetVoiceId} (streaming mode)`);

      // Split text into chunks for streaming
      const chunks = splitTextIntoChunks(text, 200);
      console.log(`Split text into ${chunks.length} chunks for streaming`);

      // Process and play chunks sequentially with true streaming
      audioQueueRef.current = [];
      isCancelledRef.current = false;

      // TRUE STREAMING: Generate and play chunks as they become available
      // Generate chunk 1 → play immediately → while chunk 1 plays, generate chunk 2 → continue
      for (let i = 0; i < chunks.length; i++) {
        if (isCancelledRef.current) break;

        const chunk = chunks[i];
        console.log(`Generating chunk ${i + 1}/${chunks.length}: "${chunk.substring(0, 50)}..."`);
        
        // Generate this chunk
        let wav;
        try {
          const tts = await ensureVITSLoaded();
          wav = await tts.predict({
            text: chunk,
            voiceId: targetVoiceId,
          });
        } catch (err) {
          console.error(`Error generating chunk ${i + 1}:`, err);
          // Continue with next chunk instead of failing completely
          continue;
        }

        if (isCancelledRef.current) {
          // Clean up the blob if cancelled
          break;
        }

        // Create audio element for this chunk
        const audio = new Audio();
        audio.src = URL.createObjectURL(wav);
        audioQueueRef.current.push(audio);

        // If this is the first chunk, start playing immediately
        if (i === 0) {
          audioRef.current = audio;
          await audio.play();
          console.log(`Playing chunk ${i + 1}/${chunks.length} (first chunk - immediate playback)`);
        } else {
          // For subsequent chunks, wait for previous chunk to finish
          const previousAudio = audioQueueRef.current[i - 1];
          await new Promise((resolve) => {
            previousAudio.onended = resolve;
            previousAudio.onerror = resolve;
          });

          if (isCancelledRef.current) {
            URL.revokeObjectURL(audio.src);
            break;
          }

          // Now play this chunk
          audioRef.current = audio;
          await audio.play();
          console.log(`Playing chunk ${i + 1}/${chunks.length}`);
        }

        // Set up cleanup and completion handlers for this audio
        audio.onended = () => {
          URL.revokeObjectURL(audio.src);
          // If this is the last chunk, mark as done
          if (i === chunks.length - 1) {
            console.log('Speech synthesis ended (all chunks played)');
            setIsSpeaking(false);
            audioRef.current = null;
            if (onEnd) {
              onEnd();
            }
          }
        };

        audio.onerror = (err) => {
          console.error(`Audio playback error for chunk ${i + 1}:`, err);
          URL.revokeObjectURL(audio.src);
          setIsSpeaking(false);
          setError('Failed to play audio');
          audioRef.current = null;
          
          if (onError) {
            onError('playback-failed', 'Failed to play audio');
          }
        };
      }

      console.log('All chunks processed and queued for playback');
    } catch (err) {
      console.error('Failed to synthesize speech:', err);
      setIsSpeaking(false);
      setError(`Speech synthesis failed: ${err.message}`);
      
      if (onError) {
        onError('synthesis-failed', `Speech synthesis failed: ${err.message}`);
      }
    }
  }, [isSupported, ensureVoiceReady, splitTextIntoChunks, onEnd, onError]);

  // Cancel speech
  const cancel = useCallback(() => {
    isCancelledRef.current = true;
    
    // Stop and cleanup all audio in queue
    audioQueueRef.current.forEach((audio) => {
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
        URL.revokeObjectURL(audio.src);
      }
    });
    audioQueueRef.current = [];
    
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
      const tts = await ensureVITSLoaded();
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
  }, [ensureVITSLoaded]);

  // Clear all stored voices
  const clearAllVoices = useCallback(async () => {
    try {
      const tts = await ensureVITSLoaded();
      await tts.flush();
      setStoredVoices([]);
      console.log('Cleared all stored voices');
      return true;
    } catch (err) {
      console.error('Error clearing voices:', err);
      setError(`Failed to clear voices: ${err.message}`);
      return false;
    }
  }, [ensureVITSLoaded]);

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


