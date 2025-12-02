# Speech Recognition Troubleshooting Guide

## Common Issues and Solutions

### 1. "Speech recognition error: aborted"

**Symptoms:**
- Error appears in console: `Speech recognition error: aborted`
- Microphone starts but immediately stops
- No transcription occurs

**Causes:**
- Race condition in continuous mode
- Component re-rendering during recognition
- Browser security restrictions

**Solutions:**
✅ **Already Fixed in v1.0.1:**
- Improved state management with `shouldBeListeningRef`
- Added 100ms delay before auto-restart in continuous mode
- Gracefully ignore intentional abort errors
- Memoized speech options to prevent unnecessary re-initialization

**User Action:**
- Refresh the page to get the latest fixes
- If issue persists, try clicking the microphone button again
- Check browser console for other error messages

---

### 2. Microphone Permission Denied

**Symptoms:**
- Error: "Microphone permission was denied"
- Microphone icon appears disabled
- No audio input captured

**Solutions:**

**Chrome/Edge:**
1. Click the lock icon in address bar
2. Find "Microphone" setting
3. Change to "Allow"
4. Refresh the page

**Safari:**
1. Safari > Settings for This Website
2. Allow Microphone
3. Or: System Preferences > Security & Privacy > Microphone
4. Check the box next to your browser

**Firefox:**
1. Click the permissions icon in address bar
2. Enable microphone access
3. Refresh the page

---

### 3. No Speech Detected

**Symptoms:**
- Microphone is active (pulsing red)
- No transcription appears
- Console shows: "Speech recognition error: no-speech"

