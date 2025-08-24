# AI Foco - Backend API

A FastAPI backend for event scheduling and management. This backend provides a complete API for creating, managing, and displaying calendar events.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip

### Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd ai-foco

# Create virtual environment
python -m venv env

# Activate virtual environment
# On Mac/Linux:
source env/bin/activate
# On Windows:
env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m app.main
```

The server will start at `http://localhost:8000`

## 📖 API Documentation

- **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

## 🔐 Authentication

All endpoints require authentication using JWT tokens.

### 1. Register a User
```bash
POST /users/register
Content-Type: application/json

{
  "username": "yourname",
  "email": "your@email.com", 
  "password": "yourpassword"
}
```

### 2. Login to Get Token
```bash
POST /users/login
Content-Type: application/json

{
  "username": "yourname",
  "password": "yourpassword"
}
```

**Response includes:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### 3. Use Token in Requests
```bash
Authorization: Bearer <your-access-token>
```

## 📅 Event Management API

### Create Event
```bash
POST /events/create
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Team Meeting",
  "description": "Weekly standup",
  "start_time": "2024-01-15T09:00:00",
  "end_time": "2024-01-15T10:00:00",
  "scheduling_flexibility": "fixed",
  "buffer_before": 15,
  "buffer_after": 15
}
```

### Get All Events
```bash
GET /events/
Authorization: Bearer <token>
```

### Get Event by ID
```bash
GET /events/{event_id}
Authorization: Bearer <token>
```

### Get Events by Date
```bash
GET /events/date?date=2024-01-15
Authorization: Bearer <token>
```

### Get Events by Date Range
```bash
GET /events/date_range?start_date=2024-01-15&end_date=2024-01-16
Authorization: Bearer <token>
```

### Update Event
```bash
PUT /events/update/{event_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Updated Meeting Title",
  "buffer_before": 30
}
```

### Delete Event
```bash
DELETE /events/delete/{event_id}
Authorization: Bearer <token>
```

## 📊 Schedule Display API

### Get Formatted Schedule
```bash
GET /schedule/?start_date=2024-01-15&end_date=2024-01-15
Authorization: Bearer <token>
```

**Response format:**
```json
{
  "events": [
    {
      "id": 1,
      "start_time": "2024-01-15T09:00:00",
      "end_time": "2024-01-15T10:00:00",
      "title": "Team Meeting",
      "description": "Weekly standup",
      "scheduling_flexibility": "fixed",
      "buffer_before": 15,
      "buffer_after": 15
    }
  ]
}
```

## 🔧 Event Schema

### Required Fields
- `title`: Event title (string)
- `start_time`: Start datetime (ISO format: "2024-01-15T09:00:00")
- `end_time`: End datetime (ISO format: "2024-01-15T10:00:00")

### Optional Fields
- `description`: Event description (string, default: "")
- `scheduling_flexibility`: "fixed", "strict", "flexible", "window", "window_unstrict"
- `buffer_before`: Minutes before event (integer)
- `buffer_after`: Minutes after event (integer)

## 🎯 Frontend Development Tips

1. **Store the JWT token** after login (localStorage, sessionStorage, or state management)
2. **Include the token** in the Authorization header for all API calls
3. **Handle token expiration** - tokens expire after 24 hours
4. **Use ISO datetime format** for all date/time fields
5. **The schedule endpoint** returns data formatted for easy frontend consumption

## 🐛 Troubleshooting

### Common Issues
- **401 Unauthorized**: Check if your JWT token is valid and included in headers
- **422 Validation Error**: Check your request body format and enum values
- **500 Internal Server Error**: Check server logs for details

### Token Expiration
If you get "Could not validate credentials", your token has expired. Re-login to get a new token.

## 📁 Project Structure
```
app/
├── main.py              # FastAPI app and route registration
├── models.py            # Database models (Event, User)
├── schemas.py           # Pydantic schemas for validation
├── routes/
│   ├── events.py        # Event CRUD endpoints
│   ├── schedule.py      # Schedule display endpoint
│   └── users.py         # User authentication
└── scheduling/          # Core scheduling logic
```

## 🚀 Ready to Build!

Your backend is fully functional and ready for frontend development. Start building your calendar interface, event forms, and schedule display!

---

**Need help?** Check the API docs at `http://localhost:8000/docs` or create an issue in the repository.
