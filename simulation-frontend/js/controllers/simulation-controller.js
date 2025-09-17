// Berlin Transport Time Machine - Simulation Controller

class SimulationController {
    constructor(apiService, mapRenderer, vehicleAnimator) {
        this.apiService = apiService;
        this.mapRenderer = mapRenderer;
        this.vehicleAnimator = vehicleAnimator;
        
        // Simulation state
        this.timeRange = null;
        this.currentTime = null;
        this.isPlaying = false;
        this.playbackSpeed = CONFIG.ANIMATION.DEFAULT_SPEED;
        this.enabledTransportTypes = CONFIG.getEnabledTransportTypes();
        
        // Data management
        this.chunkCache = new Map();
        this.cacheSize = CONFIG.PERFORMANCE.CHUNK_CACHE_SIZE;
        this.preloadChunks = CONFIG.PERFORMANCE.PRELOAD_CHUNKS;
        this.currentChunk = null;
        this.nextChunks = [];
        
        // Routes and stops data
        this.routes = [];
        this.stops = [];
        this.routeGeometries = new Map();
        
        // Loading state
        this.isLoading = false;
        this.loadingProgress = 0;
        
        // Error handling
        this.lastError = null;
        this.retryCount = 0;
        
        this.initializeController();
    }
    
    /**
     * Initialize simulation controller
     */
    async initializeController() {
        try {
            this.showLoading('Initializing simulation...');
            
            // Load basic configuration
            await this.loadTimeRange();
            await this.loadRoutes();
            await this.loadStops();
            
            // Initialize time to start of data
            if (this.timeRange) {
                this.currentTime = new Date(this.timeRange.start_time);
            }
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Load initial frame
            await this.loadCurrentFrame();
            
            this.hideLoading();
            
            // Dispatch initialization complete event
            const event = new CustomEvent('simulationInitialized', {
                detail: {
                    timeRange: this.timeRange,
                    routeCount: this.routes.length,
                    stopCount: this.stops.length
                }
            });
            window.dispatchEvent(event);
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log('Simulation controller initialized successfully');
            }
            
        } catch (error) {
            this.handleError('Failed to initialize simulation', error);
        }
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Animation events
        window.addEventListener('animationStopped', (e) => {
            if (e.detail.completed) {
                this.onAnimationComplete();
            }
        });
        
        window.addEventListener('animationFrameUpdate', (e) => {
            this.updateSimulationState(e.detail);
        });
        
        // Connection status events
        window.addEventListener('connectionStatusChange', (e) => {
            this.onConnectionStatusChange(e.detail.isOnline);
        });
        
