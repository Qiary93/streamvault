import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { PaperPlaneRight } from '@phosphor-icons/react';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import ModControls from './ModControls';
import ChatEmojiPicker from './ChatEmojiPicker';
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

export default function ChatBox({ streamId, streamerId, isSubscribed = false }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  const [systemMessage, setSystemMessage] = useState('');
  const [chatSettings, setChatSettings] = useState({ chat_enabled: true, rules: '' });
  const [rulesAccepted, setRulesAccepted] = useState(false);

  // Fetch chat settings for this streamer
  useEffect(() => {
    if (!streamerId) return;
    axios.get(`${API}/api/users/${streamerId}/chat-settings`)
      .then(res => setChatSettings({ chat_enabled: res.data.chat_enabled !== false, rules: res.data.rules || '' }))
      .catch(() => {});
  }, [streamerId]);

  // Remember rules acceptance per stream
  useEffect(() => {
    if (!streamId) return;
    try {
      const key = `sv_chat_rules_${streamId}`;
      if (localStorage.getItem(key) === '1') setRulesAccepted(true);
    } catch {}
  }, [streamId]);

  const acceptRules = () => {
    setRulesAccepted(true);
    try { localStorage.setItem(`sv_chat_rules_${streamId}`, '1'); } catch {}
  };

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
        
        // Handle system messages (bans, timeouts, slow mode)
        if (message.type === 'system') {
          setSystemMessage(message.content);
          setTimeout(() => setSystemMessage(''), 5000);
          return;
        }
        
        // Handle moderation broadcasts
        if (message.type === 'moderation') {
          const modMsg = {
            message_id: `mod_${Date.now()}`,
            type: 'moderation',
            content: message.action === 'ban' 
              ? `${message.target_username} was banned by ${message.moderator}`
              : message.action === 'timeout'
              ? `${message.target_username} was timed out for ${message.duration}s by ${message.moderator}`
              : message.action === 'slow_mode'
              ? message.duration > 0 ? `Slow mode set to ${message.duration}s by ${message.moderator}` : `Slow mode disabled by ${message.moderator}`
              : '',
            username: 'System',
            stream_id: streamId,
            created_at: new Date().toISOString()
          };
          if (modMsg.content) {
            setMessages(prev => [...prev, modMsg]);
          }
          return;
        }
        
        setMessages(prev => {
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
    <div className="h-full flex flex-col bg-[#0F0F16] border-l border-white/5 relative" data-testid="chat-box">
      {/* Chat disabled overlay */}
      {!chatSettings.chat_enabled && (
        <div className="absolute inset-0 z-20 bg-[#0F0F16]/95 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center" data-testid="chat-disabled-overlay">
          <div className="w-14 h-14 rounded-full bg-[#1A1A24] flex items-center justify-center mb-3">
            <span className="text-2xl">💬</span>
          </div>
          <h3 className="text-white font-semibold mb-1">Chat is disabled</h3>
          <p className="text-sm text-[#A0A0AB]">The streamer has turned off chat for this stream.</p>
        </div>
      )}

      {/* Rules gate overlay */}
      {chatSettings.chat_enabled && chatSettings.rules && !rulesAccepted && (
        <div className="absolute inset-0 z-20 bg-[#0F0F16]/95 backdrop-blur-sm flex flex-col p-4" data-testid="chat-rules-overlay">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xl">📜</span>
            <h3 className="font-semibold text-white">Chat rules</h3>
          </div>
          <div className="flex-1 overflow-y-auto bg-[#1A1A24] rounded-lg p-4 mb-3 text-sm text-[#A0A0AB] whitespace-pre-wrap" data-testid="chat-rules-content">
            {chatSettings.rules}
          </div>
          <Button
            onClick={acceptRules}
            className="w-full bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold"
            data-testid="chat-rules-accept-btn"
          >
            I accept the rules
          </Button>
        </div>
      )}

      {/* Header */}
      <div className="h-12 flex items-center justify-between px-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">Stream Chat</h3>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-yellow-400'}`} />
        </div>
        <div className="flex items-center gap-2">
          <ModControls streamId={streamId} />
          <span className="text-xs text-[#A0A0AB]">{messages.length} msgs</span>
        </div>
      </div>

      {/* System message */}
      {systemMessage && (
        <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 text-red-400 text-xs text-center">
          {systemMessage}
        </div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-3">
          {messages.map((msg) => (
            <div key={msg.message_id} className={`flex gap-2 chat-message-enter group ${msg.type === 'moderation' ? 'justify-center' : ''}`} data-testid={`chat-msg-${msg.message_id}`}>
              {msg.type === 'moderation' ? (
                <span className="text-xs text-yellow-400 italic bg-yellow-500/10 px-3 py-1 rounded-full">
                  {msg.content}
                </span>
              ) : (
                <>
                  <Avatar className="w-6 h-6 flex-shrink-0">
                    <AvatarImage src={msg.avatar_url} alt={msg.username} />
                    <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-xs">
                      {(msg.display_name || msg.username)?.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1">
                      <span 
                        className="text-sm font-semibold mr-1"
                        style={{ color: getUsernameColor(msg.username) }}
                      >
                        {msg.display_name || msg.username}
                      </span>
                      {msg.user_id && msg.user_id !== user?.user_id && (
                        <ModControls streamId={streamId} targetUserId={msg.user_id} targetUsername={msg.username} />
                      )}
                    </div>
                    <span className="text-sm text-[#A0A0AB] break-words">{msg.content}</span>
                  </div>
                </>
              )}
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
      <div className="p-3 border-t border-white/5">
        {user ? (
          <form onSubmit={handleSendMessage} className="flex items-center gap-1.5">
            <ChatEmojiPicker
              onSelect={(emoji) => setNewMessage(prev => prev + emoji)}
              streamerId={streamerId}
              isSubscribed={isSubscribed}
            />
            <input
              type="text"
              placeholder="Send a message..."
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              maxLength={500}
              className="flex-1 h-10 px-3 bg-[#1A1A24] border border-white/10 rounded-lg text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] transition-colors text-sm"
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
