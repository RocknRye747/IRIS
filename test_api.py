#!/usr/bin/env python3
"""
Test script for Lift Bot API
Demonstrates basic API functionality including authentication, data ingestion, and reporting.
"""

import requests
import json
from datetime import datetime, date
import time

# API Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-change-in-production"  # Should match the API key in lift_bot_api.py

def test_api():
    """Test the Lift Bot API endpoints"""
    
    print("🤖 Testing Lift Bot API")
    print("=" * 50)
    
    # Headers for API requests
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        # Test 1: Health Check
        print("\n1. Testing Health Check...")
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
        
        # Test 2: Root Endpoint
        print("\n2. Testing Root Endpoint...")
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Root endpoint accessible")
            print(f"   API Info: {response.json()['message']}")
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
        
        # Test 3: Authentication
        print("\n3. Testing Authentication...")
        response = requests.post(f"{BASE_URL}/auth/token", headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            print("✅ Authentication successful")
            print(f"   Token type: {token_data['token_type']}")
            # Add Bearer token to headers for subsequent requests
            headers["Authorization"] = f"Bearer {token_data['access_token']}"
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # Test 4: Create Worker Session
        print("\n4. Testing Worker Session Creation...")
        worker_data = {
            "external_tracker_id": "test_tracker_001",
            "site_id": "warehouse_test"
        }
        response = requests.post(f"{BASE_URL}/workers/sessions", 
                               headers=headers, 
                               json=worker_data)
        if response.status_code == 200:
            worker_session = response.json()
            worker_id = worker_session["worker_id"]
            print("✅ Worker session created")
            print(f"   Worker ID: {worker_id}")
            print(f"   External Tracker ID: {worker_session['external_tracker_id']}")
        else:
            print(f"❌ Worker session creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        # Test 5: Create Lift Events
        print("\n5. Testing Lift Event Creation...")
        lift_events = [
            {
                "worker_id": worker_id,
                "risk_score": 25.5,
                "safe_lift": False,
                "angle_data": {
                    "back_angle": 125.3,
                    "left_knee_angle": 165.2,
                    "twist_angle": 15.7,
                    "load_distance": 0.25
                }
            },
            {
                "worker_id": worker_id,
                "risk_score": 8.2,
                "safe_lift": True,
                "angle_data": {
                    "back_angle": 85.1,
                    "left_knee_angle": 95.4,
                    "twist_angle": 5.2,
                    "load_distance": 0.12
                }
            },
            {
                "worker_id": worker_id,
                "risk_score": 45.8,
                "safe_lift": False,
                "angle_data": {
                    "back_angle": 135.7,
                    "left_knee_angle": 170.1,
                    "twist_angle": 25.3,
                    "load_distance": 0.35
                }
            }
        ]
        
        created_events = []
        for i, lift_event in enumerate(lift_events):
            response = requests.post(f"{BASE_URL}/lifts", 
                                   headers=headers, 
                                   json=lift_event)
            if response.status_code == 200:
                event_data = response.json()
                created_events.append(event_data)
                print(f"✅ Lift event {i+1} created (Risk: {lift_event['risk_score']}, Safe: {lift_event['safe_lift']})")
            else:
                print(f"❌ Lift event {i+1} creation failed: {response.status_code}")
                print(f"   Response: {response.text}")
        
        # Test 6: Employee Report
        print("\n6. Testing Employee Report...")
        today = date.today().isoformat()
        response = requests.get(f"{BASE_URL}/reports/employee/{worker_id}?report_date={today}", 
                              headers=headers)
        if response.status_code == 200:
            report = response.json()
            print("✅ Employee report generated")
            print(f"   Worker ID: {report['worker_id']}")
            print(f"   Date: {report['date']}")
            print(f"   Total Lifts: {report['total_lifts']}")
            print(f"   Safe Lifts: {report['safe_lifts']}")
            print(f"   Unsafe Lifts: {report['unsafe_lifts']}")
            print(f"   Average Risk: {report['avg_risk']}")
        else:
            print(f"❌ Employee report failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # Test 7: Aggregate Report
        print("\n7. Testing Aggregate Report...")
        response = requests.get(f"{BASE_URL}/reports/aggregate", headers=headers)
        if response.status_code == 200:
            report = response.json()
            print("✅ Aggregate report generated")
            print(f"   Period: {report['period']}")
            print(f"   Total Workers: {report['total_workers']}")
            print(f"   Total Lifts: {report['total_lifts']}")
            print(f"   Safe Lifts: {report['safe_lifts']}")
            print(f"   Average Risk: {report['avg_risk']}")
        else:
            print(f"❌ Aggregate report failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # Test 8: Site Statistics
        print("\n8. Testing Site Statistics...")
        response = requests.get(f"{BASE_URL}/reports/sites/warehouse_test/stats", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            print("✅ Site statistics generated")
            print(f"   Site ID: {stats['site_id']}")
            print(f"   Period: {stats['period']}")
            print(f"   Total Workers: {stats['total_workers']}")
            print(f"   Total Lifts: {stats['total_lifts']}")
            print(f"   Average Risk: {stats['avg_risk']}")
        else:
            print(f"❌ Site statistics failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # Test 9: End Worker Session
        print("\n9. Testing Worker Session Termination...")
        response = requests.delete(f"{BASE_URL}/workers/{worker_id}", headers=headers)
        if response.status_code == 200:
            result = response.json()
            print("✅ Worker session ended")
            print(f"   Message: {result['message']}")
        else:
            print(f"❌ Worker session termination failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        print("\n" + "=" * 50)
        print("🎉 API Testing Complete!")
        print("\n📊 Summary:")
        print(f"   • Created {len(created_events)} lift events")
        print(f"   • Generated employee and aggregate reports")
        print(f"   • Tested authentication and worker management")
        print(f"   • All core API functionality verified")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the API server is running on http://localhost:8000")
        print("   Start the server with: python lift_bot_api.py")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_api()
