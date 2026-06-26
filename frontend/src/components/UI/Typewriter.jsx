import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

// Reveals `text` character-by-character. Used for coach messages so Priya
// feels like she's actually typing in Slack. Respects prefers-reduced-motion
// (renders the full text instantly in that case).
export default function Typewriter({ text, charDelay = 18, onDone }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? text : '');

  useEffect(() => {
    if (reduce) {
      setShown(text);
      onDone && onDone();
      return;
    }
    let i = 0;
    setShown('');
    const id = setInterval(() => {
      i++;
      setShown(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
        onDone && onDone();
      }
    }, charDelay);
    return () => clearInterval(id);
  }, [text, charDelay, reduce, onDone]);

  const done = shown.length >= text.length;

  return (
    <span className="whitespace-pre-wrap">
      {shown}
      {!done && (
        <span
          className="inline-block w-[1px] h-[1em] align-baseline ml-[1px] bg-current animate-pulse"
          aria-hidden="true"
        />
      )}
    </span>
  );
}
