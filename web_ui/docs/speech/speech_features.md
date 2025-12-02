# Speech Recognition & Synthesis Features

## Overview

The Sparky Studio chat interface supports advanced voice-based conversation features powered by state-of-the-art AI models:
- **Speech-to-Text (STT)**: Accurate speech recognition using OpenAI's Whisper model via @xenova/transformers
- **Text-to-Speech (TTS)**: High-quality voice synthesis using VITS models via @diffusionstudio/vits-web

## Features

### Speech-to-Text (STT) - Whisper
- Click the microphone icon in the input field to start voice input
- Powered by Whisper base model (~140MB, downloaded once)
- Real-time transcription with high accuracy
- Supports multiple languages
- Privacy-friendly: All processing happens locally in your browser
- Automatic speech detection and transcription
- Visual feedback shows when microphone is active
- Model loads automatically on first use

### Text-to-Speech (TTS) - VITS
- Automatically reads assistant responses aloud when enabled
- High-quality neural voice synthesis
- Configurable voice selection (multiple voices per language)
- Download voices on-demand (~10-50MB each)
- Offline capability once voices are downloaded
- Stored locally using browser's Origin Private File System (OPFS)
- Can be enabled/disabled in Settings

## Browser Compatibility

### Speech Recognition (STT) - Whisper via @xenova/transformers

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ Full | Excellent support, recommended |
| Edge | ✅ Full | Chromium-based, fully supported |
| Safari | ✅ Full | Works well on iOS and macOS |
| Firefox | ✅ Full | Full support with transformers.js |
| Opera | ✅ Full | Chromium-based, fully supported |

**Note**: Whisper works in all modern browsers that support WebAssembly and Web Audio API. Unlike the previous Web Speech API, Firefox now has full support!

### Speech Synthesis (TTS) - VITS via @diffusionstudio/vits-web

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ Full | Excellent support with OPFS |
| Edge | ✅ Full | Full support |
| Safari | ✅ Full | Works well, supports OPFS |
| Firefox | ✅ Full | Full support |
| Opera | ✅ Full | Full support |

**Note**: VITS TTS works in all modern browsers with Web Audio API support.

## Supported Languages

The speech features support multiple languages:
- English (US, UK)
- Spanish
- French
- German
- Italian
- Portuguese (Brazil)
- Japanese
- Korean
- Chinese (Simplified)

Language can be configured in **Settings > General > Voice & Speech**.

## Usage Guide

### Enabling Voice Conversation

1. Open **Settings** (gear icon in sidebar)
2. Go to **General** tab
3. Scroll to **Voice & Speech** section
4. Toggle **Auto-speak Responses** to ON
5. Select your preferred **Speech Language**
6. Choose and download your preferred **TTS Voice**

### First-Time Setup

On first use, the system will automatically download:
- **Whisper base model** (~140MB) for speech recognition
- **Default VITS voice** (en_US-hfc_female-medium, ~30MB) for text-to-speech

These models are cached locally, so subsequent uses will be instant.

### Using Voice Input

1. Ensure you're connected to the chat server
2. Wait for Whisper model to load (shown as loading indicator on first use)
3. Click the **microphone icon** in the input field
4. Speak your message clearly
5. Click the **stop icon** when finished
6. Your transcribed text will appear in the input field
7. Message auto-sends after 2 seconds of silence (continuous mode)

### Selecting Different Voices

1. Open **Settings** → **General** → **Voice & Speech**
2. In the **TTS Voice** section, see available voices
3. Click the **download icon** next to any voice to download it
4. Once downloaded, select it from the dropdown
5. The new voice will be used for all subsequent responses

### Visual Indicators

- **Pulsing red microphone**: Actively listening with Whisper
- **Loading spinner**: Whisper model is loading (first use only)
- **Live transcription box**: Shows transcribed text in real-time
- **Gray microphone**: Not listening
- **Disabled microphone**: Model not loaded or not connected
- **Download progress bar**: Voice model downloading in settings

## Error Handling

### Common Errors and Solutions

1. **"Microphone permission was denied"**
   - Solution: Allow microphone access in browser settings
   - Chrome: Settings > Privacy and security > Site Settings > Microphone
   - Safari: System Preferences > Security & Privacy > Microphone
   - Firefox: Preferences > Privacy & Security > Permissions > Microphone

2. **"Failed to load model"**
   - Solution: Check internet connection (needed for first download)
   - Clear browser cache and reload
   - Ensure sufficient storage space (~200MB minimum)

3. **"Voice download failed"**
   - Solution: Check internet connection
   - Try downloading a different voice
   - Clear OPFS storage and retry

4. **"Transcription failed"**
   - Solution: Ensure microphone is working
   - Speak louder or closer to microphone
   - Check that audio input is not muted
   - Try reloading the page to reinitialize model

5. **Model loading stuck**
   - Solution: Reload the page
   - Check browser console for errors
   - Ensure browser supports WebAssembly

## Privacy & Security

### Data Processing
- **All processing happens locally in your browser** - no data sent to external servers
- Whisper model runs entirely client-side using WebAssembly
- VITS TTS generates speech locally using ONNX Runtime
- No audio or transcriptions leave your device
- Models are downloaded once and cached locally
- Transcribed text follows normal chat security policies

### Permissions
- Microphone access required for speech input
- Permission is requested when you first click the microphone
- Can be revoked at any time in browser settings
- Storage permission used for caching models (OPFS)

### Storage Usage
- Whisper base model: ~140MB
- VITS voices: ~10-50MB each
- Models stored in browser's Origin Private File System (OPFS)
- Automatically managed - no manual cleanup needed
- Can remove individual voices in Settings

