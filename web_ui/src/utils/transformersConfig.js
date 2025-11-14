import { env } from '@xenova/transformers';

/**
 * Configure transformers.js environment for optimal performance
 * This should be called once at app startup
 */
export function configureTransformers() {
  // Use local models if available, otherwise fall back to CDN
  env.allowLocalModels = false;
  
  // Use remote models from Hugging Face CDN
  env.allowRemoteModels = true;
  
  // Disable browser cache to avoid stale/corrupt cached data
  env.useBrowserCache = false;
  
  // Use the HuggingFace CDN with explicit configuration
  env.remoteHost = 'https://huggingface.co';
  env.remotePathTemplate = '{model}/resolve/{revision}/';
  
  // Use CDN for faster model downloads
  env.backends = env.backends || {};
  env.backends.onnx = env.backends.onnx || {};
  env.backends.onnx.wasm = env.backends.onnx.wasm || {};
  
  // Configure WASM backend
  try {
    // Check if we have SharedArrayBuffer (requires COOP/COEP headers)
    const hasSharedArrayBuffer = typeof SharedArrayBuffer !== 'undefined';
    
    if (!hasSharedArrayBuffer) {
      console.warn('SharedArrayBuffer not available. This may affect performance.');
      console.warn('To enable SharedArrayBuffer, ensure COOP and COEP headers are set correctly.');
    }
    
    // Set WASM threading based on SharedArrayBuffer availability
    if (env.backends && env.backends.onnx && env.backends.onnx.wasm) {
      env.backends.onnx.wasm.numThreads = hasSharedArrayBuffer ? 4 : 1;
      console.log(`WASM threads configured: ${env.backends.onnx.wasm.numThreads}`);
    }
  } catch (err) {
    console.warn('Could not configure WASM backend:', err);
  }
  
  console.log('Transformers.js environment configured:', {
    allowLocalModels: env.allowLocalModels,
    allowRemoteModels: env.allowRemoteModels,
    useBrowserCache: env.useBrowserCache,
    remoteHost: env.remoteHost,
    sharedArrayBufferAvailable: typeof SharedArrayBuffer !== 'undefined',
  });
}

/**
 * Clear the transformers cache
 * Useful for troubleshooting or when models fail to load
 */
export async function clearTransformersCache() {
  try {
    if ('caches' in window) {
      const cacheNames = await caches.keys();
      const transformersCaches = cacheNames.filter(name => 
        name.includes('transformers') || name.includes('onnx')
      );
      
      for (const cacheName of transformersCaches) {
        await caches.delete(cacheName);
        console.log(`Deleted cache: ${cacheName}`);
      }
      
      console.log('Transformers cache cleared');
      return true;
    }
    return false;
  } catch (err) {
    console.error('Error clearing transformers cache:', err);
    return false;
  }
}

/**
 * Check if transformers is properly configured
 */
export function checkTransformersConfig() {
  return {
    browserCacheAvailable: 'caches' in window,
    sharedArrayBufferAvailable: typeof SharedArrayBuffer !== 'undefined',
    webAssemblyAvailable: typeof WebAssembly !== 'undefined',
    audioContextAvailable: 'AudioContext' in window || 'webkitAudioContext' in window,
  };
}

