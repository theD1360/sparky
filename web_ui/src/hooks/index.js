// Hooks barrel export
export { useSettings } from './useSettings';

// Legacy speech hooks (deprecated - use VITS and Whisper instead)
export { useSpeechRecognition } from './useSpeechRecognition';
export { useSpeechSynthesis } from './useSpeechSynthesis';

// New speech hooks (VITS TTS and Whisper STT)
export { useVitsTTS } from './useVitsTTS';
export { useWhisperSTT } from './useWhisperSTT';

