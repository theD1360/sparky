/**
 * Utility to clear all model caches
 * This helps resolve issues with corrupt or stale cached model files
 */

/**
 * Clear all browser caches related to transformers.js
 */
export async function clearAllModelCaches() {
  const results = {
    cachesCleared: [],
    errors: [],
  };

  try {
    // Clear Cache API caches
    if ('caches' in window) {
      const cacheNames = await caches.keys();
      console.log('Found caches:', cacheNames);
      
      for (const cacheName of cacheNames) {
        try {
          const deleted = await caches.delete(cacheName);
          if (deleted) {
            results.cachesCleared.push(cacheName);
            console.log(`✓ Deleted cache: ${cacheName}`);
          }
        } catch (err) {
          console.error(`Failed to delete cache ${cacheName}:`, err);
          results.errors.push({ cache: cacheName, error: err.message });
        }
      }
    } else {
      console.warn('Cache API not available');
    }

    // Clear IndexedDB databases used by transformers.js
    if ('indexedDB' in window) {
      try {
        const databases = await indexedDB.databases();
        console.log('Found IndexedDB databases:', databases);
        
        for (const db of databases) {
          if (db.name && (
            db.name.includes('transformers') || 
            db.name.includes('onnx') ||
            db.name.includes('model')
          )) {
            try {
              indexedDB.deleteDatabase(db.name);
              results.cachesCleared.push(`IDB:${db.name}`);
              console.log(`✓ Deleted IndexedDB: ${db.name}`);
            } catch (err) {
              console.error(`Failed to delete IndexedDB ${db.name}:`, err);
              results.errors.push({ db: db.name, error: err.message });
            }
          }
        }
      } catch (err) {
        console.warn('Could not list IndexedDB databases:', err);
      }
    }

    // Clear localStorage items related to transformers
    if ('localStorage' in window) {
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (
          key.includes('transformers') || 
          key.includes('model') ||
          key.includes('onnx')
        )) {
          keysToRemove.push(key);
        }
      }
      
      for (const key of keysToRemove) {
        try {
          localStorage.removeItem(key);
          results.cachesCleared.push(`LS:${key}`);
          console.log(`✓ Removed localStorage: ${key}`);
        } catch (err) {
          console.error(`Failed to remove localStorage ${key}:`, err);
          results.errors.push({ key, error: err.message });
        }
      }
    }

    console.log('Cache clearing complete:', results);
    return results;
  } catch (err) {
    console.error('Error clearing caches:', err);
    results.errors.push({ general: err.message });
    return results;
  }
}

/**
 * Get cache status and sizes
 */
export async function getCacheStatus() {
  const status = {
    caches: [],
    indexedDBs: [],
    storage: null,
  };

  try {
    // List Cache API caches
    if ('caches' in window) {
      const cacheNames = await caches.keys();
      status.caches = cacheNames;
    }

    // List IndexedDB databases
    if ('indexedDB' in window && indexedDB.databases) {
      const databases = await indexedDB.databases();
      status.indexedDBs = databases.map(db => db.name);
    }

    // Get storage estimate
    if ('storage' in navigator && navigator.storage.estimate) {
      const estimate = await navigator.storage.estimate();
      status.storage = {
        usage: estimate.usage,
        quota: estimate.quota,
        usageMB: (estimate.usage / 1024 / 1024).toFixed(2),
        quotaMB: (estimate.quota / 1024 / 1024).toFixed(2),
        percentUsed: ((estimate.usage / estimate.quota) * 100).toFixed(2),
      };
    }

    return status;
  } catch (err) {
    console.error('Error getting cache status:', err);
    return status;
  }
}

// Expose to window for debugging
if (typeof window !== 'undefined') {
  window.clearModelCaches = clearAllModelCaches;
  window.getCacheStatus = getCacheStatus;
  console.log('Cache utilities available: window.clearModelCaches(), window.getCacheStatus()');
}

