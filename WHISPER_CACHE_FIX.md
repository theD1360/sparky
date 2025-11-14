# Whisper Model Loading - Cache Fix Instructions

## Problem
Whisper model is getting HTML (`<!doctype`) instead of JSON when trying to load, indicating corrupted cache or network issues.

## Solution Steps

### Step 1: Stop the Dev Server
Press `Ctrl+C` in your terminal to stop the React dev server.

### Step 2: Clear Node Modules Cache
```bash
cd web_ui
rm -rf node_modules/.cache
```

### Step 3: Restart Dev Server
```bash
npm start
```

### Step 4: Clear Browser Caches (CRITICAL!)

Once the app loads in your browser, open DevTools console (F12) and run:

```javascript
// Clear all model-related caches
await window.clearModelCaches()
```

**Expected output:**
```
Found caches: [...]
✓ Deleted cache: workbox-precache-v2-...
✓ Deleted cache: transformers-cache
...
Cache clearing complete: {...}
```

### Step 5: Hard Refresh
After clearing caches:
- Press `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
- Or manually clear browser data:
  - Chrome: Settings → Privacy → Clear browsing data → Cached images and files + Cookies
  - Firefox: Options → Privacy → Cookies and Site Data → Clear Data
  - Safari: Develop → Empty Caches

### Step 6: Test Model Loading

After hard refresh, watch the console for:

```
🧹 Cache utilities loaded. Use window.clearModelCaches() if models fail to load.
Transformers.js environment configured: {...}
Loading Whisper model: Xenova/whisper-base
Testing HuggingFace connectivity: https://huggingface.co/Xenova/whisper-base/resolve/main/config.json
HuggingFace test response: 200 OK
Model loading progress: {status: 'initiate', ...}
Model loading progress: {status: 'download', ...}
Whisper model loaded successfully ✅
```

## If Still Failing

### Check 1: HuggingFace Connectivity
Run in console:
```javascript
fetch('https://huggingface.co/Xenova/whisper-base/resolve/main/config.json')
  .then(r => r.json())
  .then(d => console.log('✓ HuggingFace accessible:', d))
  .catch(e => console.error('✗ HuggingFace blocked:', e))
```

**If this fails:**
- You might be behind a firewall/proxy blocking HuggingFace
- Check your network connection
- Try from different network (mobile hotspot, VPN, etc.)

### Check 2: CORS Issues
Check Network tab in DevTools:
1. Look for requests to `huggingface.co`
2. Check if they return 200 OK or errors
3. Check Response tab to see if it's HTML or JSON

### Check 3: Try Different Model
Smaller model might download more reliably:

```javascript
// In useWhisperSTT hook call, change model to:
model: 'Xenova/whisper-tiny'  // Much smaller, faster to test
```

### Check 4: Check Storage Quota
```javascript
await window.getCacheStatus()
```

Should show available storage. If quota is full, clear more data.

### Check 5: Try Incognito/Private Mode
Open app in incognito window to rule out extension interference.

## Configuration Changes Made

### 1. Disabled Browser Cache
**File:** `web_ui/src/utils/transformersConfig.js`
```javascript
env.useBrowserCache = false;  // Prevent stale cache issues
```

### 2. Removed COEP/COOP Headers
**Files:** `web_ui/src/setupProxy.js`, `web_ui/public/index.html`
- Commented out strict COEP headers that block CDN access
- Trade-off: No SharedArrayBuffer, but models will load

### 3. Added Connectivity Testing
**File:** `web_ui/src/hooks/useWhisperSTT.js`
- Tests HuggingFace connectivity before loading
- Provides detailed diagnostic logging

### 4. Added Cache Utilities
**File:** `web_ui/src/utils/clearModelCache.js`
- `window.clearModelCaches()` - Clear all caches
- `window.getCacheStatus()` - Check cache status

## Debugging Commands

### Clear Everything
```javascript
// Run all in sequence
await window.clearModelCaches();
localStorage.clear();
sessionStorage.clear();
location.reload();
```

### Check What's Cached
```javascript
const status = await window.getCacheStatus();
console.log('Caches:', status.caches);
console.log('Storage:', status.storage);
```

### Manual Model URL Test
```javascript
// Test the exact URL transformers.js will use
const testUrls = [
  'https://huggingface.co/Xenova/whisper-base/resolve/main/config.json',
  'https://huggingface.co/Xenova/whisper-base/resolve/main/tokenizer.json',
  'https://huggingface.co/Xenova/whisper-base/resolve/main/preprocessor_config.json',
];

for (const url of testUrls) {
  try {
    const response = await fetch(url);
    const data = await response.json();
    console.log(`✓ ${url.split('/').pop()}: OK`);
  } catch (err) {
    console.error(`✗ ${url.split('/').pop()}: FAILED`, err.message);
  }
}
```

## Alternative: Use Tiny Model for Testing

If Whisper-base keeps failing, use tiny model temporarily:

**File:** `web_ui/src/components/chat/SpeechInput.js` (or wherever useWhisperSTT is called)
```javascript
const { ... } = useWhisperSTT({
  model: 'Xenova/whisper-tiny',  // Only 39MB vs 142MB for base
  language: 'en',
  // ... other options
});
```

Tiny model:
- ✓ Loads faster
- ✓ More reliable download
- ✗ Less accurate transcription

## Network Requirements

Whisper model files to download:
```
config.json           : ~1 KB
tokenizer.json        : ~2 MB
preprocessor_config.json : ~1 KB
model.onnx (quantized): ~140 MB  (whisper-base)
```

**Total:** ~142 MB for whisper-base, ~39 MB for whisper-tiny

## What to Send for Help

If still failing after all steps, provide:

1. **Console output** after running:
```javascript
console.log('Config:', await window.getCacheStatus());
console.log('Transform env:', {
  allowRemoteModels: env.allowRemoteModels,
  remoteHost: env.remoteHost,
  useBrowserCache: env.useBrowserCache
});
```

2. **Network tab screenshot** showing requests to huggingface.co

3. **Full error message** from console

4. **Browser and version** (Chrome 120, Firefox 121, etc.)

5. **Network environment** (home, corporate, VPN, etc.)

## Success Criteria

When working correctly, you should see:
```
Loading Whisper model: Xenova/whisper-base
HuggingFace test response: 200 OK
Model loading progress: {status: 'download', file: 'tokenizer.json'}
Model loading progress: {status: 'progress', loaded: 2048, total: 2048000}
...
Whisper model loaded successfully
```

And the microphone button in the chat should become active!

Good luck! 🎤🤞

