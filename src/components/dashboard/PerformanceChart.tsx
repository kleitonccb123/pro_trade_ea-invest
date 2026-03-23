import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, Calendar, DollarSign } from 'lucide-react';
import { cn } from '@/lib/utils';

const data = [
  { date: '01/01', value: 10000 },
  { date: '05/01', value: 12500 },
  { date: '10/01', value: 11800 },
  { date: '15/01', value: 14200 },
  { date: '20/01', value: 13500 },
  { date: '25/01', value: 16800 },
  { date: '30/01', value: 18500 },
];

const periods = ['7D', '30D', '90D', '1A'] as const;
type Period = typeof periods[number];

export function PerformanceChart() {
  const [activePeriod, setActivePeriod] = useState<Period>('30D');

  // Calculate stats
  const currentValue = data[data.length - 1].value;
  const initialValue = data[0].value;
  const changePercent = ((currentValue - initialValue) / initialValue) * 100;
  const changeValue = currentValue - initialValue;

  return (
    <div className="glass-card p-4 lg:p-6 h-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 lg:mb-6">
        <div>
          <h3 className="text-base lg:text-lg font-semibold text-foreground flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            Performance
          </h3>
          <p className="text-xs lg:text-sm text-muted-foreground">Últimos 30 dias</p>
        </div>
        <div className="flex gap-1 lg:gap-2 bg-muted/50 p-1 rounded-lg">
          {periods.map((period) => (
            <button
              key={period}
              onClick={() => setActivePeriod(period)}
              className={cn(
                "px-2 lg:px-3 py-1 lg:py-1.5 rounded-md text-xs font-medium transition-all",
                period === activePeriod 
                  ? 'bg-primary text-primary-foreground shadow-sm' 
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              )}
            >
              {period}
            </button>
          ))}
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="p-3 bg-muted/30 rounded-xl">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <DollarSign className="w-3 h-3" />
            Valor Atual
          </div>
          <p className="text-lg lg:text-xl font-bold font-mono text-foreground">
            ${currentValue.toLocaleString()}
          </p>
        </div>
        <div className="p-3 bg-muted/30 rounded-xl">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <Calendar className="w-3 h-3" />
            Variação
          </div>
          <p className={cn(
            "text-lg lg:text-xl font-bold font-mono",
            changePercent >= 0 ? "text-success" : "text-destructive"
          )}>
            {changePercent >= 0 ? '+' : ''}{changePercent.toFixed(1)}%
          </p>
        </div>
      </div>
      
      <div className="h-48 lg:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(187 85% 53%)" stopOpacity={0.4} />
                <stop offset="95%" stopColor="hsl(187 85% 53%)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 18%)" vertical={false} />
            <XAxis 
              dataKey="date" 
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'hsl(215 20% 55%)', fontSize: 10 }}
              dy={10}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'hsl(215 20% 55%)', fontSize: 10 }}
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
              width={45}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(222 47% 10%)',
                border: '1px solid hsl(217 33% 18%)',
                borderRadius: '8px',
                color: 'hsl(210 40% 98%)',
                fontSize: '12px',
              }}
              formatter={(value: number) => [`$${value.toLocaleString()}`, 'Valor']}
              labelStyle={{ color: 'hsl(215 20% 55%)' }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="hsl(187 85% 53%)"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorValue)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
