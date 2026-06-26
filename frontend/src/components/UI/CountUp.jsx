import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

// Tween a numeric value from 0 (or `from`) up to `value` over `duration` ms.
// Eased toward the end. Used by TestResults + the XP bar.
export default function CountUp({ value, from = 0, duration = 800, format = (n) => Math.round(n) }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : from);
  const startRef = useRef(null);
  const startVal = useRef(from);

  useEffect(() => {
    if (reduce) {
      setShown(value);
      return;
    }
    startRef.current = null;
    startVal.current = shown;
    let raf = 0;
    function tick(t) {
      if (startRef.current == null) startRef.current = t;
      const elapsed = t - startRef.current;
      const u = Math.min(1, elapsed / duration);
      // easeOutCubic
      const e = 1 - Math.pow(1 - u, 3);
      setShown(startVal.current + (value - startVal.current) * e);
      if (u < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration, reduce]);

  return <>{format(shown)}</>;
}
