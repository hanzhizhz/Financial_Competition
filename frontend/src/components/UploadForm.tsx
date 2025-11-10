import { InboxOutlined, AudioOutlined, FileTextOutlined, StopOutlined, DeleteOutlined } from "@ant-design/icons";
import { App, Button, Form, Input, Space, UploadFile, UploadProps } from "antd";
import Dragger from "antd/es/upload/Dragger";
import { useEffect, useState } from "react";
import { transcribeAudio } from "../api/agent";
import { useAudioRecorder } from "../hooks/useAudioRecorder";

export type UploadFormValues = {
  image?: File;
  text?: string;
  remarks?: string;
};

type UploadFormProps = {
  loading?: boolean;
  onSubmit: (values: UploadFormValues) => Promise<void> | void;
};

const UploadForm: React.FC<UploadFormProps> = ({ loading, onSubmit }) => {
  const { message } = App.useApp();
  const [form] = Form.useForm<UploadFormValues>();
  const [imageFile, setImageFile] = useState<File | undefined>();
  const [imagePreview, setImagePreview] = useState<string | undefined>(); // 图片预览 URL
  const [isTranscribing, setIsTranscribing] = useState(false);

  const {
    state: recorderState,
    recordingTime,
    error: recorderError,
    startRecording,
    stopRecording,
    cancelRecording,
    clearError
  } = useAudioRecorder({ sampleRate: 16000, minDurationMs: 1500 });

  const isRecording = recorderState === "recording";
  const isProcessing = recorderState === "processing";

  // 获取文件对象的辅助函数
  const getFileFromUploadFile = (file: UploadFile): File | null => {
    if (file.originFileObj instanceof File) {
      return file.originFileObj;
    }
    // 兼容处理：某些情况下文件可能在其他属性中
    if ((file as any).file instanceof File) {
      return (file as any).file;
    }
    return null;
  };

  // 图片文件变化处理
  const handleImageChange: UploadProps["onChange"] = (info) => {
    const { fileList } = info;
    
    console.log("[UploadForm] 图片文件变化:", {
      fileListLength: fileList.length,
      file: info.file,
      fileStatus: info.file.status
    });

    if (fileList.length === 0) {
      // 清理预览 URL
      if (imagePreview) {
        URL.revokeObjectURL(imagePreview);
        setImagePreview(undefined);
      }
      setImageFile(undefined);
      form.setFieldValue("image", undefined);
      console.log("[UploadForm] 已清空图片文件");
      return;
    }

    const lastFile = fileList[fileList.length - 1];
    const fileObj = getFileFromUploadFile(lastFile);
    
    if (fileObj) {
      console.log("[UploadForm] 成功获取图片文件对象:", {
        name: fileObj.name,
        size: fileObj.size,
        type: fileObj.type
      });
      
      // 清理旧的预览 URL
      if (imagePreview) {
        URL.revokeObjectURL(imagePreview);
      }
      
      // 生成新的预览 URL
      const previewUrl = URL.createObjectURL(fileObj);
      setImagePreview(previewUrl);
      setImageFile(fileObj);
      form.setFieldValue("image", fileObj);
    } else {
      console.warn("[UploadForm] 无法从UploadFile获取File对象:", lastFile);
      message.warning("文件读取失败，请重新选择");
    }
  };

  // 开始录音
  const handleStartRecording = async () => {
    if (isRecording || isProcessing) {
      message.warning("录音准备中，请稍候");
      return;
    }

    if (isTranscribing) {
      message.warning("正在处理上一次录音，请稍后再试");
      return;
    }

    try {
      await startRecording();
      message.success("开始录音...");
      console.log("[UploadForm] 录音开始");
    } catch (error: any) {
      const errorMessage = error?.message || "无法开始录音，请检查麦克风权限";
      console.error("[UploadForm] 开始录音失败:", error);
      message.error(errorMessage);
    }
  };

  // 停止录音
  const handleStopRecording = async () => {
    if (!isRecording) {
      message.warning("当前没有正在进行的录音");
      return;
    }

    if (isProcessing) {
      message.warning("录音数据处理中，请稍后");
      return;
    }

    try {
      const result = await stopRecording();
      if (!result) {
        return;
      }

      console.log("[UploadForm] 录音完成", {
        duration: result.duration,
        byteLength: result.byteLength,
        sampleRate: result.sampleRate,
        fileName: result.file.name
      });

      setIsTranscribing(true);
      message.info("录音已停止，正在转文本...");

      const apiResult = await transcribeAudio(result.file);

      if (apiResult.success && apiResult.text) {
        const currentText = form.getFieldValue("text") || "";
        const newText = currentText ? `${currentText}\n${apiResult.text}` : apiResult.text;
        form.setFieldValue("text", newText);
        message.success("录音已转换为文本");
      } else {
        message.error(apiResult.error || "转文本失败");
      }
    } catch (error: any) {
      console.error("[UploadForm] 停止录音或转文本失败:", error);
      const errorMessage = error?.message || "停止录音失败，请重试";
      message.error(errorMessage);
    } finally {
      setIsTranscribing(false);
    }
  };

  // 格式化录音时间
  const formatRecordingTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (recorderError) {
      message.error(recorderError.message);
      clearError();
    }
  }, [recorderError, clearError, message]);

  useEffect(() => {
    return () => {
      cancelRecording();
      // 清理预览 URL
      if (imagePreview) {
        URL.revokeObjectURL(imagePreview);
      }
    };
  }, [cancelRecording, imagePreview]);

  // 阻止自动上传
  const handleBeforeUpload = (): boolean => {
    return false;
  };

  // 表单提交
  const onFinish = async (values: UploadFormValues) => {
    console.log("[UploadForm] 表单提交开始", {
      hasImage: !!imageFile,
      imageName: imageFile?.name,
      imageSize: imageFile?.size,
      text: values.text,
      remarks: values.remarks
    });
    
    if (!imageFile) {
      message.warning("请先选择票据图片");
      return;
    }

    // 验证文件大小（5MB限制）
    const maxSize = 5 * 1024 * 1024; // 5MB
    if (imageFile.size > maxSize) {
      message.error(`图片文件过大，请选择小于5MB的文件（当前：${(imageFile.size / 1024 / 1024).toFixed(2)}MB）`);
      return;
    }

    try {
      await onSubmit({
        image: imageFile,
        text: values.text,
        remarks: values.remarks
      });
      
      console.log("[UploadForm] 提交成功");
      // 上传成功后不清空图片，保留预览
      // 只重置文本和备注字段
      form.setFieldsValue({
        text: undefined,
        remarks: undefined
      });
    } catch (error) {
      console.error("[UploadForm] 提交表单失败:", error);
      const errorMessage = error instanceof Error ? error.message : "提交失败，请重试";
      message.error(errorMessage);
    }
  };

  // 图片上传组件配置
  const imageProps: UploadProps = {
    name: "image",
    multiple: false,
    accept: "image/*",
    beforeUpload: handleBeforeUpload,
    onChange: handleImageChange,
    onRemove: () => {
      console.log("[UploadForm] 移除图片");
      // 清理预览 URL
      if (imagePreview) {
        URL.revokeObjectURL(imagePreview);
        setImagePreview(undefined);
      }
      setImageFile(undefined);
      form.setFieldValue("image", undefined);
    },
    maxCount: 1,
    // 当有预览时，不显示文件列表，只显示拖拽区域用于替换
    fileList: imagePreview ? [] : (imageFile
      ? [
          {
            uid: `image-${Date.now()}`,
            name: imageFile.name,
            status: "done" as const,
            originFileObj: imageFile
          }
        ]
      : [])
  };

  return (
    <Form layout="vertical" form={form} onFinish={onFinish}>
      <Form.Item
        label="票据图片"
        required
        validateStatus={imageFile ? "success" : undefined}
        help={imageFile ? `已选择：${imageFile.name} (${(imageFile.size / 1024).toFixed(2)} KB)` : "请上传票据图片"}
      >
        {imagePreview ? (
          <div style={{ position: "relative" }}>
            <Dragger
              {...imageProps}
              disabled={loading}
              style={{
                border: "1px dashed #d9d9d9",
                borderRadius: "4px",
                padding: "16px",
                backgroundColor: "#fafafa",
                minHeight: "200px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                position: "relative"
              }}
              showUploadList={false}
            >
              <img
                src={imagePreview}
                alt="票据预览"
                style={{
                  maxWidth: "100%",
                  maxHeight: "400px",
                  objectFit: "contain",
                  pointerEvents: "none"
                }}
              />
              <Button
                type="primary"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  // 清理预览 URL
                  if (imagePreview) {
                    URL.revokeObjectURL(imagePreview);
                    setImagePreview(undefined);
                  }
                  setImageFile(undefined);
                  form.setFieldValue("image", undefined);
                }}
                style={{
                  position: "absolute",
                  top: "8px",
                  right: "8px",
                  zIndex: 10
                }}
                disabled={loading}
              >
                删除
              </Button>
              <div
                style={{
                  position: "absolute",
                  bottom: "8px",
                  left: "50%",
                  transform: "translateX(-50%)",
                  backgroundColor: "rgba(0, 0, 0, 0.6)",
                  color: "white",
                  padding: "4px 12px",
                  borderRadius: "4px",
                  fontSize: "12px",
                  pointerEvents: "none"
                }}
              >
                点击或拖拽图片替换
              </div>
            </Dragger>
          </div>
        ) : (
          <Dragger {...imageProps} disabled={loading}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽图片到此上传</p>
            <p className="ant-upload-hint">支持 JPG/PNG/PDF 等格式，大小建议小于5MB</p>
          </Dragger>
        )}
      </Form.Item>

      <Form.Item label="语音说明（可选）">
        <Space direction="vertical" style={{ width: "100%" }}>
          <Space>
            {!isRecording ? (
              <Button
                type="primary"
                icon={<AudioOutlined />}
                onClick={handleStartRecording}
                disabled={loading || isTranscribing || isProcessing}
              >
                开始录音
              </Button>
            ) : (
              <Button
                danger
                icon={<StopOutlined />}
                onClick={handleStopRecording}
                disabled={loading || isTranscribing || isProcessing}
              >
                停止录音 {formatRecordingTime(recordingTime)}
              </Button>
            )}
            {isTranscribing && <span style={{ color: "#1890ff" }}>正在转文本...</span>}
          </Space>
          <div style={{ fontSize: 12, color: "#666" }}>
            {isRecording 
              ? `正在录音中... ${formatRecordingTime(recordingTime)}`
              : '点击"开始录音"按钮，录音完成后会自动转换为文本并填入下方文本说明'}
          </div>
        </Space>
      </Form.Item>

      <Form.Item name="text" label="文本说明（可选）">
        <Input.TextArea
          placeholder="也可以直接输入票据说明，如分类要求、报销备注等。录音转文本的结果会自动填入此处。"
          rows={4}
          allowClear
          disabled={loading}
        />
      </Form.Item>

      <Form.Item name="remarks" label="备注（可选）">
        <Input
          prefix={<FileTextOutlined />}
          placeholder="例如：项目名称、出差城市等"
          allowClear
          disabled={loading}
        />
      </Form.Item>

      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading}>
          提交识别
        </Button>
      </Form.Item>
    </Form>
  );
};

export default UploadForm;

