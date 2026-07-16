import { createBrowserRouter, Navigate } from "react-router";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Recovery from "./pages/Recovery";
import AppLayout from "./shared/components/AppLayout";
import Dashboard from "./pages/Dashboard";
import HealthProfile from "./pages/HealthProfile";
import MonthlyHealth from "./pages/MonthlyHealth";
import HealthCheckup from "./pages/HealthCheckup";
import BloodSugar from "./pages/BloodSugar";
import AIAnalysis from "./pages/AIAnalysis";
import AIReport from "./pages/AIReport";
import Challenge from "./pages/Challenge";
import MyPage from "./pages/MyPage";
import NotificationSettings from "./pages/NotificationSettings";
import Withdraw from "./pages/Withdraw";

export const router = createBrowserRouter([
  { path: "/",          Component: Landing },
  { path: "/login",     Component: Login },
  { path: "/signup",    Component: Signup },
  { path: "/recovery",  Component: Recovery },
  {
    path: "/app",
    Component: AppLayout,
    children: [
      { index: true,              Component: Dashboard },
      { path: "dashboard",        Component: Dashboard },
      { path: "health/profile",   Component: HealthProfile },
      { path: "health/monthly",   Component: MonthlyHealth },
      { path: "health/checkup",   Component: HealthCheckup },
      { path: "health/blood-sugar", Component: BloodSugar },
      { path: "ai/analysis",      Component: AIAnalysis },
      { path: "ai/report",        Component: AIReport },
      { path: "challenge",        Component: Challenge },
      { path: "mypage",           Component: MyPage },
      { path: "settings/notifications", Component: NotificationSettings },
      { path: "withdraw",         Component: Withdraw },
    ],
  },
]);
