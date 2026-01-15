import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { RecoilRoot, useRecoilValue, useSetRecoilState } from "recoil";
import { authState } from "./state/atoms";
import { mockAuthService } from "./services/auth/mockAuth";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { UpdatesProvider } from "./features/updates/UpdatesProvider";
import { LoadingSpinner } from "./components/ui";

function AppRoutes() {
  const auth = useRecoilValue(authState);
  const setAuth = useSetRecoilState(authState);

  useEffect(() => {
    const initializeAuth = async () => {
      const state = await mockAuthService.initialize();
      setAuth(state);
    };
    initializeAuth();
  }, [setAuth]);

  if (auth.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          auth.isAuthenticated ? <Navigate to="/dashboard" /> : <LoginPage />
        }
      />
      <Route
        path="/dashboard"
        element={
          auth.isAuthenticated ? <DashboardPage /> : <Navigate to="/login" />
        }
      />
      <Route
        path="/profile"
        element={
          auth.isAuthenticated ? <ProfilePage /> : <Navigate to="/login" />
        }
      />
      <Route path="/" element={<Navigate to="/dashboard" />} />
    </Routes>
  );
}

function App() {
  return (
    <RecoilRoot>
      <UpdatesProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </UpdatesProvider>
    </RecoilRoot>
  );
}

export default App;
