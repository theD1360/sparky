/* eslint-disable no-restricted-globals */
/**
 * Web Worker for Speech Processing (STT and TTS)
 * Handles both Whisper STT and VITS TTS in a single worker
 * Loads transformers and VITS from CDN since workers can't easily use npm modules
 * Note: 'self' is the global scope in Web Workers, not a restricted global
 */

/**
 * SpeechProcessor class to handle both STT and TTS operations
 */
class SpeechProcessor {
  constructor() {
    // STT (Whisper) state
    this.transcriber = null;
    this.currentSTTModel = null;
    this.isProcessingSTT = false;
    this.sttProcessingQueue = [];
    this.MAX_STT_QUEUE_SIZE = 2;
    this.sttAudioBuffer = []; // Buffer for accumulating audio chunks before processing
    
    // TTS (VITS) state
    this.ttsModule = null;
    this.currentVoiceId = null;
    this.isProcessingTTS = false;
    this.ttsProcessingQueue = [];
    this.MAX_TTS_QUEUE_SIZE = 2;
    
    // Module references
    this.transformersModule = null;
    this.pendingMessages = [];
  }

  /**
   * Initialize STT model (Whisper)
   */
  async initializeSTT(modelName, transformersModule) {
    if (!transformersModule) {
      throw new Error('Transformers module not loaded');
    }
    
    const { pipeline } = transformersModule;
    
    if (this.transcriber && this.currentSTTModel === modelName) {
      return { success: true };
    }
    
    try {
      self.postMessage({ type: 'stt-status', message: `Loading STT model: ${modelName}` });
      this.transcriber = await pipeline('automatic-speech-recognition', modelName, {
        quantized: true,
        progress_callback: (progress) => {
          self.postMessage({ 
            type: 'stt-progress', 
            progress: { ...progress, model: modelName }
          });
        },
      });
      this.currentSTTModel = modelName;
      self.postMessage({ type: 'stt-model-loaded', model: modelName });
      return { success: true };
    } catch (error) {
      self.postMessage({ type: 'stt-error', error: `Failed to load STT model: ${error.message}` });
      return { success: false, error: error.message };
    }
  }

  /**
   * Buffer audio chunk for later processing
   */
  bufferAudio(audioData) {
    // Add audio chunk to buffer
    this.sttAudioBuffer.push(new Float32Array(audioData));
    
    // Limit buffer size to prevent memory issues (max 10 seconds at 16kHz)
    const maxBufferSize = 160000; // 10 seconds
    let totalSize = 0;
    for (let i = this.sttAudioBuffer.length - 1; i >= 0; i--) {
      totalSize += this.sttAudioBuffer[i].length;
      if (totalSize > maxBufferSize) {
        // Remove oldest chunks if buffer too large
        this.sttAudioBuffer.splice(0, i);
        break;
      }
    }
  }

  /**
   * Clear audio buffer
   */
  clearBuffer() {
    this.sttAudioBuffer = [];
  }

  /**
   * Process all buffered audio
   */
  async processBufferedAudio(language = 'en') {
    if (!this.transcriber) throw new Error('STT model not loaded');
    if (this.sttAudioBuffer.length === 0) {
      throw new Error('No audio buffered to process');
    }
    
    if (this.isProcessingSTT) {
      if (this.sttProcessingQueue.length >= this.MAX_STT_QUEUE_SIZE) {
        this.sttProcessingQueue.shift();
      }
      this.sttProcessingQueue.push({ language, isBuffered: true });
      return { queued: true };
    }
    
    return await this.processBufferedAudioInternal(language);
  }

