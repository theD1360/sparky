# Speech Recognition Network Issues

## Quick Diagnostics

### Check if it's a real network issue:

1. **Open Browser DevTools** (`F12` or `Cmd+Option+I`)
2. Go to **Network** tab
3. Filter by "websocket" or "speech"
4. Click the microphone button
5. Look for failed requests to Google domains

### Expected Behavior
When speech recognition starts, Chrome/Edge should:
- Open WebSocket connection to Google servers
- Send audio chunks for processing
- Receive transcription results back

## Common Causes & Solutions

### 1. VPN or Proxy
**Problem:** VPN/proxy blocking WebRTC or Google services

**Solutions:**
- Temporarily disable VPN
- Try without proxy
- Whitelist Google speech API domains:
  - `*.google.com`
  - `*.googleapis.com`
  - `speech.google.com`

### 2. Corporate Firewall
**Problem:** Enterprise firewall blocking speech services

**Solutions:**
- Ask IT to whitelist Google Speech API
- Use Safari (doesn't require external service)
- Test on personal device/network

### 3. Browser Extensions
**Problem:** Ad blockers or privacy extensions blocking Google

**Solutions:**
- Try in Incognito/Private mode
- Disable extensions temporarily
- Whitelist your app domain in privacy extensions

### 4. HTTPS Requirement
**Problem:** Speech API requires secure context

**Verify:**
- URL starts with `https://` or `localhost`
- Mixed content not blocked
- Valid SSL certificate

### 5. Geographic Restrictions
**Problem:** Google services blocked in region

**Solutions:**
- Use VPN to different region
- Try Safari (offline processing on supported devices)
- Consider third-party STT service

## Test Your Connection

### Quick Network Test

1. **Open Console** in DevTools
2. **Run this test:**
```javascript
// Test if browser supports speech recognition
if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
  console.log('✅ Speech Recognition API available');
  
  // Check secure context
  if (window.isSecureContext) {
    console.log('✅ Secure context (HTTPS or localhost)');
  } else {
    console.log('❌ Not a secure context - HTTPS required');
  }
} else {
  console.log('❌ Speech Recognition not supported');
}

// Test internet connectivity
fetch('https://www.google.com/robots.txt')
  .then(() => console.log('✅ Can reach Google'))
  .catch(() => console.log('❌ Cannot reach Google servers'));
```

### Check Console Errors

Look for these specific errors:
- `net::ERR_CONNECTION_REFUSED` - Service unreachable
- `net::ERR_NAME_NOT_RESOLVED` - DNS issue
- `net::ERR_BLOCKED_BY_CLIENT` - Extension blocking
- `net::ERR_CERT_AUTHORITY_INVALID` - SSL issue

## Alternative Solutions

### Option 1: Use Safari (macOS/iOS)
Safari uses **on-device speech recognition** (no internet required):
- Works offline on macOS 11+ 
- Works offline on iOS 14.5+
- More private (no data sent to servers)
- May have less accuracy

**Test in Safari:**
```bash
# If your dev server is on http://localhost:3000
open -a Safari http://localhost:3000
```

### Option 2: Check Network Settings

**macOS:**
```bash
# Check if Google is reachable
ping speech.googleapis.com

# Check DNS
nslookup speech.googleapis.com

# Check for VPN
scutil --nc list
```

**Windows:**
```cmd
ping speech.googleapis.com
nslookup speech.googleapis.com
```

### Option 3: Browser Settings

**Chrome/Edge:**
1. Settings → Privacy and security
2. Security → Manage certificates
3. Clear SSL state if needed
4. Check proxy settings

### Option 4: Use Different Port/Protocol

If you're on `http://localhost`, ensure:
- Port is standard (3000, 8080, etc.)
- Not using self-signed certificate that's causing issues
- CORS is properly configured

## Environment-Specific Issues

### Development Environment
If on `localhost`:
- ✅ Should work - localhost is secure context
- Check no VPN blocking local traffic
- Verify WebSocket connections work

### Staging/Production
If on custom domain:
- Must use HTTPS (not HTTP)
- Valid SSL certificate required
- No mixed content warnings
- Firewall rules allow outbound to Google

## Temporary Workarounds

While debugging network issues:

### 1. Disable Auto-Speak
**Settings → General → Auto-speak Responses**: OFF
- Reduces load
- Only use STT (speech input)
- TTS works offline

### 2. Use Manual Transcription
Type messages until network issue resolved

### 3. Check System Settings

**macOS:**
System Preferences → Network → Advanced → Proxies
- Ensure no unexpected proxies

**Windows:**  
Settings → Network & Internet → Proxy
- Check proxy configuration

## Still Not Working?

### Collect Diagnostic Information

1. **Browser Console:**
   - Copy all error messages
   - Note exact error codes

2. **Network Tab:**
   - Export HAR file
   - Check failed requests
   - Look for status codes

3. **System Info:**
   - Browser version: `chrome://version` or `edge://version`
   - OS version
   - VPN/Proxy status
   - Firewall software

4. **Test Other Google Services:**
   ```javascript
   // Test in console
   fetch('https://translate.googleapis.com/$discovery/rest?version=v2')
     .then(r => r.json())
     .then(d => console.log('✅ Google APIs reachable'))
     .catch(e => console.log('❌ Google APIs blocked:', e));
   ```

## Working Configuration Examples

### Development (Local)
```
✅ http://localhost:3000
✅ http://127.0.0.1:3000
✅ https://localhost:3000
❌ http://192.168.x.x:3000 (not secure context)
```

### Production
```
✅ https://yourdomain.com
❌ http://yourdomain.com (not secure)
✅ https://subdomain.yourdomain.com
```

## Contact Support

If none of these work, provide:
- Browser and version
- Operating system
- Network environment (home/corporate)
- VPN/proxy info
- Console errors
- Network tab errors
- Whether Safari works (if on Mac)

## Summary

The speech recognition feature is **working correctly** - it:
- ✅ Detects browser support
- ✅ Handles errors gracefully  
- ✅ Retries intelligently (3 attempts)
- ✅ Shows clear error messages
- ✅ Stops infinite loops

The network errors indicate an **environment issue**, not a code bug. Most common fix: disable VPN or try Safari for offline recognition.

