import { useState, useEffect } from "react";
import { Search, UserCheck, UserX, Loader2, RefreshCw, Trash2, Settings2, Download } from "lucide-react";
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
import { getUsers, blockUser, unblockUser, resetUserLimits, deleteUser, updateUserLimits, User, exportUsers, downloadBlob } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();

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
        toast({ title: t('users.unblocked') });
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
    const result = await blockUser(userToBlock.id, reason || "Blocked by admin");
    if (result) {
      toast({ title: t('users.blocked_msg') });
      setBlockDialogOpen(false);
      setUserToBlock(null);
      setBlockReason("");
      loadUsers();
    }
  };

  const handleResetLimits = async (user: User) => {
    const result = await resetUserLimits(user.id);
    if (result) {
      toast({ title: t('users.limits_reset') });
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
      toast({ title: t('users.deleted') });
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
      toast({ title: t('limits.updated') });
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
            <h2 className="text-xl font-bold text-foreground">{t('users.title')}</h2>
            <p className="text-sm text-muted-foreground mt-1">{t('users.total')}: {users.length}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('users.search_placeholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-72 pl-10"
              />
            </div>
            <Button variant="outline" size="sm" onClick={handleSearch}>
              <Search className="w-4 h-4 mr-2" />
              {t('common.search')}
            </Button>
            <Button variant="outline" size="sm" onClick={loadUsers}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('common.refresh')}
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={async () => {
                const blob = await exportUsers();
                if (blob) downloadBlob(blob, 'users.csv');
              }}
            >
              <Download className="w-4 h-4 mr-2" />
              CSV
            </Button>
          </div>
        </div>

        <div className="overflow-hidden rounded-lg border border-border">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('users.telegram_id')}</th>
                <th>{t('users.username')}</th>
                <th>{t('users.subscription')}</th>
                <th>{t('users.listings')}</th>
                <th>{t('users.requests')}</th>
                <th>{t('users.status')}</th>
                <th className="text-center">{t('users.actions')}</th>
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
                          {t('users.active')}
                        </>
                      ) : (
                        <>
                          <UserX className="w-3 h-3" />
                          {t('users.blocked')}
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
                        title={t('users.change_limits')}
                      >
                        <Settings2 className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleResetLimits(user)}
                        className="h-7 text-xs"
                      >
                        {t('users.reset_limits')}
                      </Button>
                      <Button
                        variant={!user.is_blocked ? "outline" : "success"}
                        size="sm"
                        onClick={() => toggleUserStatus(user)}
                        className="h-7 text-xs"
                      >
                        {!user.is_blocked ? t('users.block') : t('users.unblock')}
                      </Button>
                      <Button
                        variant="destructive"
                        size="icon"
                        onClick={() => handleDeleteClick(user)}
                        className="h-7 w-7"
                        title={t('users.delete')}
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
            {t('common.page')} {page} {t('common.of')} {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              {t('common.back')}
            </Button>
            <div className="px-3 py-1 bg-primary text-primary-foreground rounded-md text-sm font-medium">
              {page}
            </div>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              {t('common.forward')}
            </Button>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('users.delete_confirm')}</DialogTitle>
            <DialogDescription>
              <strong>{userToDelete?.telegram_username ? `@${userToDelete.telegram_username}` : userToDelete?.telegram_id}</strong>
              <br />
              {t('users.delete_warning')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              {t('users.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Limits Edit Dialog */}
      <Dialog open={limitsDialogOpen} onOpenChange={setLimitsDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('users.change_limits')}</DialogTitle>
            <DialogDescription>
              <strong>{userToEditLimits?.telegram_username ? `@${userToEditLimits.telegram_username}` : userToEditLimits?.telegram_id}</strong>
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('limits.listings_limit')} ({t('limits.per_month')})</label>
              <Select value={listingsLimit} onValueChange={setListingsLimit}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">{t('limits.default')}</SelectItem>
                  <SelectItem value="unlimited">{t('limits.unlimited')}</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="6">6</SelectItem>
                  <SelectItem value="custom">{t('limits.custom')}</SelectItem>
                </SelectContent>
              </Select>
              {listingsLimit === "custom" && (
                <Input
                  type="number"
                  value={customListings}
                  onChange={(e) => setCustomListings(e.target.value)}
                  min={1}
                />
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('limits.requests_limit')} ({t('limits.per_month')})</label>
              <Select value={requirementsLimit} onValueChange={setRequirementsLimit}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">{t('limits.default')}</SelectItem>
                  <SelectItem value="unlimited">{t('limits.unlimited')}</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="6">6</SelectItem>
                  <SelectItem value="custom">{t('limits.custom')}</SelectItem>
                </SelectContent>
              </Select>
              {requirementsLimit === "custom" && (
                <Input
                  type="number"
                  value={customRequirements}
                  onChange={(e) => setCustomRequirements(e.target.value)}
                  min={1}
                />
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setLimitsDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleLimitsSave}>
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Block User Dialog */}
      <Dialog open={blockDialogOpen} onOpenChange={setBlockDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('users.block_user')}</DialogTitle>
            <DialogDescription>
              <strong>{userToBlock?.telegram_username ? `@${userToBlock.telegram_username}` : userToBlock?.telegram_id}</strong>
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('users.block_reason')}</label>
              <Input
                value={blockReason}
                onChange={(e) => setBlockReason(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setBlockDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="secondary" onClick={() => handleBlockConfirm("")}>
              {t('users.skip')}
            </Button>
            <Button variant="destructive" onClick={() => handleBlockConfirm(blockReason)}>
              {t('users.block')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
