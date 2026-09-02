interface SkeletonProps {
  count?: number;
}

export function Skeleton({ count = 3 }: SkeletonProps) {
  return (
    <div aria-label="불러오는 중">
      {Array.from({ length: count }, (_, index) => <div className="skeleton" key={index} />)}
    </div>
  );
}

