import { BarChart3, FileText, Users, Star, Settings2, ThumbsUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export type TabType = "statistics" | "moderation" | "users" | "subscriptions" | "limits" | "recommended";

interface TabNavigationProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const tabConfig = [
  { id: "statistics" as TabType, labelKey: "tabs.statistics", icon: BarChart3 },
  { id: "moderation" as TabType, labelKey: "tabs.moderation", icon: FileText },
  { id: "users" as TabType, labelKey: "tabs.users", icon: Users },
  { id: "subscriptions" as TabType, labelKey: "tabs.subscriptions", icon: Star },
  { id: "limits" as TabType, labelKey: "tabs.limits", icon: Settings2 },
  { id: "recommended" as TabType, labelKey: "tabs.recommended", icon: ThumbsUp },
];

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const { t } = useI18n();
  
  return (
    <nav className="bg-card border-b border-border sticky top-0 z-10">
      <div className="container mx-auto px-4">
        <div className="flex gap-1">
          {tabConfig.map((tab) => {
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
                {t(tab.labelKey)}
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
