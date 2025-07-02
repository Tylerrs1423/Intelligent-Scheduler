#!/usr/bin/env python3
"""
Setup script for AI Foco API.
This script helps you set up the environment variables and get started.
"""

import secrets
import string
import os

def generate_secret_key(length=64):
    """Generate a random secret key."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def main():
    print("🚀 Setting up AI Foco API...\n")
    
    # Check if .env already exists
    if os.path.exists('.env'):
        print("⚠️  .env file already exists. Do you want to overwrite it? (y/n): ", end="")
        response = input().lower().strip()
        if response != 'y':
            print("❌ Setup cancelled.")
            return
    
    # Generate secret key
    secret_key = generate_secret_key(64)
    
    # Create .env content
    env_content = f"""# AI Foco API Environment Variables
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
"""
    
    # Write .env file
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Environment setup completed!")
    print(f"🔑 Secret key generated: {secret_key[:20]}...")
    
    print("\n📋 Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the application: uvicorn app.main:app --reload")
    print("3. Open http://localhost:8000/docs in your browser")
    print("4. Test the API: python test_token_usage.py")
    
    print("\n🎯 API Endpoints:")
    print("   • Register: PUT /users/register")
    print("   • Login: POST /users/login")
    print("   • Refresh: POST /users/refresh")
    print("   • Protected: GET /protected/")
    print("   • Health: GET /health")
    
    print("\n📚 Documentation:")
    print("   • Swagger UI: http://localhost:8000/docs")
    print("   • ReDoc: http://localhost:8000/redoc")
    print("   • README: README.md")

if __name__ == "__main__":
    main() 