import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router";
import {
  Heart, ClipboardList, UserCircle, CalendarDays, Microscope, Droplet,
  Brain, FileText, Target, ChevronDown, LogOut, Menu, X, Bell, UserX, Settings,
  LayoutDashboard, PanelLeftClose, PanelLeftOpen,
} from "lucide-react";
import { getUser, logout, isAuthenticated } from "../api/auth";
import { getHealthProfile, HealthProfile } from "../api/healthProfileApi";

const cn = (...cls: (string | boolean | undefined)[]) => cls.filter(Boolean).join(" ");

/* ── Avatar ── */
function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  const initials = name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div
      className="rounded-full flex items-center justify-center font-semibold text-white flex-shrink-0"
      style={{ width: size, height: size, fontSize: size * 0.36, backgroundColor: "#10B981" }}
    >
      {initials}
    </div>
  );
}

/* ── Menu config ── */
interface MenuItem { label: string; path: string; icon: React.ElementType }
interface MenuGroup { id: string; label: string; icon: React.ElementType; items?: MenuItem[]; path?: string }

function getMenuConfig(hasDiabetes: boolean): MenuGroup[] {
  const healthItems: MenuItem[] = [
    { label: "건강 프로필",    path: "/app/health/profile",  icon: UserCircle },
    { label: "월별 건강설문",  path: "/app/health/monthly",  icon: CalendarDays },
    { label: "건강검진 기록",  path: "/app/health/checkup",  icon: Microscope },
  ];

  // 당뇨병 환자일 경우에만 혈당 측정 기록 메뉴 추가
  if (hasDiabetes) {
    healthItems.push({ label: "혈당 측정 기록", path: "/app/health/blood-sugar", icon: Droplet });
  }

  return [
    {
      id: "dashboard",
      label: "대시보드",
      icon: LayoutDashboard,
      path: "/app/dashboard",
    },
    {
      id: "health",
      label: "건강정보 기록",
      icon: ClipboardList,
      items: healthItems,
    },
    {
      id: "ai",
      label: "AI",
      icon: Brain,
      items: [
        { label: "AI 위험도 분석", path: "/app/ai/analysis", icon: Brain },
        { label: "AI 건강리포트",  path: "/app/ai/report",   icon: FileText },
      ],
    },
    {
      id: "challenge",
      label: "건강 챌린지",
      icon: Target,
      items: [
        { label: "건강 챌린지", path: "/app/challenge", icon: Target },
      ],
    },
    {
      id: "mypage",
      label: "마이페이지",
      icon: UserCircle,
      path: "/app/mypage",
    },
    {
      id: "settings",
      label: "설정",
      icon: Settings,
      items: [
        { label: "알림 설정", path: "/app/settings/notifications", icon: Bell },
      ],
    },
  ];
}

