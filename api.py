import React, { useState, useEffect } from "react";
import { 
  Lightbulb, Presentation, BrainCircuit, Calendar as CalendarIcon, 
  ChevronLeft, ChevronRight, TrendingUp, Newspaper, Target, Users, 
  X, Plus, Clock, Layout, Briefcase, ArrowDown, AlertCircle, Trash2, 
  Check, GripVertical, Instagram, BarChart3, Heart, MessageCircle,
  FileSpreadsheet, Sparkles, RefreshCcw, Zap, Settings, CheckCircle2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

// --- MOCK DADOS ---
const CLIENT_DATA = {
  "Varejo S.A.": {
    clipping: "Vendas online crescem 15% na região Sul. Consumidor busca frete grátis.",
    behavior: "Aumento na busca por parcelamento em 12x sem juros.",
    socialMetrics: { instagram: { followers: "125K", engagement: "4.2%", reach: "+12%" }, tiktok: { followers: "45K", engagement: "8.5%", reach: "+35%" } },
    competitorPosts: [
        { brand: "Concorrente A", content: "Promoção Relâmpago 24h", likes: "1.2K", comments: "340", platform: "instagram" },
        { brand: "Concorrente B", content: "Trend do escritório (Humor)", likes: "45K", comments: "2K", platform: "tiktok" },
        { brand: "Concorrente A", content: "Lançamento Coleção Cápsula", likes: "890", comments: "120", platform: "instagram" },
        { brand: "Concorrente C", content: "Bastidores da Fábrica", likes: "5K", comments: "45", platform: "tiktok" },
        { brand: "Concorrente B", content: "Depoimento de Cliente Real", likes: "2.1K", comments: "89", platform: "instagram" }
    ],
    trends: [ { topic: "Semana do Consumidor", growth: "+45%", sentiment: "positive" }, { topic: "Live Commerce", growth: "+12%", sentiment: "neutral" } ]
  },
  "Moda Fashion": {
    clipping: "Tons terrosos e sustentabilidade dominam a estação.",
    behavior: "Ticket médio de R$ 450,00 em lojas físicas.",
    socialMetrics: { instagram: { followers: "850K", engagement: "2.1%", reach: "-5%" }, tiktok: { followers: "200K", engagement: "5.5%", reach: "+10%" } },
    competitorPosts: [
        { brand: "Zara Inspired", content: "Look do Dia: Linho", likes: "12K", comments: "400", platform: "instagram" },
        { brand: "Shein Local", content: "Unboxing Gigante", likes: "100K", comments: "5K", platform: "tiktok" },
        { brand: "Amaro Like", content: "Guia de Estilo: Verão", likes: "3K", comments: "120", platform: "instagram" },
        { brand: "Renner Rival", content: "Provador com Influencer", likes: "45K", comments: "890", platform: "tiktok" },
        { brand: "C&A Rival", content: "Saldão Progressivo", likes: "8K", comments: "200", platform: "instagram" }
    ],
    trends: [ { topic: "Slow Fashion", growth: "+80%", sentiment: "positive" }, { topic: "Upcycling", growth: "+25%", sentiment: "positive" } ]
  }
};

const ANNUAL_PLAN_MOCK = {
    "Varejo S.A.": { pillars: ["Oferta", "Humor Corporativo", "Bastidores", "Prova Social", "Institucional"], formats: ["Reels", "Estático", "Stories"] },
    "Moda Fashion": { pillars: ["Estilo", "Sustentabilidade", "Tutorial", "Lifestyle", "Produto"], formats: ["Reels", "Carrossel", "TikTok"] }
};

const MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const INITIAL_TASKS = [
  { id: 1, title: "Analisar Concorrência", client: "Varejo S.A.", deadline: "Hoje", status: "todo", priority: "high" },
  { id: 2, title: "Definir KPI Campanha Mães", client: "Moda Fashion", deadline: "Amanhã", status: "doing", priority: "normal" },
  { id: 3, title: "Fechamento Relatório Mensal", client: "Varejo S.A.", deadline: "Ontem", status: "done", priority: "normal" },
];

export default function Planning() {
  const [selectedYear, setSelectedYear] = useState(2026);
  const [selectedClient, setSelectedClient] = useState("Varejo S.A.");
  
  // --- ESTADOS INTERATIVOS ---
  const [tasks, setTasks] = useState(INITIAL_TASKS);
  const [events, setEvents] = useState<any[]>([
    { id: 1, day: 12, month: 'Junho', title: "Dia dos Namorados", client: "Todos" },
    { id: 2, day: 15, month: 'Março', title: "Dia do Consumidor", client: "Varejo S.A." },
  ]);

  // Content Calendar State
  const [contentMonthIndex, setContentMonthIndex] = useState(0); 
  const [contentGrid, setContentGrid] = useState<any[]>([]);
  // Armazena quais células já foram disparadas: "rowIndex-colKey" (ex: "0-w1")
  const [dispatchedCells, setDispatchedCells] = useState<Set<string>>(new Set());

  // Modais
  const [showEventModal, setShowEventModal] = useState(false);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showPresentationBuilder, setShowPresentationBuilder] = useState(false);

  // Inputs
  const [newEventData, setNewEventData] = useState({ day: 1, month: 'Janeiro', title: "" });
  const [newTaskData, setNewTaskData] = useState({ title: "", status: "todo", priority: "normal" });

  // Chat
  const [strategyInput, setStrategyInput] = useState("");
  const [strategyHistory, setStrategyHistory] = useState<{role: 'ai' | 'user', content: string}[]>([
    { role: 'ai', content: `Olá. Estou monitorando os dados de ${selectedClient}. O tema 'Frete Grátis' é sensível agora. Quer ajuda com ações táticas?` }
  ]);
  
  // Presentation
  const [presentationTopic, setPresentationTopic] = useState("");
  const [presentationSkeleton, setPresentationSkeleton] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  // Drag State
  const [draggedTaskId, setDraggedTaskId] = useState<number | null>(null);

  const currentData = CLIENT_DATA[selectedClient as keyof typeof CLIENT_DATA] || CLIENT_DATA["Varejo S.A."];

  // --- EFEITO: GERADOR AUTOMÁTICO DE CONTEÚDO (AGENTE) ---
  useEffect(() => {
      generateContentSuggestions();
      setDispatchedCells(new Set()); // Limpa disparos ao mudar de mês/cliente
  }, [selectedClient, contentMonthIndex]);

  const generateContentSuggestions = () => {
      // @ts-ignore
      const plan = ANNUAL_PLAN_MOCK[selectedClient] || ANNUAL_PLAN_MOCK["Varejo S.A."];
      const pillars = plan.pillars;
      const getRandom = (arr: any[]) => arr[Math.floor(Math.random() * arr.length)];
      
      const newGrid = [
          { platform: "Instagram (Feed)", pillar: getRandom(pillars), w1: "Foto Still: Produto Hero", w2: "Carrossel: 5 Dicas", w3: "Meme: Expectativa x Realidade", w4: "Frase Motivacional" },
          { platform: "Instagram (Stories)", pillar: "Bastidores", w1: "Enquete: Qual preferem?", w2: "Dia a Dia na Loja", w3: "Repost Clientes", w4: "Box de Perguntas" },
          { platform: "TikTok / Reels", pillar: getRandom(pillars), w1: "Trend Viral: Dancinha", w2: "Desafio da Semana", w3: "Humor Corporativo", w4: "Tutorial Rápido (15s)" },
          { platform: "LinkedIn / Blog", pillar: "Institucional", w1: "Artigo: Tendências 2026", w2: "-", w3: "Case de Sucesso", w4: "-" }
      ];
      setContentGrid(newGrid);
  };

  const updateContentCell = (rowIndex: number, field: string, value: string) => {
      const newGrid = [...contentGrid];
      newGrid[rowIndex][field] = value;
      setContentGrid(newGrid);
  };

  // --- ONE-CLICK DISPATCH LOGIC (MÁGICA) ---
  const handleOneClickDispatch = (rowIndex: number, weekKey: string, content: string, platform: string) => {
      if (!content || content === "-" || dispatchedCells.has(`${rowIndex}-${weekKey}`)) return;

      const cellId = `${rowIndex}-${weekKey}`;
      
      // Inteligência de Roteamento: Decide para onde vai o Job
      let destination = "Redação (Agente C1)"; // Default
      let icon = "📝";
      
      const textLower = content.toLowerCase() + platform.toLowerCase();
      
      if (textLower.includes("foto") || textLower.includes("estático") || textLower.includes("banner") || textLower.includes("carrossel")) {
          destination = "Direção de Arte (Agente C4)";
          icon = "🎨";
      } else if (textLower.includes("vídeo") || textLower.includes("reels") || textLower.includes("tiktok") || textLower.includes("tutorial")) {
          destination = "Roteiro (Agente C3) + DA";
          icon = "🎬";
      }

      // Atualiza visualmente
      setDispatchedCells(prev => new Set(prev).add(cellId));

      // Simula envio para API
      toast.promise(
          new Promise((resolve) => setTimeout(resolve, 1000)),
          {
              loading: 'Criando Job e Briefing automático...',
              success: `${icon} Job criado em ${destination}: "${content}"`,
              error: 'Erro ao criar job'
          }
      );
  };

  // --- HANDLERS PADRÃO ---
  const handleDragStart = (e: React.DragEvent, taskId: number) => { setDraggedTaskId(taskId); e.dataTransfer.effectAllowed = "move"; e.currentTarget.classList.add("opacity-50"); };
  const handleDragEnd = (e: React.DragEvent) => { e.currentTarget.classList.remove("opacity-50"); setDraggedTaskId(null); };
  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; };
  const handleDrop = (e: React.DragEvent, newStatus: string) => { e.preventDefault(); if (draggedTaskId === null) return; setTasks((prev) => prev.map((t) => (t.id === draggedTaskId ? { ...t, status: newStatus } : t))); toast.success("Status atualizado!"); };

  const handleAddTaskClick = (status = "todo") => { setNewTaskData({ ...newTaskData, status }); setShowTaskModal(true); };
  const handleSaveTask = () => { if (!newTaskData.title) return; setTasks([...tasks, { id: Date.now(), title: newTaskData.title, client: selectedClient, deadline: "Hoje", status: newTaskData.status, priority: newTaskData.priority }]); setShowTaskModal(false); setNewTaskData({ title: "", status: "todo", priority: "normal" }); toast.success("Tarefa adicionada!"); };
  const handleDeleteTask = (id: number) => { setTasks(tasks.filter(t => t.id !== id)); toast.success("Tarefa removida."); };

  const handleDayClick = (day: number, month: string) => { setNewEventData({ ...newEventData, day, month }); setShowEventModal(true); };
  const handleSaveEvent = () => { if (!newEventData.title) return; setEvents([...events, { id: Date.now(), ...newEventData, client: selectedClient }]); setShowEventModal(false); toast.success("Evento criado!"); };
  const handleDeleteEvent = (id: number) => { setEvents(events.filter(e => e.id !== id)); toast.success("Evento removido."); };

  const handleStrategySubmit = () => { if(!strategyInput.trim()) return; const newHist = [...strategyHistory, { role: 'user' as const, content: strategyInput }]; setStrategyHistory(newHist); setStrategyInput(""); setTimeout(() => { setStrategyHistory([...newHist, { role: 'ai' as const, content: `Para ${selectedClient}, sugiro uma campanha tática focada em urgência. Agendei um lembrete no seu Kanban.` }]); }, 1000); };
  const handleGenerateSkeleton = () => { if (!presentationTopic) return; setIsGenerating(true); setTimeout(() => { setPresentationSkeleton(`# ROTEIRO: ${presentationTopic}\n\nCLIENTE: ${selectedClient}\n\n1. CENÁRIO: ${currentData.clipping}\n2. DESAFIO: Aumentar share.\n3. INSIGHT: Baseado em ${currentData.behavior}...`); setIsGenerating(false); }, 1500); };

  const nextContentMonth = () => setContentMonthIndex((prev) => (prev + 1) % 12);
  const prevContentMonth = () => setContentMonthIndex((prev) => (prev - 1 + 12) % 12);

  return (
    <div className="min-h-screen bg-black text-white font-sans flex flex-col h-screen overflow-hidden">
      
      <header className="h-16 border-b border-zinc-800 flex items-center justify-between px-6 bg-black shrink-0 z-20">
        <div className="flex items-center gap-6">
          <h1 className="text-xl font-bold flex items-center gap-2"><BrainCircuit className="w-6 h-6 text-purple-500" /> Planejamento</h1>
          <div className="flex items-center gap-2 bg-zinc-900 px-3 py-1.5 rounded-lg border border-zinc-700">
            <Users className="w-4 h-4 text-gray-400" />
            <select value={selectedClient} onChange={(e) => { setSelectedClient(e.target.value); setStrategyHistory([{ role: 'ai', content: `Contexto alterado para ${e.target.value}.` }]); }} className="bg-transparent text-sm font-bold text-white focus:outline-none cursor-pointer">
              <option value="Varejo S.A.">Varejo S.A.</option>
              <option value="Moda Fashion">Moda Fashion</option>
            </select>
          </div>
        </div>
        <div className="text-xs text-zinc-500 flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span> IA Ativa</div>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-thin scrollbar-thumb-zinc-800">
        
        {/* KANBAN */}
        <section>
           <div className="flex justify-between items-end mb-4"><h3 className="font-bold text-lg flex items-center gap-2 text-white"><Briefcase className="w-5 h-5 text-yellow-500"/> Pauta do Dia</h3><div className="flex gap-2"><Button size="sm" className="bg-yellow-600 hover:bg-yellow-500 h-8 text-xs gap-2" onClick={() => handleAddTaskClick('todo')}><Plus className="w-3 h-3" /> Nova Tarefa</Button></div></div>
           <div className="grid grid-cols-3 gap-6">
              {['todo', 'doing', 'done'].map(status => (
                 <div key={status} className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 min-h-[150px]" onDragOver={handleDragOver} onDrop={(e) => handleDrop(e, status)}>
                    <h4 className="uppercase text-xs font-bold text-gray-500 mb-3 flex justify-between items-center">{status === 'todo' ? 'A Fazer' : status === 'doing' ? 'Em Andamento' : 'Concluído'} <span className="bg-zinc-800 px-2 py-0.5 rounded text-white text-[10px]">{tasks.filter(t => t.status === status).length}</span></h4>
                    <div className="space-y-2">{tasks.filter(t => t.status === status).map(task => (<div key={task.id} draggable onDragStart={(e) => handleDragStart(e, task.id)} onDragEnd={handleDragEnd} className="bg-black border border-zinc-800 p-3 rounded-lg hover:border-yellow-500/50 cursor-grab active:cursor-grabbing group"><div className="flex justify-between mb-1"><span className="text-[10px] bg-zinc-900 px-1.5 py-0.5 rounded text-gray-300">{task.client}</span>{task.priority === 'high' && <AlertCircle className="w-3 h-3 text-red-500" />}</div><p className="text-xs font-medium text-gray-200">{task.title}</p></div>))}</div>
                 </div>
              ))}
           </div>
        </section>

        {/* DIVISOR */}
        <div className="flex items-center gap-4 py-2"><div className="h-px bg-zinc-800 flex-1"></div><span className="text-xs font-bold text-zinc-600 uppercase tracking-widest">Inteligência & Conteúdo</span><div className="h-px bg-zinc-800 flex-1"></div></div>

        {/* RAIO-X DIGITAL */}
        <section className="grid grid-cols-12 gap-6">
            <div className="col-span-4 bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 flex flex-col">
                <h3 className="text-xs font-bold text-gray-400 uppercase flex gap-2 mb-4 items-center"><BarChart3 className="w-4 h-4 text-blue-500" /> Performance Social</h3>
                <div className="flex-1 space-y-4">
                    <div className="bg-gradient-to-r from-pink-900/20 to-purple-900/20 border border-pink-500/20 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2"><Instagram className="w-4 h-4 text-pink-500" /><span className="text-sm font-bold text-pink-100">Instagram</span></div>
                        <div className="grid grid-cols-3 gap-2 text-center"><div><p className="text-xs text-zinc-400">Seguidores</p><p className="text-sm font-bold text-white">{currentData.socialMetrics.instagram.followers}</p></div><div><p className="text-xs text-zinc-400">Engajamento</p><p className="text-sm font-bold text-white">{currentData.socialMetrics.instagram.engagement}</p></div><div><p className="text-xs text-zinc-400">Alcance</p><p className={`text-sm font-bold ${currentData.socialMetrics.instagram.reach.includes('+') ? 'text-green-400' : 'text-red-400'}`}>{currentData.socialMetrics.instagram.reach}</p></div></div>
                    </div>
                    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2"><span className="text-sm font-bold text-white">TikTok</span></div>
                        <div className="grid grid-cols-3 gap-2 text-center"><div><p className="text-xs text-zinc-400">Seguidores</p><p className="text-sm font-bold text-white">{currentData.socialMetrics.tiktok.followers}</p></div><div><p className="text-xs text-zinc-400">Engajamento</p><p className="text-sm font-bold text-white">{currentData.socialMetrics.tiktok.engagement}</p></div><div><p className="text-xs text-zinc-400">Alcance</p><p className={`text-sm font-bold ${currentData.socialMetrics.tiktok.reach.includes('+') ? 'text-green-400' : 'text-red-400'}`}>{currentData.socialMetrics.tiktok.reach}</p></div></div>
                    </div>
                </div>
            </div>
            <div className="col-span-8 bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 overflow-hidden">
                <h3 className="text-xs font-bold text-gray-400 uppercase flex gap-2 mb-4 items-center"><Target className="w-4 h-4 text-red-500" /> Radar da Concorrência</h3>
                <div className="grid grid-cols-5 gap-3">
                    {currentData.competitorPosts.map((post, idx) => (
                        <div key={idx} className="bg-black border border-zinc-800 rounded-lg p-3 hover:border-zinc-600 transition group cursor-pointer relative overflow-hidden"><div className={`absolute top-0 left-0 w-1 h-full ${post.platform === 'instagram' ? 'bg-pink-600' : 'bg-black border-r border-zinc-700'}`}></div><p className="text-[10px] text-zinc-500 uppercase font-bold mb-1 pl-2">{post.brand}</p><p className="text-xs text-gray-300 font-medium mb-3 pl-2 line-clamp-2 leading-snug">"{post.content}"</p><div className="flex items-center gap-3 pl-2 pt-2 border-t border-zinc-900"><span className="flex items-center gap-1 text-[10px] text-zinc-400"><Heart className="w-3 h-3" /> {post.likes}</span><span className="flex items-center gap-1 text-[10px] text-zinc-400"><MessageCircle className="w-3 h-3" /> {post.comments}</span></div></div>
                    ))}
                </div>
            </div>
        </section>

        {/* CLIPPING & CHAT */}
        <section className="grid grid-cols-12 gap-6 h-[400px]">
          <div className="col-span-4 flex flex-col gap-4">
             <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-2xl flex-1"><h3 className="text-xs font-bold text-gray-400 uppercase flex gap-2 mb-4"><Newspaper className="w-4 h-4 text-blue-500" /> Clipping</h3><p className="text-sm font-medium text-white leading-relaxed">"{currentData.clipping}"</p><div className="mt-4 pt-4 border-t border-zinc-800"><h4 className="text-xs font-bold text-gray-500 mb-2 flex items-center gap-2"><Target className="w-3 h-3" /> Comportamento</h4><p className="text-xs text-zinc-300">{currentData.behavior}</p></div></div>
             <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-2xl h-1/3 overflow-y-auto"><h3 className="text-xs font-bold text-gray-400 uppercase flex gap-2 mb-2"><TrendingUp className="w-4 h-4 text-green-500" /> Trends</h3><div className="space-y-1">{currentData.trends.map((t, i) => (<div key={i} className="flex justify-between text-xs border-b border-zinc-800 pb-1 last:border-0"><span className="text-gray-300">{t.topic}</span><span className="text-green-500 font-bold">{t.growth}</span></div>))}</div></div>
          </div>
          <div className="col-span-8 bg-zinc-900/30 border border-zinc-800 rounded-2xl flex flex-col relative">
            <div className="p-4 border-b border-zinc-800 bg-zinc-900/50 flex justify-between items-center"><h3 className="text-sm font-bold text-purple-400 flex items-center gap-2"><Lightbulb className="w-4 h-4" /> Copiloto Estratégico</h3><Button size="sm" className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-bold text-xs gap-2 shadow-lg shadow-purple-900/20" onClick={() => setShowPresentationBuilder(true)}><Sparkles className="w-3 h-3" /> Gerar Apresentação</Button></div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-black/20">{strategyHistory.map((msg, idx) => (<div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[80%] p-3 rounded-2xl text-xs leading-relaxed shadow-md ${msg.role === 'user' ? 'bg-zinc-800 text-white rounded-br-none' : 'bg-purple-900/20 text-purple-100 border border-purple-500/20 rounded-bl-none'}`}>{msg.content}</div></div>))}</div>
            <div className="p-3 bg-black border-t border-zinc-800"><div className="relative"><input className="w-full bg-zinc-900 border border-zinc-700 rounded-xl pl-4 pr-10 py-3 text-sm focus:border-purple-500 focus:outline-none text-white" placeholder="Pergunte à IA..." value={strategyInput} onChange={(e) => setStrategyInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleStrategySubmit()} /><button onClick={handleStrategySubmit} className="absolute right-2 top-2 p-1.5 bg-purple-600 rounded-lg hover:bg-purple-500 text-white"><ArrowDown className="w-3 h-3 -rotate-90" /></button></div></div>
          </div>
        </section>

        {/* CALENDÁRIO GERAL */}
        <section className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-6">
           <div className="flex justify-between items-center mb-6"><h3 className="font-bold text-lg flex items-center gap-2 text-white"><CalendarIcon className="w-5 h-5 text-blue-500"/> Calendário {selectedYear}</h3><div className="flex gap-2"><button onClick={() => setSelectedYear(selectedYear-1)}><ChevronLeft className="w-5 h-5 text-zinc-500 hover:text-white"/></button><button onClick={() => setSelectedYear(selectedYear+1)}><ChevronRight className="w-5 h-5 text-zinc-500 hover:text-white"/></button></div></div>
           <div className="grid grid-cols-6 gap-4">{MONTHS.map((month) => { const monthEvents = events.filter(e => e.month === month); return ( <div key={month} className="bg-black border border-zinc-800 rounded-xl p-3 min-h-[100px] hover:border-zinc-600 transition group relative flex flex-col"><div className="flex justify-between items-center mb-2 border-b border-zinc-900 pb-1"><span className="text-sm font-bold text-zinc-400">{month}</span><button onClick={() => handleDayClick(1, month)} className="text-zinc-600 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition p-1"><Plus className="w-3 h-3" /></button></div><div className="space-y-1 flex-1 overflow-y-auto custom-scrollbar">{monthEvents.map(ev => (<div key={ev.id} className="text-[9px] bg-blue-900/20 border border-blue-500/30 text-blue-300 px-1.5 py-1 rounded truncate cursor-pointer hover:bg-red-900/30 hover:border-red-500/30 hover:text-red-300 transition flex justify-between items-center group/event" onClick={() => handleDeleteEvent(ev.id)}><span><strong>{ev.day}:</strong> {ev.title}</span><X className="w-2 h-2 opacity-0 group-hover/event:opacity-100" /></div>))}{monthEvents.length === 0 && (<div className="flex-1 flex items-center justify-center"><span className="text-[10px] text-zinc-800 italic">.</span></div>)}</div></div> ) })}</div>
        </section>

        {/* === SEÇÃO 4: CALENDÁRIO TÁTICO COM ONE-CLICK DISPATCH === */}
        <section className="bg-black border border-zinc-800 rounded-2xl p-6 mb-10 overflow-hidden shadow-2xl">
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-3">
                    <div className="bg-purple-900/30 p-2 rounded-lg"><FileSpreadsheet className="w-5 h-5 text-purple-500" /></div>
                    <div>
                        <h3 className="font-bold text-lg text-white">Calendário de Conteúdo Tático</h3>
                        <p className="text-xs text-zinc-500">Baseado no Planejamento Anual de {selectedClient}</p>
                    </div>
                </div>
                <div className="flex items-center gap-4 bg-zinc-900 px-4 py-2 rounded-full border border-zinc-700">
                    <button onClick={prevContentMonth} className="text-zinc-400 hover:text-white"><ChevronLeft className="w-4 h-4" /></button>
                    <span className="text-sm font-bold text-white w-24 text-center">{MONTHS[contentMonthIndex]}</span>
                    <button onClick={nextContentMonth} className="text-zinc-400 hover:text-white"><ChevronRight className="w-4 h-4" /></button>
                </div>
                <Button variant="outline" className="border-zinc-700 text-xs gap-2" onClick={generateContentSuggestions}><RefreshCcw className="w-3 h-3" /> Regenerar Sugestões</Button>
            </div>

            <div className="overflow-x-auto pb-4">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr>
                            <th className="p-4 border-b border-zinc-800 text-xs font-bold text-zinc-500 uppercase w-48 bg-zinc-900/50">Plataforma</th>
                            <th className="p-4 border-b border-zinc-800 text-xs font-bold text-zinc-500 uppercase w-32 bg-zinc-900/30">Pilar</th>
                            <th className="p-4 border-b border-zinc-800 text-xs font-bold text-zinc-500 uppercase bg-zinc-900/20">Semana 1</th>
                            <th className="p-4 border-b border-zinc-800 text-xs font-bold text-zinc-500 uppercase bg-zinc-900/20">Semana 2</th>
                            <th className="p-4 border-b border-zinc-800 text-xs font-bold text-zinc-500 uppercase bg-zinc-900/20">Semana 3</th>
                            <th className="p-4 border-b border-zinc-800 text-xs font-bold text-zinc-500 uppercase bg-zinc-900/20">Semana 4</th>
                        </tr>
                    </thead>
                    <tbody>
                        {contentGrid.map((row, idx) => (
                            <tr key={idx} className="group hover:bg-zinc-900/30 transition">
                                <td className="p-4 border-b border-zinc-800 text-sm font-bold text-purple-300 bg-zinc-950">{row.platform}</td>
                                
                                <td className="p-2 border-b border-zinc-800 border-l border-zinc-800/50 relative">
                                    <input className="w-full bg-zinc-900/50 text-xs text-blue-300 font-bold p-2 rounded hover:bg-zinc-800 focus:bg-black focus:border-blue-500 focus:outline-none border border-transparent transition text-center" value={row.pillar} onChange={(e) => updateContentCell(idx, 'pillar', e.target.value)} />
                                </td>

                                {['w1', 'w2', 'w3', 'w4'].map((week) => (
                                    <td key={week} className="p-2 border-b border-zinc-800 border-l border-zinc-800/50 relative group/cell">
                                        <input 
                                            className="w-full bg-transparent text-xs text-gray-300 p-2 rounded hover:bg-zinc-800 focus:bg-black focus:border-purple-500 focus:outline-none border border-transparent transition" 
                                            value={row[week]} 
                                            onChange={(e) => updateContentCell(idx, week, e.target.value)} 
                                        />
                                        
                                        {/* BOTÃO ONE-CLICK DISPATCH */}
                                        {row[week] && row[week] !== '-' && !dispatchedCells.has(`${idx}-${week}`) && (
                                            <button 
                                                onClick={() => handleOneClickDispatch(idx, week, row[week], row.platform)}
                                                className="absolute right-2 top-1/2 -translate-y-1/2 bg-purple-600 hover:bg-purple-500 text-white p-1.5 rounded-full shadow-lg opacity-0 group-hover/cell:opacity-100 transition-all scale-90 hover:scale-110 z-10"
                                                title="Criar Job na Criação"
                                            >
                                                <Zap className="w-3 h-3" />
                                            </button>
                                        )}

                                        {/* INDICADOR DE STATUS */}
                                        {dispatchedCells.has(`${idx}-${week}`) && (
                                            <div className="absolute right-2 top-1/2 -translate-y-1/2 text-green-500" title="Em Produção">
                                                <Settings className="w-3 h-3 animate-spin-slow" />
                                            </div>
                                        )}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
        
        <div className="h-10"></div>
      </div>

      {/* MODAIS (MANTIDOS) */}
      {showEventModal && (<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"><div className="bg-zinc-900 border border-zinc-700 p-6 rounded-xl w-80 shadow-2xl"><h3 className="text-md font-bold mb-4 flex items-center gap-2 text-white"><Plus className="w-4 h-4 text-blue-500" /> Novo Evento</h3><div className="space-y-3"><div><label className="text-xs text-gray-400 mb-1 block">Dia</label><input type="number" className="w-full bg-black border border-zinc-600 rounded p-2 text-white text-sm focus:border-blue-500 focus:outline-none" value={newEventData.day} onChange={(e) => setNewEventData({...newEventData, day: parseInt(e.target.value)})}/></div><div><label className="text-xs text-gray-400 mb-1 block">Título</label><input autoFocus className="w-full bg-black border border-zinc-600 rounded p-2 text-white text-sm focus:border-blue-500 focus:outline-none" value={newEventData.title} onChange={(e) => setNewEventData({...newEventData, title: e.target.value})}/></div></div><div className="flex justify-end gap-2 mt-6"><Button variant="ghost" size="sm" onClick={() => setShowEventModal(false)}>Cancelar</Button><Button size="sm" onClick={handleSaveEvent} className="bg-blue-600 hover:bg-blue-500">Salvar</Button></div></div></div>)}
      {showTaskModal && (<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"><div className="bg-zinc-900 border border-zinc-700 p-6 rounded-xl w-80 shadow-2xl"><h3 className="text-md font-bold mb-4 flex items-center gap-2 text-white"><Plus className="w-4 h-4 text-yellow-500" /> Nova Tarefa</h3><div className="space-y-3"><div><label className="text-xs text-gray-400 mb-1 block">Título</label><input autoFocus className="w-full bg-black border border-zinc-600 rounded p-2 text-white text-sm focus:border-yellow-500 focus:outline-none" value={newTaskData.title} onChange={(e) => setNewTaskData({...newTaskData, title: e.target.value})}/></div></div><div className="flex justify-end gap-2 mt-6"><Button variant="ghost" size="sm" onClick={() => setShowTaskModal(false)}>Cancelar</Button><Button size="sm" onClick={handleSaveTask} className="bg-yellow-600 hover:bg-yellow-500">Adicionar</Button></div></div></div>)}
      {showPresentationBuilder && (<div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex justify-end"><div className="w-[600px] bg-zinc-900 h-full border-l border-zinc-800 shadow-2xl flex flex-col"><div className="p-6 border-b border-zinc-800 flex justify-between items-center bg-black"><h2 className="text-xl font-bold flex items-center gap-2 text-white"><Presentation className="w-5 h-5 text-blue-500" /> Gerador de Roteiro</h2><button onClick={() => setShowPresentationBuilder(false)} className="text-gray-500 hover:text-white"><X className="w-5 h-5" /></button></div><div className="p-6 flex-1 overflow-y-auto space-y-6">{!presentationSkeleton ? (<div className="space-y-4"><p className="text-sm text-gray-400">Cliente: <span className="text-white font-bold">{selectedClient}</span></p><input className="w-full bg-black border border-zinc-700 rounded-xl p-3 text-sm focus:border-blue-500 focus:outline-none text-white" value={presentationTopic} onChange={(e) => setPresentationTopic(e.target.value)} placeholder="Tema da apresentação" /><Button onClick={handleGenerateSkeleton} disabled={isGenerating || !presentationTopic} className="w-full py-4 font-bold bg-blue-600 hover:bg-blue-500">{isGenerating ? <Layout className="animate-spin mr-2" /> : <BrainCircuit className="mr-2" />} Gerar Roteiro</Button></div>) : (<div className="bg-black border border-zinc-800 rounded-xl p-6 font-mono text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">{presentationSkeleton}<div className="flex gap-2 mt-4"><Button variant="ghost" onClick={() => setPresentationSkeleton("")} className="flex-1 text-zinc-500">Novo</Button><Button variant="outline" className="flex-1 border-zinc-700 text-white"><Check className="w-4 h-4 mr-2"/> Copiar</Button></div></div>)}</div></div></div>)}

    </div>
  );
}