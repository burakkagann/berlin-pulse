-- Migration 002: Fix collection_status table unique constraint
-- Add unique constraint for collector_name to support ON CONFLICT clause

-- Add unique constraint on collector_name
ALTER TABLE collection_status 
    ADD CONSTRAINT unique_collector_name UNIQUE (collector_name);