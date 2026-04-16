#!/usr/bin/env python3
"""
Test script for PIX QR code generation and copy-paste extraction
"""
import base64
from typing import Optional, Tuple

def extract_pix_info(payment_data: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract PIX QR code and copy-paste info from payment response"""
    qr_base64 = (
        payment_data.get("qrCode")
        or payment_data.get("qr_code_base64")
        or payment_data.get("qrCodeBase64")
        or payment_data.get("point_of_interaction", {})
        .get("transaction_data", {})
        .get("qr_code_base64")
    )

    copy_paste = (
        payment_data.get("brCode")
        or payment_data.get("br_code")
        or payment_data.get("copyPaste")
        or payment_data.get("copy_paste")
        or payment_data.get("copiaECola")
        or payment_data.get("pixCopyPaste")
        or payment_data.get("point_of_interaction", {})
        .get("transaction_data", {})
        .get("qr_code")
    )

    if isinstance(qr_base64, dict):
        qr_base64 = None
    if isinstance(copy_paste, dict):
        copy_paste = None

    return qr_base64, copy_paste

def test_pix_extraction():
    """Test PIX info extraction from various response formats"""
    print("=== Testing PIX Information Extraction ===\n")
    
    # Test 1: SillientPay format
    print("1. Testing SillientPay format:")
    sillientpay_response = {
        "id": "pay_12345",
        "amount": 1000,
        "currency": "BRL",
        "qrCode": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        "brCode": "00020126580014BR.GOV.BCB.PIX013612345678904012345678904012345678904520400005303986540610.005802BR5915JOAO SILVA SA6009SAO PAULO62070503***6304E2CA",
        "status": "pending"
    }
    
    qr, copy = extract_pix_info(sillientpay_response)
    print(f"   QR Code extracted: {'Yes' if qr else 'No'}")
    print(f"   Copy-paste extracted: {'Yes' if copy else 'No'}")
    print(f"   Copy-paste length: {len(copy) if copy else 0}")
    print()
    
    # Test 2: Mercado Pago format
    print("2. Testing Mercado Pago format:")
    mercadopago_response = {
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
    
    qr, copy = extract_pix_info(mercadopago_response)
    print(f"   QR Code extracted: {'Yes' if qr else 'No'}")
    print(f"   Copy-paste extracted: {'Yes' if copy else 'No'}")
    print(f"   Copy-paste length: {len(copy) if copy else 0}")
    print()
    
    # Test 3: Alternative field names
    print("3. Testing alternative field names:")
    alt_response = {
        "payment_id": "pay_alt_123",
        "qr_code_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        "copy_paste": "00020126580014BR.GOV.BCB.PIX013612345678904012345678904012345678904520400005303986540610.005802BR5915JOAO SILVA SA6009SAO PAULO62070503***6304E2CA",
        "status": "created"
    }
    
    qr, copy = extract_pix_info(alt_response)
    print(f"   QR Code extracted: {'Yes' if qr else 'No'}")
    print(f"   Copy-paste extracted: {'Yes' if copy else 'No'}")
    print()
    
    # Test 4: Missing PIX data
    print("4. Testing missing PIX data:")
    empty_response = {
        "id": "pay_empty",
        "status": "created",
        "amount": 1000
    }
    
    qr, copy = extract_pix_info(empty_response)
    print(f"   QR Code extracted: {'Yes' if qr else 'No'}")
    print(f"   Copy-paste extracted: {'Yes' if copy else 'No'}")
    print()
    
    # Test 5: Invalid base64
    print("5. Testing invalid base64:")
    invalid_response = {
        "qrCode": "not_a_valid_base64_string",
        "brCode": "valid_copy_paste_code_here"
    }
    
    qr, copy = extract_pix_info(invalid_response)
    print(f"   QR Code extracted: {'Yes' if qr else 'No'}")
    print(f"   Copy-paste extracted: {'Yes' if copy else 'No'}")
    print()

def test_qr_decoding():
    """Test QR code base64 decoding"""
    print("=== Testing QR Code Decoding ===\n")
    
    # Valid base64 for a 1x1 transparent PNG
    valid_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    print("1. Testing valid base64 decoding:")
    try:
        qr_bytes = base64.b64decode(valid_base64)
        print(f"   Decoded successfully: {len(qr_bytes)} bytes")
        print(f"   PNG signature: {qr_bytes[:8].hex()}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    print("2. Testing invalid base64:")
    try:
        qr_bytes = base64.b64decode("invalid_base64")
        print(f"   Decoded: {len(qr_bytes)} bytes")
    except Exception as e:
        print(f"   Error (expected): {e}")
    print()

def test_pix_copy_paste_format():
    """Test PIX copy-paste format validation"""
    print("=== Testing PIX Copy-Paste Format ===\n")
    
    # Valid PIX copy-paste format (simplified)
    valid_pix = "00020126580014BR.GOV.BCB.PIX013612345678904012345678904012345678904520400005303986540610.005802BR5915JOAO SILVA SA6009SAO PAULO62070503***6304E2CA"
    
    print("1. Valid PIX copy-paste:")
    print(f"   Length: {len(valid_pix)}")
    print(f"   Starts with '000201': {valid_pix.startswith('000201')}")
    print(f"   Contains 'BR.GOV.BCB.PIX': {'BR.GOV.BCB.PIX' in valid_pix}")
    print()
    
    # Invalid formats
    invalid_pix_samples = [
        "just_a_random_string",
        "123",
        "000201missing_parts",
        ""
    ]
    
    for i, invalid in enumerate(invalid_pix_samples, 2):
        print(f"{i}. Invalid PIX sample {i-1}:")
        print(f"   Length: {len(invalid)}")
        print(f"   Valid format: {invalid.startswith('000201') and 'BR.GOV.BCB.PIX' in invalid}")
        print()

def simulate_payment_responses():
    """Simulate different payment gateway responses"""
    print("=== Simulating Payment Gateway Responses ===\n")
    
    # Simulate SillientPay success response
    print("1. SillientPay Success Response:")
    sillientpay_success = {
        "id": "sp_123456",
        "status": "pending",
        "amount": 1000,
        "currency": "BRL",
        "orderId": "123",
        "qrCode": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        "brCode": "00020126580014BR.GOV.BCB.PIX013612345678904012345678904012345678904520400005303986540610.005802BR5915JOAO SILVA SA6009SAO PAULO62070503***6304E2CA",
        "expiresAt": "2026-04-16T04:00:00Z"
    }
    
    qr, copy = extract_pix_info(sillientpay_success)
    print(f"   Payment ID: {sillientpay_success['id']}")
    print(f"   Status: {sillientpay_success['status']}")
    print(f"   QR Code: {'Present' if qr else 'Missing'}")
    print(f"   Copy-paste: {'Present' if copy else 'Missing'}")
    print()
    
    # Simulate Mercado Pago success response
    print("2. Mercado Pago Success Response:")
    mercadopago_success = {
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
    
    qr, copy = extract_pix_info(mercadopago_success)
    print(f"   Payment ID: {mercadopago_success['id']}")
    print(f"   Status: {mercadopago_success['status']}")
    print(f"   QR Code: {'Present' if qr else 'Missing'}")
    print(f"   Copy-paste: {'Present' if copy else 'Missing'}")
    print()
    
    # Simulate error response
    print("3. Error Response:")
    error_response = {
        "error": "Payment gateway unavailable",
        "code": "GATEWAY_ERROR",
        "message": "Unable to process payment at this time"
    }
    
    qr, copy = extract_pix_info(error_response)
    print(f"   Error: {error_response['error']}")
    print(f"   QR Code: {'Present' if qr else 'Missing'}")
    print(f"   Copy-paste: {'Present' if copy else 'Missing'}")
    print()

if __name__ == "__main__":
    test_pix_extraction()
    test_qr_decoding()
    test_pix_copy_paste_format()
    simulate_payment_responses()
    print("=== PIX extraction tests completed ===")
