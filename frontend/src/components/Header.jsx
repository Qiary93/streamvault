import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { MagnifyingGlass, Bell, SignOut, User, Broadcast } from '@phosphor-icons/react';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <header className="sticky top-0 z-30 h-16 glass border-b border-white/5" data-testid="header">
      <div className="h-full px-4 lg:px-6 flex items-center justify-between">
        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="relative">
            <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#A0A0AB]" />
            <input
              type="text"
              placeholder="Search streams, users..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 pl-10 pr-4 bg-[#0F0F16] border border-white/10 rounded-lg text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] transition-colors"
              data-testid="search-input"
            />
          </div>
        </form>

        {/* Actions */}
        <div className="flex items-center gap-3 ml-4">
          {user ? (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="relative text-[#A0A0AB] hover:text-white hover:bg-white/10"
                data-testid="notifications-btn"
              >
                <Bell className="w-5 h-5" />
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-2 hover:opacity-80 transition-opacity" data-testid="user-menu-btn">
                    <Avatar className="w-8 h-8">
                      <AvatarImage src={user.avatar_url} alt={user.display_name || user.username} />
                      <AvatarFallback className="bg-[#292938] text-[#00E5FF]">
                        {(user.display_name || user.username)?.charAt(0).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56 bg-[#0F0F16] border-white/10">
                  <div className="px-3 py-2">
                    <p className="text-sm font-medium text-white">{user.display_name || user.username}</p>
                    <p className="text-xs text-[#A0A0AB]">@{user.username}</p>
                  </div>
                  <DropdownMenuSeparator className="bg-white/10" />
                  <DropdownMenuItem asChild>
                    <Link to={`/user/${user.username}`} className="flex items-center gap-2 text-[#A0A0AB] hover:text-white cursor-pointer">
                      <User className="w-4 h-4" />
                      Profile
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/dashboard" className="flex items-center gap-2 text-[#A0A0AB] hover:text-white cursor-pointer">
                      <Broadcast className="w-4 h-4" />
                      Dashboard
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-white/10" />
                  <DropdownMenuItem 
                    onClick={handleLogout}
                    className="flex items-center gap-2 text-red-400 hover:text-red-300 cursor-pointer"
                    data-testid="logout-btn"
                  >
                    <SignOut className="w-4 h-4" />
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                onClick={() => navigate('/auth')}
                className="text-[#A0A0AB] hover:text-white hover:bg-white/10"
                data-testid="login-btn"
              >
                Log in
              </Button>
              <Button
                onClick={() => navigate('/auth?mode=register')}
                className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]"
                data-testid="signup-btn"
              >
                Sign up
              </Button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
