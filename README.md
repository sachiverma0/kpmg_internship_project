# KPMG AI Interface

A ChatGPT-like interface built with React frontend and Flask backend, powered by Azure OpenAI.

## Prerequisites

Before starting, ensure you have the following installed:

- **Node.js** (v14 or higher) - [Download here](https://nodejs.org/)
- **Python** (v3.8 or higher) - [Download here](https://www.python.org/)
- **npm** (comes with Node.js)
- **pip** (comes with Python)

## Project Structure

```
kpmg_internship_project/
├── frontend/           # React application
│   ├── src/           # React components and services
│   ├── public/        # Static files
│   ├── server.py      # Flask backend server
│   └── package.json   # Frontend dependencies
└── README.md          # This file
```

## Setup Instructions

### 1. Configure Environment Variables

Create a `.env` file in the `frontend` directory:

```bash
cd frontend
```

Create `.env` file with the following content:

```
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_VERSION=2023-05-15
```

Replace the placeholder values with your actual Azure OpenAI credentials.

### 2. Install Frontend Dependencies

```bash
npm install
```

### 3. Install Backend Dependencies

Make sure you're in the `frontend` directory, then install Python packages:

```bash
pip install flask flask-cors python-dotenv openai
```

## Running the Application

You'll need to run **two separate terminals** - one for the backend server and one for the frontend.

### Terminal 1: Start the Backend Server

```bash
cd frontend
python server.py
```

The Flask server will start on `http://localhost:5000`

### Terminal 2: Start the Frontend

Open a new terminal and run:

```bash
cd frontend
npm start
```

The React application will start on `http://localhost:3000` and automatically open in your browser.

## Accessing the AI Interface

Once both servers are running, navigate to:

```
http://localhost:3000
```

You can now interact with the AI interface by typing messages in the chat box.

## Troubleshooting

### Port Already in Use

If you see port errors:
- Backend (port 5000): Stop any other Flask applications or change the port in `server.py`
- Frontend (port 3000): The React app will prompt you to use a different port

### Module Not Found Errors

If you encounter Python module errors:
```bash
pip install flask flask-cors python-dotenv openai
```

If you encounter npm errors:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Azure OpenAI Authentication Errors

Verify your `.env` file contains valid credentials:
- Check the API key is correct
- Verify the endpoint URL format
- Ensure the API version is compatible

## Stopping the Application

- **Backend**: Press `Ctrl + C` in the terminal running `server.py`
- **Frontend**: Press `Ctrl + C` in the terminal running `npm start`

## Development

- Frontend source code: `frontend/src/`
- Backend API: `frontend/server.py`
- API endpoint: `http://localhost:5000/api/chat`

## Technologies Used

- **Frontend**: React 18, Axios
- **Backend**: Flask, Azure OpenAI Python SDK
- **Styling**: CSS
- **API**: Azure OpenAI GPT Models