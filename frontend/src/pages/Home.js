import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import api from '../utils/api';
import Loading from '../components/Loading';

const nseSession = () => {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date());
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]));
  const day = map.weekday;
  const minutes = Number(map.hour) * 60 + Number(map.minute);
  const weekday = day !== 'Sat' && day !== 'Sun';
  const open = weekday && minutes >= 9 * 60 + 15 && minutes <= 15 * 60 + 30;
  return { open, label: open ? 'Market Open' : 'Market Closed' };
};

const Home = () => {
  const { user } = useAuth();
  const { theme } = useTheme();
  const [digest, setDigest] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [watchlistPrices, setWatchlistPrices] = useState({});
  const [freshness, setFreshness] = useState(null);
  const [conflicts, setConflicts] = useState({});
  const [marketData, setMarketData] = useState(null);
  const [newStock, setNewStock] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterTier, setFilterTier] = useState('all');

  const fetchData = async (filter = filterTier, forceReset = false) => {
    try {
      setLoading(true);
      let url = '/digest/since-last-check';
      const params = new URLSearchParams();
      
      // FIX: Only add filter param if NOT 'all'
      if (filter && filter !== 'all') {
        params.append('filter_tier', filter);
        params.append('update_checkpoint', 'false');
      }
      // If filter is 'all', send NO filter_tier (backend shows everything)
      
      if (forceReset) {
        await api.post('/digest/checkpoint/reset');
      }
      
      const queryString = params.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
      
      const [digestRes, watchlistRes, freshnessRes, marketRes] = await Promise.all([
        api.get(url),
        api.get('/watchlist/'),
        api.get('/watchlist/freshness'),
        api.get('/market/indices')
      ]);
      
      // DEDUPLICATE EVENTS: Keep only highest score per symbol+event_type
      const dedupedItems = {};
      (digestRes.data?.items || []).forEach((item) => {
        const key = `${item.symbol}_${item.event_type}`;
        if (!dedupedItems[key] || item.significance_score > dedupedItems[key].significance_score) {
          dedupedItems[key] = item;
        }
      });
      digestRes.data.items = Object.values(dedupedItems);
      
      setDigest(digestRes.data);
      setWatchlist(watchlistRes.data);
      setFreshness(freshnessRes.data);
      setMarketData(marketRes.data);
      
      // Fetch real prices for watchlist
      if (watchlistRes.data.length > 0) {
        const pricePromises = watchlistRes.data.map(stock => 
          api.get(`/watchlist/${stock.symbol}/price?include_conflict=true`)
            .then(res => ({ symbol: stock.symbol, data: res.data }))
            .catch(() => ({ symbol: stock.symbol, data: null }))
        );
        
        const priceResults = await Promise.all(pricePromises);
        const priceMap = {};
        const conflictsMap = {};
        priceResults.forEach(({ symbol, data }) => {
          if (data) {
            priceMap[symbol] = data.price;
            if (data.conflict) {
              conflictsMap[symbol] = data.conflict;
            }
          }
        });
        setWatchlistPrices(priceMap);
        setConflicts(conflictsMap);
      }
      
    } catch (err) {
      setError('Failed to load data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData('all');
  }, []);

  const handleFilterChange = (filter) => {
    setFilterTier(filter);
    fetchData(filter, false);
  };

  const addStock = async (e) => {
    e.preventDefault();
    if (!newStock.trim()) return;
    try {
      await api.post('/watchlist/', { symbol: newStock.toUpperCase(), quantity: 100 });
      setNewStock('');
      await fetchData(filterTier);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add stock');
    }
  };

  const removeStock = async (symbol) => {
    try {
      await api.delete(`/watchlist/${symbol}`);
      await fetchData(filterTier);
    } catch (err) {
      setError('Failed to remove stock');
    }
  };

  const resetCheckpoint = async () => {
    await fetchData(filterTier, true);
  };

  if (loading) return <Loading />;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = user?.email?.split('@')[0];
  const market = nseSession();

  const attentionBySymbol = {};
  (digest?.items || []).forEach((item) => {
    const current = attentionBySymbol[item.symbol];
    if (!current || item.tier === 'High attention' || (item.tier === 'Worth knowing' && current === 'Normal')) {
      attentionBySymbol[item.symbol] = item.tier;
    }
  });

  const hasStaleData = freshness?.status === 'has_stale';
  const lastUpdated = freshness?.last_updated;
  const hasConflicts = Object.keys(conflicts).length > 0;
  const topEvents = digest?.items?.slice(0, 3) || [];

  const isDark = theme === 'dark';

  const totalEvents = digest?.items?.length || 0;
  const displayMessage = totalEvents > 0 
    ? `${Math.min(totalEvents, 3)} things deserve your attention`
    : 'Nothing significant changed';

  // Use real market data or fallback
  const nifty = marketData?.nifty || { value: 24716.20, change: 0.42 };
  const sensex = marketData?.sensex || { value: 80432.15, change: 0.38 };

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#0a0a14]' : 'bg-[#f5f7fa]'}`}>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className={`text-xl sm:text-2xl font-semibold tracking-tight ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>
            {greeting}, {firstName}
          </h1>
          <p className={isDark ? 'text-gray-400 text-sm mt-0.5' : 'text-[#636e72] text-sm mt-0.5'}>
            Here's what changed while you were away.
          </p>
        </div>

        {/* Market Summary */}
        <div className={`grid grid-cols-3 gap-4 ${isDark ? 'bg-[#141420] border-[#2a2a45]' : 'bg-white border-[#e9ecef]'} rounded-xl p-4 shadow-sm border mb-6`}>
          <div>
            <p className={`text-[11px] font-medium tracking-wide ${isDark ? 'text-gray-400' : 'text-[#636e72]'}`}>NIFTY 50</p>
            <p className={`text-base font-semibold tabular ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>{nifty.value.toFixed(2)}</p>
            <p className={`text-sm ${nifty.change >= 0 ? 'text-[#00b894]' : 'text-[#e17055]'}`}>
              {nifty.change >= 0 ? '+' : ''}{nifty.change.toFixed(2)}%
            </p>
          </div>
          <div>
            <p className={`text-[11px] font-medium tracking-wide ${isDark ? 'text-gray-400' : 'text-[#636e72]'}`}>SENSEX</p>
            <p className={`text-base font-semibold tabular ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>{sensex.value.toFixed(2)}</p>
            <p className={`text-sm ${sensex.change >= 0 ? 'text-[#00b894]' : 'text-[#e17055]'}`}>
              {sensex.change >= 0 ? '+' : ''}{sensex.change.toFixed(2)}%
            </p>
          </div>
          <div className="flex flex-col items-end justify-center">
            <span className={`text-[11px] font-medium ${market.open ? 'text-[#00b894]' : isDark ? 'text-gray-500' : 'text-[#636e72]'}`}>
              ● {market.label}
            </span>
          </div>
        </div>

        {/* Warnings */}
        {hasStaleData && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-2.5 rounded-lg mb-4 text-sm">
            ⚠️ Some data may be delayed. Last updated: {lastUpdated ? new Date(lastUpdated).toLocaleString() : 'Unknown'}
          </div>
        )}
        {hasConflicts && (
          <div className="bg-orange-50 border border-orange-200 text-orange-700 px-4 py-2.5 rounded-lg mb-4 text-sm">
            ⚠️ Data discrepancy detected for {Object.keys(conflicts).join(', ')}. Showing primary source.
          </div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-2.5 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}

        {/* Since You Last Checked - ADDED ID FOR SCROLLING */}
        <div id="digest" className="mb-8">
          <div className="flex flex-wrap justify-between items-center gap-2 mb-4">
            <div>
              <h2 className={`text-lg font-semibold tracking-tight ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>Since you last checked</h2>
              <p className={isDark ? 'text-gray-400 text-sm' : 'text-[#636e72] text-sm'}>
                {displayMessage}
                {totalEvents > 3 && ` +${totalEvents - 3} other changes`}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className={`flex ${isDark ? 'bg-[#1a1a2e]' : 'bg-[#f0f0f0]'} rounded-lg p-1`}>
                <button
                  onClick={() => handleFilterChange('all')}
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                    filterTier === 'all' 
                      ? (isDark ? 'bg-[#2a2a45] text-white shadow-lg' : 'bg-white shadow-sm text-[#1a1a2e]') 
                      : (isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#1a1a2e]')
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => handleFilterChange('high')}
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                    filterTier === 'high' 
                      ? (isDark ? 'bg-[#2a2a45] text-[#e94560] shadow-lg' : 'bg-white shadow-sm text-[#e94560]') 
                      : (isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#1a1a2e]')
                  }`}
                >
                  High
                </button>
                <button
                  onClick={() => handleFilterChange('worth')}
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                    filterTier === 'worth' 
                      ? (isDark ? 'bg-[#2a2a45] text-[#fdcb6e] shadow-lg' : 'bg-white shadow-sm text-[#fdcb6e]') 
                      : (isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#1a1a2e]')
                  }`}
                >
                  Worth
                </button>
              </div>
              <button
                onClick={resetCheckpoint}
                className={`text-xs ${isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#667eea]'} px-3 py-1.5 rounded hover:bg-[#f0f0f0] transition-colors`}
              >
                Reset
              </button>
            </div>
          </div>

          {topEvents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {topEvents.map((item, idx) => (
                <EventCard key={idx} item={item} isDark={isDark} />
              ))}
            </div>
          ) : (
            <div className={`${isDark ? 'bg-[#141420] border-[#2a2a45]' : 'bg-white border-[#e9ecef]'} rounded-xl p-12 text-center border`}>
              <p className="text-3xl mb-2">🌊</p>
              <p className={isDark ? 'text-white font-medium text-base' : 'text-[#1a1a2e] font-medium text-base'}>All caught up</p>
              <p className={isDark ? 'text-gray-400 text-sm' : 'text-[#636e72] text-sm'}>
                {watchlist.length > 0
                  ? `${watchlist.length} stocks tracked — nothing significant changed`
                  : 'Add stocks to start tracking'}
              </p>
              <button
                onClick={resetCheckpoint}
                className="mt-4 px-4 py-2 text-sm font-medium text-white bg-[#667eea] hover:bg-[#764ba2] rounded-lg transition-colors"
              >
                View all events
              </button>
            </div>
          )}
        </div>

        {/* Watchlist */}
        <div id="watchlist">
          <div className="flex justify-between items-center mb-3">
            <h3 className={`text-base font-semibold tracking-tight ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>Your Watchlist</h3>
            <span className={`text-xs ${isDark ? 'text-gray-400 bg-[#1a1a2e] border-[#2a2a45]' : 'text-[#636e72] bg-white border-[#e9ecef]'} px-3 py-1 rounded-full border`}>
              {watchlist.length} stocks
            </span>
          </div>

          <form onSubmit={addStock} className="flex gap-2 mb-3">
            <input
              type="text"
              value={newStock}
              onChange={(e) => setNewStock(e.target.value)}
              placeholder="e.g. RELIANCE, TCS, HDFC, SBIN"
              className={`flex-1 px-4 py-2 text-sm ${isDark ? 'bg-[#1a1a2e] border-[#2a2a45] text-white placeholder:text-gray-500' : 'bg-white border-[#e9ecef] text-[#1a1a2e] placeholder:text-[#636e72]'} border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#667eea]/30 focus:border-[#667eea]`}
            />
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-[#667eea] hover:bg-[#764ba2] rounded-lg transition-colors"
            >
              + Add
            </button>
          </form>

          <div className={`${isDark ? 'bg-[#141420] border-[#2a2a45]' : 'bg-white border-[#e9ecef]'} rounded-xl border overflow-hidden shadow-sm`}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={`${isDark ? 'bg-[#1a1a2e]' : 'bg-[#f8f9fa]'} border-b ${isDark ? 'border-[#2a2a45]' : 'border-[#e9ecef]'}`}>
                  <tr>
                    <th className={`px-4 py-3 text-left text-xs font-medium ${isDark ? 'text-gray-400' : 'text-[#636e72]'} uppercase tracking-wider`}>Stock</th>
                    <th className={`px-4 py-3 text-right text-xs font-medium ${isDark ? 'text-gray-400' : 'text-[#636e72]'} uppercase tracking-wider`}>Price</th>
                    <th className={`px-4 py-3 text-right text-xs font-medium ${isDark ? 'text-gray-400' : 'text-[#636e72]'} uppercase tracking-wider`}>Today</th>
                    <th className={`px-4 py-3 text-left text-xs font-medium ${isDark ? 'text-gray-400' : 'text-[#636e72]'} uppercase tracking-wider`}>Status</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-[#636e72] uppercase tracking-wider"></th>
                  </tr>
                </thead>
                <tbody className={`divide-y ${isDark ? 'divide-[#2a2a45]' : 'divide-[#e9ecef]'}`}>
                  {watchlist.map((stock) => {
                    const tier = attentionBySymbol[stock.symbol];
                    const hasConflict = !!conflicts[stock.symbol];
                    const realPrice = watchlistPrices[stock.symbol];
                    
                    let status = 'Normal';
                    let statusColor = isDark ? 'text-gray-400' : 'text-[#636e72]';
                    let statusBg = isDark ? 'bg-[#1a1a2e]' : 'bg-[#f0f0f0]';
                    
                    if (tier === 'High attention') {
                      status = 'Unusual activity';
                      statusColor = 'text-[#e94560]';
                      statusBg = isDark ? 'bg-[#e94560]/20' : 'bg-red-50';
                    } else if (tier === 'Worth knowing') {
                      status = 'Sector divergence';
                      statusColor = 'text-[#fdcb6e]';
                      statusBg = isDark ? 'bg-[#fdcb6e]/20' : 'bg-yellow-50';
                    }
                    
                    const price = realPrice || stock.reference_price || 0;
                    const change = stock.reference_price && price 
                      ? ((price - stock.reference_price) / stock.reference_price * 100)
                      : 0;
                    const isPositive = change >= 0;
                    
                    return (
                      <tr key={stock.symbol} className={`${isDark ? 'hover:bg-[#1a1a2e]' : 'hover:bg-[#f8f9fa]'} transition-colors`}>
                        <td className="px-4 py-3">
                          <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>{stock.symbol}</span>
                          {hasConflict && <span className="ml-2 text-xs text-orange-500">⚠️</span>}
                        </td>
                        <td className={`px-4 py-3 text-right text-sm font-medium tabular ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>
                          {price > 0 ? `₹${price.toFixed(2)}` : '—'}
                        </td>
                        <td className={`px-4 py-3 text-right text-sm font-medium tabular ${isPositive ? 'text-[#00b894]' : 'text-[#e17055]'}`}>
                          {price > 0 ? `${isPositive ? '+' : ''}${change.toFixed(1)}%` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-1 rounded-full ${statusBg} ${statusColor}`}>
                            {status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => removeStock(stock.symbol)}
                            className={`${isDark ? 'text-gray-400 hover:text-[#e17055]' : 'text-[#636e72] hover:text-[#e17055]'} transition-colors text-sm`}
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-[#636e72]'} mt-3 text-center`}>
            {digest?.last_checked_at
              ? `Last checked: ${new Date(digest.last_checked_at).toLocaleString()}`
              : 'Never checked'}
          </p>
        </div>
      </div>

      {/* Mobile Bottom Nav */}
      <nav className={`md:hidden fixed bottom-0 inset-x-0 z-40 ${isDark ? 'bg-[#141420] border-[#2a2a45]' : 'bg-white border-[#e9ecef]'} border-t`}>
        <div className="grid grid-cols-3 h-12">
          <button className="flex flex-col items-center justify-center text-xs font-medium text-[#667eea]">
            <span className="text-base">⌂</span>
            <span>Home</span>
          </button>
          <button className={`flex flex-col items-center justify-center text-xs font-medium ${isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#1a1a2e]'}`}>
            <span className="text-base">◈</span>
            <span>Digest</span>
          </button>
          <button className={`flex flex-col items-center justify-center text-xs font-medium ${isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#1a1a2e]'}`}>
            <span className="text-base">≡</span>
            <span>Watchlist</span>
          </button>
        </div>
      </nav>
    </div>
  );
};

// EventCard - Clean, no emojis
const EventCard = ({ item, isDark }) => {
  const [showDetails, setShowDetails] = useState(false);
  
  const rupeeImpact = item.context?.rupee_impact || '';
  const price = item.context?.price || 0;
  const reasons = item.context?.reasons || [];
  
  let change = 0;
  let isPositive = true;
  for (const reason of reasons) {
    const match = reason.match(/([+-]?\d+\.?\d*)%/);
    if (match) {
      change = parseFloat(match[1]);
      isPositive = change >= 0;
      break;
    }
  }

  const getEventLabel = () => {
    const type = item.event_type?.toLowerCase() || '';
    if (type.includes('earnings')) return 'Earnings';
    if (type.includes('acquisition')) return 'Acquisition';
    if (type.includes('management')) return 'Management';
    if (type.includes('rating')) return 'Rating';
    if (type.includes('split')) return 'Stock Split';
    if (type.includes('bonus')) return 'Bonus';
    if (type.includes('halt')) return 'Trading Halt';
    if (type.includes('dividend')) return 'Dividend';
    if (type.includes('insider')) return 'Insider Trade';
    if (type.includes('regulatory')) return 'Regulatory';
    return 'Event';
  };

  const hasSectorDivergence = reasons.some(
    r => r.toLowerCase().includes('sector') || r.toLowerCase().includes('divergence')
  );

  // Clean description - remove emojis
  const cleanDescription = item.description?.replace(/[🔴🟡📊🤝👔📈⚖️🔀🎁⏸️💰📋🎁📌]/g, '').trim() || '';

  // Clean rupee impact - remove emojis
  const cleanRupeeImpact = rupeeImpact.replace(/[💰💸]/g, '').trim();

  return (
    <div className={`${isDark ? 'bg-[#141420] border-[#2a2a45]' : 'bg-white border-[#e9ecef]'} rounded-xl border p-5 shadow-sm hover:shadow-md transition-shadow`}>
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-base font-semibold tracking-tight ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>{item.symbol}</span>
            <span className={`text-xs ${isDark ? 'text-gray-400 bg-[#1a1a2e]' : 'text-[#636e72] bg-[#f0f0f0]'} px-2 py-0.5 rounded-full`}>
              {getEventLabel()}
            </span>
            {hasSectorDivergence && (
              <span className={`text-xs ${isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-50 text-blue-600'} px-2 py-0.5 rounded-full font-medium`}>
                Sector Divergence
              </span>
            )}
          </div>
          <div className="mt-1">
            <span className={`text-xl font-bold tabular ${isDark ? 'text-white' : 'text-[#1a1a2e]'}`}>₹{price.toFixed(2)}</span>
            <span className={`ml-2 text-sm font-medium tabular ${isPositive ? 'text-[#00b894]' : 'text-[#e17055]'}`}>
              {isPositive ? '+' : ''}{change.toFixed(1)}%
            </span>
          </div>
        </div>
        {item.tier === 'High attention' && (
          <span className={`text-xs ${isDark ? 'bg-[#e94560]/20 text-[#e94560]' : 'bg-red-50 text-[#e94560]'} px-2 py-0.5 rounded-full font-medium`}>
            High
          </span>
        )}
        {item.tier === 'Worth knowing' && (
          <span className={`text-xs ${isDark ? 'bg-[#fdcb6e]/20 text-[#fdcb6e]' : 'bg-yellow-50 text-[#fdcb6e]'} px-2 py-0.5 rounded-full font-medium`}>
            Worth
          </span>
        )}
      </div>

      {cleanRupeeImpact && (
        <div className={`text-sm font-medium ${isDark ? 'text-[#7c8cf5]' : 'text-[#667eea]'} mb-3`}>
          {cleanRupeeImpact}
        </div>
      )}

      <div className={`flex justify-between items-center pt-3 border-t ${isDark ? 'border-[#2a2a45]' : 'border-[#e9ecef]'}`}>
        <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-[#636e72]'}`}>
          {new Date(item.timestamp).toLocaleString()}
        </span>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className={`text-xs font-medium ${isDark ? 'text-[#7c8cf5] hover:text-[#8b6fc4]' : 'text-[#667eea] hover:text-[#764ba2]'} transition-colors`}
        >
          {showDetails ? 'Less' : 'View details →'}
        </button>
      </div>

      {showDetails && (
        <div className={`mt-3 p-3 ${isDark ? 'bg-[#1a1a2e] border-[#2a2a45]' : 'bg-[#f8f9fa] border-[#e9ecef]'} rounded-lg border`}>
          <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-[#1a1a2e]'} mb-2 leading-relaxed`}>
            {cleanDescription}
          </p>
          
          {reasons.length > 0 && (
            <>
              <p className={`text-xs font-medium ${isDark ? 'text-gray-400' : 'text-[#636e72]'} mt-2 mb-1`}>Why we're showing this:</p>
              <ul className="space-y-1">
                {reasons.slice(0, 4).map((reason, idx) => {
                  const isSector = reason.toLowerCase().includes('sector') || reason.toLowerCase().includes('divergence');
                  return (
                    <li key={idx} className={`text-sm ${isDark ? 'text-gray-300' : 'text-[#1a1a2e]'} flex items-start gap-2 leading-relaxed`}>
                      <span className={`mt-1 ${isSector ? 'text-blue-500' : 'text-[#667eea]'}`}>•</span>
                      <span className={isSector ? (isDark ? 'text-blue-400' : 'text-blue-600') : ''}>{reason}</span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
          
          <div className={`mt-2 pt-2 border-t ${isDark ? 'border-[#2a2a45]' : 'border-[#e9ecef]'} text-xs ${isDark ? 'text-gray-500' : 'text-[#636e72]'}`}>
            {price > 0 && <span>Price: ₹{price.toFixed(2)}</span>}
            {item.context?.sector && <span className="ml-3">Sector: {item.context.sector}</span>}
            <span className="ml-3">Score: {item.significance_score}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default Home;