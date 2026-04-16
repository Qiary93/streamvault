import React, { useState, useEffect, useCallback } from 'react';
import { Bell, Check } from '@phosphor-icons/react';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { ScrollArea } from './ui/scroll-area';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const typeIcons = {
  follow: '+ Follow',
  donation: '$ Tip',
  subscription: '* Sub',
};

const typeColors = {
  follow: 'text-[#00E5FF]',
  donation: 'text-purple-400',
  subscription: 'text-yellow-400',
};

export default function NotificationBell() {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);

  const fetchNotifications = useCallback(async () => {
    if (!user) return;
    try {
      const [notifsRes, countRes] = await Promise.all([
        axios.get(`${API}/api/notifications`, { withCredentials: true }),
        axios.get(`${API}/api/notifications/unread-count`, { withCredentials: true })
      ]);
      setNotifications(notifsRes.data);
      setUnreadCount(countRes.data.count);
    } catch (error) {
      console.error('Error fetching notifications:', error);
    }
  }, [user]);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 10000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  const markAllRead = async () => {
    try {
      await axios.put(`${API}/api/notifications/read-all`, {}, { withCredentials: true });
      setUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (error) {
      console.error('Error marking all read:', error);
    }
  };

  const formatTime = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  if (!user) return null;

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative text-[#A0A0AB] hover:text-white hover:bg-white/10"
          data-testid="notifications-btn"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 bg-[#0F0F16] border-white/10 p-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <h3 className="font-semibold text-white">Notifications</h3>
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-xs text-[#00E5FF] hover:underline flex items-center gap-1"
              data-testid="mark-all-read-btn"
            >
              <Check className="w-3 h-3" /> Mark all read
            </button>
          )}
        </div>
        <ScrollArea className="max-h-80">
          {notifications.length > 0 ? (
            <div>
              {notifications.map((notif) => (
                <div
                  key={notif.notification_id}
                  className={`px-4 py-3 border-b border-white/5 hover:bg-white/5 transition-colors ${!notif.read ? 'bg-[#00E5FF]/5' : ''}`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${typeColors[notif.type] || 'text-[#A0A0AB]'} bg-white/5`}>
                      {typeIcons[notif.type] || notif.type}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white">{notif.message}</p>
                      <p className="text-xs text-[#A0A0AB] mt-1">{formatTime(notif.created_at)}</p>
                    </div>
                    {!notif.read && (
                      <div className="w-2 h-2 bg-[#00E5FF] rounded-full flex-shrink-0 mt-1.5" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-4 py-8 text-center">
              <p className="text-[#A0A0AB] text-sm">No notifications yet</p>
            </div>
          )}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
