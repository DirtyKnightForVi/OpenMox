"use client";

import { ArrowsClockwise, MoonStars } from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";

interface ReflectButtonProps {
  onQuickReflect: () => void;
  onShenduReflect: () => void;
  isLoading?: boolean;
}

export function ReflectButtons({ onQuickReflect, onShenduReflect, isLoading }: ReflectButtonProps) {
  return (
    <div className="flex items-center gap-2">
      <Button variant="secondary" size="sm" onClick={onQuickReflect} disabled={isLoading}>
        <ArrowsClockwise size={14} className={isLoading ? "animate-spin" : ""} />
        Quick Reflect
      </Button>
      <Button variant="secondary" size="sm" onClick={onShenduReflect} disabled={isLoading}>
        <MoonStars size={14} />
        Shendu
      </Button>
    </div>
  );
}
