import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Activity,
  Wallet,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  BarChart2,
  List as ListIcon
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts';

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
}

function App() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [anomalies, setAnomalies] = useState<VolumeAnomaly[]>([]);
  const [_, setSignals] = useState<Signal[]>([]);
  const [equityData, setEquityData] = useState<any[]>([]);

  const [loading, setLoading] = useState(true);

  // Auto Refresh Interval
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [portRes, posRes, anomRes, sigRes, eqRes] = await Promise.all([
          axios.get(`${API_BASE}/portfolio`),
          axios.get(`${API_BASE}/positions`),
          axios.get(`${API_BASE}/volume`),
          axios.get(`${API_BASE}/signals`),
          axios.get(`${API_BASE}/equity`)
        ]);

        setPortfolio(portRes.data);
        setPositions(posRes.data);
        setAnomalies(anomRes.data);
        setSignals(sigRes.data);
        setEquityData(eqRes.data);

      } catch (err) {
        console.error("Failed to fetch data", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const formatIDR = (val: number) => {
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(val);
  };

  const formatUSD = (val: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0b1120]">
        <div className="animate-pulse flex flex-col items-center">
          <Activity className="w-12 h-12 text-[#10b981] mb-4 animate-spin" />
          <h2 className="text-xl font-bold text-gray-200">Initializing Core Engine...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0b1120] text-gray-100 p-6 font-sans">

      {/* HEADER */}
      <header className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-extrabold flex items-center gap-3">
            <span className="text-gradient">AI Trading Node</span>
            <span className="bg-[#10b981]/10 text-[#10b981] text-xs py-1 px-3 rounded-full border border-[#10b981]/20">Active</span>
          </h1>
          <p className="text-gray-400 text-sm mt-1">Indodax Autonomous Trading System</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-400">System Time</p>
          <p className="font-mono text-lg">{new Date().toLocaleTimeString()}</p>
        </div>
      </header>

      {/* METRIC CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="glass-card p-6 rounded-2xl">
          <div className="flex justify-between items-start mb-4">
            <div>
              <p className="text-gray-400 text-sm">Total Equity</p>
              <h3 className="text-2xl font-bold mt-1 text-white">{formatIDR(portfolio?.total_equity || 0)}</h3>
            </div>
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Wallet className="w-6 h-6 text-blue-400" />
            </div>
          </div>
          <div className="flex gap-2 text-sm mt-2 font-medium">
            <span className="text-gray-400">Available:</span>
            <span>{formatIDR(portfolio?.available_balance || 0)}</span>
          </div>
        </div>

        <div className="glass-card p-6 rounded-2xl">
          <div className="flex justify-between items-start mb-4">
            <div>
              <p className="text-gray-400 text-sm">Unrealized PnL</p>
              <h3 className={`text-2xl font-bold mt-1 ${(portfolio?.unrealized_pnl || 0) >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                {(portfolio?.unrealized_pnl || 0) >= 0 ? '+' : ''}{formatIDR(portfolio?.unrealized_pnl || 0)}
              </h3>
            </div>
            <div className={`p-3 rounded-xl ${(portfolio?.unrealized_pnl || 0) >= 0 ? 'bg-[#10b981]/10' : 'bg-[#ef4444]/10'}`}>
              {(portfolio?.unrealized_pnl || 0) >= 0 ? <TrendingUp className="w-6 h-6 text-[#10b981]" /> : <TrendingDown className="w-6 h-6 text-[#ef4444]" />}
            </div>
          </div>
        </div>

        <div className="glass-card p-6 rounded-2xl">
          <div className="flex justify-between items-start mb-4">
            <div>
              <p className="text-gray-400 text-sm">Realized Today</p>
              <h3 className={`text-2xl font-bold mt-1 ${(portfolio?.realized_pnl_today || 0) >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                {(portfolio?.realized_pnl_today || 0) >= 0 ? '+' : ''}{formatIDR(portfolio?.realized_pnl_today || 0)}
              </h3>
            </div>
            <div className="p-3 bg-purple-500/10 rounded-xl">
              <Activity className="w-6 h-6 text-purple-400" />
            </div>
          </div>
        </div>

        <div className="glass-card p-6 rounded-2xl">
          <div className="flex justify-between items-start mb-4">
            <div>
              <p className="text-gray-400 text-sm">Active Exposure</p>
              <h3 className="text-2xl font-bold mt-1 text-white">{portfolio?.open_positions || 0} Positions</h3>
            </div>
            <div className="p-3 bg-orange-500/10 rounded-xl">
              <AlertCircle className="w-6 h-6 text-orange-400" />
            </div>
          </div>
          <div className="flex gap-2 text-sm mt-2">
            <span className="text-gray-400">Drawdown:</span>
            <span className={`${(portfolio?.daily_drawdown_pct || 0) > 3 ? 'text-[#ef4444]' : 'text-[#10b981]'}`}>
              {portfolio?.daily_drawdown_pct.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      {/* CHARTS ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">

        {/* EQUITY CURVE */}
        <div className="lg:col-span-2 glass-card px-8 py-6 rounded-2xl flex flex-col">
          <div className="flex items-center gap-2 mb-6">
            <BarChart2 className="w-5 h-5 text-gray-400" />
            <h2 className="text-lg font-bold text-white tracking-wide">Equity Curve</h2>
          </div>
          <div className="h-[400px] w-full">
            {equityData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equityData}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    stroke="#475569"
                    tickFormatter={(val: string) => val.split(' ')[1].slice(0, 5)}
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    stroke="#475569"
                    tickFormatter={(val) => `Rp ${(val / 1000000).toFixed(1)}M`}
                    tick={{ fill: '#94a3b8', fontSize: 12 }}
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#fff' }}
                    itemStyle={{ color: '#3b82f6' }}
                  />
                  <Area type="natural" dataKey="value" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                <p>Not enough history recorded</p>
              </div>
            )}
          </div>
        </div>

        {/* VOLUME ANOMALIES FEED */}
        <div className="glass-card px-6 py-6 rounded-2xl flex flex-col h-full min-h-[400px] max-h-[500px]">
          <div className="flex items-center gap-2 mb-6 border-b border-gray-800/60 pb-4">
            <Activity className="w-5 h-5 text-[#10b981]" />
            <h2 className="text-lg font-bold text-white tracking-wide">Live Volume Feed</h2>
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
            {anomalies.length === 0 && <p className="text-gray-500 text-center py-4">No recent anomalies detected</p>}

            {anomalies.map((anom) => (
              <div key={anom.id} className="border-l-2 pl-4 py-1" style={{ borderColor: anom.side === 'buy' ? '#10b981' : '#ef4444' }}>
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-gray-200 text-sm">{anom.symbol}</span>
                  <span className="text-[11px] text-gray-500 font-medium">{anom.timestamp.split('T')[1].slice(0, 5)}</span>
                </div>
                <div className="flex items-center gap-2 text-sm mt-1">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${anom.side === 'buy' ? 'bg-[#10b981]/10 text-[#10b981]' : 'bg-[#ef4444]/10 text-[#ef4444]'}`}>
                    {anom.side.toUpperCase()}
                  </span>
                  <span className="text-gray-300 font-mono">{formatUSD(anom.amount_usd)}</span>
                </div>
                <p className="text-xs text-gray-500 mt-1 uppercase tracking-wider">{anom.type.replace('_', ' ')}</p>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* POSITIONS TABLE */}
      <div className="glass-card p-6 rounded-2xl mb-8 overflow-hidden">
        <div className="flex items-center gap-2 mb-6">
          <ListIcon className="w-5 h-5 text-gray-400" />
          <h2 className="text-lg font-bold text-white">Active Positions</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-700/50 text-xs uppercase tracking-wider text-gray-400">
                <th className="pb-3 px-4">Symbol</th>
                <th className="pb-3 px-4">Side</th>
                <th className="pb-3 px-4 text-right">Entry Price</th>
                <th className="pb-3 px-4 text-right">Current</th>
                <th className="pb-3 px-4 text-right">P&L</th>
                <th className="pb-3 px-4 text-right">Stop Loss</th>
                <th className="pb-3 px-4 text-right">Take Profit</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {positions.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-gray-500">No active positions holding</td>
                </tr>
              )}
              {positions.map(pos => (
                <tr key={pos.id} className="border-b border-gray-800/30 hover:bg-white/5 transition-colors">
                  <td className="py-4 px-4 font-bold text-white">{pos.symbol}</td>
                  <td className="py-4 px-4">
                    <span className={`px-2 py-1 inline-block rounded text-xs font-bold ${pos.side === 'buy' ? 'bg-[#10b981]/20 text-[#10b981]' : 'bg-[#ef4444]/20 text-[#ef4444]'}`}>
                      {pos.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right font-mono text-gray-300">{pos.entry_price.toLocaleString('id-ID')}</td>
                  <td className="py-4 px-4 text-right font-mono text-gray-300">{pos.current_price.toLocaleString('id-ID')}</td>
                  <td className={`py-4 px-4 text-right font-bold ${pos.unrealized_pnl >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toLocaleString('id-ID')}
                    <span className="block text-xs font-normal mt-0.5">{pos.unrealized_pnl_pct >= 0 ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}%</span>
                  </td>
                  <td className="py-4 px-4 text-right text-orange-400/80 font-mono">{pos.stop_loss.toLocaleString('id-ID')}</td>
                  <td className="py-4 px-4 text-right text-blue-400/80 font-mono">{pos.take_profit.toLocaleString('id-ID')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}

export default App;
