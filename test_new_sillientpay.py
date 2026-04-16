#!/usr/bin/env python3
"""
Test new SillientPay API key
"""
import asyncio
import httpx
import json
from datetime import datetime

SILLIENTPAY_API_KEY = "sp_live_9d7549047175ed6618bc55a0e72c338d"
SILLIENTPAY_WEBHOOK_SECRET = "sk_7eda4b706278a1b0a1fae032795a16bfb7b1e7a8847dc8ee3e32fca8d0b96942"

async def test_new_api_key():
    """Test the new SillientPay API key"""
    print("=== Testing New SillientPay API Key ===\n")
    
    # Test different endpoints with new key
    endpoints = [
        "https://api.sillientpay.com/v1/payments",
        "https://api.sillientpay.com/v1/pix",
        "https://api.sillientpay.com/v1/transactions",
        "https://sillientpay.com/api/v1/payments"
    ]
    
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Webhook-Secret": SILLIENTPAY_WEBHOOK_SECRET
    }
    
    payload = {
        "amount": 1000,
        "currency": "BRL",
        "orderId": f"TEST_{datetime.now().timestamp()}",
        "paymentMethod": "pix",
        "webhookUrl": "http://localhost:8002/webhook/sillientpay",
        "customer": {
            "email": "test@example.com"
        }
    }
    
    for endpoint in endpoints:
        print(f"Testing: {endpoint}")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                print(f"  Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"  SUCCESS! Payment ID: {data.get('id')}")
                    print(f"  Status: {data.get('status')}")
                    return data
                elif response.status_code == 401:
                    print(f"  Unauthorized - API key may be invalid")
                elif response.status_code == 404:
                    print(f"  Endpoint not found")
                else:
                    print(f"  Response: {response.text[:200]}")
                    
        except Exception as e:
            print(f"  Error: {str(e)}")
        print()
    
    return None

async def test_account_info():
    """Test account info endpoint"""
    print("=== Testing Account Info ===\n")
    
    endpoints = [
        "https://api.sillientpay.com/v1/account",
        "https://api.sillientpay.com/v1/me",
        "https://sillientpay.com/api/v1/account"
    ]
    
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
        "X-Webhook-Secret": SILLIENTPAY_WEBHOOK_SECRET
    }
    
    for endpoint in endpoints:
        print(f"Testing: {endpoint}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=headers)
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"  Account data: {data}")
                    return True
                else:
                    print(f"  Response: {response.text[:100]}")
        except Exception as e:
            print(f"  Error: {str(e)}")
        print()
    
    return False

async def main():
    """Run tests with new API key"""
    from datetime import datetime
    
    print("Testing new SillientPay configuration...\n")
    
    # Test account info
    account_ok = await test_account_info()
    
    # Test payment creation
    payment_data = await test_new_api_key()
    
    print("\n=== Results ===")
    print(f"Account Access: {'Working' if account_ok else 'Failed'}")
    print(f"Payment Creation: {'Working' if payment_data else 'Failed'}")
    
    if payment_data:
        print(f"\nPayment Details:")
        print(f"ID: {payment_data.get('id')}")
        print(f"Status: {payment_data.get('status')}")
        print(f"Amount: {payment_data.get('amount')}")
        
        # Check for PIX data
        if 'qrCode' in payment_data:
            print(f"QR Code: Present")
        if 'brCode' in payment_data:
            print(f"BR Code: Present")
    
    print("\nBot is ready with new configuration!")

if __name__ == "__main__":
    asyncio.run(main())
