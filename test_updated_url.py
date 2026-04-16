#!/usr/bin/env python3
"""
Test updated SillientPay URL
"""
import asyncio
import httpx

SILLIENTPAY_API_KEY = "sp_live_9d7549047175ed6618bc55a0e72c338d"

async def test_updated_url():
    """Test the updated SillientPay URL"""
    print("=== Testing Updated SillientPay URL ===\n")
    
    url = "https://sillientpay.com/api/v1/payments"
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
    print(f"API Key: {SILLIENTPAY_API_KEY[:20]}...")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Payment created:")
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
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
    
    return None

async def main():
    """Test the updated URL"""
    result = await test_updated_url()
    
    if result:
        print("\n=== PAYMENT WORKING! ===")
        print("SillientPay integration is functional!")
        print("Bot can now create real PIX payments!")
    else:
        print("\n=== Still not working ===")
        print("Try other URLs or check SillientPay documentation")

if __name__ == "__main__":
    asyncio.run(main())
