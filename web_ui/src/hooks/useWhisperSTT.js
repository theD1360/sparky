import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook for Whisper-based Speech Recognition (STT)
 * Provides accurate, privacy-friendly speech-to-text using Whisper models
 * 
 * @param {Object} options - Configuration options
 * @param {string} options.model - Whisper model to use (default: 'Xenova/whisper-tiny')
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
    model = 'Xenova/whisper-tiny',
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
  const [isProcessing, setIsProcessing] = useState(false);

  const workerRef = useRef(null);
  const audioContextRef = useRef(null);
  const streamRef = useRef(null);
  const sourceNodeRef = useRef(null);
  const processorNodeRef = useRef(null);
  const audioBufferRef = useRef([]);
  const accumulatedSamplesRef = useRef(new Float32Array(0));
  const isListeningRef = useRef(false);
  const shouldBeListeningRef = useRef(false);
  const processingRef = useRef(false);
  const lastProcessTimeRef = useRef(0);
  const chunkIntervalRef = useRef(null);
  const audioLevelRef = useRef(0);
  const lastAudioLevelUpdateRef = useRef(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const silenceStartTimeRef = useRef(null);
  const isProcessingBufferRef = useRef(false);
  const minAudioDetectedRef = useRef(false); // Track if we've detected meaningful audio
  const lastBufferSendTimeRef = useRef(0);
  const BUFFER_SEND_INTERVAL_MS = 500; // Send audio chunks to worker every 500ms

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

      // Check for WebAssembly support (required for Whisper)
      if (typeof WebAssembly === 'undefined') {
        setIsSupported(false);
        setError('WebAssembly not supported in this browser');
        return;
      }

      // Warn if SharedArrayBuffer is not available (affects performance but not functionality)
      // Model loading happens in worker, so this is just a performance warning
      if (typeof SharedArrayBuffer === 'undefined') {
        console.warn('SharedArrayBuffer not available - model loading may be slower. Make sure COOP/COEP headers are set.');
      } else {
        console.log('✓ SharedArrayBuffer available - multi-threaded WASM enabled');
      }

      setIsSupported(true);
    };

    checkSupport();
  }, []);

  // Initialize Web Worker and load model
  useEffect(() => {
    if (!isSupported) {
      return;
    }

    // Create worker if it doesn't exist
    if (!workerRef.current) {
      try {
        // Create worker from public folder (using consolidated speechWorker)
        const workerUrl = process.env.PUBLIC_URL 
          ? `${process.env.PUBLIC_URL}/speechWorker.js`
          : '/speechWorker.js';
          
        const worker = new Worker(workerUrl, { type: 'module' });
        workerRef.current = worker;

        // Handle worker messages
        worker.onmessage = (event) => {
          const { type, ...data } = event.data;

          switch (type) {
            case 'worker-ready':
            case 'transformers-ready':
              console.log('Speech worker ready');
              // Initialize STT model in worker
              worker.postMessage({
                type: 'stt-init',
                data: { model },
              });
              break;

            case 'stt-status':
              console.log('STT status:', data.message);
              break;

            case 'stt-progress':
              console.log('STT model loading progress:', data.progress);
              if (onModelLoading) {
                onModelLoading({ status: 'progress', progress: data.progress });
              }
              break;

            case 'stt-model-loaded':
              console.log('Whisper model loaded in worker:', data.model);
              setIsModelLoaded(true);
              setIsModelLoading(false);
              if (onModelLoading) {
                onModelLoading({ status: 'loaded', model: data.model });
              }
              break;

            case 'stt-init-result':
              if (data.success) {
                console.log('STT model initialized in worker');
                setIsModelLoaded(true);
                setIsModelLoading(false);
              } else {
                console.error('Failed to initialize STT model in worker:', data.error);
                setError(`Failed to load model: ${data.error}`);
                setIsModelLoading(false);
                setIsModelLoaded(false);
              }
              break;

            case 'stt-processing':
              console.log(`Worker processing ${data.duration}s of audio...`);
              setIsProcessing(true);
              if (onInterimTranscript) {
                onInterimTranscript('...');
              }
              break;

            case 'stt-result':
              console.log(`✅ Transcription complete: "${data.text.substring(0, 50)}..." (${data.processTime}ms)`);
              
              processingRef.current = false;
              setIsProcessing(false);
              isProcessingBufferRef.current = false;
              lastProcessTimeRef.current = Date.now();
              
              if (data.text) {
                const transcribedText = data.text.trim();
                if (transcribedText) {
                  // Update transcript
                  setTranscript(prev => {
                    const newTranscript = prev ? `${prev} ${transcribedText}` : transcribedText;
                    
                    if (onFinalTranscript) {
                      onFinalTranscript(transcribedText);
                    }
                    
                    return newTranscript;
                  });

                  if (onInterimTranscript) {
                    onInterimTranscript(transcribedText);
                  }
                }
              }
              break;

            case 'stt-error':
              console.error('STT worker error:', data.error);
              processingRef.current = false;
              isProcessingBufferRef.current = false; // Reset buffer processing flag
              setIsProcessing(false);
              
              if (data.isMemoryError) {
                setError('Memory error - please try shorter recordings or restart the browser');
              } else {
                setError(`Transcription failed: ${data.error}`);
              }
              
              if (onError) {
                onError('transcription-failed', data.isMemoryError 
                  ? 'Memory error - try shorter recordings' 
                  : `Transcription failed: ${data.error}`);
              }
              break;

            // Legacy support
            case 'status':
            case 'progress':
            case 'model-loaded':
            case 'init-result':
            case 'processing':
            case 'result':
            case 'error':
              // Handle legacy message types for backward compatibility
              if (type === 'result' || type === 'stt-result') {
                console.log(`✅ Transcription complete: "${data.text?.substring(0, 50)}..." (${data.processTime}ms)`);
                if (data.text) {
                  const transcribedText = data.text.trim();
                  if (transcribedText) {
                    setTranscript(prev => {
                      if (prev && prev.includes(transcribedText)) {
                        return prev;
                      }
                      const newTranscript = prev ? `${prev} ${transcribedText}` : transcribedText;
                      if (onFinalTranscript) {
                        onFinalTranscript(transcribedText);
                      }
                      return newTranscript;
                    });
                    if (onInterimTranscript) {
                      onInterimTranscript(transcribedText);
                    }
                  }
                }
                processingRef.current = false;
                lastProcessTimeRef.current = Date.now();
              }
              break;

            default:
              console.log('Unknown worker message:', type, data);
          }
        };

        worker.onerror = (error) => {
          console.error('Worker error:', error);
          setError(`Worker error: ${error.message}`);
          setIsModelLoading(false);
          setIsModelLoaded(false);
        };

        setIsModelLoading(true);
        setError(null);
        if (onModelLoading) {
          onModelLoading({ status: 'loading', model });
        }
      } catch (err) {
        console.error('Failed to create worker:', err);
        setError(`Failed to initialize worker: ${err.message}`);
        setIsModelLoading(false);
        setIsModelLoaded(false);
        
        if (onError) {
          onError('worker-init-failed', `Failed to initialize worker: ${err.message}`);
        }
      }
    } else {
      // Worker exists, just initialize STT model if needed
      if (!isModelLoaded) {
        workerRef.current.postMessage({
          type: 'stt-init',
          data: { model },
        });
        setIsModelLoading(true);
      }
    }

    // Cleanup worker on unmount or model change
    return () => {
      if (workerRef.current) {
        try {
          workerRef.current.terminate();
        } catch (err) {
          console.error('Error terminating worker:', err);
        }
        workerRef.current = null;
      }
    };
  }, [isSupported, model, onModelLoading, onError, onInterimTranscript, onFinalTranscript, isModelLoaded]);

  // Note: processAudioChunk is no longer used - we buffer audio in worker and process on demand

  // Start listening using Web Audio API for real-time processing
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
      // Request microphone access with optimal settings
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1, // Mono
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          // Note: sampleRate constraint may not be supported by all browsers
        } 
      });

      streamRef.current = stream;
      audioBufferRef.current = [];
      accumulatedSamplesRef.current = new Float32Array(0);

      // Create AudioContext with 16kHz sample rate (Whisper requirement)
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioContext = new AudioContextClass({
        sampleRate: 16000, // Whisper requires 16kHz
      });
      audioContextRef.current = audioContext;

      // Create source from microphone stream
      const source = audioContext.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      // Create ScriptProcessorNode for real-time audio processing
      // Buffer size: 4096 samples = ~0.25 seconds at 16kHz
      const bufferSize = 4096;
      const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
      processorNodeRef.current = processor;

      // Silence detection parameters
      const SILENCE_THRESHOLD = 0.005; // RMS threshold for silence (lower = more sensitive to silence)
      const MIN_AUDIO_LEVEL = 0.02; // Minimum RMS level to consider as "real" audio (filters out background noise)
      const SILENCE_DURATION_MS = 2000; // 2 seconds of silence triggers processing
      const MAX_BUFFER_SIZE = 160000; // Max 10 seconds - safety limit

      processor.onaudioprocess = (event) => {
        if (!shouldBeListeningRef.current || isProcessingBufferRef.current) {
          return;
        }

        // Get audio data from input (mono channel)
        const inputData = event.inputBuffer.getChannelData(0);
        
        // Calculate audio level (RMS) for visual feedback and silence detection
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        const level = Math.min(1, rms * 15); // Scale and clamp to 0-1
        audioLevelRef.current = level;
        
        // Update audio level state (throttle to ~20fps to avoid too many re-renders)
        const now = Date.now();
        if (now - lastAudioLevelUpdateRef.current > 50) {
          setAudioLevel(level);
          lastAudioLevelUpdateRef.current = now;
        }
        
        // Detect meaningful audio vs silence from mic input
        const isSilent = rms < SILENCE_THRESHOLD;
        const hasMeaningfulAudio = rms >= MIN_AUDIO_LEVEL;
        const currentSamples = accumulatedSamplesRef.current;
        
        // Track if we've detected meaningful audio (not just background noise)
        if (hasMeaningfulAudio) {
          minAudioDetectedRef.current = true;
          
          // Send audio chunks to worker for buffering (not processing yet)
          // Worker will accumulate these chunks until we send a process event
          // Throttle to avoid sending too frequently
          if (workerRef.current && isModelLoaded && currentSamples.length > 0) {
            const timeSinceLastBuffer = now - lastBufferSendTimeRef.current;
            if (timeSinceLastBuffer >= BUFFER_SEND_INTERVAL_MS) {
              // Send chunks periodically to worker for buffering
              // Use a sliding window - send last 1 second of audio every 0.5 seconds
              const bufferWindowSize = Math.min(16000, currentSamples.length); // Last 1 second
              const bufferWindow = currentSamples.slice(-bufferWindowSize);
              
              const audioCopy = new Float32Array(bufferWindow);
              workerRef.current.postMessage({
                type: 'stt-buffer',
                data: {
                  audioData: audioCopy,
                },
              }, [audioCopy.buffer]);
              
              lastBufferSendTimeRef.current = now;
            }
          }
        }
        
        if (isSilent) {
          // Mic is silent - track how long it's been silent
          // Only start tracking if we have audio in buffer AND we've detected real audio first
          if (silenceStartTimeRef.current === null && currentSamples.length > 0 && minAudioDetectedRef.current) {
            silenceStartTimeRef.current = now;
            console.log('Mic silent after speech detected, starting 2s timer...');
          } else if (silenceStartTimeRef.current !== null) {
            // Check if mic has been silent for 2 seconds
            const silenceDuration = now - silenceStartTimeRef.current;
            if (silenceDuration >= SILENCE_DURATION_MS && currentSamples.length > 0 && minAudioDetectedRef.current) {
              // Mic has been silent for 2 seconds - process the accumulated audio
              const audioDuration = currentSamples.length / 16000;
              if (audioDuration >= 1.0) {
                console.log(`Mic silent for 2s, sending process event to worker for ${audioDuration.toFixed(2)}s of buffered audio...`);
                
                // Send final chunk to worker and then request processing
                if (workerRef.current && isModelLoaded) {
                  // Send the remaining accumulated audio to worker
                  const finalChunk = currentSamples.slice();
                  workerRef.current.postMessage({
                    type: 'stt-buffer',
                    data: {
                      audioData: new Float32Array(finalChunk),
                    },
                  }, [finalChunk.buffer]);
                  
                  // Clear local buffer
                  accumulatedSamplesRef.current = new Float32Array(0);
                  silenceStartTimeRef.current = null;
                  minAudioDetectedRef.current = false;
                  
                  // Now tell worker to process all buffered audio
                  // Loading indicator will show when processing starts (handled in worker message handler)
                  isProcessingBufferRef.current = true;
                  setIsProcessing(true);
                  
                  workerRef.current.postMessage({
                    type: 'stt-process-buffer',
                    data: {
                      language: language,
                    },
                  });
                } else {
                  // Fallback: clear buffer if worker not ready
                  accumulatedSamplesRef.current = new Float32Array(0);
                  silenceStartTimeRef.current = null;
                  minAudioDetectedRef.current = false;
                }
              } else {
                // Discard buffer if it's too short (likely just noise)
                console.log(`Discarding short buffer (${audioDuration.toFixed(2)}s) - likely background noise`);
                accumulatedSamplesRef.current = new Float32Array(0);
                silenceStartTimeRef.current = null;
                minAudioDetectedRef.current = false;
                
                // Clear worker buffer too
                if (workerRef.current) {
                  workerRef.current.postMessage({
                    type: 'stt-clear-buffer',
                  });
                }
              }
              return; // Don't accumulate this silent chunk
            }
          }
        } else {
          // Mic is receiving audio - reset silence timer
          if (silenceStartTimeRef.current !== null) {
            console.log('Mic receiving audio again, canceling silence timer');
            silenceStartTimeRef.current = null;
          }
        }
        
        // Accumulate samples (only if not silent, or if we're still in the silence window)
        // Always accumulate to build up the buffer
        if (currentSamples.length + inputData.length > MAX_BUFFER_SIZE) {
          // Safety: if buffer is too large, drop oldest samples
          const keepSize = MAX_BUFFER_SIZE - inputData.length;
          const keptSamples = currentSamples.slice(-keepSize); // Keep most recent
          const newSamples = new Float32Array(keptSamples.length + inputData.length);
          newSamples.set(keptSamples);
          newSamples.set(inputData, keptSamples.length);
          accumulatedSamplesRef.current = newSamples;
          console.warn('Audio buffer limit reached, dropping old samples');
        } else {
          const newSamples = new Float32Array(currentSamples.length + inputData.length);
          newSamples.set(currentSamples);
          newSamples.set(inputData, currentSamples.length);
          accumulatedSamplesRef.current = newSamples;
        }
      };

      // Connect audio nodes
      source.connect(processor);
      processor.connect(audioContext.destination); // Connect to output to avoid errors

      // Safety check: if buffer gets too large without silence, force process
      // This prevents memory issues if silence detection fails
      chunkIntervalRef.current = setInterval(() => {
        if (!shouldBeListeningRef.current || isProcessingBufferRef.current) {
          return;
        }
        
        const bufferLength = accumulatedSamplesRef.current.length;
        const bufferDuration = bufferLength / 16000;
        
        // Safety: if buffer exceeds 10 seconds, force process (shouldn't happen normally)
        if (bufferDuration > 10) {
          console.warn(`Buffer exceeded 10s (${bufferDuration.toFixed(2)}s), forcing processing`);
          
          if (workerRef.current && isModelLoaded) {
            // Send final chunk to worker and then request processing
            const finalChunk = accumulatedSamplesRef.current.slice();
            workerRef.current.postMessage({
              type: 'stt-buffer',
              data: {
                audioData: new Float32Array(finalChunk),
              },
            }, [finalChunk.buffer]);
            
            // Clear local buffer
            accumulatedSamplesRef.current = new Float32Array(0);
            silenceStartTimeRef.current = null;
            minAudioDetectedRef.current = false;
            
            // Now tell worker to process all buffered audio
            isProcessingBufferRef.current = true;
            setIsProcessing(true);
            
            workerRef.current.postMessage({
              type: 'stt-process-buffer',
              data: {
                language: language,
              },
            });
          } else {
            // Fallback: clear buffer if worker not ready
            accumulatedSamplesRef.current = new Float32Array(0);
            silenceStartTimeRef.current = null;
            minAudioDetectedRef.current = false;
          }
        }
      }, 1000); // Check every second for safety

      setIsListening(true);
      isListeningRef.current = true;
      shouldBeListeningRef.current = true;
      setError(null);
      setTranscript(''); // Reset transcript when starting fresh
      setInterimTranscript('');
      setAudioLevel(0); // Reset audio level
      audioLevelRef.current = 0;
      silenceStartTimeRef.current = null;
      isProcessingBufferRef.current = false;
      minAudioDetectedRef.current = false;

      console.log('Started listening with Web Audio API (16kHz, real-time)');
    } catch (err) {
      console.error('Failed to start listening:', err);
      setError(`Failed to start: ${err.message}`);
      setIsListening(false);
      isListeningRef.current = false;
      shouldBeListeningRef.current = false;
      
      // Cleanup on error
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(console.error);
        audioContextRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      
      if (onError) {
        onError('start-failed', `Failed to start: ${err.message}`);
      }
    }
  }, [isSupported, isModelLoaded, language, onError]);

  // Stop listening
  const stopListening = useCallback(() => {
    shouldBeListeningRef.current = false;

    // Clear processing interval
    if (chunkIntervalRef.current) {
      clearInterval(chunkIntervalRef.current);
      chunkIntervalRef.current = null;
    }

    // Clear worker STT queue
    if (workerRef.current) {
      try {
        workerRef.current.postMessage({ type: 'stt-clear-queue' });
      } catch (err) {
        console.error('Error clearing STT queue:', err);
      }
    }

    // Disconnect audio nodes
    if (processorNodeRef.current) {
      try {
        processorNodeRef.current.disconnect();
      } catch (err) {
        console.error('Error disconnecting processor:', err);
      }
      processorNodeRef.current = null;
    }

    if (sourceNodeRef.current) {
      try {
        sourceNodeRef.current.disconnect();
      } catch (err) {
        console.error('Error disconnecting source:', err);
      }
      sourceNodeRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(console.error);
      audioContextRef.current = null;
    }

    // Stop microphone stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Clear audio buffers
    audioBufferRef.current = [];
    accumulatedSamplesRef.current = new Float32Array(0);
    setAudioLevel(0);
    audioLevelRef.current = 0;
    processingRef.current = false;
    setIsProcessing(false);
    silenceStartTimeRef.current = null;
    isProcessingBufferRef.current = false;
    minAudioDetectedRef.current = false;

    setIsListening(false);
    isListeningRef.current = false;
    console.log('Stopped listening');
  }, []);

  // Abort listening (immediate stop)
  const abortListening = useCallback(() => {
    shouldBeListeningRef.current = false;
    processingRef.current = false;
    audioBufferRef.current = [];
    accumulatedSamplesRef.current = new Float32Array(0);
    
    // Clear worker STT queue
    if (workerRef.current) {
      try {
        workerRef.current.postMessage({ type: 'stt-clear-queue' });
      } catch (err) {
        console.error('Error clearing STT queue:', err);
      }
    }

    // Clear processing interval
    if (chunkIntervalRef.current) {
      clearInterval(chunkIntervalRef.current);
      chunkIntervalRef.current = null;
    }

    // Disconnect audio nodes
    if (processorNodeRef.current) {
      try {
        processorNodeRef.current.disconnect();
      } catch (err) {
        console.error('Error disconnecting processor:', err);
      }
      processorNodeRef.current = null;
    }

    if (sourceNodeRef.current) {
      try {
        sourceNodeRef.current.disconnect();
      } catch (err) {
        console.error('Error disconnecting source:', err);
      }
      sourceNodeRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(console.error);
      audioContextRef.current = null;
    }

    // Stop microphone stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    setIsListening(false);
    isListeningRef.current = false;
    setInterimTranscript('');
    setAudioLevel(0);
    audioLevelRef.current = 0;
    silenceStartTimeRef.current = null;
    isProcessingBufferRef.current = false;
    minAudioDetectedRef.current = false;
    console.log('Aborted listening');
  }, []);

  // Reset transcript
  const resetTranscript = useCallback(() => {
    console.log('Resetting transcript');
    setTranscript('');
    setInterimTranscript('');
    audioBufferRef.current = [];
    accumulatedSamplesRef.current = new Float32Array(0);
    silenceStartTimeRef.current = null;
    isProcessingBufferRef.current = false;
    minAudioDetectedRef.current = false;
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
    isProcessing, // True when processing/transcribing audio
    error,
    audioLevel, // Audio input level (0-1) for visual feedback
    
    // Controls
    startListening,
    stopListening,
    abortListening,
    resetTranscript,
  };
}

export default useWhisperSTT;


