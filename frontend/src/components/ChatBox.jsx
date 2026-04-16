import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  for (let i = 0; i < (username || '').length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  return usernameColors[Math.abs(hash) % usernameColors.length];
}

export default function ChatBox({ streamId }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  // Fetch initial messages via REST
  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const response = await axios.get(`${API}/api/streams/${streamId}/chat`);
        setMessages(response.data);
      } catch (error) {
        console.error('Error fetching messages:', error);
      }
    };
    fetchMessages();
  }, [streamId]);

  // WebSocket connection
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    const wsUrl = API.replace('https://', 'wss://').replace('http://', 'ws://') + `/api/ws/chat/${streamId}`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      setConnected(true);
      console.log('Chat WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setMessages(prev => {
          // Deduplicate by message_id
          if (prev.some(m => m.message_id === message.message_id)) return prev;
          return [...prev, message];
        });
      } catch (e) {
        console.error('Error parsing message:', e);
      }
    };
    
    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3s
      reconnectTimerRef.current = setTimeout(connectWs, 3000);
    };
    
    ws.onerror = () => {
      ws.close();
    };
    
    wsRef.current = ws;
  }, [streamId]);

  useEffect(() => {
    connectWs();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [connectWs]);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    if (scrollRef.current) {
      const scrollEl = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollEl) {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }
    }
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !user) return;

    const content = newMessage.trim();
    setNewMessage('');

    // Send via WebSocket if connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        user_id: user.user_id,
        username: user.username,
        display_name: user.display_name,
        avatar_url: user.avatar_url,
        content: content,
        type: 'message'
      }));
    } else {
      // Fallback to REST API
      try {
        const response = await axios.post(
          `${API}/api/streams/${streamId}/chat`,
          { stream_id: streamId, content },
          { withCredentials: true }
        );
        setMessages(prev => [...prev, response.data]);
      } catch (error) {
        console.error('Error sending message:', error);
      }
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0F0F16] border-l border-white/5" data-testid="chat-box">
      {/* Header */}
      <div className="h-12 flex items-center justify-between px-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">Stream Chat</h3>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-yellow-400'}`} />
        </div>
        <span className="text-xs text-[#A0A0AB]">{messages.length} msgs</span>
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
              disabled={!newMessage.trim()}
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
