"use client";

import { useEffect, useRef } from "react";

type Point = {
  x: number;
  y: number;
  phase: number;
  radius: number;
};

export function TelemetryField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let animation = 0;
    let width = 0;
    let height = 0;
    let points: Point[] = [];

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = bounds.width;
      height = bounds.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      points = Array.from({ length: 34 }, (_, index) => ({
        x: ((index * 83 + 41) % 1000) / 1000,
        y: ((index * 137 + 73) % 900) / 900,
        phase: index * 0.61,
        radius: index % 7 === 0 ? 1.8 : 1,
      }));
    };

    const draw = () => {
      context.clearRect(0, 0, width, height);
      const time = reducedMotion.matches ? 0 : frame * 0.004;

      const plotted = points.map((point) => ({
        x: point.x * width + Math.sin(time + point.phase) * 11,
        y: point.y * height + Math.cos(time * 0.7 + point.phase) * 8,
        radius: point.radius,
      }));

      for (let first = 0; first < plotted.length; first += 1) {
        for (let second = first + 1; second < plotted.length; second += 1) {
          const dx = plotted[first].x - plotted[second].x;
          const dy = plotted[first].y - plotted[second].y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance < 155) {
            context.beginPath();
            context.moveTo(plotted[first].x, plotted[first].y);
            context.lineTo(plotted[second].x, plotted[second].y);
            context.strokeStyle = `rgba(140, 124, 255, ${0.13 * (1 - distance / 155)})`;
            context.lineWidth = 0.7;
            context.stroke();
          }
        }
      }

      plotted.forEach((point, index) => {
        context.beginPath();
        context.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
        context.fillStyle =
          index % 7 === 0 ? "rgba(200, 255, 61, 0.72)" : "rgba(140, 124, 255, 0.42)";
        context.fill();
      });

      frame += 1;
      if (!reducedMotion.matches) {
        animation = window.requestAnimationFrame(draw);
      }
    };

    resize();
    draw();
    window.addEventListener("resize", resize);

    return () => {
      window.cancelAnimationFrame(animation);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="telemetry-field" aria-hidden="true" />;
}
