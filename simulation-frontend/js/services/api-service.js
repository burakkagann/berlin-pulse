// Berlin Transport Time Machine - API Service

class ApiService {
    constructor() {
        this.baseUrl = CONFIG.API.BASE_URL;
        this.timeout = CONFIG.API.TIMEOUT;
        this.retryAttempts = CONFIG.API.RETRY_ATTEMPTS;
        this.retryDelay = CONFIG.API.RETRY_DELAY;
        
        // Request cache
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
        
        // Connection status
        this.isOnline = true;
        this.lastConnectionCheck = null;
        
        this.initializeConnectionMonitoring();
    }
    
    /**
     * Initialize connection monitoring
     */
    initializeConnectionMonitoring() {
        // Check connection status periodically
        setInterval(() => {
            this.checkConnection();
        }, 30000); // Check every 30 seconds
        
        // Listen for online/offline events
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.onConnectionStatusChange(true);
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.onConnectionStatusChange(false);
        });
    }
    
    /**
     * Check API connection status
     */
    async checkConnection() {
        try {
            const response = await this.makeRequest('/api/v1/health', {}, { timeout: 5000, cache: false });
            const wasOffline = !this.isOnline;
            this.isOnline = true;
            this.lastConnectionCheck = new Date();
            
            if (wasOffline) {
                this.onConnectionStatusChange(true);
            }
            
            return response;
        } catch (error) {
            const wasOnline = this.isOnline;
            this.isOnline = false;
            
            if (wasOnline) {
                this.onConnectionStatusChange(false);
            }
            
            throw error;
        }
    }
    
    /**
     * Connection status change handler
     */
    onConnectionStatusChange(isOnline) {
        const event = new CustomEvent('connectionStatusChange', {
            detail: { isOnline, timestamp: new Date() }
        });
        window.dispatchEvent(event);
        
        if (CONFIG.DEBUG.API_LOGGING) {
            console.log(`API connection status: ${isOnline ? 'online' : 'offline'}`);
        }
    }
    
    /**
     * Make HTTP request with retry logic
     */
    async makeRequest(endpoint, params = {}, options = {}) {
        const {
            method = 'GET',
            timeout = this.timeout,
            cache = true,
            retries = this.retryAttempts
        } = options;
        
        // Generate cache key
        const cacheKey = `${method}:${endpoint}:${JSON.stringify(params)}`;
        
        // Check cache
        if (cache && method === 'GET') {
            const cachedResult = this.getFromCache(cacheKey);
            if (cachedResult) {
                return cachedResult;
            }
        }
        
        let lastError;
        
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const result = await this.executeRequest(endpoint, params, method, timeout);
                
                // Cache successful GET requests
                if (cache && method === 'GET' && result) {
                    this.setCache(cacheKey, result);
                }
                
                return result;
                
            } catch (error) {
                lastError = error;
                
                if (CONFIG.DEBUG.API_LOGGING) {
                    console.warn(`API request attempt ${attempt + 1} failed:`, error.message);
                }
                
                // Don't retry on client errors (4xx)
                if (error.status >= 400 && error.status < 500) {
                    break;
                }
                
                // Wait before retry
                if (attempt < retries) {
                    await this.sleep(this.retryDelay * Math.pow(2, attempt)); // Exponential backoff
                }
            }
        }
        
        throw lastError;
    }
    
    /**
     * Execute single HTTP request
     */
    async executeRequest(endpoint, params, method, timeout) {
        const url = new URL(endpoint, this.baseUrl);
        
        // Add query parameters for GET requests
        if (method === 'GET' && params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== null && value !== undefined) {
                    if (Array.isArray(value)) {
                        value.forEach(v => url.searchParams.append(key, v));
                    } else {
                        url.searchParams.append(key, value);
                    }
                }
            });
        }
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        
        try {
            const response = await fetch(url.toString(), {
                method,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: method !== 'GET' ? JSON.stringify(params) : undefined
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (CONFIG.DEBUG.API_LOGGING) {
                console.log(`API ${method} ${endpoint}:`, data);
            }
            
            return data;
            
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeout}ms`);
            }
            
            throw error;
        }
    }
    
    /**
     * Get available time range for simulation
     */
    async getTimeRange() {
        return this.makeRequest('/api/v1/simulation/time-range');
    }
    
    /**
     * Get vehicle positions at specific time
     */
    async getVehiclesAtTime(timestamp, options = {}) {
        const params = {
            timestamp: timestamp.toISOString(),
            time_window_seconds: options.timeWindowSeconds || CONFIG.ANIMATION.FRAME_INTERVAL_SECONDS,
            transport_types: options.transportTypes || CONFIG.getEnabledTransportTypes(),
            routes: options.routes || undefined
        };
        
        return this.makeRequest('/api/v1/simulation/vehicles', params);
    }
    
    /**
     * Get simulation data chunk
     */
    async getSimulationChunk(startTime, options = {}) {
        const params = {
            start_time: startTime.toISOString(),
            duration_minutes: options.durationMinutes || CONFIG.ANIMATION.CHUNK_DURATION_MINUTES,
            transport_types: options.transportTypes || CONFIG.getEnabledTransportTypes(),
            routes: options.routes || undefined,
            frame_interval_seconds: options.frameIntervalSeconds || CONFIG.ANIMATION.FRAME_INTERVAL_SECONDS
        };
        
        return this.makeRequest('/api/v1/simulation/data-chunk', params);
    }
    
    /**
     * Get simulation statistics
     */
    async getSimulationStats(timestamp = null) {
        const params = timestamp ? { timestamp: timestamp.toISOString() } : {};
        return this.makeRequest('/api/v1/simulation/stats', params);
    }
    
    /**
     * Get available routes
     */
    async getRoutes() {
        return this.makeRequest('/api/v1/routes');
    }
    
    /**
     * Get route geometry
     */
    async getRouteGeometry(routeId) {
        return this.makeRequest(`/api/v1/routes/${routeId}/geometry`);
    }
    
    /**
     * Get tracked stops
     */
    async getStops(trackedOnly = true) {
        return this.makeRequest('/api/v1/stops', { tracked_only: trackedOnly });
    }
    
    /**
     * Get transport types configuration
     */
    async getTransportTypes() {
        return this.makeRequest('/api/v1/transport-types');
    }
    
    /**
     * Get time series data
     */
    async getTimeSeriesData(startTime, endTime, options = {}) {
        const params = {
            start_time: startTime.toISOString(),
            end_time: endTime.toISOString(),
            interval_minutes: options.intervalMinutes || 60,
            transport_types: options.transportTypes || CONFIG.getEnabledTransportTypes()
        };
        
        return this.makeRequest('/api/v1/simulation/time-series', params);
    }
    
    /**
     * Cache management
     */
    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        this.cache.delete(key);
        return null;
    }
    
    setCache(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
        
        // Limit cache size
        if (this.cache.size > 100) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
    }
    
    clearCache() {
        this.cache.clear();
    }
    
    /**
     * Utility methods
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Get connection status
     */
    getConnectionStatus() {
        return {
            isOnline: this.isOnline,
            lastCheck: this.lastConnectionCheck
        };
    }
}

// Create global instance
window.apiService = new ApiService();