import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';

const Signup = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    const result = await signup(email, password);
    if (result.success) {
      setSuccess('Account created! Redirecting to login...');
      setTimeout(() => navigate('/login'), 1500);
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-12 relative"
      style={{ background: 'linear-gradient(160deg, var(--auth-from), var(--auth-to))' }}
    >
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="max-w-[400px] w-full animate-fade-in">
        {/* Header: logo + name inline, left-aligned */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-5">
            <div className="inline-flex w-6 h-6 rounded brand-gradient items-center justify-center shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <span className="text-[13px] font-medium text-ink">Smart Watchlist</span>
          </div>

          <h1 className="text-[28px] font-bold tracking-tight text-ink leading-tight">
            Track what matters.
          </h1>
          <p className="text-muted/60 text-[15px] mt-1">Ignore the noise.</p>
        </div>

        <div className="bg-card rounded-lg shadow-card border border-line p-7">
          {error && (
            <div className="bg-danger/10 border border-danger/20 text-danger px-3 py-2.5 rounded mb-4 text-[13px]">
              {error}
            </div>
          )}
          {success && (
            <div className="bg-success/10 border border-success/20 text-success px-3 py-2.5 rounded mb-4 text-[13px]">
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-ink text-[13px] font-medium mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-11 px-3 bg-[var(--input-bg)] border border-line rounded text-[14px] text-ink placeholder:text-muted/70 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                placeholder="you@example.com"
                required
              />
            </div>

            <div className="mb-4">
              <label className="block text-ink text-[13px] font-medium mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-11 px-3 bg-[var(--input-bg)] border border-line rounded text-[14px] text-ink placeholder:text-muted/70 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                placeholder="Min 6 characters"
                required
              />
            </div>

            <div className="mb-6">
              <label className="block text-ink text-[13px] font-medium mb-1.5">Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full h-11 px-3 bg-[var(--input-bg)] border border-line rounded text-[14px] text-ink placeholder:text-muted/70 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                placeholder="Confirm password"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 text-[14px] font-semibold btn-brand rounded disabled:opacity-50"
            >
              {loading ? 'Creating account...' : 'Sign Up'}
            </button>
          </form>

          <p className="text-center text-muted text-[13px] mt-5">
            Already have an account?{' '}
            <Link to="/login" className="text-accent font-medium hover:underline">
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Signup;