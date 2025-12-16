import { useState, useEffect } from "react";
import { Save, RefreshCw, Loader2, Settings2, Infinity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getSettings, updateSettings, Settings } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useI18n } from "@/lib/i18n";

export function LimitsTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();
  const { t } = useI18n();

  // Listings limit
  const [listingsLimitType, setListingsLimitType] = useState<string>("custom");
  const [listingsLimitValue, setListingsLimitValue] = useState<string>("1");

  // Requirements limit
  const [requirementsLimitType, setRequirementsLimitType] = useState<string>("custom");
  const [requirementsLimitValue, setRequirementsLimitValue] = useState<string>("5");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    const result = await getSettings();
    if (result?.success && result.data) {
      const settings = result.data;
      
      // Set listings limit
      if (settings.free_listings_per_month === 0) {
        setListingsLimitType("unlimited");
      } else if ([2, 4, 6].includes(settings.free_listings_per_month)) {
        setListingsLimitType(settings.free_listings_per_month.toString());
      } else {
        setListingsLimitType("custom");
        setListingsLimitValue(settings.free_listings_per_month.toString());
      }

      // Set requirements limit
      if (settings.free_requirements_per_month === 0) {
        setRequirementsLimitType("unlimited");
      } else if ([2, 4, 6].includes(settings.free_requirements_per_month)) {
        setRequirementsLimitType(settings.free_requirements_per_month.toString());
      } else {
        setRequirementsLimitType("custom");
        setRequirementsLimitValue(settings.free_requirements_per_month.toString());
      }
    }
    setLoading(false);
  };


  const handleSave = async () => {
    setSaving(true);

    let listingsLimit: number;
    let requirementsLimit: number;

    // Parse listings limit
    if (listingsLimitType === "unlimited") {
      listingsLimit = 0;
    } else if (listingsLimitType === "custom") {
      listingsLimit = parseInt(listingsLimitValue) || 1;
    } else {
      listingsLimit = parseInt(listingsLimitType);
    }

    // Parse requirements limit
    if (requirementsLimitType === "unlimited") {
      requirementsLimit = 0;
    } else if (requirementsLimitType === "custom") {
      requirementsLimit = parseInt(requirementsLimitValue) || 5;
    } else {
      requirementsLimit = parseInt(requirementsLimitType);
    }

    const result = await updateSettings({
      free_listings_per_month: listingsLimit,
      free_requirements_per_month: requirementsLimit,
    });

    if (result?.success) {
      toast({ title: t('limits.saved') });
    } else {
      toast({ title: t('limits.save_error'), variant: "destructive" });
    }

    setSaving(false);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="glass-card p-6 animate-fade-in max-w-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg bg-primary/10">
            <Settings2 className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">{t('limits.title')}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {t('limits.subtitle')}
            </p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Listings Limit */}
          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">🏷️</span>
              <h3 className="font-semibold">{t('limits.listings_limit')}</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {t('limits.listings_desc')}
            </p>
            <div className="flex items-center gap-3">
              <Select value={listingsLimitType} onValueChange={setListingsLimitType}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="unlimited">
                    <span className="flex items-center gap-2">
                      <Infinity className="w-4 h-4" /> {t('limits.unlimited')}
                    </span>
                  </SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="6">6</SelectItem>
                  <SelectItem value="custom">{t('limits.custom')}</SelectItem>
                </SelectContent>
              </Select>
              {listingsLimitType === "custom" && (
                <Input
                  type="number"
                  value={listingsLimitValue}
                  onChange={(e) => setListingsLimitValue(e.target.value)}
                  className="w-24"
                  min={1}
                />
              )}
            </div>
          </div>

          {/* Requirements Limit */}
          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">🔍</span>
              <h3 className="font-semibold">{t('limits.requests_limit')}</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {t('limits.requests_desc')}
            </p>
            <div className="flex items-center gap-3">
              <Select value={requirementsLimitType} onValueChange={setRequirementsLimitType}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="unlimited">
                    <span className="flex items-center gap-2">
                      <Infinity className="w-4 h-4" /> {t('limits.unlimited')}
                    </span>
                  </SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="6">6</SelectItem>
                  <SelectItem value="custom">{t('limits.custom')}</SelectItem>
                </SelectContent>
              </Select>
              {requirementsLimitType === "custom" && (
                <Input
                  type="number"
                  value={requirementsLimitValue}
                  onChange={(e) => setRequirementsLimitValue(e.target.value)}
                  className="w-24"
                  min={1}
                />
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 mt-6 pt-6 border-t border-border">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            {t('common.save')}
          </Button>
          <Button variant="outline" onClick={loadSettings} disabled={loading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            {t('common.reset')}
          </Button>
        </div>
      </div>
    </div>
  );
}
