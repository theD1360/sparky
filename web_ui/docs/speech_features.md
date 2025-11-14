# Speech Recognition & Synthesis Features

## Overview

The Sparky Studio chat interface now supports voice-based conversation features, including:
- **Speech-to-Text (STT)**: Speak your messages instead of typing
- **Text-to-Speech (TTS)**: Listen to assistant responses

## Features

### Speech-to-Text (STT)
- Click the microphone icon in the input field to start voice input
- Real-time transcription appears as you speak
- Supports continuous speech recognition
- Transcribed text is added to the input field (no auto-send by default)
- Visual feedback shows when microphone is active

### Text-to-Speech (TTS)
- Automatically reads assistant responses aloud when enabled
- Configurable language and voice settings
- Queue-based playback for multiple messages
- Can be enabled/disabled in Settings

## Browser Compatibility

### Speech Recognition (STT)

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ Full | Best experience, fully supported |
| Edge | ✅ Full | Chromium-based, fully supported |
| Safari | ⚠️ Partial | Supported on iOS 14.5+ and macOS 11+, may have limitations |
| Firefox | ❌ None | Web Speech API not implemented |
| Opera | ✅ Full | Chromium-based, fully supported |

### Speech Synthesis (TTS)

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ Full | Excellent voice quality and selection |
| Edge | ✅ Full | Excellent voice quality, Windows system voices |
| Safari | ✅ Full | Good support, system voices |
| Firefox | ✅ Full | Good support |
| Opera | ✅ Full | Chromium-based voices |

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

### Using Voice Input

1. Ensure you're connected to the chat server
2. Click the **microphone icon** in the input field
3. Speak your message clearly
4. Click the **stop icon** when finished
5. Your transcribed text will appear in the input field
6. Click **Send** or press Enter to send the message

### Visual Indicators

- **Pulsing red microphone**: Actively listening
- **Live transcription box**: Shows transcribed text in real-time
- **Gray microphone**: Not listening
- **Disabled microphone**: Browser not supported or not connected

## Error Handling

### Common Errors and Solutions

1. **"Microphone permission was denied"**
   - Solution: Allow microphone access in browser settings
   - Chrome: Settings > Privacy and security > Site Settings > Microphone
   - Safari: System Preferences > Security & Privacy > Microphone

2. **"Speech recognition not supported in this browser"**
   - Solution: Use Chrome, Edge, or Safari
   - Firefox users: Switch to a supported browser for voice features

3. **"No speech detected"**
   - Solution: Speak louder or check microphone settings
   - Ensure microphone is not muted
   - Try a different microphone if available

4. **"Network error occurred"**
   - Solution: Check internet connection
   - Some browsers require internet for speech recognition

## Privacy & Security

### Data Processing
- Speech recognition uses browser APIs (Web Speech API)
- Chrome/Edge may send audio to Google servers for processing
- No audio is stored by Sparky Studio
- Transcribed text follows normal chat security policies

### Permissions
- Microphone access required for speech input
- Permission is requested per session
- Can be revoked at any time in browser settings

### Best Practices
- Use in quiet environments for better accuracy
- Speak clearly and at moderate pace
- Review transcribed text before sending
- Disable when not needed to save battery

## Technical Implementation

### Architecture

```
┌─────────────────┐
│  SpeechInput    │  Microphone button & STT UI
│   Component     │
└────────┬────────┘
         │
         ├─> useSpeechRecognition Hook
         │   (Web Speech API wrapper)
         │
         └─> App.js (Message handling)

┌─────────────────┐
│  SpeechOutput   │  TTS playback
│   Component     │
└────────┬────────┘
         │
         └─> useSpeechSynthesis Hook
             (Speech Synthesis API wrapper)
```

### Custom Hooks

1. **useSpeechRecognition**
   - Wraps Web Speech API for STT
   - Handles continuous recognition
   - Provides interim and final transcripts
   - Error handling and fallbacks

2. **useSpeechSynthesis**
   - Wraps Speech Synthesis API for TTS
   - Queue-based message playback
   - Voice selection and customization
   - Playback controls (pause, resume, cancel)

### Settings Integration

Speech settings are stored in localStorage and managed by the `useSettings` hook:
- `speechEnabled`: Boolean - Auto-speak responses
- `speechLanguage`: String - Language code (e.g., 'en-US')
- `speechAutoSend`: Boolean - Auto-send transcribed messages (future feature)

## Known Limitations

1. **Browser Support**
   - Firefox does not support Web Speech API
   - iOS Safari requires iOS 14.5 or later
   - Some Android browsers may have limited support

2. **Network Requirements**
   - Chrome/Edge require internet connection for STT
   - Safari can work offline on some devices

3. **Accuracy**
   - Background noise affects recognition quality
   - Accents and dialects may vary in accuracy
   - Technical terms may not be recognized correctly

4. **Performance**
   - Continuous listening can drain battery on mobile devices
   - Large messages may have playback delays

## Future Enhancements

Potential improvements for future versions:
- [ ] Auto-send option for transcribed messages
- [ ] Voice activation (wake word)
- [ ] Custom voice selection for TTS
- [ ] Speech rate and pitch controls
- [ ] Offline speech recognition (with libraries)
- [ ] Multi-language conversation support
- [ ] Voice commands for chat actions
- [ ] Audio recording and playback

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
1. Chrome (latest) - Primary target
2. Edge (latest) - Chromium-based
3. Safari (latest) - Apple ecosystem
4. Firefox (latest) - Verify graceful degradation
5. Mobile Chrome/Safari - Touch interaction

## Support

For issues or questions about speech features:
1. Check browser compatibility above
2. Verify microphone permissions
3. Review error messages in browser console
4. Test with different browsers
5. Contact support with browser version and OS details

## Changelog

### Version 1.0.0 (Phase 1)
- ✅ Web Speech API integration for STT
- ✅ Speech Synthesis API integration for TTS
- ✅ Visual microphone button and feedback
- ✅ Settings for speech preferences
- ✅ Multi-language support
- ✅ Error handling and fallbacks
- ✅ Browser compatibility detection

