#!/usr/bin/env python3
"""
Test script to verify rate limiting works
"""
import requests
import time
import json

# Test configuration
API_URL = "http://127.0.0.1:5000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdHVkZW50X2lkIjoiMTIzNDUiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoiVGVzdCBVc2VyIiwiZXhwIjoxNzYwNDEyMjc2LCJpYXQiOjE3NjAzMjU4NzZ9.W8D8XsWOfGwfSB2Zv29dxw2pNt5Nasf7PHcynvTM-Wg"

def test_rate_limit():
    """Test rate limiting by sending multiple rapid requests"""
    print("🧪 Testing rate limiting...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }
    
    # Send 5 rapid requests
    for i in range(5):
        print(f"\n📤 Request {i+1}/5")
        try:
            response = requests.post(
                f"{API_URL}/api/chat",
                headers=headers,
                json={"message": f"Test message {i+1}"},
                timeout=10
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 429:
                print("🚦 Rate limit hit! ✅")
                data = response.json()
                print(f"Error message: {data.get('error', 'No error message')}")
                break
            elif response.status_code == 200:
                data = response.json()
                print(f"✅ Success: {data.get('reply', 'No reply')[:50]}...")
            else:
                print(f"❌ Unexpected status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        
        # Small delay between requests
        time.sleep(0.5)
    
    print("\n🏁 Rate limit test completed!")

if __name__ == "__main__":
    test_rate_limit()

