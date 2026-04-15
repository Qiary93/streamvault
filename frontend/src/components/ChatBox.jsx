import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { PaperPlaneRight } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

// Color palette for usernames
const usernameColors = [
  '#00E5FF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3',
  '#F38181', '#AA96DA', '#FF9671', '#FFC75F', '#00C9A7'
];

function getUsernameColor(username) {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  return usernameColors[Math.abs(hash) % usernameColors.length];
}

export default function ChatBox({ streamId }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const fetchMessages = async () => {
    try {
      const response = await axios.get(`${API}/api/streams/${streamId}/chat`);
      setMessages(response.data);
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  useEffect(() => {
    fetchMessages();
    
    // Poll for new messages
    pollIntervalRef.current = setInterval(fetchMessages, 3000);
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [streamId]);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !user || loading) return;

    setLoading(true);
    try {
      const response = await axios.post(
        `${API}/api/streams/${streamId}/chat`,
        { stream_id: streamId, content: newMessage.trim() },
        { withCredentials: true }
      );
      setMessages(prev => [...prev, response.data]);
      setNewMessage('');
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0F0F16] border-l border-white/5" data-testid="chat-box">
      {/* Header */}
      <div className="h-12 flex items-center justify-between px-4 border-b border-white/5">
        <h3 className="font-semibold text-white">Stream Chat</h3>
        <span className="text-xs text-[#A0A0AB]">{messages.length} messages</span>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-3">
          {messages.map((msg) => (
            <div key={msg.message_id} className="flex gap-2 chat-message-enter" data-testid={`chat-msg-${msg.message_id}`}>
              <Avatar className="w-6 h-6 flex-shrink-0">
                <AvatarImage src={msg.avatar_url} alt={msg.username} />
                <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xs">
                  {(msg.display_name || msg.username)?.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <span 
                  className="text-sm font-semibold mr-2"
                  style={{ color: getUsernameColor(msg.username) }}
                >
                  {msg.display_name || msg.username}
                </span>
                <span className="text-sm text-[#A0A0AB] break-words">{msg.content}</span>
              </div>
            </div>
          ))}
          {messages.length === 0 && (
            <p className="text-center text-[#A0A0AB] text-sm py-8">
              No messages yet. Be the first to chat!
            </p>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t border-white/5">
        {user ? (
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <input
              type="text"
              placeholder="Send a message..."
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              maxLength={500}
              className="flex-1 h-10 px-4 bg-[#1A1A24] border border-white/10 rounded-lg text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] transition-colors"
              data-testid="chat-input"
            />
            <Button 
              type="submit" 
              disabled={loading || !newMessage.trim()}
              className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] disabled:opacity-50"
              data-testid="chat-submit-button"
            >
              <PaperPlaneRight weight="fill" className="w-5 h-5" />
            </Button>
          </form>
        ) : (
          <p className="text-center text-[#A0A0AB] text-sm">
            <a href="/auth" className="text-[#00E5FF] hover:underline">Log in</a> to chat
          </p>
        )}
      </div>
    </div>
  );
}
