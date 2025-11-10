import axios from "axios";
import type { UploadRequestOption } from "rc-upload/lib/interface";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

const api = axios.create({
  baseURL,
  timeout: 30000
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("agent_token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // 添加请求日志
  if (config.url === "/upload") {
    console.log("[API] 上传请求:", {
      url: config.url,
      method: config.method,
      hasToken: !!token,
      contentType: config.headers?.["Content-Type"],
      isFormData: config.data instanceof FormData
    });
    
    // 如果是FormData，记录字段信息（不记录文件内容）
    if (config.data instanceof FormData) {
      const formDataEntries: Record<string, string> = {};
      for (const [key, value] of config.data.entries()) {
        if (value instanceof File) {
          formDataEntries[key] = `File: ${value.name} (${value.size} bytes, ${value.type})`;
        } else {
          formDataEntries[key] = String(value);
        }
      }
      console.log("[API] FormData 字段:", formDataEntries);
    }
  }
  
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("agent_token");
      localStorage.removeItem("agent_user");
      if (window.location.pathname !== "/login") {
      window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export type AuthResponse = {
  success: boolean;
  token: string;
  username: string;
};

export const login = async (username: string, password: string): Promise<AuthResponse> => {
  const { data } = await api.post<AuthResponse>("/login", { username, password });
  return data;
};

export const register = async (username: string, password: string): Promise<AuthResponse> => {
  const { data } = await api.post<AuthResponse>("/register", { username, password });
  return data;
};

export const getCurrentUser = async () => {
  const { data } = await api.get("/me");
  return data;
};

export const logout = async () => {
  try {
    await api.post("/logout");
  } catch (error) {
    // ignore
  }
};

export const uploadDocument = async (
  payload: FormData,
  onUploadProgress?: (progressEvent: { loaded: number; total: number }) => void
) => {
  try {
    console.log("[API] uploadDocument 开始调用");
    
    // 验证FormData
    if (!(payload instanceof FormData)) {
      throw new Error("payload必须是FormData对象");
    }
    
    // 验证必需字段
    if (!payload.has("image")) {
      throw new Error("FormData中缺少必需的image字段");
    }
    
    const imageFile = payload.get("image");
    if (!(imageFile instanceof File)) {
      throw new Error("image字段必须是File对象");
    }
    
    console.log("[API] FormData验证通过:", {
      hasImage: payload.has("image"),
      hasAudio: payload.has("audio"),
      hasText: payload.has("text"),
      hasRemarks: payload.has("remarks"),
      imageName: imageFile.name,
      imageSize: imageFile.size,
      imageType: imageFile.type
    });
    
    const response = await api.post("/upload", payload, {
      headers: { 
        "Content-Type": "multipart/form-data"
      },
      timeout: 180000, // 上传和处理超时时间180秒（3分钟），因为AI处理可能需要较长时间
      onUploadProgress: (progressEvent) => {
        if (onUploadProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          console.log(`[API] 上传进度: ${percent}%`);
          onUploadProgress({
            loaded: progressEvent.loaded,
            total: progressEvent.total
          });
        }
      }
    });
    
    console.log("[API] uploadDocument 响应:", response.data);
    return response.data;
  } catch (error: any) {
    console.error("[API] uploadDocument 错误:", error);
    
    // 改进错误处理
    if (error.response) {
      // 服务器返回了错误响应
      const status = error.response.status;
      const errorData = error.response.data;
      const errorMessage = errorData?.error || errorData?.detail || `服务器错误: ${status}`;
      
      console.error("[API] 服务器错误响应:", {
        status,
        data: errorData
      });
      
      throw new Error(errorMessage);
    } else if (error.request) {
      // 请求已发出但没有收到响应
      console.error("[API] 网络错误: 未收到服务器响应", error);
      
      // 检查是否是超时错误
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        console.error("[API] 请求超时");
        throw new Error("请求超时，服务器处理时间过长。请稍后重试，或检查服务器是否正常运行。");
      }
      
      throw new Error("网络错误，请检查网络连接或服务器是否正常运行");
    } else {
      // 其他错误
      throw error;
    }
  }
};

export const confirmDocument = async (sessionId: string, modifications?: Record<string, unknown>) => {
  const { data } = await api.post("/confirm", { sessionId, modifications });
  return data;
};

export const transcribeAudio = async (audioFile: File): Promise<{ success: boolean; text?: string; error?: string }> => {
  try {
    console.log("[API] transcribeAudio 开始调用", { fileName: audioFile.name, size: audioFile.size });
    
    const formData = new FormData();
    formData.append("audio", audioFile);
    
    const { data } = await api.post("/transcribe", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000, // 转文本超时时间60秒
    });
    
    console.log("[API] transcribeAudio 响应:", data);
    return data;
  } catch (error: any) {
    console.error("[API] transcribeAudio 错误:", error);
    
    if (error.response) {
      const status = error.response.status;
      const errorData = error.response.data;
      const errorMessage = errorData?.error || errorData?.detail || `服务器错误: ${status}`;
      return { success: false, error: errorMessage };
    } else if (error.request) {
      return { success: false, error: "网络错误，请检查网络连接" };
    } else {
      return { success: false, error: error.message || "转文本失败" };
    }
  }
};

export const fetchUserSummary = async () => {
  const { data } = await api.get("/user_summary");
  return data;
};

export const fetchDocuments = async (params?: Record<string, unknown>) => {
  const { data } = await api.get("/documents", { params });
  return data;
};

export const manualProfileOptimize = async () => {
  const { data } = await api.post("/optimize_profile", { manual: true });
  return data;
};

export const triggerFeedbackLearning = async () => {
  const { data } = await api.post("/user/trigger_learning");
  return data;
};

export const uploadRequestAdapter = async ({
  file,
  onProgress,
  onSuccess,
  onError
}: UploadRequestOption) => {
  try {
    const formData = new FormData();
    formData.append("file", file as Blob);
    const response = await api.post("/upload_file", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (onProgress && event.total) {
          onProgress({ percent: (event.loaded / event.total) * 100 });
        }
      }
    });
    onSuccess?.(response.data, file as any);
  } catch (error) {
    onError?.(error as Error);
  }
};

