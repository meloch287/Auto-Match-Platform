import { useEffect, useState } from "react";
import { Users, UserPlus, FileText, Clock, Send, Target, MessageSquare, Phone, TrendingUp, Activity, Loader2 } from "lucide-react";
import { StatCard } from "./StatCard";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";
import { getStats, getChartData, AdminStats, ChartData } from "@/lib/api";

export function StatisticsTab() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    const [statsResult, chartResult] = await Promise.all([
      getStats(),
      getChartData(),
    ]);
    if (statsResult?.success) {
      setStats(statsResult.data);
    }
    if (chartResult?.success) {
      setChartData(chartResult.data);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        Ошибка загрузки статистики
      </div>
    );
  }

  const statCards = [
    { title: "Пользователи", value: stats.users.total_users, subtitle: `Активных: ${stats.users.active_users} | Заблокировано: ${stats.users.blocked_users}`, icon: Users, variant: "users" as const },
    { title: "Новые сегодня", value: stats.users.new_users_today, subtitle: `За неделю: ${stats.users.new_users_this_week} | За месяц: ${stats.users.new_users_this_month}`, icon: UserPlus, variant: "new" as const },
    { title: "Объявления", value: stats.listings.total_listings, subtitle: `Активных: ${stats.listings.active_listings} | VIP: ${stats.listings.vip_listings}`, icon: FileText, variant: "ads" as const },
    { title: "На модерации", value: stats.listings.pending_moderation, subtitle: `Отклонено: ${stats.listings.rejected_listings}`, icon: Clock, variant: "moderation" as const },
    { title: "Заявки", value: stats.requirements.total_requirements, subtitle: `Активных: ${stats.requirements.active_requirements}`, icon: Send, variant: "requests" as const },
    { title: "Совпадения", value: stats.matches.total_matches, subtitle: `Сегодня: ${stats.matches.matches_today} | Средний скор: ${stats.matches.average_match_score}%`, icon: Target, variant: "matches" as const },
    { title: "Чаты", value: stats.chats.total_chats, subtitle: `Активных: ${stats.chats.active_chats} | Сообщений: ${stats.chats.total_messages}`, icon: MessageSquare, variant: "chats" as const },
    { title: "Контакты раскрыты", value: stats.chats.contact_reveals, subtitle: `Сообщений сегодня: ${stats.chats.messages_today}`, icon: Phone, variant: "contacts" as const },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, index) => (
          <StatCard
            key={index}
            title={stat.title}
            value={stat.value}
            subtitle={stat.subtitle}
            icon={stat.icon}
            variant={stat.variant}
          />
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Activity Chart */}
        <div className="glass-card p-6 animate-fade-in" style={{ animationDelay: '0.2s' }}>
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-primary/10">
              <TrendingUp className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Активность за неделю</h3>
              <p className="text-xs text-muted-foreground">Пользователи и заявки</p>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData?.daily || []}>
                <defs>
                  <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(220, 90%, 56%)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="hsl(220, 90%, 56%)" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(262, 83%, 58%)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="hsl(262, 83%, 58%)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 13%, 91%)" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'hsl(220, 9%, 46%)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: 'hsl(220, 9%, 46%)' }} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'hsl(0, 0%, 100%)', 
                    border: '1px solid hsl(220, 13%, 91%)',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                  }}
                />
                <Area type="monotone" dataKey="users" stroke="hsl(220, 90%, 56%)" strokeWidth={2} fillOpacity={1} fill="url(#colorUsers)" name="Пользователи" />
                <Area type="monotone" dataKey="requests" stroke="hsl(262, 83%, 58%)" strokeWidth={2} fillOpacity={1} fill="url(#colorRequests)" name="Заявки" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Monthly Stats Chart */}
        <div className="glass-card p-6 animate-fade-in" style={{ animationDelay: '0.3s' }}>
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-success/10">
              <Activity className="w-5 h-5 text-success" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Регистрации по неделям</h3>
              <p className="text-xs text-muted-foreground">За последний месяц</p>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData?.weekly || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 13%, 91%)" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'hsl(220, 9%, 46%)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: 'hsl(220, 9%, 46%)' }} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'hsl(0, 0%, 100%)', 
                    border: '1px solid hsl(220, 13%, 91%)',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                  }}
                />
                <Bar dataKey="value" fill="hsl(142, 76%, 36%)" radius={[4, 4, 0, 0]} name="Регистрации" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Quick Stats Summary */}
      <div className="glass-card p-6 animate-fade-in" style={{ animationDelay: '0.4s' }}>
        <h3 className="font-semibold text-foreground mb-4">Сводка за сегодня</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-4 rounded-lg bg-primary/5 border border-primary/10">
            <p className="text-2xl font-bold text-primary">{stats.users.new_users_today}</p>
            <p className="text-xs text-muted-foreground">Новых пользователей</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-success/5 border border-success/10">
            <p className="text-2xl font-bold text-success">
              {stats.users.total_users > 0 ? Math.round((stats.users.active_users / stats.users.total_users) * 100) : 0}%
            </p>
            <p className="text-xs text-muted-foreground">Активных</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-warning/5 border border-warning/10">
            <p className="text-2xl font-bold text-warning">{stats.listings.pending_moderation}</p>
            <p className="text-xs text-muted-foreground">На модерации</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-info/5 border border-info/10">
            <p className="text-2xl font-bold text-info">{stats.matches.average_match_score}%</p>
            <p className="text-xs text-muted-foreground">Средний скор</p>
          </div>
        </div>
      </div>
    </div>
  );
}
