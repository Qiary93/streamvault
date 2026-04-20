import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import { Database, Shield, Check, Trash, Eye, EyeSlash, Globe, Upload, CurrencyDollar, Clock, X as XIcon, Bank, ToggleRight } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import AdminMonetization from '../components/AdminMonetization';
import AdminOtherSettings from '../components/AdminOtherSettings';
import AdminSmtpSettings from '../components/AdminSmtpSettings';
import AdminEmailTemplates from '../components/AdminEmailTemplates';
import AdminAutoPayoutSweep from '../components/AdminAutoPayoutSweep';
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


function WithdrawRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payoutSettings, setPayoutSettings] = useState({ automated_enabled: false });
  const [savingToggle, setSavingToggle] = useState(false);

  useEffect(() => {
    fetchRequests();
    fetchPayoutSettings();
  }, []);

  const fetchRequests = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/withdrawals`, { withCredentials: true });
      setRequests(res.data);
    } catch (e) {
      console.error('Error fetching withdrawals:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchPayoutSettings = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/payout-settings`, { withCredentials: true });
      setPayoutSettings(res.data);
    } catch {}
  };

  const toggleAutomated = async () => {
    setSavingToggle(true);
    try {
      const next = !payoutSettings.automated_enabled;
      await axios.put(`${API}/api/admin/payout-settings`, {
        automated_enabled: next,
        platform_fee_percent: payoutSettings.platform_fee_percent || 0,
      }, { withCredentials: true });
      setPayoutSettings(prev => ({ ...prev, automated_enabled: next }));
      toast.success(`Automated payouts ${next ? 'ENABLED' : 'DISABLED'}`);
    } catch (err) {
      toast.error('Failed to update setting');
    } finally {
      setSavingToggle(false);
    }
  };

  const handleApprove = async (id) => {
    const auto = payoutSettings.automated_enabled;
    const msg = auto
      ? 'Approve and send automated payout via Stripe Connect? Funds will be transferred to the streamer\'s bank.'
      : 'Approve this withdrawal? Funds will need to be sent manually to the streamer.';
    if (!window.confirm(msg)) return;
    try {
      const res = await axios.put(`${API}/api/admin/withdrawals/${id}/approve`, {}, { withCredentials: true });
      toast.success(res.data?.payout_info?.method === 'stripe_connect' ? 'Approved & payout queued via Stripe!' : 'Withdrawal approved');
      fetchRequests();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to approve');
    }
  };

  const handleReject = async (id) => {
    const reason = prompt('Rejection reason (optional):') || 'Request rejected by admin';
    try {
      await axios.put(`${API}/api/admin/withdrawals/${id}/reject`, { reason }, { withCredentials: true, headers: { 'Content-Type': 'application/json' } });
      toast.success('Withdrawal rejected');
      fetchRequests();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to reject');
    }
  };

  if (loading) return null;

  const pending = requests.filter(r => r.status === 'pending');
  const processed = requests.filter(r => r.status !== 'pending');

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mt-6" data-testid="withdraw-requests-section">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
        <div className="flex items-center gap-3">
          <Bank className="w-6 h-6 text-green-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Withdraw Requests</h2>
            <p className="text-sm text-[#A0A0AB]">{pending.length} pending request{pending.length !== 1 ? 's' : ''}</p>
          </div>
        </div>
        <button
          onClick={toggleAutomated}
          disabled={savingToggle}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${payoutSettings.automated_enabled ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-[#1A1A24] text-[#A0A0AB] border border-white/10'}`}
          data-testid="automated-payout-toggle"
        >
          <ToggleRight weight={payoutSettings.automated_enabled ? 'fill' : 'regular'} className="w-5 h-5" />
          Automated payouts: {payoutSettings.automated_enabled ? 'ON' : 'OFF'}
        </button>
      </div>

      <div className={`mb-4 p-3 rounded-lg text-xs ${payoutSettings.automated_enabled ? 'bg-green-500/5 border border-green-500/20 text-green-200' : 'bg-[#1A1A24] text-[#A0A0AB]'}`}>
        {payoutSettings.automated_enabled
          ? 'When ON: approving a withdrawal triggers an automatic Stripe Connect transfer + payout to the streamer\'s connected bank account.'
          : 'When OFF: approved withdrawals are marked completed but you must transfer the funds manually (e.g. via IBAN bank transfer).'}
      </div>

      {pending.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-bold text-yellow-400 uppercase tracking-wider mb-3">Pending</h3>
          <div className="space-y-3">
            {pending.map((wd) => (
              <div key={wd.withdrawal_id} className="p-4 bg-[#1A1A24] border border-yellow-500/20 rounded-lg">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-white font-semibold">{wd.first_name} {wd.last_name}</p>
                    <p className="text-sm text-[#A0A0AB]">@{wd.username} - {wd.display_name}</p>
                  </div>
                  <span className="text-xl font-bold text-green-400">${wd.amount?.toFixed(2)}</span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                  <div>
                    <p className="text-xs text-[#A0A0AB]">IBAN</p>
                    <p className="text-white font-mono text-xs">{wd.iban}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[#A0A0AB]">PayPal</p>
                    <p className="text-white text-xs">{wd.paypal_email || 'Not provided'}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-[#A0A0AB]">{new Date(wd.created_at).toLocaleString()}</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleReject(wd.withdrawal_id)}
                      className="px-4 py-1.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg text-sm font-medium hover:bg-red-500/20 transition-colors"
                      data-testid={`reject-${wd.withdrawal_id}`}
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleApprove(wd.withdrawal_id)}
                      className="px-4 py-1.5 bg-green-500 text-white rounded-lg text-sm font-bold hover:bg-green-600 transition-colors"
                      data-testid={`approve-${wd.withdrawal_id}`}
                    >
                      Approve
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {processed.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-[#A0A0AB] uppercase tracking-wider mb-3">History</h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {processed.map((wd) => (
              <div key={wd.withdrawal_id} className="flex items-center justify-between p-3 bg-[#1A1A24] rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${wd.status === 'completed' ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10'}`}>
                    {wd.status === 'completed' ? <Check className="w-3 h-3" /> : <XIcon className="w-3 h-3" />}
                    {wd.status}
                  </span>
                  <div>
                    <p className="text-sm text-white">{wd.first_name} {wd.last_name} - ${wd.amount?.toFixed(2)}</p>
                    <p className="text-xs text-[#A0A0AB]">@{wd.username}</p>
                  </div>
                </div>
                <p className="text-xs text-[#A0A0AB]">{new Date(wd.created_at).toLocaleDateString()}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {requests.length === 0 && (
        <p className="text-center text-[#A0A0AB] py-8">No withdrawal requests yet</p>
      )}
    </div>
  );
}


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
  const [siteSettings, setSiteSettings] = useState({ title: 'StreamVault', description: '', icon_url: '' });
  const [savingSite, setSavingSite] = useState(false);

  useEffect(() => {
    fetchConfig();
    fetchSiteSettings();
  }, []);

  const fetchSiteSettings = async () => {
    try {
      const res = await axios.get(`${API}/api/admin/site-settings`, { withCredentials: true });
      if (res.data) setSiteSettings({ title: res.data.title || 'StreamVault', description: res.data.description || '', icon_url: res.data.icon_url || '' });
    } catch (e) {}
  };

  const saveSiteSettings = async (e) => {
    e.preventDefault();
    setSavingSite(true);
    try {
      await axios.post(`${API}/api/admin/site-settings`, siteSettings, { withCredentials: true });
      toast.success('Site settings saved!');
    } catch (err) {
      toast.error('Failed to save site settings');
    } finally {
      setSavingSite(false);
    }
  };

  const handleIconUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`${API}/api/upload/thumbnail`, formData, { withCredentials: true, headers: { 'Content-Type': 'multipart/form-data' } });
      setSiteSettings(prev => ({ ...prev, icon_url: `${API}${res.data.url}` }));
      toast.success('Icon uploaded');
    } catch (err) {
      toast.error('Failed to upload icon');
    }
  };

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

      {/* Site Settings */}
      <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6 mb-6" data-testid="site-settings-section">
        <div className="flex items-center gap-3 mb-6">
          <Globe className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">Site Settings</h2>
            <p className="text-sm text-[#A0A0AB]">Website title, description, and icon</p>
          </div>
        </div>
        <form onSubmit={saveSiteSettings} className="space-y-4">
          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">Website Title</label>
            <Input value={siteSettings.title} onChange={(e) => setSiteSettings(prev => ({ ...prev, title: e.target.value }))} className="bg-[#1A1A24] border-white/10 text-white" data-testid="site-title-input" />
          </div>
          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">Website Description</label>
            <textarea value={siteSettings.description} onChange={(e) => setSiteSettings(prev => ({ ...prev, description: e.target.value }))} rows={3} className="w-full p-3 bg-[#1A1A24] border border-white/10 rounded-md text-white placeholder-[#A0A0AB] focus:outline-none focus:border-[#00E5FF] resize-none" data-testid="site-description-input" />
          </div>
          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1.5">Website Icon (Favicon)</label>
            <div className="flex items-center gap-4">
              {siteSettings.icon_url && <img src={siteSettings.icon_url} alt="Icon" className="w-10 h-10 rounded" />}
              <label className="flex items-center gap-2 px-4 py-2 bg-[#1A1A24] border border-white/10 rounded-lg cursor-pointer hover:border-[#00E5FF]/50 transition-colors text-sm text-[#A0A0AB]">
                <Upload className="w-4 h-4" /> Upload icon
                <input type="file" accept="image/*" onChange={handleIconUpload} className="hidden" data-testid="icon-upload-input" />
              </label>
            </div>
          </div>
          <Button type="submit" disabled={savingSite} className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC] disabled:opacity-50" data-testid="save-site-btn">
            {savingSite ? 'Saving...' : 'Save Site Settings'}
          </Button>
        </form>
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

      {/* Other Settings */}
      <AdminOtherSettings />

      {/* SMTP / Email verification */}
      <AdminSmtpSettings />

      {/* Email templates */}
      <AdminEmailTemplates />

      {/* Monetization */}
      <AdminMonetization />

      {/* Withdraw Requests */}
      <WithdrawRequests />

      {/* Auto-payout scheduling */}
      <AdminAutoPayoutSweep />
    </div>
  );
}
