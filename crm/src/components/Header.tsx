import { Home, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { clearToken } from "@/lib/api";

interface HeaderProps {
  onLogout?: () => void;
}

export function Header({ onLogout }: HeaderProps) {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearToken();
    onLogout?.();
    navigate("/login");
  };

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
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleLogout}
              className="text-header-foreground/70 hover:text-header-foreground hover:bg-header-foreground/10"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Выйти
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
