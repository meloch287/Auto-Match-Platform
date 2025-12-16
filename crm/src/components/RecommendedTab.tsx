import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Trash2, Plus, GripVertical, Shuffle, ImageOff } from 'lucide-react';
import {
  getRecommendedListings,
  getAvailableListingsForRecommended,
  addRecommendedListing,
  removeRecommendedListing,
  setRandomRecommended,
  RecommendedListing,
  AvailableListing,
  apiCall,
} from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/lib/i18n';

// Component to load Telegram photos
function TelegramPhoto({ fileId, className }: { fileId: string | null; className?: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!fileId) return;
    
    apiCall<{ success: boolean; data: { url: string } }>(`/media/telegram/${fileId}`)
      .then(res => {
        if (res?.success && res.data?.url) {
          setUrl(res.data.url);
        } else {
          setError(true);
        }
      })
      .catch(() => setError(true));
  }, [fileId]);

  if (!fileId || error) {
    return (
      <div className={`bg-muted flex items-center justify-center ${className}`}>
        <ImageOff className="h-6 w-6 text-muted-foreground" />
      </div>
    );
  }

  if (!url) {
    return <div className={`bg-muted animate-pulse ${className}`} />;
  }

  return <img src={url} alt="" className={className} onError={() => setError(true)} />;
}

export function RecommendedTab() {
  const [recommended, setRecommended] = useState<RecommendedListing[]>([]);
  const [available, setAvailable] = useState<AvailableListing[]>([]);
  const [isRandom, setIsRandom] = useState(false);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const { t } = useI18n();

  const loadData = async () => {
    setLoading(true);
    try {
      const [recRes, availRes] = await Promise.all([
        getRecommendedListings(),
        getAvailableListingsForRecommended(),
      ]);
      
      if (recRes?.success) {
        setRecommended(recRes.data.recommended);
        setIsRandom(recRes.data.recommended.some(r => r.is_random));
      }
      if (availRes?.success) {
        setAvailable(availRes.data.listings);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAdd = async (listingId: string) => {
    const res = await addRecommendedListing(listingId);
    if (res) {
      toast({ title: t('rec.added') });
      loadData();
    }
  };

  const handleRemove = async (recId: string) => {
    const res = await removeRecommendedListing(recId);
    if (res) {
      toast({ title: t('rec.removed') });
      loadData();
    }
  };

  const handleRandomToggle = async (enabled: boolean) => {
    const res = await setRandomRecommended(enabled);
    if (res) {
      setIsRandom(enabled);
      toast({ title: enabled ? t('rec.random_on') : t('rec.random_off') });
      loadData();
    }
  };

  const formatPrice = (price: number | null) => {
    if (!price) return '-';
    return new Intl.NumberFormat('ru-RU').format(price) + ' AZN';
  };

  if (loading) {
    return <div className="p-4">{t('common.loading')}</div>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{t('rec.title')}</span>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  id="random-mode"
                  checked={isRandom}
                  onCheckedChange={handleRandomToggle}
                />
                <Label htmlFor="random-mode" className="flex items-center gap-1">
                  <Shuffle className="h-4 w-4" />
                  {t('rec.random_mode')}
                </Label>
              </div>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            {t('rec.subtitle')}
            {isRandom && ` ${t('rec.random_now')}`}
          </p>
          
          {recommended.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('rec.no_recommended')}
            </div>
          ) : (
            <div className="space-y-2">
              {recommended.map((rec, index) => (
                <div
                  key={rec.id}
                  className="flex items-center gap-3 p-3 border rounded-lg bg-card"
                >
                  <GripVertical className="h-5 w-5 text-muted-foreground cursor-move" />
                  <span className="text-sm font-medium w-6">{index + 1}</span>
                  
                  <TelegramPhoto 
                    fileId={rec.listing.photo_url} 
                    className="w-16 h-12 object-cover rounded"
                  />
                  
                  <div className="flex-1">
                    <div className="font-medium">{formatPrice(rec.listing.price)}</div>
                    <div className="text-sm text-muted-foreground">
                      {rec.listing.rooms && `${rec.listing.rooms} ${t('rec.rooms')}`}
                      {rec.listing.area && ` • ${rec.listing.area} м²`}
                      {rec.listing.floor && ` • ${rec.listing.floor} ${t('rec.floor')}`}
                    </div>
                  </div>
                  
                  <Badge variant={rec.listing.status === 'active' ? 'default' : 'secondary'}>
                    {rec.listing.status}
                  </Badge>
                  
                  {rec.is_random && (
                    <Badge variant="outline">
                      <Shuffle className="h-3 w-3 mr-1" />
                      {t('rec.random')}
                    </Badge>
                  )}
                  
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemove(rec.id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('rec.available')}</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px]">
            {available.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('rec.no_available')}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {available.map((listing) => (
                  <div
                    key={listing.id}
                    className="border rounded-lg p-3 hover:bg-accent/50 transition-colors"
                  >
                    <TelegramPhoto 
                      fileId={listing.photo_url} 
                      className="w-full h-24 object-cover rounded mb-2"
                    />
                    <div className="font-medium">{formatPrice(listing.price)}</div>
                    <div className="text-sm text-muted-foreground mb-2">
                      {listing.rooms && `${listing.rooms} ${t('rec.rooms')}`}
                      {listing.area && ` • ${listing.area} м²`}
                      {listing.floor && ` • ${listing.floor} ${t('rec.floor')}`}
                    </div>
                    <Button
                      size="sm"
                      className="w-full"
                      onClick={() => handleAdd(listing.id)}
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      {t('common.add')}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