        // Keyboard shortcuts
        if (CONFIG.UI.KEYBOARD_SHORTCUTS_ENABLED) {
            this.setupKeyboardShortcuts();
        }
    }
    
    /**
     * Load available time range
     */
    async loadTimeRange() {
        try {
            this.timeRange = await this.apiService.getTimeRange();
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log('Time range loaded:', this.timeRange);
            }
            
        } catch (error) {
            throw new Error(`Failed to load time range: ${error.message}`);
        }
    }
    
    /**
     * Load available routes
     */
    async loadRoutes() {
        try {
            this.routes = await this.apiService.getRoutes();
            
            // Load route geometries for significant routes
            const routesToLoad = this.routes
                .filter(route => route.geometry_available && route.vehicle_count_24h > 50)
                .slice(0, 20); // Limit to prevent overload
            
            for (const route of routesToLoad) {
                try {
                    const geometry = await this.apiService.getRouteGeometry(route.route_id);
                    this.routeGeometries.set(route.route_id, geometry);
                    this.mapRenderer.addRouteGeometry(route.route_id, geometry.geometry, route);
                } catch (error) {
                    console.warn(`Failed to load geometry for route ${route.route_id}:`, error);
                }
            }
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log(`Loaded ${this.routes.length} routes, ${routesToLoad.length} with geometry`);
            }
            
        } catch (error) {
            console.warn('Failed to load routes:', error);
        }
    }
    
    /**
     * Load tracked stops
     */
    async loadStops() {
        try {
            this.stops = await this.apiService.getStops(true);
            this.mapRenderer.addStops(this.stops);
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log(`Loaded ${this.stops.length} stops`);
            }
            
        } catch (error) {
            console.warn('Failed to load stops:', error);
        }
    }
    
    /**
     * Load current frame data
     */
    async loadCurrentFrame() {
        if (!this.currentTime) return;
        
        try {
            const vehicles = await this.apiService.getVehiclesAtTime(this.currentTime, {
                transportTypes: this.enabledTransportTypes
            });
            
            this.mapRenderer.updateVehiclePositions(vehicles.vehicles);
            this.updateStats(vehicles);
            
        } catch (error) {
            console.error('Failed to load current frame:', error);
        }
    }
    
    /**
     * Play simulation
     */
    async play() {
        if (this.isPlaying || !this.currentTime) return;
        
        try {
            this.isPlaying = true;
            this.showLoading('Loading simulation data...');
            
            // Load simulation chunk
            const chunkDuration = CONFIG.ANIMATION.CHUNK_DURATION_MINUTES;
            const chunk = await this.loadSimulationChunk(this.currentTime, chunkDuration);
            
            if (chunk && chunk.vehicles.length > 0) {
                // Load data into animator
                this.vehicleAnimator.loadAnimationData(chunk);
                this.vehicleAnimator.setSpeed(this.playbackSpeed);
                
                this.hideLoading();
                
                // Start animation
                this.vehicleAnimator.startAnimation();
                
                // Preload next chunks
                this.preloadNextChunks();
                
                // Dispatch play event
                const event = new CustomEvent('simulationPlayStarted', {
                    detail: { 
                        startTime: this.currentTime,
                        speed: this.playbackSpeed,
                        chunkDuration: chunkDuration
                    }
                });
                window.dispatchEvent(event);
                
            } else {
                this.hideLoading();
                this.handleError('No vehicle data available for selected time period');
                this.isPlaying = false;
            }
            
        } catch (error) {
            this.hideLoading();
            this.handleError('Failed to start simulation', error);
            this.isPlaying = false;
        }
    }
    
    /**
     * Pause simulation
     */
    pause() {
        if (!this.isPlaying) return;
        
        this.isPlaying = false;
        this.vehicleAnimator.pause();
        
        // Dispatch pause event
        const event = new CustomEvent('simulationPaused');
        window.dispatchEvent(event);
    }
    
    /**
     * Resume simulation
     */
    resume() {
        if (this.isPlaying) return;
        
        this.isPlaying = true;
        this.vehicleAnimator.resume();
        
        // Dispatch resume event
        const event = new CustomEvent('simulationResumed');
        window.dispatchEvent(event);
    }
    
    /**
     * Stop simulation
     */
    stop() {
        this.isPlaying = false;
        this.vehicleAnimator.stopAnimation();
        
        // Dispatch stop event
        const event = new CustomEvent('simulationStopped');
        window.dispatchEvent(event);
    }
    
    /**
     * Reset simulation to beginning
     */
    reset() {
        this.stop();
        
        if (this.timeRange) {
            this.currentTime = new Date(this.timeRange.start_time);
            this.loadCurrentFrame();
        }
        
        this.vehicleAnimator.reset();
        
        // Dispatch reset event
        const event = new CustomEvent('simulationReset');
        window.dispatchEvent(event);
    }
    
    /**
     * Jump to specific time
     */
    async jumpToTime(targetTime) {
        if (!this.timeRange || targetTime < new Date(this.timeRange.start_time) || 
            targetTime > new Date(this.timeRange.end_time)) {
            console.warn('Target time outside available range');
            return;
        }
        
        const wasPlaying = this.isPlaying;
        
        if (wasPlaying) {
            this.pause();
        }
        
        this.currentTime = new Date(targetTime);
        
        // If currently animating, try to jump within current animation
        if (this.vehicleAnimator.totalFrames > 0) {
            this.vehicleAnimator.jumpToTime(targetTime);
        } else {
            // Load single frame
            await this.loadCurrentFrame();
        }
        
        // Dispatch jump event
        const event = new CustomEvent('simulationJumped', {
            detail: { targetTime: targetTime }
        });
        window.dispatchEvent(event);
        
        if (wasPlaying) {
            this.resume();
        }
    }
    
    /**
     * Set playback speed
     */
    setSpeed(speed) {
        if (CONFIG.ANIMATION.SPEED_OPTIONS.includes(speed)) {
            this.playbackSpeed = speed;
            this.vehicleAnimator.setSpeed(speed);
            
            // Dispatch speed change event
            const event = new CustomEvent('simulationSpeedChanged', {
                detail: { speed: speed }
            });
            window.dispatchEvent(event);
        }
    }
    
    /**
     * Update enabled transport types
     */
    updateTransportTypes(transportTypes) {
        this.enabledTransportTypes = transportTypes;
        
        // Update configuration
        transportTypes.forEach(type => {
            CONFIG.updateTransportTypeEnabled(type, true);
        });
        
        // If currently playing, this will affect next chunk load
        // If paused, reload current frame
        if (!this.isPlaying) {
            this.loadCurrentFrame();
        }
        
        // Dispatch transport types update event
        const event = new CustomEvent('simulationTransportTypesUpdated', {
            detail: { transportTypes: transportTypes }
        });
        window.dispatchEvent(event);
    }
    
    /**
     * Load simulation chunk
     */
    async loadSimulationChunk(startTime, durationMinutes) {
        const cacheKey = `${startTime.toISOString()}_${durationMinutes}_${this.enabledTransportTypes.join(',')}`;
        
        // Check cache first
        if (this.chunkCache.has(cacheKey)) {
            return this.chunkCache.get(cacheKey);
        }
        
        try {
            const chunk = await this.apiService.getSimulationChunk(startTime, {
                durationMinutes: durationMinutes,
                transportTypes: this.enabledTransportTypes,
                frameIntervalSeconds: CONFIG.ANIMATION.FRAME_INTERVAL_SECONDS
            });
            
            // Cache the chunk
            this.cacheChunk(cacheKey, chunk);
            
            return chunk;
            
        } catch (error) {
            console.error('Failed to load simulation chunk:', error);
            throw error;
        }
    }
    
    /**
     * Preload next chunks for smooth playback
     */
    async preloadNextChunks() {
        if (!this.currentTime) return;
        
        const chunkDuration = CONFIG.ANIMATION.CHUNK_DURATION_MINUTES;
        
        for (let i = 1; i <= this.preloadChunks; i++) {
            const nextTime = new Date(this.currentTime.getTime() + (chunkDuration * 60 * 1000 * i));
            
            // Don't preload beyond available data
            if (nextTime > new Date(this.timeRange.end_time)) {
                break;
            }
            
            try {
                await this.loadSimulationChunk(nextTime, chunkDuration);
                
                if (CONFIG.DEBUG.ENABLED) {
                    console.log(`Preloaded chunk ${i} starting at ${nextTime.toISOString()}`);
                }
                
            } catch (error) {
                console.warn(`Failed to preload chunk ${i}:`, error);
                break;
            }
        }
    }
    
    /**
     * Cache management
     */
    cacheChunk(key, chunk) {
        // Remove oldest cache entries if limit exceeded
        if (this.chunkCache.size >= this.cacheSize) {
            const firstKey = this.chunkCache.keys().next().value;
            this.chunkCache.delete(firstKey);
        }
        
        this.chunkCache.set(key, chunk);
    }
    
    /**
     * Update simulation statistics
     */
    updateStats(vehicleData) {
        const activeVehiclesElement = document.getElementById('active-vehicles');
        const averageDelayElement = document.getElementById('average-delay');
        const dataPointsElement = document.getElementById('data-points');
        
        if (activeVehiclesElement) {
            activeVehiclesElement.textContent = vehicleData.total_vehicles || 0;
            activeVehiclesElement.classList.add('updating');
            setTimeout(() => activeVehiclesElement.classList.remove('updating'), 500);
        }
        
        if (averageDelayElement && vehicleData.vehicles) {
            const delays = vehicleData.vehicles
                .filter(v => v.delay_minutes > 0)
                .map(v => v.delay_minutes);
            
            const avgDelay = delays.length > 0 
                ? (delays.reduce((a, b) => a + b, 0) / delays.length).toFixed(1)
                : '0.0';
            
            averageDelayElement.textContent = `${avgDelay} min`;
            averageDelayElement.classList.add('updating');
            setTimeout(() => averageDelayElement.classList.remove('updating'), 500);
        }
        
        if (dataPointsElement) {
            dataPointsElement.textContent = vehicleData.vehicles?.length || 0;
        }
    }
    
    /**
     * Event handlers
     */
    onAnimationComplete() {
        this.isPlaying = false;
        
        // Try to load next chunk and continue
        if (this.currentTime && new Date(this.currentTime.getTime() + CONFIG.ANIMATION.CHUNK_DURATION_MINUTES * 60 * 1000) < new Date(this.timeRange.end_time)) {
            this.currentTime = new Date(this.currentTime.getTime() + CONFIG.ANIMATION.CHUNK_DURATION_MINUTES * 60 * 1000);
            this.play();
        }
    }
    
    updateSimulationState(frameDetail) {
        // Update current time based on animation progress
        if (frameDetail.timestamp) {
            this.currentTime = new Date(frameDetail.timestamp);
        }
        
        // Update progress display
        this.updateProgressDisplay(frameDetail.progress);
    }
    
    onConnectionStatusChange(isOnline) {
        const statusElement = document.getElementById('api-status');
        if (statusElement) {
            statusElement.className = `status-indicator ${isOnline ? 'connected' : 'disconnected'}`;
            statusElement.textContent = isOnline ? '🟢' : '🔴';
        }
        
        if (!isOnline && this.isPlaying) {
            // Pause on connection loss
            this.pause();
            this.showError('Connection lost. Simulation paused.');
        }
    }
    
    /**
     * Keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            switch (e.key) {
                case CONFIG.KEYBOARD.PLAY_PAUSE:
                    e.preventDefault();
                    this.isPlaying ? this.pause() : this.play();
                    break;
                    
                case CONFIG.KEYBOARD.STEP_FORWARD:
                    e.preventDefault();
                    this.vehicleAnimator.stepForward();
                    break;
                    
                case CONFIG.KEYBOARD.STEP_BACKWARD:
                    e.preventDefault();
                    this.vehicleAnimator.stepBackward();
                    break;
                    
                case CONFIG.KEYBOARD.RESET:
                    e.preventDefault();
                    this.reset();
                    break;
                    
                case CONFIG.KEYBOARD.SPEED_UP:
                    e.preventDefault();
                    this.increaseSpeed();
                    break;
                    
                case CONFIG.KEYBOARD.SPEED_DOWN:
                    e.preventDefault();
                    this.decreaseSpeed();
                    break;
                    
                case CONFIG.KEYBOARD.TOGGLE_ROUTES:
                    e.preventDefault();
                    this.mapRenderer.toggleRoutes();
                    break;
                    
                case CONFIG.KEYBOARD.TOGGLE_STOPS:
                    e.preventDefault();
                    this.mapRenderer.toggleStops();
                    break;
            }
        });
    }
    
    /**
     * Speed adjustment helpers
     */
    increaseSpeed() {
        const currentIndex = CONFIG.ANIMATION.SPEED_OPTIONS.indexOf(this.playbackSpeed);
        if (currentIndex < CONFIG.ANIMATION.SPEED_OPTIONS.length - 1) {
            this.setSpeed(CONFIG.ANIMATION.SPEED_OPTIONS[currentIndex + 1]);
        }
    }
    
    decreaseSpeed() {
        const currentIndex = CONFIG.ANIMATION.SPEED_OPTIONS.indexOf(this.playbackSpeed);
        if (currentIndex > 0) {
            this.setSpeed(CONFIG.ANIMATION.SPEED_OPTIONS[currentIndex - 1]);
        }
    }
    
    /**
     * Progress display
     */
    updateProgressDisplay(progress) {
        const progressElement = document.getElementById('current-progress');
        const timelineElement = document.getElementById('timeline-scrubber');
        
        if (progressElement) {
            progressElement.textContent = `${(progress * 100).toFixed(1)}%`;
        }
        
        if (timelineElement) {
            timelineElement.value = progress * 100;
            timelineElement.style.setProperty('--progress', `${progress * 100}%`);
        }
    }
    
    /**
     * UI state management
     */
    showLoading(message = 'Loading...') {
        this.isLoading = true;
        const overlay = document.getElementById('loading-overlay');
        const messageElement = document.getElementById('loading-message');
        
        if (overlay) {
            overlay.classList.remove('hidden');
        }
        
        if (messageElement) {
            messageElement.textContent = message;
        }
    }
    
    hideLoading() {
        this.isLoading = false;
        const overlay = document.getElementById('loading-overlay');
        
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }
    
    showError(message, duration = 5000) {
        console.error(message);
        
        // You could implement a toast notification system here
        // For now, just log to console and update status
        
        setTimeout(() => {
            // Clear error after duration
        }, duration);
    }
    
    handleError(message, error = null) {
        this.lastError = error;
        const fullMessage = error ? `${message}: ${error.message}` : message;
        this.showError(fullMessage);
        
        // Dispatch error event
        const event = new CustomEvent('simulationError', {
            detail: { message: fullMessage, error: error }
        });
        window.dispatchEvent(event);
    }
    
    /**
     * Get simulation state
     */
    getState() {
        return {
            timeRange: this.timeRange,
            currentTime: this.currentTime,
            isPlaying: this.isPlaying,
            playbackSpeed: this.playbackSpeed,
            enabledTransportTypes: this.enabledTransportTypes,
            isLoading: this.isLoading,
            animatorState: this.vehicleAnimator.getState(),
            cacheSize: this.chunkCache.size,
            lastError: this.lastError
        };
    }
    
    /**
     * Destroy controller
     */
    destroy() {
        this.stop();
        this.chunkCache.clear();
        this.vehicleAnimator.destroy();
    }
}