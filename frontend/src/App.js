import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import ChatMessage from './components/ChatMessage';
import { sendMessageToAI } from './services/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedColor, setSelectedColor] = useState('blue');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
      // This is where the AI integration happens
      const response = await sendMessageToAI(inputMessage, messages);
      
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.message,
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

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Chat Interface</h1>
        <button onClick={handleClearChat} className="clear-button">
          Clear Chat
        </button>
      </header>

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

        <div className="color-selector-container">
          <div className="color-selector-label">Your icon color:</div>
          {['red','orange','yellow','green','blue','purple','pink'].map((c) => (
            <button
              key={c}
              type="button"
              className={`color-swatch ${selectedColor === c ? 'selected' : ''}`}
              onClick={() => setSelectedColor(c)}
              aria-label={`Select ${c}`}
            >
              <span className={`swatch-circle ${c}`}></span>
            </button>
          ))}
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
  );
}

export default App;
