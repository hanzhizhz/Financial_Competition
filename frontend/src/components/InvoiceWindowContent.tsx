import { App, Button, Card, Progress, Space } from "antd";
import { useState, useCallback } from "react";
import UploadForm, { UploadFormValues } from "./UploadForm";
import RecognitionResult, { ClassificationModifications } from "./RecognitionResult";
import { confirmDocument, uploadDocument } from "../api/agent";
import type { UploadResponse } from "../types";

type InvoiceWindowContentProps = {
  /** 窗口ID */
  windowId: string;
  /** 窗口标题 */
  title: string;
  /** 上传回调，用于更新窗口状态 */
  onUploadStart?: (windowId: string) => void;
  /** 上传进度回调 */
  onUploadProgress?: (windowId: string, progress: number) => void;
  /** 上传完成回调 */
  onUploadComplete?: (windowId: string, result: UploadResponse, sessionId: string | null) => void;
  /** 上传失败回调 */
  onUploadError?: (windowId: string, error: string) => void;
  /** 确认完成回调 */
  onConfirmComplete?: (windowId: string) => void;
  /** 标题更新回调 */
  onTitleUpdate?: (windowId: string, title: string) => void;
};

const InvoiceWindowContent: React.FC<InvoiceWindowContentProps> = ({
  windowId,
  title,
  onUploadStart,
  onUploadProgress,
  onUploadComplete,
  onUploadError,
  onConfirmComplete,
  onTitleUpdate,
  onModificationsChange,
}) => {
  const { message, modal } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [modifications, setModifications] = useState<ClassificationModifications | null>(null);

  const handleSubmit = async ({ image, text, remarks }: UploadFormValues) => {
    try {
      console.log(`[窗口 ${windowId}] handleSubmit 被调用`, { image, text, remarks });
      
      if (!image) {
        message.warning("请先选择票据图片");
        return;
      }
      
      // 更新窗口标题为文件名
      const windowTitle = image.name || `票据-${new Date().toLocaleString("zh-CN")}`;
      if (onTitleUpdate) {
        onTitleUpdate(windowId, windowTitle);
      }
      
      console.log("准备构建 FormData...");
      const formData = new FormData();
      formData.append("image", image);
      if (text) {
        formData.append("text", text);
        console.log("添加文本:", text);
      }
      if (remarks) {
        formData.append("remarks", remarks);
        console.log("添加备注:", remarks);
      }
      
      console.log("开始上传，调用 uploadDocument...");
      setLoading(true);
      setUploadProgress(0);
      if (onUploadStart) {
        onUploadStart(windowId);
      }
      message.info("正在上传图片，请稍候...");
      
      const data: UploadResponse = await uploadDocument(formData, (progressEvent) => {
        const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
        setUploadProgress(percent);
        if (onUploadProgress) {
          onUploadProgress(windowId, percent);
        }
        console.log(`[窗口 ${windowId}] 上传进度: ${percent}%`);
      });
      
      // 确保进度条显示100%
      setUploadProgress(100);
      if (onUploadProgress) {
        onUploadProgress(windowId, 100);
      }
      
      console.log(`[窗口 ${windowId}] 收到服务器响应:`, data);
      
      if (!data) {
        throw new Error("服务器返回空响应");
      }
      
      setResult(data);
      const currentSessionId = data.sessionId || null;
      setSessionId(currentSessionId);
      setModifications(null);
      
      if (onUploadComplete) {
        onUploadComplete(windowId, data, currentSessionId);
      }
      
      if (data.success) {
        message.success("识别完成，请确认结果");
        // 成功时延迟重置进度条，让用户看到100%
        setTimeout(() => {
          setUploadProgress(0);
          if (onUploadProgress) {
            onUploadProgress(windowId, 0);
          }
        }, 1500);
      } else {
        message.error(data.error || "识别失败");
      }
    } catch (error) {
      console.error(`[窗口 ${windowId}] 上传失败:`, error);
      let errorMessage = "上传失败，请重试";
      
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null) {
        const axiosError = error as any;
        if (axiosError.response) {
          errorMessage = `服务器错误: ${axiosError.response.status} - ${axiosError.response.data?.error || axiosError.response.statusText}`;
        } else if (axiosError.request) {
          errorMessage = "网络错误，请检查网络连接";
        } else {
          errorMessage = axiosError.message || errorMessage;
        }
      }
      
      message.error(errorMessage);
      setResult({
        success: false,
        error: errorMessage
      });
      setLoading(false);
      setUploadProgress(0);
      if (onUploadError) {
        onUploadError(windowId, errorMessage);
      }
      if (onUploadProgress) {
        onUploadProgress(windowId, 0);
      }
    } finally {
      setLoading(false);
      console.log(`[窗口 ${windowId}] 上传流程结束`);
    }
  };

  const handleConfirm = async () => {
    if (!sessionId) return;
    
    try {
      setConfirming(true);
      const modificationsToSend = modifications || undefined;
      console.log(`[窗口 ${windowId}] 提交确认，修改内容:`, modificationsToSend);
      const response = await confirmDocument(sessionId, modificationsToSend);
      if (response.success) {
        modal.success({
          title: "票据已确认",
          content: "系统会根据该票据更新统计数据和规则。"
        });
        setSessionId(null);
        setModifications(null);
        if (onConfirmComplete) {
          onConfirmComplete(windowId);
        }
      } else {
        throw new Error(response.error || "确认失败");
      }
    } catch (error) {
      console.error(`[窗口 ${windowId}] 确认失败:`, error);
      modal.error({
        title: "确认失败",
        content: (error as Error).message || "请稍后再试"
      });
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div>
      <Card title={title} size="small" style={{ marginBottom: 16 }}>
        <UploadForm loading={loading} onSubmit={handleSubmit} />
        {(loading || uploadProgress > 0) && (
          <div style={{ marginTop: 16 }}>
            <Progress 
              percent={uploadProgress >= 100 ? 100 : uploadProgress} 
              status={loading && uploadProgress >= 100 ? "active" : uploadProgress === 100 ? "success" : "active"}
              showInfo={true}
              format={(percent) => {
                if (loading && percent >= 100) {
                  return "处理中...";
                }
                if (percent === 100) {
                  return "上传完成";
                }
                return `上传中 ${percent}%`;
              }}
            />
          </div>
        )}
      </Card>
      
      <RecognitionResult 
        loading={loading} 
        result={result}
        onModificationsChange={(modifications) => {
          setModifications(modifications);
          if (onModificationsChange) {
            onModificationsChange(windowId, modifications);
          }
        }}
      />
      
      <Space style={{ marginTop: 16, marginBottom: 0 }}>
        <Button
          type="primary"
          disabled={!sessionId || confirming}
          loading={confirming}
          onClick={handleConfirm}
        >
          确认入账
        </Button>
        <Button
          disabled={!result}
          onClick={() => {
            setResult(null);
            setSessionId(null);
            setModifications(null);
          }}
        >
          清空结果
        </Button>
      </Space>
    </div>
  );
};

export default InvoiceWindowContent;

