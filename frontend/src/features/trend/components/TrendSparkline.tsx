interface TrendSparklineProps {
  /** 그릴 값들. 서버에서 받은 실제 언급량만 넘깁니다. */
  points: number[];
  width?: number;
  height?: number;
  color?: string;
  /** 선 아래를 옅게 채웁니다. 큰 차트에서 추이가 더 잘 읽힙니다. */
  filled?: boolean;
  /** 채움 그러데이션 id가 svg마다 겹치면 안 되어 부르는 쪽이 정합니다. */
  gradientId?: string;
  className?: string;
}

function toPolyline(values: number[], width: number, height: number) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  // 값이 하나뿐이면 나눌 구간이 없어 가운데 높이의 가로선으로 둡니다.
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values
    .map((value, index) => `${(index * step).toFixed(1)},${(height - ((value - min) / span) * height).toFixed(1)}`)
    .join(' ');
}

/**
 * 언급량 추이를 한 줄로 보여 줍니다. 값은 부르는 쪽이 넘기므로 이 컴포넌트가 수치를 지어내지 않습니다.
 */
export function TrendSparkline({
  points,
  width = 120,
  height = 32,
  color = '#818cf8',
  filled = false,
  gradientId,
  className = '',
}: TrendSparklineProps) {
  if (points.length === 0) return null;

  const line = toPolyline(points, width, height);
  const last = line.split(' ').at(-1)?.split(',') ?? [String(width), String(height)];
  const fillId = gradientId ?? 'trend-spark-fill';

  return (
    <svg className={`trend-sparkline ${className}`} viewBox={`0 0 ${width} ${height}`} width={width} height={height} preserveAspectRatio="none" aria-hidden="true">
      {filled && (
        <>
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.16" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <polygon points={`0,${height} ${line} ${width},${height}`} fill={`url(#${fillId})`} />
        </>
      )}
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r="2.3" fill={color} />
    </svg>
  );
}
