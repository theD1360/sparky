import { useState, useEffect, useCallback, useRef } from 'react';
import { pipeline, env } from '@xenova/transformers';
import { checkTransformersConfig } from '../utils/transformersConfig';

/**
 * Custom hook for Whisper-based Speech Recognition (STT)
 * Provides accurate, privacy-friendly speech-to-text using Whisper models
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.model - Whisper model to use (default: 'Xenova/whisper-base')
 * @param {string} options.language - Language code (default: 'en')
 * @param {boolean} options.continuous - Enable continuous recognition (default: true)
 * @param {Function} options.onFinalTranscript - Callback when final transcript is ready
 * @param {Function} options.onInterimTranscript - Callback for interim transcripts
 * @param {Function} options.onError - Error callback
 * @param {Function} options.onModelLoading - Callback for model loading progress
 * 
 * @returns {Object} Speech recognition state and controls
 */
export function useWhisperSTT(options = {}) {
  const {
    model = 'Xenova/whisper-base',
    language = 'en',
    continuous = true,
    onFinalTranscript,
    onInterimTranscript,
    onError,
    onModelLoading,
  } = options;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [error, setError] = useState(null);

  const transciberRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const streamRef = useRef(null);
  const isListeningRef = useRef(false);
  const shouldBeListeningRef = useRef(false);
  const processingRef = useRef(false);

  // Check browser support and configure transformers
  useEffect(() => {
    const checkSupport = () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setIsSupported(false);
        setError('Microphone access not supported in this browser');
        return;
      }

      if (!('AudioContext' in window || 'webkitAudioContext' in window)) {
        setIsSupported(false);
        setError('Web Audio API not supported in this browser');
        return;
      }

      // Check transformers configuration (configured in index.js at app startup)
      const config = checkTransformersConfig();
      console.log('Transformers config check:', config);

      if (!config.webAssemblyAvailable) {
        setIsSupported(false);
        setError('WebAssembly not supported in this browser');
        return;
      }

      // Warn if SharedArrayBuffer is not available (affects performance but not functionality)
      if (!config.sharedArrayBufferAvailable) {
        console.warn('SharedArrayBuffer not available - model loading may be slower. Make sure COOP/COEP headers are set.');
      }

      setIsSupported(true);
    };

    checkSupport();
  }, []);

  // Load Whisper model
  useEffect(() => {
    const loadModel = async () => {
      if (!isSupported || transciberRef.current) {
        return;
      }

      try {
        setIsModelLoading(true);
        setError(null);

        console.log(`Loading Whisper model: ${model}`);
        console.log('Transformers env config:', {
          allowLocalModels: env.allowLocalModels,
          allowRemoteModels: env.allowRemoteModels,
          remoteHost: env.remoteHost,
          remotePathTemplate: env.remotePathTemplate,
          useBrowserCache: env.useBrowserCache,
        });
        
        // Test if we can reach HuggingFace
        try {
          const testUrl = `${env.remoteHost}/${model}/resolve/main/config.json`;
          console.log('Testing HuggingFace connectivity:', testUrl);
          const testResponse = await fetch(testUrl, { method: 'HEAD' });
          console.log('HuggingFace test response:', testResponse.status, testResponse.statusText);
        } catch (testErr) {
          console.warn('HuggingFace connectivity test failed:', testErr.message);
        }
        
        if (onModelLoading) {
          onModelLoading({ status: 'loading', model });
        }

        // Create transcription pipeline with explicit configuration
        const transcriber = await pipeline('automatic-speech-recognition', model, {
          quantized: true, // Use quantized model for better performance
          progress_callback: (progress) => {
            console.log('Model loading progress:', progress);
            if (onModelLoading) {
              onModelLoading({ status: 'progress', progress });
            }
          },
        });

        transciberRef.current = transcriber;
        setIsModelLoaded(true);
        setIsModelLoading(false);

        console.log('Whisper model loaded successfully');
        
        if (onModelLoading) {
          onModelLoading({ status: 'loaded', model });
        }
      } catch (err) {
        console.error('Error loading Whisper model:', err);
        console.error('Error details:', {
          message: err.message,
          stack: err.stack,
          name: err.name,
        });
        
        setIsModelLoading(false);
        setIsModelLoaded(false);
        
        // Provide more helpful error messages
        let errorMessage = err.message;
        if (err.message.includes('<!doctype') || err.message.includes('not valid JSON')) {
          errorMessage = 'Failed to fetch model files. This may be due to network issues or CORS restrictions. Please check your internet connection and browser console for details.';
        }
        
        setError(`Failed to load model: ${errorMessage}`);
        
        if (onError) {
          onError('model-load-failed', `Failed to load model: ${errorMessage}`);
        }
      }
    };

    loadModel();
  }, [isSupported, model, onModelLoading, onError]);

  // Process audio chunk with Whisper
  const processAudioChunk = useCallback(async (audioBlob) => {
    if (!transciberRef.current || processingRef.current) {
      return;
    }

    try {
      processingRef.current = true;
      console.log('Processing audio chunk:', audioBlob.size, 'bytes');

      // Convert blob to array buffer
      const arrayBuffer = await audioBlob.arrayBuffer();
      
      // Decode audio data
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // Get audio data as Float32Array
      const audioData = audioBuffer.getChannelData(0);
      
      // Transcribe audio
      const result = await transciberRef.current(audioData, {
        language: language,
        task: 'transcribe',
        return_timestamps: false,
      });

      console.log('Transcription result:', result);

      if (result && result.text) {
        const transcribedText = result.text.trim();
        
        if (transcribedText) {
          setTranscript(prev => {
            const newTranscript = prev ? `${prev} ${transcribedText}` : transcribedText;
            
            if (onFinalTranscript) {
              onFinalTranscript(transcribedText);
            }
            
            return newTranscript;
          });
        }
      }

      processingRef.current = false;
    } catch (err) {
      console.error('Error processing audio:', err);
      processingRef.current = false;
      setError(`Transcription failed: ${err.message}`);
      
      if (onError) {
        onError('transcription-failed', `Transcription failed: ${err.message}`);
      }
    }
  }, [language, onFinalTranscript, onError]);

  // Start listening
  const startListening = useCallback(async () => {
    if (!isSupported || !isModelLoaded) {
      const msg = !isSupported 
        ? 'Speech recognition not supported' 
        : 'Model not loaded yet';
      console.warn(`Cannot start listening: ${msg}`);
      setError(msg);
      return;
    }

    if (isListeningRef.current) {
      console.warn('Already listening');
      return;
    }

    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        } 
      });

      streamRef.current = stream;
      audioChunksRef.current = [];

      // Create MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm',
      });

      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        console.log('MediaRecorder stopped');
        
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          audioChunksRef.current = [];
          
          // Process the audio
          await processAudioChunk(audioBlob);
        }

        // Auto-restart if continuous mode
        if (continuous && shouldBeListeningRef.current && !processingRef.current) {
          console.log('Auto-restarting in continuous mode');
          setTimeout(() => {
            if (shouldBeListeningRef.current) {
              startListening();
            }
          }, 100);
        } else {
          setIsListening(false);
          isListeningRef.current = false;
        }
      };

      // Start recording in chunks (every 3 seconds)
      mediaRecorder.start();
      
      // Stop and restart every 3 seconds to process audio
      const recordingInterval = setInterval(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          mediaRecorderRef.current.stop();
          
          // Restart if still listening
          if (shouldBeListeningRef.current) {
            setTimeout(() => {
              if (mediaRecorderRef.current && shouldBeListeningRef.current) {
                audioChunksRef.current = [];
                mediaRecorderRef.current.start();
              }
            }, 100);
          }
        }
      }, 3000);

      // Store interval for cleanup
      mediaRecorderRef.current.recordingInterval = recordingInterval;

      setIsListening(true);
      isListeningRef.current = true;
      shouldBeListeningRef.current = true;
      setError(null);

      console.log('Started listening');
    } catch (err) {
      console.error('Failed to start listening:', err);
      setError(`Failed to start: ${err.message}`);
      setIsListening(false);
      isListeningRef.current = false;
      shouldBeListeningRef.current = false;
      
      if (onError) {
        onError('start-failed', `Failed to start: ${err.message}`);
      }
    }
  }, [isSupported, isModelLoaded, continuous, processAudioChunk, onError]);

  // Stop listening
  const stopListening = useCallback(() => {
    shouldBeListeningRef.current = false;

    if (mediaRecorderRef.current) {
      // Clear recording interval
      if (mediaRecorderRef.current.recordingInterval) {
        clearInterval(mediaRecorderRef.current.recordingInterval);
      }

      if (mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      mediaRecorderRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    setIsListening(false);
    isListeningRef.current = false;
    console.log('Stopped listening');
  }, []);

  // Abort listening (immediate stop)
  const abortListening = useCallback(() => {
    shouldBeListeningRef.current = false;
    processingRef.current = false;
    audioChunksRef.current = [];

    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.recordingInterval) {
        clearInterval(mediaRecorderRef.current.recordingInterval);
      }
      
      try {
        if (mediaRecorderRef.current.state !== 'inactive') {
          mediaRecorderRef.current.stop();
        }
      } catch (err) {
        console.error('Error aborting recorder:', err);
      }
      mediaRecorderRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    setIsListening(false);
    isListeningRef.current = false;
    setInterimTranscript('');
    console.log('Aborted listening');
  }, []);

  // Reset transcript
  const resetTranscript = useCallback(() => {
    console.log('Resetting transcript');
    setTranscript('');
    setInterimTranscript('');
    audioChunksRef.current = [];
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortListening();
    };
  }, [abortListening]);

  return {
    // State
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    isModelLoaded,
    isModelLoading,
    error,
    
    // Controls
    startListening,
    stopListening,
    abortListening,
    resetTranscript,
  };
}

export default useWhisperSTT;


