import { useState, useEffect } from 'react';
import { 
  Play, 
  Clock, 
  CheckCircle, 
  Lock, 
  Star, 
  BookOpen,
  TrendingUp,
  Bot,
  Shield,
  Zap,
  ChevronRight,
  PlayCircle,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { apiCall } from '@/services/apiClient';

interface Video {
  id: string;
  title: string;
  description: string;
  duration: string;
  thumbnail: string;
  isCompleted: boolean;
  isLocked: boolean;
  videoUrl?: string;
}

interface Module {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  gradient: string;
  videos: Video[];
  progress: number;
}

const modules: Module[] = [
  {
    id: 'intro',
    title: 'Introdução ao Trading',
    description: 'Fundamentos essenciais para começar no mercado de criptomoedas',
    icon: BookOpen,
    gradient: 'from-blue-500 to-cyan-500',
    progress: 100,
    videos: [
      {
        id: '1',
        title: 'O que é Bitcoin?',
        description: 'Aprenda sobre a primeira criptomoeda do mundo',
        duration: '12:45',
        thumbnail: '₿',
        isCompleted: true,
        isLocked: false,
      },
      {
        id: '2',
        title: 'Carteiras e Segurança',
        description: 'Como proteger seus ativos digitais',
        duration: '18:20',
        thumbnail: '🔐',
        isCompleted: true,
        isLocked: false,
      },
      {
        id: '3',
        title: 'Primeiras Transações',
        description: 'Seu primeiro passo no mercado crypto',
        duration: '15:30',
        thumbnail: '💸',
        isCompleted: true,
        isLocked: false,
      },
    ]
  },
  {
    id: 'robots',
    title: 'Robôs de Trading',
    description: 'Automação inteligente do seu portfólio',
    icon: Bot,
    gradient: 'from-orange-500 to-red-500',
    progress: 66,
    videos: [
      {
        id: '4',
        title: 'Introdução aos Robôs',
        description: 'Como os robôs podem te ajudar',
        duration: '14:15',
        thumbnail: '🤖',
        isCompleted: true,
        isLocked: false,
      },
      {
        id: '5',
        title: 'Configurações Básicas',
        description: 'Setup inicial para seu primeiro robô',
        duration: '22:00',
        thumbnail: '⚙️',
        isCompleted: true,
        isLocked: false,
      },
      {
        id: '6',
        title: 'Estratégias Avançadas',
        description: 'Maximize seus lucros com algoritmos inteligentes',
        duration: '28:45',
        thumbnail: '📊',
        isCompleted: false,
        isLocked: true,
      },
    ]
  },
  {
    id: 'strategies',
    title: 'Estratégias de Investimento',
    description: 'Aprenda técnicas profissionais de trading',
    icon: TrendingUp,
    gradient: 'from-purple-500 to-pink-500',
    progress: 0,
    videos: [
      {
        id: '7',
        title: 'Análise Técnica 101',
        description: 'Fundamentos de gráficos e indicadores',
        duration: '19:30',
        thumbnail: '📈',
        isCompleted: false,
        isLocked: true,
      },
      {
        id: '8',
        title: 'Suporte e Resistência',
        description: 'Identifique pontos-chave de mercado',
        duration: '16:20',
        thumbnail: '🎯',
        isCompleted: false,
        isLocked: true,
      },
      {
        id: '9',
        title: 'Padrões de Candlestick',
        description: 'Domine a leitura de velas japonesas',
        duration: '24:10',
        thumbnail: '🕯️',
        isCompleted: false,
        isLocked: true,
      },
    ]
  },
  {
    id: 'risk',
    title: 'Gestão de Risco',
    description: 'Proteja seu capital em todas as situações',
    icon: Shield,
    gradient: 'from-green-500 to-teal-500',
    progress: 0,
    videos: [
      {
        id: '10',
        title: 'Stop Loss e Take Profit',
        description: 'Ferramentas essenciais de proteção',
        duration: '13:50',
        thumbnail: '🛑',
        isCompleted: false,
        isLocked: true,
      },
      {
        id: '11',
        title: 'Gestão de Posição',
        description: 'Tamanhe corretamente suas operações',
        duration: '17:40',
        thumbnail: '⚖️',
        isCompleted: false,
        isLocked: true,
      },
      {
        id: '12',
        title: 'Diversificação de Portfolio',
        description: 'Distribua seus investimentos inteligentemente',
        duration: '20:15',
        thumbnail: '🎲',
        isCompleted: false,
        isLocked: true,
      },
    ]
  }
];

export default function VideoAulas() {
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [playingVideo, setPlayingVideo] = useState<Video | null>(null);
  const [apiModules, setApiModules] = useState<Module[] | null>(null);
  const [loadingModules, setLoadingModules] = useState(true);

  // Fetch courses from backend; keep static data as fallback
  useEffect(() => {
    apiCall('/api/education/courses')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        const courses: any[] = Array.isArray(data) ? data : (data?.courses ?? []);
        if (courses.length === 0) return; // stay with static fallback
        const iconMap: Record<string, React.ElementType> = {
          trading: TrendingUp, bots: Bot, risk: Shield, intro: BookOpen,
        };
        const gradients = ['from-blue-500 to-cyan-500', 'from-orange-500 to-red-500',
          'from-purple-500 to-pink-500', 'from-green-500 to-teal-500'];
        setApiModules(courses.map((c: any, idx: number) => ({
          id: c.id ?? String(idx),
          title: c.title ?? 'Curso',
          description: c.description ?? '',
          icon: iconMap[c.category] ?? BookOpen,
          gradient: gradients[idx % gradients.length],
          videos: [],
          progress: 0,
        })));
      })
      .catch(() => { /* stay with static fallback */ })
      .finally(() => setLoadingModules(false));
  }, []);

  // Lazy-load lessons when a module from the API is expanded
  useEffect(() => {
    if (!selectedModule || !apiModules) return;
    const apiMod = apiModules.find(m => m.id === selectedModule.id);
    if (!apiMod || apiMod.videos.length > 0) return;
    apiCall(`/api/education/courses/${selectedModule.id}/lessons`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        const lessons: any[] = Array.isArray(data) ? data : (data?.lessons ?? []);
        const videos: Video[] = lessons.map((l: any) => ({
          id: l.id ?? String(l._id ?? Math.random()),
          title: l.title ?? 'Aula',
          description: l.description ?? '',
          duration: l.duration_minutes ? `${l.duration_minutes}:00` : '0:00',
          thumbnail: '📹',
          isCompleted: false,
          isLocked: l.is_premium ?? false,
          videoUrl: l.video_url,
        }));
        setApiModules(prev =>
          prev ? prev.map(m => m.id === selectedModule.id ? { ...m, videos } : m) : prev
        );
        setSelectedModule(prev => prev?.id === selectedModule.id ? { ...prev, videos } : prev);
      })
      .catch(() => { /* keep empty video list */ });
  }, [selectedModule?.id, apiModules]);

  const displayModules = apiModules ?? modules;


  const handlePlayVideo = (video: Video) => {
    if (!video.isLocked) {
      setPlayingVideo(video);
    }
  };

  const totalVideos = displayModules.reduce((acc, mod) => acc + mod.videos.length, 0);
  const completedVideos = displayModules.reduce((acc, mod) => 
    acc + mod.videos.filter(v => v.isCompleted).length, 0
  );
  const totalTime = displayModules.reduce((acc, mod) => {
    const moduleTime = mod.videos.reduce((sum, v) => {
      const [minutes, seconds] = v.duration.split(':').map(Number);
      return sum + (minutes * 60 + seconds);
    }, 0);
    return acc + moduleTime;
  }, 0);

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}min`;
    return `${minutes}min`;
  };

  return (
    <div className="min-h-screen bg-background p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 md:gap-3">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <PlayCircle className="w-4 h-4 text-white" />
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-foreground">Vídeo Aulas</h1>
          </div>
          <p className="text-xs md:text-sm text-muted-foreground">
            Aprenda a dominar o trading com nossos cursos completos
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <div className="glass-card p-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0 mb-1">
              <BookOpen className="w-4 h-4 text-blue-500" />
            </div>
            <div className="text-xs text-muted-foreground">Módulos</div>
            <div className="text-lg font-bold text-foreground">{displayModules.length}</div>
          </div>

          <div className="glass-card p-3">
            <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center flex-shrink-0 mb-1">
              <Play className="w-4 h-4 text-orange-500" />
            </div>
            <div className="text-xs text-muted-foreground">Total</div>
            <div className="text-lg font-bold text-foreground">{totalVideos}</div>
          </div>

          <div className="glass-card p-3">
            <div className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center flex-shrink-0 mb-1">
              <CheckCircle className="w-4 h-4 text-green-500" />
            </div>
            <div className="text-xs text-muted-foreground">Concluídas</div>
            <div className="text-lg font-bold text-foreground">{completedVideos}</div>
          </div>

          <div className="glass-card p-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0 mb-1">
              <Clock className="w-4 h-4 text-purple-500" />
            </div>
            <div className="text-xs text-muted-foreground">Tempo</div>
            <div className="text-lg font-bold text-foreground">{formatTime(totalTime)}</div>
          </div>
        </div>
      </div>

      {/* Modules Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {loadingModules ? (
          <div className="col-span-2 flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : displayModules.map((module) => (
          <div
            key={module.id}
            className={cn(
              "glass-card p-6 cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:shadow-xl",
              selectedModule?.id === module.id && "ring-2 ring-primary"
            )}
            onClick={() => setSelectedModule(selectedModule?.id === module.id ? null : module)}
          >
            {/* Module Header */}
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "w-10 h-10 rounded-lg flex items-center justify-center bg-gradient-to-br text-white flex-shrink-0",
                  module.gradient
                )}>
                  <module.icon className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-foreground">{module.title}</h3>
                  <p className="text-xs text-muted-foreground truncate">{module.description}</p>
                </div>
              </div>
              <ChevronRight className={cn(
                "w-5 h-5 text-muted-foreground transition-transform flex-shrink-0",
                selectedModule?.id === module.id && "rotate-90"
              )} />
            </div>

            {/* Progress */}
            <div className="flex items-center gap-2 mb-2">
              <Progress value={module.progress} className="flex-1 h-1.5" />
              <span className="text-xs font-medium text-muted-foreground w-6">{module.progress}%</span>
            </div>

            {/* Videos Count */}
            <div className="flex items-center justify-between text-xs gap-2">
              <span className="text-muted-foreground">
                {module.videos.filter(v => v.isCompleted).length}/{module.videos.length}
              </span>
              <Badge variant={module.progress === 100 ? "default" : "secondary"} className="text-xs">
                {module.progress === 100 ? "✓" : "Em progresso"}
              </Badge>
            </div>

            {/* Expanded Video List */}
            {selectedModule?.id === module.id && (
              <div className="mt-2 space-y-1 border-t border-border/50 pt-2">
                {module.videos.map((video) => (
                  <div
                    key={video.id}
                    className={cn(
                      "flex items-center gap-2 p-2 rounded text-xs transition-all",
                      video.isLocked 
                        ? "bg-muted/30 opacity-60" 
                        : "bg-card/50 hover:bg-card cursor-pointer"
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePlayVideo(video);
                    }}
                  >
                    {/* Thumbnail */}
                    <div className={cn(
                      "w-8 h-8 rounded flex items-center justify-center text-lg flex-shrink-0",
                      video.isCompleted ? "bg-green-500/20" : "bg-primary/20"
                    )}>
                      {video.isLocked ? (
                        <Lock className="w-3 h-3 text-muted-foreground" />
                      ) : (
                        video.thumbnail
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <h4 className="font-medium text-foreground truncate text-xs">{video.title}</h4>
                        {video.isCompleted && (
                          <CheckCircle className="w-3 h-3 text-green-500 flex-shrink-0" />
                        )}
                      </div>
                    </div>

                    {/* Duration & Play */}
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        {video.duration}
                      </div>
                      {!video.isLocked && (
                        <Button size="sm" variant="ghost" className="w-6 h-6 p-0">
                          <Play className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Video Player Modal */}
      {playingVideo && (
        <div 
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setPlayingVideo(null)}
        >
          <div 
            className="w-full max-w-4xl bg-card rounded-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Video Player Placeholder */}
            <div className="aspect-video bg-black flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-4">
                  <Play className="w-10 h-10 text-primary" />
                </div>
                <p className="text-white text-lg font-medium">{playingVideo.title}</p>
                <p className="text-white/60 text-sm mt-1">Clique para reproduzir</p>
              </div>
            </div>
            
            {/* Video Info */}
            <div className="p-3 md:p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="text-base md:text-lg font-semibold text-foreground truncate">{playingVideo.title}</h3>
                  <p className="text-xs md:text-sm text-muted-foreground line-clamp-1">{playingVideo.description}</p>
                </div>
                <Button size="sm" onClick={() => setPlayingVideo(null)} className="flex-shrink-0">Fechar</Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Call to Action */}
      <div className="glass-card p-4 md:p-6 text-center bg-gradient-to-r from-primary/10 via-transparent to-accent/10">
        <Zap className="w-8 h-8 text-primary mx-auto mb-2" />
        <h3 className="text-lg md:text-xl font-bold text-foreground mb-1">
          Quer desbloquear todo o conteúdo?
        </h3>
        <p className="text-xs md:text-sm text-muted-foreground mb-3 max-w-xl mx-auto">
          Faça upgrade para Premium e tenha acesso a todos os módulos, estratégias avançadas e suporte.
        </p>
        <Button size="sm" className="bg-gradient-to-r from-primary to-accent">
          <Star className="w-4 h-4 mr-1.5" />
          Upgrade para Premium
        </Button>
      </div>
    </div>
  );
}
