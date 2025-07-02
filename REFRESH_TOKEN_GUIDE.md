# JWT Refresh Token System Guide

## Overview

This implementation provides a secure JWT authentication system with access and refresh tokens.

## How It Works

### 1. **Token Types**
- **Access Token**: Short-lived (30 minutes by default) for API access
- **Refresh Token**: Long-lived (7 days by default) for getting new access tokens

### 2. **Token Claims**
Both tokens include:
- `sub`: Username
- `exp`: Expiration time
- `type`: Token type ("access" or "refresh")

### 3. **Security Features**
- Access tokens can only be used for API access
- Refresh tokens can only be used to get new access tokens
- Tokens are validated for correct type before use

## API Endpoints

### Login
```bash
POST /login
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Refresh Token
```bash
POST /refresh
Content-Type: application/json

{
  "refresh_token": "your_refresh_token_here"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "message": "Token refreshed successfully"
}
```

### Protected Route
```bash
GET /protected
Authorization: Bearer your_access_token_here
```

## Usage Examples

### 1. Manual Testing with curl

```bash
# Register
curl -X PUT "http://localhost:8000/register" \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "email": "test@example.com", "password": "password123"}'

# Login
curl -X POST "http://localhost:8000/login" \
     -d "username=testuser&password=password123"

# Use access token
curl -X GET "http://localhost:8000/protected" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Refresh token
curl -X POST "http://localhost:8000/refresh" \
     -H "Content-Type: application/json" \
     -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

### 2. Using the Test Script

```bash
python test_token_usage.py
```

## Environment Variables

```bash
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Security Notes

1. **Access tokens** should be short-lived (15-60 minutes)
2. **Refresh tokens** should be long-lived (days/weeks)
3. **Store refresh tokens securely** in production (database with revocation capability)
4. **Use HTTPS** in production
5. **Rotate refresh tokens** periodically

## Production Considerations

For a production system, consider:
- Storing refresh tokens in a database
- Adding token revocation capability
- Implementing refresh token rotation
- Adding rate limiting
- Using separate secrets for access and refresh tokens 