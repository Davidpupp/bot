#!/usr/bin/env python3
"""
Test alternative endpoints and API formats
"""
import asyncio
import httpx
import json

SILLIENTPAY_API_KEY = "sp_live_810a34a0a85860235def74a554f3af24"

async def test_pix_generation():
    """Test PIX generation with different payload formats"""
    print("=== Testing PIX Generation Formats ===\n")
    
    base_url = "https://api.sillientpay.com"
    
    # Different possible endpoints
    endpoints = [
        "/v1/pix",
        "/v1/qrcode",
        "/v1/pix/generate",
        "/pix/generate",
        "/pix",
        "/qrcode"
    ]
    
    # Different payload formats
    payloads = [
        {
            "amount": 10.00,
            "currency": "BRL",
            "orderId": "TEST_001",
            "paymentMethod": "pix",
            "customer": {"email": "test@example.com"}
        },
        {
            "value": 10.00,
            "orderId": "TEST_001",
            "type": "pix",
            "callbackUrl": "http://localhost:8002/webhook"
        },
        {
            "valor": 10.00,
            "pedido": "TEST_001",
            "metodo": "pix",
            "webhook": "http://localhost:8002/webhook"
        }
    ]
    
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for endpoint in endpoints:
        for i, payload in enumerate(payloads):
            print(f"Testing {endpoint} with format {i+1}")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(base_url + endpoint, headers=headers, json=payload)
                    print(f"  Status: {response.status_code}")
                    if response.status_code == 200:
                        data = response.json()
                        print(f"  SUCCESS! Response: {data}")
                        return data
                    else:
                        print(f"  Response: {response.text[:100]}")
            except Exception as e:
                print(f"  Error: {str(e)}")
            print()
    
    return None

async def test_api_key_validation():
    """Test if API key is valid"""
    print("=== Testing API Key Validation ===\n")
    
    # Try to access account info or similar
    test_endpoints = [
        "https://api.sillientpay.com/v1/account",
        "https://api.sillientpay.com/v1/me",
        "https://api.sillientpay.com/v1/balance",
        "https://sillientpay.com/api/v1/account"
    ]
    
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
    }
    
    for endpoint in test_endpoints:
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

async def test_webhook_format():
    """Test webhook endpoint format"""
    print("=== Testing Webhook Format ===\n")
    
    webhook_url = "http://localhost:8002/webhook/sillientpay"
    
    # Test different webhook formats
    test_payloads = [
        {
            "event": "payment.succeeded",
            "data": {
                "id": "test_payment_123",
                "status": "paid",
                "amount": 1000
            }
        },
        {
            "type": "payment",
            "status": "paid",
            "payment_id": "test_payment_123",
            "order_id": "TEST_001"
        },
        {
            "paymentId": "test_payment_123",
            "status": "paid",
            "orderId": "TEST_001",
            "amount": 10.00
        }
    ]
    
    for i, payload in enumerate(test_payloads):
        print(f"Testing webhook format {i+1}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)
                print(f"  Status: {response.status_code}")
                print(f"  Response: {response.json()}")
        except Exception as e:
            print(f"  Error: {str(e)}")
        print()

async def main():
    """Run all tests"""
    print("Testing SillientPay API with different formats...\n")
    
    # Test 1: API Key validation
    api_valid = await test_api_key_validation()
    
    # Test 2: PIX generation
    pix_data = await test_pix_generation()
    
    # Test 3: Webhook formats
    await test_webhook_format()
    
    print("\n=== Summary ===")
    print(f"API Key Valid: {api_valid}")
    print(f"PIX Generation: {'Working' if pix_data else 'Not Working'}")
    print("Webhook Handler: Ready")
    
    if not api_valid and not pix_data:
        print("\n=== RECOMMENDATION ===")
        print("1. Check if SillientPay API key is correct")
        print("2. Verify SillientPay account is active")
        print("3. Check SillientPay documentation for correct endpoint")
        print("4. Consider using Mercado Pago as alternative")

if __name__ == "__main__":
    asyncio.run(main())
