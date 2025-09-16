-- Migration 001: Fix VARCHAR length constraints
-- Fix database schema constraints causing vehicle data insertion failures

-- Update vehicle_positions table constraints
ALTER TABLE vehicle_positions 
    ALTER COLUMN route_id TYPE VARCHAR(50),
    ALTER COLUMN line_name TYPE VARCHAR(30);

-- Update departure_events table constraints for consistency
ALTER TABLE departure_events 
    ALTER COLUMN route_id TYPE VARCHAR(50),
    ALTER COLUMN line_name TYPE VARCHAR(30);

-- Update route_geometry table constraints for consistency  
ALTER TABLE route_geometry 
    ALTER COLUMN route_id TYPE VARCHAR(50),
    ALTER COLUMN line_name TYPE VARCHAR(30);

-- Add indexes for the updated columns
DROP INDEX IF EXISTS idx_vehicle_positions_route_time;
CREATE INDEX idx_vehicle_positions_route_time ON vehicle_positions(route_id, timestamp);

DROP INDEX IF EXISTS idx_route_geometry_route;
CREATE INDEX idx_route_geometry_route ON route_geometry(route_id, transport_type);