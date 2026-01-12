import React from 'react';
import './ChatMessage.css';

function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const colorMap = {
    red: '#ef4444',
    orange: '#fb923c',
    yellow: '#f59e0b',
    green: '#10b981',
    blue: '#3b82f6',
    purple: '#8b5cf6',
    pink: '#ec4899'
  };
  const avatarStyle = isUser ? { backgroundColor: colorMap[message.color] || '#565869' } : {};
  
  return (
    <div className={`chat-message ${isUser ? 'user-message' : 'assistant-message'} ${message.isError ? 'error-message' : ''}`}>
      <div className="message-avatar">
        <div style={avatarStyle} className="avatar-inner">{isUser ? '👤' : '🤖'}</div>
      </div>
      <div className="message-content">
        <div className="message-role">
          {isUser ? 'You' : 'AI Assistant'}
        </div>
        <div className="message-text">
          {message.content}
        </div>
        <div className="message-timestamp">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

export default ChatMessage;
