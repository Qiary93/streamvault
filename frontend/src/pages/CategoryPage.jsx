import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from '@phosphor-icons/react';
import StreamCard from '../components/StreamCard';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function CategoryPage() {
  const { categoryId } = useParams();
  const [category, setCategory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCategory = async () => {
      try {
        const response = await axios.get(`${API}/api/categories/${categoryId}`);
        setCategory(response.data);
      } catch (error) {
        console.error('Error fetching category:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCategory();
  }, [categoryId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!category) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <h2 className="text-xl font-bold text-white mb-2">Category not found</h2>
        <Link to="/browse" className="text-[#00E5FF] hover:underline">Browse categories</Link>
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6" data-testid="category-page">
      {/* Back button */}
      <Link 
        to="/browse" 
        className="inline-flex items-center gap-2 text-[#A0A0AB] hover:text-white mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Browse
      </Link>

      {/* Category Header */}
      <div className="flex items-start gap-4 mb-8">
        {category.image_url && (
          <div className="w-24 h-32 rounded-lg overflow-hidden flex-shrink-0">
            <img 
              src={category.image_url} 
              alt={category.name}
              className="w-full h-full object-cover"
            />
          </div>
        )}
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold text-white mb-2 font-['Outfit']" data-testid="category-title">
            {category.name}
          </h1>
          {category.description && (
            <p className="text-[#A0A0AB] mb-2">{category.description}</p>
          )}
          <p className="text-sm text-[#00E5FF]">
            {category.streams?.length || 0} live streams
          </p>
        </div>
      </div>

      {/* Streams */}
      {category.streams && category.streams.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {category.streams.map((stream) => (
            <StreamCard key={stream.stream_id} stream={stream} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-[#0F0F16] rounded-xl">
          <p className="text-[#A0A0AB]">No live streams in this category</p>
        </div>
      )}
    </div>
  );
}
