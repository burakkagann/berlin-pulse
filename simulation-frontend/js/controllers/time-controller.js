// Berlin Transport Time Machine - Time Controller

class TimeController {
    constructor(simulationController) {
        this.simulationController = simulationController;
        
        // Time state
        this.currentTime = null;
        this.timeRange = null;
        this.playbackSpeed = 1;
        this.isPlaying = false;
        
        // Time navigation
        this.bookmarks = new Map();
        this.history = [];
        this.historyIndex = -1;
        this.maxHistorySize = 50;
        
        // Auto-advance settings
        this.autoAdvanceEnabled = false;
        this.autoAdvanceInterval = null;
        this.autoAdvanceStep = 5; // minutes
        
        // Time zone handling
        this.timezone = 'Europe/Berlin';
        this.useLocalTime = false;
        
        this.initialize();
    }
    
    /**
     * Initialize time controller
     */
    initialize() {
        this.setupEventListeners();
        this.loadBookmarks();
        
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Time controller initialized');
        }
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Simulation events
        window.addEventListener('simulationInitialized', (e) => {
            this.onSimulationInitialized(e.detail);
        });
        
        window.addEventListener('simulationJumped', (e) => {
            this.onTimeChanged(e.detail.targetTime);
        });
        
        window.addEventListener('animationFrameUpdate', (e) => {
            this.onTimeChanged(e.detail.timestamp);
        });
        
        window.addEventListener('simulationPlayStarted', () => {
            this.isPlaying = true;
        });
        
        window.addEventListener('simulationPaused', () => {
            this.isPlaying = false;
        });
        
