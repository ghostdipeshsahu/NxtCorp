import { useEffect, useRef } from 'react';

// Custom orange dot cursor (spec §4). Grows on hover over interactive
// elements, contracts on click. Pure CSS class swap — no per-frame React
// state to keep the cost off the main thread.
//
// Respects coarse pointer (touch devices): no custom cursor there.
export default function CustomCursor() {
  const ref = useRef(null);

  useEffect(() => {
    const coarse =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(pointer: coarse)').matches;
    if (coarse) return; // skip on touch
    const reduce =
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) return; // don't add cursor effects when reduced motion

    const el = document.createElement('div');
    el.className = 'nxt-cursor';
    document.body.appendChild(el);
    ref.current = el;

    function onMove(e) {
      el.style.transform = `translate(${e.clientX}px, ${e.clientY}px) translate(-50%, -50%)`;
    }
    function onDown() {
      el.classList.add('is-down');
    }
    function onUp() {
      el.classList.remove('is-down');
    }
    function onOver(e) {
      const t = e.target;
      const interactive =
        t && (
          t.tagName === 'BUTTON' ||
          t.tagName === 'A' ||
          t.tagName === 'INPUT' ||
          t.tagName === 'TEXTAREA' ||
          (t.closest && t.closest('button, a, [role="button"]'))
        );
      el.classList.toggle('is-hover', !!interactive);
    }

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerdown', onDown);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointerover', onOver);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointerover', onOver);
      el.remove();
    };
  }, []);

  return null;
}
