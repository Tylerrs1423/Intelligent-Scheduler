# AI Foco API

A FastAPI application with JWT authentication and refresh tokens, organized in a modular structure.

## Project Structure

```
ai_foco/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic models
│   ├── database.py      # DB connection + session
│   ├── auth.py          # All auth logic: create tokens, verify, refresh
│   └── routes/
│       ├── __init__.py
│       ├── users.py      # Registration, login routes
│       └── protected.py  # Protected route example
├── .env
├── requirements.txt
└── README.md
```

## Features

- ✅ JWT Authentication with access and refresh tokens
- ✅ User registration and login
- ✅ Protected routes requiring authentication
- ✅ Token refresh functionality
- ✅ Modular code structure
- ✅ SQLAlchemy ORM with SQLite
- ✅ Pydantic validation
- ✅ FastAPI automatic documentation

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory:

```bash
SECRET_KEY=your-secret-key-here-make-it-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 3. Run the Application

```bash
uvicorn app.main:app --reload
```

### 4. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/users/register` | Register a new user |
| POST | `/users/login` | Login (OAuth2 form data) |
| POST | `/users/refresh` | Refresh access token |

### Protected Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/protected/` | Example protected route |
| GET | `/protected/me` | Get current user info |
| GET | `/protected/admin` | Admin route example |

### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |

## Usage Examples

### Register a User

```bash
curl -X PUT "http://localhost:8000/users/register" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "email": "test@example.com",
       "password": "password123"
     }'
```

### Login

```bash
curl -X POST "http://localhost:8000/users/login" \
     -d "username=testuser&password=password123"
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Access Protected Route

```bash
curl -X GET "http://localhost:8000/protected/" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Refresh Token

```bash
curl -X POST "http://localhost:8000/users/refresh" \
     -H "Content-Type: application/json" \
     -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

## Testing

Run the comprehensive test script:

```bash
python test_token_usage.py
```

This will test:
- User registration
- Login and token generation
- Protected route access
- Token refresh functionality
- Error handling

## Code Organization

### `app/main.py`
- FastAPI application entry point
- Router registration
- Database table creation

### `app/database.py`
- SQLAlchemy engine and session setup
- Database connection management

### `app/models.py`
- SQLAlchemy ORM models
- Database table definitions

### `app/schemas.py`
- Pydantic models for request/response validation
- API input/output schemas

### `app/auth.py`
- JWT token creation and verification
- Password hashing and verification
- OAuth2 scheme configuration

### `app/routes/users.py`
- User registration and login endpoints
- Token refresh endpoint

### `app/routes/protected.py`
- Protected route examples
- Authentication-required endpoints

## Security Features

- **Access Tokens**: Short-lived (30 minutes) for API access
- **Refresh Tokens**: Long-lived (7 days) for token renewal
- **Token Type Validation**: Prevents token type confusion
- **Password Hashing**: bcrypt for secure password storage
- **JWT Claims**: Includes token type and expiration

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing secret | Required |
| `ALGORITHM` | JWT algorithm | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | 7 |

## Development

### Adding New Routes

1. Create a new file in `app/routes/`
2. Define your router with endpoints
3. Import and include the router in `app/main.py`

### Adding New Models

1. Add the model to `app/models.py`
2. Create corresponding schemas in `app/schemas.py`
3. Update database migrations if needed

### Adding New Authentication Features

1. Add functions to `app/auth.py`
2. Import and use in your route handlers

## Production Considerations

- Use a production database (PostgreSQL, MySQL)
- Store refresh tokens in database for revocation
- Use environment-specific configuration
- Implement rate limiting
- Add logging and monitoring
- Use HTTPS in production
- Consider token rotation strategies
