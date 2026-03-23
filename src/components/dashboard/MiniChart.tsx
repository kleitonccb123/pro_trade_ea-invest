import { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface ChartData {
  name: string;
  value: number;
  [key: string]: any;
}

interface MiniChartProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  type: 'bar' | 'line';
  data: ChartData[];
  dataKey: string;
  color?: string;
  height?: number;
  className?: string;
}

export function MiniChart({
  title,
  description,
  icon,
  type,
  data,
  dataKey,
  color = '#06b6d4',
  height = 200,
  className,
}: MiniChartProps) {
  const colorGradient = type === 'line' ? '#06b6d4' : '#06b6d4';

  return (
    <Card className={cn(
      'glass-card border-white/5 bg-gradient-to-br from-card/60 to-card/30',
      className
    )}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          {icon && (
            <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-sm">
              {icon}
            </div>
          )}
          <div className="flex-1">
            <CardTitle className="text-sm">{title}</CardTitle>
            {description && (
              <CardDescription className="text-xs">{description}</CardDescription>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          {type === 'bar' ? (
            <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.5)' }} />
              <YAxis tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.5)' }} />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  color: '#fff'
                }}
              />
              <Bar dataKey={dataKey} fill={colorGradient} radius={[8, 8, 0, 0]} />
            </BarChart>
          ) : (
            <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.5)' }} />
              <YAxis tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.5)' }} />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  color: '#fff'
                }}
              />
              <Line dataKey={dataKey} stroke={colorGradient} strokeWidth={2} dot={false} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
