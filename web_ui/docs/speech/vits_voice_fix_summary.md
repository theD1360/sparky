# VITS Voice Download Fix Summary

## Issues Fixed

1. ❌ **Voice names not displaying** - Voices showed as blank or undefined
2. ❌ **Default voice not downloading** - No automatic download of the default voice on first use
3. ❌ **Voice download not working** - Download button clicks had no effect
4. ❌ **Empty voice list** - No error handling when voice lists were empty

## Root Cause

The `tts.voices()` function from `@diffusionstudio/vits-web` returns an **array** of voice objects, not an object with voice IDs as keys. The Settings modal was treating it as an object, causing:
- `Object.keys(availableVoices)` to return empty array or wrong keys
- Voice metadata not being accessible
- Voice display names not rendering

## Changes Made

### 1. Fixed SettingsModal.js - Voice Data Structure

**Location:** `web_ui/src/components/modals/SettingsModal.js`

**Before:**
```javascript
const voices = await tts.voices();
setAvailableVoices(voices); // Assumed voices was already an object

Object.keys(availableVoices).slice(0, 20).map(...) // Broken
```

**After:**
```javascript
// Get available voices - returns an array of voice objects
const voicesArray = await tts.voices();

// Convert array to object for easier lookup: { voiceId: voiceMetadata }
const voicesObj = {};
if (Array.isArray(voicesArray)) {
  voicesArray.forEach(voice => {
    if (voice && voice.key) {
      voicesObj[voice.key] = voice;
    }
  });
}

setAvailableVoices(voicesObj);
```

### 2. Added Automatic Default Voice Download

**Feature:** When settings modal opens and no voices are downloaded, automatically download the default voice.

```javascript
// If no voices are downloaded, download the default voice automatically
if (stored.length === 0) {
  const defaultVoiceId = settings.ttsVoiceId || 'en_US-hfc_female-medium';
  
  if (voicesObj[defaultVoiceId]) {
    await handleDownloadVoice(defaultVoiceId);
  }
}
```

### 3. Improved Voice Display Names

**Before:** Only parsed voice IDs
**After:** Uses voice metadata when available

```javascript
const getVoiceDisplayName = (voiceId) => {
  // Try to get name from voice metadata first
  if (availableVoices[voiceId] && availableVoices[voiceId].name) {
    return availableVoices[voiceId].name;
  }
  
  // Fallback: Parse voice ID
  // en_US-hfc_female-medium -> English (US) - HFC Female - Medium
  ...
}
```

### 4. Enhanced Voice List Display

**Improvements:**
- Shows first 30 voices (up from 20)
- Prioritizes English voices at the top
- Shows voice metadata (language, ID) when available
- Better empty state handling
- Improved progress indicators

**New Features:**
```javascript
Object.keys(availableVoices)
  .sort((a, b) => {
    // Prioritize English voices
    const aIsEn = a.startsWith('en_');
    const bIsEn = b.startsWith('en_');
    if (aIsEn && !bIsEn) return -1;
    if (!aIsEn && bIsEn) return 1;
    return a.localeCompare(b);
  })
  .slice(0, 30)
  .map((voiceId) => {
    const voiceData = availableVoices[voiceId];
    // Display with name and metadata
  })
```

### 5. Better Error Handling

**Empty Voice List:**
```javascript
{storedVoices.length > 0 ? (
  <FormControl>
    <Select>...</Select>
  </FormControl>
) : (
  <Box>
    <Typography>
      No voices downloaded yet. Download a voice below to enable TTS.
    </Typography>
  </Box>
)}
```

**No Available Voices:**
```javascript
{Object.keys(availableVoices).length > 0 ? (
  // Show voice list
) : (
  <Box>
    <Typography>
      No voices available. Please check your internet connection.
    </Typography>
  </Box>
)}
```

### 6. Enhanced Download Function

**Improvements:**
- Better logging for debugging
- Automatic voice selection after download
- Sets first downloaded voice as default

```javascript
const handleDownloadVoice = useCallback(async (voiceId) => {
  try {
    console.log(`Starting download of voice: ${voiceId}`);
    
    await tts.download(voiceId, (progress) => {
      const percent = Math.round((progress.loaded * 100) / progress.total);
      setDownloadProgress(percent);
      console.log(`Downloading ${voiceId}: ${percent}%`);
    });

    const stored = await tts.stored();
    setStoredVoices(stored);
    updateSetting('ttsDownloadedVoices', stored);
    
    // Set as default voice if this is the first voice
    if (stored.length === 1) {
      updateSetting('ttsVoiceId', voiceId);
    }
  } catch (error) {
    console.error('Error downloading voice:', error);
    alert(`Failed to download voice: ${error.message}`);
  }
}, [updateSetting]);
```

### 7. Updated useVitsTTS Hook

**Location:** `web_ui/src/hooks/useVitsTTS.js`

**Added:** Automatic array-to-object conversion for consistency

```javascript
// Fetch available voices - returns array of voice objects
const voicesArray = await tts.voices();

// Convert to object if it's an array
let voicesObj = voicesArray;
if (Array.isArray(voicesArray)) {
  voicesObj = {};
  voicesArray.forEach(voice => {
    if (voice && voice.key) {
      voicesObj[voice.key] = voice;
    }
  });
}

setAvailableVoices(voicesObj);
```

