import React from 'react';

const Loading = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-app">
      <div className="text-center animate-fade-in">
        <div className="inline-block w-9 h-9 border-2 border-line border-t-accent rounded-full animate-spin"></div>
        <p className="mt-3 text-muted text-[13px]">Loading your watchlist...</p>
      </div>
    </div>
  );
};

export default Loading;
