import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import { Database, Shield, Check, Trash, Eye, EyeSlash } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const WASABI_REGIONS = [
  { value: 'us-east-1', label: 'US East 1 (N. Virginia)' },
  { value: 'us-east-2', label: 'US East 2 (N. Virginia)' },
  { value: 'us-central-1', label: 'US Central 1 (Texas)' },
  { value: 'us-west-1', label: 'US West 1 (Oregon)' },
  { value: 'eu-central-1', label: 'EU Central 1 (Amsterdam)' },
  { value: 'eu-central-2', label: 'EU Central 2 (Frankfurt)' },
  { value: 'eu-west-1', label: 'EU West 1 (London)' },
  { value: 'eu-west-2', label: 'EU West 2 (Paris)' },
  { value: 'ap-northeast-1', label: 'AP Northeast 1 (Tokyo)' },
  { value: 'ap-northeast-2', label: 'AP Northeast 2 (Osaka)' },
  { value: 'ap-southeast-1', label: 'AP Southeast 1 (Singapore)' },
  { value: 'ap-southeast-2', label: 'AP Southeast 2 (Sydney)' },
];

export default function AdminPage() {
  const { user } = useAuth();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [form, setForm] = useState({
    provider: 'wasabi',
    endpoint: 's3.wasabisys.com',
    bucket: '',
    region: 'us-east-1',
    access_key: '',
    secret_key: '',
    force_path_style: true
  });

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API}/api/admin/storage-config`, {
        withCredentials: true
      });
      if (response.data && response.data.configured) {
        setConfig(response.data);
        setForm(prev => ({
          ...prev,
          provider: response.data.provider || 'wasabi',
          endpoint: response.data.endpoint || 's3.wasabisys.com',
          bucket: response.data.bucket || '',
          region: response.data.region || 'us-east-1',
          access_key: response.data.access_key || '',
          secret_key: '', // Don't show existing secret
          force_path_style: response.data.force_path_style !== false
        }));
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.bucket || !form.access_key || !form.endpoint) {
      toast.error('Please fill in all required fields');
      return;
    }

    // If editing existing config and secret_key is empty, user hasn't changed it
    if (config?.configured && !form.secret_key) {
      toast.error('Please enter the secret key to update the configuration');
      return;
    }

    setSaving(true);
    try {
      await axios.post(`${API}/api/admin/storage-config`, form, {
        withCredentials: true
      });
      toast.success('Storage configuration saved!');
      fetchConfig();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete the storage configuration?')) return;
    
    try {
      await axios.delete(`${API}/api/admin/storage-config`, {
        withCredentials: true
      });
      setConfig(null);
      setForm({
        provider: 'wasabi',
        endpoint: 's3.wasabisys.com',
        bucket: '',
        region: 'us-east-1',
        access_key: '',
        secret_key: '',
        force_path_style: true
      });
      toast.success('Configuration deleted');
    } catch (error) {
      toast.error('Failed to delete configuration');
    }
  };

  if (!user) return null;
  if (user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6 max-w-3xl" data-testid="admin-page">
      <div className="flex items-center gap-3 mb-8">
        <Shield weight="fill" className="w-8 h-8 text-[#00E5FF]" />
        <h1 className="text-2xl lg:text-3xl font-bold text-white font-['Outfit']">Admin Panel</h1>
      </div>

      {/* S3 Storage Configuration */}
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="storage-config-section">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Database className="w-6 h-6 text-[#00E5FF]" />
            <div>
              <h2 className="text-lg font-semibold text-white">Wasabi S3 Storage</h2>
              <p className="text-sm text-[#A0A0AB]">Configure storage for stream recordings (LiveKit Egress)</p>
            </div>
          </div>
          {config?.configured && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-green-400 bg-green-500/10 px-3 py-1 rounded-full flex items-center gap-1">
                <Check className="w-3 h-3" /> Configured
              </span>
            </div>
          )}
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">Provider</label>
              <Select value={form.provider} onValueChange={(v) => setForm(prev => ({ ...prev, provider: v }))}>
                <SelectTrigger className="bg-[#1A1A24] border-white/10 text-white" data-testid="provider-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F16] border-white/10">
                  <SelectItem value="wasabi" className="text-white">Wasabi</SelectItem>
                  <SelectItem value="aws" className="text-white">AWS S3</SelectItem>
                  <SelectItem value="other" className="text-white">Other S3-compatible</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1.5">Region *</label>
              <Select value={form.region} onValueChange={(v) => {
                const endpoint = form.provider === 'wasabi' ? `s3.${v}.wasabisys.com` : form.endpoint;
                setForm(prev => ({ ...prev, region: v, endpoint }));
              }}>
                <SelectTrigger className="bg-[#1A1A24] border-white/10 text-white" data-testid="region-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#0F0F16] border-white/10 max-h-60">
                  {WASABI_REGIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value} className="text-white">{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">S3 Endpoint *</label>
            <Input
              value={form.endpoint}
              onChange={(e) => setForm(prev => ({ ...prev, endpoint: e.target.value }))}
              placeholder="s3.us-east-1.wasabisys.com"
              className="bg-[#1A1A24] border-white/10 text-white"
              data-testid="endpoint-input"
            />
            <p className="text-xs text-[#A0A0AB] mt-1">For Wasabi: s3.REGION.wasabisys.com</p>
          </div>

          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">Bucket Name *</label>
            <Input
              value={form.bucket}
              onChange={(e) => setForm(prev => ({ ...prev, bucket: e.target.value }))}
              placeholder="my-stream-recordings"
              className="bg-[#1A1A24] border-white/10 text-white"
              data-testid="bucket-input"
            />
          </div>

          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">Access Key *</label>
            <Input
              value={form.access_key}
              onChange={(e) => setForm(prev => ({ ...prev, access_key: e.target.value }))}
              placeholder="Your Wasabi access key"
              className="bg-[#1A1A24] border-white/10 text-white font-mono"
              data-testid="access-key-input"
            />
          </div>

          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">Secret Key *</label>
            <div className="relative">
              <Input
                type={showSecret ? 'text' : 'password'}
                value={form.secret_key}
                onChange={(e) => setForm(prev => ({ ...prev, secret_key: e.target.value }))}
                placeholder={config?.configured ? 'Enter new secret key to update' : 'Your Wasabi secret key'}
                className="bg-[#1A1A24] border-white/10 text-white font-mono pr-10"
                data-testid="secret-key-input"
              />
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#A0A0AB] hover:text-white"
              >
                {showSecret ? <EyeSlash className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="flex items-center gap-4 pt-2">
            <Button
              type="submit"
              disabled={saving}
              className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] disabled:opacity-50"
              data-testid="save-storage-btn"
            >
              {saving ? 'Saving...' : (config?.configured ? 'Update Configuration' : 'Save Configuration')}
            </Button>
            
            {config?.configured && (
              <Button
                type="button"
                onClick={handleDelete}
                variant="ghost"
                className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                data-testid="delete-storage-btn"
              >
                <Trash className="w-4 h-4 mr-2" /> Delete
              </Button>
            )}
          </div>
        </form>

        {/* Info box */}
        <div className="mt-6 p-4 bg-[#1A1A24] rounded-lg border border-white/5">
          <h3 className="text-sm font-semibold text-white mb-2">How to set up Wasabi:</h3>
          <ol className="text-xs text-[#A0A0AB] space-y-1.5 list-decimal pl-4">
            <li>Sign up at <a href="https://wasabi.com" target="_blank" rel="noopener noreferrer" className="text-[#00E5FF] hover:underline">wasabi.com</a></li>
            <li>Create a new bucket in your preferred region</li>
            <li>Go to Access Keys and create a new key pair</li>
            <li>Enter the bucket name, access key, and secret key above</li>
            <li>Select the matching region for your bucket</li>
            <li>Stream recordings will be saved as HLS segments in your bucket</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
