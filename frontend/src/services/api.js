import axios from 'axios';
import { msalInstance } from '../msalConfig';

// Configure the base URL for your backend API
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to every request
api.interceptors.request.use(async (config) => {
  try {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      const response = await msalInstance.acquireTokenSilent({
        scopes: ["openid", "profile", "email"],
        account: accounts[0],
      });
      config.headers.Authorization = `Bearer ${response.accessToken}`;
    }
  } catch (error) {
    console.error('Error acquiring token:', error);
    // Continue without token - backend will reject with 401
  }
  return config;
}, (error) => {
  return Promise.reject(error);
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
      if (error.response.status === 401) {
        throw new Error('Authentication failed. Please sign in again.');
      }
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

    // Use direct endpoint to bypass queue issues
    const response = await api.post(
      '/api/upload-excel-direct',
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

/**
 * Get uploaded files for a user
 */
export const getUploadedFiles = async () => {
  try {
    const response = await api.get('/api/get-uploaded-files');
    return response.data;
  } catch (error) {
    console.error('Error fetching uploaded files:', error);
    return { csvFiles: [], policyFiles: [] };
  }
};

/**
 * Upload policy documents (PDF, DOCX, DOC, TXT) to backend
 * @param {File[]} files - Array of policy document files
 */
export const uploadPolicyDocuments = async (files) => {
  try {
    const formData = new FormData();
    
    // Add all files
    files.forEach((file) => {
      formData.append("files", file);
    });

    const response = await api.post(
      '/api/upload-policy-documents',
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      }
    );

    return response.data;
  } catch (error) {
    console.error("Policy document upload failed:", error);

    if (error.response) {
      throw new Error(error.response.data.error || "Upload failed");
    }
    throw new Error("Unable to upload policy documents.");
  }
};

export default api;
