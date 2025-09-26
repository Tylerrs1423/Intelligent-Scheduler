# AI-FOCO: Intelligent Calendar Scheduler

An AI-powered calendar scheduling system that automatically allocates time for your tasks, eliminating the mental burden of manual scheduling. Stop wasting time trying to figure out when to do things - let AI handle the complex scheduling decisions for you.

## 🎯 Problem This Solves

**The Challenge:** Most people struggle with manually scheduling tasks, leading to:
- Time wasted on "when should I do this?" decisions
- Poor time allocation and over-scheduling
- Tasks getting forgotten or delayed
- Mental fatigue from constant scheduling decisions

**The Solution:** AI-FOCO automatically schedules your tasks based on your preferences, sleep schedule, and optimal timing, freeing you to focus on actually doing the work instead of planning when to do it.

## ✨ Core Features

### 🧠 **Intelligent Auto-Scheduling**
- **Flexible vs Fixed Events**: Let AI find the best time for flexible tasks, or lock in exact times for meetings
- **Multi-Factor Scoring**: Considers your time preferences, task priority, sleep schedule, and existing commitments
- **Conflict Resolution**: Automatically handles scheduling conflicts and finds alternative times

### ⏰ **Smart Time Management**
- **Sleep Schedule Integration**: Never schedules during your sleep hours (customizable)
- **Buffer Time Management**: Automatically adds transition time between tasks
- **Priority-Based Scheduling**: High-priority tasks get the best time slots
- **Work Hour Limits**: Respects your daily capacity to prevent over-scheduling

### 🎨 **Personalized Preferences**
- **Time Windows**: Set preferred work hours (morning person vs night owl)
- **Theme-Based Scheduling**: Personalize based on interests (fitness, learning, productivity)
- **Intensity Profiles**: Choose your scheduling style (chill, steady, or hardcore)
- **Difficulty Matching**: Tasks are scheduled based on your energy levels throughout the day

### 📊 **Visual Calendar Management**
- **Real-Time Updates**: See your schedule update automatically as tasks are added
- **Buffer Visualization**: See transition time blocks in your calendar (gray blocks)
- **Conflict Detection**: Clear indicators when scheduling conflicts occur
- **Drag-and-Drop Override**: Manually adjust when needed, AI learns from your changes

## 🛠️ Technical Architecture

- **Backend**: FastAPI with SQLite database
- **Frontend**: Next.js with TypeScript and Tailwind CSS
- **Scheduling Engine**: Custom multi-factor scoring algorithm
- **Real-Time Updates**: WebSocket integration for live calendar updates
- **Authentication**: JWT-based user management

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- Modern web browser

### Quick Setup

1. **Clone and Install:**
   ```bash
   git clone <repository-url>
   cd ai-foco
   pip install -r requirements.txt
   cd app/frontend && npm install
   ```

2. **Configure Your Preferences:**
   - Set your sleep schedule (Sleep Settings)
   - Choose your work intensity level
   - Select your preferred time windows
   - Configure buffer times (Buffer Settings)

3. **Start Using:**
   ```bash
   # Start backend
   python -m uvicorn app.main:app --reload
   
   # Start frontend (new terminal)
   cd app/frontend && npm run dev
   ```

4. **Create Your First Tasks:**
   - Add flexible tasks and let AI schedule them optimally
   - Add fixed events for meetings and appointments
   - Watch as your calendar automatically fills with perfectly timed blocks

## 📈 How It Works

1. **Add Tasks**: Simply describe what you need to do and how long it takes
2. **AI Scheduling**: The system analyzes your preferences, existing schedule, and optimal timing
3. **Automatic Placement**: Tasks are placed in the best available time slots
4. **Smart Adjustments**: If conflicts arise, the system finds the next best time
5. **Visual Feedback**: See your optimized schedule update in real-time

## 🎯 Key Benefits

- **⏱️ Time Saved**: No more manual scheduling decisions - save 30+ minutes daily
- **🧠 Mental Relief**: Eliminate the cognitive load of "when should I do this?"
- **📈 Better Productivity**: Optimal task placement leads to higher completion rates
- **⚖️ Work-Life Balance**: Automatic respect for sleep and personal time
- **🎯 Focus on Execution**: Spend time doing tasks, not planning when to do them

## 🔧 Recent Updates

### ✨ **New Features Added:**
- **Sleep Settings Modal**: Configure your sleep schedule to prevent scheduling during sleep hours
- **Buffer Settings Modal**: Set default buffer times for smooth transitions between tasks
- **Buffer Visualization**: See buffer blocks (gray) in your calendar alongside events (blue)
- **Enhanced UI**: Professional modals with intuitive controls and helpful descriptions

### 🐛 **Bug Fixes:**
- **Buffer Display**: Fixed calendar to properly show buffer time blocks
- **Event Creation**: Resolved syntax errors in event creation endpoints
- **Frontend Integration**: Improved component communication and state management

## 📖 API Documentation

- **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

### Key Endpoints:
- `POST /events/create` - Create new events (flexible or fixed)
- `GET /events/scheduler-slots` - Get formatted schedule with buffers
- `POST /users/user/sleep-preferences` - Configure sleep schedule
- `GET /users/user/preferences` - Get user preferences

## 🔮 Future Enhancements

- **AI-Powered Task Breakdown**: Automatically chunk large projects into manageable pieces
- **Energy Level Optimization**: Schedule cognitively demanding tasks during peak energy hours
- **Habit Integration**: Automatically schedule recurring habits at optimal times
- **Team Scheduling**: Coordinate schedules with colleagues and family
- **Mobile App**: Full scheduling control from your phone
- **Theme Tags Integration**: Personalized scheduling based on interests (fitness, learning, etc.)

## 🐛 Troubleshooting

### Common Issues
- **401 Unauthorized**: Make sure you're logged in and token is valid
- **Buffer Not Showing**: Check that you've set sleep preferences first
- **Scheduling Conflicts**: The system will automatically find alternative times
- **Frontend Not Loading**: Ensure both backend (port 8000) and frontend (port 3000) are running

### Getting Help
1. Check the browser console for errors
2. Verify both backend and frontend servers are running
3. Check the API docs at `http://localhost:8000/docs`
4. Create an issue in the repository

## 📁 Project Structure
```
ai-foco/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── models/                    # Database models
│   ├── routes/                    # API endpoints
│   ├── scheduling/                # Core scheduling algorithms
│   ├── services/                  # Business logic services
│   └── frontend/                  # Next.js React application
│       ├── app/
│       │   ├── components/        # React components
│       │   ├── hooks/             # Custom React hooks
│       │   └── page.tsx           # Main application page
│       └── package.json           # Frontend dependencies
├── requirements.txt               # Python dependencies
└── README.md                     # This file
```

---

**Stop spending time planning when to work. Start spending time actually working.**

AI-FOCO handles the complex scheduling decisions so you can focus on what matters most: getting things done.

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines and feel free to submit pull requests for new features or bug fixes.

## 📄 License

This project is licensed under the MIT License.