// Berlin Transport Time Machine - Map Renderer

class MapRenderer {
    constructor(containerId) {
        this.containerId = containerId;
        this.map = null;
        this.baseLayer = null;
        
        // Layer groups
        this.routeLayers = new Map();
        this.vehicleMarkers = new Map();
        this.stopMarkers = new Map();
        
        // Layer group containers
        this.routeLayerGroup = null;
        this.vehicleLayerGroup = null;
        this.stopLayerGroup = null;
        
        // State
        this.isInitialized = false;
        this.showRoutes = true;
        this.showStops = true;
        this.followVehicle = null;
        
        // Performance tracking
        this.lastUpdateTime = 0;
        this.renderCount = 0;
        
        this.initializeMap();
    }
    
    /**
     * Initialize Leaflet map
     */
    initializeMap() {
        try {
            // Create map instance
            this.map = L.map(this.containerId, {
                center: CONFIG.MAP.CENTER,
                zoom: CONFIG.MAP.ZOOM,
                minZoom: CONFIG.MAP.MIN_ZOOM,
                maxZoom: CONFIG.MAP.MAX_ZOOM,
                zoomControl: true,
                attributionControl: true,
                preferCanvas: true, // Better performance for many markers
                maxBounds: [
                    [CONFIG.MAP.BOUNDS.MIN_LAT, CONFIG.MAP.BOUNDS.MIN_LNG],
                    [CONFIG.MAP.BOUNDS.MAX_LAT, CONFIG.MAP.BOUNDS.MAX_LNG]
                ],
                maxBoundsViscosity: 0.1
            });
            
            // Add base tile layer
            this.baseLayer = L.tileLayer(CONFIG.MAP.TILE_LAYER, {
                attribution: CONFIG.MAP.ATTRIBUTION,
                maxZoom: CONFIG.MAP.MAX_ZOOM,
                crossOrigin: true
            }).addTo(this.map);
            
            // Create layer groups
            this.routeLayerGroup = L.layerGroup().addTo(this.map);
            this.vehicleLayerGroup = L.layerGroup().addTo(this.map);
            this.stopLayerGroup = L.layerGroup().addTo(this.map);
            
            // Set up event listeners
            this.setupEventListeners();
            
            this.isInitialized = true;
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log('Map renderer initialized successfully');
            }
            
        } catch (error) {
            console.error('Failed to initialize map:', error);
            throw error;
        }
    }
    
    /**
     * Set up map event listeners
     */
    setupEventListeners() {
        // Map events
        this.map.on('zoomend', () => {
            this.onZoomChange();
        });
        
        this.map.on('moveend', () => {
            this.onViewChange();
        });
        
        this.map.on('click', (e) => {
            this.onMapClick(e);
        });
        
        // Window resize
        window.addEventListener('resize', () => {
            if (this.map) {
                this.map.invalidateSize();
            }
        });
    }
    
    /**
     * Add route geometry to map
     */
    addRouteGeometry(routeId, geoJsonData, routeInfo) {
        try {
            if (!this.isInitialized) {
                throw new Error('Map not initialized');
            }
            
            const transportType = routeInfo?.transport_type || 'unknown';
            const color = CONFIG.TRANSPORT_TYPES[transportType]?.color || '#666666';
            
            const routeStyle = {
                color: color,
                weight: 3,
                opacity: 0.7,
                className: `route-line ${transportType}`
            };
            
            const layer = L.geoJSON(geoJsonData, {
                style: routeStyle,
                onEachFeature: (feature, layer) => {
                    // Add popup with route information
                    if (routeInfo) {
                        const popupContent = this.createRoutePopup(routeInfo);
                        layer.bindPopup(popupContent);
                    }
                    
                    // Add hover effects
                    layer.on('mouseover', function() {
                        this.setStyle({ weight: 5, opacity: 1 });
                    });
                    
                    layer.on('mouseout', function() {
                        this.setStyle(routeStyle);
                    });
                },
                pointToLayer: (feature, latlng) => {
                    // Handle station points if present in geometry
                    if (feature.properties && feature.properties.type === 'station') {
                        return this.createStopMarker(latlng, feature.properties);
                    }
                }
            });
            
            // Store route layer
            this.routeLayers.set(routeId, layer);
            
            // Add to map if routes are visible
            if (this.showRoutes) {
                this.routeLayerGroup.addLayer(layer);
            }
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log(`Added route geometry for ${routeId}`);
            }
            
        } catch (error) {
            console.error(`Failed to add route geometry for ${routeId}:`, error);
        }
    }
    
    /**
     * Update vehicle positions on map
     */
    updateVehiclePositions(vehicles) {
        try {
            const startTime = performance.now();
            
            // Clear existing markers
            this.clearVehicleMarkers();
            
            // Filter vehicles within viewport (for performance)
            const bounds = this.map.getBounds();
            const visibleVehicles = vehicles.filter(vehicle => {
                return bounds.contains([vehicle.latitude, vehicle.longitude]);
            });
            
            // Limit number of vehicles for performance
            const vehiclesToShow = visibleVehicles.slice(0, CONFIG.PERFORMANCE.MAX_VEHICLES_ON_MAP);
            
            // Create markers for vehicles
            vehiclesToShow.forEach(vehicle => {
                const marker = this.createVehicleMarker(vehicle);
                if (marker) {
                    this.vehicleMarkers.set(vehicle.vehicle_id, marker);
                    this.vehicleLayerGroup.addLayer(marker);
                }
            });
            
            // Update performance stats
            const renderTime = performance.now() - startTime;
            this.lastUpdateTime = renderTime;
            this.renderCount++;
            
            // Follow vehicle if enabled
            if (this.followVehicle && this.vehicleMarkers.has(this.followVehicle)) {
                const marker = this.vehicleMarkers.get(this.followVehicle);
                this.map.panTo(marker.getLatLng());
            }
            
            // Dispatch update event
            const event = new CustomEvent('vehiclePositionsUpdated', {
                detail: {
                    vehicleCount: vehiclesToShow.length,
                    renderTime: renderTime,
                    totalVehicles: vehicles.length
                }
            });
            window.dispatchEvent(event);
            
            if (CONFIG.DEBUG.PERFORMANCE_MONITORING) {
                console.log(`Rendered ${vehiclesToShow.length} vehicles in ${renderTime.toFixed(1)}ms`);
            }
            
        } catch (error) {
            console.error('Failed to update vehicle positions:', error);
        }
    }
    
    /**
     * Create vehicle marker
     */
    createVehicleMarker(vehicle) {
        try {
            const transportType = vehicle.transport_type;
            const config = CONFIG.TRANSPORT_TYPES[transportType];
            
            if (!config || !config.enabled) {
                return null;
            }
            
            const icon = L.divIcon({
                className: `vehicle-marker ${transportType} ${vehicle.status}`,
                html: '',
                iconSize: [CONFIG.MARKERS.VEHICLE.SIZE, CONFIG.MARKERS.VEHICLE.SIZE],
                iconAnchor: [CONFIG.MARKERS.VEHICLE.SIZE / 2, CONFIG.MARKERS.VEHICLE.SIZE / 2]
            });
            
            const marker = L.marker([vehicle.latitude, vehicle.longitude], {
                icon: icon,
                title: `${vehicle.line_name || 'Unknown'} - ${vehicle.direction || 'Unknown direction'}`
            });
            
            // Add popup with vehicle details
            const popupContent = this.createVehiclePopup(vehicle);
            marker.bindPopup(popupContent);
            
            // Add hover effects
            marker.on('mouseover', () => {
                this.showVehicleInfo(vehicle);
            });
            
            marker.on('mouseout', () => {
                this.hideVehicleInfo();
            });
            
            // Add click handler
            marker.on('click', () => {
                this.onVehicleClick(vehicle);
            });
            
            return marker;
            
        } catch (error) {
            console.error('Failed to create vehicle marker:', error);
            return null;
        }
    }
    
    /**
     * Create stop marker
     */
    createStopMarker(latlng, stopData) {
        const isTracked = stopData.is_tracked || false;
        const size = isTracked ? CONFIG.MARKERS.STOP.MAJOR_SIZE : CONFIG.MARKERS.STOP.SIZE;
        
        const icon = L.divIcon({
            className: `stop-marker ${isTracked ? 'major' : 'minor'}`,
            html: '',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2]
        });
        
        const marker = L.marker(latlng, { icon: icon });
        
        // Add popup with stop information
        const popupContent = this.createStopPopup(stopData);
        marker.bindPopup(popupContent);
        
        return marker;
    }
    
    /**
     * Add stops to map
     */
    addStops(stops) {
        try {
            stops.forEach(stop => {
                const marker = this.createStopMarker(
                    [stop.latitude, stop.longitude],
                    stop
                );
                
                this.stopMarkers.set(stop.stop_id, marker);
                
                if (this.showStops) {
                    this.stopLayerGroup.addLayer(marker);
                }
            });
            
            if (CONFIG.DEBUG.ENABLED) {
                console.log(`Added ${stops.length} stops to map`);
            }
            
        } catch (error) {
            console.error('Failed to add stops:', error);
        }
    }
    
    /**
     * Create popup content for vehicle
     */
    createVehiclePopup(vehicle) {
        const delayText = vehicle.delay_minutes > 0 
            ? `<span class="popup-delay">+${vehicle.delay_minutes} min</span>`
            : '<span class="popup-on-time">On time</span>';
            
        return `
            <div class="popup-title">${vehicle.line_name || 'Unknown Line'}</div>
            <div class="popup-details">
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Type:</span>
                    <span class="popup-detail-value">${CONFIG.TRANSPORT_TYPES[vehicle.transport_type]?.name || vehicle.transport_type}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Direction:</span>
                    <span class="popup-detail-value">${vehicle.direction || 'Unknown'}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Status:</span>
                    <span class="popup-detail-value">${vehicle.status}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Delay:</span>
                    <span class="popup-detail-value">${delayText}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Time:</span>
                    <span class="popup-detail-value">${moment(vehicle.timestamp).format('HH:mm:ss')}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Create popup content for route
     */
    createRoutePopup(routeInfo) {
        return `
            <div class="popup-title">${routeInfo.line_name}</div>
            <div class="popup-details">
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Type:</span>
                    <span class="popup-detail-value">${CONFIG.TRANSPORT_TYPES[routeInfo.transport_type]?.name || routeInfo.transport_type}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Description:</span>
                    <span class="popup-detail-value">${routeInfo.description || 'No description'}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Vehicles (24h):</span>
                    <span class="popup-detail-value">${routeInfo.vehicle_count_24h || 0}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Create popup content for stop
     */
    createStopPopup(stopData) {
        const transportTypes = stopData.transport_types || [];
        const typesList = transportTypes.map(type => 
            CONFIG.TRANSPORT_TYPES[type]?.name || type
        ).join(', ');
        
        return `
            <div class="popup-title">${stopData.stop_name}</div>
            <div class="popup-details">
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Types:</span>
                    <span class="popup-detail-value">${typesList || 'Unknown'}</span>
                </div>
                <div class="popup-detail-row">
                    <span class="popup-detail-label">Tracked:</span>
                    <span class="popup-detail-value">${stopData.is_tracked ? 'Yes' : 'No'}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Clear vehicle markers
     */
    clearVehicleMarkers() {
        this.vehicleLayerGroup.clearLayers();
        this.vehicleMarkers.clear();
    }
    
    /**
     * Toggle route visibility
     */
    toggleRoutes() {
        this.showRoutes = !this.showRoutes;
        
        if (this.showRoutes) {
            this.routeLayers.forEach(layer => {
                this.routeLayerGroup.addLayer(layer);
            });
        } else {
            this.routeLayerGroup.clearLayers();
        }
        
        return this.showRoutes;
    }
    
    /**
     * Toggle stop visibility
     */
    toggleStops() {
        this.showStops = !this.showStops;
        
        if (this.showStops) {
            this.stopMarkers.forEach(marker => {
                this.stopLayerGroup.addLayer(marker);
            });
        } else {
            this.stopLayerGroup.clearLayers();
        }
        
        return this.showStops;
    }
    
    /**
     * Show vehicle info panel
     */
    showVehicleInfo(vehicle) {
        const infoPanel = document.getElementById('hover-info');
        const vehicleDetails = document.getElementById('vehicle-details');
        
        if (infoPanel && vehicleDetails) {
            vehicleDetails.innerHTML = this.createVehiclePopup(vehicle);
            infoPanel.classList.remove('hidden');
        }
    }
    
    /**
     * Hide vehicle info panel
     */
    hideVehicleInfo() {
        const infoPanel = document.getElementById('hover-info');
        if (infoPanel) {
            infoPanel.classList.add('hidden');
        }
    }
    
    /**
     * Event handlers
     */
    onZoomChange() {
        // Adjust marker sizes based on zoom level
        const zoom = this.map.getZoom();
        const scale = Math.max(0.5, Math.min(2, zoom / 11));
        
        // Update CSS custom property for marker scaling
        document.documentElement.style.setProperty('--marker-scale', scale);
    }
    
    onViewChange() {
        // Trigger viewport change event for performance optimization
        const event = new CustomEvent('mapViewChanged', {
            detail: {
                bounds: this.map.getBounds(),
                zoom: this.map.getZoom(),
                center: this.map.getCenter()
            }
        });
        window.dispatchEvent(event);
    }
    
    onMapClick(e) {
        // Handle map clicks
        if (CONFIG.DEBUG.ENABLED) {
            console.log('Map clicked at:', e.latlng);
        }
    }
    
    onVehicleClick(vehicle) {
        // Handle vehicle marker clicks
        const event = new CustomEvent('vehicleClicked', {
            detail: { vehicle }
        });
        window.dispatchEvent(event);
    }
    
    /**
     * Set vehicle to follow
     */
    setFollowVehicle(vehicleId) {
        this.followVehicle = vehicleId;
    }
    
    /**
     * Stop following vehicle
     */
    stopFollowing() {
        this.followVehicle = null;
    }
    
    /**
     * Get performance stats
     */
    getPerformanceStats() {
        return {
            lastUpdateTime: this.lastUpdateTime,
            renderCount: this.renderCount,
            vehicleCount: this.vehicleMarkers.size,
            routeCount: this.routeLayers.size,
            stopCount: this.stopMarkers.size
        };
    }
    
    /**
     * Resize map
     */
    resize() {
        if (this.map) {
            this.map.invalidateSize();
        }
    }
    
    /**
     * Destroy map instance
     */
    destroy() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
        this.isInitialized = false;
    }
}