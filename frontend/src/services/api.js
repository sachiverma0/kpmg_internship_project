import axios from 'axios';

// Configure the base URL for your backend API
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Send a message to the AI backend
 * 
 * THIS IS THE MAIN INTEGRATION POINT FOR YOUR AI SERVICE
 * 
 * @param {string} message - The user's message
 * @param {Array} conversationHistory - Previous messages in the conversation
 * @returns {Promise<Object>} - Response from the AI
 */
export const sendMessageToAI = async (message, conversationHistory = []) => {
  try {
    const response = await api.post('/api/chat', {
      message,
      conversationHistory: conversationHistory.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    });

    return response.data;
  } catch (error) {
    console.error('API Error:', error);
    
    if (error.response) {
      // Server responded with error
      throw new Error(error.response.data.error || 'Server error occurred');
    } else if (error.request) {
      // Request made but no response
      throw new Error('No response from server. Please check your connection.');
    } else {
      // Error in request setup
      throw new Error('Error sending request');
    }
  }
};

/**
 * Additional API functions you might need:
 */

// Get chat history from server
export const getChatHistory = async (sessionId) => {
  try {
    const response = await api.get(`/api/chat/history/${sessionId}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching chat history:', error);
    throw error;
  }
};

// Save chat session
export const saveChatSession = async (messages) => {
  try {
    const response = await api.post('/api/chat/save', { messages });
    return response.data;
  } catch (error) {
    console.error('Error saving chat session:', error);
    throw error;
  }
};


/**
 * Upload Excel/CSV file to backend
 * @param {File} file   The uploaded file object from frontend input
 */
export const uploadExcelFile = async (file) => {
  try {
    const formData = new FormData();
    formData.append("file", file);      // REQUIRED — backend expects this key
    formData.append("userId", "client-123"); // ADD THIS LINE


    // Use direct endpoint to bypass queue issues
    const response = await axios.post(
      `${API_BASE_URL}/api/upload-excel-direct`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      }
    );

    return response.data;
  } catch (error) {
    console.error("Upload failed:", error);

    if (error.response) {
      throw new Error(error.response.data.error);
    }
    throw new Error("Unable to upload file.");
  }
};

// RAG Query function
export const ragQuery = async (question) => {
  try {
    const response = await api.post('/api/rag-query', {
      question
    });
    return response.data;
  } catch (error) {
    console.error('RAG Query Error:', error);
    if (error.response) {
      throw new Error(error.response.data.error || 'Server error occurred');
    } else if (error.request) {
      throw new Error('No response from server. Please check your connection.');
    } else {
      throw new Error('Error sending request');
    }
  }
};

export default api;
