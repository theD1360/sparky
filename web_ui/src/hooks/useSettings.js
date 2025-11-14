import { useState, useEffect, useCallback } from 'react';

/**
 * Settings keys for localStorage
 */
const SETTINGS_KEY = 'sparky_settings';

/**
 * Default settings
 */
const DEFAULT_SETTINGS = {
  theme: 'blue', // blue, purple, green, orange
  notifications: true,
  soundEffects: false,
  autoSave: true,
  analytics: false,
  // Speech settings
  speechEnabled: false,
  speechLanguage: 'en-US',
  speechAutoSend: false,
  // VITS TTS settings
  ttsVoiceId: 'en_US-hfc_female-medium',
  ttsDownloadedVoices: [],
  // Whisper STT settings
  sttModel: 'Xenova/whisper-base',
};

/**
 * Custom hook for managing application settings
 * @returns {Object} Settings state and methods
 */
export const useSettings = () => {
  const [settings, setSettings] = useState(() => {
    // Load settings from localStorage on mount
    try {
      const saved = localStorage.getItem(SETTINGS_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return { ...DEFAULT_SETTINGS, ...parsed };
      }
    } catch (error) {
      console.error('Error loading settings:', error);
    }
    return DEFAULT_SETTINGS;
  });

  // Save settings to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
      console.log('Settings saved:', settings);
    } catch (error) {
      console.error('Error saving settings:', error);
    }
  }, [settings]);

  /**
   * Update a single setting
   * @param {string} key - Setting key
   * @param {any} value - Setting value
   */
  const updateSetting = useCallback((key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  /**
   * Update multiple settings at once
   * @param {Object} updates - Object with setting updates
   */
  const updateSettings = useCallback((updates) => {
    setSettings(prev => ({
      ...prev,
      ...updates,
    }));
  }, []);

  /**
   * Reset settings to defaults
   */
  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem(SETTINGS_KEY);
  }, []);

  /**
   * Request notification permission if notifications are enabled
   */
  const requestNotificationPermission = useCallback(async () => {
    if (!('Notification' in window)) {
      console.warn('Browser does not support notifications');
      return false;
    }

    if (Notification.permission === 'granted') {
      return true;
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    }

    return false;
  }, []);

  /**
   * Show a notification if enabled and permitted
   * @param {string} title - Notification title
   * @param {Object} options - Notification options
   */
  const showNotification = useCallback(async (title, options = {}) => {
    if (!settings.notifications) {
      return;
    }

    const hasPermission = await requestNotificationPermission();
    if (hasPermission) {
      new Notification(title, {
        icon: '/robot-logo.svg',
        badge: '/robot-logo.svg',
        ...options,
      });
    }
  }, [settings.notifications, requestNotificationPermission]);

  /**
   * Play a sound effect if enabled
   * @param {string} soundName - Name of sound to play (message, notification, error, success)
   */
  const playSound = useCallback((soundName) => {
    if (!settings.soundEffects) {
      return;
    }

    // Create simple beep sounds using Web Audio API
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      // Different frequencies for different sounds
      const frequencies = {
        message: 440,      // A4
        notification: 523, // C5
        error: 220,        // A3
        success: 659,      // E5
      };

      oscillator.frequency.value = frequencies[soundName] || 440;
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.2);
    } catch (error) {
      console.error('Error playing sound:', error);
    }
  }, [settings.soundEffects]);

  return {
    settings,
    updateSetting,
    updateSettings,
    resetSettings,
    showNotification,
    playSound,
  };
};