### Best Practices
- Use in quiet environments for better accuracy
- Speak clearly and at moderate pace
- Allow models to download fully on first use
- Download additional voices when on Wi-Fi
- Disable when not needed to save battery

## Technical Implementation

### Architecture

```
┌─────────────────┐
│  SpeechInput    │  Microphone button & STT UI
│   Component     │
└────────┬────────┘
         │
         ├─> useWhisperSTT Hook
         │   (@xenova/transformers + MediaRecorder)
         │   - Loads Whisper model
         │   - Captures audio via MediaRecorder
         │   - Transcribes with Whisper
         │
         └─> App.js (Message handling)

┌─────────────────┐
│  SpeechOutput   │  TTS playback
│   Component     │
└────────┬────────┘
         │
         └─> useVitsTTS Hook
             (@diffusionstudio/vits-web)
             - Manages voice downloads
             - Generates speech with VITS
             - Plays audio via Audio element
```

### Custom Hooks

1. **useWhisperSTT** (new)
   - Uses @xenova/transformers for Whisper integration
   - Automatic model loading and caching
   - Captures audio using MediaRecorder API
   - Real-time transcription with Whisper
   - Supports multiple languages
   - Progress callbacks for model loading
   - Full browser support (including Firefox!)

2. **useVitsTTS** (new)
   - Uses @diffusionstudio/vits-web for VITS TTS
   - Downloads and caches voice models in OPFS
   - Generates high-quality WAV audio
   - Multiple voice options per language
   - Progress callbacks for voice downloads
   - Voice management (download, remove, list)

3. **useSpeechRecognition** (legacy, deprecated)
   - Old Web Speech API implementation
   - Still available for compatibility

4. **useSpeechSynthesis** (legacy, deprecated)
   - Old Speech Synthesis API implementation
   - Still available for compatibility

### Settings Integration

Speech settings are stored in localStorage and managed by the `useSettings` hook:
- `speechEnabled`: Boolean - Auto-speak responses
- `speechLanguage`: String - Language code (e.g., 'en-US')
- `ttsVoiceId`: String - Selected VITS voice ID
- `ttsDownloadedVoices`: Array - List of downloaded voice IDs
- `sttModel`: String - Whisper model to use (default: 'Xenova/whisper-base')

## Known Limitations

1. **Initial Download Size**
   - First use requires downloading ~140MB Whisper model
   - Each voice is ~10-50MB
   - Requires good internet connection for initial setup
   - Subsequent uses are fully offline

2. **Performance**
   - Model loading takes 5-30 seconds on first use (varies by device)
   - Transcription may be slightly slower than cloud services
   - Older/slower devices may experience delays
   - Battery usage can be higher on mobile devices

3. **Accuracy**
   - Background noise affects recognition quality
   - Whisper is very good but not perfect
   - Accents and dialects generally well-supported
   - Technical terms usually recognized better than Web Speech API

4. **Storage**
   - Requires ~200-500MB of storage space
   - OPFS storage is separate from normal browser cache
   - Storage is persistent across sessions
   - May fill up on devices with limited storage

5. **Browser Compatibility**
   - Requires modern browser with WebAssembly support
   - Requires OPFS support (all modern browsers)
   - Mobile browsers may have memory constraints

## Future Enhancements

Potential improvements for future versions:
- [x] Offline speech recognition ✅ (Whisper)
- [x] Custom voice selection for TTS ✅ (VITS)
- [ ] Voice rate and pitch controls for VITS
- [ ] Whisper model size selection (tiny/small/medium)
- [ ] Voice activation (wake word detection)
- [ ] Multi-language conversation support (real-time translation)
- [ ] Voice commands for chat actions (e.g., "clear chat", "new chat")
- [ ] Audio recording and playback for messages
- [ ] Speaker diarization (identify different speakers)
- [ ] Custom voice training/cloning

## Testing

### Manual Testing Checklist

- [x] STT works in supported browsers
- [x] TTS plays assistant responses
- [x] Settings persist across sessions
- [x] Error messages display correctly
- [x] Microphone permission handling
- [x] Unsupported browser fallback
- [x] Visual indicators work correctly
- [x] Real-time transcription updates
- [x] Multiple language support
- [x] Mobile responsiveness

### Browser Testing

Test in the following browsers:
1. Chrome (latest) - Primary target, excellent WASM performance
2. Edge (latest) - Chromium-based, same as Chrome
3. Safari (latest) - Apple ecosystem, good WASM support
4. Firefox (latest) - Full support now with transformers.js!
5. Mobile Chrome/Safari - Touch interaction, memory constraints

## Support

For issues or questions about speech features:
1. Check browser compatibility above
2. Verify microphone permissions
3. Review error messages in browser console
4. Test with different browsers
5. Contact support with browser version and OS details

## Changelog

### Version 2.0.0 (Current - AI-Powered Speech)
- ✅ Whisper STT via @xenova/transformers
- ✅ VITS TTS via @diffusionstudio/vits-web
- ✅ Voice selection and management UI
- ✅ Offline capability with local models
- ✅ Progress indicators for downloads
- ✅ Privacy-friendly local processing
- ✅ Firefox support (previously unsupported)
- ✅ Voice download management in Settings
- ✅ Multiple voices per language
- ✅ Storage usage display

### Version 1.0.0 (Legacy - Browser APIs)
- ✅ Web Speech API integration for STT
- ✅ Speech Synthesis API integration for TTS
- ✅ Visual microphone button and feedback
- ✅ Settings for speech preferences
- ✅ Multi-language support
- ✅ Error handling and fallbacks
- ✅ Browser compatibility detection

### Migration Notes
- Old hooks (`useSpeechRecognition`, `useSpeechSynthesis`) are deprecated but still available
- New components automatically use new hooks
- Settings migrated automatically
- No breaking changes for existing functionality