// 用户设置相关API
export type UserProfileResponse = {
  profile_items: string[];
  category_tags: Record<string, string[]>;
};

export type CategoryTagsResponse = {
  category: string;
  tags: string[];
};

export const getUserProfile = async (): Promise<UserProfileResponse> => {
  const { data } = await api.get<UserProfileResponse>("/user/profile");
  return data;
};

export const updateUserProfile = async (items: string[]): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.put("/user/profile", { items });
  return data;
};

export const addProfileItem = async (item: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.post("/user/profile/items", { item });
  return data;
};

export const removeProfileItem = async (item: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.delete("/user/profile/items", { params: { item } });
  return data;
};

// 分类规则相关API
export type ClassificationRulesResponse = {
  rules: string[];
};

export const getClassificationRules = async (): Promise<ClassificationRulesResponse> => {
  const { data } = await api.get<ClassificationRulesResponse>("/user/classification_rules");
  return data;
};

export const addClassificationRule = async (rule: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.post("/user/classification_rules", { rule });
  return data;
};

export const updateClassificationRule = async (index: number, rule: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.put("/user/classification_rules", { index, rule });
  return data;
};

export const removeClassificationRule = async (index: number): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.delete("/user/classification_rules", { params: { index } });
  return data;
};

export const getCategoryTags = async (category: string): Promise<CategoryTagsResponse> => {
  const { data } = await api.get<CategoryTagsResponse>(`/user/categories/${encodeURIComponent(category)}/tags`);
  return data;
};

export const addCategoryTag = async (category: string, tag: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.post(`/user/categories/${encodeURIComponent(category)}/tags`, { tag });
  return data;
};

export const removeCategoryTag = async (category: string, tag: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.delete(`/user/categories/${encodeURIComponent(category)}/tags`, { params: { tag } });
  return data;
};

// 文档管理相关API
export const updateDocument = async (
  documentId: string,
  updates: { 
    document_type?: string; 
    user_category?: string; 
    tags?: string[];
    amount?: number;
    status?: string;
  }
): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.put(`/documents/${documentId}`, updates);
  return data;
};

export const deleteDocument = async (documentId: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.delete(`/documents/${documentId}`);
  return data;
};

export const batchConfirmDocuments = async (
  documentIds: string[]
): Promise<{ success: boolean; confirmed_count: number; failed_count: number; message: string }> => {
  const { data } = await api.post("/documents/batch_confirm", { document_ids: documentIds });
  return data;
};

export const confirmDocumentById = async (documentId: string): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.post(`/documents/${documentId}/confirm`);
  return data;
};

export const batchDeleteDocuments = async (
  documentIds: string[]
): Promise<{ success: boolean; deleted_count: number; failed_count: number; message: string }> => {
  const { data } = await api.post("/documents/batch_delete", { document_ids: documentIds });
  return data;
};

export default api;
