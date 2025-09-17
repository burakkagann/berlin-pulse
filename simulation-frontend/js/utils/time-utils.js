// Berlin Transport Time Machine - Time Utilities

const TimeUtils = {
    /**
     * Format timestamp for display
     */
    formatTime(timestamp, format = 'HH:mm:ss') {
        return moment(timestamp).format(format);
    },
    
    /**
     * Format date for display
     */
    formatDate(timestamp, format = 'YYYY/MM/DD') {
        return moment(timestamp).format(format);
    },
    
    /**
     * Format duration in human readable format
     */
    formatDuration(seconds) {
        const duration = moment.duration(seconds, 'seconds');
        
        if (duration.asDays() >= 1) {
            return `${Math.floor(duration.asDays())}d ${duration.hours()}h ${duration.minutes()}m`;
        } else if (duration.asHours() >= 1) {
            return `${duration.hours()}h ${duration.minutes()}m`;
        } else if (duration.asMinutes() >= 1) {
            return `${duration.minutes()}m ${duration.seconds()}s`;
        } else {
            return `${duration.seconds()}s`;
        }
    },
    
    /**
     * Calculate time difference in minutes
     */
    diffInMinutes(start, end) {
        return moment(end).diff(moment(start), 'minutes');
    },
    
    /**
     * Calculate progress between two times
     */
    calculateProgress(current, start, end) {
        const total = moment(end).diff(moment(start));
        const elapsed = moment(current).diff(moment(start));
        
        return Math.max(0, Math.min(1, elapsed / total));
    },
    
    /**
     * Interpolate between two timestamps
     */
    interpolateTime(start, end, progress) {
        const startMs = moment(start).valueOf();
        const endMs = moment(end).valueOf();
        const interpolatedMs = startMs + (endMs - startMs) * progress;
        
        return new Date(interpolatedMs);
    },
    
    /**
     * Round time to nearest interval
     */
    roundToInterval(timestamp, intervalSeconds) {
        const ms = moment(timestamp).valueOf();
        const intervalMs = intervalSeconds * 1000;
        const rounded = Math.round(ms / intervalMs) * intervalMs;
        
        return new Date(rounded);
    },
    
    /**
     * Get time range chunks
     */
    getTimeChunks(startTime, endTime, chunkDurationMinutes) {
        const chunks = [];
        let current = moment(startTime);
        const end = moment(endTime);
        
        while (current.isBefore(end)) {
            const chunkEnd = moment.min(
                current.clone().add(chunkDurationMinutes, 'minutes'),
                end
            );
            
            chunks.push({
                start: current.toDate(),
                end: chunkEnd.toDate(),
                duration: chunkEnd.diff(current, 'minutes')
            });
            
            current = chunkEnd;
        }
        
        return chunks;
    },
    
    /**
     * Convert UTC to Berlin timezone
     */
    toBerlinTime(utcTime) {
        return moment.utc(utcTime).tz('Europe/Berlin');
    },
    
    /**
     * Check if time is within business hours
     */
    isBusinessHours(timestamp) {
        const time = moment(timestamp);
        const hour = time.hour();
        const day = time.day();
        
        // Monday = 1, Sunday = 0
        const isWeekday = day >= 1 && day <= 5;
        const isBusinessHour = hour >= 6 && hour <= 22;
        
        return isWeekday && isBusinessHour;
    },
    
    /**
     * Get rush hour periods
     */
    getRushHourPeriod(timestamp) {
        const hour = moment(timestamp).hour();
        
        if (hour >= 7 && hour <= 9) {
            return 'morning';
        } else if (hour >= 17 && hour <= 19) {
            return 'evening';
        } else if (hour >= 6 && hour <= 22) {
            return 'day';
        } else {
            return 'night';
        }
    },
    
    /**
     * Parse datetime-local input value
     */
    parseLocalDateTime(dateTimeLocalValue) {
        return moment(dateTimeLocalValue).toDate();
    },
    
    /**
     * Format for datetime-local input
     */
    formatForLocalInput(timestamp) {
        return moment(timestamp).format('YYYY-MM-DDTHH:mm');
    },
    
    /**
     * Validate timestamp is within bounds
     */
    isWithinBounds(timestamp, startTime, endTime) {
        const time = moment(timestamp);
        return time.isBetween(moment(startTime), moment(endTime), null, '[]');
    },
    
    /**
     * Get relative time description
     */
    getRelativeTime(timestamp) {
        return moment(timestamp).fromNow();
    },
    
    /**
     * Get time zone offset
     */
    getTimezoneOffset(timestamp) {
        return moment(timestamp).utcOffset();
    }
};

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.TimeUtils = TimeUtils;
}