  /**
   * Internal processing of buffered audio
   */
  async processBufferedAudioInternal(language) {
    this.isProcessingSTT = true;
    
    try {
      // Concatenate all buffered audio chunks
      let totalLength = 0;
      for (const chunk of this.sttAudioBuffer) {
        totalLength += chunk.length;
      }
      
      const concatenatedAudio = new Float32Array(totalLength);
      let offset = 0;
      for (const chunk of this.sttAudioBuffer) {
        concatenatedAudio.set(chunk, offset);
        offset += chunk.length;
      }
      
      // Clear buffer after concatenating
      this.sttAudioBuffer = [];
      
      // Allow up to 10 seconds for better accuracy (Whisper works better with longer audio)
      const maxChunkSize = 160000; // 10 seconds at 16kHz
      const audioToProcess = concatenatedAudio.length > maxChunkSize 
        ? concatenatedAudio.slice(0, maxChunkSize) 
        : concatenatedAudio;
      
      self.postMessage({ 
        type: 'stt-processing', 
        duration: (audioToProcess.length / 16000).toFixed(2) 
      });
      
      const startTime = Date.now();
      const result = await this.transcriber(audioToProcess, {
        language: language,
        task: 'transcribe',
        return_timestamps: false,
        chunk_length_s: Math.min(10, Math.ceil(audioToProcess.length / 16000)),
      });
      
      const processTime = Date.now() - startTime;
      self.postMessage({
        type: 'stt-result',
        text: result?.text || '',
        processTime,
        duration: (audioToProcess.length / 16000).toFixed(2),
      });
      
      // Process next in queue
      if (this.sttProcessingQueue.length > 0) {
        const next = this.sttProcessingQueue.shift();
        setTimeout(() => {
          if (next.isBuffered) {
            this.processBufferedAudioInternal(next.language).catch(() => {
              this.isProcessingSTT = false;
            });
          } else {
            // Legacy support for direct processing (shouldn't be used anymore)
            this.processAudioInternal(next.audioData, next.language).catch(() => {
              this.isProcessingSTT = false;
            });
          }
        }, 50);
      } else {
        this.isProcessingSTT = false;
      }
      
      return { success: true, text: result?.text || '' };
    } catch (error) {
      this.isProcessingSTT = false;
      const isMemoryError = error.message && (
        error.message.includes('memory') || 
        error.message.includes('Memory') ||
        error.message.includes('OOM')
      );
      
      if (isMemoryError) {
        self.postMessage({ 
          type: 'stt-error', 
          error: 'Memory error - audio chunk may be too large. Try shorter phrases.' 
        });
      } else {
        self.postMessage({ 
          type: 'stt-error', 
          error: `STT processing failed: ${error.message}` 
        });
      }
      
      // Process next in queue even on error
      if (this.sttProcessingQueue.length > 0) {
        const next = this.sttProcessingQueue.shift();
        setTimeout(() => {
          if (next.isBuffered) {
            this.processBufferedAudioInternal(next.language).catch(() => {
              this.isProcessingSTT = false;
            });
          } else {
            this.processAudioInternal(next.audioData, next.language).catch(() => {
              this.isProcessingSTT = false;
            });
          }
        }, 50);
      }
      
      throw error;
    }
  }

  /**
   * Legacy: Process audio directly (kept for backwards compatibility)
   */
  async processAudio(audioData, language = 'en') {
    if (!this.transcriber) throw new Error('STT model not loaded');
    if (this.isProcessingSTT) {
      if (this.sttProcessingQueue.length >= this.MAX_STT_QUEUE_SIZE) {
        this.sttProcessingQueue.shift();
      }
      this.sttProcessingQueue.push({ audioData, language });
      return { queued: true };
    }
    return await this.processAudioInternal(audioData, language);
  }

