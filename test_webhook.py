#!/usr/bin/env python3
"""
Test script for webhook handlers
"""
import asyncio
import httpx
import json
from datetime import datetime

# Test data
WEBHOOK_URL = "http://localhost:8002"

async def test_webhook_endpoints():
    """Test all webhook endpoints"""
    async with httpx.AsyncClient() as client:
        print("=== Testing Webhook Endpoints ===\n")
        
        # Test 1: GET root
        print("1. Testing GET /")
        try:
            response = await client.get(f"{WEBHOOK_URL}/")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
        
        # Test 2: GET health
        print("2. Testing GET /health")
        try:
            response = await client.get(f"{WEBHOOK_URL}/health")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
        
        # Test 3: GET webhook/sillientpay
        print("3. Testing GET /webhook/sillientpay")
        try:
            response = await client.get(f"{WEBHOOK_URL}/webhook/sillientpay")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
        
        # Test 4: POST root with payment data
        print("4. Testing POST / with payment data")
        payload = {
            "orderId": "123",
            "status": "paid",
            "id": "pay_123"
        }
        try:
            response = await client.post(f"{WEBHOOK_URL}/", json=payload)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
        
        # Test 5: POST webhook/sillientpay with event
        print("5. Testing POST /webhook/sillientpay with payment.succeeded")
        payload = {
            "event": "payment.succeeded",
            "data": {
                "id": "pay_456"
            }
        }
        try:
            response = await client.post(f"{WEBHOOK_URL}/webhook/sillientpay", json=payload)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
        
        # Test 6: PUT webhook/sillientpay
        print("6. Testing PUT /webhook/sillientpay")
        payload = {
            "event": "payment.succeeded",
            "data": {
                "id": "pay_789"
            }
        }
        try:
            response = await client.put(f"{WEBHOOK_URL}/webhook/sillientpay", json=payload)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()
        
        # Test 7: PATCH webhook/sillientpay
        print("7. Testing PATCH /webhook/sillientpay")
        payload = {
            "event": "payment.succeeded",
            "data": {
                "id": "pay_101112"
            }
        }
        try:
            response = await client.patch(f"{WEBHOOK_URL}/webhook/sillientpay", json=payload)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        print()

if __name__ == "__main__":
    asyncio.run(test_webhook_endpoints())
