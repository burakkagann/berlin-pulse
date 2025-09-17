// Berlin Transport Time Machine - Main Application

class BerlinTransportSimulation {
    constructor() {
        // Core components
        this.apiService = null;
        this.dataService = null;
        this.mapRenderer = null;
        this.vehicleAnimator = null;
        this.simulationController = null;
        this.playbackControls = null;
        this.timelineScrubber = null;
        this.timeController = null;
        
        // Application state
        this.isInitialized = false;
        this.hasError = false;
        this.initializationStartTime = null;
        
        // Performance monitoring
        this.performanceStats = {
            initTime: 0,
            frameRate: 0,
            memoryUsage: 0,
            apiResponseTime: 0
        };
        
        this.initialize();
    }
    
    /**
     * Initialize the application
     */
    async initialize() {
        this.initializationStartTime = performance.now();
        
        try {
            console.log('🚀 Initializing Berlin Transport Time Machine...');
            
            // Show loading screen
            this.showLoadingScreen('Initializing application...');
            
            // Initialize components in order
            await this.initializeCore();
            await this.initializeServices();
            await this.initializeUI();
            await this.initializeControllers();
            
            // Set up global event handlers
            this.setupGlobalEventHandlers();
            
            // Start performance monitoring
            this.startPerformanceMonitoring();
            
            // Calculate initialization time
            this.performanceStats.initTime = performance.now() - this.initializationStartTime;
            
            // Hide loading screen
            this.hideLoadingScreen();
            
            // Mark as initialized
            this.isInitialized = true;
            
            console.log(`✅ Application initialized successfully in ${this.performanceStats.initTime.toFixed(1)}ms`);
            
            // Show welcome message or tutorial if first time
            this.showWelcomeMessage();
            
        } catch (error) {
            this.handleInitializationError(error);
        }
    }
    
    /**
     * Initialize core services
     */
    async initializeCore() {
        this.updateLoadingMessage('Connecting to API...');
        
        // Initialize API service (already created globally)
        this.apiService = window.apiService;
        
        // Initialize data service
        this.dataService = new DataService(this.apiService);
        
        // Test API connection
        await this.apiService.checkConnection();
        
        console.log('✅ API service initialized');
    }
    
    /**
     * Initialize UI services
     */
    async initializeServices() {
        this.updateLoadingMessage('Setting up map...');
        
        // Initialize map renderer
        this.mapRenderer = new MapRenderer('map');
        
        // Initialize vehicle animator
        this.vehicleAnimator = new VehicleAnimator(this.mapRenderer);
        
        console.log('✅ UI services initialized');
    }
    
    /**
     * Initialize UI components
     */
    async initializeUI() {
        this.updateLoadingMessage('Loading controls...');
        
        // Initialize simulation controller (this will load initial data)
        this.simulationController = new SimulationController(
            this.apiService,
            this.mapRenderer,
            this.vehicleAnimator
        );
        
        // Wait for simulation controller to initialize
        await this.waitForSimulationReady();
        
        console.log('✅ UI components initialized');
    }
    
    /**
     * Initialize controllers
     */
    async initializeControllers() {
        this.updateLoadingMessage('Setting up controls...');
        
        // Initialize playback controls
        this.playbackControls = new PlaybackControls(this.simulationController);
        
        console.log('✅ Controllers initialized');
    }
    