  /**
   * Legacy: Internal audio processing (kept for backwards compatibility)
   */
  async processAudioInternal(audioData, language) {
    this.isProcessingSTT = true;
    try {
      // Allow up to 5 seconds for better accuracy (Whisper works better with longer audio)
      const maxChunkSize = 80000; // 5 seconds at 16kHz
      const audioToProcess = audioData.length > maxChunkSize 
        ? audioData.slice(0, maxChunkSize) 
        : audioData;
      
      self.postMessage({ 
        type: 'stt-processing', 
        duration: (audioToProcess.length / 16000).toFixed(2) 
      });
      
      const startTime = Date.now();
      const result = await this.transcriber(audioToProcess, {
        language: language,
        task: 'transcribe',
        return_timestamps: false,
        chunk_length_s: Math.min(5, Math.ceil(audioToProcess.length / 16000)),
      });
      
      const processTime = Date.now() - startTime;
      self.postMessage({
        type: 'stt-result',
        text: result?.text || '',
        processTime,
        duration: (audioToProcess.length / 16000).toFixed(2),
      });
      
      // Process next in queue
      if (this.sttProcessingQueue.length > 0) {
        const next = this.sttProcessingQueue.shift();
        setTimeout(() => {
          this.processAudioInternal(next.audioData, next.language).catch(() => {
            this.isProcessingSTT = false;
          });
        }, 50);
      } else {
        this.isProcessingSTT = false;
      }
      
      return { success: true, text: result?.text || '' };
    } catch (error) {
      this.isProcessingSTT = false;
      const isMemoryError = error.message && (
        error.message.includes('memory') || 
        error.message.includes('allocation')
      );
      self.postMessage({ 
        type: 'stt-error', 
        error: error.message, 
        isMemoryError 
      });
      if (isMemoryError) this.sttProcessingQueue.length = 0;
      throw error;
    }
  }

  /**
   * Initialize TTS module (VITS)
   */
  async initializeTTS(ttsModule) {
    if (!ttsModule) {
      throw new Error('TTS module not loaded');
    }
    this.ttsModule = ttsModule;
    self.postMessage({ type: 'tts-ready' });
    return { success: true };
  }

  /**
   * Get available voices
   */
  async getVoices() {
    if (!this.ttsModule) {
      throw new Error('TTS module not loaded');
    }
    const voicesArray = await this.ttsModule.voices();
    // Convert array to object for easier lookup
    let voicesObj = voicesArray;
    if (Array.isArray(voicesArray)) {
      voicesObj = {};
      voicesArray.forEach(voice => {
        if (voice && voice.key) {
          voicesObj[voice.key] = voice;
        }
      });
    }
    return voicesObj;
  }

  /**
   * Get stored voices
   */
  async getStoredVoices() {
    if (!this.ttsModule) {
      throw new Error('TTS module not loaded');
    }
    return await this.ttsModule.stored();
  }

  /**
   * Download a voice
   */
  async downloadVoice(voiceId, onProgress) {
    if (!this.ttsModule) {
      throw new Error('TTS module not loaded');
    }
    await this.ttsModule.download(voiceId, (progress) => {
      if (onProgress) {
        self.postMessage({
          type: 'tts-download-progress',
          voiceId,
          progress: {
            loaded: progress.loaded,
            total: progress.total,
            percent: Math.round((progress.loaded * 100) / progress.total),
            url: progress.url,
          },
        });
      }
    });
    const stored = await this.ttsModule.stored();
    self.postMessage({
      type: 'tts-voice-downloaded',
      voiceId,
      stored,
    });
    return { success: true };
  }

  /**
   * Remove a voice
   */
  async removeVoice(voiceId) {
    if (!this.ttsModule) {
      throw new Error('TTS module not loaded');
    }
    await this.ttsModule.remove(voiceId);
    const stored = await this.ttsModule.stored();
    self.postMessage({
      type: 'tts-voice-removed',
      voiceId,
      stored,
    });
    return { success: true };
  }

  /**
   * Clear all voices
   */
  async clearAllVoices() {
    if (!this.ttsModule) {
      throw new Error('TTS module not loaded');
    }
    await this.ttsModule.flush();
    self.postMessage({
      type: 'tts-voices-cleared',
      stored: [],
    });
    return { success: true };
  }

