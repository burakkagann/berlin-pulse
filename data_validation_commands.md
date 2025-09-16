# Berlin Pulse Data Validation Commands

## Database Connection
First, connect to your PostgreSQL database:
```bash
# Using Docker Compose
docker compose exec postgres psql -U transport_user -d berlin_transport

# Or from host (if port is exposed)
psql -h localhost -p 5432 -U transport_user -d berlin_transport
```

## Dataset Overview Commands

### 1. Check Table Structure and Row Counts
```sql
-- Get basic table information
SELECT 
    schemaname,
    tablename, 
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows
FROM pg_stat_user_tables 
ORDER BY live_rows DESC;
```

### 2. Transport Type Distribution
```sql
-- Check transport type classification
SELECT 
    transport_type,
    COUNT(*) as total_records,
    COUNT(DISTINCT vehicle_id) as unique_vehicles,
    COUNT(DISTINCT route_id) as unique_routes,
    MIN(timestamp) as earliest_record,
    MAX(timestamp) as latest_record
FROM vehicle_positions 
GROUP BY transport_type 
ORDER BY total_records DESC;
```

### 3. Data Quality Assessment
```sql
-- Check data completeness
SELECT 
    transport_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN route_id IS NOT NULL THEN 1 END) as has_route_id,
    COUNT(CASE WHEN line_name IS NOT NULL THEN 1 END) as has_line_name,
    COUNT(CASE WHEN direction IS NOT NULL THEN 1 END) as has_direction,
    COUNT(CASE WHEN delay_minutes IS NOT NULL THEN 1 END) as has_delay_data,
    ROUND(
        COUNT(CASE WHEN route_id IS NOT NULL THEN 1 END)::numeric / COUNT(*) * 100, 2
    ) as route_completeness_pct
FROM vehicle_positions 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY transport_type;
```

### 4. Recent Data Collection Status
```sql
-- Check collection status and recent activity
SELECT 
    collector_name,
    status,
    last_run_at,
    last_success_at,
    records_collected,
    error_message,
    EXTRACT(EPOCH FROM (NOW() - last_success_at))/60 as minutes_since_success
FROM collection_status
ORDER BY last_success_at DESC;
```

### 5. Geographic Distribution
```sql
-- Check geographic spread
SELECT 
    transport_type,
    COUNT(*) as records,
    MIN(latitude) as min_lat,
    MAX(latitude) as max_lat,
    MIN(longitude) as min_lng,
    MAX(longitude) as max_lng,
    ROUND(AVG(latitude)::numeric, 4) as avg_lat,
    ROUND(AVG(longitude)::numeric, 4) as avg_lng
FROM vehicle_positions 
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY transport_type;
```

### 6. Route Geometry Status
```sql
-- Check route geometry collection
SELECT 
    transport_type,
    COUNT(*) as routes_with_geometry,
    COUNT(DISTINCT route_id) as unique_routes,
    MIN(created_at) as first_geometry,
    MAX(updated_at) as last_updated
FROM route_geometry 
GROUP BY transport_type;
```

### 7. Departure Events Analysis
```sql
-- Check departure tracking
SELECT 
    transport_type,
    COUNT(*) as total_departures,
    COUNT(DISTINCT stop_id) as unique_stops,
    COUNT(CASE WHEN status = 'delayed' THEN 1 END) as delayed_count,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
    ROUND(AVG(delay_minutes), 2) as avg_delay_minutes
FROM departure_events 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY transport_type;
```

### 8. Top Active Lines by Transport Type
```sql
-- Most active lines in last hour
SELECT 
    transport_type,
    line_name,
    COUNT(*) as position_updates,
    COUNT(DISTINCT vehicle_id) as active_vehicles
FROM vehicle_positions 
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY transport_type, line_name
ORDER BY transport_type, position_updates DESC;
```

### 9. Sector Performance
```sql
-- Check Berlin sector data (if available)
SELECT 
    raw_data->>'sector' as sector,
    COUNT(*) as vehicle_count,
    COUNT(DISTINCT vehicle_id) as unique_vehicles,
    transport_type,
    MAX(timestamp) as latest_update
FROM vehicle_positions 
WHERE timestamp >= NOW() - INTERVAL '1 hour'
  AND raw_data->>'sector' IS NOT NULL
GROUP BY raw_data->>'sector', transport_type
ORDER BY vehicle_count DESC;
```

### 10. Data Freshness Check
```sql
-- Check how fresh the data is
SELECT 
    transport_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '5 minutes' THEN 1 END) as last_5min,
    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '15 minutes' THEN 1 END) as last_15min,
    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '1 hour' THEN 1 END) as last_1hour,
    MAX(timestamp) as newest_record,
    MIN(timestamp) as oldest_record
FROM vehicle_positions 
GROUP BY transport_type;
```

## Troubleshooting Queries

### Check for Ring Bahn Classification
```sql
-- Verify Ring Bahn lines are properly classified
SELECT 
    line_name,
    transport_type,
    COUNT(*) as records
FROM vehicle_positions 
WHERE line_name IN ('S41', 'S42')
GROUP BY line_name, transport_type;
```

### Check Line Name Patterns
```sql
-- Analyze line naming patterns
SELECT 
    transport_type,
    line_name,
    COUNT(*) as records,
    CASE 
        WHEN line_name ~ '^S[0-9]+$' THEN 'S-Bahn'
        WHEN line_name ~ '^U[0-9]+$' THEN 'U-Bahn'
        WHEN line_name ~ '^M[0-9]+$' THEN 'Metro Tram/Bus'
        WHEN line_name ~ '^[0-9]+$' THEN 'Regular Tram/Bus'
        WHEN line_name ~ '^X[0-9]+$' THEN 'Express Bus'
        WHEN line_name ~ '^N[0-9]+$' THEN 'Night Bus'
        ELSE 'Other'
    END as pattern_type
FROM vehicle_positions 
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY transport_type, line_name, pattern_type
ORDER BY records DESC
LIMIT 50;
```

## Expected Results Guide

- **Vehicle Positions**: Should show thousands of records per hour
- **Transport Types**: suburban, subway, tram, bus, ring (if Ring Bahn data exists)
- **Collection Status**: All collectors should show "idle" or "running" status
- **Data Freshness**: Most recent records should be within last 5-15 minutes
- **Geographic Bounds**: Berlin area (lat: 52.3-52.7, lng: 13.0-13.8)
- **Route Completeness**: Should be >80% for route_id field

## Quick Health Check Command
```sql
-- One-liner system health check
SELECT 
    'SYSTEM HEALTH CHECK' as check_type,
    COUNT(*) as total_vehicle_positions_24h,
    COUNT(DISTINCT transport_type) as transport_types,
    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '15 minutes' THEN 1 END) as fresh_records,
    MAX(timestamp) as newest_data,
    (SELECT COUNT(*) FROM route_geometry) as stored_routes,
    (SELECT COUNT(*) FROM departure_events WHERE timestamp >= NOW() - INTERVAL '24 hours') as departure_events_24h
FROM vehicle_positions 
WHERE timestamp >= NOW() - INTERVAL '24 hours';
```