/* ── Sidebar content ── */
function SidebarContent({ onNavigate, collapsed, onToggleCollapse }: {
  onNavigate?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  const navigate   = useNavigate();
  const location   = useLocation();
  const user       = getUser();
  const displayName = user?.nickname || user?.email || "사용자";

  const [healthProfile, setHealthProfile] = useState<HealthProfile | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);

  // Load health profile to check diabetes status
  useEffect(() => {
    const loadProfile = async () => {
      try {
        const profile = await getHealthProfile();
        setHealthProfile(profile);
      } catch (err) {
        console.error("Failed to load health profile:", err);
      } finally {
        setLoadingProfile(false);
      }
    };
    loadProfile();
  }, []);

  const MENU = getMenuConfig(healthProfile?.has_diabetes ?? false);

  // auto-open the group that contains the active path
  const initialOpen = MENU.reduce<Record<string, boolean>>((acc, g) => {
    acc[g.id] = g.items?.some((item) => location.pathname.startsWith(item.path)) ?? false;
    return acc;
  }, {});
  // always open dashboard group by default
  if (!Object.values(initialOpen).some(Boolean)) initialOpen["dashboard"] = true;

  const [open, setOpen] = useState<Record<string, boolean>>(initialOpen);

  const toggle = (id: string) => {
    if (collapsed) return; // Don't toggle when collapsed
    setOpen((o) => ({ ...o, [id]: !o[id] }));
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (loadingProfile) {
    return (
      <div className="flex flex-col h-full" style={{ backgroundColor: "#0B1628" }}>
        <div className="flex items-center justify-center h-full">
          <div className="text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>로딩 중...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: "#0B1628" }}>
      {/* Logo */}
      <div
        className="border-b flex items-center justify-center overflow-hidden"
        style={{
          borderColor: "rgba(255,255,255,0.07)",
          height: "68px",
          paddingLeft: collapsed ? "0" : "20px",
          paddingRight: collapsed ? "0" : "20px",
          transition: "padding 0.3s ease",
        }}
      >
        {collapsed ? (
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: "#10B981" }}>
            <Heart size={17} className="text-white" />
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center flex-shrink-0">
              <Heart size={15} className="text-white" />
            </div>
            <span className="font-bold text-base text-white" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>
              VitalAI
            </span>
          </div>
        )}
      </div>

      {/* User profile */}
      {!collapsed && (
        <div className="px-4 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
          <div className="flex items-center gap-3 px-2 py-2.5 rounded-xl" style={{ backgroundColor: "rgba(255,255,255,0.05)" }}>
            <Avatar name={displayName} size={36} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-white truncate">{user?.nickname || user?.name || "사용자"}</div>
              <div className="text-xs truncate mt-0.5" style={{ color: "rgba(255,255,255,0.4)", fontFamily: "JetBrains Mono" }}>
                {user?.email}
              </div>
            </div>
          </div>
        </div>
      )}

      {collapsed && (
        <div className="py-4 border-b flex items-center justify-center" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
          <Avatar name={displayName} size={36} />
        </div>
      )}

      {/* Menu */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
        {MENU.map((group) => {
          const GroupIcon = group.icon;

          // Single menu item (no sub-items)
          if (group.path) {
            return (
              <NavLink
                key={group.id}
                to={group.path}
                onClick={onNavigate}
                title={collapsed ? group.label : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex items-center rounded-lg text-sm font-medium transition-all duration-150",
                    collapsed ? "justify-center px-3 py-3" : "gap-3 px-3 py-2.5",
                    isActive ? "text-white" : "hover:bg-white/5"
                  )
                }
                style={({ isActive }) => ({
                  color: isActive ? "#10B981" : "rgba(255,255,255,0.55)",
                  backgroundColor: isActive ? "rgba(16,185,129,0.1)" : undefined,
                })}
              >
                {({ isActive }) => (
                  <>
                    <GroupIcon size={17} style={{ color: isActive ? "#10B981" : "rgba(255,255,255,0.4)" }} />
                    {!collapsed && group.label}
                  </>
                )}
              </NavLink>
            );
          }

          // Group with sub-items
          const isGroupActive = group.items?.some((item) => location.pathname.startsWith(item.path)) ?? false;
          const isOpen = open[group.id];

          // In collapsed mode, show only the icon for groups (no expansion)
          if (collapsed) {
            // Find the active item in this group if any
            const activeItem = group.items?.find((item) => location.pathname.startsWith(item.path));
            if (activeItem) {
              const ActiveIcon = activeItem.icon;
              return (
                <NavLink
                  key={group.id}
                  to={activeItem.path}
                  onClick={onNavigate}
                  title={activeItem.label}
                  className="flex items-center justify-center px-3 py-3 rounded-lg text-sm font-medium transition-all duration-150"
                  style={{
                    color: "#10B981",
                    backgroundColor: "rgba(16,185,129,0.1)",
                  }}
                >
                  <ActiveIcon size={17} style={{ color: "#10B981" }} />
                </NavLink>
              );
            } else {
              // Show group icon when no active item
              return (
                <button
                  key={group.id}
                  title={group.label}
                  className="flex items-center justify-center px-3 py-3 rounded-lg text-sm font-medium transition-all duration-150 hover:bg-white/5"
                  style={{ color: "rgba(255,255,255,0.55)" }}
                >
                  <GroupIcon size={17} style={{ color: "rgba(255,255,255,0.4)" }} />
                </button>
              );
            }
          }

          return (
            <div key={group.id}>
              {/* Group header */}
              <button
                onClick={() => toggle(group.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  isGroupActive ? "text-white" : "hover:bg-white/5"
                )}
                style={{ color: isGroupActive ? "#fff" : "rgba(255,255,255,0.55)" }}
              >
                <GroupIcon size={17} style={{ color: isGroupActive ? "#10B981" : "rgba(255,255,255,0.4)" }} />
                <span className="flex-1 text-left">{group.label}</span>
                <ChevronDown
                  size={14}
                  className="transition-transform duration-200"
                  style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)", color: "rgba(255,255,255,0.3)" }}
                />
              </button>

              {/* Sub items */}
              {isOpen && (
                <div className="ml-3 pl-4 mt-0.5 mb-1 flex flex-col gap-0.5" style={{ borderLeft: "1px solid rgba(255,255,255,0.08)" }}>
                  {group.items?.map((item) => {
                    const ItemIcon = item.icon;
                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        onClick={onNavigate}
                        className={({ isActive }) =>
                          cn(
                            "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150",
                            isActive ? "font-semibold" : "hover:bg-white/5 font-normal"
                          )
                        }
                        style={({ isActive }) => ({
                          color: isActive ? "#10B981" : "rgba(255,255,255,0.5)",
                          backgroundColor: isActive ? "rgba(16,185,129,0.1)" : undefined,
                        })}
                      >
                        {({ isActive }) => (
                          <>
                            <ItemIcon size={15} style={{ color: isActive ? "#10B981" : "rgba(255,255,255,0.35)" }} />
                            {item.label}
                          </>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Collapse Toggle & Logout */}
      <div className="px-3 py-4 border-t flex flex-col gap-1" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            title={collapsed ? "메뉴 펼치기" : "메뉴 접기"}
            className={cn(
              "w-full flex items-center rounded-lg text-sm transition-colors hover:bg-white/5",
              collapsed ? "justify-center px-3 py-3" : "gap-3 px-3 py-2.5"
            )}
            style={{ color: "rgba(255,255,255,0.4)" }}
          >
            {collapsed ? <PanelLeftOpen size={17} /> : <><PanelLeftClose size={16} />메뉴 접기</>}
          </button>
        )}

        <button
          onClick={handleLogout}
          title={collapsed ? "로그아웃" : undefined}
          className={cn(
            "w-full flex items-center rounded-lg text-sm transition-colors hover:bg-white/5",
            collapsed ? "justify-center px-3 py-3" : "gap-3 px-3 py-2.5"
          )}
          style={{ color: "rgba(255,255,255,0.4)" }}
        >
          <LogOut size={16} />
          {!collapsed && "로그아웃"}
        </button>

        <NavLink
          to="/app/withdraw"
          onClick={onNavigate}
          title={collapsed ? "회원 탈퇴" : undefined}
          className={cn(
            "w-full flex items-center rounded-lg text-sm transition-colors hover:bg-white/5",
            collapsed ? "justify-center px-3 py-2.5" : "gap-3 px-3 py-2"
          )}
          style={{ color: "rgba(239,68,68,0.5)" }}
        >
          <UserX size={15} />
          {!collapsed && "회원 탈퇴"}
        </NavLink>
      </div>
    </div>
  );
}

/* ── Main layout ── */
export default function AppLayout() {
  const navigate  = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const user = getUser();

  // Auth guard
  useEffect(() => {
    if (!isAuthenticated()) navigate("/login", { replace: true });
  }, []);

  if (!isAuthenticated()) return null;

  const displayName = user?.nickname || user?.name || "사용자";

  return (
    <div className="flex h-screen overflow-hidden bg-background" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Desktop sidebar */}
      <aside
        className="hidden lg:flex flex-col flex-shrink-0 h-full overflow-hidden"
        style={{
          width: collapsed ? "80px" : "256px",
          transition: "width 0.3s ease",
        }}
      >
        <SidebarContent collapsed={collapsed} onToggleCollapse={() => setCollapsed(!collapsed)} />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="relative z-50 flex flex-col w-72 h-full overflow-hidden shadow-2xl">
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="flex-shrink-0 h-14 flex items-center justify-between px-6 border-b border-border bg-background">
          {/* Left: Mobile menu or Branding when collapsed */}
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden p-1.5 rounded-lg hover:bg-muted text-muted-foreground transition-colors"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={20} />
            </button>

            {/* Show branding when sidebar is collapsed */}
            {collapsed && (
              <div className="hidden lg:flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: "#10B981" }}>
                  <Heart size={13} className="text-white" />
                </div>
                <span className="font-bold text-base" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em", color: "#0B1628" }}>
                  VitalAI
                </span>
              </div>
            )}
          </div>

          {/* Right: Notifications & User */}
          <div className="flex items-center gap-3">
            <button className="p-2 rounded-lg hover:bg-muted text-muted-foreground transition-colors relative">
              <Bell size={17} />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#10B981" }} />
            </button>
            <div className="flex items-center gap-2.5">
              <Avatar name={displayName} size={30} />
              <span className="hidden sm:block text-sm font-medium text-foreground">{displayName}</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
