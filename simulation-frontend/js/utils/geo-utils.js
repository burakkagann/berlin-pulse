// Berlin Transport Time Machine - Geographic Utilities

const GeoUtils = {
    /**
     * Calculate distance between two points using Haversine formula
     * Returns distance in meters
     */
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 6371000; // Earth's radius in meters
        const φ1 = this.toRadians(lat1);
        const φ2 = this.toRadians(lat2);
        const Δφ = this.toRadians(lat2 - lat1);
        const Δλ = this.toRadians(lng2 - lng1);
        
        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        
        return R * c;
    },
    
    /**
     * Calculate bearing between two points
     * Returns bearing in degrees (0-360)
     */
    calculateBearing(lat1, lng1, lat2, lng2) {
        const φ1 = this.toRadians(lat1);
        const φ2 = this.toRadians(lat2);
        const Δλ = this.toRadians(lng2 - lng1);
        
        const y = Math.sin(Δλ) * Math.cos(φ2);
        const x = Math.cos(φ1) * Math.sin(φ2) - 
                  Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
        
        const θ = Math.atan2(y, x);
        
        return (this.toDegrees(θ) + 360) % 360;
    },
    
    /**
     * Interpolate position between two points
     */
    interpolatePosition(lat1, lng1, lat2, lng2, fraction) {
        const φ1 = this.toRadians(lat1);
        const λ1 = this.toRadians(lng1);
        const φ2 = this.toRadians(lat2);
        const λ2 = this.toRadians(lng2);
        
        // Simple linear interpolation for short distances
        if (this.calculateDistance(lat1, lng1, lat2, lng2) < 1000) {
            return {
                lat: lat1 + (lat2 - lat1) * fraction,
                lng: lng1 + (lng2 - lng1) * fraction
            };
        }
        
        // Great circle interpolation for longer distances
        const d = Math.acos(Math.sin(φ1) * Math.sin(φ2) + 
                           Math.cos(φ1) * Math.cos(φ2) * Math.cos(λ2 - λ1));
        
        if (d === 0) {
            return { lat: lat1, lng: lng1 };
        }
        
        const a = Math.sin((1 - fraction) * d) / Math.sin(d);
        const b = Math.sin(fraction * d) / Math.sin(d);
        
        const x = a * Math.cos(φ1) * Math.cos(λ1) + b * Math.cos(φ2) * Math.cos(λ2);
        const y = a * Math.cos(φ1) * Math.sin(λ1) + b * Math.cos(φ2) * Math.sin(λ2);
        const z = a * Math.sin(φ1) + b * Math.sin(φ2);
        
        const φ3 = Math.atan2(z, Math.sqrt(x * x + y * y));
        const λ3 = Math.atan2(y, x);
        
        return {
            lat: this.toDegrees(φ3),
            lng: this.toDegrees(λ3)
        };
    },
    
    /**
     * Calculate speed in km/h between two positions and times
     */
    calculateSpeed(lat1, lng1, time1, lat2, lng2, time2) {
        const distance = this.calculateDistance(lat1, lng1, lat2, lng2); // meters
        const timeDiff = (time2.getTime() - time1.getTime()) / 1000; // seconds
        
        if (timeDiff <= 0) return 0;
        
        const speedMs = distance / timeDiff;
        return speedMs * 3.6; // Convert m/s to km/h
    },
    
    /**
     * Check if point is within Berlin bounds
     */
    isWithinBerlin(lat, lng) {
        return lat >= CONFIG.MAP.BOUNDS.MIN_LAT && 
               lat <= CONFIG.MAP.BOUNDS.MAX_LAT &&
               lng >= CONFIG.MAP.BOUNDS.MIN_LNG && 
               lng <= CONFIG.MAP.BOUNDS.MAX_LNG;
    },
    
    /**
     * Get bounding box for a set of coordinates
     */
    getBoundingBox(coordinates, padding = 0.01) {
        if (!coordinates || coordinates.length === 0) {
            return {
                minLat: CONFIG.MAP.BOUNDS.MIN_LAT,
                maxLat: CONFIG.MAP.BOUNDS.MAX_LAT,
                minLng: CONFIG.MAP.BOUNDS.MIN_LNG,
                maxLng: CONFIG.MAP.BOUNDS.MAX_LNG
            };
        }
        
        const lats = coordinates.map(coord => coord.lat || coord[0]);
        const lngs = coordinates.map(coord => coord.lng || coord[1]);
        
        return {
            minLat: Math.min(...lats) - padding,
            maxLat: Math.max(...lats) + padding,
            minLng: Math.min(...lngs) - padding,
            maxLng: Math.max(...lngs) + padding
        };
    },
    
    /**
     * Check if point is within bounding box
     */
    isWithinBounds(lat, lng, bounds) {
        return lat >= bounds.minLat && lat <= bounds.maxLat &&
               lng >= bounds.minLng && lng <= bounds.maxLng;
    },
    
    /**
     * Convert coordinates to Berlin local grid system (if needed)
     */
    toBerlinGrid(lat, lng) {
        // This would implement conversion to local coordinate system
        // For now, just return lat/lng
        return { x: lng, y: lat };
    },
    
    /**
     * Create GeoJSON Point feature
     */
    createGeoJSONPoint(lat, lng, properties = {}) {
        return {
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [lng, lat]
            },
            properties: properties
        };
    },
    
    /**
     * Create GeoJSON LineString feature
     */
    createGeoJSONLineString(coordinates, properties = {}) {
        return {
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: coordinates.map(coord => [
                    coord.lng || coord[1], 
                    coord.lat || coord[0]
                ])
            },
            properties: properties
        };
    },
    
    /**
     * Simplify line using Douglas-Peucker algorithm
     */
    simplifyLine(points, tolerance = 0.001) {
        if (points.length <= 2) return points;
        
        return this.douglasPeucker(points, tolerance);
    },
    
    /**
     * Douglas-Peucker line simplification
     */
    douglasPeucker(points, tolerance) {
        if (points.length <= 2) return points;
        
        let maxDistance = 0;
        let maxIndex = 0;
        
        for (let i = 1; i < points.length - 1; i++) {
            const distance = this.perpendicularDistance(
                points[i], 
                points[0], 
                points[points.length - 1]
            );
            
            if (distance > maxDistance) {
                maxDistance = distance;
                maxIndex = i;
            }
        }
        
        if (maxDistance > tolerance) {
            const left = this.douglasPeucker(points.slice(0, maxIndex + 1), tolerance);
            const right = this.douglasPeucker(points.slice(maxIndex), tolerance);
            
            return left.slice(0, -1).concat(right);
        } else {
            return [points[0], points[points.length - 1]];
        }
    },
    
    /**
     * Calculate perpendicular distance from point to line
     */
    perpendicularDistance(point, lineStart, lineEnd) {
        const A = lineEnd.lat - lineStart.lat;
        const B = lineStart.lng - lineEnd.lng;
        const C = lineEnd.lng * lineStart.lat - lineStart.lng * lineEnd.lat;
        
        return Math.abs(A * point.lng + B * point.lat + C) / 
               Math.sqrt(A * A + B * B);
    },
    
    /**
     * Snap point to nearest position on line
     */
    snapToLine(point, linePoints) {
        let minDistance = Infinity;
        let closestPoint = null;
        let segmentIndex = -1;
        
        for (let i = 0; i < linePoints.length - 1; i++) {
            const segment = this.closestPointOnSegment(
                point, 
                linePoints[i], 
                linePoints[i + 1]
            );
            
            const distance = this.calculateDistance(
                point.lat, point.lng,
                segment.lat, segment.lng
            );
            
            if (distance < minDistance) {
                minDistance = distance;
                closestPoint = segment;
                segmentIndex = i;
            }
        }
        
        return {
            point: closestPoint,
            distance: minDistance,
            segmentIndex: segmentIndex
        };
    },
    
    /**
     * Find closest point on line segment
     */
    closestPointOnSegment(point, segmentStart, segmentEnd) {
        const A = point.lng - segmentStart.lng;
        const B = point.lat - segmentStart.lat;
        const C = segmentEnd.lng - segmentStart.lng;
        const D = segmentEnd.lat - segmentStart.lat;
        
        const dot = A * C + B * D;
        const lenSq = C * C + D * D;
        
        if (lenSq === 0) {
            return { lat: segmentStart.lat, lng: segmentStart.lng };
        }
        
        const param = dot / lenSq;
        
        if (param < 0) {
            return { lat: segmentStart.lat, lng: segmentStart.lng };
        } else if (param > 1) {
            return { lat: segmentEnd.lat, lng: segmentEnd.lng };
        } else {
            return {
                lat: segmentStart.lat + param * D,
                lng: segmentStart.lng + param * C
            };
        }
    },
    
    /**
     * Utility functions
     */
    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    },
    
    toDegrees(radians) {
        return radians * (180 / Math.PI);
    },
    
    /**
     * Format coordinates for display
     */
    formatCoordinates(lat, lng, precision = 6) {
        return {
            lat: parseFloat(lat.toFixed(precision)),
            lng: parseFloat(lng.toFixed(precision))
        };
    },
    
    /**
     * Validate coordinates
     */
    isValidCoordinate(lat, lng) {
        return typeof lat === 'number' && typeof lng === 'number' &&
               lat >= -90 && lat <= 90 &&
               lng >= -180 && lng <= 180 &&
               !isNaN(lat) && !isNaN(lng);
    }
};

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.GeoUtils = GeoUtils;
}