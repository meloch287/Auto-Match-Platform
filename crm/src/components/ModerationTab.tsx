import { useState, useEffect } from "react";
import { Home, Search, RefreshCw, CheckCircle, XCircle, Loader2, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { getListings, getRequirements, changeListingStatus, changeRequirementStatus, Listing, Requirement } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

type SubTab = "sellers" | "buyers";

export function ModerationTab() {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("buyers");
  const [listings, setListings] = useState<Listing[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [listingStatusFilter, setListingStatusFilter] = useState("all");
  const { toast } = useToast();

  useEffect(() => {
    if (activeSubTab === "buyers") {
      loadRequirements();
    } else {
      loadListings();
    }
  }, [activeSubTab, statusFilter, listingStatusFilter]);

  const loadRequirements = async () => {
    setLoading(true);
    const result = await getRequirements(1, 50, statusFilter === "all" ? undefined : statusFilter);
    if (result?.success) {
      setRequirements(result.data.requirements);
    }
    setLoading(false);
  };

  const loadListings = async () => {
    setLoading(true);
    const result = await getListings(1, 50, listingStatusFilter === "all" ? undefined : listingStatusFilter);
    if (result?.success) {
      setListings(result.data.listings);
    }
    setLoading(false);
  };


  const handleChangeListingStatus = async (id: string, newStatus: string) => {
    const result = await changeListingStatus(id, newStatus);
    if (result) {
      toast({ title: `Статус изменён на ${newStatus}` });
      loadListings();
    }
  };

  const handleChangeRequirementStatus = async (id: string, newStatus: string) => {
    const result = await changeRequirementStatus(id, newStatus);
    if (result) {
      toast({ title: `Статус изменён на ${newStatus}` });
      loadRequirements();
    }
  };

  const formatPrice = (min: number | null, max: number | null) => {
    if (min === null && max === null) return "-";
    const minStr = min !== null ? min.toLocaleString() : "0";
    const maxStr = max !== null ? max.toLocaleString() : "∞";
    return `${minStr} - ${maxStr} AZN`;
  };

  const formatRange = (min: number | null, max: number | null, suffix = "") => {
    if (min === null && max === null) return "-";
    const minStr = min !== null ? min.toString() : "?";
    const maxStr = max !== null ? max.toString() : "?";
    return `${minStr} - ${maxStr}${suffix}`;
  };

  const formatSinglePrice = (price: number | null) => {
    if (price === null) return "-";
    return `${price.toLocaleString()} AZN`;
  };

  const formatSingleValue = (value: number | null, suffix = "") => {
    if (value === null) return "-";
    return `${value}${suffix}`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("ru-RU");
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { variant: "active" | "secondary" | "destructive" | "warning"; label: string }> = {
      active: { variant: "active", label: "Активно" },
      inactive: { variant: "secondary", label: "Неактивно" },
      pending_moderation: { variant: "warning", label: "На модерации" },
      rejected: { variant: "destructive", label: "Отклонено" },
      expired: { variant: "secondary", label: "Истекло" },
      deleted: { variant: "destructive", label: "Удалено" },
    };
    const config = statusMap[status] || { variant: "secondary" as const, label: status };
    return (
      <Badge variant={config.variant} className="gap-1">
        {config.variant === "active" ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="p-6">
      <div className="glass-card p-6 animate-fade-in">
        {/* Sub Navigation */}
        <div className="flex gap-3 mb-6">
          <button
            onClick={() => setActiveSubTab("sellers")}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all",
              activeSubTab === "sellers"
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80"
            )}
          >
            <Home className="w-4 h-4" />
            Объявления (продавцы)
          </button>
          <button
            onClick={() => setActiveSubTab("buyers")}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all",
              activeSubTab === "buyers"
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80"
            )}
          >
            <Search className="w-4 h-4" />
            Заявки (покупатели)
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center min-h-[300px]">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : activeSubTab === "buyers" ? (
          <>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-foreground">Заявки покупателей</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Активных: {requirements.filter(r => r.status === "active").length} | 
                  Всего: {requirements.length}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Все статусы" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все статусы</SelectItem>
                    <SelectItem value="active">Активно</SelectItem>
                    <SelectItem value="inactive">Неактивно</SelectItem>
                    <SelectItem value="expired">Истекло</SelectItem>
                  </SelectContent>
                </Select>
                <Button variant="outline" size="sm" onClick={loadRequirements}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Обновить
                </Button>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-border">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Покупатель</th>
                    <th>Цена (от-до)</th>
                    <th>Комнат</th>
                    <th>Площадь</th>
                    <th>Статус</th>
                    <th>Дата</th>
                    <th className="text-center">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {requirements.map((req, index) => (
                    <tr key={req.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.05}s` }}>
                      <td>
                        <code className="text-xs bg-muted px-2 py-1 rounded font-mono">{req.id.substring(0, 8)}...</code>
                      </td>
                      <td>
                        <span className="font-medium text-primary hover:underline cursor-pointer">
                          {req.buyer_telegram_username ? `@${req.buyer_telegram_username}` : req.buyer_telegram_id}
                        </span>
                      </td>
                      <td>
                        <span className="text-sm font-medium">{formatPrice(req.price_min, req.price_max)}</span>
                      </td>
                      <td>
                        <span className="text-sm">{formatRange(req.rooms_min, req.rooms_max)}</span>
                      </td>
                      <td>
                        <span className="text-sm">{formatRange(req.area_min, req.area_max, " м²")}</span>
                      </td>
                      <td>{getStatusBadge(req.status)}</td>
                      <td>
                        <span className="text-sm text-muted-foreground">{formatDate(req.created_at)}</span>
                      </td>
                      <td className="text-center">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleChangeRequirementStatus(req.id, "active")}>
                              <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
                              Активировать
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeRequirementStatus(req.id, "inactive")}>
                              <XCircle className="w-4 h-4 mr-2 text-gray-500" />
                              Деактивировать
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeRequirementStatus(req.id, "deleted")} className="text-destructive">
                              <XCircle className="w-4 h-4 mr-2" />
                              Удалить
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                  {requirements.length === 0 && (
                    <tr>
                      <td colSpan={8} className="text-center py-8 text-muted-foreground">
                        Нет заявок
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-foreground">Объявления продавцов</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  На модерации: {listings.filter(l => l.status === "pending_moderation").length} | 
                  Всего: {listings.length}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Select value={listingStatusFilter} onValueChange={setListingStatusFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Все статусы" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Все статусы</SelectItem>
                    <SelectItem value="pending_moderation">На модерации</SelectItem>
                    <SelectItem value="active">Активные</SelectItem>
                    <SelectItem value="rejected">Отклонённые</SelectItem>
                    <SelectItem value="expired">Истёкшие</SelectItem>
                  </SelectContent>
                </Select>
                <Button variant="outline" size="sm" onClick={loadListings}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Обновить
                </Button>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-border">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Продавец</th>
                    <th>Цена</th>
                    <th>Комнат</th>
                    <th>Площадь</th>
                    <th>Статус</th>
                    <th>Дата</th>
                    <th className="text-center">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {listings.map((listing, index) => (
                    <tr key={listing.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.05}s` }}>
                      <td>
                        <code className="text-xs bg-muted px-2 py-1 rounded font-mono">{listing.id.substring(0, 8)}...</code>
                      </td>
                      <td>
                        <span className="font-medium text-primary hover:underline cursor-pointer">
                          {listing.seller_telegram_username ? `@${listing.seller_telegram_username}` : listing.seller_telegram_id}
                        </span>
                      </td>
                      <td>
                        <span className="text-sm font-medium">{formatSinglePrice(listing.price)}</span>
                      </td>
                      <td>
                        <span className="text-sm">{formatSingleValue(listing.rooms, " комн.")}</span>
                      </td>
                      <td>
                        <span className="text-sm">{formatSingleValue(listing.area, " м²")}</span>
                      </td>
                      <td>{getStatusBadge(listing.status)}</td>
                      <td>
                        <span className="text-sm text-muted-foreground">{formatDate(listing.created_at)}</span>
                      </td>
                      <td className="text-center">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "active")}>
                              <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
                              Активировать
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "inactive")}>
                              <XCircle className="w-4 h-4 mr-2 text-gray-500" />
                              Деактивировать
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "rejected")}>
                              <XCircle className="w-4 h-4 mr-2 text-orange-500" />
                              Отклонить
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "deleted")} className="text-destructive">
                              <XCircle className="w-4 h-4 mr-2" />
                              Удалить
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                  {listings.length === 0 && (
                    <tr>
                      <td colSpan={8} className="text-center py-8 text-muted-foreground">
                        Нет объявлений
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