  /**
   * Generate speech from text
   */
  async synthesizeSpeech(text, voiceId, index = 0) {
    if (!this.ttsModule) {
      throw new Error('TTS module not loaded');
    }
    
    if (this.isProcessingTTS) {
      if (this.ttsProcessingQueue.length >= this.MAX_TTS_QUEUE_SIZE) {
        this.ttsProcessingQueue.shift();
      }
      this.ttsProcessingQueue.push({ text, voiceId, index });
      return { queued: true };
    }
    
    return await this.synthesizeSpeechInternal(text, voiceId, index);
  }

  /**
   * Internal speech synthesis
   */
  async synthesizeSpeechInternal(text, voiceId, index = 0) {
    this.isProcessingTTS = true;
    try {
      self.postMessage({ type: 'tts-processing', text: text.substring(0, 50), index });
      
      const startTime = Date.now();
      const wav = await this.ttsModule.predict({
        text: text,
        voiceId: voiceId,
      });
      
      const processTime = Date.now() - startTime;
      
      // Convert Blob to ArrayBuffer for transfer
      const arrayBuffer = await wav.arrayBuffer();
      
      self.postMessage({
        type: 'tts-result',
        audioData: arrayBuffer,
        voiceId,
        index, // Include index for ordering
        processTime,
        textLength: text.length,
      }, [arrayBuffer]); // Transfer ownership
      
      // Process next in queue
      if (this.ttsProcessingQueue.length > 0) {
        const next = this.ttsProcessingQueue.shift();
        setTimeout(() => {
          this.synthesizeSpeechInternal(next.text, next.voiceId, next.index || 0).catch(() => {
            this.isProcessingTTS = false;
          });
        }, 50);
      } else {
        this.isProcessingTTS = false;
      }
      
      return { success: true };
    } catch (error) {
      this.isProcessingTTS = false;
      self.postMessage({ 
        type: 'tts-error', 
        error: error.message,
        index,
      });
      throw error;
    }
  }

  /**
   * Clear STT processing queue
   */
  clearSTTQueue() {
    this.sttProcessingQueue.length = 0;
    self.postMessage({ type: 'stt-queue-cleared' });
  }

  /**
   * Clear TTS processing queue
   */
  clearTTSQueue() {
    this.ttsProcessingQueue.length = 0;
    self.postMessage({ type: 'tts-queue-cleared' });
  }
}

// Create global speech processor instance
const speechProcessor = new SpeechProcessor();

// Load transformers from CDN
const transformersPromise = import('https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js')
  .then((module) => {
    speechProcessor.transformersModule = module;
    const { env } = module;
    
    // Configure transformers
    env.allowLocalModels = false;
    env.allowRemoteModels = true;
    env.useBrowserCache = false;
    env.remoteHost = 'https://huggingface.co';
    env.remotePathTemplate = '{model}/resolve/{revision}/';
    
    return module;
  })
  .catch(error => {
    self.postMessage({ 
      type: 'error', 
      error: `Failed to load transformers: ${error.message}` 
    });
    throw error;
  });

// VITS TTS cannot be loaded in workers due to ES module bare specifier limitations
// VITS uses 'import ... from "onnxruntime-web"' which requires import maps
// Workers don't support import maps, so VITS must be loaded in the main thread
// We'll skip VITS loading here and let the main thread handle it
const vitsPromise = Promise.resolve(null);

// Initialize modules when ready
// Note: VITS is loaded in main thread, not worker (due to ES module limitations)
Promise.all([transformersPromise, vitsPromise])
  .then(async ([transformersModule, vitsModule]) => {
    if (transformersModule) {
      self.postMessage({ type: 'transformers-ready' });
    }
    // VITS is handled in main thread, not worker
    self.postMessage({ type: 'worker-ready' });
    
    // Process any pending messages
    while (speechProcessor.pendingMessages.length > 0) {
      const event = speechProcessor.pendingMessages.shift();
      await handleMessage(event);
    }
  })
  .catch(error => {
    self.postMessage({ 
      type: 'error', 
      error: `Failed to initialize worker: ${error.message}` 
    });
  });

