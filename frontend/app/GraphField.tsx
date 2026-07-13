"use client";

import { useEffect, useRef } from "react";

// Interactive knowledge-graph field for the landing hero.
//
// Design constraints (deliberate):
// - One requestAnimationFrame loop that only draws to canvas -- it never
//   reads or writes layout, so it cannot cause reflow.
// - The pointer is *eased* toward its target (lerp) so the field lags the
//   cursor instead of snapping -- calm, not twitchy.
// - prefers-reduced-motion renders a single static frame and never animates.
// - The loop pauses when the hero scrolls offscreen or the tab is hidden.
// - Device pixel ratio is capped at 2 to bound fill-rate on 4k displays.

type Node = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  hub: boolean;
};

const LINK_DISTANCE = 130;
const POINTER_RADIUS = 200;
const POINTER_EASE = 0.055;
const DRIFT_SPEED = 0.12;

function buildNodes(width: number, height: number, seedFn: () => number): Node[] {
  const count = Math.max(40, Math.min(110, Math.floor((width * height) / 16000)));
  return Array.from({ length: count }, () => ({
    x: seedFn() * width,
    y: seedFn() * height,
    vx: (seedFn() - 0.5) * DRIFT_SPEED * 2,
    vy: (seedFn() - 0.5) * DRIFT_SPEED * 2,
    radius: 1 + seedFn() * 1.4,
    hub: seedFn() < 0.08,
  }));
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  nodes: Node[],
  width: number,
  height: number,
  pointer: { x: number; y: number; active: boolean },
) {
  ctx.clearRect(0, 0, width, height);

  // Edges between nearby nodes.
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distance = Math.hypot(dx, dy);
      if (distance < LINK_DISTANCE) {
        const alpha = (1 - distance / LINK_DISTANCE) * 0.13;
        ctx.strokeStyle = `rgba(61, 220, 151, ${alpha.toFixed(3)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
  }

  // Edges from the eased pointer to nodes inside its radius -- the cursor
  // behaves like a temporary node joining the graph.
  if (pointer.active) {
    for (const node of nodes) {
      const distance = Math.hypot(node.x - pointer.x, node.y - pointer.y);
      if (distance < POINTER_RADIUS) {
        const alpha = (1 - distance / POINTER_RADIUS) * 0.22;
        ctx.strokeStyle = `rgba(232, 179, 75, ${alpha.toFixed(3)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.lineTo(pointer.x, pointer.y);
        ctx.stroke();
      }
    }
  }

  // Nodes on top.
  for (const node of nodes) {
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.hub ? node.radius + 1 : node.radius, 0, Math.PI * 2);
    ctx.fillStyle = node.hub
      ? "rgba(232, 179, 75, 0.9)"
      : "rgba(61, 220, 151, 0.55)";
    ctx.fill();
  }
}

export default function GraphField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    let width = 0;
    let height = 0;
    let nodes: Node[] = [];
    let frameId = 0;
    let running = false;
    let inView = true;

    const pointer = { x: 0, y: 0, active: false };
    const pointerTarget = { x: 0, y: 0, active: false };

    const configure = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      nodes = buildNodes(width, height, Math.random);
      if (reducedMotion) {
        // Static fallback: one composed frame, no loop.
        drawFrame(ctx, nodes, width, height, { x: 0, y: 0, active: false });
      }
    };

    const step = () => {
      if (!running) return;

      // Ease the pointer toward its target -- the lag is the effect.
      pointer.x += (pointerTarget.x - pointer.x) * POINTER_EASE;
      pointer.y += (pointerTarget.y - pointer.y) * POINTER_EASE;
      pointer.active = pointerTarget.active;

      for (const node of nodes) {
        node.x += node.vx;
        node.y += node.vy;

        // Soft attraction toward the eased pointer.
        if (pointer.active) {
          const dx = pointer.x - node.x;
          const dy = pointer.y - node.y;
          const distance = Math.hypot(dx, dy);
          if (distance > 1 && distance < POINTER_RADIUS) {
            const pull = (1 - distance / POINTER_RADIUS) * 0.012;
            node.x += (dx / distance) * pull * distance * 0.1;
            node.y += (dy / distance) * pull * distance * 0.1;
          }
        }

        // Wrap at the edges with a small margin so nodes re-enter smoothly.
        if (node.x < -20) node.x = width + 20;
        if (node.x > width + 20) node.x = -20;
        if (node.y < -20) node.y = height + 20;
        if (node.y > height + 20) node.y = -20;
      }

      drawFrame(ctx, nodes, width, height, pointer);
      frameId = requestAnimationFrame(step);
    };

    const start = () => {
      if (!running && !reducedMotion && inView && !document.hidden) {
        running = true;
        frameId = requestAnimationFrame(step);
      }
    };
    const stop = () => {
      running = false;
      cancelAnimationFrame(frameId);
    };

    const onPointerMove = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointerTarget.x = event.clientX - rect.left;
      pointerTarget.y = event.clientY - rect.top;
      pointerTarget.active = true;
    };
    const onPointerLeave = () => {
      pointerTarget.active = false;
    };
    const onVisibility = () => (document.hidden ? stop() : start());

    configure();
    start();

    const resizeObserver = new ResizeObserver(() => {
      stop();
      configure();
      start();
    });
    resizeObserver.observe(canvas);

    const intersectionObserver = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      if (inView) start();
      else stop();
    });
    intersectionObserver.observe(canvas);

    // Listen on the hero section (canvas's parent) so text on top of the
    // canvas does not block the interaction.
    const surface = canvas.parentElement ?? canvas;
    surface.addEventListener("pointermove", onPointerMove);
    surface.addEventListener("pointerleave", onPointerLeave);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      surface.removeEventListener("pointermove", onPointerMove);
      surface.removeEventListener("pointerleave", onPointerLeave);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="absolute inset-0 h-full w-full"
    />
  );
}
