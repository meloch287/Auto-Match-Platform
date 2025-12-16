import { useState } from "react";
import { Header } from "@/components/Header";
import { TabNavigation, TabType } from "@/components/TabNavigation";
import { StatisticsTab } from "@/components/StatisticsTab";
import { ModerationTab } from "@/components/ModerationTab";
import { UsersTab } from "@/components/UsersTab";
import { SubscriptionsTab } from "@/components/SubscriptionsTab";
import { LimitsTab } from "@/components/LimitsTab";
import { RecommendedTab } from "@/components/RecommendedTab";
import { useToast } from "@/hooks/use-toast";

const Index = () => {
  const [activeTab, setActiveTab] = useState<TabType>("statistics");
  const { toast } = useToast();

  const handleLogout = () => {
    toast({
      title: "Выход из системы",
      description: "Вы успешно вышли из админ-панели",
    });
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "statistics":
        return <StatisticsTab />;
      case "moderation":
        return <ModerationTab />;
      case "users":
        return <UsersTab />;
      case "subscriptions":
        return <SubscriptionsTab />;
      case "limits":
        return <LimitsTab />;
      case "recommended":
        return <RecommendedTab />;
      default:
        return <StatisticsTab />;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header onLogout={handleLogout} />
      <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="container mx-auto">
        {renderTabContent()}
      </main>
    </div>
  );
};

export default Index;
