#!/usr/bin/env python3
"""
Test different SillientPay API endpoints
"""
import asyncio
import httpx
import json

SILLIENTPAY_API_KEY = "sp_live_810a34a0a85860235def74a554f3af24"

async def test_sillientpay_endpoints():
    """Test different possible endpoints for SillientPay"""
    print("=== Testing SillientPay API Endpoints ===\n")
    
    endpoints_to_test = [
        "https://api.sillientpay.com/v1/payments",
        "https://api.sillientpay.com/v1/payment",
        "https://api.sillientpay.com/payments",
        "https://sillientpay.com/api/v1/payments",
        "https://sillientpay.com/api/payments"
    ]
    
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": 1000,
        "currency": "BRL",
        "orderId": "TEST_001",
        "paymentMethod": "pix",
        "customer": {
            "email": "test@example.com"
        }
    }
    
    for endpoint in endpoints_to_test:
        print(f"Testing: {endpoint}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"  Success! Payment ID: {data.get('id')}")
                    return data
                else:
                    print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"  Error: {str(e)}")
        print()
    
    return None

async def test_get_endpoints():
    """Test GET endpoints to check API status"""
    print("=== Testing GET Endpoints ===\n")
    
    get_endpoints = [
        "https://api.sillientpay.com/v1/",
        "https://api.sillientpay.com/v1/health",
        "https://api.sillientpay.com/",
        "https://sillientpay.com/api/v1/"
    ]
    
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
    }
    
    for endpoint in get_endpoints:
        print(f"Testing GET: {endpoint}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=headers)
                print(f"  Status: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"  Error: {str(e)}")
        print()

async def main():
    """Run all endpoint tests"""
    await test_get_endpoints()
    payment_data = await test_sillientpay_endpoints()
    
    if payment_data:
        print("\n=== SUCCESS ===")
        print("Found working endpoint!")
        print(f"Payment ID: {payment_data.get('id')}")
    else:
        print("\n=== NO WORKING ENDPOINT FOUND ===")
        print("Please check SillientPay documentation for correct endpoint")

if __name__ == "__main__":
    asyncio.run(main())
