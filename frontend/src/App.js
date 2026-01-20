import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import ChatMessage from './components/ChatMessage';
import { sendMessageToAI, uploadExcelFile, ragQuery, uploadPolicyDocuments, getUploadedFiles } from './services/api';
import { MsalProvider, useMsal } from "@azure/msal-react";
import { msalInstance } from "./msalConfig";
import AuthenticationComponent, { useBypassAuth } from './components/AuthenticationComponent';

function AppContent() {
  const { instance } = useMsal();
  const bypassAuthContext = useBypassAuth();
  const bypassAuth = bypassAuthContext?.bypassAuth;
  const setBypassAuth = bypassAuthContext?.setBypassAuth;

  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedColor, setSelectedColor] = useState('blue');
  const [showSettings, setShowSettings] = useState(false);
  const [clientFiles, setClientFiles] = useState([]);
  const [uploadedClientFiles, setUploadedClientFiles] = useState([]);
  const [clientDragActive, setClientDragActive] = useState(false);
  const [policyFiles, setPolicyFiles] = useState([]);
  const [uploadedPolicyFiles, setUploadedPolicyFiles] = useState([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const settingsRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Fetch existing uploaded files when component mounts
    const fetchFiles = async () => {
      const files = await getUploadedFiles();
      if (files.csvFiles.length > 0) {
        setUploadedClientFiles(files.csvFiles.map(f => ({ name: f.name })));
      }
      if (files.policyFiles.length > 0) {
        setUploadedPolicyFiles(files.policyFiles.map(f => ({ name: f.name })));
      }
    };
    fetchFiles();
  }, []);

  useEffect(() => {
    function handleClickOutside(e) {
      if (showSettings && settingsRef.current && !settingsRef.current.contains(e.target) && !e.target.closest('.settings-button')) {
        setShowSettings(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showSettings]);

  const handleClientFileUpload = async () => {
    if (clientFiles.length === 0) {
      alert("Please select a CSV/XLSX file first.");
      return;
    }

    const file = clientFiles[0];

    try {
      console.log("Uploading file:", file.name);

      const result = await uploadExcelFile(file);

      alert(`Uploaded ${result.rowsProcessed || result.rowsQueued} rows to the server.`);
      console.log("Upload result:", result);
      
      // Store uploaded files and clear selection
      setUploadedClientFiles([file]);
      setClientFiles([]);

    } catch (error) {
      console.error("Upload failed:", error);
      alert(error.message || "Upload failed. See console.");
    }
  };

  const handlePolicyDocumentUpload = async () => {
    if (policyFiles.length === 0) {
      alert("Please select policy document files first.");
      return;
    }

    try {
      console.log("Uploading policy documents:", policyFiles.map(f => f.name));

      const result = await uploadPolicyDocuments(policyFiles);

      alert(`Uploaded ${result.filesProcessed} policy document(s) to the database.`);
      console.log("Upload result:", result);
      
      // Store uploaded files and clear selection
      setUploadedPolicyFiles(policyFiles);
      setPolicyFiles([]);

    } catch (error) {
      console.error("Policy document upload failed:", error);
      alert(error.message || "Upload failed. See console.");
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      color: selectedColor,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Call RAG query to get context from uploaded documents
      const ragResult = await ragQuery(inputMessage);
  
      // Use RAG answer if available, otherwise fall back to regular chat
      let assistantContent;
      if (ragResult && ragResult.answer) {
        assistantContent = ragResult.answer;
      } else {
        // Fallback to regular chat if no RAG results
        const response = await sendMessageToAI(inputMessage, messages);
        assistantContent = response.message;
      }
      
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: assistantContent,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
        isError: true
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
  };

  const handleClientFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    setClientFiles(prev => [...prev, ...files]);
  };

  const handleClientDrop = (e) => {
    e.preventDefault();
    setClientDragActive(false);
    const files = Array.from(e.dataTransfer?.files || []);
    // Only accept csv files here
    const csvFiles = files.filter(f => f.name.toLowerCase().endsWith('.csv'));
    if (csvFiles.length) setClientFiles(prev => [...prev, ...csvFiles]);
  };

  const handleClientDragOver = (e) => {
    e.preventDefault();
    setClientDragActive(true);
  };

  const handleClientDragLeave = (e) => {
    e.preventDefault();
    setClientDragActive(false);
  };

  const handlePolicyFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    setPolicyFiles(files);
  };

  const handleSignOut = async () => {
    if (bypassAuth) {
      setBypassAuth(false);
    } else {
      await instance.logout({
        postLogoutRedirectUri: "/",
      });
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <img src="/kpmg_logo.png" alt="KPMG" className="header-logo" />
          <span className="header-title">Client Compliance Tool</span>
        </div>
        <div className="header-actions">
          <button onClick={handleClearChat} className="clear-button">
            Clear Chat
          </button>
          <button onClick={handleSignOut} className="clear-button">
            Sign Out
          </button>
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              className="settings-button"
              onClick={() => setShowSettings(s => !s)}
              aria-label="Help"
            >
              ?
            </button>
            <div ref={settingsRef} className={`settings-dropdown ${showSettings ? 'open' : ''}`}>
              <div className="settings-placeholder">Settings</div>
            </div>
          </div>
        </div>
      </header>

      <div className="main-area">
        <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
          <div className="collapse-area">
            <button
              type="button"
              className="collapse-button"
              onClick={() => setSidebarCollapsed(s => !s)}
              aria-label="Toggle sidebar"
            >
              ◀
            </button>
          </div>

          <div className={`upload-section ${sidebarCollapsed ? 'hidden' : ''}`}>
            <h3>Upload client fund data</h3>
            <div
              className={`upload-dropzone ${clientDragActive ? 'drag-active' : ''}`}
              onDrop={handleClientDrop}
              onDragOver={handleClientDragOver}
              onDragLeave={handleClientDragLeave}
              onClick={() => document.getElementById('client-file-input')?.click()}
            >
              <input
                id="client-file-input"
                type="file"
                accept=".csv,text/csv"
                multiple
                onChange={handleClientFileChange}
                className="upload-input"
              />
              <div className="dropzone-content">
                <div className="dropbox-icon" aria-hidden>
                  {/* simple upload/cloud SVG */}
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 3c-2.21 0-4 1.79-4 4 0 .55.45 1 1 1h6c.55 0 1-.45 1-1 0-2.21-1.79-4-4-4z" fill="#cfcfd6"/>
                    <path d="M6 10c-1.1 0-2 .9-2 2v3c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-3c0-1.1-.9-2-2-2H6z" fill="#9aa0a8"/>
                    <path d="M8 12l4 3 4-3" stroke="#343541" strokeWidth="0.5" fill="none"/>
                  </svg>
                </div>
                <p className="dropzone-instruction">Drag & drop CSV files here, or click to choose files</p>
                {clientFiles.length > 0 && <p className="dropzone-count">{clientFiles.length} file{clientFiles.length>1?'s':''} selected</p>}
              </div>
            </div>
            {clientFiles.length > 0 && (
              <ul className="file-list">
                {clientFiles.map((f, i) => (
                  <li key={i}>{f.name}</li>
                ))}
              </ul>
            )}
            
            {clientFiles.length > 0 && (
              <button
                onClick={handleClientFileUpload}
                className="upload-button"
                style={{ marginTop: "10px" }}
              >
                Upload to Backend
              </button>
            )}

            {uploadedClientFiles.length > 0 && clientFiles.length === 0 && (
              <div>
                <p style={{ marginTop: "10px", fontSize: "0.9em", color: "#666" }}>Uploaded files:</p>
                <ul className="file-list">
                  {uploadedClientFiles.map((f, i) => (
                    <li key={i}>{f.name}</li>
                  ))}
                </ul>
              </div>
            )}

          </div>

          <div className={`upload-section ${sidebarCollapsed ? 'hidden' : ''}`}>
            <h3>Upload compliance policy documents</h3>
            <div
              className={`upload-dropzone policy-dropzone`}
              onDrop={(e) => {
                e.preventDefault();
                const files = Array.from(e.dataTransfer?.files || []);
                if (files.length) setPolicyFiles(prev => [...prev, ...files]);
              }}
              onDragOver={(e) => { e.preventDefault(); }}
              onDragLeave={(e) => { e.preventDefault(); }}
              onClick={() => document.getElementById('policy-file-input')?.click()}
            >
              <input
                id="policy-file-input"
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                multiple
                onChange={handlePolicyFileChange}
                className="policy-input"
              />
              <div className="dropzone-content">
                <div className="dropbox-icon" aria-hidden>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 3c-2.21 0-4 1.79-4 4 0 .55.45 1 1 1h6c.55 0 1-.45 1-1 0-2.21-1.79-4-4-4z" fill="#cfcfd6"/>
                    <path d="M6 10c-1.1 0-2 .9-2 2v3c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-3c0-1.1-.9-2-2-2H6z" fill="#9aa0a8"/>
                    <path d="M8 12l4 3 4-3" stroke="#343541" strokeWidth="0.5" fill="none"/>
                  </svg>
                </div>
                <p className="dropzone-instruction">Drag & drop files here, or click to choose files</p>
                {policyFiles.length > 0 && <p className="dropzone-count">{policyFiles.length} file{policyFiles.length>1?'s':''} selected</p>}
              </div>
            </div>
            {policyFiles.length > 0 && (
              <ul className="file-list">
                {policyFiles.map((f, i) => (
                  <li key={i}>{f.name}</li>
                ))}
              </ul>
            )}

            {policyFiles.length > 0 && (
              <button
                onClick={handlePolicyDocumentUpload}
                className="upload-button"
                style={{ marginTop: "10px" }}
              >
                Upload to Backend
              </button>
            )}

            {uploadedPolicyFiles.length > 0 && policyFiles.length === 0 && (
              <div>
                <p style={{ marginTop: "10px", fontSize: "0.9em", color: "#666" }}>Uploaded files:</p>
                <ul className="file-list">
                  {uploadedPolicyFiles.map((f, i) => (
                    <li key={i}>{f.name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </aside>

        <div className="chat-container">
        <div className="messages-container">
          {messages.length === 0 && (
            <div className="empty-state">
              <h2>👋 Welcome!</h2>
              <p>Start a conversation by typing a message below.</p>
            </div>
          )}
          
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
          
          {isLoading && (
            <div className="loading-indicator">
              <div className="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSendMessage} className="input-container">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message here..."
            className="message-input"
            disabled={isLoading}
          />
          <button 
            type="submit" 
            className="send-button"
            disabled={!inputMessage.trim() || isLoading}
          >
            Send
          </button>
        </form>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthenticationComponent>
        <AppContent />
      </AuthenticationComponent>
    </MsalProvider>
  );
}

export default App;
