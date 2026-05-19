import { RefObject, useEffect, useMemo, useRef, useState } from "react";

type VisibleItemsOptions = {
  initialCount?: number;
  step?: number;
  rootMargin?: string;
};

type VisibleItemsResult<T> = {
  visibleItems: T[];
  hasMore: boolean;
  loadMoreRef: RefObject<HTMLDivElement>;
};

const DEFAULT_INITIAL_COUNT = 12;
const DEFAULT_STEP = 12;
const DEFAULT_ROOT_MARGIN = "240px 0px";

export function useVisibleItems<T>(
  items: T[],
  options: VisibleItemsOptions = {},
): VisibleItemsResult<T> {
  const initialCount = Math.max(options.initialCount ?? DEFAULT_INITIAL_COUNT, 1);
  const step = Math.max(options.step ?? DEFAULT_STEP, 1);
  const rootMargin = options.rootMargin ?? DEFAULT_ROOT_MARGIN;
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const [visibleCount, setVisibleCount] = useState(initialCount);

  useEffect(() => {
    setVisibleCount(initialCount);
  }, [initialCount, items]);

  const hasMore = visibleCount < items.length;
  const visibleItems = useMemo(
    () => items.slice(0, visibleCount),
    [items, visibleCount],
  );

  useEffect(() => {
    if (!hasMore) {
      return;
    }
    const node = loadMoreRef.current;
    if (!node) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleCount((prev) => Math.min(prev + step, items.length));
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore, items.length, rootMargin, step]);

  return {
    visibleItems,
    hasMore,
    loadMoreRef,
  };
}