    /**
     * Wait for simulation controller to be ready
     */
    waitForSimulationReady() {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Simulation initialization timeout'));
            }, 30000); // 30 second timeout
            
            const checkReady = () => {
                if (this.simulationController && this.simulationController.timeRange) {
                    clearTimeout(timeout);
                    resolve();
                } else {
                    setTimeout(checkReady, 100);
                }
            };
            
            // Listen for initialization event
            window.addEventListener('simulationInitialized', () => {
                clearTimeout(timeout);
                resolve();
            }, { once: true });
            
            checkReady();
        });
    }
    
    /**
     * Set up global event handlers
     */
    setupGlobalEventHandlers() {
        // Error handling
        window.addEventListener('error', (e) => {
            this.handleGlobalError(e.error);
        });
        
        window.addEventListener('unhandledrejection', (e) => {
            this.handleGlobalError(e.reason);
        });
        
        // Connection status changes
        window.addEventListener('connectionStatusChange', (e) => {
            this.handleConnectionChange(e.detail);
        });
        
        // Simulation events
        window.addEventListener('simulationError', (e) => {
            this.handleSimulationError(e.detail);
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleGlobalKeyboard(e);
        });
        
        // Page visibility changes
        document.addEventListener('visibilitychange', () => {
            this.handleVisibilityChange();
        });
        
        // Window resize
        window.addEventListener('resize', () => {
            this.handleWindowResize();
        });
        
        // Before unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }
    
    /**
     * Start performance monitoring
     */
    startPerformanceMonitoring() {
        if (!CONFIG.DEBUG.PERFORMANCE_MONITORING) return;
        
        setInterval(() => {
            this.updatePerformanceStats();
        }, 1000);
    }
    
    /**
     * Update performance statistics
     */
    updatePerformanceStats() {
        // Frame rate from animator
        if (this.vehicleAnimator) {
            const animatorStats = this.vehicleAnimator.getPerformanceStats();
            this.performanceStats.frameRate = animatorStats.actualFrameRate;
        }
        
        // Memory usage
        if (performance.memory) {
            this.performanceStats.memoryUsage = performance.memory.usedJSHeapSize / 1024 / 1024; // MB
        }
        
        // Log performance stats if debug enabled
        if (CONFIG.DEBUG.ENABLED && CONFIG.DEBUG.PERFORMANCE_MONITORING) {
            console.log('Performance Stats:', this.performanceStats);
        }
    }
    
    /**
     * Event handlers
     */
    handleConnectionChange(detail) {
        console.log(`Connection status: ${detail.isOnline ? 'online' : 'offline'}`);
        
        if (!detail.isOnline) {
            this.showNotification('Connection lost. Some features may not work.', 'warning');
        } else {
            this.showNotification('Connection restored.', 'success');
        }
    }
    
    handleSimulationError(detail) {
        console.error('Simulation error:', detail);
        this.showNotification(`Simulation error: ${detail.message}`, 'error');
    }
    
    handleGlobalError(error) {
        console.error('Global error:', error);
        
        if (!this.hasError) {
            this.hasError = true;
            this.showNotification('An unexpected error occurred.', 'error');
        }
    }
    
    handleGlobalKeyboard(event) {
        // Global keyboard shortcuts that don't conflict with controls
        switch (event.key) {
            case CONFIG.KEYBOARD.TOGGLE_HELP:
                event.preventDefault();
                this.toggleKeyboardHelp();
                break;
                
            case CONFIG.KEYBOARD.ESCAPE:
                event.preventDefault();
                this.handleEscape();
                break;
        }
    }
    
    handleVisibilityChange() {
        if (document.hidden) {
            // Page is hidden - pause animation to save resources
            if (this.simulationController && this.simulationController.isPlaying) {
                this.simulationController.pause();
            }
        }
    }
    
    handleWindowResize() {
        // Debounce resize events
        clearTimeout(this.resizeTimeout);
        this.resizeTimeout = setTimeout(() => {
            if (this.mapRenderer) {
                this.mapRenderer.resize();
            }
        }, 250);
    }
    
    handleEscape() {
        // Handle escape key - close modals, stop playback, etc.
        this.hideKeyboardHelp();
        
        if (this.simulationController && this.simulationController.isPlaying) {
            this.simulationController.pause();
        }
    }
    
    /**
     * UI helper methods
     */
    showLoadingScreen(message) {
        const overlay = document.getElementById('loading-overlay');
        const messageElement = document.getElementById('loading-message');
        
        if (overlay) {
            overlay.classList.remove('hidden');
        }
        
        if (messageElement && message) {
            messageElement.textContent = message;
        }
    }
    
    hideLoadingScreen() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }
    
    updateLoadingMessage(message) {
        const messageElement = document.getElementById('loading-message');
        if (messageElement) {
            messageElement.textContent = message;
        }
    }
    
    showNotification(message, type = 'info', duration = 5000) {
        // Enhanced notification system with better visual feedback
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // Update API status indicator
        const statusElement = document.getElementById('api-status');
        if (statusElement) {
            const statusColors = {
                'success': '🟢',
                'warning': '🟡', 
                'error': '🔴',
                'info': '🔵'
            };
            
            const originalStatus = statusElement.textContent;
            statusElement.textContent = statusColors[type] || '⚫';
            statusElement.title = message;
            
            // Reset status after duration
            setTimeout(() => {
                if (statusElement.title === message) {
                    statusElement.textContent = '🟢'; // Default to green when healthy
                    statusElement.title = '';
                }
            }, duration);
        }
        
        // Create temporary toast notification
        this.createToastNotification(message, type, duration);
    }
    
    createToastNotification(message, type, duration) {
        // Create toast notification element
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 16px;
            border-radius: 4px;
            color: white;
            font-size: 14px;
            z-index: 10000;
            max-width: 300px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: opacity 0.3s ease;
            ${type === 'error' ? 'background: #dc2626;' : ''}
            ${type === 'warning' ? 'background: #f59e0b;' : ''}
            ${type === 'success' ? 'background: #10b981;' : ''}
            ${type === 'info' ? 'background: #3b82f6;' : ''}
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after duration
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
    }
    
    showWelcomeMessage() {
        // Show welcome message for first-time users
        const hasVisited = localStorage.getItem('berlin-transport-visited');
        
        if (!hasVisited) {
            localStorage.setItem('berlin-transport-visited', 'true');
            
            setTimeout(() => {
                this.showNotification('Welcome to Berlin Transport Time Machine! Press ? for keyboard shortcuts.', 'info', 10000);
            }, 2000);
        }
    }
    
    toggleKeyboardHelp() {
        const helpElement = document.querySelector('.keyboard-shortcuts');
        if (helpElement) {
            helpElement.classList.toggle('visible');
        } else {
            this.createKeyboardHelp();
        }
    }
    
    hideKeyboardHelp() {
        const helpElement = document.querySelector('.keyboard-shortcuts');
        if (helpElement) {
            helpElement.classList.remove('visible');
        }
    }
    
    createKeyboardHelp() {
        const helpHtml = `
            <div class="keyboard-shortcuts visible">
                <h4>Keyboard Shortcuts</h4>
                <div class="shortcut-item">
                    <span class="shortcut-key">Space</span>
                    <span class="shortcut-desc">Play/Pause</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">←/→</span>
                    <span class="shortcut-desc">Step backward/forward</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">↑/↓</span>
                    <span class="shortcut-desc">Speed up/down</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">Home</span>
                    <span class="shortcut-desc">Reset to start</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">R</span>
                    <span class="shortcut-desc">Toggle routes</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">S</span>
                    <span class="shortcut-desc">Toggle stops</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">Esc</span>
                    <span class="shortcut-desc">Pause/Close</span>
                </div>
                <div class="shortcut-item">
                    <span class="shortcut-key">?</span>
                    <span class="shortcut-desc">Toggle this help</span>
                </div>
            </div>
        `;
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = helpHtml;
        document.body.appendChild(tempDiv.firstElementChild);
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            this.hideKeyboardHelp();
        }, 10000);
    }
    
    /**
     * Error handling
     */
    handleInitializationError(error) {
        console.error('Failed to initialize application:', error);
        
        this.hasError = true;
        this.hideLoadingScreen();
        
        // Categorize error for better user feedback
        let title = 'Initialization Failed';
        let message = 'Failed to initialize the application.';
        let suggestion = 'Please try refreshing the page.';
        
        if (error.message.includes('timeout') || error.message.includes('Network')) {
            title = 'Connection Error';
            message = 'Unable to connect to the simulation server.';
            suggestion = 'Please check your internet connection and try again.';
        } else if (error.message.includes('404') || error.message.includes('Not Found')) {
            title = 'Service Unavailable';
            message = 'The simulation service appears to be offline.';
            suggestion = 'Please try again later or contact support.';
        } else if (error.message.includes('data') || error.message.includes('API')) {
            title = 'Data Loading Error';
            message = 'Unable to load simulation data.';
            suggestion = 'The data service may be temporarily unavailable. Please try again.';
        }
        
        const fullMessage = `${message}\n\n${suggestion}\n\nTechnical details: ${error.message}`;
        
        // Show error modal
        this.showErrorModal(title, fullMessage, () => window.location.reload());
    }
    
    showErrorModal(title, message, retryCallback = null) {
        const modal = document.getElementById('error-modal');
        const titleElement = modal?.querySelector('h3');
        const messageElement = document.getElementById('error-message');
        const retryButton = document.getElementById('error-retry');
        
        if (titleElement) titleElement.textContent = title;
        if (messageElement) messageElement.textContent = message;
        
        if (modal) {
            modal.classList.remove('hidden');
        }
        
        // Set up retry button
        if (retryButton && retryCallback) {
            retryButton.onclick = retryCallback;
            retryButton.style.display = 'block';
        } else if (retryButton) {
            retryButton.style.display = 'none';
        }
        
        // Set up close button
        const closeButton = document.getElementById('error-close');
        const dismissButton = document.getElementById('error-dismiss');
        
        const closeModal = () => {
            if (modal) modal.classList.add('hidden');
        };
        
        if (closeButton) closeButton.onclick = closeModal;
        if (dismissButton) dismissButton.onclick = closeModal;
    }
    
    /**
     * Application state
     */
    getApplicationState() {
        return {
            isInitialized: this.isInitialized,
            hasError: this.hasError,
            performanceStats: this.performanceStats,
            simulationState: this.simulationController?.getState(),
            animatorState: this.vehicleAnimator?.getState(),
            mapStats: this.mapRenderer?.getPerformanceStats()
        };
    }
    
    /**
     * Cleanup
     */
    cleanup() {
        console.log('Cleaning up application...');
        
        // Stop any running animations
        if (this.simulationController) {
            this.simulationController.stop();
        }
        
        // Clear any timers
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        
        // Clean up components
        if (this.vehicleAnimator) {
            this.vehicleAnimator.destroy();
        }
        
        if (this.mapRenderer) {
            this.mapRenderer.destroy();
        }
        
        if (this.apiService) {
            this.apiService.clearCache();
        }
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing Berlin Transport Time Machine...');
    
    // Create global application instance
    window.berlinTransportApp = new BerlinTransportSimulation();
});

// Handle module loading errors
window.addEventListener('error', (e) => {
    if (e.filename && e.filename.includes('.js')) {
        console.error('Script loading error:', e.filename, e.message);
    }
});