// Berlin Transport Time Machine - Playback Controls

class PlaybackControls {
    constructor(simulationController) {
        this.simulationController = simulationController;
        
        // Control elements
        this.playButton = null;
        this.resetButton = null;
        this.stepButton = null;
        this.speedButtons = [];
        this.timelineScrubber = null;
        this.jumpToTimeInput = null;
        this.jumpButton = null;
        
        // Transport filter checkboxes
        this.transportFilters = new Map();
        
        // State
        this.isInitialized = false;
        this.isDraggingTimeline = false;
        this.lastUpdateTime = 0;
        
        this.initializeControls();
    }
    
    /**
     * Initialize playback controls
     */
    initializeControls() {
        try {
            // Get control elements
            this.getControlElements();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Initialize state
            this.updateControlStates();
            
            // Set up transport filters
            this.setupTransportFilters();
            
            this.isInitialized = true;
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log('Playback controls initialized');
            }
            
        } catch (error) {
            console.error('Failed to initialize playback controls:', error);
        }
    }
    
    /**
     * Get control elements from DOM
     */
    getControlElements() {
        this.playButton = document.getElementById('play-button');
        this.resetButton = document.getElementById('reset-button');
        this.stepButton = document.getElementById('step-button');
        this.timelineScrubber = document.getElementById('timeline-scrubber');
        this.jumpToTimeInput = document.getElementById('jump-to-time');
        this.jumpButton = document.getElementById('jump-button');
        
        // Speed control buttons
        this.speedButtons = Array.from(document.querySelectorAll('.speed-control'));
        
        // Validate required elements
        if (!this.playButton || !this.timelineScrubber) {
            throw new Error('Required control elements not found');
        }
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Play/Pause button
        if (this.playButton) {
            this.playButton.addEventListener('click', () => {
                this.togglePlayback();
            });
        }
        
        // Reset button
        if (this.resetButton) {
            this.resetButton.addEventListener('click', () => {
                this.resetSimulation();
            });
        }
        
        // Step forward button
        if (this.stepButton) {
            this.stepButton.addEventListener('click', () => {
                this.stepForward();
            });
        }
        
        // Speed controls
        this.speedButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const speed = parseFloat(e.target.dataset.speed);
                this.setSpeed(speed);
            });
        });
        
        // Timeline scrubber
        if (this.timelineScrubber) {
            this.setupTimelineControls();
        }
        
        // Jump to time controls
        if (this.jumpButton && this.jumpToTimeInput) {
            this.setupJumpControls();
        }
        
        // Simulation events
        this.setupSimulationEventListeners();
    }
    
    /**
     * Set up timeline controls
     */
    setupTimelineControls() {
        // Mouse/touch events for timeline scrubbing
        this.timelineScrubber.addEventListener('mousedown', (e) => {
            this.isDraggingTimeline = true;
            this.handleTimelineScrub(e);
        });
        
        this.timelineScrubber.addEventListener('touchstart', (e) => {
            this.isDraggingTimeline = true;
            this.handleTimelineScrub(e.touches[0]);
        }, { passive: false });
        
        // Global mouse/touch move and up events
        document.addEventListener('mousemove', (e) => {
            if (this.isDraggingTimeline) {
                this.handleTimelineScrub(e);
            }
        });
        
        document.addEventListener('touchmove', (e) => {
            if (this.isDraggingTimeline) {
                e.preventDefault();
                this.handleTimelineScrub(e.touches[0]);
            }
        }, { passive: false });
        
        document.addEventListener('mouseup', () => {
            this.isDraggingTimeline = false;
        });
        
        document.addEventListener('touchend', () => {
            this.isDraggingTimeline = false;
        });
        
        // Input event for value changes
        this.timelineScrubber.addEventListener('input', (e) => {
            if (!this.isDraggingTimeline) {
                this.handleTimelineChange(parseFloat(e.target.value));
            }
        });
        
        // Keyboard events for fine control
        this.timelineScrubber.addEventListener('keydown', (e) => {
            this.handleTimelineKeyboard(e);
        });
    }
    
    /**
     * Set up jump to time controls
     */
    setupJumpControls() {
        this.jumpButton.addEventListener('click', () => {
            this.jumpToTime();
        });
        
        this.jumpToTimeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.jumpToTime();
            }
        });
        
        // Set min/max for datetime input based on available data
        if (this.simulationController.timeRange) {
            const startTime = new Date(this.simulationController.timeRange.start_time);
            const endTime = new Date(this.simulationController.timeRange.end_time);
            
            // Convert to local datetime-local format
            this.jumpToTimeInput.min = this.formatDateTimeLocal(startTime);
            this.jumpToTimeInput.max = this.formatDateTimeLocal(endTime);
            
            // Set current value
            if (this.simulationController.currentTime) {
                this.jumpToTimeInput.value = this.formatDateTimeLocal(this.simulationController.currentTime);
            }
        }
    }
    
    /**
     * Set up transport filter controls
     */
    setupTransportFilters() {
        const filterCheckboxes = document.querySelectorAll('.transport-filters input[type=\"checkbox\"]');
        
        filterCheckboxes.forEach(checkbox => {
            const transportType = checkbox.dataset.type;
            this.transportFilters.set(transportType, checkbox);
            
            // Set initial state
            checkbox.checked = CONFIG.TRANSPORT_TYPES[transportType]?.enabled || false;
            
            // Add event listener
            checkbox.addEventListener('change', () => {
                this.updateTransportFilters();
            });
        });
    }
    
    /**
     * Set up simulation event listeners
     */
    setupSimulationEventListeners() {
        // Animation state changes
        window.addEventListener('simulationPlayStarted', () => {
            this.updatePlayButtonState(true);
        });
        
        window.addEventListener('simulationPaused', () => {
            this.updatePlayButtonState(false);
        });
        
        window.addEventListener('simulationResumed', () => {
            this.updatePlayButtonState(true);
        });
        
        window.addEventListener('simulationStopped', () => {
            this.updatePlayButtonState(false);
        });
        
        window.addEventListener('simulationReset', () => {
            this.updatePlayButtonState(false);
            this.updateTimelinePosition(0);
        });
        
        // Animation progress updates
        window.addEventListener('animationFrameUpdate', (e) => {
            this.updateTimelinePosition(e.detail.progress);
            this.updateTimeDisplay(e.detail.timestamp);
        });
        
        // Speed changes
        window.addEventListener('simulationSpeedChanged', (e) => {
            this.updateSpeedDisplay(e.detail.speed);
        });
        
        // Time range loaded
        window.addEventListener('simulationInitialized', (e) => {
            this.updateTimeRangeDisplay(e.detail.timeRange);
        });
    }
    
    /**
     * Control actions
     */
    togglePlayback() {
        if (this.simulationController.isPlaying) {
            this.simulationController.pause();
        } else {
            this.simulationController.play();
        }
    }
    
    resetSimulation() {
        this.simulationController.reset();
    }
    
    stepForward() {
        this.simulationController.vehicleAnimator.stepForward();
    }
    
    setSpeed(speed) {
        this.simulationController.setSpeed(speed);
    }
    
    jumpToTime() {
        if (!this.jumpToTimeInput.value) return;
        
        try {
            const targetTime = new Date(this.jumpToTimeInput.value);
            this.simulationController.jumpToTime(targetTime);
        } catch (error) {
            console.error('Invalid time format:', error);
            this.showError('Invalid time format');
        }
    }
    
    /**
     * Timeline handling
     */
    handleTimelineScrub(event) {
        const rect = this.timelineScrubber.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const progress = Math.max(0, Math.min(1, x / rect.width));
        
        this.timelineScrubber.value = progress * 100;
        this.handleTimelineChange(progress * 100);
    }
    
    handleTimelineChange(value) {
        const progress = value / 100;
        
        // Throttle updates to prevent too frequent scrubbing
        const now = Date.now();
        if (now - this.lastUpdateTime < CONFIG.PERFORMANCE.UPDATE_THROTTLE) {
            return;
        }
        this.lastUpdateTime = now;
        
        // Calculate target time
        if (this.simulationController.timeRange) {
            const startTime = new Date(this.simulationController.timeRange.start_time);
            const endTime = new Date(this.simulationController.timeRange.end_time);
            const duration = endTime.getTime() - startTime.getTime();
            const targetTime = new Date(startTime.getTime() + (duration * progress));
            
            this.simulationController.jumpToTime(targetTime);
        }
    }
    
    handleTimelineKeyboard(event) {
        const step = 0.1; // 0.1% steps
        let newValue = parseFloat(this.timelineScrubber.value);
        
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
            default:
                return;
        }
        
        this.timelineScrubber.value = newValue;
        this.handleTimelineChange(newValue);
    }
    
    /**
     * Transport filter handling
     */
    updateTransportFilters() {
        const enabledTypes = [];
        
        this.transportFilters.forEach((checkbox, transportType) => {
            if (checkbox.checked) {
                enabledTypes.push(transportType);
            }
        });
        
        this.simulationController.updateTransportTypes(enabledTypes);
    }
    
    /**
     * UI updates
     */
    updatePlayButtonState(isPlaying) {
        if (!this.playButton) return;
        
        const icon = this.playButton.querySelector('.icon');
        if (icon) {
            icon.textContent = isPlaying ? '⏸️' : '▶️';
        }
        
        this.playButton.title = isPlaying ? 'Pause' : 'Play';
        this.playButton.setAttribute('data-state', isPlaying ? 'playing' : 'paused');
        
        // Update button styling
        if (isPlaying) {
            this.playButton.classList.add('playing');
        } else {
            this.playButton.classList.remove('playing');
        }
    }
    
    updateSpeedDisplay(speed) {
        this.speedButtons.forEach(button => {
            const buttonSpeed = parseFloat(button.dataset.speed);
            
            if (buttonSpeed === speed) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }
    
    updateTimelinePosition(progress) {
        if (this.isDraggingTimeline) return; // Don't update while user is dragging
        
        if (this.timelineScrubber) {
            this.timelineScrubber.value = progress * 100;
            this.timelineScrubber.style.setProperty('--progress', `${progress * 100}%`);
        }
    }
    
    updateTimeDisplay(timestamp) {
        if (this.jumpToTimeInput && timestamp) {
            this.jumpToTimeInput.value = this.formatDateTimeLocal(new Date(timestamp));
        }
    }
    
    updateTimeRangeDisplay(timeRange) {
        const startTimeElement = document.getElementById('start-time');
        const endTimeElement = document.getElementById('end-time');
        
        if (startTimeElement && timeRange) {
            startTimeElement.textContent = moment(timeRange.start_time).format('HH:mm');
        }
        
        if (endTimeElement && timeRange) {
            endTimeElement.textContent = moment(timeRange.end_time).format('HH:mm');
        }
        
        // Update jump to time input bounds
        if (this.jumpToTimeInput && timeRange) {
            this.jumpToTimeInput.min = this.formatDateTimeLocal(new Date(timeRange.start_time));
            this.jumpToTimeInput.max = this.formatDateTimeLocal(new Date(timeRange.end_time));
        }
    }
    
    updateControlStates() {
        // Enable/disable controls based on simulation state
        const state = this.simulationController.getState();
        
        // Disable controls while loading
        this.setControlsEnabled(!state.isLoading);
        
        // Update play button state
        this.updatePlayButtonState(state.isPlaying);
        
        // Update speed display
        this.updateSpeedDisplay(state.playbackSpeed);
    }
    
    setControlsEnabled(enabled) {
        const controls = [
            this.playButton,
            this.resetButton,
            this.stepButton,
            this.timelineScrubber,
            this.jumpButton,
            ...this.speedButtons
        ].filter(Boolean);
        
        controls.forEach(control => {
            control.disabled = !enabled;
            
            if (enabled) {
                control.classList.remove('control-loading');
            } else {
                control.classList.add('control-loading');
            }
        });
    }
    
    /**
     * Utility methods
     */
    formatDateTimeLocal(date) {
        // Format date for datetime-local input
        const pad = (num) => num.toString().padStart(2, '0');
        
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }
    
    showError(message, duration = 3000) {
        // Simple error display - could be enhanced with toast notifications
        console.error(message);
        
        // You could implement a more sophisticated notification system here
        alert(message);
    }
    
    /**
     * Keyboard shortcuts help
     */
    showKeyboardShortcuts() {
        const shortcuts = document.querySelector('.keyboard-shortcuts');
        if (shortcuts) {
            shortcuts.classList.add('visible');
            
            // Hide after 5 seconds
            setTimeout(() => {
                shortcuts.classList.remove('visible');
            }, 5000);
        }
    }
    
    hideKeyboardShortcuts() {
        const shortcuts = document.querySelector('.keyboard-shortcuts');
        if (shortcuts) {
            shortcuts.classList.remove('visible');
        }
    }
    
    /**
     * Section collapse/expand functionality
     */
    setupSectionCollapse() {
        const sectionHeaders = document.querySelectorAll('.control-panel h3');
        
        sectionHeaders.forEach(header => {
            header.addEventListener('click', () => {
                const section = header.parentElement;
                section.classList.toggle('collapsed');
                
                // Save state to localStorage
                const sectionId = section.className.split(' ')[0]; // Get first class name
                localStorage.setItem(`section-${sectionId}-collapsed`, section.classList.contains('collapsed'));
            });
            
            // Restore state from localStorage
            const section = header.parentElement;
            const sectionId = section.className.split(' ')[0];
            const isCollapsed = localStorage.getItem(`section-${sectionId}-collapsed`) === 'true';
            
            if (isCollapsed) {
                section.classList.add('collapsed');
            }
        });
    }
    
    /**
     * Get control state
     */
    getState() {
        return {
            isInitialized: this.isInitialized,
            isDraggingTimeline: this.isDraggingTimeline,
            enabledTransportTypes: Array.from(this.transportFilters.entries())
                .filter(([_, checkbox]) => checkbox.checked)
                .map(([type, _]) => type)
        };
    }
    
    /**
     * Destroy controls
     */
    destroy() {
        // Remove event listeners and clean up
        this.transportFilters.clear();
        this.isInitialized = false;
    }
}