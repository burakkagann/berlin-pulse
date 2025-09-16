-- Berlin Transport Time Machine Database Schema
-- Phase 1: Data Collection Infrastructure

-- Create database user and set permissions
CREATE USER IF NOT EXISTS transport_user WITH PASSWORD 'transport_pass';
GRANT ALL PRIVILEGES ON DATABASE berlin_transport TO transport_user;

-- Vehicle position tracking table
CREATE TABLE IF NOT EXISTS vehicle_positions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    vehicle_id VARCHAR(50) NOT NULL,
    route_id VARCHAR(20),
    line_name VARCHAR(10),
    transport_type VARCHAR(20) NOT NULL, -- 'suburban', 'subway', 'tram', 'bus'
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(11, 7) NOT NULL,
    direction VARCHAR(100),
    delay_minutes INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'delayed', 'cancelled'
    raw_data JSONB, -- Store original API response
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Departure/arrival events table
CREATE TABLE IF NOT EXISTS departure_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    stop_id VARCHAR(50) NOT NULL,
    stop_name VARCHAR(200) NOT NULL,
    route_id VARCHAR(20),
    line_name VARCHAR(10),
    transport_type VARCHAR(20) NOT NULL,
    direction VARCHAR(200),
    scheduled_time TIMESTAMPTZ NOT NULL,
    actual_time TIMESTAMPTZ,
    delay_minutes INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'on_time', -- 'on_time', 'delayed', 'cancelled'
    platform VARCHAR(20),
    trip_id VARCHAR(100),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Route geometry storage
CREATE TABLE IF NOT EXISTS route_geometry (
    id SERIAL PRIMARY KEY,
    route_id VARCHAR(20) NOT NULL,
    line_name VARCHAR(10) NOT NULL,
    transport_type VARCHAR(20) NOT NULL,
    direction VARCHAR(200),
    trip_id VARCHAR(100),
    geometry_geojson JSONB NOT NULL, -- GeoJSON FeatureCollection
    stops_data JSONB, -- Array of stops with coordinates
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stops reference table
CREATE TABLE IF NOT EXISTS stops_reference (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(50) UNIQUE NOT NULL,
    stop_name VARCHAR(200) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(11, 7) NOT NULL,
    products JSONB, -- Transport types available at this stop
    is_tracked BOOLEAN DEFAULT FALSE, -- Whether this is one of our 10 tracked stops
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Data collection status tracking
CREATE TABLE IF NOT EXISTS collection_status (
    id SERIAL PRIMARY KEY,
    collector_name VARCHAR(50) NOT NULL,
    last_run_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'idle', -- 'running', 'idle', 'error'
    error_message TEXT,
    records_collected INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_timestamp ON vehicle_positions(timestamp);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_route_time ON vehicle_positions(route_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_vehicle_time ON vehicle_positions(vehicle_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_transport_type ON vehicle_positions(transport_type);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_location ON vehicle_positions(latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_departure_events_timestamp ON departure_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_departure_events_stop_time ON departure_events(stop_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_departure_events_scheduled_time ON departure_events(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_departure_events_transport_type ON departure_events(transport_type);

CREATE INDEX IF NOT EXISTS idx_route_geometry_route ON route_geometry(route_id, transport_type);
CREATE INDEX IF NOT EXISTS idx_stops_reference_stop_id ON stops_reference(stop_id);
CREATE INDEX IF NOT EXISTS idx_stops_reference_tracked ON stops_reference(is_tracked) WHERE is_tracked = TRUE;

CREATE INDEX IF NOT EXISTS idx_collection_status_name ON collection_status(collector_name);

-- Insert tracked stops data
INSERT INTO stops_reference (stop_id, stop_name, latitude, longitude, is_tracked) VALUES
    ('900100003', 'S+U Alexanderplatz', 52.521508, 13.411267, TRUE),
    ('900003201', 'S+U Zoologischer Garten', 52.507450, 13.332740, TRUE),
    ('900100001', 'S+U Friedrichstr.', 52.520330, 13.387140, TRUE),
    ('900120005', 'S Ostbahnhof', 52.510972, 13.434567, TRUE),
    ('900100004', 'S+U Potsdamer Platz', 52.509470, 13.376200, TRUE),
    ('900100002', 'Berlin Hauptbahnhof', 52.525592, 13.369548, TRUE),
    ('900058102', 'S Gesundbrunnen', 52.548900, 13.384700, TRUE),
    ('900056102', 'S Südkreuz', 52.475800, 13.365300, TRUE),
    ('900068201', 'U Tempelhof', 52.471000, 13.385800, TRUE),
    ('900245025', 'S Warschauer Str.', 52.506944, 13.449444, TRUE)
ON CONFLICT (stop_id) DO UPDATE SET
    stop_name = EXCLUDED.stop_name,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    is_tracked = EXCLUDED.is_tracked,
    updated_at = NOW();

-- Grant permissions to transport_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO transport_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO transport_user;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_route_geometry_updated_at BEFORE UPDATE ON route_geometry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stops_reference_updated_at BEFORE UPDATE ON stops_reference
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_collection_status_updated_at BEFORE UPDATE ON collection_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();