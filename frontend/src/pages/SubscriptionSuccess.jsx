import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { CheckCircle, XCircle, ArrowLeft } from '@phosphor-icons/react';
import { Button } from '../components/ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function SubscriptionSuccess() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('loading');
  const [paymentData, setPaymentData] = useState(null);

  useEffect(() => {
    const sessionId = searchParams.get('session_id');
    
    if (!sessionId) {
      setStatus('cancelled');
      return;
    }

    const checkStatus = async (attempts = 0) => {
      try {
        const response = await axios.get(`${API}/api/subscriptions/status/${sessionId}`, {
          withCredentials: true
        });
        
        if (response.data.payment_status === 'paid') {
          setPaymentData(response.data);
          setStatus('success');
        } else if (response.data.status === 'expired') {
          setStatus('failed');
        } else if (attempts < 5) {
          setTimeout(() => checkStatus(attempts + 1), 2000);
        } else {
          setStatus('pending');
        }
      } catch (error) {
        setStatus('failed');
      }
    };

    checkStatus();
  }, [searchParams]);

  return (
    <div className="min-h-[50vh] flex items-center justify-center p-6" data-testid="subscription-result">
      <div className="text-center max-w-md">
        {status === 'loading' && (
          <>
            <div className="w-16 h-16 border-4 border-[#00E5FF] border-t-transparent rounded-full animate-spin mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-white mb-2">Processing Subscription</h2>
            <p className="text-[#A0A0AB]">Please wait while we verify your subscription...</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle weight="fill" className="w-20 h-20 text-green-400 mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-white mb-2">Subscription Active!</h2>
            <p className="text-[#A0A0AB] mb-6">
              Your subscription of ${paymentData?.amount?.toFixed(2)} is now active for 30 days!
            </p>
            <Link to="/">
              <Button className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]">
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Streams
              </Button>
            </Link>
          </>
        )}

        {status === 'cancelled' && (
          <>
            <XCircle weight="fill" className="w-20 h-20 text-[#A0A0AB] mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-white mb-2">Subscription Cancelled</h2>
            <p className="text-[#A0A0AB] mb-6">No charges were made.</p>
            <Link to="/">
              <Button className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]">
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Streams
              </Button>
            </Link>
          </>
        )}

        {status === 'failed' && (
          <>
            <XCircle weight="fill" className="w-20 h-20 text-red-400 mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-white mb-2">Payment Failed</h2>
            <p className="text-[#A0A0AB] mb-6">Something went wrong. Please try again.</p>
            <Link to="/">
              <Button className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]">
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Streams
              </Button>
            </Link>
          </>
        )}

        {status === 'pending' && (
          <>
            <div className="w-20 h-20 border-4 border-yellow-400 border-dashed rounded-full mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-white mb-2">Processing</h2>
            <p className="text-[#A0A0AB] mb-6">Your payment is being processed.</p>
            <Link to="/">
              <Button className="bg-[#00E5FF] text-black font-bold hover:bg-[#00B3CC]">
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Streams
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
