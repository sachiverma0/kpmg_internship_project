# ChatGPT-like AI Interface

A modern, full-stack chat interface with pluggable AI backend integration. Built with React and Node.js/Express.

## 🌟 Features

- **Modern Chat UI** - Clean, responsive ChatGPT-style interface
- **Real-time Messaging** - Smooth message flow with typing indicators
- **Conversation History** - Maintains context throughout the chat
- **Pluggable AI Backend** - Easy integration with multiple AI services
- **Error Handling** - Graceful error management and user feedback
- **Mobile Responsive** - Works seamlessly on all devices

## 🏗️ Architecture

```
kpmg_internship_project/
├── frontend/                 # React frontend application
│   ├── public/
│   ├── src/
│   │   ├── components/      # React components
│   │   │   ├── ChatMessage.js
│   │   │   └── ChatMessage.css
│   │   ├── services/        # API integration layer
│   │   │   └── api.js       # ⭐ Frontend AI integration point
│   │   ├── App.js
│   │   ├── App.css
│   │   └── index.js
│   └── package.json
│
└── backend/                  # Node.js/Express backend
    ├── controllers/
    │   └── chatController.js # Request handlers
    ├── routes/
    │   └── chatRoutes.js    # API routes
    ├── services/
    │   └── aiService.js     # ⭐ Backend AI integration point
    ├── server.js            # Express server setup
    └── package.json
```

## 🚀 Quick Start

### Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- An API key from your chosen AI service (OpenAI, Azure OpenAI, or Anthropic)

### Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd kpmg_internship_project
   ```

2. **Install Backend Dependencies**
   ```bash
   cd backend
   npm install
   ```

3. **Install Frontend Dependencies**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Configure Environment Variables**

   **Backend:**
   ```bash
   cd ../backend
   cp .env.example .env
   ```
   
   Edit `.env` and add your AI service credentials:
   ```env
   # For OpenAI
   OPENAI_API_KEY=your-api-key-here
   OPENAI_MODEL=gpt-3.5-turbo
   ```

   **Frontend:**
   ```bash
   cd ../frontend
   cp .env.example .env
   ```

5. **Configure AI Service** (see AI Integration section below)

### Running the Application

**Terminal 1 - Start Backend Server:**
```bash
cd backend
npm start
```
Backend will run on http://localhost:5000

**Terminal 2 - Start Frontend:**
```bash
cd frontend
npm start
```
Frontend will run on http://localhost:3000

## 🤖 AI Integration

### Integration Points

There are **two main files** where you plug in your AI service:

1. **Backend**: `backend/services/aiService.js`
   - This is where the actual AI API calls happen
   - Contains ready-to-use integration code for multiple services

2. **Frontend**: `frontend/src/services/api.js`
   - Handles communication with your backend
   - Already configured, minimal changes needed

### Supported AI Services

#### Option 1: OpenAI (ChatGPT)

1. **Install OpenAI SDK:**
   ```bash
   cd backend
   npm install openai
   ```

2. **Configure** `backend/services/aiService.js`:
   - Uncomment the OpenAI integration section (lines ~18-50)
   - Comment out the mock implementation

3. **Add API Key** to `backend/.env`:
   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-3.5-turbo
   ```

#### Option 2: Azure OpenAI

1. **Install Azure SDK:**
   ```bash
   cd backend
   npm install @azure/openai
   ```

2. **Configure** `backend/services/aiService.js`:
   - Uncomment the Azure OpenAI section (lines ~52-88)

3. **Add credentials** to `backend/.env`:
   ```env
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_KEY=your-key
   AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment
   ```

#### Option 3: Anthropic Claude

1. **Install Anthropic SDK:**
   ```bash
   cd backend
   npm install @anthropic-ai/sdk
   ```

2. **Configure** `backend/services/aiService.js`:
   - Uncomment the Anthropic section (lines ~90-125)

3. **Add API Key** to `backend/.env`:
   ```env
   ANTHROPIC_API_KEY=your-api-key
   ANTHROPIC_MODEL=claude-3-sonnet-20240229
   ```

#### Option 4: Custom AI Service

To integrate your own AI service:

1. Open `backend/services/aiService.js`
2. Scroll to "OPTION 5: Custom Integration" section
3. Implement the `generateResponse` function
4. Return an object with: `{ content, usage, model }`

### Testing Without AI (Mock Mode)

The application comes with a mock AI service enabled by default. This allows you to test the interface without API credentials. The mock simply echoes your messages back.

To use mock mode, just start the application without configuring any AI service.

## 📁 Project Structure Details

### Frontend Components

- **App.js** - Main application component with message state management
- **ChatMessage.js** - Individual message display component
- **api.js** - API service layer for backend communication

### Backend Components

- **server.js** - Express server configuration
- **chatRoutes.js** - API endpoint definitions
- **chatController.js** - Request handling logic
- **aiService.js** - AI service integration layer

## 🔧 Development

### Development Mode

**Backend with auto-reload:**
```bash
cd backend
npm run dev
```

**Frontend with hot-reload:**
```bash
cd frontend
npm start
```

### Building for Production

**Frontend:**
```bash
cd frontend
npm run build
```

The build folder will contain optimized production files.

## 🎨 Customization

### Changing the UI Theme

Edit `frontend/src/App.css` and `frontend/src/index.css` to customize colors and styling.

### Adding Features

Some ideas for extending the application:

- **User Authentication** - Add login/signup functionality
- **Chat History** - Persist conversations to a database
- **Multiple Conversations** - Support for multiple chat sessions
- **File Uploads** - Allow image/document uploads
- **Streaming Responses** - Real-time AI response streaming
- **Voice Input** - Speech-to-text integration
- **Export Chats** - Download conversations as text/PDF

## 🔒 Security Notes

- Never commit `.env` files with real API keys
- Use environment variables for all sensitive data
- Implement rate limiting in production
- Add authentication before deploying publicly
- Validate and sanitize all user inputs

## 📝 API Endpoints

### POST `/api/chat`
Send a message to the AI.

**Request:**
```json
{
  "message": "Your message here",
  "conversationHistory": [
    { "role": "user", "content": "Previous message" },
    { "role": "assistant", "content": "Previous response" }
  ]
}
```

**Response:**
```json
{
  "message": "AI response",
  "usage": { "prompt_tokens": 10, "completion_tokens": 20 },
  "model": "gpt-3.5-turbo"
}
```

### GET `/health`
Health check endpoint.

## 🐛 Troubleshooting

**Frontend can't connect to backend:**
- Check that backend is running on port 5000
- Verify `REACT_APP_API_URL` in frontend `.env`
- Check for CORS errors in browser console

**AI responses not working:**
- Verify API keys in backend `.env`
- Check backend console for error messages
- Ensure you've uncommented the correct integration in `aiService.js`
- Verify you've installed the required SDK package

**Port already in use:**
- Change `PORT` in backend `.env`
- Update `REACT_APP_API_URL` in frontend `.env` accordingly

## 📚 Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [React Documentation](https://react.dev/)
- [Express.js Guide](https://expressjs.com/)

## 📄 License

This project is open source and available for educational and commercial use.

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

---

**Built for KPMG Internship Project** - A production-ready foundation for AI-powered chat applications.