// Message handler
async function handleMessage(event) {
  const { type, data } = event.data;
  
  try {
    // STT operations
    if (type === 'stt-init') {
      const transformersModule = await transformersPromise;
      const result = await speechProcessor.initializeSTT(data.model, transformersModule);
      self.postMessage({ type: 'stt-init-result', ...result });
    } else if (type === 'stt-buffer') {
      // Buffer audio chunk for later processing
      speechProcessor.bufferAudio(data.audioData);
    } else if (type === 'stt-process-buffer') {
      // Process all buffered audio
      await speechProcessor.processBufferedAudio(data.language);
    } else if (type === 'stt-clear-buffer') {
      // Clear audio buffer
      speechProcessor.clearBuffer();
    } else if (type === 'stt-process') {
      // Legacy: Direct processing (kept for backwards compatibility)
      await speechProcessor.processAudio(data.audioData, data.language);
    } else if (type === 'stt-clear-queue') {
      speechProcessor.clearSTTQueue();
    }
    // TTS operations
    else if (type === 'tts-init') {
      const vitsModule = await vitsPromise;
      if (!vitsModule) {
        self.postMessage({ type: 'tts-init-result', success: false, error: 'VITS module not loaded' });
        return;
      }
      const result = await speechProcessor.initializeTTS(vitsModule);
      self.postMessage({ type: 'tts-init-result', ...result });
    } else if (type === 'tts-get-voices') {
      const voices = await speechProcessor.getVoices();
      self.postMessage({ type: 'tts-voices', voices });
    } else if (type === 'tts-get-stored') {
      const stored = await speechProcessor.getStoredVoices();
      self.postMessage({ type: 'tts-stored', stored });
    } else if (type === 'tts-download') {
      await speechProcessor.downloadVoice(data.voiceId, true);
    } else if (type === 'tts-remove') {
      await speechProcessor.removeVoice(data.voiceId);
    } else if (type === 'tts-clear-all') {
      await speechProcessor.clearAllVoices();
    } else if (type === 'tts-synthesize') {
      await speechProcessor.synthesizeSpeech(data.text, data.voiceId, data.index || 0);
    } else if (type === 'tts-clear-queue') {
      speechProcessor.clearTTSQueue();
    }
    // Legacy support (for backward compatibility)
    else if (type === 'init') {
      // Legacy STT init
      const transformersModule = await transformersPromise;
      const result = await speechProcessor.initializeSTT(data.model, transformersModule);
      self.postMessage({ type: 'init-result', ...result });
    } else if (type === 'process') {
      // Legacy STT process
      await speechProcessor.processAudio(data.audioData, data.language);
    } else if (type === 'clear-queue') {
      // Legacy clear queue
      speechProcessor.clearSTTQueue();
    }
  } catch (error) {
    // Determine error type
    const errorType = type.startsWith('stt-') ? 'stt-error' : 
                     type.startsWith('tts-') ? 'tts-error' : 'error';
    self.postMessage({ 
      type: errorType, 
      error: error.message 
    });
  }
}

// Handle messages
self.addEventListener('message', (event) => {
  // If modules aren't ready, queue the message
  const messageType = event.data?.type || '';
  const needsTransformers = messageType.startsWith('stt-') || messageType === 'init' || messageType === 'process';
  const needsVITS = messageType.startsWith('tts-') && messageType !== 'tts-init';
  
  if (needsTransformers && !speechProcessor.transformersModule) {
    speechProcessor.pendingMessages.push(event);
    return;
  }
  
  if (needsVITS && !speechProcessor.ttsModule) {
    speechProcessor.pendingMessages.push(event);
    return;
  }
  
  handleMessage(event);
});

