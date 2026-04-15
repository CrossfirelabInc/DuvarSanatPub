import { useState, useRef, useCallback, useEffect } from "react";

interface ComparisonSliderProps {
  beforeUrl: string;
  afterUrl: string;
  beforeLabel?: string;
  afterLabel?: string;
}

function ComparisonSlider({
  beforeUrl,
  afterUrl,
  beforeLabel = "Before",
  afterLabel = "After",
}: ComparisonSliderProps) {
  const [position, setPosition] = useState(50);
  const [height, setHeight] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const beforeRef = useRef<HTMLImageElement>(null);
  const afterRef = useRef<HTMLImageElement>(null);
  const dragging = useRef(false);

  const calcHeight = useCallback(() => {
    const bImg = beforeRef.current;
    const aImg = afterRef.current;
    if (!bImg || !aImg) return;
    // Use naturalWidth/Height if loaded, otherwise wait
    if (bImg.naturalWidth === 0 || aImg.naturalWidth === 0) return;
    const w = containerRef.current?.clientWidth || 600;
    const bH = (bImg.naturalHeight / bImg.naturalWidth) * w;
    const aH = (aImg.naturalHeight / aImg.naturalWidth) * w;
    setHeight(Math.min(bH, aH));
  }, []);

  // Recalc when URLs change — use a small delay so refs update
  useEffect(() => {
    setHeight(0);
    const timer = setTimeout(calcHeight, 50);
    return () => clearTimeout(timer);
  }, [beforeUrl, afterUrl, calcHeight]);

  // Recalc on window resize
  useEffect(() => {
    const onResize = () => calcHeight();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [calcHeight]);

  const updatePosition = useCallback((clientX: number) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = clientX - rect.left;
    setPosition(Math.max(0, Math.min(100, (x / rect.width) * 100)));
  }, []);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      dragging.current = true;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      updatePosition(e.clientX);
    },
    [updatePosition]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (dragging.current) updatePosition(e.clientX);
    },
    [updatePosition]
  );

  const handlePointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const ready = height > 0;

  return (
    <div
      ref={containerRef}
      className="comparison-container"
      style={{ height: ready ? height : "auto" }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <img
        ref={beforeRef}
        src={beforeUrl}
        alt={beforeLabel}
        className="comparison-img"
        style={ready ? { height, objectFit: "cover" } : undefined}
        draggable={false}
        onLoad={calcHeight}
      />
      <img
        ref={afterRef}
        src={afterUrl}
        alt={afterLabel}
        className="comparison-img comparison-img-after"
        style={{
          clipPath: `inset(0 0 0 ${position}%)`,
          ...(ready ? { height, objectFit: "cover" } : {}),
        }}
        draggable={false}
        onLoad={calcHeight}
      />

      {position > 10 && (
        <span className="comparison-label comparison-label-before">
          {beforeLabel}
        </span>
      )}
      {position < 90 && (
        <span className="comparison-label comparison-label-after">
          {afterLabel}
        </span>
      )}

      <div className="comparison-divider" style={{ left: `${position}%` }}>
        <div className="comparison-handle" />
      </div>
    </div>
  );
}

export default ComparisonSlider;
