import React from 'react';
import { cn } from '@/lib/utils';

export interface Avatar {
  id: string;
  emoji: string;
  name: string;
}

interface AvatarSelectorProps {
  avatars: Avatar[];
  selectedId: string;
  onSelect: (id: string) => void;
  size?: 'small' | 'medium' | 'large';
}

const sizeClasses = {
  small: 'w-12 h-12 text-lg',
  medium: 'w-16 h-16 text-2xl',
  large: 'w-20 h-20 text-4xl',
};

const gridClasses = {
  small: 'grid-cols-6 sm:grid-cols-8 md:grid-cols-10',
  medium: 'grid-cols-4 sm:grid-cols-5 md:grid-cols-8',
  large: 'grid-cols-3 sm:grid-cols-4 md:grid-cols-6',
};

export const AvatarSelector: React.FC<AvatarSelectorProps> = ({
  avatars,
  selectedId,
  onSelect,
  size = 'medium',
}) => {
  return (
    <div className={cn(
      'grid gap-2',
      gridClasses[size]
    )}>
      {avatars.map((avatar) => {
        const isSelected = selectedId === avatar.id;
        return (
          <button
            key={avatar.id}
            onClick={() => onSelect(avatar.id)}
            title={avatar.name}
            className={cn(
              sizeClasses[size],
              'rounded-lg flex items-center justify-center transition-all duration-300 transform hover:scale-110 active:scale-95',
              isSelected
                ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 ring-2 ring-indigo-400 shadow-lg'
                : 'bg-slate-700 hover:bg-slate-600 border border-slate-600'
            )}
          >
            {avatar.emoji}
          </button>
        );
      })}
    </div>
  );
};

export default AvatarSelector;
