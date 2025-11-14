# Markdown Stripping for TTS

## Why Strip Markdown?

When Sparky responds with markdown formatting, it sounds terrible when spoken aloud:
- ❌ "Star star bold text star star" 
- ❌ "Backtick code backtick"
- ❌ "Square bracket link text close bracket open paren URL close paren"

After stripping:
- ✅ "bold text"
- ✅ "code"
- ✅ "link text"

---

## Examples

### Bold Text

**Input:**
```
This is **bold text** and this is __also bold__.
```

**Output (for TTS):**
```
This is bold text and this is also bold.
```

---

### Italic Text

**Input:**
```
This is *italic* and this is _also italic_.
```

**Output (for TTS):**
```
This is italic and this is also italic.
```

---

### Code Blocks

**Input:**
```
Here's some code:
```python
def hello():
    print("Hello")
```
That was a code example.
```

**Output (for TTS):**
```
Here's some code: code block That was a code example.
```

---

### Inline Code

**Input:**
```
Use the `useState` hook to manage state in React.
```

**Output (for TTS):**
```
Use the useState hook to manage state in React.
```

---

### Links

**Input:**
```
Check out [this documentation](https://example.com) for more info.
```

**Output (for TTS):**
```
Check out this documentation for more info.
```

---

### Headers

**Input:**
```
# Main Title
## Subtitle
### Section
Regular text here.
```

**Output (for TTS):**
```
Main Title Subtitle Section Regular text here.
```

---

### Lists

**Input:**
```
Here are the steps:
- First step
- Second step
- Third step
```

**Output (for TTS):**
```
Here are the steps: First step Second step Third step
```

---

### Complex Example

**Input:**
```
# Python Tutorial

Here's how to use **lists** in Python:

```python
my_list = [1, 2, 3]
```

You can use the `append()` method to add items. Check out [the docs](https://python.org) for more info.

Key points:
- Lists are *mutable*
- Use `[]` to create them
- They can hold **any type**
```

**Output (for TTS):**
```
Python Tutorial Here's how to use lists in Python: code block You can use the append() method to add items. Check out the docs for more info. Key points: Lists are mutable Use [] to create them They can hold any type
```

---

## Implementation Details

### What Gets Stripped

✅ **Removed:**
- Code blocks (``` or ~~~)
- Inline code markers (``)
- Bold markers (** or __)
- Italic markers (* or _)
- Link URLs ([text](url) → text)
- Headers (# ## ###)
- List markers (- * 1.)
- Blockquotes (>)
- HTML tags (<tag>)
- Horizontal rules (---)
- Task lists ([x])
- Images (![alt](url))

✅ **Preserved:**
- Actual text content
- Natural word spacing
- Sentence structure
- Punctuation

### Special Handling

**Code Blocks:**
- Replaced with " code block " for context
- Prevents speaking the entire code

**Links:**
- Keeps link text
- Removes URL (which would be nonsense when spoken)

**Newlines:**
- Multiple newlines → single space
- Creates better speech flow

---

## Usage

### Automatic in App

```javascript
// In App.js when receiving bot message
const textForSpeech = stripMarkdown(data.data.text);
setLastBotMessage(textForSpeech);
```

### Manual Usage

```javascript
import { stripMarkdown } from './utils/textUtils';

const markdown = "This is **bold** and this is `code`";
const plain = stripMarkdown(markdown);
// Result: "This is bold and this is code"
```

### With Options

```javascript
import { prepareTextForSpeech } from './utils/textUtils';

const text = prepareTextForSpeech(markdown, {
  stripMarkdown: true,  // Strip markdown (default: true)
  maxLength: 500,       // Truncate long text (default: 0 = no limit)
});
```

---

## Testing

### Console Output

When a message arrives, you'll see:
```
Preparing text for speech: Python Tutorial Here's how to use lists in Python code block You can...
```

This confirms markdown was stripped before sending to TTS.

### Manual Test

Open browser console and test:
```javascript
// Load the utility
const { stripMarkdown } = await import('./utils/textUtils.js');

// Test with markdown
const input = "This is **bold** with `code` and [a link](http://example.com)";
const output = stripMarkdown(input);
console.log(output);
// Output: "This is bold with code and a link"
```

---

## Edge Cases Handled

### Nested Formatting

**Input:** `***bold and italic***`
**Output:** `bold and italic`

### Multiple Code Blocks

**Input:**
```
First block:
```js
code1
```

Second block:
```py
code2
```
```

**Output:** `First block: code block Second block: code block`

### Mixed Lists

**Input:**
```
1. First item
2. Second item
   - Sub item
   * Another sub
```

**Output:** `First item Second item Sub item Another sub`

---

## Benefits

### Improved TTS Quality
- 🎯 **Natural Speech** - No more "star star bold"
- 🗣️ **Better Flow** - Smooth reading without interruptions
- 📖 **Readable** - Sounds like normal conversation
- ⚡ **Faster** - Less to speak = quicker responses

### User Experience
- ✨ **Professional** - Doesn't sound like reading code
- 🎵 **Pleasant** - Easy to listen to
- 💡 **Clear** - Focuses on content, not formatting
- 🚀 **Efficient** - No wasted words

---

## Future Enhancements

Potential improvements:
- [ ] Replace code block with actual code summary
- [ ] Speak list items with "first, second, third"
- [ ] Add pauses for better prosody
- [ ] Handle math expressions specially
- [ ] Preserve important formatting as words ("in bold:")

---

## Related Files

- **Implementation:** `/web_ui/src/utils/textUtils.js`
- **Usage:** `/web_ui/src/App.js` (line ~786)
- **Tests:** Could add unit tests in future

---

## Summary

The markdown stripping ensures that Sparky's responses sound natural when read aloud, removing all formatting symbols while preserving the actual content. This creates a much better voice conversation experience!

**Before:** "Star star Python Tutorial star star Here's how to use star star lists star star in Python..."

**After:** "Python Tutorial. Here's how to use lists in Python..."

Much better! 🎉

