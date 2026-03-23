import React, { useEffect, useState } from 'react';

interface Particle {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  color: string;
}

interface FireworksProps {
  trigger?: boolean;
  onComplete?: () => void;
  position?: { x: number; y: number };
}

export default function Fireworks({ trigger = false, onComplete, position = { x: 50, y: 50 } }: FireworksProps) {
  const [particles, setParticles] = useState<Particle[]>([]);
  const [isActive, setIsActive] = useState(false);

  const colors = [
    '#00FF41', // Neon Green
    '#23C882', // KuCoin Green
    '#FF006E', // Pink/Magenta
    '#FFBE0B', // Yellow
    '#FB5607', // Orange
    '#8338EC', // Purple
    '#3A86FF', // Blue
  ];

  useEffect(() => {
    if (!trigger) return;

    setIsActive(true);
    const newParticles: Particle[] = [];

    // Criar partículas de fogos
    for (let i = 0; i < 60; i++) {
      const angle = (Math.PI * 2 * i) / 60;
      const velocity = 4 + Math.random() * 6;

      newParticles.push({
        id: i,
        x: position.x,
        y: position.y,
        vx: Math.cos(angle) * velocity,
        vy: Math.sin(angle) * velocity,
        life: 1,
        color: colors[Math.floor(Math.random() * colors.length)],
      });
    }

    setParticles(newParticles);

    // Animar partículas
    const animationInterval = setInterval(() => {
      setParticles((prev) => {
        const updated = prev
          .map((p) => ({
            ...p,
            x: p.x + p.vx,
            y: p.y + p.vy,
            vy: p.vy + 0.2, // Gravidade
            life: p.life - 0.02,
          }))
          .filter((p) => p.life > 0);

        if (updated.length === 0) {
          setIsActive(false);
          onComplete?.();
        }

        return updated;
      });
    }, 20);

    return () => clearInterval(animationInterval);
  }, [trigger]);

  if (!isActive && particles.length === 0) return null;

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden">
      {particles.map((p) => (
        <div
          key={p.id}
          className="absolute w-2 h-2 rounded-full"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            backgroundColor: p.color,
            opacity: p.life,
            boxShadow: `0 0 10px ${p.color}`,
            transform: `translate(-50%, -50%)`,
            transition: 'none',
          }}
        />
      ))}
    </div>
  );
}
