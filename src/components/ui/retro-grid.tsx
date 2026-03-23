import { cn } from "@/lib/utils";
import React from "react";

export function RetroGrid({
  className,
  angle = 65,
}: {
  className?: string;
  angle?: number;
}) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden [perspective:200px]",
        className,
      )}
      style={{ "--grid-angle": `${angle}deg` } as React.CSSProperties}
    >
      {/* Grid */}
      <div className="absolute inset-0 [transform:rotateX(var(--grid-angle))]">
        <div
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(35,200,130,0.15) 1px, transparent 0), linear-gradient(to bottom, rgba(35,200,130,0.15) 1px, transparent 0)",
            backgroundSize: "60px 60px",
            height: "300vh",
            width: "600vw",
            marginLeft: "-50%",
            transformOrigin: "100% 0 0",
            backgroundRepeat: "repeat",
            animation: "grid 15s linear infinite, grid-fade 8s ease-in-out infinite",
          }}
        />
      </div>

      {/* Bottom fade */}
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(to top, #0B0E11 0%, transparent 90%)",
        }}
      />
    </div>
  );
}
