import React from 'react';
import { Link } from 'react-router-dom';
import { Eye } from '@phosphor-icons/react';

export default function CategoryCard({ category }) {
  return (
    <Link 
      to={`/category/${category.category_id}`}
      className="group stream-card block bg-[#0F0F16] border border-white/5 rounded-xl overflow-hidden"
      data-testid={`category-card-${category.category_id}`}
    >
      {/* Image */}
      <div className="relative aspect-[3/4] bg-[#1A1A24]">
        {category.image_url ? (
          <img 
            src={category.image_url} 
            alt={category.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#0F0F16] to-[#292938]">
            <span className="text-2xl font-bold text-[#3D3D52]">{category.name?.charAt(0)}</span>
          </div>
        )}
        
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
        
        {/* Category name */}
        <div className="absolute bottom-0 left-0 right-0 p-3">
          <h3 className="text-sm font-bold text-white">{category.name}</h3>
          {category.stream_count > 0 && (
            <div className="flex items-center gap-1 mt-1 text-xs text-[#A0A0AB]">
              <Eye className="w-3.5 h-3.5" />
              {category.stream_count} live
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
