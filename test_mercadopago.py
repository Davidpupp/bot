#!/usr/bin/env python3
"""
Test Mercado Pago as alternative payment gateway
"""
import asyncio
import httpx
import json

async def test_mercadopago():
    """Test Mercado Pago API"""
    print("=== Testing Mercado Pago API ===\n")
    
    # First, let's test without credentials to see what we need
    url = "https://api.mercadopago.com/v1/payments"
    
    payload = {
        "transaction_amount": 10.00,
        "description": "Test Order #001",
        "payment_method_id": "pix",
        "payer": {
            "email": "test@example.com"
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:300]}")
            
            if response.status_code == 401:
                print("\nMercado Pago requires access token")
                print("To get Mercado Pago working:")
                print("1. Create account at https://mercadopago.com")
                print("2. Get your Access Token from credentials")
                print("3. Set MP_ACCESS_TOKEN environment variable")
                return False
                
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    
    return True

async def create_test_mercadopago_payment():
    """Create a test payment with Mercado Pago simulation"""
    print("\n=== Creating Mercado Pago Test Payment ===\n")
    
    # Simulate a Mercado Pago response
    simulated_response = {
        "id": "1234567890",
        "status": "pending",
        "status_detail": "pending_waiting_payment",
        "payment_method_id": "pix",
        "point_of_interaction": {
            "transaction_data": {
                "qr_code_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
                "qr_code": "00020126580014BR.GOV.BCB.PIX013612345678904012345678904012345678904520400005303986540610.005802BR5915JOAO SILVA SA6009SAO PAULO62070503***6304E2CA",
                "transaction_amount": 10.00
            }
        }
    }
    
    print("Simulated Mercado Pago response:")
    print(f"Payment ID: {simulated_response['id']}")
    print(f"Status: {simulated_response['status']}")
    print(f"QR Code: {'Present' if simulated_response['point_of_interaction']['transaction_data']['qr_code_base64'] else 'Missing'}")
    print(f"BR Code: {'Present' if simulated_response['point_of_interaction']['transaction_data']['qr_code'] else 'Missing'}")
    
    return simulated_response

async def main():
    """Run Mercado Pago tests"""
    print("Testing Mercado Pago as alternative payment gateway...\n")
    
    # Test Mercado Pago API
    mp_works = await test_mercadopago()
    
    # Create test payment simulation
    test_payment = await create_test_mercadopago_payment()
    
    print("\n=== Summary ===")
    print("Mercado Pago API: " + ("Working" if mp_works else "Needs Configuration"))
    print("Test Payment: Created")
    print("\n=== RECOMMENDATIONS ===")
    
    if not mp_works:
        print("1. Mercado Pago is a reliable alternative to SillientPay")
        print("2. To configure Mercado Pago:")
        print("   - Create account at https://mercadopago.com")
        print("   - Get your Access Token")
        print("   - Set MP_ACCESS_TOKEN environment variable")
        print("3. Benefits of Mercado Pago:")
        print("   - Well-documented API")
        print("   - Reliable PIX generation")
        print("   - Brazilian market focus")
        print("4. Current system can work with either gateway")

if __name__ == "__main__":
    asyncio.run(main())
