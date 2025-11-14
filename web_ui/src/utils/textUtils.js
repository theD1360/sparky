/**
 * Text utility functions for formatting and processing
 */

/**
 * Strip markdown formatting from text for TTS
 * Converts markdown to plain text while preserving readability
 * 
 * @param {string} text - Text with markdown formatting
 * @returns {string} - Plain text suitable for speech synthesis
 */
export function stripMarkdown(text) {
  if (!text) return '';

  let result = text;

  // Remove code blocks (``` or ~~~)
  result = result.replace(/```[\s\S]*?```/g, ' code block ');
  result = result.replace(/~~~[\s\S]*?~~~/g, ' code block ');

  // Remove inline code with space around it
  result = result.replace(/`([^`]+)`/g, ' $1 ');

  // Remove links but keep text [text](url) -> text
  result = result.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

  // Remove images ![alt](url)
  result = result.replace(/!\[([^\]]*)\]\([^)]+\)/g, '');

  // Remove reference-style links [text][ref]
  result = result.replace(/\[([^\]]+)\]\[[^\]]+\]/g, '$1');

  // Remove bold/italic markers but keep text
  result = result.replace(/\*\*\*([^*]+)\*\*\*/g, '$1'); // Bold + italic
  result = result.replace(/___([^_]+)___/g, '$1');       // Bold + italic
  result = result.replace(/\*\*([^*]+)\*\*/g, '$1');     // Bold
  result = result.replace(/__([^_]+)__/g, '$1');         // Bold
  result = result.replace(/\*([^*]+)\*/g, '$1');         // Italic
  result = result.replace(/_([^_]+)_/g, '$1');           // Italic

  // Remove strikethrough
  result = result.replace(/~~([^~]+)~~/g, '$1');

  // Remove headers but keep text (# Header -> Header)
  result = result.replace(/^#{1,6}\s+(.+)$/gm, '$1');

  // Remove horizontal rules
  result = result.replace(/^(\*{3,}|-{3,}|_{3,})$/gm, '');

  // Remove blockquote markers
  result = result.replace(/^>\s+/gm, '');

  // Remove list markers but keep text
  result = result.replace(/^\s*[-*+]\s+/gm, ''); // Unordered lists
  result = result.replace(/^\s*\d+\.\s+/gm, '');  // Ordered lists

  // Remove task list markers
  result = result.replace(/^\s*-\s*\[[x ]\]\s+/gmi, '');

  // Remove HTML tags
  result = result.replace(/<[^>]+>/g, '');

  // Remove extra whitespace
  result = result.replace(/\n{3,}/g, '\n\n'); // Max 2 newlines
  result = result.replace(/[ \t]{2,}/g, ' ');  // Multiple spaces to single
  result = result.trim();

  // Replace remaining newlines with spaces for better speech flow
  result = result.replace(/\n+/g, ' ');

  // Clean up multiple spaces again
  result = result.replace(/\s{2,}/g, ' ');

  return result;
}

/**
 * Truncate text to a maximum length for speech
 * Useful for very long responses
 * 
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length (default: 1000 characters)
 * @returns {string} - Truncated text
 */
export function truncateForSpeech(text, maxLength = 1000) {
  if (!text || text.length <= maxLength) return text;
  
  // Try to break at a sentence
  const truncated = text.substring(0, maxLength);
  const lastPeriod = truncated.lastIndexOf('.');
  const lastQuestion = truncated.lastIndexOf('?');
  const lastExclamation = truncated.lastIndexOf('!');
  
  const lastSentence = Math.max(lastPeriod, lastQuestion, lastExclamation);
  
  if (lastSentence > maxLength * 0.8) {
    // Good break point found
    return truncated.substring(0, lastSentence + 1);
  }
  
  // No good break point, truncate at word boundary
  const lastSpace = truncated.lastIndexOf(' ');
  if (lastSpace > 0) {
    return truncated.substring(0, lastSpace) + '...';
  }
  
  return truncated + '...';
}

/**
 * Prepare text for speech synthesis
 * Combines markdown stripping and optional truncation
 * 
 * @param {string} text - Text to prepare
 * @param {Object} options - Options
 * @param {boolean} options.stripMarkdown - Strip markdown (default: true)
 * @param {number} options.maxLength - Max length, 0 for no limit (default: 0)
 * @returns {string} - Prepared text
 */
export function prepareTextForSpeech(text, options = {}) {
  const {
    stripMarkdown: shouldStripMarkdown = true,
    maxLength = 0,
  } = options;

  let result = text;

  if (shouldStripMarkdown) {
    result = stripMarkdown(result);
  }

  if (maxLength > 0) {
    result = truncateForSpeech(result, maxLength);
  }

  return result;
}

export default {
  stripMarkdown,
  truncateForSpeech,
  prepareTextForSpeech,
};