**Solutions:**
- Speak louder and closer to microphone
- Check microphone is not muted in system settings
- Test microphone with another app
- Try selecting a different microphone in system settings
- Reduce background noise
- Check microphone permissions (see #2)

**On macOS:**
1. System Preferences > Sound > Input
2. Verify correct microphone is selected
3. Check input level meter moves when speaking

**On Windows:**
1. Settings > System > Sound > Input
2. Test your microphone
3. Adjust input volume if needed

---

### 4. Browser Not Supported

**Symptoms:**
- Microphone icon is grayed out
- Message: "Speech recognition not supported in this browser"
- Feature not available

**Solution:**
Use a supported browser:
- ✅ Chrome (recommended)
- ✅ Edge (Chromium-based)
- ✅ Safari 14.5+ on macOS 11+ or iOS 14.5+
- ❌ Firefox (not supported)

---

### 5. Continuous Mode Auto-Restart Issues

**Symptoms:**
- Recognition stops unexpectedly
- Microphone turns off after speaking
- Need to click microphone repeatedly

**Solutions:**
✅ **Already Fixed:**
- Improved continuous mode with proper state tracking
- Added delay before auto-restart
- Better handling of speech gaps

**User Tips:**
- Continuous mode works better with longer pauses between sentences
- Click the stop button to explicitly stop listening
- In noisy environments, use shorter recording sessions

---

### 6. Network Errors

**Symptoms:**
- Error: "Network error occurred"
- Recognition works intermittently
- Slower transcription

**Causes:**
- Chrome/Edge send audio to Google servers for processing
- Poor internet connection
- Server timeouts

**Solutions:**
- Check internet connectivity
- Try refreshing the page
- Use Safari for offline recognition (if supported)
- Wait for connection to stabilize

---

### 7. Transcription Accuracy Issues

**Symptoms:**
- Wrong words transcribed
- Missing words
- Gibberish text

**Solutions:**
- Speak clearly and at moderate pace
- Reduce background noise
- Use a better quality microphone
- Ensure correct language is selected in Settings
- Avoid technical jargon (may not be in recognition vocabulary)
- Speak in complete sentences

**Tips for Better Accuracy:**
- Pause briefly between sentences
- Enunciate clearly
- Maintain consistent volume
- Position microphone 6-12 inches from mouth
- Use a headset microphone for best results

---

### 8. Text-to-Speech Not Working

**Symptoms:**
- Auto-speak is enabled but no audio plays
- Assistant responses are silent
- No errors shown

**Solutions:**

**Check Settings:**
1. Open Settings > General
2. Verify "Auto-speak Responses" is ON
3. Check system volume is not muted

**Browser Audio:**
1. Ensure browser has permission to play audio
2. Check no other app is using audio output
3. Try playing audio in another tab to verify browser audio works

**System Audio:**
- Check system volume (not muted)
- Verify correct audio output device selected
- Test with another audio source

---

### 9. Wrong Language Detected

**Symptoms:**
- Transcription is in wrong language
- Poor accuracy with correct language
- Mixed language results

**Solutions:**
1. Open Settings > General > Voice & Speech
2. Select correct language from dropdown
3. Refresh the page
4. Try speaking again

**Note:** Language setting affects both:
- Speech recognition (input)
- Speech synthesis (output)

---

### 10. High CPU/Battery Usage

**Symptoms:**
- Device gets warm
- Battery drains quickly
- Fan runs constantly
- Browser uses high CPU

**Causes:**
- Continuous listening mode is resource-intensive
- Real-time speech processing

**Solutions:**
- Click stop button when not actively using voice input
- Disable "Auto-speak Responses" when not needed
- Use typed messages for longer conversations
- Close other browser tabs
- Use desktop instead of mobile for extended voice sessions

---

## Browser Console Debugging

### Enable Console Logging

1. Open Developer Tools:
   - Chrome/Edge: `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
   - Safari: Enable Develop menu first, then `Cmd+Option+C`
   - Firefox: `F12` or `Ctrl+Shift+I`

2. Go to **Console** tab

3. Look for messages starting with:
   - `Speech recognition started`
   - `Speech recognition error:`
   - `Speech synthesis:`

### Common Console Messages

**Normal Operation:**
```
Speech recognition started
Speech recognition ended
Auto-restarting recognition in continuous mode
```

**Errors to Report:**
```
Speech recognition error: audio-capture
Speech recognition error: not-allowed
Speech recognition error: service-not-allowed
Failed to start recognition: [error details]
```

---

## System Requirements

### Minimum Requirements
- **Browser:** Chrome 25+, Edge 79+, Safari 14.5+
- **OS:** Windows 10+, macOS 11+, iOS 14.5+, Android 5+
- **Internet:** Required for Chrome/Edge STT
- **Microphone:** Any working microphone device

### Recommended Setup
- **Browser:** Latest Chrome or Edge
- **Connection:** Stable broadband internet
- **Microphone:** USB or headset microphone
- **Environment:** Quiet room

---

## Still Having Issues?

### Collect Diagnostic Information

1. **Browser and Version:**
   - Chrome: Menu > Help > About Google Chrome
   - Edge: Menu > Help and feedback > About Microsoft Edge
   - Safari: Safari menu > About Safari

2. **Operating System:**
   - Windows: Settings > System > About
   - macOS: Apple menu > About This Mac
   - Check for system updates

3. **Error Messages:**
   - Copy exact error text from console
   - Screenshot if possible
   - Note when error occurs

4. **Microphone Info:**
   - Device name and type
   - Connection type (built-in, USB, Bluetooth)
   - Whether it works in other apps

### Report Issue

When reporting issues, include:
- Browser name and version
- Operating system and version
- Microphone device type
- Exact error message
- Steps to reproduce
- Screenshots of console errors

---

## Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| Aborted error | Refresh page (fixed in v1.0.1) |
| No permission | Allow microphone in browser |
| Not supported | Use Chrome, Edge, or Safari |
| No speech detected | Speak louder, check mic |
| Poor accuracy | Reduce noise, speak clearly |
| No audio output | Check volume, enable auto-speak |
| High CPU | Stop listening when not in use |
| Network error | Check internet connection |

---

## Version History

### v1.0.1 (Current)
- Fixed "aborted" error in continuous mode
- Improved state management with dual refs
- Added auto-restart delay
- Graceful error suppression for intentional aborts
- Memoized callbacks to prevent re-initialization

### v1.0.0 (Initial)
- Web Speech API integration
- Speech Synthesis support
- Multi-language support
- Settings panel
- Basic error handling

