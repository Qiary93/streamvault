import React, { useEffect, useState } from 'react';
import { LiveKitRoom, VideoTrack, useRemoteParticipants, useLocalParticipant, useTracks, RoomAudioRenderer } from '@livekit/components-react';
import '@livekit/components-styles';
import { Track } from 'livekit-client';
import { Broadcast, Camera, CameraSlash, Microphone, MicrophoneSlash, Monitor } from '@phosphor-icons/react';
import { Button } from './ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

function StreamerControls() {
  const { localParticipant } = useLocalParticipant();
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [micEnabled, setMicEnabled] = useState(true);

  const toggleCamera = async () => {
    if (localParticipant) {
      await localParticipant.setCameraEnabled(!cameraEnabled);
      setCameraEnabled(!cameraEnabled);
    }
  };

  const toggleMic = async () => {
    if (localParticipant) {
      await localParticipant.setMicrophoneEnabled(!micEnabled);
      setMicEnabled(!micEnabled);
    }
  };

  const shareScreen = async () => {
    if (localParticipant) {
      await localParticipant.setScreenShareEnabled(true);
    }
  };

  return (
    <div className="flex items-center gap-2 p-3 bg-[#0F0F16] border-t border-white/5">
      <Button
        onClick={toggleCamera}
        variant="ghost"
        size="sm"
        className={`${cameraEnabled ? 'text-white hover:text-[#00E5FF]' : 'text-red-400 hover:text-red-300'} hover:bg-white/10`}
        data-testid="toggle-camera-btn"
      >
        {cameraEnabled ? <Camera className="w-5 h-5" /> : <CameraSlash className="w-5 h-5" />}
      </Button>
      <Button
        onClick={toggleMic}
        variant="ghost"
        size="sm"
        className={`${micEnabled ? 'text-white hover:text-[#00E5FF]' : 'text-red-400 hover:text-red-300'} hover:bg-white/10`}
        data-testid="toggle-mic-btn"
      >
        {micEnabled ? <Microphone className="w-5 h-5" /> : <MicrophoneSlash className="w-5 h-5" />}
      </Button>
      <Button
        onClick={shareScreen}
        variant="ghost"
        size="sm"
        className="text-white hover:text-[#00E5FF] hover:bg-white/10"
        data-testid="share-screen-btn"
      >
        <Monitor className="w-5 h-5" />
      </Button>
    </div>
  );
}

function VideoDisplay() {
  const tracks = useTracks([Track.Source.Camera, Track.Source.ScreenShare]);
  
  if (tracks.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0F0F16]">
        <div className="text-center">
          <Broadcast className="w-16 h-16 text-[#292938] mx-auto mb-4" />
          <p className="text-[#A0A0AB]">Waiting for stream to start...</p>
        </div>
      </div>
    );
  }

  // Prefer screen share, fallback to camera
  const screenTrack = tracks.find(t => t.source === Track.Source.ScreenShare);
  const cameraTrack = tracks.find(t => t.source === Track.Source.Camera);
  const displayTrack = screenTrack || cameraTrack;

  return (
    <div className="w-full h-full relative bg-black">
      {displayTrack && (
        <VideoTrack
          trackRef={displayTrack}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      )}
      <RoomAudioRenderer />
    </div>
  );
}

export function LiveKitViewer({ roomName, streamThumbnail }) {
  const [token, setToken] = useState(null);
  const [serverUrl, setServerUrl] = useState(null);
  const [error, setError] = useState(null);
  const [connecting, setConnecting] = useState(true);

  useEffect(() => {
    const getToken = async () => {
      try {
        const viewerId = `viewer_${Math.random().toString(36).slice(2, 10)}`;
        const response = await axios.post(`${API}/api/livekit/token/viewer`, {
          room_name: roomName,
          viewer_id: viewerId,
          viewer_name: 'Viewer'
        });
        setToken(response.data.token);
        setServerUrl(response.data.server_url);
      } catch (err) {
        console.error('Failed to get viewer token:', err);
        setError('Could not connect to stream');
      } finally {
        setConnecting(false);
      }
    };

    if (roomName) {
      getToken();
    }
  }, [roomName]);

  if (connecting) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0F0F16]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !token || !serverUrl) {
    // Show thumbnail as fallback
    return (
      <div className="w-full h-full relative bg-black">
        {streamThumbnail ? (
          <img src={streamThumbnail} alt="Stream" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#0F0F16] to-[#1A1A24]">
            <div className="text-center">
              <Broadcast className="w-16 h-16 text-[#292938] mx-auto mb-4" />
              <p className="text-[#A0A0AB]">{error || 'Stream preview'}</p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <LiveKitRoom
      token={token}
      serverUrl={serverUrl}
      connect={true}
      video={false}
      audio={true}
      style={{ width: '100%', height: '100%' }}
    >
      <VideoDisplay />
    </LiveKitRoom>
  );
}

export function LiveKitStreamer({ roomName, onReady }) {
  const [token, setToken] = useState(null);
  const [serverUrl, setServerUrl] = useState(null);
  const [error, setError] = useState(null);
  const [connecting, setConnecting] = useState(true);

  useEffect(() => {
    const getToken = async () => {
      try {
        const response = await axios.post(`${API}/api/livekit/token/streamer`, {
          room_name: roomName
        }, { withCredentials: true });
        setToken(response.data.token);
        setServerUrl(response.data.server_url);
        if (onReady) onReady();
      } catch (err) {
        console.error('Failed to get streamer token:', err);
        setError('Could not start streaming');
      } finally {
        setConnecting(false);
      }
    };

    if (roomName) {
      getToken();
    }
  }, [roomName]);

  if (connecting) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0F0F16]">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#A0A0AB]">Setting up stream...</p>
        </div>
      </div>
    );
  }

  if (error || !token || !serverUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0F0F16]">
        <p className="text-red-400">{error || 'Failed to connect'}</p>
      </div>
    );
  }

  return (
    <LiveKitRoom
      token={token}
      serverUrl={serverUrl}
      connect={true}
      video={true}
      audio={true}
      style={{ width: '100%', height: '100%' }}
    >
      <div className="w-full h-full flex flex-col">
        <div className="flex-1">
          <VideoDisplay />
        </div>
        <StreamerControls />
      </div>
    </LiveKitRoom>
  );
}
