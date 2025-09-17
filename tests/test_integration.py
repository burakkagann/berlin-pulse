#!/usr/bin/env python3
"""
Berlin Transport Time Machine - Integration Test Script
Tests the complete Phase 2 implementation
"""

import asyncio
import httpx
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

API_BASE_URL = "http://localhost:8081/api/v1"
FRONTEND_URL = "http://localhost:3000"

class IntegrationTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = {}
        self.start_time = time.time()
        
    async def run_all_tests(self):
        """Run comprehensive integration tests"""
        print("🧪 Starting Berlin Transport Time Machine Integration Tests")
        print("=" * 60)
        
        # Test API health and data availability
        await self.test_api_health()
        await self.test_data_availability()
        
        # Test core simulation endpoints
        await self.test_time_range_endpoint()
        await self.test_vehicle_positions_endpoint()
        await self.test_simulation_chunk_endpoint()
        
        # Test transport information endpoints
        await self.test_routes_endpoint()
        await self.test_stops_endpoint()
        
        # Test performance with realistic data loads
        await self.test_performance_scenarios()
        
        # Test error handling
        await self.test_error_scenarios()
        
        # Generate test report
        self.generate_test_report()
        
    async def test_api_health(self):
        """Test API health endpoints"""
        print("\n🏥 Testing API Health...")
        
        try:
            # Basic health check
            response = await self.client.get(f"{API_BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            self.test_results["api_health"] = "✅ PASS"
            
            # Database health check
            response = await self.client.get(f"{API_BASE_URL}/health/database")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            self.test_results["database_health"] = "✅ PASS"
            
            # Data health check
            response = await self.client.get(f"{API_BASE_URL}/health/data")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]
            self.test_results["data_health"] = "✅ PASS"
            
            print("✅ API health checks passed")
            
        except Exception as e:
            print(f"❌ API health check failed: {e}")
            self.test_results["api_health"] = f"❌ FAIL: {e}"
    
    async def test_data_availability(self):
        """Test data availability and quality"""
        print("\n📊 Testing Data Availability...")
        
        try:
            # Get time range
            response = await self.client.get(f"{API_BASE_URL}/simulation/time-range")
            assert response.status_code == 200
            time_range = response.json()
            
            # Validate time range data
            assert "start_time" in time_range
            assert "end_time" in time_range
            assert "total_records" in time_range
            assert time_range["total_records"] > 0
            
            # Check duration is reasonable (should have multiple hours of data)
            assert time_range["total_duration_hours"] > 1
            
            # Check transport types are available
            assert len(time_range["transport_types_available"]) >= 4
            
            print(f"✅ Data available: {time_range['total_records']:,} records over {time_range['total_duration_hours']:.1f} hours")
            print(f"   Transport types: {', '.join(time_range['transport_types_available'])}")
            
            self.test_results["data_availability"] = "✅ PASS"
            self.time_range = time_range
            
        except Exception as e:
            print(f"❌ Data availability test failed: {e}")
            self.test_results["data_availability"] = f"❌ FAIL: {e}"
    
    async def test_time_range_endpoint(self):
        """Test time range endpoint performance and accuracy"""
        print("\n⏰ Testing Time Range Endpoint...")
        
        try:
            start_time = time.time()
            response = await self.client.get(f"{API_BASE_URL}/simulation/time-range")
            response_time = (time.time() - start_time) * 1000
            
            assert response.status_code == 200
            data = response.json()
            
            # Validate response structure
            required_fields = ["start_time", "end_time", "total_duration_hours", "total_records", "transport_types_available"]
            for field in required_fields:
                assert field in data, f"Missing field: {field}"
            
            # Performance check
            assert response_time < 1000, f"Response too slow: {response_time:.1f}ms"
            
            print(f"✅ Time range endpoint: {response_time:.1f}ms response time")
            self.test_results["time_range_endpoint"] = "✅ PASS"
            
        except Exception as e:
            print(f"❌ Time range endpoint failed: {e}")
            self.test_results["time_range_endpoint"] = f"❌ FAIL: {e}"
    
    async def test_vehicle_positions_endpoint(self):
        """Test vehicle positions endpoint with various parameters"""
        print("\n🚗 Testing Vehicle Positions Endpoint...")
        
        try:
            # Test with current time
            if hasattr(self, 'time_range'):
                start_time = datetime.fromisoformat(self.time_range["start_time"].replace('Z', '+00:00'))
                test_time = start_time + timedelta(hours=2)  # 2 hours into the data
                
                # Test basic request
                params = {
                    "timestamp": test_time.isoformat(),
                    "time_window_seconds": 60
                }
                
                start_time = time.time()
                response = await self.client.get(f"{API_BASE_URL}/simulation/vehicles", params=params)
                response_time = (time.time() - start_time) * 1000
                
                assert response.status_code == 200
                data = response.json()
                
                # Validate response structure
                assert "vehicles" in data
                assert "total_vehicles" in data
                assert "transport_type_counts" in data
                assert isinstance(data["vehicles"], list)
                
                # Should have some vehicles during normal hours
                assert data["total_vehicles"] > 0, "No vehicles found"
                
                # Validate vehicle data structure
                if data["vehicles"]:
                    vehicle = data["vehicles"][0]
                    required_fields = ["vehicle_id", "transport_type", "latitude", "longitude", "timestamp"]
                    for field in required_fields:
                        assert field in vehicle, f"Missing vehicle field: {field}"
                
                # Performance check
                assert response_time < 2000, f"Response too slow: {response_time:.1f}ms"
                
                print(f"✅ Vehicle positions: {data['total_vehicles']} vehicles, {response_time:.1f}ms")
                self.test_results["vehicle_positions"] = "✅ PASS"
                
        except Exception as e:
            print(f"❌ Vehicle positions test failed: {e}")
            self.test_results["vehicle_positions"] = f"❌ FAIL: {e}"
    
    async def test_simulation_chunk_endpoint(self):
        """Test simulation chunk endpoint for animation data"""
        print("\n🎬 Testing Simulation Chunk Endpoint...")
        
        try:
            if hasattr(self, 'time_range'):
                start_time = datetime.fromisoformat(self.time_range["start_time"].replace('Z', '+00:00'))
                test_time = start_time + timedelta(hours=1)
                
                params = {
                    "start_time": test_time.isoformat(),
                    "duration_minutes": 10,
                    "frame_interval_seconds": 30
                }
                
                start_time = time.time()
                response = await self.client.get(f"{API_BASE_URL}/simulation/data-chunk", params=params)
                response_time = (time.time() - start_time) * 1000
                
                assert response.status_code == 200
                data = response.json()
                
                # Validate response structure
                required_fields = ["start_time", "end_time", "duration_seconds", "vehicles", "total_vehicles", "frame_count"]
                for field in required_fields:
                    assert field in data, f"Missing field: {field}"
                
                # Should have reasonable amount of data
                assert data["total_vehicles"] > 0, "No vehicles in chunk"
                assert data["frame_count"] > 0, "No frames in chunk"
                
                # Performance check for chunk loading
                assert response_time < 5000, f"Chunk loading too slow: {response_time:.1f}ms"
                
                print(f"✅ Simulation chunk: {data['total_vehicles']} vehicles, {data['frame_count']} frames, {response_time:.1f}ms")
                self.test_results["simulation_chunk"] = "✅ PASS"
                
        except Exception as e:
            print(f"❌ Simulation chunk test failed: {e}")
            self.test_results["simulation_chunk"] = f"❌ FAIL: {e}"
    
    async def test_routes_endpoint(self):
        """Test routes information endpoint"""
        print("\n🛤️ Testing Routes Endpoint...")
        
        try:
            start_time = time.time()
            response = await self.client.get(f"{API_BASE_URL}/routes")
            response_time = (time.time() - start_time) * 1000
            
            assert response.status_code == 200
            routes = response.json()
            
            assert isinstance(routes, list)
            assert len(routes) > 0, "No routes found"
            
            # Validate route structure
            if routes:
                route = routes[0]
                required_fields = ["route_id", "line_name", "transport_type", "color"]
                for field in required_fields:
                    assert field in route, f"Missing route field: {field}"
            
            print(f"✅ Routes: {len(routes)} routes loaded, {response_time:.1f}ms")
            self.test_results["routes"] = "✅ PASS"
            
        except Exception as e:
            print(f"❌ Routes test failed: {e}")
            self.test_results["routes"] = f"❌ FAIL: {e}"
    
    async def test_stops_endpoint(self):
        """Test stops information endpoint"""
        print("\n🚏 Testing Stops Endpoint...")
        
        try:
            start_time = time.time()
            response = await self.client.get(f"{API_BASE_URL}/stops")
            response_time = (time.time() - start_time) * 1000
            
            assert response.status_code == 200
            stops = response.json()
            
            assert isinstance(stops, list)
            assert len(stops) > 0, "No stops found"
            
            # Validate stop structure
            if stops:
                stop = stops[0]
                required_fields = ["stop_id", "stop_name", "latitude", "longitude", "is_tracked"]
                for field in required_fields:
                    assert field in stop, f"Missing stop field: {field}"
            
            print(f"✅ Stops: {len(stops)} stops loaded, {response_time:.1f}ms")
            self.test_results["stops"] = "✅ PASS"
            
        except Exception as e:
            print(f"❌ Stops test failed: {e}")
            self.test_results["stops"] = f"❌ FAIL: {e}"
    
    async def test_performance_scenarios(self):
        """Test performance under realistic load scenarios"""
        print("\n⚡ Testing Performance Scenarios...")
        
        try:
            # Test 1: Large chunk request (simulate 1 hour of data)
            if hasattr(self, 'time_range'):
                start_time = datetime.fromisoformat(self.time_range["start_time"].replace('Z', '+00:00'))
                test_time = start_time + timedelta(hours=2)
                
                params = {
                    "start_time": test_time.isoformat(),
                    "duration_minutes": 60,  # 1 hour chunk
                    "frame_interval_seconds": 30
                }
                
                start_time = time.time()
                response = await self.client.get(f"{API_BASE_URL}/simulation/data-chunk", params=params)
                response_time = (time.time() - start_time) * 1000
                
                assert response.status_code == 200
                data = response.json()
                
                # Should handle large requests reasonably well
                assert response_time < 10000, f"Large chunk too slow: {response_time:.1f}ms"
                
                print(f"✅ Large chunk (1h): {data.get('total_vehicles', 0)} vehicles, {response_time:.1f}ms")
                
            # Test 2: Multiple concurrent requests
            tasks = []
            for i in range(5):
                task = self.client.get(f"{API_BASE_URL}/simulation/time-range")
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks)
            total_time = (time.time() - start_time) * 1000
            
            # All requests should succeed
            for response in responses:
                assert response.status_code == 200
            
            print(f"✅ Concurrent requests: 5 requests in {total_time:.1f}ms")
            
            self.test_results["performance"] = "✅ PASS"
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            self.test_results["performance"] = f"❌ FAIL: {e}"
    
    async def test_error_scenarios(self):
        """Test error handling and edge cases"""
        print("\n🚨 Testing Error Scenarios...")
        
        try:
            # Test 1: Invalid timestamp
            response = await self.client.get(f"{API_BASE_URL}/simulation/vehicles", 
                                           params={"timestamp": "invalid-timestamp"})
            assert response.status_code == 422  # Validation error
            
            # Test 2: Future timestamp (outside data range)
            future_time = datetime.now() + timedelta(days=1)
            response = await self.client.get(f"{API_BASE_URL}/simulation/vehicles",
                                           params={"timestamp": future_time.isoformat()})
            # Should return empty result, not error
            assert response.status_code == 200
            
            # Test 3: Invalid route ID
            response = await self.client.get(f"{API_BASE_URL}/routes/nonexistent-route/geometry")
            assert response.status_code == 404
            
            # Test 4: Invalid parameters
            response = await self.client.get(f"{API_BASE_URL}/simulation/data-chunk",
                                           params={"start_time": "invalid", "duration_minutes": -1})
            assert response.status_code == 422
            
            print("✅ Error scenarios handled correctly")
            self.test_results["error_handling"] = "✅ PASS"
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            self.test_results["error_handling"] = f"❌ FAIL: {e}"
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("📋 INTEGRATION TEST REPORT")
        print("=" * 60)
        
        total_time = time.time() - self.start_time
        passed = sum(1 for result in self.test_results.values() if result.startswith("✅"))
        total = len(self.test_results)
        
        print(f"Test Duration: {total_time:.1f} seconds")
        print(f"Tests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        print("\nDetailed Results:")
        print("-" * 40)
        for test_name, result in self.test_results.items():
            print(f"{test_name:<25}: {result}")
        
        # Overall assessment
        if passed == total:
            print("\n🎉 ALL TESTS PASSED - Phase 2 implementation is ready!")
            print("\nNext Steps:")
            print("1. Frontend is available at: http://localhost:3000")
            print("2. API documentation at: http://localhost:8081/docs")
            print("3. Ready for user testing and feedback")
        else:
            print(f"\n⚠️ {total - passed} tests failed - review and fix issues")
        
        print("\n" + "=" * 60)
    
    async def cleanup(self):
        """Clean up test resources"""
        await self.client.aclose()

async def main():
    """Run integration tests"""
    tester = IntegrationTester()
    try:
        await tester.run_all_tests()
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())