// Berlin Transport Time Machine - Configuration

const CONFIG = {
    // API Configuration
    API: {
        BASE_URL: 'http://localhost:8081/api/v1',
        TIMEOUT: 30000, // 30 seconds
        RETRY_ATTEMPTS: 3,
        RETRY_DELAY: 1000 // 1 second
    },
    
    // Map Configuration
    MAP: {
        CENTER: [52.5200, 13.4050], // Berlin center
        ZOOM: 11,
        MIN_ZOOM: 9,
        MAX_ZOOM: 18,
        TILE_LAYER: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        ATTRIBUTION: '© OpenStreetMap contributors, © CARTO',
        BOUNDS: {
            MIN_LAT: 52.3,
            MAX_LAT: 52.7,
            MIN_LNG: 13.0,
            MAX_LNG: 13.8
        }
    },
    
    // Transport Type Configuration
    TRANSPORT_TYPES: {
        suburban: {
            name: 'S-Bahn',
            color: '#0066cc',
            icon: '🚊',
            priority: 1,
            enabled: true
        },
        subway: {
            name: 'U-Bahn',
            color: '#003d82',
            icon: '🚇',
            priority: 2,
            enabled: true
        },
        ring: {
            name: 'Ring',
            color: '#ff6b35',
            icon: '🔄',
            priority: 3,
            enabled: true
        },
        tram: {
            name: 'Tram',
            color: '#00a86b',
            icon: '🚋',
            priority: 4,
            enabled: true
        },
        bus: {
            name: 'Bus',
            color: '#dc2626',
            icon: '🚌',
            priority: 5,
            enabled: true
        },
        ferry: {
            name: 'Ferry',
            color: '#8b5cf6',
            icon: '⛴️',
            priority: 6,
            enabled: false
        },
        regional: {
            name: 'Regional',
            color: '#ff8c00',
            icon: '🚆',
            priority: 7,
            enabled: false
        }
    },
    
    // Animation Configuration
    ANIMATION: {
        DEFAULT_SPEED: 1,
        SPEED_OPTIONS: [0.5, 1, 2, 5, 10],
        FRAME_RATE: 30, // FPS
        INTERPOLATION_ENABLED: true,
        SMOOTH_TRANSITIONS: true,
        CHUNK_DURATION_MINUTES: 10,
        FRAME_INTERVAL_SECONDS: 30
    },
    
    // Vehicle Marker Configuration
    MARKERS: {
        VEHICLE: {
            SIZE: 16,
            BORDER_WIDTH: 2,
            HOVER_SCALE: 1.3,
            ANIMATION_DURATION: 1000 // milliseconds
        },
        STOP: {
            SIZE: 12,
            MAJOR_SIZE: 16,
            HOVER_SCALE: 1.5
        }
    },
    
    // Performance Configuration
    PERFORMANCE: {
        MAX_VEHICLES_ON_MAP: 5000,
        VIEWPORT_BUFFER: 0.1, // 10% buffer around viewport
        UPDATE_THROTTLE: 100, // milliseconds
        DEBOUNCE_DELAY: 300, // milliseconds
        CHUNK_CACHE_SIZE: 10, // number of chunks to cache
        PRELOAD_CHUNKS: 2 // number of chunks to preload ahead
    },
    
    // UI Configuration
    UI: {
        LOADING_TIMEOUT: 10000, // 10 seconds
        ERROR_DISPLAY_DURATION: 5000, // 5 seconds
        TOAST_DURATION: 3000, // 3 seconds
        PANEL_ANIMATION_DURATION: 300, // milliseconds
        KEYBOARD_SHORTCUTS_ENABLED: true
    },
    
    // Timeline Configuration
    TIMELINE: {
        PRECISION: 0.1, // 0.1% precision for scrubber
        AUTO_ADVANCE: false,
        LOOP_PLAYBACK: false,
        STEP_SIZE_MINUTES: 5,
        BOOKMARK_ENABLED: true
    },
    
    // Data Configuration
    DATA: {
        REFRESH_INTERVAL: 30000, // 30 seconds for live data
        STALE_THRESHOLD: 300000, // 5 minutes
        OFFLINE_CACHE_DURATION: 86400000, // 24 hours
        COMPRESSION_ENABLED: true
    },
    
    // Keyboard Shortcuts
    KEYBOARD: {
        PLAY_PAUSE: ' ', // Spacebar
        STEP_FORWARD: 'ArrowRight',
        STEP_BACKWARD: 'ArrowLeft',
        SPEED_UP: 'ArrowUp',
        SPEED_DOWN: 'ArrowDown',
        RESET: 'Home',
        TOGGLE_ROUTES: 'r',
        TOGGLE_STOPS: 's',
        TOGGLE_HELP: '?',
        ESCAPE: 'Escape'
    },
    
    // Debug Configuration
    DEBUG: {
        ENABLED: true,
        LOG_LEVEL: 'info', // 'debug', 'info', 'warn', 'error'
        PERFORMANCE_MONITORING: true,
        API_LOGGING: true,
        ANIMATION_STATS: false
    }
};

// Validation and runtime configuration
CONFIG.validate = function() {
    const errors = [];
    
    // Validate API URL
    try {
        new URL(CONFIG.API.BASE_URL);
    } catch (e) {
        errors.push('Invalid API base URL');
    }
    
    // Validate map bounds
    const bounds = CONFIG.MAP.BOUNDS;
    if (bounds.MIN_LAT >= bounds.MAX_LAT || bounds.MIN_LNG >= bounds.MAX_LNG) {
        errors.push('Invalid map bounds');
    }
    
    // Validate transport types
    const transportTypes = Object.keys(CONFIG.TRANSPORT_TYPES);
    if (transportTypes.length === 0) {
        errors.push('No transport types configured');
    }
    
    if (errors.length > 0) {
        console.error('Configuration validation failed:', errors);
        return false;
    }
    
    return true;
};

// Get enabled transport types
CONFIG.getEnabledTransportTypes = function() {
    return Object.entries(CONFIG.TRANSPORT_TYPES)
        .filter(([_, config]) => config.enabled)
        .map(([type, _]) => type);
};

// Get transport type by priority
CONFIG.getTransportTypesByPriority = function() {
    return Object.entries(CONFIG.TRANSPORT_TYPES)
        .sort(([_, a], [__, b]) => a.priority - b.priority)
        .map(([type, config]) => ({ type, ...config }));
};

// Dynamic configuration updates
CONFIG.updateTransportTypeEnabled = function(type, enabled) {
    if (CONFIG.TRANSPORT_TYPES[type]) {
        CONFIG.TRANSPORT_TYPES[type].enabled = enabled;
        return true;
    }
    return false;
};

// Environment-specific overrides
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    CONFIG.DEBUG.ENABLED = true;
    CONFIG.API.BASE_URL = 'http://localhost:8081/api/v1';
} else {
    CONFIG.DEBUG.ENABLED = false;
    CONFIG.API.BASE_URL = '/api/v1'; // Relative URL for production
}

// Initialize configuration
if (!CONFIG.validate()) {
    throw new Error('Configuration validation failed. Check console for details.');
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}