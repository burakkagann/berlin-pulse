-- Migration 004: Reclassify existing transport types with Berlin-specific patterns
-- Fix misclassified Ring Bahn and MetroTram lines in existing data

-- Step 1: Add 'ring' transport type to the enum if it doesn't exist
DO $$ 
BEGIN
    -- Check if 'ring' type exists in the enum
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = 'ring' 
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transport_type')
    ) THEN
        ALTER TYPE transport_type ADD VALUE 'ring';
    END IF;
END $$;

-- Step 2: Update Ring Bahn lines (S41, S42) from 'suburban' to 'ring'
UPDATE vehicle_positions 
SET transport_type = 'ring'
WHERE line_name IN ('S41', 'S42') 
AND transport_type = 'suburban';

-- Step 3: Update MetroTram lines (M-prefix) from 'suburban' to 'tram'
UPDATE vehicle_positions 
SET transport_type = 'tram'
WHERE line_name ~ '^M[1-9][0-9]?$'
AND transport_type = 'suburban';

-- Step 4: Update specific regular tram lines that might be misclassified
UPDATE vehicle_positions 
SET transport_type = 'tram'
WHERE line_name IN ('12', '16', '18', '21', '27', '37', '50', '60', '61', '62', '63', '67', '68')
AND transport_type != 'tram';

-- Step 5: Update Express Bus lines (X-prefix) to ensure they're marked as 'bus'
UPDATE vehicle_positions 
SET transport_type = 'bus'
WHERE line_name ~ '^X[1-9][0-9]?$'
AND transport_type != 'bus';

-- Step 6: Update Night Bus lines (N-prefix) to ensure they're marked as 'bus'
UPDATE vehicle_positions 
SET transport_type = 'bus'
WHERE line_name ~ '^N[1-9][0-9]?$'
AND transport_type != 'bus';

-- Step 7: Fix departure_events table as well
-- Update Ring Bahn lines in departure_events
UPDATE departure_events 
SET transport_type = 'ring'
WHERE line_name IN ('S41', 'S42') 
AND transport_type = 'suburban';

-- Update MetroTram lines in departure_events
UPDATE departure_events 
SET transport_type = 'tram'
WHERE line_name ~ '^M[1-9][0-9]?$'
AND transport_type = 'suburban';

-- Update specific regular tram lines in departure_events
UPDATE departure_events 
SET transport_type = 'tram'
WHERE line_name IN ('12', '16', '18', '21', '27', '37', '50', '60', '61', '62', '63', '67', '68')
AND transport_type != 'tram';

-- Update Express Bus lines in departure_events
UPDATE departure_events 
SET transport_type = 'bus'
WHERE line_name ~ '^X[1-9][0-9]?$'
AND transport_type != 'bus';

-- Update Night Bus lines in departure_events
UPDATE departure_events 
SET transport_type = 'bus'
WHERE line_name ~ '^N[1-9][0-9]?$'
AND transport_type != 'bus';

-- Log the results
DO $$
DECLARE
    ring_vehicles INTEGER;
    metro_tram_vehicles INTEGER;
    ring_departures INTEGER;
    metro_tram_departures INTEGER;
BEGIN
    -- Count reclassified records
    SELECT COUNT(*) INTO ring_vehicles 
    FROM vehicle_positions 
    WHERE transport_type = 'ring';
    
    SELECT COUNT(*) INTO metro_tram_vehicles 
    FROM vehicle_positions 
    WHERE transport_type = 'tram' AND line_name ~ '^M[1-9][0-9]?$';
    
    SELECT COUNT(*) INTO ring_departures 
    FROM departure_events 
    WHERE transport_type = 'ring';
    
    SELECT COUNT(*) INTO metro_tram_departures 
    FROM departure_events 
    WHERE transport_type = 'tram' AND line_name ~ '^M[1-9][0-9]?$';
    
    RAISE NOTICE 'Reclassification complete:';
    RAISE NOTICE 'Ring Bahn vehicles: %', ring_vehicles;
    RAISE NOTICE 'MetroTram vehicles: %', metro_tram_vehicles;
    RAISE NOTICE 'Ring Bahn departures: %', ring_departures;
    RAISE NOTICE 'MetroTram departures: %', metro_tram_departures;
END $$;