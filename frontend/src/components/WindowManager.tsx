import { App, Button, Card, Space, Tag, Typography } from "antd";
import { CloseOutlined, CheckCircleOutlined, ClockCircleOutlined, PlusOutlined } from "@ant-design/icons";
import type { InvoiceWindow } from "../types/window";

const { Text } = Typography;

type WindowManagerProps = {
  /** 窗口列表 */
  windows: InvoiceWindow[];
  /** 当前选中的窗口ID */
  activeWindowId: string | null;
  /** 切换窗口回调 */
  onSwitchWindow: (windowId: string) => void;
  /** 删除窗口回调 */
  onDeleteWindow: (windowId: string) => void;
  /** 创建新窗口回调 */
  onCreateWindow?: () => void;
};

const WindowManager: React.FC<WindowManagerProps> = ({
  windows,
  activeWindowId,
  onSwitchWindow,
  onDeleteWindow,
  onCreateWindow,
}) => {
  const { modal } = App.useApp();

  // 获取窗口状态标签
  const getWindowStatus = (window: InvoiceWindow) => {
    if (window.confirming) {
      return { text: "确认中", color: "processing" as const };
    }
    if (window.loading) {
      return { text: "处理中", color: "processing" as const };
    }
    if (window.result?.success && window.sessionId) {
      return { text: "待确认", color: "warning" as const };
    }
    if (window.result?.success) {
      return { text: "已确认", color: "success" as const };
    }
    if (window.result && !window.result.success) {
      return { text: "识别失败", color: "error" as const };
    }
    return { text: "准备中", color: "default" as const };
  };

  // 处理删除窗口
  const handleDelete = (window: InvoiceWindow, e: React.MouseEvent) => {
    e.stopPropagation();
    modal.confirm({
      title: "确认删除窗口",
      content: `确定要删除窗口"${window.title}"吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: () => {
        onDeleteWindow(window.id);
      },
    });
  };

  return (
    <Card 
      title={
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>窗口管理 ({windows.length})</span>
          {onCreateWindow && (
            <Button
              type="primary"
              size="small"
              icon={<PlusOutlined />}
              onClick={onCreateWindow}
            >
              新建窗口
            </Button>
          )}
        </div>
      }
      size="small" 
      style={{ marginBottom: 16 }}
    >
      {windows.length === 0 ? (
        <div style={{ textAlign: "center", padding: "24px 0" }}>
          <Text type="secondary">暂无窗口</Text>
          {onCreateWindow && (
            <div style={{ marginTop: 12 }}>
              <Button type="primary" icon={<PlusOutlined />} onClick={onCreateWindow}>
                创建第一个窗口
              </Button>
            </div>
          )}
        </div>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }} size="small">
        {windows.map((window) => {
          const isActive = window.id === activeWindowId;
          const status = getWindowStatus(window);

          return (
            <Card
              key={window.id}
              size="small"
              hoverable
              onClick={() => onSwitchWindow(window.id)}
              style={{
                cursor: "pointer",
                border: isActive ? "2px solid #1890ff" : "1px solid #d9d9d9",
                backgroundColor: isActive ? "#f0f7ff" : "#fff",
                transition: "all 0.2s",
              }}
              bodyStyle={{ padding: "12px" }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 4,
                    }}
                  >
                    <Text
                      strong={isActive}
                      ellipsis
                      style={{
                        fontSize: 14,
                        color: isActive ? "#1890ff" : undefined,
                      }}
                    >
                      {window.title}
                    </Text>
                    <Tag
                      color={status.color}
                      icon={
                        status.color === "success" ? (
                          <CheckCircleOutlined />
                        ) : (
                          <ClockCircleOutlined />
                        )
                      }
                      style={{ margin: 0 }}
                    >
                      {status.text}
                    </Tag>
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {new Date(window.createdAt).toLocaleString("zh-CN", {
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </Text>
                </div>
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={(e) => handleDelete(window, e)}
                  style={{ flexShrink: 0 }}
                />
              </div>
            </Card>
          );
        })}
        </Space>
      )}
    </Card>
  );
};

export default WindowManager;

