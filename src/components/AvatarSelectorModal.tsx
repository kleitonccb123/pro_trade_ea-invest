import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { CheckCircle2 } from 'lucide-react';

interface Avatar {
  id: string;
  emoji: string;
  name: string;
}

interface AvatarSelectorModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  avatars: Avatar[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function AvatarSelectorModal({
  open,
  onOpenChange,
  avatars,
  selectedId,
  onSelect,
}: AvatarSelectorModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-white">Escolha seu Avatar</DialogTitle>
          <DialogDescription>
            Selecione um avatar de trader para seu perfil
          </DialogDescription>
        </DialogHeader>
        
        <div className="grid grid-cols-4 gap-4 py-6">
          {avatars.map((avatar) => {
            const isSelected = avatar.id === selectedId;
            return (
              <button
                key={avatar.id}
                onClick={() => {
                  onSelect(avatar.id);
                  onOpenChange(false);
                }}
                className={`flex flex-col items-center justify-center gap-2 p-4 rounded-xl transition-all duration-300 ${
                  isSelected
                    ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 ring-2 ring-indigo-400 shadow-lg shadow-indigo-500/50'
                    : 'bg-slate-700/50 hover:bg-slate-600/50 hover:scale-105'
                }`}
              >
                <span className="text-4xl">{avatar.emoji}</span>
                <span className="text-xs font-medium text-white text-center">{avatar.name}</span>
                {isSelected && (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-1" />
                )}
              </button>
            );
          })}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-slate-700">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-slate-600 text-slate-300 hover:bg-slate-700/50"
          >
            Cancelar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
