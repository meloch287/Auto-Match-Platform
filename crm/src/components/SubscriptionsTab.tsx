import { useState, useEffect } from "react";
import { Search, Save, RefreshCw, Edit, Crown, Star, User, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { getUsers, updateUserSubscription, resetUserLimits, User as ApiUser } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useI18n } from "@/lib/i18n";

const subscriptionConfig: Record<string, { icon: typeof User; color: string; bg: string; label: string }> = {
  free: { icon: User, color: "text-muted-foreground", bg: "bg-muted", label: "Free" },
  premium: { icon: Star, color: "text-primary", bg: "bg-primary/10", label: "Premium" },
  agency_basic: { icon: Star, color: "text-info", bg: "bg-info/10", label: "Agency Basic" },
  agency_pro: { icon: Crown, color: "text-warning", bg: "bg-warning/10", label: "Agency Pro" },
};

export function SubscriptionsTab() {
  const [searchQuery, setSearchQuery] = useState("");
  const [users, setUsers] = useState<ApiUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<ApiUser | null>(null);
  const [newSubscription, setNewSubscription] = useState("free");
  const [days, setDays] = useState("30");
  const { toast } = useToast();
  const { t } = useI18n();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    const result = await getUsers(1, 50);
    if (result?.success) {
      setUsers(result.data.users);
    }
    setLoading(false);
  };

  const handleSearch = () => {
    const found = users.find(
      (user) =>
        (user.telegram_username?.toLowerCase().includes(searchQuery.toLowerCase())) ||
        user.telegram_id.toString().includes(searchQuery)
    );
    if (found) {
      setSelectedUser(found);
      setNewSubscription(found.subscription_type);
    }
  };

  const handleSaveSubscription = async () => {
    if (!selectedUser) return;
    const result = await updateUserSubscription(selectedUser.id, newSubscription, parseInt(days));
    if (result) {
      toast({ title: t('subs.subscription_updated') });
      loadUsers();
      setSelectedUser(null);
    }
  };

  const handleResetLimits = async () => {
    if (!selectedUser) return;
    const result = await resetUserLimits(selectedUser.id);
    if (result) {
      toast({ title: t('subs.limits_reset') });
      loadUsers();
    }
  };

  const filteredUsers = users.filter(
    (user) =>
      (user.telegram_username?.toLowerCase().includes(searchQuery.toLowerCase())) ||
      user.telegram_id.toString().includes(searchQuery)
  );

  const getConfig = (type: string) => subscriptionConfig[type] || subscriptionConfig.free;

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="glass-card p-6 animate-fade-in">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-foreground">{t('subs.title')}</h2>
            <p className="text-sm text-muted-foreground mt-1">{t('subs.subtitle')}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('users.search_placeholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-72 pl-10"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button variant="default" onClick={handleSearch}>
              {t('common.find')}
            </Button>
            <Button variant="outline" onClick={loadUsers}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('common.refresh')}
            </Button>
          </div>
        </div>

        {selectedUser && (
          <div className="mb-6 p-6 rounded-xl border border-border bg-gradient-to-r from-muted/50 to-transparent animate-fade-in">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className={cn("p-3 rounded-xl", getConfig(selectedUser.subscription_type).bg)}>
                  {(() => {
                    const Icon = getConfig(selectedUser.subscription_type).icon;
                    return <Icon className={cn("w-6 h-6", getConfig(selectedUser.subscription_type).color)} />;
                  })()}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {selectedUser.telegram_username ? `@${selectedUser.telegram_username}` : `ID: ${selectedUser.telegram_id}`}
                  </h3>
                  <p className="text-sm text-muted-foreground">Telegram ID: {selectedUser.telegram_id}</p>
                </div>
              </div>
              <Badge className={cn("px-3 py-1", getConfig(selectedUser.subscription_type).bg, getConfig(selectedUser.subscription_type).color)}>
                {getConfig(selectedUser.subscription_type).label}
              </Badge>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-4 rounded-lg bg-card border border-border">
                <p className="text-xs text-muted-foreground mb-1">{t('subs.expires')}</p>
                <p className="font-semibold">
                  {selectedUser.subscription_expires_at 
                    ? new Date(selectedUser.subscription_expires_at).toLocaleDateString("ru-RU")
                    : "—"}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <p className="text-xs text-muted-foreground mb-1">{t('users.listings')}</p>
                <p className="font-semibold">{selectedUser.listing_count || 0}</p>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <p className="text-xs text-muted-foreground mb-1">{t('users.requests')}</p>
                <p className="font-semibold">{selectedUser.requirement_count || 0}</p>
              </div>
              <div className="p-4 rounded-lg bg-card border border-border">
                <p className="text-xs text-muted-foreground mb-1">{t('subs.status')}</p>
                <p className="font-semibold">{selectedUser.is_blocked ? t('users.blocked') : t('users.active')}</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-border">
              <Select value={newSubscription} onValueChange={setNewSubscription}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">
                    <span className="flex items-center gap-2">
                      <User className="w-4 h-4" /> Free
                    </span>
                  </SelectItem>
                  <SelectItem value="premium">
                    <span className="flex items-center gap-2">
                      <Star className="w-4 h-4 text-primary" /> Premium
                    </span>
                  </SelectItem>
                  <SelectItem value="agency_basic">
                    <span className="flex items-center gap-2">
                      <Star className="w-4 h-4 text-info" /> Agency Basic
                    </span>
                  </SelectItem>
                  <SelectItem value="agency_pro">
                    <span className="flex items-center gap-2">
                      <Crown className="w-4 h-4 text-warning" /> Agency Pro
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
              <Input
                type="number"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                className="w-24"
                placeholder={t('common.days')}
              />
              <Button variant="default" onClick={handleSaveSubscription}>
                <Save className="w-4 h-4 mr-2" />
                {t('common.save')}
              </Button>
              <Button variant="outline" onClick={handleResetLimits}>
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('common.reset')}
              </Button>
            </div>
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-border">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('users.telegram_id')}</th>
                <th>{t('users.username')}</th>
                <th>{t('users.subscription')}</th>
                <th>{t('subs.expires')}</th>
                <th>{t('users.listings')}</th>
                <th>{t('users.requests')}</th>
                <th className="text-center">{t('users.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user, index) => (
                <tr key={user.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.05}s` }}>
                  <td>
                    <code className="text-xs bg-muted px-2 py-1 rounded font-mono">{user.telegram_id}</code>
                  </td>
                  <td>
                    <span className="font-medium text-primary hover:underline cursor-pointer">
                      {user.telegram_username ? `@${user.telegram_username}` : '-'}
                    </span>
                  </td>
                  <td>
                    <div className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium", getConfig(user.subscription_type).bg)}>
                      {(() => {
                        const Icon = getConfig(user.subscription_type).icon;
                        return <Icon className={cn("w-3 h-3", getConfig(user.subscription_type).color)} />;
                      })()}
                      <span className={getConfig(user.subscription_type).color}>
                        {getConfig(user.subscription_type).label}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="text-sm text-muted-foreground">
                      {user.subscription_expires_at 
                        ? new Date(user.subscription_expires_at).toLocaleDateString("ru-RU")
                        : "—"}
                    </span>
                  </td>
                  <td>
                    <span className="font-medium">{user.listing_count || 0}</span>
                  </td>
                  <td>
                    <span className="font-medium">{user.requirement_count || 0}</span>
                  </td>
                  <td className="text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedUser(user);
                        setNewSubscription(user.subscription_type);
                      }}
                      className="h-8"
                    >
                      <Edit className="w-4 h-4 mr-1" />
                      {t('common.edit')}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-muted-foreground">
            {t('common.shown')} {filteredUsers.length} {t('common.of')} {users.length}
          </p>
        </div>
      </div>
    </div>
  );
}
