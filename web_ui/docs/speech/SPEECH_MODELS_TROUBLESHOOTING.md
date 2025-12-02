# Speech Models Troubleshooting Guide

This guide helps troubleshoot issues with Whisper STT and VITS TTS model loading.

## Common Issues and Solutions

### 1. Whisper Model Not Loading (Error: "<!doctype" not valid JSON)

**Symptoms:**
- Console error: `SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON`
- Model fails to load
- STT functionality not available

**Causes:**
- Network connectivity issues
- CORS/COEP header configuration problems
- Browser cache corruption
- CDN unavailability

**Solutions:**

#### A. Clear Browser Cache
1. Open browser DevTools (F12)
2. Go to Application/Storage tab
3. Clear all cached data for the site
4. Alternatively, run in console:
```javascript
caches.keys().then(keys => Promise.all(keys.map(key => caches.delete(key))))
```

#### B. Check Network Connectivity
1. Verify you can access https://huggingface.co
2. Check browser console Network tab for failed requests
3. Look for any 404 or CORS errors

#### C. Verify COOP/COEP Headers
1. Open Network tab in DevTools
2. Check the main document headers
3. Should see:
   - `Cross-Origin-Embedder-Policy: credentialless`
   - `Cross-Origin-Opener-Policy: same-origin`

#### D. Check SharedArrayBuffer Availability
Run in browser console:
```javascript
console.log('SharedArrayBuffer available:', typeof SharedArrayBuffer !== 'undefined');
```

If `false`, models will load slower but should still work.

#### E. Restart Development Server
```bash
# Stop the server (Ctrl+C)
# Clear node_modules cache
rm -rf node_modules/.cache
# Restart
npm start
```

### 2. VITS TTS Not Working

**Symptoms:**
- No audio output when TTS is triggered
- Voices not downloading
- "Stored VITS voices: []" in console (this is normal on first run)

**Normal Behavior:**
- First run will show 0 stored voices
- Voices download automatically on first use
- Each voice is ~5-20MB and cached in IndexedDB

**Solutions:**

#### A. Check Browser Support
```javascript
// Run in console
console.log('IndexedDB:', 'indexedDB' in window);
console.log('AudioContext:', 'AudioContext' in window || 'webkitAudioContext' in window);
```

Both should be `true`.

#### B. Check Storage Quota
VITS stores voices in IndexedDB. Check available storage:
```javascript
navigator.storage.estimate().then(estimate => {
  console.log('Storage:', estimate.usage, 'of', estimate.quota, 'bytes');
});
```

#### C. Manually Trigger Voice Download
If auto-download fails, try manually:
```javascript
import * as tts from '@diffusionstudio/vits-web';
await tts.download('en_US-hfc_female-medium', (progress) => {
  console.log(progress);
});
```

### 3. Performance Issues

**Symptoms:**
- Models load very slowly
- High CPU usage during transcription/synthesis
- Browser becomes unresponsive

**Solutions:**

#### A. Verify SharedArrayBuffer
SharedArrayBuffer enables multi-threading for better performance.

Check if available:
```javascript
console.log('SharedArrayBuffer:', typeof SharedArrayBuffer !== 'undefined');
```

If not available, ensure COOP/COEP headers are set correctly (see above).

#### B. Use Smaller Models
For Whisper, try smaller models:
- `Xenova/whisper-tiny` (fastest, less accurate)
- `Xenova/whisper-base` (default, balanced)
- `Xenova/whisper-small` (slower, more accurate)

Change in component:
```javascript
useWhisperSTT({
  model: 'Xenova/whisper-tiny',
  // ... other options
});
```

#### C. Reduce Audio Quality
Lower sample rate for faster processing:
```javascript
navigator.mediaDevices.getUserMedia({
  audio: {
    sampleRate: 16000,  // Lower is faster
    channelCount: 1,    // Mono is faster than stereo
  }
});
```

### 4. Development Server Configuration

The development server requires specific configuration for model loading.

**Check setupProxy.js:**
```javascript
// Should include:
res.setHeader('Cross-Origin-Embedder-Policy', 'credentialless');
res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin');
```

**Check public/index.html:**
```html
<meta http-equiv="Cross-Origin-Embedder-Policy" content="credentialless" />
<meta http-equiv="Cross-Origin-Opener-Policy" content="same-origin" />
```

### 5. Production Deployment

For production, ensure your web server sets the correct headers.

**Nginx Example:**
```nginx
add_header Cross-Origin-Embedder-Policy "credentialless";
add_header Cross-Origin-Opener-Policy "same-origin";
add_header Cross-Origin-Resource-Policy "cross-origin";
```

**Apache Example:**
```apache
Header set Cross-Origin-Embedder-Policy "credentialless"
Header set Cross-Origin-Opener-Policy "same-origin"
Header set Cross-Origin-Resource-Policy "cross-origin"
```

## Debugging Tools

### Check Transformers Configuration
```javascript
import { checkTransformersConfig } from './utils/transformersConfig';
console.log(checkTransformersConfig());
```

### Clear Transformers Cache
```javascript
import { clearTransformersCache } from './utils/transformersConfig';
await clearTransformersCache();
```

### Check Available VITS Voices
```javascript
import * as tts from '@diffusionstudio/vits-web';
const voices = await tts.voices();
console.log('Available voices:', Object.keys(voices));
```

### Check Stored VITS Voices
```javascript
import * as tts from '@diffusionstudio/vits-web';
const stored = await tts.stored();
console.log('Stored voices:', stored);
```

## Browser Compatibility

### Minimum Requirements
- Chrome/Edge 92+
- Firefox 95+
- Safari 16.4+

### Features Requiring COOP/COEP
- SharedArrayBuffer (for multi-threaded WASM)
- Better performance for model loading and inference

### Features Working Without COOP/COEP
- All models will still load and work
- Single-threaded mode (slower)
- Increased latency

## Getting Help

If issues persist:

1. Check browser console for detailed error messages
2. Check Network tab for failed requests
3. Verify internet connectivity to huggingface.co
4. Try in different browser
5. Try in incognito/private mode (rules out extensions)
6. Clear all browser data and retry

## Recent Changes

- Added COOP/COEP headers for SharedArrayBuffer support
- Configured transformers.js for optimal CDN usage
- Improved error messages and logging
- Added automatic fallback for single-threaded mode