        window.addEventListener('simulationStopped', () => {
            this.isPlaying = false;
            this.stopAutoAdvance();
        });
    }
    
    /**
     * Jump to specific time
     */
    jumpToTime(targetTime) {
        if (!this.isValidTime(targetTime)) {
            console.warn('Invalid target time:', targetTime);
            return false;
        }
        
        // Add to history
        this.addToHistory(this.currentTime);
        
        // Update current time
        this.currentTime = new Date(targetTime);
        
        // Notify simulation controller
        if (this.simulationController) {
            this.simulationController.jumpToTime(this.currentTime);
        }
        
        return true;
    }
    
    /**
     * Jump to relative time
     */
    jumpRelative(minutes) {
        if (!this.currentTime) return false;
        
        const targetTime = new Date(this.currentTime.getTime() + (minutes * 60 * 1000));
        return this.jumpToTime(targetTime);
    }
    
    /**
     * Jump to start of data
     */
    jumpToStart() {
        if (this.timeRange) {
            return this.jumpToTime(new Date(this.timeRange.start_time));
        }
        return false;
    }
    
    /**
     * Jump to end of data
     */
    jumpToEnd() {
        if (this.timeRange) {
            return this.jumpToTime(new Date(this.timeRange.end_time));
        }
        return false;
    }
    
    /**
     * Jump to progress percentage (0-100)
     */
    jumpToProgress(percentage) {
        if (!this.timeRange) return false;
        
        const progress = Math.max(0, Math.min(100, percentage)) / 100;
        const startTime = new Date(this.timeRange.start_time);
        const endTime = new Date(this.timeRange.end_time);
        const duration = endTime.getTime() - startTime.getTime();
        const targetTime = new Date(startTime.getTime() + (duration * progress));
        
        return this.jumpToTime(targetTime);
    }
    
    /**
     * Step forward by specified time
     */
    stepForward(minutes = 5) {
        return this.jumpRelative(minutes);
    }
    
    /**
     * Step backward by specified time
     */
    stepBackward(minutes = 5) {
        return this.jumpRelative(-minutes);
    }
    
    /**
     * Jump to specific hour of current day
     */
    jumpToHour(hour) {
        if (!this.currentTime || hour < 0 || hour > 23) return false;
        
        const targetTime = new Date(this.currentTime);
        targetTime.setHours(hour, 0, 0, 0);
        
        return this.jumpToTime(targetTime);
    }
    
    /**
     * Jump to rush hour periods
     */
    jumpToRushHour(period = 'morning') {
        if (!this.currentTime) return false;
        
        const targetTime = new Date(this.currentTime);
        
        switch (period) {
            case 'morning':
                targetTime.setHours(8, 0, 0, 0); // 8 AM
                break;
            case 'evening':
                targetTime.setHours(18, 0, 0, 0); // 6 PM
                break;
            case 'lunch':
                targetTime.setHours(12, 0, 0, 0); // 12 PM
                break;
            default:
                return false;
        }
        
        return this.jumpToTime(targetTime);
    }
    
    /**
     * Bookmark management
     */
    addBookmark(name, time = null) {
        const bookmarkTime = time || this.currentTime;
        if (!bookmarkTime) return false;
        
        this.bookmarks.set(name, {
            time: new Date(bookmarkTime),
            created: new Date(),
            description: this.generateTimeDescription(bookmarkTime)
        });
        
        this.saveBookmarks();
        
        // Dispatch bookmark added event
        const event = new CustomEvent('bookmarkAdded', {
            detail: { name, time: bookmarkTime }
        });
        window.dispatchEvent(event);
        
        return true;
    }
    
    /**
     * Jump to bookmark
     */
    jumpToBookmark(name) {
        const bookmark = this.bookmarks.get(name);
        if (!bookmark) return false;
        
        return this.jumpToTime(bookmark.time);
    }
    
    /**
     * Remove bookmark
     */
    removeBookmark(name) {
        const removed = this.bookmarks.delete(name);
        if (removed) {
            this.saveBookmarks();
        }
        return removed;
    }
    
    /**
     * Get all bookmarks
     */
    getBookmarks() {
        return Array.from(this.bookmarks.entries()).map(([name, bookmark]) => ({
            name,
            ...bookmark
        }));
    }
    
    /**
     * History navigation
     */
    addToHistory(time) {
        if (!time) return;
        
        // Remove future history if we're in the middle
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Add new entry
        this.history.push(new Date(time));
        this.historyIndex = this.history.length - 1;
        
        // Limit history size
        if (this.history.length > this.maxHistorySize) {
            this.history.shift();
            this.historyIndex--;
        }
    }
    
    /**
     * Go back in history
     */
    goBack() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            const targetTime = this.history[this.historyIndex];
            this.currentTime = new Date(targetTime);
            
            if (this.simulationController) {
                this.simulationController.jumpToTime(this.currentTime);
            }
            
            return true;
        }
        return false;
    }
    
    /**
     * Go forward in history
     */
    goForward() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            const targetTime = this.history[this.historyIndex];
            this.currentTime = new Date(targetTime);
            
            if (this.simulationController) {
                this.simulationController.jumpToTime(this.currentTime);
            }
            
            return true;
        }
        return false;
    }
    
    /**
     * Auto-advance functionality
     */
    startAutoAdvance(stepMinutes = 5, intervalMs = 2000) {
        this.stopAutoAdvance();
        
        this.autoAdvanceEnabled = true;
        this.autoAdvanceStep = stepMinutes;
        
        this.autoAdvanceInterval = setInterval(() => {
            if (this.autoAdvanceEnabled && !this.isPlaying) {
                if (!this.stepForward(this.autoAdvanceStep)) {
                    // Reached end, stop auto-advance
                    this.stopAutoAdvance();
                }
            }
        }, intervalMs);
    }
    
    /**
     * Stop auto-advance
     */
    stopAutoAdvance() {
        this.autoAdvanceEnabled = false;
        
        if (this.autoAdvanceInterval) {
            clearInterval(this.autoAdvanceInterval);
            this.autoAdvanceInterval = null;
        }
    }
    
    /**
     * Time formatting and display
     */
    formatTime(time, format = 'HH:mm:ss') {
        if (!time) return '--:--:--';
        
        const momentTime = this.useLocalTime 
            ? moment(time) 
            : moment(time).tz(this.timezone);
            
        return momentTime.format(format);
    }
    
    /**
     * Get relative time description
     */
    getRelativeTimeDescription(time) {
        if (!time || !this.currentTime) return '';
        
        const diff = time.getTime() - this.currentTime.getTime();
        const minutes = Math.round(diff / (60 * 1000));
        
        if (minutes === 0) return 'now';
        if (minutes > 0) return `in ${minutes} minutes`;
        return `${Math.abs(minutes)} minutes ago`;
    }
    
    /**
     * Generate time description
     */
    generateTimeDescription(time) {
        if (!time) return '';
        
        const hour = time.getHours();
        const minute = time.getMinutes();
        
        let period = 'night';
        if (hour >= 6 && hour < 10) period = 'morning rush';
        else if (hour >= 10 && hour < 16) period = 'day';
        else if (hour >= 16 && hour < 20) period = 'evening rush';
        else if (hour >= 20 && hour < 22) period = 'evening';
        
        return `${this.formatTime(time, 'HH:mm')} (${period})`;
    }
    
    /**
     * Time validation
     */
    isValidTime(time) {
        if (!time || !this.timeRange) return false;
        
        const startTime = new Date(this.timeRange.start_time);
        const endTime = new Date(this.timeRange.end_time);
        const targetTime = new Date(time);
        
        return targetTime >= startTime && targetTime <= endTime;
    }
    
    /**
     * Get current progress (0-1)
     */
    getCurrentProgress() {
        if (!this.currentTime || !this.timeRange) return 0;
        
        const startTime = new Date(this.timeRange.start_time);
        const endTime = new Date(this.timeRange.end_time);
        const current = this.currentTime;
        
        const total = endTime.getTime() - startTime.getTime();
        const elapsed = current.getTime() - startTime.getTime();
        
        return Math.max(0, Math.min(1, elapsed / total));
    }
    
    /**
     * Event handlers
     */
    onSimulationInitialized(detail) {
        this.timeRange = detail.timeRange;
        
        if (this.timeRange) {
            this.currentTime = new Date(this.timeRange.start_time);
        }
    }
    
    onTimeChanged(timestamp) {
        if (timestamp) {
            this.currentTime = new Date(timestamp);
        }
    }
    
    /**
     * Persistence
     */
    saveBookmarks() {
        try {
            const bookmarksData = {};
            for (const [name, bookmark] of this.bookmarks.entries()) {
                bookmarksData[name] = {
                    time: bookmark.time.toISOString(),
                    created: bookmark.created.toISOString(),
                    description: bookmark.description
                };
            }
            
            localStorage.setItem('berlin-transport-bookmarks', JSON.stringify(bookmarksData));
        } catch (error) {
            console.warn('Failed to save bookmarks:', error);
        }
    }
    
    /**
     * Load bookmarks
     */
    loadBookmarks() {
        try {
            const stored = localStorage.getItem('berlin-transport-bookmarks');
            if (stored) {
                const bookmarksData = JSON.parse(stored);
                
                for (const [name, bookmark] of Object.entries(bookmarksData)) {
                    this.bookmarks.set(name, {
                        time: new Date(bookmark.time),
                        created: new Date(bookmark.created),
                        description: bookmark.description
                    });
                }
            }
        } catch (error) {
            console.warn('Failed to load bookmarks:', error);
        }
    }
    
    /**
     * Get controller state
     */
    getState() {
        return {
            currentTime: this.currentTime,
            timeRange: this.timeRange,
            isPlaying: this.isPlaying,
            progress: this.getCurrentProgress(),
            autoAdvanceEnabled: this.autoAdvanceEnabled,
            bookmarksCount: this.bookmarks.size,
            historyPosition: this.historyIndex,
            historySize: this.history.length
        };
    }
    
    /**
     * Destroy time controller
     */
    destroy() {
        this.stopAutoAdvance();
        this.saveBookmarks();
        this.bookmarks.clear();
        this.history = [];
        this.historyIndex = -1;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.TimeController = TimeController;
}