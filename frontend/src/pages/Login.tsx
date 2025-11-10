import { useEffect, useState } from "react";
import { Button, Card, Form, Input, Tabs, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { login, register as registerApi } from "../api/agent";
import { useAuth } from "../context/AuthContext";

const { Title, Text } = Typography;

const LoginPage = () => {
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [activeTab, setActiveTab] = useState<"login" | "register">("login");
  const navigate = useNavigate();
  const { login: setAuth, isAuthenticated } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleLogin = async (values: { username: string; password: string }) => {
    try {
      const hide = message.loading("登录中...");
      const data = await login(values.username, values.password);
      hide();
      if (!data?.token) throw new Error("缺少 token");
      setAuth(data.token, { username: data.username ?? values.username });
      message.success("登录成功");
      navigate("/dashboard", { replace: true });
    } catch (error) {
      console.error(error);
      message.error((error as Error).message || "登录失败，请重试");
    }
  };

  const handleRegister = async (values: { username: string; password: string; confirmPassword: string }) => {
    if (values.password !== values.confirmPassword) {
      message.error("两次输入的密码不一致");
      return;
    }
    try {
      const hide = message.loading("注册中...");
      const data = await registerApi(values.username, values.password);
      hide();
      if (!data?.token) throw new Error("注册失败，请重试");
      message.success("注册成功，已自动登录");
      setAuth(data.token, { username: data.username ?? values.username });
      navigate("/dashboard", { replace: true });
    } catch (error) {
      console.error(error);
      message.error((error as Error).message || "注册失败，请重试");
    }
  };

  const handleDemoLogin = () => {
    handleLogin({ username: "123", password: "123" });
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f5f5f5",
        padding: 24
      }}
    >
      <Card style={{ width: 400 }}>
        <Title level={3} style={{ textAlign: "center" }}>
          智能票据管理系统
        </Title>
        <Text type="secondary" style={{ display: "block", textAlign: "center", marginBottom: 32 }}>
          登录后即可使用自动入账与智能分析功能
        </Text>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as "login" | "register")}
          items={[
            {
              key: "login",
              label: "账号登录",
              children: (
                <Form
                  form={loginForm}
                  layout="vertical"
                  onFinish={handleLogin}
                  initialValues={{ username: "", password: "" }}
                >
                  <Form.Item
                    label="用户名"
                    name="username"
                    rules={[{ required: true, message: "请输入用户名" }]}
                  >
                    <Input placeholder="请输入用户名" />
                  </Form.Item>
                  <Form.Item
                    label="密码"
                    name="password"
                    rules={[{ required: true, message: "请输入密码" }]}
                  >
                    <Input.Password placeholder="请输入密码" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block>
                      登录
                    </Button>
                  </Form.Item>
                  <Form.Item>
                    <Button block onClick={handleDemoLogin}>
                      使用演示账号 (123 / 123)
                    </Button>
                  </Form.Item>
                </Form>
              )
            },
            {
              key: "register",
              label: "注册账号",
              children: (
                <Form form={registerForm} layout="vertical" onFinish={handleRegister}>
                  <Form.Item
                    label="用户名"
                    name="username"
                    rules={[{ required: true, message: "请输入用户名" }]}
                  >
                    <Input placeholder="请输入用户名" />
                  </Form.Item>
                  <Form.Item
                    label="密码"
                    name="password"
                    rules={[{ required: true, message: "请输入密码" }]}
                    hasFeedback
                  >
                    <Input.Password placeholder="请输入密码" />
                  </Form.Item>
                  <Form.Item
                    label="确认密码"
                    name="confirmPassword"
                    dependencies={["password"]}
                    rules={[
                      { required: true, message: "请再次输入密码" },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue("password") === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error("两次输入的密码不一致"));
                        }
                      })
                    ]}
                    hasFeedback
                  >
                    <Input.Password placeholder="请再次输入密码" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block>
                      注册并登录
                    </Button>
                  </Form.Item>
                </Form>
              )
            }
          ]}
        />
      </Card>
    </div>
  );
};

export default LoginPage;
