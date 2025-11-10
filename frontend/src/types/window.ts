import type { UploadResponse } from "./index";
import type { ClassificationModifications } from "../components/RecognitionResult";

/**
 * 票据分类窗口状态
 */
export type InvoiceWindow = {
  /** 窗口唯一标识符 */
  id: string;
  /** 窗口标题（票据文件名或时间戳） */
  title: string;
  /** 会话ID */
  sessionId: string | null;
  /** 识别结果 */
  result: UploadResponse | null;
  /** 分类修改内容 */
  modifications: ClassificationModifications | null;
  /** 上传中状态 */
  loading: boolean;
  /** 确认中状态 */
  confirming: boolean;
  /** 上传进度 */
  uploadProgress: number;
  /** 创建时间戳 */
  createdAt: number;
};

