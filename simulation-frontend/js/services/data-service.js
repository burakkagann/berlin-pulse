// Berlin Transport Time Machine - Data Service

class DataService {
    constructor(apiService) {
        this.apiService = apiService;
        
        // Cache management
        this.cache = new Map();
        this.cacheTimeout = 10 * 60 * 1000; // 10 minutes
        this.maxCacheSize = 50;
        
        // Data state
        this.isLoading = false;
        this.loadingProgress = 0;
        this.lastError = null;
        
        // Prefetch queue
        this.prefetchQueue = [];
        this.isPrefetching = false;
    }
    
    /**
     * Get cached data or fetch from API
     */
    async getData(key, fetchFunction, useCache = true) {
        // Check cache first
        if (useCache && this.cache.has(key)) {
            const cached = this.cache.get(key);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
            // Remove expired cache
            this.cache.delete(key);
        }
        
        try {
            this.isLoading = true;
            const data = await fetchFunction();
            
            // Cache the result
            if (useCache) {
                this.setCache(key, data);
            }
            
            this.isLoading = false;
            this.lastError = null;
            return data;
            
        } catch (error) {
            this.isLoading = false;
            this.lastError = error;
            throw error;
        }
    }
    
    /**
     * Get time range data
     */
    async getTimeRange() {
        return this.getData('timeRange', () => this.apiService.getTimeRange());
    }
    
    /**
     * Get vehicle positions at specific time
     */
    async getVehiclePositions(timestamp, options = {}) {
        const key = `vehicles_${timestamp.toISOString()}_${JSON.stringify(options)}`;
        return this.getData(key, () => this.apiService.getVehiclesAtTime(timestamp, options));
    }
    
    /**
     * Get simulation chunk
     */
    async getSimulationChunk(startTime, options = {}) {
        const key = `chunk_${startTime.toISOString()}_${JSON.stringify(options)}`;
        return this.getData(key, () => this.apiService.getSimulationChunk(startTime, options));
    }
    
    /**
     * Get routes data
     */
    async getRoutes() {
        return this.getData('routes', () => this.apiService.getRoutes());
    }
    
    /**
     * Get stops data
     */
    async getStops() {
        return this.getData('stops', () => this.apiService.getStops());
    }
    
    /**
     * Prefetch data for upcoming time periods
     */
    async prefetchData(currentTime, duration = 30) {
        if (this.isPrefetching) return;
        
        this.isPrefetching = true;
        
        try {
            // Prefetch next few chunks
            for (let i = 1; i <= 3; i++) {
                const nextTime = new Date(currentTime.getTime() + (duration * 60 * 1000 * i));
                
                this.prefetchQueue.push({
                    type: 'chunk',
                    startTime: nextTime,
                    options: { durationMinutes: duration }
                });
            }
            
            // Process prefetch queue
            await this.processPrefetchQueue();
            
        } finally {
            this.isPrefetching = false;
        }
    }
    
    /**
     * Process prefetch queue
     */
    async processPrefetchQueue() {
        while (this.prefetchQueue.length > 0) {
            const item = this.prefetchQueue.shift();
            
            try {
                switch (item.type) {
                    case 'chunk':
                        await this.getSimulationChunk(item.startTime, item.options);
                        break;
                    case 'vehicles':
                        await this.getVehiclePositions(item.timestamp, item.options);
                        break;
                }
                
                // Small delay to prevent overwhelming the API
                await this.sleep(100);
                
            } catch (error) {
                console.warn('Prefetch failed:', error);
                // Continue with next item
            }
        }
    }
    
    /**
     * Cache management
     */
    setCache(key, data) {
        // Remove oldest entries if cache is full
        if (this.cache.size >= this.maxCacheSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });
    }
    
    /**
     * Clear cache
     */
    clearCache() {
        this.cache.clear();
    }
    
    /**
     * Clear expired cache entries
     */
    clearExpiredCache() {
        const now = Date.now();
        for (const [key, value] of this.cache.entries()) {
            if (now - value.timestamp > this.cacheTimeout) {
                this.cache.delete(key);
            }
        }
    }
    
    /**
     * Get cache statistics
     */
    getCacheStats() {
        return {
            size: this.cache.size,
            maxSize: this.maxCacheSize,
            usage: (this.cache.size / this.maxCacheSize) * 100
        };
    }
    
    /**
     * Utility methods
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Get service status
     */
    getStatus() {
        return {
            isLoading: this.isLoading,
            loadingProgress: this.loadingProgress,
            lastError: this.lastError,
            cacheStats: this.getCacheStats(),
            isPrefetching: this.isPrefetching,
            prefetchQueueSize: this.prefetchQueue.length
        };
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.DataService = DataService;
}