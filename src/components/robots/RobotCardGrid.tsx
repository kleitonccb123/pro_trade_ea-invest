import { useState } from 'react';
import { Settings, TrendingUp, TrendingDown, Activity, Lock, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Robot } from '@/types/robot';

const COUNTRY_FLAGS: { [key: string]: { flag: string; name: string; code: string } } = {
  'usa': { flag: '🇺🇸', name: 'USA', code: 'US' },
  'us': { flag: '🇺🇸', name: 'USA', code: 'US' },
  'japan': { flag: '🇯🇵', name: 'Japan', code: 'JP' },
  'jp': { flag: '🇯🇵', name: 'Japan', code: 'JP' },
  'china': { flag: '🇨🇳', name: 'China', code: 'CN' },
  'cn': { flag: '🇨🇳', name: 'China', code: 'CN' },
  'germany': { flag: '🇩🇪', name: 'Germany', code: 'DE' },
  'de': { flag: '🇩🇪', name: 'Germany', code: 'DE' },
  'uk': { flag: '🇬🇧', name: 'UK', code: 'GB' },
  'gb': { flag: '🇬🇧', name: 'UK', code: 'GB' },
  'france': { flag: '🇫🇷', name: 'France', code: 'FR' },
  'fr': { flag: '🇫🇷', name: 'France', code: 'FR' },
  'brazil': { flag: '🇧🇷', name: 'Brazil', code: 'BR' },
  'br': { flag: '🇧🇷', name: 'Brazil', code: 'BR' },
  'singapore': { flag: '🇸🇬', name: 'Singapore', code: 'SG' },
  'sg': { flag: '🇸🇬', name: 'Singapore', code: 'SG' },
  'south-korea': { flag: '🇰🇷', name: 'Korea', code: 'KR' },
  'kr': { flag: '🇰🇷', name: 'Korea', code: 'KR' },
  'india': { flag: '🇮🇳', name: 'India', code: 'IN' },
  'in': { flag: '🇮🇳', name: 'India', code: 'IN' },
};

interface RobotCardGridProps {
  robot: Robot & { country?: string; description?: string; activeUsers?: number };
  onSelect: (robot: Robot) => void;
  isSelected?: boolean;
  isLocked?: boolean;
}

export function RobotCardGrid({ robot, onSelect, isSelected, isLocked = false }: RobotCardGridProps) {
  const [isHovered, setIsHovered] = useState(false);

  const countryKey = robot.country?.toLowerCase() || 'usa';
  const countryInfo = COUNTRY_FLAGS[countryKey] || { flag: '🌍', name: 'Global', code: 'GL' };

  const statusIndicatorColor = {
    active: 'from-emerald-500 to-green-600',
    paused: 'from-amber-500 to-yellow-600',
    stopped: 'from-slate-500 to-gray-600',
    error: 'from-red-500 to-rose-600',
  };

  const statusBgColor = {
    active: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    paused: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    stopped: 'bg-slate-500/10 border-slate-500/30 text-slate-400',
    error: 'bg-red-500/10 border-red-500/30 text-red-400',
  };

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onSelect(robot)}
      className={`cursor-pointer transition-all duration-300 ${isSelected ? 'ring-2 ring-blue-500' : ''} relative`}
    >
      {/* Professional Card Design */}
      <div className={`bg-slate-900 border border-slate-800 rounded-lg overflow-hidden hover:border-slate-700 transition-all duration-300 flex flex-col h-full shadow-md hover:shadow-lg hover:shadow-blue-500/10 ${isLocked ? 'grayscale-[0.5] opacity-90' : ''}`}>
        
        {/* Lock Overlay */}
        {isLocked && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 backdrop-blur-[1px] group-hover:bg-black/30 transition-all">
                <div className="bg-slate-900/90 p-3 rounded-full border border-yellow-500/50 shadow-lg shadow-yellow-500/20 animate-pulse">
                    <Lock className="w-6 h-6 text-yellow-500" />
                </div>
            </div>
        )}

        {/* Header - Status and Country Badge */}
        <div className="px-5 py-4 flex items-start justify-between border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            {/* Country Flag Badge */}
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center border border-blue-400/30">
              <span className="text-sm font-bold text-white">{countryInfo.code}</span>
            </div>
            <div>
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Par</p>
              <p className="text-sm font-bold text-white">{robot.pair}</p>
            </div>
          </div>

          {/* Status Badge */}
          <div className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border flex items-center gap-1.5 ${statusBgColor[robot.status as keyof typeof statusBgColor]}`}>
            <div className="w-2 h-2 rounded-full bg-current opacity-80 animate-pulse"></div>
            {robot.status}
          </div>
        </div>

        {/* Main Content Area */}
        <div className="px-5 py-4 flex-1 space-y-3">
          {/* Robot Name */}
          <div>
            <p className="text-sm font-bold text-white leading-tight">
              {robot.name}
            </p>
          </div>

          {/* Key Metrics - 2x2 Grid */}
          <div className="grid grid-cols-2 gap-3">
            {/* Win Rate */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded p-2.5">
              <p className="text-xs text-slate-400 font-semibold uppercase mb-1">Taxa Acerto</p>
              <p className="text-lg font-bold text-emerald-400">{(robot.winRate || 0).toFixed(1)}%</p>
            </div>

            {/* Trades */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded p-2.5">
              <p className="text-xs text-slate-400 font-semibold uppercase mb-1">Trades</p>
              <p className="text-lg font-bold text-white">{robot.trades}</p>
            </div>

            {/* Profit */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded p-2.5">
              <p className="text-xs text-slate-400 font-semibold uppercase mb-1">Lucro</p>
              <div className="flex items-center gap-1.5">
                {robot.profit >= 0 ? (
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-red-400" />
                )}
                <p className={`text-lg font-bold ${robot.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  ${Math.abs(robot.profit).toFixed(0)}
                </p>
              </div>
            </div>

            {/* Status Indicator */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded p-2.5">
              <p className="text-xs text-slate-400 font-semibold uppercase mb-1">Timeframe</p>
              <p className="text-lg font-bold text-blue-400">{robot.timeframe || '1h'}</p>
            </div>
          </div>
        </div>

        {/* Footer - Action Button & Robot Icon */}
        <div className="px-5 py-4 border-t border-slate-800 bg-slate-900/50 flex flex-col gap-3">
            <Button
                onClick={(e) => {
                e.stopPropagation();
                onSelect(robot);
                }}
                disabled={isLocked}
                className={`w-full gap-2 h-9 font-semibold text-sm transition-all duration-200 ${isLocked ? 'bg-slate-800 text-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}
            >
                {isLocked ? (
                    <>
                        <Lock className="w-4 h-4" />
                        Bloqueado
                    </>
                ) : (
                    <>
                        <Settings className={`w-4 h-4 ${isHovered ? 'rotate-90' : ''} transition-transform`} />
                        Configurar
                    </>
                )}
            </Button>
            
            <div className="flex justify-center pt-2 border-t border-slate-800/50">
                 <Bot className="w-6 h-6 text-slate-600 hover:text-blue-400 transition-colors" />
            </div>
        </div>
      </div>
    </div>
  );
}
