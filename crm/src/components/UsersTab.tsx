import { useState, useEffect } from "react";
import { Search, UserCheck, UserX, Loader2, RefreshCw, Trash2, Settings2 } from "lucide-react";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getUsers, blockUser, unblockUser, resetUserLimits, deleteUser, updateUserLimits, User } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const subscriptionColors: Record<string, string> = {
  free: "bg-muted text-muted-foreground",
  premium: "bg-gradient-to-r from-primary/20 to-accent/20 text-primary border border-primary/20",
  agency_basic: "bg-gradient-to-r from-info/20 to-info/10 text-info border border-info/20",
  agency_pro: "bg-gradient-to-r from-warning/20 to-warning/10 text-warning border border-warning/20",
};

export function UsersTab() {
  const [searchQuery, setSearchQuery] = useState("");
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const { toast } = useToast();

  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  // Limits dialog
  const [limitsDialogOpen, setLimitsDialogOpen] = useState(false);
  const [userToEditLimits, setUserToEditLimits] = useState<User | null>(null);
  const [listingsLimit, setListingsLimit] = useState<string>("default");
  const [requirementsLimit, setRequirementsLimit] = useState<string>("default");
  const [customListings, setCustomListings] = useState("");
  const [customRequirements, setCustomRequirements] = useState("");

  // Block dialog
  const [blockDialogOpen, setBlockDialogOpen] = useState(false);
  const [userToBlock, setUserToBlock] = useState<User | null>(null);
  const [blockReason, setBlockReason] = useState("");

  useEffect(() => {
    loadUsers();
  }, [page]);

  const loadUsers = async () => {
    setLoading(true);
    const result = await getUsers(page, 10, searchQuery || undefined);
    if (result?.success) {
      setUsers(result.data.users);
      setTotalPages(result.pagination?.total_pages || 1);
    }
    setLoading(false);
  };


  const handleSearch = () => {
    setPage(1);
    loadUsers();
  };

  const toggleUserStatus = async (user: User) => {
    if (user.is_blocked) {
      const result = await unblockUser(user.id);
      if (result) {
        toast({ title: "Пользователь разблокирован" });
        loadUsers();
      }
    } else {
      // Open block dialog
      setUserToBlock(user);
      setBlockReason("");
      setBlockDialogOpen(true);
    }
  };

  const handleBlockConfirm = async (reason: string) => {
    if (!userToBlock) return;
    const result = await blockUser(userToBlock.id, reason || "Заблокирован администратором");
    if (result) {
      toast({ title: "Пользователь заблокирован" });
      setBlockDialogOpen(false);
      setUserToBlock(null);
      setBlockReason("");
      loadUsers();
    }
  };

  const handleResetLimits = async (user: User) => {
    const result = await resetUserLimits(user.id);
    if (result) {
      toast({ title: "Лимиты сброшены" });
      loadUsers();
    }
  };

  const handleDeleteClick = (user: User) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;
    const result = await deleteUser(userToDelete.id);
    if (result) {
      toast({ title: "Пользователь удалён" });
      setDeleteDialogOpen(false);
      setUserToDelete(null);
      loadUsers();
    }
  };

  const handleLimitsClick = (user: User) => {
    setUserToEditLimits(user);
    setListingsLimit("default");
    setRequirementsLimit("default");
    setCustomListings("");
    setCustomRequirements("");
    setLimitsDialogOpen(true);
  };

  const handleLimitsSave = async () => {
    if (!userToEditLimits) return;

    let listingsValue: number | null = null;
    let requirementsValue: number | null = null;

    // Parse listings limit
    if (listingsLimit === "unlimited") {
      listingsValue = 0; // 0 = unlimited in backend
    } else if (listingsLimit === "custom") {
      listingsValue = parseInt(customListings) || null;
    } else if (listingsLimit !== "default") {
      listingsValue = parseInt(listingsLimit);
    }

    // Parse requirements limit
    if (requirementsLimit === "unlimited") {
      requirementsValue = 0; // 0 = unlimited in backend
    } else if (requirementsLimit === "custom") {
      requirementsValue = parseInt(customRequirements) || null;
    } else if (requirementsLimit !== "default") {
      requirementsValue = parseInt(requirementsLimit);
    }

    const result = await updateUserLimits(userToEditLimits.id, listingsValue, requirementsValue);
    if (result) {
      toast({ title: "Лимиты обновлены" });
      setLimitsDialogOpen(false);
      setUserToEditLimits(null);
      loadUsers();
    }
  };

  if (loading && users.length === 0) {
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
            <h2 className="text-xl font-bold text-foreground">Пользователи</h2>
            <p className="text-sm text-muted-foreground mt-1">Всего: {users.length} пользователей</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Поиск по username или ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-72 pl-10"
              />
            </div>
            <Button variant="outline" size="sm" onClick={handleSearch}>
              <Search className="w-4 h-4 mr-2" />
              Поиск
            </Button>
            <Button variant="outline" size="sm" onClick={loadUsers}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>
        </div>

        <div className="overflow-hidden rounded-lg border border-border">
          <table className="data-table">
            <thead>
              <tr>
                <th>Telegram ID</th>
                <th>Username</th>
                <th>Подписка</th>
                <th>Объявлений</th>
                <th>Заявок</th>
                <th>Статус</th>
                <th className="text-center">Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user, index) => (
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
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${subscriptionColors[user.subscription_type] || subscriptionColors.free}`}>
                      {user.subscription_type.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <span className="font-medium">{user.listing_count || 0}</span>
                  </td>
                  <td>
                    <span className="font-medium">{user.requirement_count || 0}</span>
                  </td>
                  <td>
                    <Badge variant={!user.is_blocked ? "active" : "destructive"} className="gap-1">
                      {!user.is_blocked ? (
                        <>
                          <UserCheck className="w-3 h-3" />
                          Активен
                        </>
                      ) : (
                        <>
                          <UserX className="w-3 h-3" />
                          Заблокирован
                        </>
                      )}
                    </Badge>
                  </td>
                  <td className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleLimitsClick(user)}
                        className="h-7 w-7"
                        title="Изменить лимиты"
                      >
                        <Settings2 className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleResetLimits(user)}
                        className="h-7 text-xs"
                      >
                        Сбросить
                      </Button>
                      <Button
                        variant={!user.is_blocked ? "outline" : "success"}
                        size="sm"
                        onClick={() => toggleUserStatus(user)}
                        className="h-7 text-xs"
                      >
                        {!user.is_blocked ? "Блок" : "Разблок"}
                      </Button>
                      <Button
                        variant="destructive"
                        size="icon"
                        onClick={() => handleDeleteClick(user)}
                        className="h-7 w-7"
                        title="Удалить"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>


        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-muted-foreground">
            Страница {page} из {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              ← Назад
            </Button>
            <div className="px-3 py-1 bg-primary text-primary-foreground rounded-md text-sm font-medium">
              {page}
            </div>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              Вперед →
            </Button>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Удалить пользователя?</DialogTitle>
            <DialogDescription>
              Вы уверены, что хотите удалить пользователя{" "}
              <strong>{userToDelete?.telegram_username ? `@${userToDelete.telegram_username}` : userToDelete?.telegram_id}</strong>?
              <br />
              Все его объявления и заявки будут удалены. Это действие нельзя отменить.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Отмена
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              Удалить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Limits Edit Dialog */}
      <Dialog open={limitsDialogOpen} onOpenChange={setLimitsDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Изменить лимиты</DialogTitle>
            <DialogDescription>
              Пользователь:{" "}
              <strong>{userToEditLimits?.telegram_username ? `@${userToEditLimits.telegram_username}` : userToEditLimits?.telegram_id}</strong>
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Лимит объявлений (в месяц)</label>
              <Select value={listingsLimit} onValueChange={setListingsLimit}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите лимит" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">По умолчанию</SelectItem>
                  <SelectItem value="unlimited">Безлимит</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="6">6</SelectItem>
                  <SelectItem value="custom">Своё значение</SelectItem>
                </SelectContent>
              </Select>
              {listingsLimit === "custom" && (
                <Input
                  type="number"
                  placeholder="Введите число"
                  value={customListings}
                  onChange={(e) => setCustomListings(e.target.value)}
                  min={1}
                />
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Лимит заявок (в месяц)</label>
              <Select value={requirementsLimit} onValueChange={setRequirementsLimit}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите лимит" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">По умолчанию</SelectItem>
                  <SelectItem value="unlimited">Безлимит</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="6">6</SelectItem>
                  <SelectItem value="custom">Своё значение</SelectItem>
                </SelectContent>
              </Select>
              {requirementsLimit === "custom" && (
                <Input
                  type="number"
                  placeholder="Введите число"
                  value={customRequirements}
                  onChange={(e) => setCustomRequirements(e.target.value)}
                  min={1}
                />
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setLimitsDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleLimitsSave}>
              Сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Block User Dialog */}
      <Dialog open={blockDialogOpen} onOpenChange={setBlockDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Заблокировать пользователя</DialogTitle>
            <DialogDescription>
              Пользователь:{" "}
              <strong>{userToBlock?.telegram_username ? `@${userToBlock.telegram_username}` : userToBlock?.telegram_id}</strong>
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Причина блокировки (необязательно)</label>
              <Input
                placeholder="Введите причину..."
                value={blockReason}
                onChange={(e) => setBlockReason(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setBlockDialogOpen(false)}>
              Отмена
            </Button>
            <Button variant="secondary" onClick={() => handleBlockConfirm("")}>
              Пропустить
            </Button>
            <Button variant="destructive" onClick={() => handleBlockConfirm(blockReason)}>
              Заблокировать
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
