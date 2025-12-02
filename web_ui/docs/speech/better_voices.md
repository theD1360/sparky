# How to Get Better Text-to-Speech Voices

## 🎯 The Quick Fix

### macOS - Download Better Voices

Safari uses **macOS system voices**. The default voices are robotic, but Apple has much better "Premium" voices available for free!

#### Download Enhanced Voices:

1. **Open System Preferences** → **Accessibility** → **Spoken Content**
2. Click **System Voice** dropdown → **Customize...**
3. Download these high-quality voices:

**English:**
- ✅ **Samantha (Enhanced)** - Female, US English (Best!)
- ✅ **Alex (Enhanced)** - Male, US English
- ✅ **Ava (Premium)** - Female, US English (Natural)
- ✅ **Tom (Premium)** - Male, US English

**Other Languages:**
- French: **Thomas (Premium)**
- Spanish: **Monica (Premium)**
- German: **Anna (Premium)**

4. **Set as default:**
   - After downloading, select your preferred voice
   - Close System Preferences
   - Refresh your browser

### The Voice Will Sound MUCH Better! 🎉

---

## 🔧 Fine-Tuning Speech Settings

### In Sparky Settings

**Settings → General → Voice & Speech**
- The app uses speech rate **1.1** by default (10% faster than normal)
- System voice is determined by macOS settings

### Adjust macOS Voice Settings

**System Preferences → Accessibility → Spoken Content:**
- **Speaking Rate:** Adjust slider (we override this to 1.1 in code)
- **System Voice:** Select from downloaded voices
- Click **Play** to test

---

## 📱 iOS/iPadOS

### Better Voices on iPhone/iPad

1. **Settings** → **Accessibility** → **Spoken Content** → **Voices**
2. Select your language (e.g., **English**)
3. Download **Enhanced Quality** voices:
   - **Siri Voice 3** - Most natural
   - **Samantha (Enhanced)**
   - **Nicky (Premium)**

---

## 🎛️ Advanced: Custom Voice Settings

If you want to customize speech further, you can adjust the code:

### In `SpeechOutput.js`:

**Current settings:**
```javascript
speak(textToSpeak, { rate: 1.1 });
```

**Customize:**
```javascript
speak(textToSpeak, { 
  rate: 1.1,    // Speed: 0.5 (slow) to 2.0 (fast)
  pitch: 1.0,   // Pitch: 0 (low) to 2 (high)
  volume: 0.8,  // Volume: 0 (silent) to 1 (max)
});
```

### Find Available Voices Programmatically

Open browser console and run:
```javascript
// List all available voices
window.speechSynthesis.getVoices().forEach((voice, i) => {
  console.log(`${i}: ${voice.name} (${voice.lang})`);
});
```

Look for voices with:
- "Premium" in the name
- "Enhanced" in the name
- "Siri" in the name (iOS)

---

## 🌟 Best Voice Recommendations

### macOS/Safari
1. **Ava (Premium)** - Most natural female voice
2. **Tom (Premium)** - Most natural male voice
3. **Samantha (Enhanced)** - Good balance
4. **Alex** - Classic Mac voice (okay quality)

### Chrome/Edge (Online)
- Uses Google's voices (generally good quality)
- Requires internet connection
- More robotic than macOS Premium voices

### Windows
- **Microsoft David** - Good male voice
- **Microsoft Zira** - Good female voice
- Download more from Windows Settings → Time & Language → Speech

---

## 🎵 Voice Quality Comparison

| Voice Type | Quality | Natural? | Offline? |
|------------|---------|----------|----------|
| macOS Default | ⭐⭐ | No | Yes |
| macOS Enhanced | ⭐⭐⭐ | Decent | Yes |
| macOS Premium | ⭐⭐⭐⭐⭐ | Very! | Yes |
| Google (Chrome) | ⭐⭐⭐⭐ | Good | No |
| Windows Default | ⭐⭐⭐ | Okay | Yes |

---

## 🐛 Troubleshooting Voice Issues

### Voice Sounds Robotic
- Download **Premium/Enhanced** voices (see above)
- Try different voices in System Preferences
- Restart browser after installing new voices

### Voice is Too Slow/Fast
- Adjust rate in Settings (or code)
- Default is 1.1x speed (10% faster)
- Try 1.0x for normal or 1.3x for faster

### Wrong Voice Being Used
- Check System Preferences → Spoken Content → System Voice
- Make sure you selected the voice **after** downloading it
- Restart browser

### Voice Cuts Off
- Known Safari bug with very long messages
- Breaking into shorter sentences helps
- Code automatically handles message chunking

---

## 💡 Pro Tips

### Make It Sound More Natural:
1. **Download Premium voices** (biggest improvement!)
2. Use **1.1x rate** (default in our app)
3. Select voices labeled "Premium" or "Enhanced"
4. Test different voices - personal preference matters!

### For Development:
- Test with **short messages first**
- Premium voices take longer to download (100-500 MB)
- Download over WiFi
- Restart browser after installing voices

### Best Overall Experience:
- **macOS + Safari + Ava Premium voice** = Most natural
- **Chrome/Edge + Google voices** = Good but needs internet
- **Windows + Enhanced voices** = Decent quality

---

## 🎤 Quick Test

After downloading better voices:

1. Open Safari with Sparky
2. Enable Auto-speak in Settings
3. Send a test message: "Hello Sparky, how are you?"
4. Listen to the response
5. If still robotic, download Premium voices!

---

## 📚 Additional Resources

**macOS Voice Management:**
```bash
# List all installed voices
say -v '?'

# Test a voice from terminal
say -v "Samantha" "This is a test of Samantha's voice"
say -v "Ava" "This is a test of Ava's Premium voice"
```

**Download Voices via Terminal (macOS):**
System Preferences is easier, but voices are in:
`/System/Library/Speech/Voices/`

---

## Summary

1. ✅ **Download Premium/Enhanced voices** in System Preferences
2. ✅ **Select your preferred voice** as system default
3. ✅ **Refresh browser**
4. 🎉 **Enjoy natural-sounding speech!**

The difference between default and Premium voices is **night and day**. Definitely worth the 5-minute setup!

