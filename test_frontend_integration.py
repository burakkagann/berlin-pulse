#!/usr/bin/env python3
"""
Frontend Integration Test Script
Tests the complete frontend-to-backend integration after fixing 404 errors
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
import time

class FrontendIntegrationTest:
    def __init__(self):
        self.api_base = "http://localhost:8081/api/v1"
        self.frontend_base = "http://localhost:8082"
        self.test_results = []
        
    async def run_all_tests(self):
        """Run all integration tests"""
        print("🧪 Starting Frontend Integration Tests")
        print("=" * 50)
        
        async with aiohttp.ClientSession() as session:
            # Test API connectivity
            await self.test_api_health(session)
            await self.test_time_range_api(session)
            await self.test_vehicle_data_api(session)
            await self.test_transport_types_api(session)
            
            # Test frontend resources
            await self.test_frontend_html(session)
            await self.test_frontend_js_files(session)
            await self.test_frontend_css_files(session)
            
        # Print summary
        self.print_summary()
        
    async def test_api_health(self, session):
        """Test API health endpoints"""
        test_name = "API Health Check"
        try:
            async with session.get(f"{self.api_base}/health", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    self.add_result(test_name, True, f"API healthy: {data.get('status')}")
                else:
                    self.add_result(test_name, False, f"HTTP {response.status}")
        except Exception as e:
            self.add_result(test_name, False, str(e))
    
    async def test_time_range_api(self, session):
        """Test time range API"""
        test_name = "Time Range API"
        try:
            async with session.get(f"{self.api_base}/simulation/time-range", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    start_time = data.get('start_time')
                    end_time = data.get('end_time')
                    total_records = data.get('total_records', 0)
                    
                    if start_time and end_time and total_records > 0:
                        self.add_result(test_name, True, f"{total_records} records from {start_time[:10]} to {end_time[:10]}")
                    else:
                        self.add_result(test_name, False, "Invalid data structure")
                else:
                    self.add_result(test_name, False, f"HTTP {response.status}")
        except Exception as e:
            self.add_result(test_name, False, str(e))
    
    async def test_vehicle_data_api(self, session):
        """Test vehicle data API with a sample timestamp"""
        test_name = "Vehicle Data API"
        try:
            # Use a timestamp that should have data
            test_timestamp = "2025-09-16T12:00:00Z"
            params = {
                'timestamp': test_timestamp,
                'time_window_seconds': 300,
                'transport_types': ['bus', 'tram', 'subway']
            }
            
            url = f"{self.api_base}/simulation/vehicles"
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    vehicles = data.get('vehicles', [])
                    timestamp = data.get('timestamp')
                    
                    if len(vehicles) > 0:
                        self.add_result(test_name, True, f"{len(vehicles)} vehicles at {timestamp}")
                    else:
                        self.add_result(test_name, False, "No vehicles found")
                else:
                    self.add_result(test_name, False, f"HTTP {response.status}")
        except Exception as e:
            self.add_result(test_name, False, str(e))
    
    async def test_transport_types_api(self, session):
        """Test transport types API"""
        test_name = "Transport Types API"
        try:
            async with session.get(f"{self.api_base}/transport-types", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    transport_types = data.get('transport_types', {})
                    
                    if len(transport_types) >= 5:  # Expect at least 5 transport types
                        types_list = list(transport_types.keys())
                        self.add_result(test_name, True, f"{len(transport_types)} types: {', '.join(types_list[:3])}...")
                    else:
                        self.add_result(test_name, False, f"Only {len(transport_types)} transport types found")
                else:
                    self.add_result(test_name, False, f"HTTP {response.status}")
        except Exception as e:
            self.add_result(test_name, False, str(e))
    
    async def test_frontend_html(self, session):
        """Test frontend HTML loading"""
        test_name = "Frontend HTML"
        try:
            async with session.get(f"{self.frontend_base}/", timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    if "Berlin Transport Time Machine" in content:
                        self.add_result(test_name, True, "HTML loads with correct title")
                    else:
                        self.add_result(test_name, False, "HTML missing expected content")
                else:
                    self.add_result(test_name, False, f"HTTP {response.status}")
        except Exception as e:
            self.add_result(test_name, False, str(e))
    
    async def test_frontend_js_files(self, session):
        """Test that previously missing JS files are now accessible"""
        test_name = "Frontend JavaScript Files"
        js_files = [
            "/js/services/data-service.js",
            "/js/components/timeline-scrubber.js", 
            "/js/controllers/time-controller.js"
        ]
        
        success_count = 0
        total_files = len(js_files)
        
        for js_file in js_files:
            try:
                async with session.get(f"{self.frontend_base}{js_file}", timeout=5) as response:
                    if response.status == 200:
                        success_count += 1
            except Exception:
                pass
        
        if success_count == total_files:
            self.add_result(test_name, True, f"All {total_files} JS files accessible")
        else:
            self.add_result(test_name, False, f"Only {success_count}/{total_files} JS files accessible")
    
    async def test_frontend_css_files(self, session):
        """Test frontend CSS files"""
        test_name = "Frontend CSS Files"
        css_files = [
            "/css/main.css",
            "/css/map.css",
            "/css/controls.css"
        ]
        
        success_count = 0
        total_files = len(css_files)
        
        for css_file in css_files:
            try:
                async with session.get(f"{self.frontend_base}{css_file}", timeout=5) as response:
                    if response.status == 200:
                        success_count += 1
            except Exception:
                pass
        
        if success_count == total_files:
            self.add_result(test_name, True, f"All {total_files} CSS files accessible")
        else:
            self.add_result(test_name, False, f"Only {success_count}/{total_files} CSS files accessible")
    
    def add_result(self, test_name, success, message):
        """Add test result"""
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
    
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "=" * 50)
        print("🧪 Integration Test Summary")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  • {result['test']}: {result['message']}")
        
        print("\n" + "=" * 50)

async def main():
    """Main test execution"""
    tester = FrontendIntegrationTest()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())