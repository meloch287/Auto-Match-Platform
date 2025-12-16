import { useState, useEffect } from "react";
import { Home, Search, RefreshCw, CheckCircle, XCircle, Loader2, MoreHorizontal, Car, List, Download } from "lucide-react";
import { useI18n } from "@/lib/i18n";
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
import { 
  getListings, getRequirements, changeListingStatus, changeRequirementStatus, Listing, Requirement,
  getAutoListings, getAutoRequirements, changeAutoListingStatus, changeAutoRequirementStatus, AutoListing, AutoRequirement
} from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import * as XLSX from "xlsx";

type MainTab = "all" | "realty" | "auto";
type RoleFilter = "all" | "sellers" | "buyers";

export function ModerationTab() {
  const [activeMainTab, setActiveMainTab] = useState<MainTab>("all");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [listings, setListings] = useState<Listing[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [autoListings, setAutoListings] = useState<AutoListing[]>([]);
  const [autoRequirements, setAutoRequirements] = useState<AutoRequirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const { toast } = useToast();
  const { t } = useI18n();

  useEffect(() => {
    loadData();
  }, [activeMainTab, roleFilter, statusFilter]);

  const loadData = async () => {
    setLoading(true);
    
    const statusParam = statusFilter === "all" ? undefined : statusFilter;
    
    if (activeMainTab === "all") {
      // Load all data
      const [listingsRes, reqsRes, autoListingsRes, autoReqsRes] = await Promise.all([
        roleFilter !== "buyers" ? getListings(1, 50, statusParam) : null,
        roleFilter !== "sellers" ? getRequirements(1, 50, statusParam) : null,
        roleFilter !== "buyers" ? getAutoListings(1, 50, statusParam) : null,
        roleFilter !== "sellers" ? getAutoRequirements(1, 50, statusParam) : null,
      ]);
      
      if (listingsRes?.success) setListings(listingsRes.data.listings);
      else if (roleFilter === "buyers") setListings([]);
      
      if (reqsRes?.success) setRequirements(reqsRes.data.requirements);
      else if (roleFilter === "sellers") setRequirements([]);
      
      if (autoListingsRes?.success) setAutoListings(autoListingsRes.data.listings);
      else if (roleFilter === "buyers") setAutoListings([]);
      
      if (autoReqsRes?.success) setAutoRequirements(autoReqsRes.data.requirements);
      else if (roleFilter === "sellers") setAutoRequirements([]);
      
    } else if (activeMainTab === "realty") {
      const [listingsRes, reqsRes] = await Promise.all([
        roleFilter !== "buyers" ? getListings(1, 50, statusParam) : null,
        roleFilter !== "sellers" ? getRequirements(1, 50, statusParam) : null,
      ]);
      
      if (listingsRes?.success) setListings(listingsRes.data.listings);
      else setListings([]);
      
      if (reqsRes?.success) setRequirements(reqsRes.data.requirements);
      else setRequirements([]);
      
      setAutoListings([]);
      setAutoRequirements([]);
      
    } else if (activeMainTab === "auto") {
      const [autoListingsRes, autoReqsRes] = await Promise.all([
        roleFilter !== "buyers" ? getAutoListings(1, 50, statusParam) : null,
        roleFilter !== "sellers" ? getAutoRequirements(1, 50, statusParam) : null,
      ]);
      
      if (autoListingsRes?.success) setAutoListings(autoListingsRes.data.listings);
      else setAutoListings([]);
      
      if (autoReqsRes?.success) setAutoRequirements(autoReqsRes.data.requirements);
      else setAutoRequirements([]);
      
      setListings([]);
      setRequirements([]);
    }
    
    setLoading(false);
  };

  const handleChangeListingStatus = async (id: string, newStatus: string) => {
    const result = await changeListingStatus(id, newStatus);
    if (result) {
      toast({ title: t('common.status_changed') });
      loadData();
    }
  };

  const handleChangeRequirementStatus = async (id: string, newStatus: string) => {
    const result = await changeRequirementStatus(id, newStatus);
    if (result) {
      toast({ title: t('common.status_changed') });
      loadData();
    }
  };

  const handleChangeAutoListingStatus = async (id: string, newStatus: string) => {
    const result = await changeAutoListingStatus(id, newStatus);
    if (result) {
      toast({ title: t('common.status_changed') });
      loadData();
    }
  };

  const handleChangeAutoRequirementStatus = async (id: string, newStatus: string) => {
    const result = await changeAutoRequirementStatus(id, newStatus);
    if (result) {
      toast({ title: t('common.status_changed') });
      loadData();
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
    const statusMap: Record<string, { variant: "active" | "secondary" | "destructive" | "warning"; labelKey: string }> = {
      active: { variant: "active", labelKey: "status.active" },
      inactive: { variant: "secondary", labelKey: "status.inactive" },
      pending_moderation: { variant: "warning", labelKey: "status.pending" },
      rejected: { variant: "destructive", labelKey: "status.rejected" },
      expired: { variant: "secondary", labelKey: "status.expired" },
      deleted: { variant: "destructive", labelKey: "status.deleted" },
    };
    const config = statusMap[status] || { variant: "secondary" as const, labelKey: status };
    return (
      <Badge variant={config.variant} className="gap-1">
        {config.variant === "active" ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
        {t(config.labelKey)}
      </Badge>
    );
  };

  // Calculate totals
  const totalPendingRealty = listings.filter(l => l.status === "pending_moderation").length;
  const totalPendingAuto = autoListings.filter(l => l.status === "pending_moderation").length;
  const totalAll = listings.length + requirements.length + autoListings.length + autoRequirements.length;

  // Export to Excel
  const exportToExcel = (type: "all" | "realty" | "auto") => {
    const wb = XLSX.utils.book_new();
    
    // Prepare sellers data
    const sellersData: Record<string, unknown>[] = [];
    const buyersData: Record<string, unknown>[] = [];
    
    if (type === "all" || type === "realty") {
      // Realty listings (sellers)
      listings.forEach(l => {
        sellersData.push({
          "Тип": "🏠 Недвижимость",
          "ID": l.id,
          "Продавец": l.seller_telegram_username ? `@${l.seller_telegram_username}` : l.seller_telegram_id,
          "Цена": l.price,
          "Комнат": l.rooms || "-",
          "Площадь": l.area ? `${l.area} м²` : "-",
          "Статус": l.status,
          "Дата": formatDate(l.created_at),
        });
      });
      
      // Realty requirements (buyers)
      requirements.forEach(r => {
        buyersData.push({
          "Тип": "🏠 Недвижимость",
          "ID": r.id,
          "Покупатель": r.buyer_telegram_username ? `@${r.buyer_telegram_username}` : r.buyer_telegram_id,
          "Цена от": r.price_min,
          "Цена до": r.price_max,
          "Комнат от": r.rooms_min || "-",
          "Комнат до": r.rooms_max || "-",
          "Площадь от": r.area_min ? `${r.area_min} м²` : "-",
          "Площадь до": r.area_max ? `${r.area_max} м²` : "-",
          "Статус": r.status,
          "Дата": formatDate(r.created_at),
        });
      });
    }
    
    if (type === "all" || type === "auto") {
      // Auto listings (sellers)
      autoListings.forEach(l => {
        sellersData.push({
          "Тип": "🚗 Авто",
          "ID": l.id,
          "Продавец": l.seller_telegram_username ? `@${l.seller_telegram_username}` : l.seller_telegram_id,
          "Марка": l.brand,
          "Модель": l.model,
          "Год": l.year,
          "Цена": l.price,
          "Тип сделки": l.deal_type === "rent" ? "Аренда" : "Продажа",
          "Статус": l.status,
          "Дата": formatDate(l.created_at),
        });
      });
      
      // Auto requirements (buyers)
      autoRequirements.forEach(r => {
        buyersData.push({
          "Тип": "🚗 Авто",
          "ID": r.id,
          "Покупатель": r.buyer_telegram_username ? `@${r.buyer_telegram_username}` : r.buyer_telegram_id,
          "Марки": r.brands?.join(", ") || "-",
          "Год от": r.year_min || "-",
          "Год до": r.year_max || "-",
          "Цена от": r.price_min,
          "Цена до": r.price_max,
          "Тип сделки": r.deal_type === "rent" ? "Аренда" : "Покупка",
          "Статус": r.status,
          "Дата": formatDate(r.created_at),
        });
      });
    }
    
    // Create sheets
    if (sellersData.length > 0) {
      const sellersSheet = XLSX.utils.json_to_sheet(sellersData);
      XLSX.utils.book_append_sheet(wb, sellersSheet, "Продавцы");
    }
    
    if (buyersData.length > 0) {
      const buyersSheet = XLSX.utils.json_to_sheet(buyersData);
      XLSX.utils.book_append_sheet(wb, buyersSheet, "Покупатели");
    }
    
    // Generate filename
    const typeNames = { all: "Все", realty: "Недвижимость", auto: "Авто" };
    const filename = `${typeNames[type]}_${new Date().toISOString().split("T")[0]}.xlsx`;
    
    // Download
    XLSX.writeFile(wb, filename);
    toast({ title: `Экспортировано: ${filename}` });
  };

  return (
    <div className="p-6">
      <div className="glass-card p-6 animate-fade-in">
        {/* Main Tab Navigation */}
        <div className="flex flex-wrap gap-3 mb-4">
          <button
            onClick={() => setActiveMainTab("all")}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all",
              activeMainTab === "all"
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80"
            )}
          >
            <List className="w-4 h-4" />
            {t('mod.all')}
          </button>
          <button
            onClick={() => setActiveMainTab("realty")}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all",
              activeMainTab === "realty"
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80"
            )}
          >
            <Home className="w-4 h-4" />
            🏠 {t('mod.realty')}
          </button>
          <button
            onClick={() => setActiveMainTab("auto")}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all",
              activeMainTab === "auto"
                ? "bg-primary text-primary-foreground shadow-md"
                : "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80"
            )}
          >
            <Car className="w-4 h-4" />
            🚗 {t('mod.auto')}
          </button>
        </div>

        {/* Filters Row */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {activeMainTab === "all" ? t('mod.all_requests') : activeMainTab === "realty" ? `🏠 ${t('mod.realty')}` : `🚗 ${t('mod.auto')}`}
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              {t('mod.on_moderation')}: {totalPendingRealty + totalPendingAuto} | {t('mod.total')}: {totalAll}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Select value={roleFilter} onValueChange={(v) => setRoleFilter(v as RoleFilter)}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('mod.all_roles')}</SelectItem>
                <SelectItem value="sellers">{t('mod.sellers')}</SelectItem>
                <SelectItem value="buyers">{t('mod.buyers')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('mod.all_statuses')}</SelectItem>
                <SelectItem value="pending_moderation">{t('mod.pending')}</SelectItem>
                <SelectItem value="active">{t('mod.active')}</SelectItem>
                <SelectItem value="rejected">{t('mod.rejected')}</SelectItem>
                <SelectItem value="inactive">{t('mod.inactive')}</SelectItem>
                <SelectItem value="expired">{t('mod.expired')}</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={loadData}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('mod.refresh')}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <Download className="w-4 h-4 mr-2" />
                  {t('mod.export')}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => exportToExcel("all")}>
                  📊 {t('mod.export_all')}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => exportToExcel("realty")}>
                  🏠 {t('mod.export_realty')}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => exportToExcel("auto")}>
                  🚗 {t('mod.export_auto')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center min-h-[300px]">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Realty Listings (Sellers) */}
            {(activeMainTab === "all" || activeMainTab === "realty") && roleFilter !== "buyers" && listings.length > 0 && (
              <div>
                <h4 className="text-md font-semibold mb-3 flex items-center gap-2">
                  <Home className="w-4 h-4" /> {t('mod.realty_sellers')} ({listings.length})
                </h4>
                <div className="overflow-hidden rounded-lg border border-border">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t('table.id')}</th>
                        <th>{t('table.seller')}</th>
                        <th>{t('table.price')}</th>
                        <th>{t('table.rooms')}</th>
                        <th>{t('table.area')}</th>
                        <th>{t('table.status')}</th>
                        <th>{t('table.date')}</th>
                        <th className="text-center">{t('table.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {listings.map((listing, index) => (
                        <tr key={listing.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.02}s` }}>
                          <td><code className="text-xs bg-muted px-2 py-1 rounded font-mono">{listing.id.substring(0, 8)}...</code></td>
                          <td><span className="font-medium text-primary">{listing.seller_telegram_username ? `@${listing.seller_telegram_username}` : listing.seller_telegram_id}</span></td>
                          <td><span className="text-sm font-medium">{formatSinglePrice(listing.price)}</span></td>
                          <td><span className="text-sm">{formatSingleValue(listing.rooms, ` ${t('common.rooms')}`)}</span></td>
                          <td><span className="text-sm">{formatSingleValue(listing.area, " м²")}</span></td>
                          <td>{getStatusBadge(listing.status)}</td>
                          <td><span className="text-sm text-muted-foreground">{formatDate(listing.created_at)}</span></td>
                          <td className="text-center">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto"><MoreHorizontal className="w-4 h-4" /></Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "active")}><CheckCircle className="w-4 h-4 mr-2 text-green-500" />{t('action.activate')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "rejected")}><XCircle className="w-4 h-4 mr-2 text-orange-500" />{t('action.reject')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeListingStatus(listing.id, "deleted")} className="text-destructive"><XCircle className="w-4 h-4 mr-2" />{t('action.delete')}</DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Realty Requirements (Buyers) */}
            {(activeMainTab === "all" || activeMainTab === "realty") && roleFilter !== "sellers" && requirements.length > 0 && (
              <div>
                <h4 className="text-md font-semibold mb-3 flex items-center gap-2">
                  <Search className="w-4 h-4" /> {t('mod.realty_buyers')} ({requirements.length})
                </h4>
                <div className="overflow-hidden rounded-lg border border-border">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t('table.id')}</th>
                        <th>{t('table.buyer')}</th>
                        <th>{t('table.price_range')}</th>
                        <th>{t('table.rooms')}</th>
                        <th>{t('table.area')}</th>
                        <th>{t('table.status')}</th>
                        <th>{t('table.date')}</th>
                        <th className="text-center">{t('table.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {requirements.map((req, index) => (
                        <tr key={req.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.02}s` }}>
                          <td><code className="text-xs bg-muted px-2 py-1 rounded font-mono">{req.id.substring(0, 8)}...</code></td>
                          <td><span className="font-medium text-primary">{req.buyer_telegram_username ? `@${req.buyer_telegram_username}` : req.buyer_telegram_id}</span></td>
                          <td><span className="text-sm font-medium">{formatPrice(req.price_min, req.price_max)}</span></td>
                          <td><span className="text-sm">{formatRange(req.rooms_min, req.rooms_max)}</span></td>
                          <td><span className="text-sm">{formatRange(req.area_min, req.area_max, " м²")}</span></td>
                          <td>{getStatusBadge(req.status)}</td>
                          <td><span className="text-sm text-muted-foreground">{formatDate(req.created_at)}</span></td>
                          <td className="text-center">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto"><MoreHorizontal className="w-4 h-4" /></Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleChangeRequirementStatus(req.id, "active")}><CheckCircle className="w-4 h-4 mr-2 text-green-500" />{t('action.activate')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeRequirementStatus(req.id, "inactive")}><XCircle className="w-4 h-4 mr-2 text-gray-500" />{t('action.deactivate')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeRequirementStatus(req.id, "deleted")} className="text-destructive"><XCircle className="w-4 h-4 mr-2" />{t('action.delete')}</DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Auto Listings (Sellers) */}
            {(activeMainTab === "all" || activeMainTab === "auto") && roleFilter !== "buyers" && autoListings.length > 0 && (
              <div>
                <h4 className="text-md font-semibold mb-3 flex items-center gap-2">
                  <Car className="w-4 h-4" /> {t('mod.auto_sellers')} ({autoListings.length})
                </h4>
                <div className="overflow-hidden rounded-lg border border-border">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t('table.id')}</th>
                        <th>{t('table.seller')}</th>
                        <th>{t('table.brand_model')}</th>
                        <th>{t('table.year')}</th>
                        <th>{t('table.price')}</th>
                        <th>{t('table.type')}</th>
                        <th>{t('table.status')}</th>
                        <th>{t('table.date')}</th>
                        <th className="text-center">{t('table.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {autoListings.map((listing, index) => (
                        <tr key={listing.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.02}s` }}>
                          <td><code className="text-xs bg-muted px-2 py-1 rounded font-mono">{listing.id.substring(0, 8)}...</code></td>
                          <td><span className="font-medium text-primary">{listing.seller_telegram_username ? `@${listing.seller_telegram_username}` : listing.seller_telegram_id}</span></td>
                          <td><span className="text-sm font-medium">{listing.brand} {listing.model}</span></td>
                          <td><span className="text-sm">{listing.year}</span></td>
                          <td><span className="text-sm font-medium">{formatSinglePrice(listing.price)}</span></td>
                          <td><Badge variant={listing.deal_type === "rent" ? "secondary" : "default"}>{listing.deal_type === "rent" ? t('deal.rent') : t('deal.sale')}</Badge></td>
                          <td>{getStatusBadge(listing.status)}</td>
                          <td><span className="text-sm text-muted-foreground">{formatDate(listing.created_at)}</span></td>
                          <td className="text-center">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto"><MoreHorizontal className="w-4 h-4" /></Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleChangeAutoListingStatus(listing.id, "active")}><CheckCircle className="w-4 h-4 mr-2 text-green-500" />{t('action.activate')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeAutoListingStatus(listing.id, "rejected")}><XCircle className="w-4 h-4 mr-2 text-orange-500" />{t('action.reject')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeAutoListingStatus(listing.id, "deleted")} className="text-destructive"><XCircle className="w-4 h-4 mr-2" />{t('action.delete')}</DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Auto Requirements (Buyers) */}
            {(activeMainTab === "all" || activeMainTab === "auto") && roleFilter !== "sellers" && autoRequirements.length > 0 && (
              <div>
                <h4 className="text-md font-semibold mb-3 flex items-center gap-2">
                  <Search className="w-4 h-4" /> {t('mod.auto_buyers')} ({autoRequirements.length})
                </h4>
                <div className="overflow-hidden rounded-lg border border-border">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t('table.id')}</th>
                        <th>{t('table.buyer')}</th>
                        <th>{t('table.brands')}</th>
                        <th>{t('table.year')}</th>
                        <th>{t('table.price')}</th>
                        <th>{t('table.type')}</th>
                        <th>{t('table.status')}</th>
                        <th>{t('table.date')}</th>
                        <th className="text-center">{t('table.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {autoRequirements.map((req, index) => (
                        <tr key={req.id} className="animate-fade-in" style={{ animationDelay: `${index * 0.02}s` }}>
                          <td><code className="text-xs bg-muted px-2 py-1 rounded font-mono">{req.id.substring(0, 8)}...</code></td>
                          <td><span className="font-medium text-primary">{req.buyer_telegram_username ? `@${req.buyer_telegram_username}` : req.buyer_telegram_id}</span></td>
                          <td><span className="text-sm">{req.brands?.slice(0, 2).join(", ") || "-"}{req.brands && req.brands.length > 2 ? "..." : ""}</span></td>
                          <td><span className="text-sm">{formatRange(req.year_min, req.year_max)}</span></td>
                          <td><span className="text-sm font-medium">{formatPrice(req.price_min, req.price_max)}</span></td>
                          <td><Badge variant={req.deal_type === "rent" ? "secondary" : "default"}>{req.deal_type === "rent" ? t('deal.rent') : t('deal.buy')}</Badge></td>
                          <td>{getStatusBadge(req.status)}</td>
                          <td><span className="text-sm text-muted-foreground">{formatDate(req.created_at)}</span></td>
                          <td className="text-center">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 mx-auto"><MoreHorizontal className="w-4 h-4" /></Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleChangeAutoRequirementStatus(req.id, "active")}><CheckCircle className="w-4 h-4 mr-2 text-green-500" />{t('action.activate')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeAutoRequirementStatus(req.id, "inactive")}><XCircle className="w-4 h-4 mr-2 text-gray-500" />{t('action.deactivate')}</DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleChangeAutoRequirementStatus(req.id, "deleted")} className="text-destructive"><XCircle className="w-4 h-4 mr-2" />{t('action.delete')}</DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Empty state */}
            {listings.length === 0 && requirements.length === 0 && autoListings.length === 0 && autoRequirements.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                {t('mod.no_requests')}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
