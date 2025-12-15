import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: LucideIcon;
  variant: "users" | "new" | "ads" | "moderation" | "requests" | "matches" | "chats" | "contacts";
  trend?: { value: number; isPositive: boolean };
}

const variantColors = {
  users: "text-primary",
  new: "text-success",
  ads: "text-accent",
  moderation: "text-warning",
  requests: "text-[hsl(340,82%,52%)]",
  matches: "text-info",
  chats: "text-[hsl(25,95%,53%)]",
  contacts: "text-[hsl(172,66%,50%)]",
};

const iconBgColors = {
  users: "bg-primary/10",
  new: "bg-success/10",
  ads: "bg-accent/10",
  moderation: "bg-warning/10",
  requests: "bg-[hsl(340,82%,52%)]/10",
  matches: "bg-info/10",
  chats: "bg-[hsl(25,95%,53%)]/10",
  contacts: "bg-[hsl(172,66%,50%)]/10",
};

export function StatCard({ title, value, subtitle, icon: Icon, variant, trend }: StatCardProps) {
  return (
    <div className={cn("stat-card", `stat-card-${variant}`, "animate-fade-in")}>
      <div className="flex items-start justify-between mb-3">
        <div className={cn("p-2.5 rounded-lg", iconBgColors[variant])}>
          <Icon className={cn("w-5 h-5", variantColors[variant])} />
        </div>
        {trend && (
          <span className={cn(
            "text-xs font-semibold px-2 py-1 rounded-full",
            trend.isPositive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
          )}>
            {trend.isPositive ? "+" : ""}{trend.value}%
          </span>
        )}
      </div>
      <p className={cn("text-3xl font-bold mb-1", variantColors[variant])}>{value}</p>
      <h3 className="text-sm font-medium text-foreground mb-1">{title}</h3>
      {subtitle && (
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
}
