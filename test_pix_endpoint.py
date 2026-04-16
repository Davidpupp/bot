#!/usr/bin/env python3
"""
Test the new PIX endpoint
"""
import asyncio
import httpx

SILLIENTPAY_API_KEY = "sp_live_9d7549047175ed6618bc55a0e72c338d"

async def test_pix_endpoint():
    """Test the PIX endpoint"""
    print("=== Testing PIX Endpoint ===\n")
    
    url = "https://api.sillientpay.com/v1/pix"
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": 1000,
        "currency": "BRL",
        "orderId": "TEST_ORDER_001",
        "paymentMethod": "pix",
        "webhookUrl": "http://localhost:8002/webhook/sillientpay",
        "customer": {
            "email": "test@example.com"
        }
    }
    
    print(f"Testing URL: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! PIX created:")
                print(f"Payment ID: {data.get('id')}")
                print(f"Status: {data.get('status')}")
                print(f"Amount: {data.get('amount')}")
                
                # Check for PIX data
                if 'qrCode' in data:
                    print(f"QR Code: Present")
                if 'brCode' in data:
                    print(f"BR Code: Present")
                    
                return data
            else:
                print(f"Response: {response.text[:200]}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
    
    return None

async def main():
    """Test the PIX endpoint"""
    result = await test_pix_endpoint()
    
    if result:
        print("\n=== PIX ENDPOINT WORKING! ===")
        print("SillientPay PIX integration is functional!")
        print("Bot can now create real PIX payments!")
    else:
        print("\n=== Still not working ===")
        print("The PIX endpoint also returned 404")
        print("Bot will continue working in simulation mode")

if __name__ == "__main__":
    asyncio.run(main())
