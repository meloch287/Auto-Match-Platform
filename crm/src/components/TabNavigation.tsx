import { BarChart3, FileText, Users, Star, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type TabType = "statistics" | "moderation" | "users" | "subscriptions" | "limits";

interface TabNavigationProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const tabs = [
  { id: "statistics" as TabType, label: "Статистика", icon: BarChart3 },
  { id: "moderation" as TabType, label: "Модерация", icon: FileText },
  { id: "users" as TabType, label: "Пользователи", icon: Users },
  { id: "subscriptions" as TabType, label: "Подписки", icon: Star },
  { id: "limits" as TabType, label: "Ограничения", icon: Settings2 },
];

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <nav className="bg-card border-b border-border sticky top-0 z-10">
      <div className="container mx-auto px-4">
        <div className="flex gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={cn(
                  "relative flex items-center gap-2 px-5 py-4 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className={cn("w-4 h-4 transition-transform", isActive && "scale-110")} />
                {tab.label}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary to-accent rounded-full" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
