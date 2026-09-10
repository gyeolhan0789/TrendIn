import type { Trend } from '../types/trend';

interface SparklineProps {
  trend: Trend;
  width?: number;
  height?: number;
  color?: string;
}

function makeSeries(trend: Trend, count = 14) {
  const growth = Math.max(-20, Math.min(240, trend.growthRate));
  const start = 14 + ((trend.keyword.length * 7) % 12);
  return Array.from({ length: count }, (_, index) => {
    const progress = index / (count - 1);
    const wave = ((trend.keyword.charCodeAt(index % trend.keyword.length) ?? 40) % 9) - 4;
    return Math.max(4, start + progress * (growth * 0.28 + 26) + wave + (index > count - 4 ? growth * 0.08 : 0));
  });
}

function getSparkPoints(values: number[], width: number, height: number) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values.map((value, index) => `${((index / (values.length - 1)) * width).toFixed(1)},${(height - ((value - min) / span) * height).toFixed(1)}`).join(' ');
}

export function Sparkline({ trend, width = 72, height = 26, color = '#4966d8' }: SparklineProps) {
  const points = getSparkPoints(makeSeries(trend, 7), width, height);
  const lastPoint = points.split(' ').at(-1)?.split(',') ?? [String(width), String(height)];
  return (
    <svg className="trend-sparkline" viewBox={`0 0 ${width} ${height}`} width={width} height={height} preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastPoint[0]} cy={lastPoint[1]} r="2.3" fill={color} />
    </svg>
  );
}
