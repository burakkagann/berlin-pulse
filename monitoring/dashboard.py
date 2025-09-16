"""
Real-time monitoring dashboard for Berlin Transport data collection.
Provides web interface to monitor collection status, data quality, and system health.
"""

import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import psycopg2
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import plotly.graph_objs as go
import plotly.utils
import pandas as pd
import redis
import uvicorn

app = FastAPI(title="Berlin Transport Data Collection Monitor")

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://transport_user:transport_pass@postgres:5432/berlin_transport')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# Setup templates
templates = Jinja2Templates(directory="templates")

class DataCollectionMonitor:
    def __init__(self):
        self.db_connection = None
        self.redis_client = None
        
    def get_db_connection(self):
        """Get database connection"""
        if not self.db_connection or self.db_connection.closed:
            self.db_connection = psycopg2.connect(DATABASE_URL)
        return self.db_connection
    
    def get_redis_client(self):
        """Get Redis client"""
        if not self.redis_client:
            self.redis_client = redis.from_url(REDIS_URL)
        return self.redis_client
    
    def get_collection_status(self) -> List[Dict]:
        """Get current status of all collectors"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT collector_name, status, last_run_at, last_success_at,
                       records_collected, error_message, updated_at
                FROM collection_status
                ORDER BY collector_name
            """)
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            collectors = []
            for row in rows:
                collector = dict(zip(columns, row))
                
                # Calculate time since last success
                if collector['last_success_at']:
                    time_diff = datetime.now() - collector['last_success_at'].replace(tzinfo=None)
                    collector['time_since_success'] = time_diff.total_seconds()
                else:
                    collector['time_since_success'] = None
                
                # Determine health status with different thresholds for different collectors
                if collector['status'] == 'error':
                    collector['health'] = 'error'
                elif collector['time_since_success']:
                    # Route-based collectors have longer intervals, use 4 hour threshold
                    if collector['collector_name'] in ['route_mapper']:
                        threshold = 14400  # 4 hours
                    else:
                        threshold = 600    # 10 minutes for real-time collectors
                    
                    if collector['time_since_success'] > threshold:
                        collector['health'] = 'warning'
                    else:
                        collector['health'] = 'healthy'
                else:
                    collector['health'] = 'healthy'
                
                collectors.append(collector)
            
            return collectors
            
        except Exception as e:
            print(f"Error getting collection status: {e}")
            return []
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """Get data collection statistics"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get vehicle position statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_positions,
                    COUNT(DISTINCT vehicle_id) as unique_vehicles,
                    COUNT(DISTINCT route_id) as unique_routes,
                    MIN(timestamp) as earliest_data,
                    MAX(timestamp) as latest_data
                FROM vehicle_positions
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            """)
            vehicle_stats = dict(zip([desc[0] for desc in cursor.description], cursor.fetchone()))
            
            # Get departure event statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_departures,
                    COUNT(DISTINCT stop_id) as unique_stops,
                    AVG(delay_minutes) as avg_delay,
                    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count
                FROM departure_events
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            """)
            departure_stats = dict(zip([desc[0] for desc in cursor.description], cursor.fetchone()))
            
            # Get route geometry count
            cursor.execute("SELECT COUNT(*) as route_count FROM route_geometry")
            route_count = cursor.fetchone()[0]
            
            # Get transport type breakdown
            cursor.execute("""
                SELECT transport_type, COUNT(*) as count
                FROM vehicle_positions
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
                GROUP BY transport_type
                ORDER BY count DESC
            """)
            transport_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                'vehicle_stats': vehicle_stats,
                'departure_stats': departure_stats,
                'route_count': route_count,
                'transport_breakdown': transport_breakdown
            }
            
        except Exception as e:
            print(f"Error getting data statistics: {e}")
            return {}
    
    def get_hourly_collection_data(self) -> Dict[str, Any]:
        """Get hourly collection data for charts"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Vehicle positions per hour for last 24 hours
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('hour', timestamp) as hour,
                    COUNT(*) as vehicle_count
                FROM vehicle_positions
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour
            """)
            vehicle_hourly = cursor.fetchall()
            
            # Departure events per hour
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('hour', timestamp) as hour,
                    COUNT(*) as departure_count
                FROM departure_events
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour
            """)
            departure_hourly = cursor.fetchall()
            
            return {
                'vehicle_hourly': vehicle_hourly,
                'departure_hourly': departure_hourly
            }
            
        except Exception as e:
            print(f"Error getting hourly data: {e}")
            return {}
    
    def create_collection_chart(self) -> str:
        """Create collection volume chart"""
        try:
            hourly_data = self.get_hourly_collection_data()
            
            if not hourly_data:
                return ""
            
            # Prepare data for plotting
            vehicle_data = hourly_data.get('vehicle_hourly', [])
            departure_data = hourly_data.get('departure_hourly', [])
            
            if not vehicle_data and not departure_data:
                return ""
            
            fig = go.Figure()
            
            if vehicle_data:
                vehicle_hours = [row[0] for row in vehicle_data]
                vehicle_counts = [row[1] for row in vehicle_data]
                
                fig.add_trace(go.Scatter(
                    x=vehicle_hours,
                    y=vehicle_counts,
                    mode='lines+markers',
                    name='Vehicle Positions',
                    line=dict(color='#00d4ff', width=3)
                ))
            
            if departure_data:
                departure_hours = [row[0] for row in departure_data]
                departure_counts = [row[1] for row in departure_data]
                
                fig.add_trace(go.Scatter(
                    x=departure_hours,
                    y=departure_counts,
                    mode='lines+markers',
                    name='Departure Events',
                    line=dict(color='#7c3aed', width=3)
                ))
            
            fig.update_layout(
                title='Data Collection Volume (Last 24 Hours)',
                xaxis_title='Time',
                yaxis_title='Records Collected',
                template='plotly_dark',
                height=400,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating collection chart: {e}")
            return ""
    
    def create_transport_breakdown_chart(self) -> str:
        """Create transport type breakdown chart"""
        try:
            stats = self.get_data_statistics()
            transport_breakdown = stats.get('transport_breakdown', {})
            
            if not transport_breakdown:
                return ""
            
            colors = {
                'suburban': '#0066cc',
                'subway': '#003d82',
                'ring': '#ff6b35',
                'tram': '#00a86b',
                'bus': '#dc2626',
                'ferry': '#8b5cf6',
                'regional': '#ff8c00',
                'express': '#dc143c'
            }
            
            labels = list(transport_breakdown.keys())
            values = list(transport_breakdown.values())
            chart_colors = [colors.get(label, '#888888') for label in labels]
            
            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                marker_colors=chart_colors,
                textinfo='label+percent',
                hole=0.4
            )])
            
            fig.update_layout(
                title='Active Vehicles by Transport Type (Last Hour)',
                template='plotly_dark',
                height=400,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating transport breakdown chart: {e}")
            return ""
    
    def get_sector_performance(self) -> Dict[str, Any]:
        """Get performance metrics by Berlin sector"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Extract sector from raw_data and get counts
            cursor.execute("""
                SELECT 
                    raw_data->>'sector' as sector,
                    COUNT(*) as vehicle_count,
                    COUNT(DISTINCT vehicle_id) as unique_vehicles,
                    AVG(delay_minutes) as avg_delay,
                    MAX(timestamp) as latest_update
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
                  AND raw_data->>'sector' IS NOT NULL
                GROUP BY raw_data->>'sector'
                ORDER BY vehicle_count DESC
            """)
            
            sectors = []
            for row in cursor.fetchall():
                sector_data = {
                    'name': row[0],
                    'vehicle_count': row[1],
                    'unique_vehicles': row[2],
                    'avg_delay': round(row[3] or 0, 1),
                    'latest_update': row[4],
                    'health': 'healthy' if row[4] and (datetime.now() - row[4].replace(tzinfo=None)).total_seconds() < 300 else 'warning'
                }
                sectors.append(sector_data)
            
            return {'sectors': sectors}
            
        except Exception as e:
            print(f"Error getting sector performance: {e}")
            return {'sectors': []}
    
    def get_collection_rates(self) -> Dict[str, Any]:
        """Get real-time collection rate metrics"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get collection rates for last few minutes
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('minute', timestamp) as minute,
                    COUNT(*) as count
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '10 minutes'
                GROUP BY minute
                ORDER BY minute DESC
                LIMIT 10
            """)
            
            rates = []
            for row in cursor.fetchall():
                rates.append({
                    'minute': row[0],
                    'count': row[1]
                })
            
            # Calculate average rate
            avg_rate = sum(r['count'] for r in rates) / len(rates) if rates else 0
            
            return {
                'rates': rates,
                'avg_rate_per_minute': round(avg_rate, 1),
                'current_rate': rates[0]['count'] if rates else 0
            }
            
        except Exception as e:
            print(f"Error getting collection rates: {e}")
            return {'rates': [], 'avg_rate_per_minute': 0, 'current_rate': 0}
    
    def get_api_health_metrics(self) -> Dict[str, Any]:
        """Get API health and response time metrics"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get recent data quality metrics
            cursor.execute("""
                SELECT 
                    transport_type,
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN route_id IS NOT NULL THEN 1 END) as with_route,
                    COUNT(CASE WHEN line_name IS NOT NULL THEN 1 END) as with_line,
                    COUNT(CASE WHEN delay_minutes > 0 THEN 1 END) as with_delay
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
                GROUP BY transport_type
                ORDER BY total_records DESC
            """)
            
            quality_metrics = {}
            for row in cursor.fetchall():
                transport_type = row[0]
                total = row[1]
                quality_metrics[transport_type] = {
                    'total_records': total,
                    'route_completeness': round((row[2] / total) * 100, 1) if total > 0 else 0,
                    'line_completeness': round((row[3] / total) * 100, 1) if total > 0 else 0,
                    'delay_data_available': round((row[4] / total) * 100, 1) if total > 0 else 0
                }
            
            return quality_metrics
            
        except Exception as e:
            print(f"Error getting API health metrics: {e}")
            return {}
    
    def create_sector_performance_chart(self) -> str:
        """Create sector performance visualization"""
        try:
            sector_data = self.get_sector_performance()
            sectors = sector_data.get('sectors', [])
            
            if not sectors:
                return ""
            
            fig = go.Figure()
            
            # Vehicle count by sector
            sector_names = [s['name'] for s in sectors]
            vehicle_counts = [s['vehicle_count'] for s in sectors]
            unique_counts = [s['unique_vehicles'] for s in sectors]
            
            fig.add_trace(go.Bar(
                x=sector_names,
                y=vehicle_counts,
                name='Total Vehicles',
                marker_color='#00d4ff',
                yaxis='y'
            ))
            
            fig.add_trace(go.Bar(
                x=sector_names,
                y=unique_counts,
                name='Unique Vehicles',
                marker_color='#7c3aed',
                yaxis='y'
            ))
            
            fig.update_layout(
                title='Vehicle Collection by Berlin Sector (Last Hour)',
                xaxis_title='Sector',
                yaxis_title='Vehicle Count',
                template='plotly_dark',
                height=400,
                margin=dict(l=40, r=40, t=40, b=40),
                barmode='group'
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating sector performance chart: {e}")
            return ""
    
    def create_collection_rate_chart(self) -> str:
        """Create real-time collection rate chart"""
        try:
            rate_data = self.get_collection_rates()
            rates = rate_data.get('rates', [])
            
            if not rates:
                return ""
            
            times = [r['minute'] for r in reversed(rates)]
            counts = [r['count'] for r in reversed(rates)]
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=times,
                y=counts,
                mode='lines+markers',
                name='Vehicles/Minute',
                line=dict(color='#10b981', width=3),
                marker=dict(size=8)
            ))
            
            # Add average line
            avg_rate = rate_data.get('avg_rate_per_minute', 0)
            fig.add_hline(
                y=avg_rate,
                line_dash="dash",
                line_color="#f59e0b",
                annotation_text=f"Avg: {avg_rate:.1f}/min"
            )
            
            fig.update_layout(
                title='Real-time Collection Rate (Last 10 Minutes)',
                xaxis_title='Time',
                yaxis_title='Vehicles Collected per Minute',
                template='plotly_dark',
                height=300,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating collection rate chart: {e}")
            return ""
    
    def get_geographic_data(self) -> Dict[str, Any]:
        """Get geographic distribution of vehicles for map visualization"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get recent vehicle positions with coordinates
            cursor.execute("""
                SELECT 
                    latitude,
                    longitude,
                    transport_type,
                    line_name,
                    direction,
                    status,
                    delay_minutes,
                    raw_data->>'sector' as sector
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '10 minutes'
                  AND latitude BETWEEN 52.3 AND 52.7
                  AND longitude BETWEEN 13.0 AND 13.8
                ORDER BY timestamp DESC
                LIMIT 1000
            """)
            
            vehicles = []
            for row in cursor.fetchall():
                vehicle = {
                    'lat': float(row[0]),
                    'lng': float(row[1]),
                    'transport_type': row[2],
                    'line_name': row[3] or 'Unknown',
                    'direction': row[4] or 'Unknown',
                    'status': row[5] or 'active',
                    'delay_minutes': row[6] or 0,
                    'sector': row[7] or 'unknown'
                }
                vehicles.append(vehicle)
            
            # Get sector boundaries (approximate)
            sector_boundaries = {
                'central': {'center': [52.515, 13.40], 'bounds': [[52.48, 13.35], [52.55, 13.45]]},
                'east': {'center': [52.515, 13.50], 'bounds': [[52.48, 13.45], [52.55, 13.55]]},
                'west': {'center': [52.515, 13.30], 'bounds': [[52.48, 13.25], [52.55, 13.35]]},
                'north': {'center': [52.575, 13.40], 'bounds': [[52.55, 13.30], [52.60, 13.50]]},
                'south': {'center': [52.45, 13.40], 'bounds': [[52.42, 13.30], [52.48, 13.50]]},
                'northeast': {'center': [52.575, 13.60], 'bounds': [[52.55, 13.50], [52.60, 13.70]]},
                'southeast': {'center': [52.45, 13.60], 'bounds': [[52.42, 13.50], [52.48, 13.70]]},
                'northwest': {'center': [52.575, 13.20], 'bounds': [[52.55, 13.10], [52.60, 13.30]]},
                'southwest': {'center': [52.43, 13.20], 'bounds': [[52.40, 13.10], [52.48, 13.30]]}
            }
            
            return {
                'vehicles': vehicles,
                'sectors': sector_boundaries,
                'total_vehicles': len(vehicles)
            }
            
        except Exception as e:
            print(f"Error getting geographic data: {e}")
            return {'vehicles': [], 'sectors': {}, 'total_vehicles': 0}
    
    def create_heat_density_chart(self) -> str:
        """Create vehicle density heat map chart"""
        try:
            geo_data = self.get_geographic_data()
            vehicles = geo_data.get('vehicles', [])
            
            if not vehicles:
                return ""
            
            # Group vehicles by transport type
            transport_groups = {}
            for vehicle in vehicles:
                transport_type = vehicle['transport_type']
                if transport_type not in transport_groups:
                    transport_groups[transport_type] = []
                transport_groups[transport_type].append(vehicle)
            
            fig = go.Figure()
            
            colors = {
                'suburban': '#0066cc',
                'subway': '#003d82',
                'ring': '#ff6b35',
                'tram': '#00a86b',
                'bus': '#dc2626',
                'ferry': '#8b5cf6',
                'regional': '#ff8c00',
                'express': '#dc143c'
            }
            
            for transport_type, vehicles_group in transport_groups.items():
                lats = [v['lat'] for v in vehicles_group]
                lons = [v['lng'] for v in vehicles_group]
                
                fig.add_trace(go.Scattermapbox(
                    lat=lats,
                    lon=lons,
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=colors.get(transport_type, '#888888'),
                        opacity=0.7
                    ),
                    name=transport_type.title(),
                    text=[f"{v['line_name']} - {v['sector']}" for v in vehicles_group],
                    hovertemplate='<b>%{text}</b><br>Type: ' + transport_type + '<extra></extra>'
                ))
            
            fig.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    center=dict(lat=52.52, lon=13.405),
                    zoom=10
                ),
                margin=dict(l=0, r=0, t=40, b=0),
                height=500,
                title='Live Vehicle Distribution Across Berlin',
                title_font_color='white',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                showlegend=True,
                legend=dict(
                    bgcolor='rgba(0,0,0,0.8)',
                    bordercolor='rgba(255,255,255,0.2)',
                    borderwidth=1
                )
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating heat density chart: {e}")
            return ""
    
    def get_system_performance_insights(self) -> Dict[str, Any]:
        """Get advanced system performance insights and trends"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Calculate system performance metrics
            cursor.execute("""
                WITH recent_data AS (
                    SELECT 
                        DATE_TRUNC('hour', timestamp) as hour,
                        COUNT(*) as records_per_hour,
                        COUNT(DISTINCT vehicle_id) as unique_vehicles_per_hour,
                        AVG(CASE WHEN delay_minutes > 0 THEN delay_minutes ELSE NULL END) as avg_delay_per_hour
                    FROM vehicle_positions 
                    WHERE timestamp >= NOW() - INTERVAL '24 hours'
                    GROUP BY hour
                    ORDER BY hour
                ),
                performance_stats AS (
                    SELECT 
                        AVG(records_per_hour) as avg_collection_rate,
                        STDDEV(records_per_hour) as collection_rate_variance,
                        MAX(records_per_hour) as peak_collection_rate,
                        MIN(records_per_hour) as min_collection_rate,
                        AVG(unique_vehicles_per_hour) as avg_unique_vehicles,
                        AVG(avg_delay_per_hour) as system_avg_delay
                    FROM recent_data
                )
                SELECT * FROM performance_stats
            """)
            
            performance_row = cursor.fetchone()
            if performance_row:
                performance_metrics = {
                    'avg_collection_rate': round(performance_row[0] or 0, 1),
                    'collection_rate_variance': round(performance_row[1] or 0, 1),
                    'peak_collection_rate': performance_row[2] or 0,
                    'min_collection_rate': performance_row[3] or 0,
                    'avg_unique_vehicles': round(performance_row[4] or 0, 1),
                    'system_avg_delay': round(performance_row[5] or 0, 2)
                }
            else:
                performance_metrics = {}
            
            # Get sector efficiency rankings
            cursor.execute("""
                SELECT 
                    raw_data->>'sector' as sector,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT vehicle_id) as unique_vehicles,
                    ROUND(COUNT(*)::numeric / COUNT(DISTINCT vehicle_id), 2) as records_per_vehicle,
                    AVG(delay_minutes) as avg_delay
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '2 hours'
                  AND raw_data->>'sector' IS NOT NULL
                GROUP BY raw_data->>'sector'
                ORDER BY total_records DESC
            """)
            
            sector_efficiency = []
            for row in cursor.fetchall():
                sector_efficiency.append({
                    'sector': row[0],
                    'total_records': row[1],
                    'unique_vehicles': row[2],
                    'records_per_vehicle': float(row[3]),
                    'avg_delay': round(row[4] or 0, 1),
                    'efficiency_score': round((row[1] / max(row[2], 1)) * 100, 1)
                })
            
            # Get transport type performance comparison with better delay calculation
            cursor.execute("""
                SELECT 
                    transport_type,
                    COUNT(*) as total_records,
                    COUNT(DISTINCT vehicle_id) as unique_vehicles,
                    AVG(CASE WHEN delay_minutes > 0 THEN delay_minutes ELSE NULL END) as avg_delay,
                    ROUND((COUNT(CASE WHEN delay_minutes > 0 THEN 1 END)::numeric / GREATEST(COUNT(*), 1)) * 100, 1) as delay_percentage,
                    COUNT(CASE WHEN delay_minutes > 0 THEN 1 END) as delayed_vehicles
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '2 hours'
                GROUP BY transport_type
                ORDER BY total_records DESC
            """)
            
            transport_performance = []
            for row in cursor.fetchall():
                transport_performance.append({
                    'type': row[0],
                    'total_records': row[1],
                    'unique_vehicles': row[2],
                    'avg_delay': round(row[3] or 0, 1),
                    'delay_percentage': float(row[4] or 0),
                    'delayed_vehicles': row[5]
                })
            
            return {
                'performance_metrics': performance_metrics,
                'sector_efficiency': sector_efficiency,
                'transport_performance': transport_performance
            }
            
        except Exception as e:
            print(f"Error getting system performance insights: {e}")
            return {'performance_metrics': {}, 'sector_efficiency': [], 'transport_performance': []}
    
    def get_route_coverage_data(self) -> Dict[str, Any]:
        """Get route coverage analysis for heat map visualization"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    transport_type,
                    line_name,
                    COUNT(*) as data_points,
                    COUNT(DISTINCT vehicle_id) as unique_vehicles,
                    MAX(timestamp) as latest_data,
                    MIN(timestamp) as earliest_data,
                    CASE 
                        WHEN COUNT(*) > 100 THEN 'High'
                        WHEN COUNT(*) > 50 THEN 'Medium'
                        ELSE 'Low'
                    END as coverage_level
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '2 hours'
                GROUP BY transport_type, line_name
                ORDER BY data_points DESC
            """)
            
            route_coverage = []
            for row in cursor.fetchall():
                route_coverage.append({
                    'transport_type': row[0],
                    'line_name': row[1],
                    'data_points': row[2],
                    'unique_vehicles': row[3],
                    'latest_data': row[4],
                    'earliest_data': row[5],
                    'coverage_level': row[6]
                })
            
            return {'route_coverage': route_coverage}
            
        except Exception as e:
            print(f"Error getting route coverage data: {e}")
            return {'route_coverage': []}
    
    def get_time_series_reliability(self) -> Dict[str, Any]:
        """Get 7-day delay trends by transport type"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', timestamp) as day,
                    transport_type,
                    AVG(CASE WHEN delay_minutes > 0 THEN delay_minutes ELSE NULL END) as avg_delay,
                    COUNT(CASE WHEN delay_minutes > 0 THEN 1 END) as delayed_count,
                    COUNT(*) as total_records,
                    ROUND((COUNT(CASE WHEN delay_minutes > 0 THEN 1 END)::numeric / COUNT(*)) * 100, 1) as delay_rate
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('day', timestamp), transport_type
                ORDER BY day DESC, transport_type
            """)
            
            reliability_data = []
            for row in cursor.fetchall():
                reliability_data.append({
                    'day': row[0],
                    'transport_type': row[1],
                    'avg_delay': round(row[2] or 0, 1),
                    'delayed_count': row[3],
                    'total_records': row[4],
                    'delay_rate': float(row[5] or 0)
                })
            
            return {'reliability_data': reliability_data}
            
        except Exception as e:
            print(f"Error getting time series reliability: {e}")
            return {'reliability_data': []}
    
    def get_data_quality_score(self) -> Dict[str, Any]:
        """Calculate real-time data quality score"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Calculate freshness score (0-100)
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '5 minutes' THEN 1 END) as very_fresh,
                    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '15 minutes' THEN 1 END) as fresh,
                    COUNT(*) as total
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """)
            freshness_row = cursor.fetchone()
            if freshness_row and freshness_row[2] > 0:
                freshness_score = min(100, (freshness_row[1] / freshness_row[2]) * 100)
            else:
                freshness_score = 0
            
            # Calculate completeness score (0-100)
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN route_id IS NOT NULL THEN 1 END) as has_route,
                    COUNT(CASE WHEN line_name IS NOT NULL THEN 1 END) as has_line,
                    COUNT(CASE WHEN direction IS NOT NULL THEN 1 END) as has_direction,
                    COUNT(*) as total
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """)
            completeness_row = cursor.fetchone()
            if completeness_row and completeness_row[3] > 0:
                completeness_score = ((completeness_row[0] + completeness_row[1] + completeness_row[2]) / (completeness_row[3] * 3)) * 100
            else:
                completeness_score = 0
            
            # Calculate accuracy score (0-100) - based on reasonable coordinates
            cursor.execute("""
                SELECT 
                    COUNT(CASE 
                        WHEN latitude BETWEEN 52.3 AND 52.7 
                        AND longitude BETWEEN 13.0 AND 13.8 THEN 1 
                    END) as valid_coords,
                    COUNT(*) as total
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """)
            accuracy_row = cursor.fetchone()
            if accuracy_row and accuracy_row[1] > 0:
                accuracy_score = (accuracy_row[0] / accuracy_row[1]) * 100
            else:
                accuracy_score = 0
            
            # Calculate overall score
            overall_score = (freshness_score + completeness_score + accuracy_score) / 3
            
            # Determine status
            if overall_score >= 85:
                status = 'excellent'
                status_color = '#10b981'
            elif overall_score >= 70:
                status = 'good' 
                status_color = '#10b981'
            elif overall_score >= 50:
                status = 'fair'
                status_color = '#f59e0b'
            else:
                status = 'poor'
                status_color = '#ef4444'
            
            return {
                'freshness_score': round(freshness_score, 1),
                'completeness_score': round(completeness_score, 1),
                'accuracy_score': round(accuracy_score, 1),
                'overall_score': round(overall_score, 1),
                'status': status,
                'status_color': status_color
            }
            
        except Exception as e:
            print(f"Error calculating data quality score: {e}")
            return {
                'freshness_score': 0,
                'completeness_score': 0,
                'accuracy_score': 0,
                'overall_score': 0,
                'status': 'unknown',
                'status_color': '#6b7280'
            }
    
    def get_recent_vehicle_data(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent vehicle position data for table display"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    timestamp,
                    vehicle_id,
                    transport_type,
                    line_name,
                    direction,
                    latitude,
                    longitude,
                    delay_minutes,
                    status
                FROM vehicle_positions 
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
                ORDER BY timestamp DESC
                LIMIT %s
            """, (limit,))
            
            recent_data = []
            for row in cursor.fetchall():
                recent_data.append({
                    'timestamp': row[0].strftime('%H:%M:%S') if row[0] else '',
                    'vehicle_id': row[1] or '',
                    'transport_type': row[2] or '',
                    'line_name': row[3] or '',
                    'direction': row[4][:50] + '...' if row[4] and len(row[4]) > 50 else (row[4] or ''),
                    'latitude': round(row[5], 4) if row[5] else 0,
                    'longitude': round(row[6], 4) if row[6] else 0,
                    'delay_minutes': row[7] or 0,
                    'status': row[8] or 'active'
                })
            
            return recent_data
            
        except Exception as e:
            print(f"Error getting recent vehicle data: {e}")
            return []
    
    def create_route_coverage_chart(self) -> str:
        """Create route coverage heat map chart"""
        try:
            coverage_data = self.get_route_coverage_data()
            routes = coverage_data.get('route_coverage', [])
            
            if not routes:
                return ""
            
            # Group by transport type
            transport_groups = {}
            for route in routes:
                transport_type = route['transport_type']
                if transport_type not in transport_groups:
                    transport_groups[transport_type] = []
                transport_groups[transport_type].append(route)
            
            fig = go.Figure()
            
            for transport_type, route_group in transport_groups.items():
                route_names = [r['line_name'] for r in route_group]
                data_points = [r['data_points'] for r in route_group]
                
                fig.add_trace(go.Bar(
                    x=route_names,
                    y=data_points,
                    name=transport_type.title(),
                    text=[f"{r['unique_vehicles']} vehicles" for r in route_group],
                    textposition='auto'
                ))
            
            fig.update_layout(
                title='Route Data Coverage (Last 2 Hours)',
                xaxis_title='Route Lines',
                yaxis_title='Data Points Collected',
                template='plotly_dark',
                height=400,
                margin=dict(l=40, r=40, t=40, b=40),
                barmode='group'
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating route coverage chart: {e}")
            return ""
    
    def create_reliability_trends_chart(self) -> str:
        """Create 7-day reliability trends chart"""
        try:
            reliability_data = self.get_time_series_reliability()
            data = reliability_data.get('reliability_data', [])
            
            if not data:
                return ""
            
            # Group by transport type
            transport_groups = {}
            for item in data:
                transport_type = item['transport_type']
                if transport_type not in transport_groups:
                    transport_groups[transport_type] = {'days': [], 'delay_rates': []}
                transport_groups[transport_type]['days'].append(item['day'])
                transport_groups[transport_type]['delay_rates'].append(item['delay_rate'])
            
            fig = go.Figure()
            
            colors = {
                'suburban': '#0066cc',
                'subway': '#003d82',
                'ring': '#ff6b35',
                'tram': '#00a86b',
                'bus': '#dc2626'
            }
            
            for transport_type, group_data in transport_groups.items():
                fig.add_trace(go.Scatter(
                    x=group_data['days'],
                    y=group_data['delay_rates'],
                    mode='lines+markers',
                    name=transport_type.title(),
                    line=dict(color=colors.get(transport_type, '#888888'), width=3),
                    marker=dict(size=8)
                ))
            
            fig.update_layout(
                title='7-Day Delay Rate Trends',
                xaxis_title='Date',
                yaxis_title='Delay Rate (%)',
                template='plotly_dark',
                height=400,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating reliability trends chart: {e}")
            return ""
    
    def create_data_quality_gauge(self) -> str:
        """Create data quality score gauge"""
        try:
            quality_data = self.get_data_quality_score()
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = quality_data['overall_score'],
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Data Quality Score"},
                delta = {'reference': 85},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': quality_data['status_color']},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 85], 'color': "yellow"},
                        {'range': [85, 100], 'color': "lightgreen"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            
            fig.update_layout(
                template='plotly_dark',
                height=300,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            return plotly.utils.PlotlyJSONEncoder().encode(fig)
            
        except Exception as e:
            print(f"Error creating data quality gauge: {e}")
            return ""

# Global monitor instance
monitor = DataCollectionMonitor()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Enhanced dashboard page with detailed component monitoring"""
    try:
        # Get current data
        collectors = monitor.get_collection_status()
        statistics = monitor.get_data_statistics()
        sector_performance = monitor.get_sector_performance()
        collection_rates = monitor.get_collection_rates()
        api_health = monitor.get_api_health_metrics()
        geographic_data = monitor.get_geographic_data()
        performance_insights = monitor.get_system_performance_insights()
        
        # Get new advanced analytics data
        route_coverage = monitor.get_route_coverage_data()
        reliability_trends = monitor.get_time_series_reliability()
        recent_vehicle_data = monitor.get_recent_vehicle_data()
        
        # Create charts
        collection_chart = monitor.create_collection_chart()
        transport_chart = monitor.create_transport_breakdown_chart()
        sector_chart = monitor.create_sector_performance_chart()
        rate_chart = monitor.create_collection_rate_chart()
        heat_map = monitor.create_heat_density_chart()
        
        # Create new advanced analytics charts
        route_coverage_chart = monitor.create_route_coverage_chart()
        reliability_chart = monitor.create_reliability_trends_chart()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "collectors": collectors,
            "statistics": statistics,
            "sector_performance": sector_performance,
            "collection_rates": collection_rates,
            "api_health": api_health,
            "geographic_data": geographic_data,
            "performance_insights": performance_insights,
            "route_coverage": route_coverage,
            "reliability_trends": reliability_trends,
            "recent_vehicle_data": recent_vehicle_data,
            "collection_chart": collection_chart,
            "transport_chart": transport_chart,
            "sector_chart": sector_chart,
            "rate_chart": rate_chart,
            "heat_map": heat_map,
            "route_coverage_chart": route_coverage_chart,
            "reliability_chart": reliability_chart,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        print(f"Error rendering dashboard: {e}")
        return HTMLResponse(f"<h1>Error loading dashboard: {e}</h1>", status_code=500)

@app.get("/api/status")
async def api_status():
    """Enhanced API endpoint for collection status"""
    try:
        collectors = monitor.get_collection_status()
        statistics = monitor.get_data_statistics()
        sector_performance = monitor.get_sector_performance()
        collection_rates = monitor.get_collection_rates()
        api_health = monitor.get_api_health_metrics()
        
        return {
            "collectors": collectors,
            "statistics": statistics,
            "sector_performance": sector_performance,
            "collection_rates": collection_rates,
            "api_health": api_health,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/sectors")
async def api_sectors():
    """API endpoint for sector performance data"""
    try:
        return monitor.get_sector_performance()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/rates")
async def api_rates():
    """API endpoint for collection rate data"""
    try:
        return monitor.get_collection_rates()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/quality")
async def api_quality():
    """API endpoint for data quality metrics"""
    try:
        return monitor.get_api_health_metrics()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/geographic")
async def api_geographic():
    """API endpoint for geographic vehicle distribution"""
    try:
        return monitor.get_geographic_data()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/insights")
async def api_insights():
    """API endpoint for system performance insights"""
    try:
        return monitor.get_system_performance_insights()
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = monitor.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# Create templates directory and template file
import os
os.makedirs("templates", exist_ok=True)

# Write the enhanced dashboard template with reorganized layout
dashboard_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Berlin Transport Data Collection Monitor</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #0a0a0f;
            color: #ffffff;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(124, 58, 237, 0.1));
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #00d4ff;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #94a3b8;
            font-size: 0.8rem;
        }
        .rate-indicator {
            font-size: 1rem;
            color: #10b981;
            margin-top: 5px;
        }
        .section-header {
            margin: 40px 0 20px 0;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            border-left: 4px solid #00d4ff;
            position: relative;
        }
        .section-description {
            font-size: 0.9rem;
            color: #94a3b8;
            margin-top: 8px;
            font-weight: normal;
        }
        .collectors-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .collector-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
        }
        .collector-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .collector-name {
            font-weight: bold;
            font-size: 1.1rem;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .status-healthy { background-color: #10b981; color: white; }
        .status-warning { background-color: #f59e0b; color: white; }
        .status-error { background-color: #ef4444; color: white; }
        .sectors-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .sector-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .sector-name {
            font-weight: bold;
            color: #00d4ff;
            margin-bottom: 10px;
            text-transform: capitalize;
        }
        .quality-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .quality-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
        }
        .quality-metric {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
        }
        .data-table {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            overflow-x: auto;
        }
        .data-table table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .data-table th,
        .data-table td {
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .data-table th {
            background: rgba(255, 255, 255, 0.1);
            font-weight: bold;
            color: #00d4ff;
        }
        .toggle-btn {
            background: rgba(0, 212, 255, 0.2);
            border: 1px solid #00d4ff;
            color: #00d4ff;
            padding: 5px 15px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            float: right;
            margin-top: -5px;
        }
        .collapsible-content {
            max-height: 400px;
            overflow-y: auto;
            transition: all 0.3s ease;
        }
        .collapsed {
            display: none;
        }
        .last-updated {
            text-align: center;
            color: #64748b;
            margin-top: 20px;
            font-size: 0.9rem;
        }
        .refresh-btn {
            background: linear-gradient(45deg, #00d4ff, #7c3aed);
            border: none;
            border-radius: 8px;
            color: white;
            padding: 10px 20px;
            cursor: pointer;
            margin: 10px;
        }
        .progress-bar {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            height: 8px;
            margin-top: 5px;
        }
        .progress-fill {
            background: linear-gradient(90deg, #10b981, #00d4ff);
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚊 Berlin Transport Data Collection Monitor</h1>
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
    </div>

    <!-- Enhanced Statistics Grid -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{{ statistics.vehicle_stats.total_positions or 0 }}</div>
            <div class="stat-label">Vehicle Positions (24h)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ statistics.vehicle_stats.unique_vehicles or 0 }}</div>
            <div class="stat-label">Unique Vehicles</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ collection_rates.current_rate or 0 }}</div>
            <div class="stat-label">Current Rate/Min</div>
            <div class="rate-indicator">Avg: {{ collection_rates.avg_rate_per_minute or 0 }}/min</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ sector_performance.sectors|length or 0 }}</div>
            <div class="stat-label">Active Sectors</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ statistics.departure_stats.total_departures or 0 }}</div>
            <div class="stat-label">Departure Events (24h)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ statistics.route_count or 0 }}</div>
            <div class="stat-label">Route Geometries</div>
        </div>
    </div>

    <!-- Advanced Analytics moved to TOP -->
    <h2 class="section-header">📈 Advanced Analytics</h2>
    
    <!-- Advanced Analytics Charts -->
    <div class="charts-grid">
        {% if route_coverage_chart %}
        <div class="chart-container">
            <div id="route-coverage-chart"></div>
        </div>
        {% endif %}
        
        {% if reliability_chart %}
        <div class="chart-container">
            <div id="reliability-chart"></div>
        </div>
        {% endif %}
        
        {% if sector_chart %}
        <div class="chart-container">
            <div id="sector-chart"></div>
        </div>
        {% endif %}
        
        {% if collection_chart %}
        <div class="chart-container">
            <div id="collection-chart"></div>
        </div>
        {% endif %}
        
        {% if transport_chart %}
        <div class="chart-container">
            <div id="transport-chart"></div>
        </div>
        {% endif %}

        {% if rate_chart %}
        <div class="chart-container">
            <div id="rate-chart"></div>
        </div>
        {% endif %}
    </div>

    <!-- Live Berlin Transport Map -->
    <h2 class="section-header">🗺️ Live Vehicle Distribution Across Berlin</h2>
    {% if heat_map %}
    <div class="chart-container">
        <div id="heat-map" style="height: 500px;"></div>
        <div style="margin-top: 10px; color: #94a3b8; font-size: 0.9rem;">
            🔴 Bus &nbsp;&nbsp; 🔵 S-Bahn &nbsp;&nbsp; 🟢 Tram &nbsp;&nbsp; 🟣 U-Bahn &nbsp;&nbsp; 🟠 Ring &nbsp;&nbsp;
            Showing {{ geographic_data.total_vehicles }} vehicles from last 10 minutes
        </div>
    </div>
    {% endif %}

    <!-- Transport Performance moved AFTER map -->
    <h2 class="section-header">
        🚌 Transport Type Performance
        <div class="section-description">Delay calculations based on vehicles with delay_minutes > 0. Zero values indicate either no delays or insufficient delay data in the current time window.</div>
    </h2>
    <div class="quality-grid">
        {% for transport in performance_insights.transport_performance %}
        <div class="quality-card">
            <div class="collector-name">{{ transport.type.title() }} Performance</div>
            <div class="quality-metric">
                <span>Total Records:</span>
                <span><strong>{{ transport.total_records }}</strong></span>
            </div>
            <div class="quality-metric">
                <span>Unique Vehicles:</span>
                <span>{{ transport.unique_vehicles }}</span>
            </div>
            <div class="quality-metric">
                <span>Delayed Vehicles:</span>
                <span>{{ transport.delayed_vehicles or 0 }}</span>
            </div>
            <div class="quality-metric">
                <span>Avg Delay:</span>
                <span>{{ transport.avg_delay }} min</span>
            </div>
            <div class="quality-metric">
                <span>Delay Rate:</span>
                <span>{{ transport.delay_percentage }}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {{ 100 - transport.delay_percentage }}%"></div>
            </div>
        </div>
        {% endfor %}
    </div>

    <!-- Data Quality Monitoring -->
    <h2 class="section-header">📊 Data Quality Metrics</h2>
    <div class="quality-grid">
        {% for transport_type, metrics in api_health.items() %}
        <div class="quality-card">
            <div class="collector-name">{{ transport_type.title() }}</div>
            <div class="quality-metric">
                <span>Records:</span>
                <span><strong>{{ metrics.total_records }}</strong></span>
            </div>
            <div class="quality-metric">
                <span>Route Data:</span>
                <span>{{ metrics.route_completeness }}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {{ metrics.route_completeness }}%"></div>
            </div>
            <div class="quality-metric">
                <span>Line Data:</span>
                <span>{{ metrics.line_completeness }}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {{ metrics.line_completeness }}%"></div>
            </div>
        </div>
        {% endfor %}
    </div>

    <!-- Dataset Table Display -->
    <h2 class="section-header">
        📊 Recent Dataset Sample (Last Hour)
        <button class="toggle-btn" onclick="toggleTable('dataset-table')">Toggle Table</button>
    </h2>
    <div id="dataset-table" class="data-table">
        <div class="collapsible-content">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Vehicle ID</th>
                        <th>Type</th>
                        <th>Line</th>
                        <th>Direction</th>
                        <th>Lat</th>
                        <th>Lng</th>
                        <th>Delay</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for vehicle in recent_vehicle_data[:25] %}
                    <tr>
                        <td>{{ vehicle.timestamp }}</td>
                        <td>{{ vehicle.vehicle_id }}</td>
                        <td>{{ vehicle.transport_type }}</td>
                        <td>{{ vehicle.line_name }}</td>
                        <td>{{ vehicle.direction }}</td>
                        <td>{{ vehicle.latitude }}</td>
                        <td>{{ vehicle.longitude }}</td>
                        <td>{{ vehicle.delay_minutes }}min</td>
                        <td>{{ vehicle.status }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <p style="text-align: center; color: #94a3b8; margin-top: 15px;">
                Showing 25 of {{ recent_vehicle_data|length }} recent records
            </p>
        </div>
    </div>

    <!-- Collection Status -->
    <h2 class="section-header">📊 Data Collection Status</h2>
    <div class="collectors-grid">
        {% for collector in collectors %}
        <div class="collector-card">
            <div class="collector-header">
                <div class="collector-name">{{ collector.collector_name.replace('_', ' ').title() }}</div>
                <div class="status-badge status-{{ collector.health }}">{{ collector.health.title() }}</div>
            </div>
            <div><strong>Status:</strong> {{ collector.status }}</div>
            <div><strong>Records Collected:</strong> {{ collector.records_collected or 0 }}</div>
            {% if collector.last_success_at %}
            <div><strong>Last Success:</strong> {{ collector.last_success_at.strftime('%H:%M:%S') }}</div>
            {% endif %}
            {% if collector.error_message %}
            <div style="color: #ef4444;"><strong>Error:</strong> {{ collector.error_message }}</div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <!-- Performance Insights -->
    <h2 class="section-header">📊 System Performance Insights</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{{ performance_insights.performance_metrics.avg_collection_rate or 0 }}</div>
            <div class="stat-label">Avg Records/Hour</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ performance_insights.performance_metrics.peak_collection_rate or 0 }}</div>
            <div class="stat-label">Peak Collection Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ performance_insights.performance_metrics.avg_unique_vehicles or 0 }}</div>
            <div class="stat-label">Avg Unique Vehicles/Hour</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{{ performance_insights.performance_metrics.collection_rate_variance or 0 }}</div>
            <div class="stat-label">Collection Variance</div>
        </div>
    </div>

    <!-- Sector Efficiency Rankings with explanation -->
    <h2 class="section-header">
        🏆 Sector Efficiency Rankings
        <div class="section-description">Efficiency Score = (Total Records / Unique Vehicles) × 100. Higher scores indicate more frequent data collection per vehicle in that sector, suggesting better tracking coverage.</div>
    </h2>
    <div class="sectors-grid">
        {% for sector in performance_insights.sector_efficiency %}
        <div class="sector-card">
            <div class="sector-name">{{ sector.sector.title() }}</div>
            <div><strong>{{ sector.total_records }}</strong> records</div>
            <div><small>{{ sector.unique_vehicles }} vehicles</small></div>
            <div style="margin-top: 8px;">
                <small>Efficiency: {{ sector.efficiency_score }}%</small>
            </div>
            <div style="margin-top: 5px;">
                <small>{{ sector.records_per_vehicle }} rec/vehicle</small>
            </div>
        </div>
        {% endfor %}
    </div>

    <!-- Berlin Sector Performance MOVED TO END -->
    <h2 class="section-header">🗺️ Berlin Sector Performance</h2>
    <div class="sectors-grid">
        {% for sector in sector_performance.sectors %}
        <div class="sector-card">
            <div class="sector-name">{{ sector.name }}</div>
            <div><strong>{{ sector.vehicle_count }}</strong> vehicles</div>
            <div><small>{{ sector.unique_vehicles }} unique</small></div>
            <div class="status-badge status-{{ sector.health }}" style="margin-top: 8px;">{{ sector.health.title() }}</div>
        </div>
        {% endfor %}
    </div>

    <div class="last-updated">
        Last updated: {{ last_updated }} | Auto-refresh in 2 minutes
    </div>

    <script>
        {% if route_coverage_chart %}
        var routeCoverageChart = {{ route_coverage_chart | safe }};
        Plotly.newPlot('route-coverage-chart', routeCoverageChart.data, routeCoverageChart.layout);
        {% endif %}
        
        {% if reliability_chart %}
        var reliabilityChart = {{ reliability_chart | safe }};
        Plotly.newPlot('reliability-chart', reliabilityChart.data, reliabilityChart.layout);
        {% endif %}
        
        {% if rate_chart %}
        var rateChart = {{ rate_chart | safe }};
        Plotly.newPlot('rate-chart', rateChart.data, rateChart.layout);
        {% endif %}
        
        {% if heat_map %}
        var heatMap = {{ heat_map | safe }};
        Plotly.newPlot('heat-map', heatMap.data, heatMap.layout, {responsive: true});
        {% endif %}
        
        {% if sector_chart %}
        var sectorChart = {{ sector_chart | safe }};
        Plotly.newPlot('sector-chart', sectorChart.data, sectorChart.layout);
        {% endif %}
        
        {% if collection_chart %}
        var collectionChart = {{ collection_chart | safe }};
        Plotly.newPlot('collection-chart', collectionChart.data, collectionChart.layout);
        {% endif %}
        
        {% if transport_chart %}
        var transportChart = {{ transport_chart | safe }};
        Plotly.newPlot('transport-chart', transportChart.data, transportChart.layout);
        {% endif %}
        
        // Toggle function for collapsible sections
        function toggleTable(tableId) {
            const content = document.querySelector(`#${tableId} .collapsible-content`);
            content.classList.toggle('collapsed');
        }
        
        // Auto-refresh every 2 minutes for real-time monitoring
        setTimeout(function() {
            location.reload();
        }, 120000);
    </script>
</body>
</html>
"""

with open("templates/dashboard.html", "w") as f:
    f.write(dashboard_template)

if __name__ == "__main__":
    uvicorn.run(
        "dashboard:app", 
        host="0.0.0.0", 
        port=8080, 
        reload=False,
        log_level="info"
    )