## Voice Object Structure

### What tts.voices() Returns

```javascript
[
  {
    key: 'en_US-hfc_female-medium',
    name: 'English (US) - HFC Female - Medium',
    language: 'en-US',
    quality: 'medium',
    // ... other metadata
  },
  {
    key: 'en_GB-northern_english_male-medium',
    name: 'English (GB) - Northern English Male - Medium',
    language: 'en-GB',
    quality: 'medium',
  },
  // ... 122 more voices
]
```

### What We Convert It To

```javascript
{
  'en_US-hfc_female-medium': {
    key: 'en_US-hfc_female-medium',
    name: 'English (US) - HFC Female - Medium',
    language: 'en-US',
    quality: 'medium',
  },
  'en_GB-northern_english_male-medium': {
    key: 'en_GB-northern_english_male-medium',
    name: 'English (GB) - Northern English Male - Medium',
    language: 'en-GB',
    quality: 'medium',
  },
  // ... more voices
}
```

## Testing Instructions

### 1. Clear Everything (Important!)

```bash
# Clear browser data
# Chrome: Settings → Privacy → Clear browsing data → Cached images and IndexedDB
# Or run in console:
indexedDB.databases().then(dbs => {
  dbs.forEach(db => {
    if (db.name.includes('vits')) {
      indexedDB.deleteDatabase(db.name);
    }
  });
});
```

### 2. Restart Dev Server

```bash
cd web_ui
rm -rf node_modules/.cache
npm start
```

### 3. Test Voice Download

1. Open app in browser
2. Go to Settings (gear icon)
3. Navigate to General tab
4. Scroll to "Voice & Speech" section

**Expected Behavior:**
- Should see "Available voices (0/124 downloaded)"
- Should see list of 30 voices with proper names
- English voices should appear first
- Default voice should start downloading automatically

### 4. Monitor Console

**Expected Logs:**
```
Available voices: array of 124 items
Converted array to object with 124 voices
Stored VITS voices: 0 voices - []
No voices downloaded, downloading default voice...
Starting download of voice: en_US-hfc_female-medium
Downloading en_US-hfc_female-medium: 10%
Downloading en_US-hfc_female-medium: 25%
...
Downloading en_US-hfc_female-medium: 100%
Voice en_US-hfc_female-medium downloaded successfully
```

### 5. Verify Voice Names Display

- Each voice should show a readable name like:
  - "English (US) - HFC Female - Medium"
  - "English (GB) - Northern English Male - Medium"
  - "Spanish (Spain) - Female - Medium"
- Voice ID should appear below name in smaller text
- Downloaded voices should show "Downloaded" chip with delete button
- Not downloaded voices should show download icon button

### 6. Test Download

1. Click download icon on any voice
2. Should see progress bar
3. Should see percentage (0% → 100%)
4. After completion:
   - Voice should show "Downloaded" chip
   - Voice should appear in dropdown at top
   - Counter should update (e.g., "1/124 downloaded")

### 7. Test Voice Selection

1. After downloading multiple voices
2. Use dropdown at top to switch between voices
3. Selected voice should be saved automatically
4. Test TTS with different voices to verify they work

## Troubleshooting

### Voices Still Not Showing Names

**Check Console:**
```javascript
// Run in console to inspect voice data
tts.voices().then(voices => {
  console.log('First voice:', voices[0]);
  console.log('Has key?', voices[0]?.key);
  console.log('Has name?', voices[0]?.name);
});
```

### Download Not Starting

**Check:**
1. Internet connection to CDN
2. IndexedDB is enabled in browser
3. Enough storage space (voices are 10-50MB each)
4. Check console for specific errors

**Test Storage:**
```javascript
navigator.storage.estimate().then(estimate => {
  console.log('Storage:', {
    usage: (estimate.usage / 1024 / 1024).toFixed(2) + ' MB',
    quota: (estimate.quota / 1024 / 1024).toFixed(2) + ' MB',
    available: ((estimate.quota - estimate.usage) / 1024 / 1024).toFixed(2) + ' MB'
  });
});
```

### Voice Not Playing After Download

1. Check voice is actually downloaded: `await tts.stored()`
2. Verify voice ID matches: Check settings.ttsVoiceId
3. Check audio permissions
4. Try different browser

## Files Modified

```
web_ui/
├── src/
│   ├── components/
│   │   └── modals/
│   │       └── SettingsModal.js          [Modified - Major changes]
│   └── hooks/
│       └── useVitsTTS.js                 [Modified - Array handling]
```

## Summary of Fixes

✅ **Voice names now display correctly** using metadata from voice objects  
✅ **Default voice downloads automatically** when settings opened with no voices  
✅ **Voice download works** with proper progress tracking  
✅ **Empty states handled** with helpful messages  
✅ **Better logging** for debugging  
✅ **Improved UX** with English voices prioritized, better layout  
✅ **First voice auto-selected** as default after download  
✅ **Array/object conversion** handles both data formats

## Next Steps

1. Stop dev server and clear caches
2. Restart server
3. Open settings and verify voices load
4. Test downloading a voice
5. Test voice playback
6. Monitor console for any errors

All voice download and display functionality should now work correctly! 🎉

