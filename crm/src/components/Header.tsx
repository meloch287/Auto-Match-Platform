import { Home, LogOut, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useNavigate } from "react-router-dom";
import { clearToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface HeaderProps {
  onLogout?: () => void;
}

const languages = [
  { code: 'az' as const, name: '🇦🇿 Azərbaycan' },
  { code: 'ru' as const, name: '🇷🇺 Русский' },
  { code: 'en' as const, name: '🇬🇧 English' },
];

export function Header({ onLogout }: HeaderProps) {
  const navigate = useNavigate();
  const { language, setLanguage, t } = useI18n();

  const handleLogout = () => {
    clearToken();
    onLogout?.();
    navigate("/login");
  };

  const currentLang = languages.find(l => l.code === language);

  return (
    <header className="bg-header text-header-foreground border-b border-border/10">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-primary to-accent">
              <Home className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight">AutoMatch</span>
              <span className="text-xs ml-2 px-2 py-0.5 rounded-full bg-primary/20 text-primary-foreground/80">Admin</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="sm"
                  className="text-header-foreground/70 hover:text-header-foreground hover:bg-header-foreground/10"
                >
                  <Globe className="w-4 h-4 mr-2" />
                  {currentLang?.name.split(' ')[0]}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {languages.map((lang) => (
                  <DropdownMenuItem
                    key={lang.code}
                    onClick={() => setLanguage(lang.code)}
                    className={language === lang.code ? 'bg-accent' : ''}
                  >
                    {lang.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleLogout}
              className="text-header-foreground/70 hover:text-header-foreground hover:bg-header-foreground/10"
            >
              <LogOut className="w-4 h-4 mr-2" />
              {t('header.logout')}
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
