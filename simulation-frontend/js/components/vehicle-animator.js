// Berlin Transport Time Machine - Vehicle Animator

class VehicleAnimator {
    constructor(mapRenderer) {
        this.mapRenderer = mapRenderer;
        this.animationFrameId = null;
        this.isAnimating = false;
        this.isPaused = false;
        
        // Animation state
        this.currentFrame = 0;
        this.totalFrames = 0;
        this.animationSpeed = CONFIG.ANIMATION.DEFAULT_SPEED;
        this.frameRate = CONFIG.ANIMATION.FRAME_RATE;
        
        // Frame data
        this.frameData = [];
        this.frameTimestamps = [];
        this.interpolationEnabled = CONFIG.ANIMATION.INTERPOLATION_ENABLED;
        
        // Performance tracking
        this.lastFrameTime = 0;
        this.actualFrameRate = 0;
        this.frameRateHistory = [];
        this.droppedFrames = 0;
        
        // Vehicle position cache for interpolation
        this.vehiclePositionCache = new Map();
        this.lastVehiclePositions = new Map();
        
        this.initializeAnimator();
    }
    
    /**
     * Initialize animator
     */
    initializeAnimator() {
        // Set up frame rate monitoring
        this.startFrameRateMonitoring();
        
        // Listen for visibility changes to pause/resume
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && this.isAnimating) {
                this.pause();
            }
        });
        
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Vehicle animator initialized');
        }
    }
    
    /**
     * Load animation data from simulation chunk
     */
    loadAnimationData(simulationChunk) {
        try {
            this.frameData = [];
            this.frameTimestamps = [];
            this.currentFrame = 0;
            
            // Process chunk data into animation frames
            this.processChunkIntoFrames(simulationChunk);
            
            this.totalFrames = this.frameData.length;
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log(`Loaded animation data: ${this.totalFrames} frames`);
            }
            
            // Dispatch data loaded event
            const event = new CustomEvent('animationDataLoaded', {
                detail: {
                    totalFrames: this.totalFrames,
                    duration: simulationChunk.duration_seconds,
                    vehicleCount: simulationChunk.total_vehicles
                }
            });
            window.dispatchEvent(event);
            
        } catch (error) {
            console.error('Failed to load animation data:', error);
            throw error;
        }
    }
    
    /**
     * Process simulation chunk into animation frames
     */
    processChunkIntoFrames(simulationChunk) {
        const vehicles = simulationChunk.vehicles;
        const frameInterval = CONFIG.ANIMATION.FRAME_INTERVAL_SECONDS * 1000; // Convert to ms
        
        // Group vehicles by timestamp
        const vehiclesByTime = new Map();
        
        vehicles.forEach(vehicle => {
            const timestamp = new Date(vehicle.timestamp).getTime();
            
            // Round timestamp to frame interval
            const frameTime = Math.round(timestamp / frameInterval) * frameInterval;
            
            if (!vehiclesByTime.has(frameTime)) {
                vehiclesByTime.set(frameTime, []);
            }
            
            vehiclesByTime.get(frameTime).push(vehicle);
        });
        
        // Sort timestamps and create frames
        const sortedTimestamps = Array.from(vehiclesByTime.keys()).sort((a, b) => a - b);
        
        sortedTimestamps.forEach(timestamp => {
            this.frameTimestamps.push(new Date(timestamp));
            this.frameData.push(vehiclesByTime.get(timestamp));
        });
        
        // If interpolation is enabled, generate intermediate frames
        if (this.interpolationEnabled && this.frameData.length > 1) {
            this.generateInterpolatedFrames();
        }
    }
    
    /**
     * Generate interpolated frames for smooth animation
     */
    generateInterpolatedFrames() {
        const interpolatedFrames = [];
        const interpolatedTimestamps = [];
        const interpolationSteps = Math.max(1, Math.floor(CONFIG.ANIMATION.FRAME_RATE / 2));
        
        for (let i = 0; i < this.frameData.length - 1; i++) {
            const currentFrame = this.frameData[i];
            const nextFrame = this.frameData[i + 1];
            const currentTime = this.frameTimestamps[i];
            const nextTime = this.frameTimestamps[i + 1];
            
            // Add current frame
            interpolatedFrames.push(currentFrame);
            interpolatedTimestamps.push(currentTime);
            
            // Generate interpolated frames
            for (let step = 1; step < interpolationSteps; step++) {
                const progress = step / interpolationSteps;
                const interpolatedTime = new Date(
                    currentTime.getTime() + (nextTime.getTime() - currentTime.getTime()) * progress
                );
                
                const interpolatedFrame = this.interpolateFrame(currentFrame, nextFrame, progress);
                
                interpolatedFrames.push(interpolatedFrame);
                interpolatedTimestamps.push(interpolatedTime);
            }
        }
        
        // Add last frame
        if (this.frameData.length > 0) {
            interpolatedFrames.push(this.frameData[this.frameData.length - 1]);
            interpolatedTimestamps.push(this.frameTimestamps[this.frameTimestamps.length - 1]);
        }
        
        this.frameData = interpolatedFrames;
        this.frameTimestamps = interpolatedTimestamps;
    }
    
    /**
     * Interpolate between two frames
     */
    interpolateFrame(frame1, frame2, progress) {
        const interpolatedVehicles = [];
        
        // Create lookup maps for efficient matching
        const frame1Map = new Map();
        const frame2Map = new Map();
        
        frame1.forEach(vehicle => frame1Map.set(vehicle.vehicle_id, vehicle));
        frame2.forEach(vehicle => frame2Map.set(vehicle.vehicle_id, vehicle));
        
        // Interpolate vehicles that exist in both frames
        frame1Map.forEach((vehicle1, vehicleId) => {
            const vehicle2 = frame2Map.get(vehicleId);
            
            if (vehicle2) {
                // Interpolate position
                const lat = vehicle1.latitude + (vehicle2.latitude - vehicle1.latitude) * progress;
                const lng = vehicle1.longitude + (vehicle2.longitude - vehicle1.longitude) * progress;
                
                const interpolatedVehicle = {
                    ...vehicle1,
                    latitude: lat,
                    longitude: lng,
                    timestamp: new Date(
                        new Date(vehicle1.timestamp).getTime() +
                        (new Date(vehicle2.timestamp).getTime() - new Date(vehicle1.timestamp).getTime()) * progress
                    ).toISOString()
                };
                
                interpolatedVehicles.push(interpolatedVehicle);
            } else {
                // Vehicle only exists in frame1 - fade out
                if (progress < 0.5) {
                    interpolatedVehicles.push({
                        ...vehicle1,
                        opacity: 1 - progress * 2
                    });
                }
            }
        });
        
        // Add vehicles that only exist in frame2 - fade in
        frame2Map.forEach((vehicle2, vehicleId) => {
            if (!frame1Map.has(vehicleId) && progress > 0.5) {
                interpolatedVehicles.push({
                    ...vehicle2,
                    opacity: (progress - 0.5) * 2
                });
            }
        });
        
        return interpolatedVehicles;
    }
    
    /**
     * Start animation
     */
    startAnimation() {
        if (this.isAnimating || this.frameData.length === 0) {
            return;
        }
        
        this.isAnimating = true;
        this.isPaused = false;
        this.lastFrameTime = performance.now();
        
        this.animate();
        
        // Dispatch animation started event
        const event = new CustomEvent('animationStarted', {
            detail: { speed: this.animationSpeed }
        });
        window.dispatchEvent(event);
        
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Animation started');
        }
    }
    
    /**
     * Main animation loop
     */
    animate() {
        if (!this.isAnimating || this.isPaused) {
            return;
        }
        
        const currentTime = performance.now();
        const deltaTime = currentTime - this.lastFrameTime;
        
        // Calculate target frame rate based on speed
        const targetFrameInterval = 1000 / (this.frameRate * this.animationSpeed);
        
        if (deltaTime >= targetFrameInterval) {
            // Update frame
            this.updateFrame();
            
            // Track frame rate
            this.trackFrameRate(currentTime);
            
            this.lastFrameTime = currentTime;
        }
        
        // Schedule next frame
        this.animationFrameId = requestAnimationFrame(() => {
            this.animate();
        });
    }
    
    /**
     * Update current frame
     */
    updateFrame() {
        if (this.currentFrame >= this.frameData.length) {
            // Animation complete
            this.stopAnimation();
            return;
        }
        
        const currentFrameData = this.frameData[this.currentFrame];
        const currentTimestamp = this.frameTimestamps[this.currentFrame];
        
        if (currentFrameData && this.mapRenderer) {
            // Update vehicle positions on map
            this.mapRenderer.updateVehiclePositions(currentFrameData);
            
            // Update time display
            this.updateTimeDisplay(currentTimestamp);
            
            // Dispatch frame update event
            const event = new CustomEvent('animationFrameUpdate', {
                detail: {
                    frame: this.currentFrame,
                    totalFrames: this.totalFrames,
                    timestamp: currentTimestamp,
                    vehicleCount: currentFrameData.length,
                    progress: this.currentFrame / this.totalFrames
                }
            });
            window.dispatchEvent(event);
        }
        
        this.currentFrame++;
    }
    
    /**
     * Pause animation
     */
    pause() {
        this.isPaused = true;
        
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        
        // Dispatch animation paused event
        const event = new CustomEvent('animationPaused');
        window.dispatchEvent(event);
        
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Animation paused');
        }
    }
    
    /**
     * Resume animation
     */
    resume() {
        if (this.isAnimating && this.isPaused) {
            this.isPaused = false;
            this.lastFrameTime = performance.now();
            this.animate();
            
            // Dispatch animation resumed event
            const event = new CustomEvent('animationResumed');
            window.dispatchEvent(event);
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log('Animation resumed');
            }
        }
    }
    
    /**
     * Stop animation
     */
    stopAnimation() {
        this.isAnimating = false;
        this.isPaused = false;
        
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        
        // Dispatch animation stopped event
        const event = new CustomEvent('animationStopped', {
            detail: { 
                completed: this.currentFrame >= this.frameData.length,
                finalFrame: this.currentFrame
            }
        });
        window.dispatchEvent(event);
        
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Animation stopped');
        }
    }
    
    /**
     * Reset animation to beginning
     */
    reset() {
        this.stopAnimation();
        this.currentFrame = 0;
        
        // Show first frame
        if (this.frameData.length > 0) {
            this.mapRenderer.updateVehiclePositions(this.frameData[0]);
            this.updateTimeDisplay(this.frameTimestamps[0]);
        }
        
        // Dispatch animation reset event
        const event = new CustomEvent('animationReset');
        window.dispatchEvent(event);
    }
    
    /**
     * Jump to specific frame
     */
    jumpToFrame(frameIndex) {
        if (frameIndex < 0 || frameIndex >= this.frameData.length) {
            return;
        }
        
        const wasAnimating = this.isAnimating;
        
        if (wasAnimating) {
            this.pause();
        }
        
        this.currentFrame = frameIndex;
        
        // Update display
        const frameData = this.frameData[frameIndex];
        const timestamp = this.frameTimestamps[frameIndex];
        
        this.mapRenderer.updateVehiclePositions(frameData);
        this.updateTimeDisplay(timestamp);
        
        // Dispatch jump event
        const event = new CustomEvent('animationJumped', {
            detail: {
                frame: frameIndex,
                timestamp: timestamp,
                progress: frameIndex / this.totalFrames
            }
        });
        window.dispatchEvent(event);
        
        if (wasAnimating) {
            this.resume();
        }
    }
    
    /**
     * Jump to specific time
     */
    jumpToTime(targetTime) {
        const targetTimestamp = targetTime.getTime();
        
        // Find closest frame
        let closestFrame = 0;
        let closestDiff = Math.abs(this.frameTimestamps[0].getTime() - targetTimestamp);
        
        for (let i = 1; i < this.frameTimestamps.length; i++) {
            const diff = Math.abs(this.frameTimestamps[i].getTime() - targetTimestamp);
            if (diff < closestDiff) {
                closestDiff = diff;
                closestFrame = i;
            }
        }
        
        this.jumpToFrame(closestFrame);
    }
    
    /**
     * Set animation speed
     */
    setSpeed(speed) {
        if (speed > 0 && CONFIG.ANIMATION.SPEED_OPTIONS.includes(speed)) {
            this.animationSpeed = speed;
            
            // Dispatch speed change event
            const event = new CustomEvent('animationSpeedChanged', {
                detail: { speed: speed }
            });
            window.dispatchEvent(event);
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log(`Animation speed set to ${speed}x`);
            }
        }
    }
    
    /**
     * Step forward one frame
     */
    stepForward() {
        if (this.currentFrame < this.frameData.length - 1) {
            this.jumpToFrame(this.currentFrame + 1);
        }
    }
    
    /**
     * Step backward one frame
     */
    stepBackward() {
        if (this.currentFrame > 0) {
            this.jumpToFrame(this.currentFrame - 1);
        }
    }
    
    /**
     * Update time display
     */
    updateTimeDisplay(timestamp) {
        const currentTimeElement = document.getElementById('current-time');
        const currentDateElement = document.getElementById('current-date');
        
        if (currentTimeElement && timestamp) {
            currentTimeElement.textContent = moment(timestamp).format('HH:mm:ss');
        }
        
        if (currentDateElement && timestamp) {
            currentDateElement.textContent = moment(timestamp).format('YYYY/MM/DD');
        }
    }
    
    /**
     * Track frame rate performance
     */
    trackFrameRate(currentTime) {
        if (this.frameRateHistory.length > 0) {
            const lastTime = this.frameRateHistory[this.frameRateHistory.length - 1];
            const fps = 1000 / (currentTime - lastTime);
            
            // Keep history of last 30 frames
            if (this.frameRateHistory.length >= 30) {
                this.frameRateHistory.shift();
            }
            
            this.frameRateHistory.push(currentTime);
            
            // Calculate average FPS
            if (this.frameRateHistory.length > 1) {
                const totalTime = currentTime - this.frameRateHistory[0];
                this.actualFrameRate = (this.frameRateHistory.length - 1) * 1000 / totalTime;
            }
            
            // Track dropped frames
            if (fps < this.frameRate * 0.8) {
                this.droppedFrames++;
            }
        } else {
            this.frameRateHistory.push(currentTime);
        }
    }
    
    /**
     * Start frame rate monitoring
     */
    startFrameRateMonitoring() {
        setInterval(() => {
            if (this.isAnimating && CONFIG.DEBUG.ANIMATION_STATS) {
                console.log(`FPS: ${this.actualFrameRate.toFixed(1)}, Dropped: ${this.droppedFrames}`);
            }
            
            // Update frame rate display
            const frameRateElement = document.getElementById('frame-rate');
            if (frameRateElement) {
                frameRateElement.textContent = `${this.actualFrameRate.toFixed(1)} fps`;
            }
        }, 1000);
    }
    
    /**
     * Get animation state
     */
    getState() {
        return {
            isAnimating: this.isAnimating,
            isPaused: this.isPaused,
            currentFrame: this.currentFrame,
            totalFrames: this.totalFrames,
            progress: this.totalFrames > 0 ? this.currentFrame / this.totalFrames : 0,
            speed: this.animationSpeed,
            frameRate: this.actualFrameRate,
            droppedFrames: this.droppedFrames
        };
    }
    
    /**
     * Get performance stats
     */
    getPerformanceStats() {
        return {
            actualFrameRate: this.actualFrameRate,
            targetFrameRate: this.frameRate,
            droppedFrames: this.droppedFrames,
            frameRateHistory: [...this.frameRateHistory]
        };
    }
    
    /**
     * Toggle interpolation
     */
    toggleInterpolation() {
        this.interpolationEnabled = !this.interpolationEnabled;
        return this.interpolationEnabled;
    }
    
    /**
     * Destroy animator
     */
    destroy() {
        this.stopAnimation();
        this.frameData = [];
        this.frameTimestamps = [];
        this.vehiclePositionCache.clear();
        this.lastVehiclePositions.clear();
    }
}