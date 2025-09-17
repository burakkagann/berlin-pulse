// Berlin Transport Time Machine - Timeline Scrubber Component

class TimelineScrubber {
    constructor(simulationController) {
        this.simulationController = simulationController;
        
        // DOM elements
        this.timelineElement = null;
        this.progressElement = null;
        this.startTimeElement = null;
        this.endTimeElement = null;
        this.currentTimeElement = null;
        
        // State
        this.isDragging = false;
        this.isEnabled = true;
        this.currentProgress = 0;
        this.timeRange = null;
        
        // Configuration
        this.precision = 0.1; // 0.1% precision
        this.updateThrottle = 50; // ms
        this.lastUpdateTime = 0;
        
        this.initialize();
    }
    
    /**
     * Initialize timeline scrubber
     */
    initialize() {
        this.getElements();
        this.setupEventListeners();
        this.setupGlobalEvents();
        
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Timeline scrubber initialized');
        }
    }
    
    /**
     * Get DOM elements
     */
    getElements() {
        this.timelineElement = document.getElementById('timeline-scrubber');
        this.progressElement = document.getElementById('current-progress');
        this.startTimeElement = document.getElementById('start-time');
        this.endTimeElement = document.getElementById('end-time');
        this.currentTimeElement = document.getElementById('current-time');
        
        if (!this.timelineElement) {
            console.warn('Timeline scrubber element not found');
            return;
        }
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        if (!this.timelineElement) return;
        
        // Mouse events
        this.timelineElement.addEventListener('mousedown', (e) => {
            this.startDrag(e);
        });
        
        this.timelineElement.addEventListener('touchstart', (e) => {
            this.startDrag(e.touches[0]);
        }, { passive: false });
        
        // Input events
        this.timelineElement.addEventListener('input', (e) => {
            if (!this.isDragging) {
                this.handleTimelineChange(parseFloat(e.target.value));
            }
        });
        
        // Keyboard events
        this.timelineElement.addEventListener('keydown', (e) => {
            this.handleKeyboard(e);
        });
        
        // Focus events
        this.timelineElement.addEventListener('focus', () => {
            this.onFocus();
        });
        
        this.timelineElement.addEventListener('blur', () => {
            this.onBlur();
        });
    }
    
    /**
     * Set up global event listeners
     */
    setupGlobalEvents() {
        // Global mouse/touch events for dragging
        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.handleDrag(e);
            }
        });
        
        document.addEventListener('touchmove', (e) => {
            if (this.isDragging) {
                e.preventDefault();
                this.handleDrag(e.touches[0]);
            }
        }, { passive: false });
        
        document.addEventListener('mouseup', () => {
            this.endDrag();
        });
        
        document.addEventListener('touchend', () => {
            this.endDrag();
        });
        
        // Simulation events
        window.addEventListener('simulationInitialized', (e) => {
            this.onSimulationInitialized(e.detail);
        });
        
        window.addEventListener('animationFrameUpdate', (e) => {
            this.onAnimationUpdate(e.detail);
        });
        
        window.addEventListener('simulationJumped', (e) => {
            this.onTimeJump(e.detail);
        });
    }
    
    /**
     * Start dragging
     */
    startDrag(event) {
        if (!this.isEnabled || !this.timelineElement) return;
        
        this.isDragging = true;
        this.timelineElement.classList.add('dragging');
        
        // Prevent text selection
        document.body.style.userSelect = 'none';
        
        // Handle initial position
        this.handleDrag(event);
    }
    
    /**
     * Handle drag movement
     */
    handleDrag(event) {
        if (!this.isDragging || !this.timelineElement) return;
        
        const rect = this.timelineElement.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const progress = Math.max(0, Math.min(1, x / rect.width));
        
        // Update timeline position
        this.updateTimelinePosition(progress * 100);
        
        // Throttle timeline changes
        this.throttledTimelineChange(progress * 100);
    }
    
    /**
     * End dragging
     */
    endDrag() {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        
        if (this.timelineElement) {
            this.timelineElement.classList.remove('dragging');
        }
        
        // Restore text selection
        document.body.style.userSelect = '';
    }
    
    /**
     * Handle timeline change with throttling
     */
    throttledTimelineChange(value) {
        const now = Date.now();
        if (now - this.lastUpdateTime < this.updateThrottle) {
            return;
        }
        
        this.lastUpdateTime = now;
        this.handleTimelineChange(value);
    }
    
    /**
     * Handle timeline value change
     */
    handleTimelineChange(value) {
        if (!this.timeRange) return;
        
        const progress = value / 100;
        this.currentProgress = progress;
        
        // Calculate target time
        const startTime = new Date(this.timeRange.start_time);
        const endTime = new Date(this.timeRange.end_time);
        const duration = endTime.getTime() - startTime.getTime();
        const targetTime = new Date(startTime.getTime() + (duration * progress));
        
        // Update simulation controller
        if (this.simulationController) {
            this.simulationController.jumpToTime(targetTime);
        }
        
        // Update progress display
        this.updateProgressDisplay(progress);
    }
    
    /**
     * Handle keyboard navigation
     */
    handleKeyboard(event) {
        if (!this.isEnabled) return;
        
        const step = this.precision;
        let newValue = parseFloat(this.timelineElement.value);
        
        switch (event.key) {
            case 'ArrowLeft':
                event.preventDefault();
                newValue = Math.max(0, newValue - step);
                break;
                
            case 'ArrowRight':
                event.preventDefault();
                newValue = Math.min(100, newValue + step);
                break;
                
            case 'Home':
                event.preventDefault();
                newValue = 0;
                break;
                
            case 'End':
                event.preventDefault();
                newValue = 100;
                break;
                
            case 'PageUp':
                event.preventDefault();
                newValue = Math.max(0, newValue - 10);
                break;
                
            case 'PageDown':
                event.preventDefault();
                newValue = Math.min(100, newValue + 10);
                break;
                
            default:
                return;
        }
        
        this.updateTimelinePosition(newValue);
        this.handleTimelineChange(newValue);
    }
    
    /**
     * Update timeline position without triggering change
     */
    updateTimelinePosition(progress) {
        if (!this.timelineElement) return;
        
        this.timelineElement.value = progress;
        this.timelineElement.style.setProperty('--progress', `${progress}%`);
    }
    
    /**
     * Update progress display
     */
    updateProgressDisplay(progress) {
        if (this.progressElement) {
            this.progressElement.textContent = `${(progress * 100).toFixed(1)}%`;
        }
    }
    
    /**
     * Update time range display
     */
    updateTimeRangeDisplay(timeRange) {
        if (this.startTimeElement && timeRange) {
            this.startTimeElement.textContent = moment(timeRange.start_time).format('HH:mm');
        }
        
        if (this.endTimeElement && timeRange) {
            this.endTimeElement.textContent = moment(timeRange.end_time).format('HH:mm');
        }
    }
    
    /**
     * Update current time display
     */
    updateCurrentTimeDisplay(timestamp) {
        if (this.currentTimeElement && timestamp) {
            this.currentTimeElement.textContent = moment(timestamp).format('HH:mm:ss');
        }
    }
    
    /**
     * Event handlers
     */
    onSimulationInitialized(detail) {
        this.timeRange = detail.timeRange;
        this.updateTimeRangeDisplay(this.timeRange);
        this.setEnabled(true);
    }
    
    onAnimationUpdate(detail) {
        if (!this.isDragging) {
            this.currentProgress = detail.progress || 0;
            this.updateTimelinePosition(this.currentProgress * 100);
            this.updateProgressDisplay(this.currentProgress);
            
            if (detail.timestamp) {
                this.updateCurrentTimeDisplay(detail.timestamp);
            }
        }
    }
    
    onTimeJump(detail) {
        if (detail.targetTime && this.timeRange) {
            const startTime = new Date(this.timeRange.start_time);
            const endTime = new Date(this.timeRange.end_time);
            const duration = endTime.getTime() - startTime.getTime();
            const elapsed = detail.targetTime.getTime() - startTime.getTime();
            const progress = elapsed / duration;
            
            this.currentProgress = Math.max(0, Math.min(1, progress));
            this.updateTimelinePosition(this.currentProgress * 100);
            this.updateProgressDisplay(this.currentProgress);
            this.updateCurrentTimeDisplay(detail.targetTime);
        }
    }
    
    onFocus() {
        // Show keyboard navigation hints
        if (this.timelineElement) {
            this.timelineElement.title = 'Use arrow keys to navigate, Home/End for start/end';
        }
    }
    
    onBlur() {
        // Clear title
        if (this.timelineElement) {
            this.timelineElement.title = '';
        }
    }
    
    /**
     * Control methods
     */
    setEnabled(enabled) {
        this.isEnabled = enabled;
        
        if (this.timelineElement) {
            this.timelineElement.disabled = !enabled;
            
            if (enabled) {
                this.timelineElement.classList.remove('disabled');
            } else {
                this.timelineElement.classList.add('disabled');
            }
        }
    }
    
    setProgress(progress) {
        this.currentProgress = Math.max(0, Math.min(1, progress));
        this.updateTimelinePosition(this.currentProgress * 100);
        this.updateProgressDisplay(this.currentProgress);
    }
    
    reset() {
        this.setProgress(0);
        this.endDrag();
    }
    
    /**
     * Get current state
     */
    getState() {
        return {
            progress: this.currentProgress,
            isDragging: this.isDragging,
            isEnabled: this.isEnabled,
            timeRange: this.timeRange
        };
    }
    
    /**
     * Destroy timeline scrubber
     */
    destroy() {
        this.endDrag();
        this.timeRange = null;
        this.isEnabled = false;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.TimelineScrubber = TimelineScrubber;
}