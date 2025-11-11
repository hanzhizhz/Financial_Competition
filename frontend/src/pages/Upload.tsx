import { App, Row, Col } from "antd";
import { useState, useCallback } from "react";
import WindowManager from "../components/WindowManager";
import InvoiceWindowContent from "../components/InvoiceWindowContent";
import type { ClassificationModifications } from "../components/RecognitionResult";
import type { UploadResponse } from "../types";
import type { InvoiceWindow } from "../types/window";

// 生成初始窗口ID（在组件外部，确保稳定）
const getInitialWindowId = () => `window-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

const UploadPage = () => {
  const { message } = App.useApp();
  
  // 初始化第一个窗口
  const [windows, setWindows] = useState<InvoiceWindow[]>(() => {
    const windowId = getInitialWindowId();
    const firstWindow: InvoiceWindow = {
      id: windowId,
      title: "窗口-1",
      sessionId: null,
      result: null,
      modifications: null,
      loading: false,
      confirming: false,
      uploadProgress: 0,
      createdAt: Date.now(),
    };
    // 将窗口ID存储到sessionStorage，用于初始化activeWindowId
    sessionStorage.setItem('initialWindowId', windowId);
    return [firstWindow];
  });
  
  // 当前选中的窗口ID，初始化为第一个窗口
  const [activeWindowId, setActiveWindowId] = useState<string | null>(() => {
    const initialId = sessionStorage.getItem('initialWindowId');
    sessionStorage.removeItem('initialWindowId'); // 清理
    return initialId;
  });

  // 获取当前活动窗口
  const activeWindow = windows.find((w) => w.id === activeWindowId) || null;

  // 创建新窗口
  const createWindow = useCallback((title?: string): string => {
    const windowId = `window-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const windowTitle = title || `新窗口-${windows.length + 1}`;
    const newWindow: InvoiceWindow = {
      id: windowId,
      title: windowTitle,
      sessionId: null,
      result: null,
      modifications: null,
      loading: false,
      confirming: false,
      uploadProgress: 0,
      createdAt: Date.now(),
    };
    setWindows((prev) => [...prev, newWindow]);
    setActiveWindowId(windowId);
    return windowId;
  }, [windows.length]);

  // 更新窗口状态
  const updateWindow = useCallback(
    (windowId: string, updates: Partial<InvoiceWindow>) => {
      setWindows((prev) =>
        prev.map((w) => (w.id === windowId ? { ...w, ...updates } : w))
      );
    },
    []
  );

  // 处理上传开始
  const handleUploadStart = useCallback((windowId: string) => {
    updateWindow(windowId, { loading: true, uploadProgress: 0 });
  }, [updateWindow]);

  // 处理上传进度
  const handleUploadProgress = useCallback((windowId: string, progress: number) => {
    updateWindow(windowId, { uploadProgress: progress });
  }, [updateWindow]);

  // 处理上传完成
  const handleUploadComplete = useCallback((windowId: string, result: UploadResponse, sessionId: string | null) => {
    updateWindow(windowId, {
      result,
      sessionId,
      modifications: null,
      loading: false,
    });
  }, [updateWindow]);

  // 处理上传错误
  const handleUploadError = useCallback((windowId: string, error: string) => {
    updateWindow(windowId, {
      result: {
        success: false,
        error
      },
      loading: false,
      uploadProgress: 0,
    });
  }, [updateWindow]);

  // 处理确认完成
  const handleConfirmComplete = useCallback((windowId: string) => {
    updateWindow(windowId, {
      sessionId: null,
      modifications: null,
      confirming: false,
    });
  }, [updateWindow]);

  // 处理标题更新
  const handleTitleUpdate = useCallback((windowId: string, title: string) => {
    updateWindow(windowId, { title });
  }, [updateWindow]);

  // 处理分类修改变化
  const handleModificationsChange = useCallback((windowId: string, modifications: ClassificationModifications | null) => {
    updateWindow(windowId, { modifications });
  }, [updateWindow]);

  // 删除窗口
  const handleDeleteWindow = useCallback((windowId: string) => {
    setWindows((prev) => {
      const newWindows = prev.filter((w) => w.id !== windowId);
      // 如果删除的是当前活动窗口，切换到其他窗口或清空
      setActiveWindowId((prevActiveId) => {
        if (windowId === prevActiveId) {
          if (newWindows.length > 0) {
            return newWindows[0].id;
          } else {
            return null;
          }
        }
        return prevActiveId;
      });
      return newWindows;
    });
  }, []);

  // 切换窗口
  const handleSwitchWindow = useCallback((windowId: string) => {
    setActiveWindowId(windowId);
  }, []);

  // 创建空白窗口
  const handleCreateWindow = useCallback(() => {
    createWindow();
  }, [createWindow]);

  return (
    <Row gutter={[24, 24]}>
      <Col xs={24} lg={8}>
        <WindowManager
          windows={windows}
          activeWindowId={activeWindowId}
          onSwitchWindow={handleSwitchWindow}
          onDeleteWindow={handleDeleteWindow}
          onCreateWindow={handleCreateWindow}
        />
      </Col>
      <Col xs={24} lg={16}>
        {windows.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "#999" }}>
            <p style={{ fontSize: 16, marginBottom: 16 }}>请选择一个窗口或创建新窗口</p>
            <p style={{ fontSize: 14 }}>点击左侧"新建窗口"按钮创建空白窗口，然后在窗口内上传票据</p>
          </div>
        ) : (
          <>
            {windows.map((window) => (
              <div
                key={window.id}
                style={{ display: window.id === activeWindowId ? 'block' : 'none' }}
              >
                <InvoiceWindowContent
                  windowId={window.id}
                  title={window.title}
                  onUploadStart={handleUploadStart}
                  onUploadProgress={handleUploadProgress}
                  onUploadComplete={handleUploadComplete}
                  onUploadError={handleUploadError}
                  onConfirmComplete={handleConfirmComplete}
                  onTitleUpdate={handleTitleUpdate}
                  onModificationsChange={handleModificationsChange}
                  controlledResult={window.result}
                  controlledSessionId={window.sessionId}
                  controlledModifications={window.modifications}
                />
              </div>
            ))}
          </>
        )}
      </Col>
    </Row>
  );
};

export default UploadPage;
