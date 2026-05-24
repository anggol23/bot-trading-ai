import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Activity,
  Wallet,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  BarChart2,
  List as ListIcon,
  Target,
  History,
  LayoutDashboard,
  CheckCircle2,
  XCircle,
  Clock,
  Settings,
} from 'lucide-react';
import ReactApexChart from 'react-apexcharts';

const API_BASE = '/api';

interface PortfolioSummary {
  total_equity: number;
  available_balance: number;
  unrealized_pnl: number;
  realized_pnl_today: number;
  open_positions: number;
  daily_drawdown_pct: number;
}

interface Position {
  id: number;
  symbol: string;
  side: string;
  entry_price: number;
  current_price: number;
  stop_loss: number;
  take_profit: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

interface VolumeAnomaly {
  id: number;
  symbol: string;
  type: string;
  side: string;
  amount_usd: number;
  imbalance_ratio: number;
  timestamp: string;
}

interface Signal {
  id: number;
  symbol: string;
  action: string;
  confidence: number;
  reason: string;
  timestamp: string;
  ai_decision?: string;
  ai_reasoning?: string;
}

interface TradeHistory {
  id: number;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  amount: number;
  cost: number;
  pnl: number | null;
  pnl_percent: number | null;
  status: string;
  mode: string;
  close_reason: string | null;
  opened_at: string;
  closed_at: string | null;
  duration_minutes: number | null;
}

interface DailyTarget {
  target_pct: number;
  target_idr: number;
  realized_pnl_today: number;
  progress_pct: number;
  status: string;
  daily_drawdown_pct: number;
  drawdown_limit_pct: number;
  equity: number;
}

type Tab = 'overview' | 'history' | 'settings';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [email, setEmail] = useState<string | null>(localStorage.getItem('email'));
  
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [anomalies, setAnomalies] = useState<VolumeAnomaly[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [equityData, setEquityData] = useState<any[]>([]);
  const [tradeHistory, setTradeHistory] = useState<TradeHistory[]>([]);
  const [dailyTarget, setDailyTarget] = useState<DailyTarget | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [chartFilter, setChartFilter] = useState<'1' | '7' | '30' | 'all'>('1');
  const [loading, setLoading] = useState(!!localStorage.getItem('token'));
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Auth Form State
  const [showRegister, setShowRegister] = useState(false);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authConfirmPassword, setAuthConfirmPassword] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccess, setAuthSuccess] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Settings State (API Keys)
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [keysLoading, setKeysLoading] = useState(false);
  const [keysMessage, setKeysMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [savedKeys, setSavedKeys] = useState<{ api_key: string | null; api_secret: string | null } | null>(null);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('email');
    localStorage.removeItem('userId');
    setToken(null);
    setEmail(null);
    setPortfolio(null);
    setPositions([]);
  };

  // Configure axios authorization header
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  // Handle 401 errors
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          handleLogout();
        }
        return Promise.reject(error);
      }
    );
    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  const fetchKeysStatus = async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${API_BASE}/auth/keys`);
      setSavedKeys(res.data);
    } catch (err) {
      console.error('Gagal mengambil status API Keys', err);
    }
  };

  useEffect(() => {
    if (token && activeTab === 'settings') {
      fetchKeysStatus();
    }
  }, [token, activeTab]);

  useEffect(() => {
    if (!token) return;

    const fetchData = async () => {
      try {
        const equityUrl = chartFilter === 'all' ? `${API_BASE}/equity` : `${API_BASE}/equity?days=${chartFilter}`;

        const [portRes, posRes, anomRes, sigRes, eqRes, tradeRes, targetRes] = await Promise.all([
          axios.get(`${API_BASE}/portfolio`),
          axios.get(`${API_BASE}/positions`),
          axios.get(`${API_BASE}/volume`),
          axios.get(`${API_BASE}/signals`),
          axios.get(equityUrl),
          axios.get(`${API_BASE}/trades?limit=50`),
          axios.get(`${API_BASE}/daily-target`),
        ]);

        setPortfolio(portRes.data);
        setPositions(posRes.data);
        setAnomalies(anomRes.data);
        setSignals(sigRes.data);
        setEquityData(eqRes.data);
        setTradeHistory(tradeRes.data);
        setDailyTarget(targetRes.data);
        setLastUpdate(new Date());
      } catch (err) {
        console.error('Failed to fetch data', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [chartFilter, token]);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSuccess(null);
    
    if (showRegister && authPassword !== authConfirmPassword) {
      setAuthError("Konfirmasi password tidak cocok.");
      return;
    }

    setAuthLoading(true);
    try {
      const endpoint = showRegister ? `${API_BASE}/auth/register` : `${API_BASE}/auth/login`;
      const response = await axios.post(endpoint, {
        email: authEmail,
        password: authPassword
      });

      const { access_token, email: userEmail, user_id } = response.data;
      
      localStorage.setItem('token', access_token);
      localStorage.setItem('email', userEmail);
      localStorage.setItem('userId', String(user_id));

      setToken(access_token);
      setEmail(userEmail);
      setLoading(true);
      setAuthSuccess(showRegister ? "Registrasi berhasil! Masuk..." : "Login berhasil!");
      
      setAuthEmail('');
      setAuthPassword('');
      setAuthConfirmPassword('');
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Email atau password salah.";
      setAuthError(msg);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleKeysSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setKeysMessage(null);
    setKeysLoading(true);

    try {
      await axios.post(`${API_BASE}/auth/keys`, {
        api_key: apiKey,
        api_secret: apiSecret
      });
      setKeysMessage({ type: 'success', text: 'API Keys Indodax berhasil diperbarui!' });
      setApiKey('');
      setApiSecret('');
      fetchKeysStatus();
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Gagal memperbarui API Keys.";
      setKeysMessage({ type: 'error', text: msg });
    } finally {
      setKeysLoading(false);
    }
  };

  const formatIDR = (val: number) =>
    new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(val);

  const formatUSD = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);

  const formatDuration = (mins: number | null) => {
    if (mins === null) return '—';
    if (mins < 60) return `${mins}m`;
    return `${Math.floor(mins / 60)}h ${Math.round(mins % 60)}m`;
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  const getDailyTargetConfig = (status: string) => {
    switch (status) {
      case 'TARGET_MET':
        return { icon: <CheckCircle2 className="w-5 h-5 text-[#10b981]" />, label: '✅ Target Tercapai!', barColor: '#10b981', badgeClass: 'bg-[#10b981]/15 text-[#10b981] border-[#10b981]/30' };
      case 'DRAWDOWN_LIMIT':
        return { icon: <XCircle className="w-5 h-5 text-[#ef4444]" />, label: '⛔ Drawdown Limit', barColor: '#ef4444', badgeClass: 'bg-[#ef4444]/15 text-[#ef4444] border-[#ef4444]/30' };
      case 'HUNTING':
        return { icon: <Target className="w-5 h-5 text-[#f59e0b]" />, label: '🎯 Mengejar Target', barColor: '#f59e0b', badgeClass: 'bg-[#f59e0b]/15 text-[#f59e0b] border-[#f59e0b]/30' };
      default:
        return { icon: <Clock className="w-5 h-5 text-gray-400" />, label: '⏳ Belum Ada Trade', barColor: '#64748b', badgeClass: 'bg-gray-700/50 text-gray-400 border-gray-600/30' };
    }
  };

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0b1120] px-4 font-sans relative overflow-hidden">
        <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-blue-500/10 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-[#10b981]/10 blur-[120px] pointer-events-none" />

        <div className="w-full max-w-md glass-card rounded-3xl p-8 relative z-10 border border-white/10 shadow-2xl">
          <div className="flex flex-col items-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-[#10b981]/20 flex items-center justify-center mb-4 border border-[#10b981]/30 shadow-lg shadow-[#10b981]/10">
              <Activity className="w-8 h-8 text-[#10b981]" />
            </div>
            <h2 className="text-3xl font-extrabold text-white tracking-tight">AI Trading Node</h2>
            <p className="text-gray-400 text-sm mt-1">Multi-user Autonomous Trading Agent</p>
          </div>

          <div className="flex gap-2 mb-6 p-1 bg-gray-800/40 border border-gray-700/30 rounded-xl">
            <button
              onClick={() => {
                setShowRegister(false);
                setAuthError(null);
                setAuthSuccess(null);
              }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all duration-300 ${!showRegister ? 'bg-[#10b981] text-white shadow-lg shadow-[#10b981]/25' : 'text-gray-400 hover:text-gray-200'}`}
            >
              Sign In
            </button>
            <button
              onClick={() => {
                setShowRegister(true);
                setAuthError(null);
                setAuthSuccess(null);
              }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all duration-300 ${showRegister ? 'bg-[#10b981] text-white shadow-lg shadow-[#10b981]/25' : 'text-gray-400 hover:text-gray-200'}`}
            >
              Register
            </button>
          </div>

          {authError && (
            <div className="mb-4 flex items-center gap-2 bg-[#ef4444]/10 border border-[#ef4444]/20 text-[#ef4444] text-xs px-4 py-3 rounded-xl">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{authError}</span>
            </div>
          )}

          {authSuccess && (
            <div className="mb-4 flex items-center gap-2 bg-[#10b981]/10 border border-[#10b981]/20 text-[#10b981] text-xs px-4 py-3 rounded-xl">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{authSuccess}</span>
            </div>
          )}

          <form onSubmit={handleAuthSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5 ml-1">Email Address</label>
              <input
                type="email"
                required
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full bg-gray-900/60 border border-gray-800 focus:border-[#10b981] outline-none text-white text-sm px-4 py-3 rounded-xl transition-all duration-300 placeholder:text-gray-600 focus:shadow-md focus:shadow-[#10b981]/5"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5 ml-1">Password</label>
              <input
                type="password"
                required
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-gray-900/60 border border-gray-800 focus:border-[#10b981] outline-none text-white text-sm px-4 py-3 rounded-xl transition-all duration-300 placeholder:text-gray-600 focus:shadow-md focus:shadow-[#10b981]/5"
              />
            </div>

            {showRegister && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5 ml-1">Confirm Password</label>
                <input
                  type="password"
                  required
                  value={authConfirmPassword}
                  onChange={(e) => setAuthConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-gray-900/60 border border-gray-800 focus:border-[#10b981] outline-none text-white text-sm px-4 py-3 rounded-xl transition-all duration-300 placeholder:text-gray-600 focus:shadow-md focus:shadow-[#10b981]/5"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={authLoading}
              className="w-full mt-2 py-3 bg-[#10b981] hover:bg-[#10b981]/80 text-white font-bold text-sm rounded-xl transition-all duration-300 shadow-lg shadow-[#10b981]/20 hover:shadow-[#10b981]/30 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {authLoading ? (
                <>
                  <Activity className="w-4 h-4 animate-spin" />
                  {showRegister ? 'Creating Account...' : 'Signing In...'}
                </>
              ) : (
                showRegister ? 'Register Account' : 'Sign In to Dashboard'
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0b1120]">
        <div className="flex flex-col items-center gap-4">
          <Activity className="w-12 h-12 text-[#10b981] animate-spin" />
          <h2 className="text-xl font-bold text-gray-200">Initializing Core Engine...</h2>
        </div>
      </div>
    );
  }

  const targetCfg = getDailyTargetConfig(dailyTarget?.status || 'NO_TRADES');
  const equityIsZero = !portfolio || portfolio.total_equity === 0;

  if (!portfolio) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0b1120]">
        <div className="flex flex-col items-center gap-4">
          <AlertCircle className="w-12 h-12 text-[#ef4444]" />
          <h2 className="text-xl font-bold text-gray-200">Gagal Memuat Data Dashboard</h2>
          <p className="text-gray-500 text-sm">Cek koneksi ke server backend AI Trading.</p>
          <button
            onClick={handleLogout}
            className="mt-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs rounded-xl"
          >
            Logout & Login Ulang
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0b1120] text-gray-100 font-sans">

      {/* ── HEADER ── */}
      <header className="px-6 py-4 flex justify-between items-center border-b border-gray-800/60 sticky top-0 z-20 bg-[#0b1120]/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#10b981]/20 flex items-center justify-center">
            <Activity className="w-5 h-5 text-[#10b981]" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">AI Trading Node</h1>
            <p className="text-gray-500 text-xs">Indodax Autonomous System</p>
          </div>
          <span className="ml-2 bg-[#10b981]/10 text-[#10b981] text-[10px] py-0.5 px-2 rounded-full border border-[#10b981]/20 font-medium">LIVE</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">User Akun</span>
            <span className="text-xs text-gray-300 font-medium">{email}</span>
          </div>
          <button
            onClick={handleLogout}
            className="px-3.5 py-1.5 bg-gray-800 hover:bg-red-500/15 border border-gray-700 hover:border-red-500/30 text-gray-300 hover:text-red-400 text-xs rounded-xl font-semibold transition-all duration-300 cursor-pointer"
          >
            Logout
          </button>
          <div className="text-right border-l border-gray-800/60 pl-6">
            <p className="text-xs text-gray-500">Last Update</p>
            <p className="font-mono text-sm text-gray-300">{lastUpdate.toLocaleTimeString()}</p>
          </div>
        </div>
      </header>

      <div className="p-6">

        {/* ── METRIC CARDS ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">

          {/* Total Equity */}
          <div className="glass-card p-5 rounded-2xl">
            <div className="flex justify-between items-start mb-3">
              <p className="text-gray-400 text-xs uppercase tracking-wider">Total Equity</p>
              <div className="p-2 bg-blue-500/10 rounded-xl">
                <Wallet className="w-5 h-5 text-blue-400" />
              </div>
            </div>
            {equityIsZero ? (
              <p className="text-sm text-yellow-400 font-medium">⏳ Menunggu data balance...</p>
            ) : (
              <h3 className="text-2xl font-bold text-white">{formatIDR(portfolio!.total_equity)}</h3>
            )}
            <div className="flex gap-2 text-xs mt-2 text-gray-400">
              <span>Tersedia:</span>
              <span className="text-gray-300">{formatIDR(portfolio?.available_balance || 0)}</span>
            </div>
          </div>

          {/* Unrealized PnL */}
          <div className="glass-card p-5 rounded-2xl">
            <div className="flex justify-between items-start mb-3">
              <p className="text-gray-400 text-xs uppercase tracking-wider">Unrealized PnL</p>
              <div className={`p-2 rounded-xl ${(portfolio?.unrealized_pnl || 0) >= 0 ? 'bg-[#10b981]/10' : 'bg-[#ef4444]/10'}`}>
                {(portfolio?.unrealized_pnl || 0) >= 0
                  ? <TrendingUp className="w-5 h-5 text-[#10b981]" />
                  : <TrendingDown className="w-5 h-5 text-[#ef4444]" />}
              </div>
            </div>
            <h3 className={`text-2xl font-bold ${(portfolio?.unrealized_pnl || 0) >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
              {(portfolio?.unrealized_pnl || 0) >= 0 ? '+' : ''}{formatIDR(portfolio?.unrealized_pnl || 0)}
            </h3>
            <div className="text-xs mt-2 text-gray-400">Posisi terbuka saat ini</div>
          </div>

          {/* Realized Today */}
          <div className="glass-card p-5 rounded-2xl">
            <div className="flex justify-between items-start mb-3">
              <p className="text-gray-400 text-xs uppercase tracking-wider">Realized Today</p>
              <div className="p-2 bg-purple-500/10 rounded-xl">
                <Activity className="w-5 h-5 text-purple-400" />
              </div>
            </div>
            <h3 className={`text-2xl font-bold ${(portfolio?.realized_pnl_today || 0) >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
              {(portfolio?.realized_pnl_today || 0) >= 0 ? '+' : ''}{formatIDR(portfolio?.realized_pnl_today || 0)}
            </h3>
            <div className="text-xs mt-2 text-gray-400">Profit/Loss hari ini (closed)</div>
          </div>

          {/* Daily Target */}
          <div className="glass-card p-5 rounded-2xl">
            <div className="flex justify-between items-start mb-3">
              <p className="text-gray-400 text-xs uppercase tracking-wider">Daily Target</p>
              {targetCfg.icon}
            </div>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-2xl font-bold text-white">
                {Math.max(0, dailyTarget?.progress_pct || 0).toFixed(0)}%
              </span>
              <span className="text-xs text-gray-500">/ {dailyTarget?.target_pct.toFixed(1)}% target</span>
            </div>
            {/* Progress Bar */}
            <div className="w-full bg-gray-700/50 rounded-full h-1.5 mt-2 mb-2 overflow-hidden">
              <div
                className="h-1.5 rounded-full transition-all duration-700"
                style={{
                  width: `${Math.min(100, Math.max(0, dailyTarget?.progress_pct || 0))}%`,
                  backgroundColor: targetCfg.barColor,
                }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-gray-500">
              <span>{formatIDR(dailyTarget?.realized_pnl_today || 0)}</span>
              <span>Target: {formatIDR(dailyTarget?.target_idr || 0)}</span>
            </div>
            <span className={`mt-2 inline-block text-[10px] px-2 py-0.5 rounded-full border ${targetCfg.badgeClass}`}>
              {targetCfg.label}
            </span>
          </div>

        </div>

        {/* ── DRAWDOWN WARNING ── */}
        {(dailyTarget?.daily_drawdown_pct || 0) > 3 && (
          <div className="mb-6 flex items-center gap-3 bg-[#ef4444]/10 border border-[#ef4444]/30 text-[#ef4444] px-4 py-3 rounded-xl text-sm">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span>
              <strong>Peringatan Drawdown:</strong> {dailyTarget?.daily_drawdown_pct.toFixed(2)}% dari limit {dailyTarget?.drawdown_limit_pct}%.
              {(dailyTarget?.daily_drawdown_pct || 0) >= (dailyTarget?.drawdown_limit_pct || 5) && ' Trading dihentikan hari ini.'}
            </span>
          </div>
        )}

        {/* ── TAB NAVIGATION ── */}
        <div className="flex gap-1 mb-6 p-1 bg-gray-800/50 rounded-xl w-fit">
          <button
            id="tab-overview"
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'overview' ? 'bg-[#10b981] text-white shadow-lg shadow-[#10b981]/20' : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            Overview
          </button>
          <button
            id="tab-history"
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'history' ? 'bg-[#10b981] text-white shadow-lg shadow-[#10b981]/20' : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <History className="w-4 h-4" />
            Trade History
            {tradeHistory.length > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${activeTab === 'history' ? 'bg-white/20' : 'bg-gray-700 text-gray-300'}`}>
                {tradeHistory.length}
              </span>
            )}
          </button>
          <button
            id="tab-settings"
            onClick={() => setActiveTab('settings')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'settings' ? 'bg-[#10b981] text-white shadow-lg shadow-[#10b981]/20' : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <Settings className="w-4 h-4" />
            API Settings
          </button>
        </div>

        {/* ════════════════════ OVERVIEW TAB ════════════════════ */}
        {activeTab === 'overview' && (
          <>
            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

              {/* Equity Curve */}
              <div className="lg:col-span-2 glass-card px-6 py-5 rounded-2xl">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <BarChart2 className="w-4 h-4 text-gray-400" />
                    <h2 className="text-base font-bold text-white">Equity Curve</h2>
                  </div>
                  <div className="flex gap-1 bg-gray-800/50 p-1 rounded-lg">
                    {(['1', '7', '30', 'all'] as const).map((filter) => (
                      <button
                        key={filter}
                        onClick={() => setChartFilter(filter)}
                        className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${chartFilter === filter
                          ? 'bg-[#3b82f6] text-white shadow-md shadow-[#3b82f6]/20'
                          : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.05]'
                          }`}
                      >
                        {filter === '1' ? 'Hari Ini' : filter === '7' ? '7 Hari' : filter === '30' ? '30 Hari' : 'Semua'}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="h-[350px] w-full">
                  {equityData.length > 0 ? (
                    <ReactApexChart
                      options={{
                        chart: { type: 'area', background: 'transparent', toolbar: { show: false }, animations: { enabled: false } },
                        theme: { mode: 'dark' },
                        colors: ['#3b82f6'],
                        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, stops: [0, 100] } },
                        dataLabels: { enabled: false },
                        stroke: { curve: 'smooth', width: 2 },
                        xaxis: { type: 'datetime', labels: { style: { colors: '#64748b' } }, axisBorder: { color: '#1e293b' } },
                        yaxis: {
                          tooltip: { enabled: true },
                          labels: { style: { colors: '#64748b' }, formatter: (val: number) => `Rp ${(val / 1000).toFixed(0)}K` },
                        },
                        grid: { borderColor: '#1e293b', strokeDashArray: 4 },
                        tooltip: { theme: 'dark' },
                      }}
                      series={[{ name: 'Equity', data: equityData.map((d: any) => [new Date(d.time).getTime(), d.value]) }]}
                      type="area"
                      height="100%"
                    />
                  ) : (
                    <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                      📊 Belum ada histori equity yang tercatat
                    </div>
                  )}
                </div>
              </div>

              {/* Volume Anomaly Feed */}
              <div className="glass-card px-5 py-5 rounded-2xl flex flex-col" style={{ maxHeight: '450px' }}>
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-gray-800/60">
                  <Activity className="w-4 h-4 text-[#10b981]" />
                  <h2 className="text-base font-bold text-white">Live Volume Feed</h2>
                </div>
                <div className="flex-1 overflow-y-auto space-y-3 pr-1" style={{ scrollbarWidth: 'thin' }}>
                  {anomalies.length === 0 && (
                    <p className="text-gray-500 text-sm text-center py-6">Tidak ada anomali terdeteksi</p>
                  )}
                  {anomalies.map((anom) => (
                    <div key={anom.id} className="border-l-2 pl-3 py-0.5" style={{ borderColor: anom.side === 'buy' ? '#10b981' : '#ef4444' }}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-bold text-gray-200 text-sm">{anom.symbol}</span>
                        <span className="text-[10px] text-gray-500">{anom.timestamp.split('T')[1]?.slice(0, 5)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${anom.side === 'buy' ? 'bg-[#10b981]/10 text-[#10b981]' : 'bg-[#ef4444]/10 text-[#ef4444]'}`}>
                          {anom.side.toUpperCase()}
                        </span>
                        <span className="text-gray-300 font-mono">{formatUSD(anom.amount_usd)}</span>
                      </div>
                      <p className="text-[10px] text-gray-600 mt-0.5 uppercase tracking-wider">{anom.type.replace('_', ' ')}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Active Positions Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Active Positions */}
              <div className="lg:col-span-2 glass-card p-5 rounded-2xl">
                <div className="flex items-center gap-2 mb-5">
                  <ListIcon className="w-4 h-4 text-gray-400" />
                  <h2 className="text-base font-bold text-white">Active Positions</h2>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">{positions.length} open</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-gray-700/40 text-[10px] uppercase tracking-wider text-gray-500">
                        <th className="pb-3 px-3">Symbol</th>
                        <th className="pb-3 px-3">Side</th>
                        <th className="pb-3 px-3 text-right">Entry</th>
                        <th className="pb-3 px-3 text-right">Current</th>
                        <th className="pb-3 px-3 text-right">P&L</th>
                        <th className="pb-3 px-3 text-right">Stop Loss</th>
                        <th className="pb-3 px-3 text-right">Take Profit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.length === 0 && (
                        <tr>
                          <td colSpan={7} className="text-center py-8 text-gray-500 text-sm">
                            Tidak ada posisi aktif
                          </td>
                        </tr>
                      )}
                      {positions.map(pos => (
                        <tr key={pos.id} className="border-b border-gray-800/30 hover:bg-white/[0.02] transition-colors">
                          <td className="py-3 px-3 font-bold text-white">{pos.symbol}</td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${pos.side === 'buy' ? 'bg-[#10b981]/15 text-[#10b981]' : 'bg-[#ef4444]/15 text-[#ef4444]'}`}>
                              {pos.side.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-gray-300">{pos.entry_price.toLocaleString('id-ID')}</td>
                          <td className="py-3 px-3 text-right font-mono text-gray-300">{pos.current_price.toLocaleString('id-ID')}</td>
                          <td className={`py-3 px-3 text-right font-bold ${pos.unrealized_pnl >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                            {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toLocaleString('id-ID')}
                            <span className="block text-[10px] font-normal mt-0.5 opacity-70">
                              {pos.unrealized_pnl_pct >= 0 ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}%
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right text-orange-400/70 font-mono text-xs">{pos.stop_loss.toLocaleString('id-ID')}</td>
                          <td className="py-3 px-3 text-right text-blue-400/70 font-mono text-xs">{pos.take_profit.toLocaleString('id-ID')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Recent Signals & AI Audits */}
              <div className="glass-card p-5 rounded-2xl flex flex-col" style={{ maxHeight: '450px' }}>
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-gray-800/60">
                  <Target className="w-4 h-4 text-blue-400" />
                  <h2 className="text-base font-bold text-white">AI Signals & Audits</h2>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">{signals.length} total</span>
                </div>
                <div className="flex-1 overflow-y-auto space-y-3 pr-1" style={{ scrollbarWidth: 'thin' }}>
                  {signals.length === 0 && (
                    <p className="text-gray-500 text-sm text-center py-6">Tidak ada sinyal terdeteksi</p>
                  )}
                  {signals.map((sig) => {
                    const isBuy = sig.action.includes('BUY');
                    const isSell = sig.action.includes('SELL');
                    const colorClass = isBuy 
                      ? 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30' 
                      : isSell 
                        ? 'text-[#ef4444] bg-[#ef4444]/15 border-[#ef4444]/30' 
                        : 'text-gray-400 bg-gray-800/30 border-gray-700/30';
                    const aiApproved = sig.ai_decision === 'APPROVED';
                    const aiRejected = sig.ai_decision === 'REJECTED';
                    
                    return (
                      <div key={sig.id} className="p-3 bg-gray-800/20 rounded-xl border border-gray-800/40 hover:border-gray-700/30 transition-colors">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <span className="font-bold text-white text-sm">{sig.symbol}</span>
                            <span className="text-[10px] text-gray-500 block font-mono">{formatDate(sig.timestamp)}</span>
                          </div>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${colorClass}`}>
                            {sig.action.replace('_', ' ')}
                          </span>
                        </div>
                        
                        <div className="text-xs text-gray-400 mb-2 leading-relaxed">
                          {sig.reason}
                        </div>
                        
                        {/* LLM Audit Section */}
                        {sig.ai_decision && (
                          <div className="mt-2 pt-2 border-t border-gray-800/40 flex flex-col gap-1 bg-black/20 p-2 rounded-lg">
                            <div className="flex items-center justify-between text-[10px]">
                              <span className="text-gray-500 uppercase tracking-wider font-semibold">AI Strategist Audit</span>
                              <span className={`font-bold px-1.5 py-0.2 rounded text-[9px] ${
                                aiApproved 
                                  ? 'text-[#10b981] bg-[#10b981]/10 border border-[#10b981]/20' 
                                  : aiRejected 
                                    ? 'text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20' 
                                    : 'text-yellow-400 bg-yellow-400/10 border border-yellow-400/20'
                              }`}>
                                {sig.ai_decision}
                              </span>
                            </div>
                            {sig.ai_reasoning && (
                              <p className="text-[10px] text-gray-400 italic mt-0.5 leading-snug">
                                "{sig.ai_reasoning}"
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          </>
        )}

        {/* ════════════════════ HISTORY TAB ════════════════════ */}
        {activeTab === 'history' && (
          <div className="glass-card p-5 rounded-2xl">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-gray-400" />
                <h2 className="text-base font-bold text-white">Riwayat Semua Trade</h2>
              </div>
              <div className="flex gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#10b981] inline-block" />
                  Profit
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#ef4444] inline-block" />
                  Loss
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />
                  Open
                </span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-gray-700/40 text-[10px] uppercase tracking-wider text-gray-500">
                    <th className="pb-3 px-3">#</th>
                    <th className="pb-3 px-3">Symbol</th>
                    <th className="pb-3 px-3">Side</th>
                    <th className="pb-3 px-3">Mode</th>
                    <th className="pb-3 px-3 text-right">Entry</th>
                    <th className="pb-3 px-3 text-right">Exit</th>
                    <th className="pb-3 px-3 text-right">Amount</th>
                    <th className="pb-3 px-3 text-right">P&L</th>
                    <th className="pb-3 px-3">Alasan Tutup</th>
                    <th className="pb-3 px-3">Durasi</th>
                    <th className="pb-3 px-3">Status</th>
                    <th className="pb-3 px-3">Waktu Buka</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeHistory.length === 0 && (
                    <tr>
                      <td colSpan={12} className="text-center py-10 text-gray-500">
                        Belum ada riwayat trade
                      </td>
                    </tr>
                  )}
                  {tradeHistory.map(trade => {
                    const isOpen = trade.status === 'open';
                    const isProfit = (trade.pnl ?? 0) >= 0;
                    const rowBorderColor = isOpen ? '#3b82f6' : isProfit ? '#10b981' : '#ef4444';
                    return (
                      <tr
                        key={trade.id}
                        className="border-b border-gray-800/30 hover:bg-white/[0.02] transition-colors"
                        style={{ borderLeft: `3px solid ${rowBorderColor}` }}
                      >
                        <td className="py-3 px-3 text-gray-500 font-mono text-xs">{trade.id}</td>
                        <td className="py-3 px-3 font-bold text-white">{trade.symbol}</td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${trade.side === 'buy' ? 'bg-[#10b981]/15 text-[#10b981]' : 'bg-[#ef4444]/15 text-[#ef4444]'}`}>
                            {trade.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] ${trade.mode === 'live' ? 'bg-orange-500/15 text-orange-400' : 'bg-gray-600/30 text-gray-400'}`}>
                            {trade.mode.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-gray-300 text-xs">{trade.entry_price.toLocaleString('id-ID')}</td>
                        <td className="py-3 px-3 text-right font-mono text-gray-300 text-xs">
                          {trade.exit_price ? trade.exit_price.toLocaleString('id-ID') : <span className="text-blue-400">Terbuka</span>}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-gray-400 text-xs">{trade.amount.toLocaleString('id-ID', { maximumFractionDigits: 4 })}</td>
                        <td className={`py-3 px-3 text-right font-bold ${isOpen ? 'text-blue-400' : isProfit ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                          {isOpen ? '—' : (
                            <>
                              {isProfit ? '+' : ''}{(trade.pnl ?? 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                              <span className="block text-[10px] font-normal opacity-70">
                                {isProfit ? '+' : ''}{(trade.pnl_percent ?? 0).toFixed(2)}%
                              </span>
                            </>
                          )}
                        </td>
                        <td className="py-3 px-3 text-xs text-gray-500 max-w-[160px] truncate" title={trade.close_reason || ''}>
                          {trade.close_reason || '—'}
                        </td>
                        <td className="py-3 px-3 text-xs text-gray-400 font-mono">{formatDuration(trade.duration_minutes)}</td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${isOpen ? 'bg-blue-500/15 text-blue-400' : isProfit ? 'bg-[#10b981]/15 text-[#10b981]' : 'bg-[#ef4444]/15 text-[#ef4444]'}`}>
                            {isOpen ? 'OPEN' : isProfit ? 'PROFIT' : 'LOSS'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-[11px] text-gray-500 font-mono whitespace-nowrap">{formatDate(trade.opened_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Summary footer */}
            {tradeHistory.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-800/60 flex flex-wrap gap-6 text-xs text-gray-400">
                <span>Total: <strong className="text-white">{tradeHistory.length} trade</strong></span>
                <span>Closed: <strong className="text-white">{tradeHistory.filter(t => t.status === 'closed').length}</strong></span>
                <span>Open: <strong className="text-blue-400">{tradeHistory.filter(t => t.status === 'open').length}</strong></span>
                <span>Profit: <strong className="text-[#10b981]">{tradeHistory.filter(t => t.pnl !== null && t.pnl > 0).length}</strong></span>
                <span>Loss: <strong className="text-[#ef4444]">{tradeHistory.filter(t => t.pnl !== null && t.pnl < 0).length}</strong></span>
                <span>Total PnL: <strong className={(() => { const t = tradeHistory.reduce((a, t) => a + (t.pnl ?? 0), 0); return t >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'; })()}>
                  {formatIDR(tradeHistory.reduce((a, t) => a + (t.pnl ?? 0), 0))}
                </strong></span>
              </div>
            )}
          </div>
        )}

        {/* ════════════════════ SETTINGS TAB ════════════════════ */}
        {activeTab === 'settings' && (
          <div className="max-w-2xl mx-auto glass-card p-6 rounded-2xl animate-fade-in">
            <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-800/60">
              <div className="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center">
                <Wallet className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">Indodax API Keys Settings</h2>
                <p className="text-gray-400 text-xs mt-0.5">Simpan API Key & API Secret Indodax Anda untuk live trading secara autonomous.</p>
              </div>
            </div>

            {keysMessage && (
              <div className={`mb-6 flex items-center gap-2 border text-xs px-4 py-3 rounded-xl ${
                keysMessage.type === 'success' 
                  ? 'bg-[#10b981]/10 border-[#10b981]/25 text-[#10b981]' 
                  : 'bg-[#ef4444]/10 border-[#ef4444]/25 text-[#ef4444]'
              }`}>
                {keysMessage.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                <span>{keysMessage.text}</span>
              </div>
            )}

            {/* Current Config State Box */}
            <div className="mb-6 p-4 bg-gray-900/40 border border-gray-800 rounded-xl space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Status Kunci Saat Ini</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-[10px] text-gray-500 block uppercase">Indodax API Key</span>
                  <span className="font-mono text-sm text-gray-300">
                    {savedKeys?.api_key ? savedKeys.api_key : <span className="text-yellow-500 text-xs italic">Belum dikonfigurasi</span>}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-gray-500 block uppercase">Indodax API Secret</span>
                  <span className="font-mono text-sm text-gray-300">
                    {savedKeys?.api_secret ? savedKeys.api_secret : <span className="text-yellow-500 text-xs italic">Belum dikonfigurasi</span>}
                  </span>
                </div>
              </div>
            </div>

            <form onSubmit={handleKeysSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5 ml-1">New Indodax API Key</label>
                <input
                  type="text"
                  required
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Masukkan API Key baru..."
                  className="w-full bg-gray-950/40 border border-gray-800 focus:border-[#10b981] outline-none text-white text-sm px-4 py-3 rounded-xl transition-all duration-300 placeholder:text-gray-600 focus:shadow-md focus:shadow-[#10b981]/5"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5 ml-1">New Indodax API Secret</label>
                <input
                  type="password"
                  required
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Masukkan API Secret baru..."
                  className="w-full bg-gray-950/40 border border-gray-800 focus:border-[#10b981] outline-none text-white text-sm px-4 py-3 rounded-xl transition-all duration-300 placeholder:text-gray-600 focus:shadow-md focus:shadow-[#10b981]/5"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={keysLoading}
                  className="w-full py-3 bg-[#10b981] hover:bg-[#10b981]/80 text-white font-bold text-sm rounded-xl transition-all duration-300 shadow-lg shadow-[#10b981]/25 hover:shadow-[#10b981]/30 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {keysLoading ? (
                    <>
                      <Activity className="w-4 h-4 animate-spin" />
                      Saving Keys...
                    </>
                  ) : (
                    'Simpan API Keys'
                  )}
                </button>
              </div>
            </form>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
