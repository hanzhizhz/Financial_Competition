import { Layout, Menu, theme, Button } from "antd";
import {
  DashboardOutlined,
  UploadOutlined,
  LogoutOutlined,
  SettingOutlined
} from "@ant-design/icons";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useMemo, useState } from "react";
import UploadPage from "./pages/Upload";
import DashboardPage from "./pages/Dashboard";
import LoginPage from "./pages/Login";
import { useAuth } from "./context/AuthContext";
import RoleSettings from "./components/RoleSettings";

const { Header, Content, Sider } = Layout;

type RouteKey = "dashboard" | "upload";

const AppLayout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    token: { colorBgContainer }
  } = theme.useToken();
  const { logout, userInfo } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const selectedKey = useMemo<RouteKey>(() => {
    if (location.pathname.startsWith("/upload")) return "upload";
    return "dashboard";
  }, [location.pathname]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth="0" style={{ display: "flex", flexDirection: "column" }}>
        <div style={{
          height: 64,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontWeight: 600,
          fontSize: 18
        }}>
          智能票据
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          onClick={async ({ key }) => {
            if (key === "logout") {
              await logout();
              navigate("/login");
              return;
            }
            navigate(key as string);
          }}
          items={[
            { key: "dashboard", icon: <DashboardOutlined />, label: "数据概览" },
            { key: "upload", icon: <UploadOutlined />, label: "自动入账" },
            { key: "logout", icon: <LogoutOutlined />, label: "退出登录" }
          ]}
          style={{ flex: 1 }}
        />
        <div style={{
          padding: "16px",
          borderTop: "1px solid rgba(255, 255, 255, 0.1)"
        }}>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={() => setSettingsOpen(true)}
            style={{
              width: "100%",
              color: "#fff",
              textAlign: "left",
              height: "auto",
              padding: "8px 12px"
            }}
          >
            角色设置
          </Button>
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            padding: "0 24px",
            background: colorBgContainer,
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end"
          }}
        >
          <span style={{ color: "#999" }}>{userInfo?.username ?? "用户"}</span>
        </Header>
        <Content style={{ margin: "24px 16px" }}>
          <div style={{
            padding: 24,
            minHeight: 360,
            background: colorBgContainer,
            borderRadius: 12
          }}>
            {children}
          </div>
        </Content>
      </Layout>
      <RoleSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </Layout>
  );
};

const App = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          isAuthenticated ? (
            <AppLayout>
              <Routes>
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="*" element={<Navigate to="dashboard" replace />} />
              </Routes>
            </AppLayout>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
};

export default App;
