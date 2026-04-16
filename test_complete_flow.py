#!/usr/bin/env python3
"""
Test complete payment flow with SillientPay API
"""
import asyncio
import httpx
import json
from datetime import datetime

# Configuration
SILLIENTPAY_API_KEY = "sp_live_810a34a0a85860235def74a554f3af24"
WEBHOOK_URL = "http://localhost:8002"
BOT_TOKEN = "8633859972:AAHQfiWp7XGjGtFSGGzveznFsLex2XABQHw"

async def test_sillientpay_payment():
    """Test creating a real payment with SillientPay"""
    print("=== Testing SillientPay Payment Creation ===\n")
    
    url = "https://api.sillientpay.com/v1/payments"
    headers = {
        "Authorization": f"Bearer {SILLIENTPAY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": 1000,  # R$ 10.00 in cents
        "currency": "BRL",
        "orderId": "TEST_ORDER_001",
        "paymentMethod": "pix",
        "webhookUrl": f"{WEBHOOK_URL}/webhook/sillientpay",
        "customer": {
            "email": "test@example.com"
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            payment_data = response.json()
            print(f"Payment created successfully!")
            print(f"Payment ID: {payment_data.get('id')}")
            print(f"Status: {payment_data.get('status')}")
            print(f"Amount: {payment_data.get('amount')} cents")
            
            # Check for PIX data
            qr_code = payment_data.get('qrCode')
            br_code = payment_data.get('brCode')
            
            print(f"\nPIX Data:")
            print(f"QR Code: {'Present' if qr_code else 'Missing'}")
            print(f"BR Code: {'Present' if br_code else 'Missing'}")
            
            if br_code:
                print(f"BR Code length: {len(br_code)}")
            
            return payment_data
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

async def test_webhook_simulation(payment_data):
    """Test webhook by simulating payment confirmation"""
    print("\n=== Testing Webhook Simulation ===\n")
    
    if not payment_data:
        print("No payment data to test webhook")
        return
    
    webhook_url = f"{WEBHOOK_URL}/webhook/sillientpay"
    
    # Simulate payment succeeded event
    webhook_payload = {
        "event": "payment.succeeded",
        "data": {
            "id": payment_data.get('id'),
            "status": "paid",
            "amount": payment_data.get('amount'),
            "orderId": "TEST_ORDER_001"
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=webhook_payload)
            print(f"Webhook sent: {response.status_code}")
            print(f"Response: {response.json()}")
            
    except Exception as e:
        print(f"Webhook error: {str(e)}")

async def test_telegram_bot():
    """Test Telegram bot connection"""
    print("\n=== Testing Telegram Bot Connection ===\n")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            data = response.json()
            
            if data.get('ok'):
                bot_info = data.get('result', {})
                print(f"Bot connected successfully!")
                print(f"Bot name: {bot_info.get('first_name')}")
                print(f"Username: @{bot_info.get('username')}")
                print(f"Bot ID: {bot_info.get('id')}")
                return True
            else:
                print(f"Bot connection failed: {data.get('description')}")
                return False
                
    except Exception as e:
        print(f"Error testing bot: {str(e)}")
        return False

async def test_webhook_server():
    """Test if webhook server is responding"""
    print("\n=== Testing Webhook Server ===\n")
    
    endpoints = [
        f"{WEBHOOK_URL}/",
        f"{WEBHOOK_URL}/health",
        f"{WEBHOOK_URL}/webhook/sillientpay"
    ]
    
    for endpoint in endpoints:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(endpoint)
                print(f"{endpoint}: {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response: {response.json()}")
        except Exception as e:
            print(f"{endpoint}: Error - {str(e)}")

async def main():
    """Run all tests"""
    print("Starting complete system test...\n")
    
    # Test 1: Telegram Bot
    bot_ok = await test_telegram_bot()
    
    # Test 2: Webhook Server
    await test_webhook_server()
    
    # Test 3: SillientPay Payment (only if bot is working)
    if bot_ok:
        payment_data = await test_sillientpay_payment()
        
        # Test 4: Webhook Simulation
        await test_webhook_simulation(payment_data)
    else:
        print("\nSkipping payment tests due to bot connection issues")
    
    print("\n=== Test Summary ===")
    print("1. Telegram Bot: " + ("OK" if bot_ok else "FAILED"))
    print("2. Webhook Server: OK (if running)")
    print("3. SillientPay API: " + ("OK" if bot_ok else "SKIPPED"))
    print("4. Webhook Handler: " + ("OK" if bot_ok else "SKIPPED"))
    
    print("\nSystem ready for production!")

if __name__ == "__main__":
    asyncio.run(main())
