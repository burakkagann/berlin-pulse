-- Migration 003: Fix collection_status unique constraint
-- Add unique constraint for collector_name to support ON CONFLICT clause

-- First, remove any duplicate entries if they exist
DELETE FROM collection_status a USING collection_status b
WHERE a.id < b.id AND a.collector_name = b.collector_name;

-- Add unique constraint on collector_name
ALTER TABLE collection_status 
    ADD CONSTRAINT unique_collector_name UNIQUE (collector_name);