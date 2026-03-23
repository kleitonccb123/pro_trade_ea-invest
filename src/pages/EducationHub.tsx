/**
 * EducationHub.tsx - Centro de Educação com Cursos e Vídeos
 * 
 * Integra com:
 * - GET /education/courses
 * - GET /education/courses/{id}
 * - GET /education/courses/{id}/lessons
 * - POST /education/courses/{id}/enroll
 * - POST /education/progress
 * - GET /education/my-courses
 * 
 * Features:
 * - Lista de cursos com filtros
 * - Player de vídeo com progresso
 * - Tracking de conclusão
 * - Certificados
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { 
  Play, Pause, CheckCircle2, Circle, Lock, Crown,
  ChevronDown, ChevronRight, Clock, BookOpen, GraduationCap,
  Loader2, PlayCircle, Award, FileText, Download,
  Volume2, VolumeX, Maximize, SkipBack, SkipForward,
  Filter, Search, Star, Users, BarChart, HelpCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { useToast } from '@/hooks/use-toast';
import useApi from '@/hooks/useApi';
import { authService } from '@/services/authService';

// ============== TYPES ==============

interface Course {
  id: string;
  title: string;
  description: string;
  thumbnail_url: string | null;
  level: string;
  category: string;
  tags: string[];
  lesson_count: number;
  estimated_duration: number;
  is_premium: boolean;
  required_license: string | null;
  instructor_name: string | null;
  enrolled_count: number;
  rating: number;
  review_count: number;
  status: string;
  is_enrolled?: boolean;
  enrollment?: Enrollment;
}

interface Lesson {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  type: string;
  order: number;
  video_url: string | null;
  video_duration: number | null;
  video_provider: string | null;
  content_html: string | null;
  is_preview: boolean;
  is_downloadable: boolean;
  resources: Array<{ title: string; url: string; type: string }>;
}

interface LessonProgress {
  lesson_id: string;
  watched_seconds: number;
  completed: boolean;
  completed_at?: string;
}

interface QuizQuestion {
  question: string;
  options: string[];
  explanation?: string;
  // only present after submission:
  correct_index?: number;
  user_answer?: number;
  is_correct?: boolean;
}

interface QuizAttempt {
  id: string;
  score: number;
  passed: boolean;
  attempted_at: string;
}

interface QuizData {
  id: string;
  title: string;
  passing_score: number;
  questions: QuizQuestion[];
}

interface Enrollment {
  id: string;
  course_id: string;
  enrolled_at: string;
  progress_percent: number;
  lessons_completed: number;
  total_lessons: number;
  certificate_issued?: boolean;
  lessons?: LessonProgress[];
}

// ============== COMPONENT ==============

export default function EducationHub() {
  const { courseId, lessonId } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { toast } = useToast();
  const videoRef = useRef<HTMLVideoElement>(null);

  // View mode
  const [view, setView] = useState<'browse' | 'course' | 'lesson'>(
    courseId ? (lessonId ? 'lesson' : 'course') : 'browse'
  );

  // Data state
  const [courses, setCourses] = useState<Course[]>([]);
  const [myCourses, setMyCourses] = useState<Enrollment[]>([]);
  const [currentCourse, setCurrentCourse] = useState<Course | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [currentLesson, setCurrentLesson] = useState<Lesson | null>(null);
  
  // UI state
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState<string>('all');
  const [activeTab, setActiveTab] = useState('all');

  // Video state
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [lastSavedTime, setLastSavedTime] = useState(0);

  // Quiz state
  const [quizData, setQuizData] = useState<QuizData | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<number[]>([]);
  const [quizResult, setQuizResult] = useState<{
    score: number;
    passed: boolean;
    correct_count: number;
    total_questions: number;
    questions_review: QuizQuestion[];
  } | null>(null);
  const [quizLoading, setQuizLoading] = useState(false);
  const [showQuiz, setShowQuiz] = useState(false);

  // ============== DATA FETCHING ==============

  useEffect(() => {
    if (view === 'browse') {
      fetchCourses();
      fetchMyCourses();
    }
  }, [view]);

  useEffect(() => {
    if (courseId) {
      setView(lessonId ? 'lesson' : 'course');
      fetchCourseWithLessons(courseId);
    } else {
      setView('browse');
    }
  }, [courseId, lessonId]);

  useEffect(() => {
    if (lessonId && lessons.length > 0) {
      const lesson = lessons.find(l => l.id === lessonId);
      if (lesson) {
        setCurrentLesson(lesson);
        // Restore progress
        const progress = currentCourse?.enrollment?.lessons?.find(
          l => l.lesson_id === lessonId
        );
        if (progress && videoRef.current) {
          videoRef.current.currentTime = progress.watched_seconds;
        }
      }
    }
  }, [lessonId, lessons]);

  const fetchCourses = async () => {
    try {
      const result = await api.get<{ courses: Course[]; total: number }>(
        '/education/courses?status=published'
      );
      setCourses(result.courses || []);
    } catch (err) {
      console.error('Failed to fetch courses:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMyCourses = async () => {
    try {
      const result = await api.get<{ enrollments: Enrollment[] }>('/education/my-courses');
      setMyCourses(result.enrollments || []);
    } catch (err) {
      console.error('Failed to fetch my courses:', err);
    }
  };

  const fetchCourseWithLessons = async (id: string) => {
    setLoading(true);
    try {
      const [course, lessonsResult] = await Promise.all([
        api.get<Course>(`/education/courses/${id}`),
        api.get<{ lessons: Lesson[] }>(`/education/courses/${id}/lessons`)
      ]);
      
      setCurrentCourse(course);
      setLessons(lessonsResult.lessons || []);
      
      // Se está em view de lesson mas não tem lessonId, seleciona primeira aula
      if (!lessonId && lessonsResult.lessons.length > 0) {
        setCurrentLesson(lessonsResult.lessons[0]);
      }
    } catch (err: any) {
      console.error('Failed to fetch course:', err);
      toast({
        title: 'Erro',
        description: 'Não foi possível carregar o curso.',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  // ============== HANDLERS ==============

  const handleEnroll = async () => {
    if (!currentCourse) return;
    
    setEnrolling(true);
    try {
      await api.post(`/education/courses/${currentCourse.id}/enroll`);
      toast({
        title: '🎉 Matrícula Realizada!',
        description: 'Você já pode começar a assistir.'
      });
      fetchCourseWithLessons(currentCourse.id);
    } catch (err: any) {
      toast({
        title: 'Erro na Matrícula',
        description: err.message,
        variant: 'destructive'
      });
    } finally {
      setEnrolling(false);
    }
  };

  const handleSelectLesson = (lesson: Lesson) => {
    // Verifica se pode acessar
    if (!currentCourse?.is_enrolled && !lesson.is_preview) {
      toast({
        title: '🔒 Aula Bloqueada',
        description: 'Faça sua matrícula para acessar.',
      });
      return;
    }
    // Reset quiz state when changing lessons
    setQuizData(null);
    setQuizResult(null);
    setQuizAnswers([]);
    setShowQuiz(false);
    navigate(`/educacao/${currentCourse?.id}/aula/${lesson.id}`);
    // Fetch quiz for every lesson (quiz may have been added to any lesson type)
    if (currentCourse?.id) {
      fetchQuiz(lesson.id, currentCourse.id);
    }
  };

  const saveProgress = useCallback(async (completed: boolean = false) => {
    if (!currentLesson || !currentCourse?.is_enrolled) return;
    
    // Evita salvar muito frequentemente
    const now = Date.now();
    if (!completed && now - lastSavedTime < 10000) return;
    
    try {
      await api.post('/education/progress', {
        lesson_id: currentLesson.id,
        course_id: currentCourse.id,
        watched_seconds: Math.floor(currentTime),
        completed
      });
      
      setLastSavedTime(now);
      
      if (completed) {
        toast({
          title: '✅ Aula Concluída!',
          description: 'Progresso salvo.'
        });
        fetchCourseWithLessons(currentCourse.id);
      }
    } catch (err) {
      console.error('Failed to save progress:', err);
    }
  }, [currentLesson, currentCourse, currentTime, lastSavedTime]);

  const handleVideoTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      
      // Salva a cada 30 segundos
      if (Math.floor(videoRef.current.currentTime) % 30 === 0) {
        saveProgress();
      }
    }
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
    saveProgress(true);
    
    // Próxima aula após 3 segundos
    const idx = lessons.findIndex(l => l.id === currentLesson?.id);
    if (idx >= 0 && idx < lessons.length - 1) {
      const next = lessons[idx + 1];
      setTimeout(() => handleSelectLesson(next), 3000);
    }
  };

  const fetchQuiz = async (lessonId: string, courseId: string) => {
    setQuizData(null);
    setQuizResult(null);
    setQuizAnswers([]);
    setShowQuiz(false);
    try {
      const result = await api.get<{ quiz: QuizData; latest_attempt: QuizAttempt | null }>(
        `/education/courses/${courseId}/lessons/${lessonId}/quiz`
      );
      if (result.quiz?.questions?.length > 0) {
        setQuizData(result.quiz);
        setQuizAnswers(new Array(result.quiz.questions.length).fill(-1));
      }
    } catch {
      // no quiz for this lesson
    }
  };

  const handleSubmitQuiz = async () => {
    if (!quizData || !currentLesson || !currentCourse) return;
    setQuizLoading(true);
    try {
      const result = await api.post<{
        score: number;
        passed: boolean;
        correct_count: number;
        total_questions: number;
        questions_review: QuizQuestion[];
      }>(
        `/education/courses/${currentCourse.id}/lessons/${currentLesson.id}/quiz`,
        { answers: quizAnswers }
      );
      setQuizResult(result);
      if (result.passed) {
        toast({ title: '🎉 Aprovado!', description: `Pontuação: ${result.score}%` });
        fetchCourseWithLessons(currentCourse.id);
      } else {
        toast({
          title: `Quiz: ${result.score}%`,
          description: `Mínimo: ${quizData.passing_score}%. Tente novamente!`,
          variant: 'destructive',
        });
      }
    } catch (err: any) {
      toast({ title: 'Erro', description: err.message, variant: 'destructive' });
    } finally {
      setQuizLoading(false);
    }
  };

  const handleDownloadCertificate = async () => {
    if (!currentCourse) return;
    try {
      // Open PDF in new tab
      const token = authService.getAccessToken() || '';
      const base = (window as any).__API_BASE__ || '';
      window.open(
        `${base}/education/courses/${currentCourse.id}/certificate?format=pdf`,
        '_blank'
      );
    } catch (err: any) {
      toast({ title: 'Erro', description: err.message, variant: 'destructive' });
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  // ============== HELPERS ==============

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDuration = (minutes: number) => {
    if (minutes < 60) return `${minutes}min`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}min`;
  };

  const isLessonCompleted = (lessonId: string): boolean => {
    return currentCourse?.enrollment?.lessons?.some(
      l => l.lesson_id === lessonId && l.completed
    ) || false;
  };

  const getLevelColor = (level: string) => {
    const colors: Record<string, string> = {
      beginner: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      intermediate: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      advanced: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      expert: 'bg-red-500/20 text-red-400 border-red-500/30'
    };
    return colors[level] || colors.beginner;
  };

  const getLevelLabel = (level: string) => {
    const labels: Record<string, string> = {
      beginner: 'Iniciante',
      intermediate: 'Intermediário',
      advanced: 'Avançado',
      expert: 'Expert'
    };
    return labels[level] || level;
  };

  const filteredCourses = courses.filter(course => {
    const matchesSearch = !searchQuery || 
      course.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      course.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLevel = levelFilter === 'all' || course.level === levelFilter;
    const matchesTab = activeTab === 'all' || 
      (activeTab === 'enrolled' && myCourses.some(m => m.course_id === course.id));
    return matchesSearch && matchesLevel && matchesTab;
  });

  // ============== RENDER: BROWSE VIEW ==============

  if (view === 'browse') {
    return (
      <div className="min-h-screen bg-slate-950 p-6">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                <GraduationCap className="w-8 h-8 text-blue-500" />
                Centro de Educação
              </h1>
              <p className="text-slate-400 mt-1">
                Aprenda trading com nossos cursos exclusivos
              </p>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Buscar cursos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 bg-slate-900 border-slate-800"
              />
            </div>
            <Select value={levelFilter} onValueChange={setLevelFilter}>
              <SelectTrigger className="w-48 bg-slate-900 border-slate-800">
                <SelectValue placeholder="Nível" />
              </SelectTrigger>
              <SelectContent className="bg-slate-900 border-slate-800">
                <SelectItem value="all">Todos os níveis</SelectItem>
                <SelectItem value="beginner">Iniciante</SelectItem>
                <SelectItem value="intermediate">Intermediário</SelectItem>
                <SelectItem value="advanced">Avançado</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-slate-800 border border-slate-700">
              <TabsTrigger value="all" className="data-[state=active]:bg-blue-600">
                Todos os Cursos
              </TabsTrigger>
              <TabsTrigger value="enrolled" className="data-[state=active]:bg-blue-600">
                Meus Cursos ({myCourses.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-6">
              {loading ? (
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {[1, 2, 3].map(i => (
                    <Skeleton key={i} className="h-80 bg-slate-800" />
                  ))}
                </div>
              ) : filteredCourses.length === 0 ? (
                <Card className="bg-slate-900 border-slate-800">
                  <CardContent className="py-12 text-center">
                    <BookOpen className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <h3 className="text-lg font-medium text-white">
                      Nenhum curso encontrado
                    </h3>
                    <p className="text-slate-400 mt-1">
                      Tente ajustar os filtros de busca
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredCourses.map((course) => {
                    const enrollment = myCourses.find(m => m.course_id === course.id);
                    
                    return (
                      <Card 
                        key={course.id}
                        className="bg-slate-900 border-slate-800 overflow-hidden hover:border-slate-700 transition-colors cursor-pointer group"
                        onClick={() => navigate(`/educacao/${course.id}`)}
                      >
                        {/* Thumbnail */}
                        <div className="aspect-video bg-slate-800 relative">
                          {course.thumbnail_url ? (
                            <img 
                              src={course.thumbnail_url} 
                              alt={course.title}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <PlayCircle className="w-16 h-16 text-slate-600" />
                            </div>
                          )}
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            <Play className="w-12 h-12 text-white" />
                          </div>
                          {course.is_premium && (
                            <Badge className="absolute top-2 right-2 bg-amber-500">
                              <Crown className="w-3 h-3 mr-1" />
                              PRO
                            </Badge>
                          )}
                        </div>

                        <CardContent className="p-4 space-y-3">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className={getLevelColor(course.level)}>
                              {getLevelLabel(course.level)}
                            </Badge>
                            <Badge variant="outline" className="border-slate-700">
                              {course.category}
                            </Badge>
                          </div>

                          <h3 className="font-semibold text-white line-clamp-2">
                            {course.title}
                          </h3>

                          <p className="text-sm text-slate-400 line-clamp-2">
                            {course.description}
                          </p>

                          <div className="flex items-center justify-between text-sm text-slate-500">
                            <span className="flex items-center gap-1">
                              <BookOpen className="w-4 h-4" />
                              {course.lesson_count} aulas
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="w-4 h-4" />
                              {formatDuration(course.estimated_duration)}
                            </span>
                          </div>

                          {enrollment && (
                            <div className="pt-2 border-t border-slate-800">
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-slate-400">Progresso</span>
                                <span className="text-emerald-400">
                                  {enrollment.progress_percent.toFixed(0)}%
                                </span>
                              </div>
                              <Progress value={enrollment.progress_percent} className="h-1" />
                            </div>
                          )}

                          {course.rating > 0 && (
                            <div className="flex items-center gap-2 pt-2">
                              <div className="flex items-center gap-1">
                                <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                                <span className="text-white font-medium">
                                  {course.rating.toFixed(1)}
                                </span>
                              </div>
                              <span className="text-slate-500 text-sm">
                                ({course.review_count} avaliações)
                              </span>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    );
  }

  // ============== RENDER: COURSE/LESSON VIEW ==============

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!currentCourse) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Card className="bg-slate-900 border-slate-800 p-8 text-center">
          <BookOpen className="w-12 h-12 mx-auto mb-4 text-slate-600" />
          <h2 className="text-xl font-medium text-white mb-2">Curso não encontrado</h2>
          <Button onClick={() => navigate('/educacao')}>
            Voltar aos Cursos
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex">
      {/* Sidebar */}
      <aside className="w-80 border-r border-slate-800 flex flex-col bg-slate-900/50">
        <div className="p-4 border-b border-slate-800">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/educacao')}
            className="mb-3 text-slate-400"
          >
            ← Voltar aos Cursos
          </Button>
          <h2 className="font-semibold text-white">{currentCourse.title}</h2>
          {currentCourse.enrollment && (
            <div className="mt-2">
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>{currentCourse.enrollment.lessons_completed}/{currentCourse.enrollment.total_lessons} aulas</span>
                <span>{currentCourse.enrollment.progress_percent.toFixed(0)}%</span>
              </div>
              <Progress value={currentCourse.enrollment.progress_percent} className="h-1" />
            </div>
          )}
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {lessons.map((lesson, idx) => {
              const completed = isLessonCompleted(lesson.id);
              const locked = !currentCourse.is_enrolled && !lesson.is_preview;
              const isCurrent = currentLesson?.id === lesson.id;

              return (
                <button
                  key={lesson.id}
                  onClick={() => handleSelectLesson(lesson)}
                  className={`w-full p-3 rounded-lg text-left flex items-center gap-3 transition-colors ${
                    isCurrent 
                      ? 'bg-blue-500/20 border border-blue-500/30' 
                      : locked
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:bg-slate-800'
                  }`}
                >
                  {completed ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                  ) : locked ? (
                    <Lock className="w-5 h-5 text-slate-500 flex-shrink-0" />
                  ) : isCurrent ? (
                    <PlayCircle className="w-5 h-5 text-blue-500 flex-shrink-0" />
                  ) : (
                    <Circle className="w-5 h-5 text-slate-600 flex-shrink-0" />
                  )}
                  
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm truncate ${isCurrent ? 'text-blue-400' : 'text-white'}`}>
                      {idx + 1}. {lesson.title}
                    </p>
                    {lesson.video_duration && (
                      <span className="text-xs text-slate-500">
                        {formatTime(lesson.video_duration)}
                      </span>
                    )}
                  </div>

                  {lesson.is_preview && !currentCourse.is_enrolled && (
                    <Badge variant="outline" className="text-xs border-slate-700">
                      Preview
                    </Badge>
                  )}
                </button>
              );
            })}
          </div>
        </ScrollArea>

        {/* Enroll CTA */}
        {!currentCourse.is_enrolled && (
          <div className="p-4 border-t border-slate-800">
            <Button
              onClick={handleEnroll}
              disabled={enrolling}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              {enrolling ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <PlayCircle className="w-4 h-4 mr-2" />
              )}
              Matricular-se Grátis
            </Button>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {currentLesson && view === 'lesson' ? (
          <>
            {/* Video Player */}
            <div className="relative bg-black aspect-video">
              {currentLesson.video_url ? (
                (() => {
                  const provider = currentLesson.video_provider;
                  const isYouTube =
                    provider === 'youtube' ||
                    currentLesson.video_url.includes('youtube.com') ||
                    currentLesson.video_url.includes('youtu.be');
                  const isVimeo =
                    provider === 'vimeo' ||
                    currentLesson.video_url.includes('vimeo.com');

                  if (isYouTube || isVimeo) {
                    // Extract embed URL
                    let embedUrl = currentLesson.video_url;
                    if (isYouTube && !embedUrl.includes('/embed/')) {
                      const m = embedUrl.match(
                        /(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/
                      );
                      if (m) embedUrl = `https://www.youtube.com/embed/${m[1]}`;
                    }
                    if (isVimeo && !embedUrl.includes('player.vimeo.com')) {
                      const m = embedUrl.match(/vimeo\.com\/(?:video\/)?(\d+)/);
                      if (m) embedUrl = `https://player.vimeo.com/video/${m[1]}`;
                    }
                    return (
                      <iframe
                        src={embedUrl}
                        className="w-full h-full"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        allowFullScreen
                        title={currentLesson.title}
                      />
                    );
                  }

                  // Direct video file
                  return (
                    <>
                      <video
                        ref={videoRef}
                        src={currentLesson.video_url}
                        className="w-full h-full"
                        muted={isMuted}
                        onTimeUpdate={handleVideoTimeUpdate}
                        onEnded={handleVideoEnded}
                        onLoadedMetadata={() => {
                          if (videoRef.current) {
                            setDuration(videoRef.current.duration);
                          }
                        }}
                      />

                      {/* Controls */}
                      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-4">
                        {/* Progress */}
                        <div
                          className="h-1.5 bg-slate-700 rounded-full mb-3 cursor-pointer group"
                          onClick={(e) => {
                            if (videoRef.current) {
                              const rect = e.currentTarget.getBoundingClientRect();
                              const percent = (e.clientX - rect.left) / rect.width;
                              videoRef.current.currentTime = percent * duration;
                            }
                          }}
                        >
                          <div
                            className="h-full bg-blue-500 rounded-full relative"
                            style={{ width: `${(currentTime / duration) * 100}%` }}
                          >
                            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        </div>

                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={togglePlay}
                              className="text-white hover:bg-white/10"
                            >
                              {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6" />}
                            </Button>

                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => videoRef.current && (videoRef.current.currentTime -= 10)}
                              className="text-white hover:bg-white/10"
                            >
                              <SkipBack className="w-5 h-5" />
                            </Button>

                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => videoRef.current && (videoRef.current.currentTime += 10)}
                              className="text-white hover:bg-white/10"
                            >
                              <SkipForward className="w-5 h-5" />
                            </Button>

                            <span className="text-white/80 text-sm ml-2">
                              {formatTime(currentTime)} / {formatTime(duration)}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setIsMuted(!isMuted)}
                              className="text-white hover:bg-white/10"
                            >
                              {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                            </Button>

                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => videoRef.current?.requestFullscreen()}
                              className="text-white hover:bg-white/10"
                            >
                              <Maximize className="w-5 h-5" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </>
                  );
                })()
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-400">
                  <div className="text-center">
                    <PlayCircle className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p>Vídeo não disponível</p>
                  </div>
                </div>
              )}
            </div>

            {/* Lesson Info */
            <div className="flex-1 overflow-auto p-6">
              <div className="max-w-3xl mx-auto space-y-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h1 className="text-2xl font-bold text-white">{currentLesson.title}</h1>
                    {currentLesson.description && (
                      <p className="mt-2 text-slate-400">{currentLesson.description}</p>
                    )}
                  </div>
                  
                  {currentCourse.is_enrolled && !isLessonCompleted(currentLesson.id) && (
                    <Button
                      onClick={() => saveProgress(true)}
                      className="bg-emerald-600 hover:bg-emerald-700 flex-shrink-0"
                    >
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Concluir Aula
                    </Button>
                  )}
                </div>

                {/* Resources */}
                {currentLesson.resources?.length > 0 && (
                  <Card className="bg-slate-900 border-slate-800">
                    <CardHeader>
                      <CardTitle className="text-white text-lg flex items-center gap-2">
                        <FileText className="w-5 h-5 text-blue-500" />
                        Materiais de Apoio
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {currentLesson.resources.map((resource, idx) => (
                        <a
                          key={idx}
                          href={resource.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-3 p-3 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors"
                        >
                          <Download className="w-4 h-4 text-blue-500" />
                          <span className="text-white flex-1">{resource.title}</span>
                          <Badge variant="outline" className="text-xs">
                            {resource.type}
                          </Badge>
                        </a>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* HTML Content */}
                {currentLesson.content_html && (
                  <Card className="bg-slate-900 border-slate-800">
                    <CardContent className="prose prose-invert max-w-none pt-6">
                      <div dangerouslySetInnerHTML={{ __html: currentLesson.content_html }} />
                    </CardContent>
                  </Card>
                )}

                {/* Quiz Section */}
                {quizData && quizData.questions.length > 0 && (
                  <Card className="bg-slate-900 border-slate-800">
                    <CardHeader>
                      <CardTitle className="text-white text-lg flex items-center gap-2">
                        <HelpCircle className="w-5 h-5 text-blue-500" />
                        {quizData.title}
                      </CardTitle>
                      <CardDescription className="text-slate-400">
                        Pontuação mínima para aprovação: {quizData.passing_score}%
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      {quizResult ? (
                        <div className="space-y-4">
                          <div className={`p-4 rounded-lg flex items-center gap-3 ${
                            quizResult.passed
                              ? 'bg-emerald-500/20 border border-emerald-500/30'
                              : 'bg-red-500/20 border border-red-500/30'
                          }`}>
                            {quizResult.passed
                              ? <CheckCircle2 className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                              : <Circle className="w-6 h-6 text-red-400 flex-shrink-0" />}
                            <div>
                              <p className="font-semibold text-white">
                                {quizResult.passed ? '🎉 Aprovado!' : 'Reprovado'} — {quizResult.score}%
                              </p>
                              <p className="text-sm text-slate-400">
                                {quizResult.correct_count} de {quizResult.total_questions} questões corretas
                              </p>
                            </div>
                          </div>
                          <div className="space-y-3">
                            {quizResult.questions_review.map((q, idx) => (
                              <div key={idx} className={`p-3 rounded-lg border ${
                                q.is_correct
                                  ? 'border-emerald-500/30 bg-emerald-500/10'
                                  : 'border-red-500/30 bg-red-500/10'
                              }`}>
                                <p className="text-white text-sm font-medium mb-2">{idx + 1}. {q.question}</p>
                                {q.options.map((opt, oi) => (
                                  <p key={oi} className={`text-xs py-0.5 ${
                                    oi === q.correct_index ? 'text-emerald-400 font-medium'
                                    : oi === q.user_answer && !q.is_correct ? 'text-red-400 line-through'
                                    : 'text-slate-500'
                                  }`}>
                                    {oi === q.correct_index ? '✓ ' : oi === q.user_answer && !q.is_correct ? '✗ ' : '  '}{opt}
                                  </p>
                                ))}
                                {q.explanation && (
                                  <p className="text-xs text-slate-400 mt-2 italic">{q.explanation}</p>
                                )}
                              </div>
                            ))}
                          </div>
                          {!quizResult.passed && (
                            <Button
                              variant="outline"
                              className="w-full"
                              onClick={() => {
                                setQuizResult(null);
                                setQuizAnswers(new Array(quizData.questions.length).fill(-1));
                              }}
                            >
                              Tentar Novamente
                            </Button>
                          )}
                        </div>
                      ) : !showQuiz ? (
                        <Button
                          onClick={() => setShowQuiz(true)}
                          className="w-full bg-blue-600 hover:bg-blue-700"
                        >
                          <HelpCircle className="w-4 h-4 mr-2" />
                          Fazer Quiz
                        </Button>
                      ) : (
                        <div className="space-y-6">
                          {quizData.questions.map((q, qi) => (
                            <div key={qi} className="space-y-2">
                              <p className="text-white font-medium text-sm">{qi + 1}. {q.question}</p>
                              {q.options.map((opt, oi) => (
                                <button
                                  key={oi}
                                  onClick={() => {
                                    const a = [...quizAnswers];
                                    a[qi] = oi;
                                    setQuizAnswers(a);
                                  }}
                                  className={`w-full text-left p-3 rounded-lg transition-colors text-sm ${
                                    quizAnswers[qi] === oi
                                      ? 'bg-blue-600/30 border border-blue-500/50 text-blue-300'
                                      : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                                  }`}
                                >
                                  {opt}
                                </button>
                              ))}
                            </div>
                          ))}
                          <Button
                            onClick={handleSubmitQuiz}
                            disabled={quizLoading || quizAnswers.includes(-1)}
                            className="w-full bg-blue-600 hover:bg-blue-700"
                          >
                            {quizLoading
                              ? <Loader2 className="w-4 h-4 animate-spin mr-2" />
                              : <CheckCircle2 className="w-4 h-4 mr-2" />}
                            Enviar Respostas
                          </Button>
                          {quizAnswers.includes(-1) && (
                            <p className="text-xs text-slate-500 text-center">
                              Responda todas as questões para enviar.
                            </p>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}

                {/* Certificate Banner */}
                {currentCourse.enrollment && currentCourse.enrollment.progress_percent >= 100 && (
                  <Card className="bg-gradient-to-r from-amber-500/20 to-yellow-500/20 border border-amber-500/30">
                    <CardContent className="py-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <Award className="w-8 h-8 text-amber-400 flex-shrink-0" />
                          <div>
                            <p className="font-semibold text-white">Parabéns! Curso Concluído 🎓</p>
                            <p className="text-sm text-amber-300/80">Você tem direito ao certificado de conclusão.</p>
                          </div>
                        </div>
                        <Button
                          onClick={handleDownloadCertificate}
                          className="bg-amber-500 hover:bg-amber-600 text-black font-semibold flex-shrink-0"
                        >
                          <Download className="w-4 h-4 mr-2" />
                          Baixar Certificado
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </>
        ) : (
          /* Course Overview */
          <div className="flex-1 overflow-auto p-6">
            <div className="max-w-3xl mx-auto space-y-6">
              {currentCourse.thumbnail_url && (
                <img 
                  src={currentCourse.thumbnail_url}
                  alt={currentCourse.title}
                  className="w-full aspect-video object-cover rounded-lg"
                />
              )}

              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline" className={getLevelColor(currentCourse.level)}>
                  {getLevelLabel(currentCourse.level)}
                </Badge>
                <Badge variant="outline" className="border-slate-700">
                  {currentCourse.category}
                </Badge>
                {currentCourse.is_premium && (
                  <Badge className="bg-amber-500">
                    <Crown className="w-3 h-3 mr-1" />
                    Premium
                  </Badge>
                )}
              </div>

              <h1 className="text-3xl font-bold text-white">{currentCourse.title}</h1>
              <p className="text-lg text-slate-400">{currentCourse.description}</p>

              <div className="flex items-center gap-6 text-slate-400">
                <span className="flex items-center gap-1">
                  <BookOpen className="w-5 h-5" />
                  {currentCourse.lesson_count} aulas
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-5 h-5" />
                  {formatDuration(currentCourse.estimated_duration)}
                </span>
                <span className="flex items-center gap-1">
                  <Users className="w-5 h-5" />
                  {currentCourse.enrolled_count} alunos
                </span>
                {currentCourse.rating > 0 && (
                  <span className="flex items-center gap-1">
                    <Star className="w-5 h-5 text-amber-500" />
                    {currentCourse.rating.toFixed(1)}
                  </span>
                )}
              </div>

              {!currentCourse.is_enrolled ? (
                <Button
                  size="lg"
                  onClick={handleEnroll}
                  disabled={enrolling}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {enrolling ? (
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  ) : (
                    <PlayCircle className="w-5 h-5 mr-2" />
                  )}
                  Começar Curso Grátis
                </Button>
              ) : (
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button
                    size="lg"
                    onClick={() => lessons.length > 0 && handleSelectLesson(lessons[0])}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    <Play className="w-5 h-5 mr-2" />
                    Continuar de Onde Parou
                  </Button>
                  {currentCourse.enrollment && currentCourse.enrollment.progress_percent >= 100 && (
                    <Button
                      size="lg"
                      onClick={handleDownloadCertificate}
                      className="bg-amber-500 hover:bg-amber-600 text-black font-semibold"
                    >
                      <Award className="w-5 h-5 mr-2" />
                      Baixar Certificado
                    </Button>
                  )}
                </div>
              )}

              {/* Course Content */}
              <Card className="bg-slate-900 border-slate-800">
                <CardHeader>
                  <CardTitle className="text-white">Conteúdo do Curso</CardTitle>
                  <CardDescription>
                    {currentCourse.lesson_count} aulas • {formatDuration(currentCourse.estimated_duration)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {lessons.map((lesson, idx) => {
                    const completed = isLessonCompleted(lesson.id);
                    const locked = !currentCourse.is_enrolled && !lesson.is_preview;

                    return (
                      <button
                        key={lesson.id}
                        onClick={() => handleSelectLesson(lesson)}
                        disabled={locked}
                        className={`w-full p-4 rounded-lg text-left flex items-center gap-4 transition-colors ${
                          locked 
                            ? 'opacity-50 cursor-not-allowed bg-slate-800/50' 
                            : 'hover:bg-slate-800 bg-slate-800/30'
                        }`}
                      >
                        <span className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-sm text-white">
                          {completed ? (
                            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                          ) : locked ? (
                            <Lock className="w-4 h-4" />
                          ) : (
                            idx + 1
                          )}
                        </span>
                        
                        <div className="flex-1">
                          <p className="text-white font-medium">{lesson.title}</p>
                          {lesson.description && (
                            <p className="text-sm text-slate-400 line-clamp-1">
                              {lesson.description}
                            </p>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          {lesson.is_preview && !currentCourse.is_enrolled && (
                            <Badge variant="outline" className="border-blue-500/30 text-blue-400">
                              Preview
                            </Badge>
                          )}
                          {lesson.video_duration && (
                            <span className="text-sm text-slate-500">
                              {formatTime(lesson.video_duration)}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
