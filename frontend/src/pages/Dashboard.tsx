import { useEffect, useState, useMemo } from "react";
import { App, Button, Modal, Form, Select, InputNumber, Radio } from "antd";
import DashboardCharts from "../components/DashboardCharts";
import DocumentTable from "../components/DocumentTable";
import { 
  fetchDocuments, 
  fetchUserSummary, 
  manualProfileOptimize,
  triggerFeedbackLearning,
  updateDocument,
  deleteDocument,
  confirmDocumentById,
  batchConfirmDocuments,
  batchDeleteDocuments,
  getCategoryTags
} from "../api/agent";
import type { ClassificationSummary, DocumentRecord } from "../types";

type TimeRange = "week" | "month" | "year" | "all";

const DOCUMENT_TYPES = [
  "发票",
  "行程单",
  "小票",
  "收据"
];

const USER_CATEGORIES = [
  "餐饮消费",
  "购物消费",
  "交通出行",
  "居住相关",
  "医疗健康",
  "教育文娱",
  "人情往来",
  "收入类",
  "其他支出"
];

const DOCUMENT_STATUSES = [
  { value: "pending", label: "待确认" },
  { value: "verified", label: "已入账" },
  { value: "cancelled", label: "已取消" }
];

const DashboardPage = () => {
  const { message, modal } = App.useApp();
  const [form] = Form.useForm();
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [summary, setSummary] = useState<ClassificationSummary | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [modifyModalVisible, setModifyModalVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<DocumentRecord | null>(null);
  const [availableTags, setAvailableTags] = useState<string[]>([]); // 当前分类下的可选子标签
  const [loadingTags, setLoadingTags] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>("all");

  const loadSummary = async () => {
    try {
      setLoadingSummary(true);
      const data = await fetchUserSummary();
      setSummary(data.summary ?? null);
    } catch (error) {
      console.error(error);
      message.error("获取统计信息失败");
    } finally {
      setLoadingSummary(false);
    }
  };

  const loadDocuments = async () => {
    try {
      setLoadingDocuments(true);
      const data = await fetchDocuments();
      setDocuments(data.documents ?? []);
    } catch (error) {
      console.error(error);
      message.error("获取票据列表失败");
    } finally {
      setLoadingDocuments(false);
    }
  };

  useEffect(() => {
    loadSummary();
    loadDocuments();
  }, []);

  // 根据时间范围过滤文档
  const filteredDocuments = useMemo(() => {
    if (timeRange === "all") {
      return documents.filter(doc => doc.status === "verified");
    }

    const now = new Date();
    let startDate: Date;

    switch (timeRange) {
      case "week":
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case "month":
        startDate = new Date(now.getFullYear(), now.getMonth(), 1);
        break;
      case "year":
        startDate = new Date(now.getFullYear(), 0, 1);
        break;
      default:
        return documents.filter(doc => doc.status === "verified");
    }

    return documents.filter(doc => {
      if (doc.status !== "verified") return false;
      
      // 优先使用 issuedDate，如果没有则使用 uploadTime
      const dateStr = doc.issuedDate || doc.uploadTime;
      if (!dateStr) return false;

      // 解析日期字符串（支持 YYYY/MM/DD 和 ISO 格式）
      let docDate: Date;
      if (dateStr.includes("/")) {
        const [year, month, day] = dateStr.split("/").map(Number);
        docDate = new Date(year, month - 1, day);
      } else {
        docDate = new Date(dateStr);
      }

      return docDate >= startDate && docDate <= now;
    });
  }, [documents, timeRange]);

  const handleViewDocument = (record: DocumentRecord) => {
    // 处理图片URL - 如果是本地路径，转换为API路径
    const getImageUrl = (sourceImage: string | undefined) => {
      if (!sourceImage) return null;
      // 如果是完整的URL，直接使用
      if (sourceImage.startsWith('http://') || sourceImage.startsWith('https://')) {
        return sourceImage;
      }
      // 如果是本地文件路径，通过API访问
      // 提取文件名部分（最后一个斜杠后面的内容）
      const filename = sourceImage.split(/[/\\]/).pop();
      if (!filename) return null;
      
      // 获取token
      const token = localStorage.getItem("agent_token");
      if (!token) return null;
      
      const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";
      return `${baseURL}/files/${record.documentId}/${filename}?token=${encodeURIComponent(token)}`;
    };

    const imageUrl = getImageUrl(record.sourceImage);

    modal.info({
      title: "票据详情",
      width: 820,
      content: (
        <div>
          {imageUrl && (
            <div style={{ marginBottom: 16, textAlign: "center" }}>
              <img 
                src={imageUrl} 
                alt="票据原图" 
                style={{ 
                  maxWidth: "100%", 
                  maxHeight: 400, 
                  objectFit: "contain",
                  border: "1px solid #d9d9d9",
                  borderRadius: 4
                }} 
                onError={(e) => {
                  console.error("图片加载失败:", imageUrl);
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            </div>
          )}
          <p>
            <strong>上传时间：</strong>
            {record.uploadTime}
          </p>
          <p>
            <strong>票据类型：</strong>
            {record.documentType}
          </p>
          <p>
            <strong>用户分类：</strong>
            {record.userCategory}
          </p>
          <p>
            <strong>标签：</strong>
            {record.tags?.join(", ") || "-"}
          </p>
          {record.amount !== undefined && record.amount !== null && (
            <p>
              <strong>金额：</strong>
              ￥{record.amount.toFixed(2)}
            </p>
          )}
          <p>
            <strong>状态：</strong>
            {record.status === "pending" ? "待确认" : record.status === "verified" ? "已入账" : record.status === "cancelled" ? "已取消" : record.status}
          </p>
          {record.markdownContent && (
            <div style={{ marginTop: 16 }}>
              <strong>详细内容：</strong>
              <pre style={{ maxHeight: 300, overflow: "auto", marginTop: 8, padding: 12, background: "#f5f5f5", borderRadius: 4 }}>
                {record.markdownContent}
              </pre>
            </div>
          )}
        </div>
      )
    });
  };

  const handleModify = async (record: DocumentRecord) => {
    setCurrentRecord(record);
    const userCategory = record.userCategory || undefined;
    form.setFieldsValue({
      document_type: record.documentType || undefined,
      user_category: userCategory,
      tags: record.tags || [],
      amount: record.amount || undefined,
      status: record.status || undefined
    });
    setModifyModalVisible(true);
    
    // 加载该分类下的子标签
    if (userCategory) {
      await loadCategoryTags(userCategory);
    } else {
      setAvailableTags([]);
    }
  };

  // 加载分类下的子标签
  const loadCategoryTags = async (category: string): Promise<string[]> => {
    if (!category) {
      setAvailableTags([]);
      return [];
    }

    try {
      setLoadingTags(true);
      const response = await getCategoryTags(category);
      const tags = response.tags || [];
      setAvailableTags(tags);
      return tags;
    } catch (error: any) {
      console.error("加载子标签失败:", error);
      setAvailableTags([]);
      return [];
    } finally {
      setLoadingTags(false);
    }
  };

  const handleModifySubmit = async () => {
    try {
      const values = await form.validateFields();
      if (!currentRecord?.documentId) {
        message.error("票据ID不存在");
        return;
      }

      message.loading({ content: "正在修改...", key: "modify" });
      const result = await updateDocument(currentRecord.documentId, {
        document_type: values.document_type,
        user_category: values.user_category,
        tags: values.tags || [],
        amount: values.amount,
        status: values.status
      });

      if (result.success) {
        message.success({ content: "修改成功", key: "modify" });
        setModifyModalVisible(false);
        form.resetFields();
        setCurrentRecord(null);
        setAvailableTags([]);
        // 刷新数据
        loadDocuments();
        loadSummary();
      } else {
        message.error({ content: result.message || "修改失败", key: "modify" });
      }
    } catch (error) {
      console.error(error);
      message.error({ content: (error as Error).message || "修改失败", key: "modify" });
    }
  };

  const handleConfirm = async (record: DocumentRecord) => {
    if (!record.documentId) {
      message.error("票据ID不存在");
      return;
    }

    if (record.status !== "pending") {
      message.warning("只能确认待确认状态的票据");
      return;
    }

    modal.confirm({
      title: "确认票据",
      content: `确定要确认这条票据吗？`,
      okText: "确认",
      cancelText: "取消",
      onOk: async () => {
        try {
          message.loading({ content: "正在确认...", key: "confirm" });
          const result = await confirmDocumentById(record.documentId);
          
          if (result.success) {
            message.success({ content: "确认成功", key: "confirm" });
            // 刷新数据
            loadDocuments();
            loadSummary();
          } else {
            message.error({ content: result.message || "确认失败", key: "confirm" });
          }
        } catch (error) {
          console.error(error);
          message.error({ content: (error as Error).message || "确认失败", key: "confirm" });
        }
      }
    });
  };

  const handleDelete = (record: DocumentRecord) => {
    modal.confirm({
      title: "确认删除",
      content: `确定要删除这条票据吗？删除后无法恢复。`,
      okText: "确认",
      cancelText: "取消",
      okType: "danger",
      onOk: async () => {
        if (!record.documentId) {
          message.error("票据ID不存在");
          return;
        }

        try {
          message.loading({ content: "正在删除...", key: "delete" });
          const result = await deleteDocument(record.documentId);
          
          if (result.success) {
            message.success({ content: "删除成功", key: "delete" });
            // 刷新数据
            loadDocuments();
            loadSummary();
          } else {
            message.error({ content: result.message || "删除失败", key: "delete" });
          }
        } catch (error) {
          console.error(error);
          message.error({ content: (error as Error).message || "删除失败", key: "delete" });
        }
      }
    });
  };

  const handleBatchConfirm = async (documentIds: string[]): Promise<void> => {
    if (documentIds.length === 0) {
      message.warning("请至少选择一条票据");
      return;
    }

    return new Promise((resolve, reject) => {
      modal.confirm({
        title: "确认批量确认",
        content: `确定要确认选中的 ${documentIds.length} 条票据吗？`,
        okText: "确认",
        cancelText: "取消",
        onOk: async () => {
          try {
            message.loading({ content: "正在批量确认...", key: "batchConfirm" });
            const result = await batchConfirmDocuments(documentIds);
            
            if (result.success) {
              message.success({ 
                content: result.message || `成功确认 ${result.confirmed_count} 条票据`, 
                key: "batchConfirm" 
              });
              // 刷新数据
              await loadDocuments();
              await loadSummary();
              resolve();
            } else {
              message.error({ content: result.message || "批量确认失败", key: "batchConfirm" });
              reject(new Error(result.message || "批量确认失败"));
            }
          } catch (error) {
            console.error(error);
            message.error({ content: (error as Error).message || "批量确认失败", key: "batchConfirm" });
            reject(error);
          }
        },
        onCancel: () => {
          reject(new Error("用户取消操作"));
        }
      });
    });
  };

  const handleBatchDelete = async (documentIds: string[]): Promise<void> => {
    if (documentIds.length === 0) {
      message.warning("请至少选择一条票据");
      return;
    }

    return new Promise((resolve, reject) => {
      modal.confirm({
        title: "确认批量删除",
        content: `确定要删除选中的 ${documentIds.length} 条票据吗？删除后无法恢复。`,
        okText: "确认",
        cancelText: "取消",
        okType: "danger",
        onOk: async () => {
          try {
            message.loading({ content: "正在批量删除...", key: "batchDelete" });
            const result = await batchDeleteDocuments(documentIds);
            
            if (result.success) {
              message.success({ 
                content: result.message || `成功删除 ${result.deleted_count} 条票据`, 
                key: "batchDelete" 
              });
              // 刷新数据
              await loadDocuments();
              await loadSummary();
              resolve();
            } else {
              message.error({ content: result.message || "批量删除失败", key: "batchDelete" });
              reject(new Error(result.message || "批量删除失败"));
            }
          } catch (error) {
            console.error(error);
            message.error({ content: (error as Error).message || "批量删除失败", key: "batchDelete" });
            reject(error);
          }
        },
        onCancel: () => {
          reject(new Error("用户取消操作"));
        }
      });
    });
  };

  const handleOptimizeProfile = async () => {
    try {
      message.loading({ content: "正在触发画像优化...", key: "optimize" });
      const result = await manualProfileOptimize();
      if (result.success) {
        message.success({ content: "画像优化完成", key: "optimize" });
      } else {
        message.error({ content: result.error || "画像优化失败", key: "optimize" });
      }
    } catch (error) {
      console.error(error);
      message.error({ content: (error as Error).message || "画像优化失败", key: "optimize" });
    }
  };

  const handleTriggerLearning = async () => {
    try {
      message.loading({ content: "正在触发反馈学习...", key: "learning" });
      const result = await triggerFeedbackLearning();
      if (result.success && result.triggered) {
        const rulesInfo = result.rules_count 
          ? `，生成了 ${result.rules_count} 条规则` 
          : "";
        message.success({ 
          content: `反馈学习完成${rulesInfo}`, 
          key: "learning",
          duration: 5
        });
        if (result.summary) {
          modal.info({
            title: "反馈学习结果",
            width: 600,
            content: (
              <div>
                <p><strong>反馈数量：</strong>{result.feedback_count || 0}</p>
                <p><strong>生成规则数：</strong>{result.rules_count || 0}</p>
                {result.summary && (
                  <div style={{ marginTop: 16 }}>
                    <strong>摘要：</strong>
                    <p style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{result.summary}</p>
                  </div>
                )}
                {result.rules && result.rules.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <strong>生成的规则：</strong>
                    <ul style={{ marginTop: 8 }}>
                      {result.rules.map((rule, index) => (
                        <li key={index} style={{ marginBottom: 8 }}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )
          });
        }
      } else {
        message.error({ 
          content: result.error || result.reason || "反馈学习失败", 
          key: "learning" 
        });
      }
    } catch (error) {
      console.error(error);
      message.error({ content: (error as Error).message || "反馈学习失败", key: "learning" });
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Radio.Group 
          value={timeRange} 
          onChange={(e) => setTimeRange(e.target.value)}
          buttonStyle="solid"
        >
          <Radio.Button value="week">周</Radio.Button>
          <Radio.Button value="month">月</Radio.Button>
          <Radio.Button value="year">年</Radio.Button>
          <Radio.Button value="all">全部</Radio.Button>
        </Radio.Group>
      </div>
      <DashboardCharts documents={filteredDocuments} loading={loadingDocuments} />
      <div style={{ marginTop: 24 }}>
        <DocumentTable
          data={documents}
          loading={loadingDocuments}
          onView={handleViewDocument}
          onModify={handleModify}
          onDelete={handleDelete}
          onConfirm={handleConfirm}
          onBatchConfirm={handleBatchConfirm}
          onBatchDelete={handleBatchDelete}
        />
      </div>
      <div style={{ marginTop: 16, textAlign: "right", display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <Button type="default" onClick={handleTriggerLearning}>
          手动触发反馈学习
        </Button>
        <Button type="default" onClick={handleOptimizeProfile}>
          手动触发画像优化
        </Button>
      </div>

      <Modal
        title="修改票据"
        open={modifyModalVisible}
        onOk={handleModifySubmit}
        onCancel={() => {
          setModifyModalVisible(false);
          form.resetFields();
          setCurrentRecord(null);
          setAvailableTags([]);
        }}
        okText="确认"
        cancelText="取消"
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Form.Item
            label="票据类型"
            name="document_type"
          >
            <Select 
              placeholder="请选择票据类型" 
              allowClear
            >
              {DOCUMENT_TYPES.map((type) => (
                <Select.Option key={type} value={type}>
                  {type}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="票据分类"
            name="user_category"
          >
            <Select 
              placeholder="请选择票据分类" 
              allowClear
              onChange={async (value) => {
                // 当分类改变时，加载对应的子标签
                if (value) {
                  const tags = await loadCategoryTags(value);
                  // 获取当前已选的标签，过滤掉不在新分类子标签列表中的标签
                  const currentTags = form.getFieldValue("tags") || [];
                  const filteredTags = currentTags.filter((tag: string) => 
                    tags.includes(tag)
                  );
                  form.setFieldsValue({ tags: filteredTags });
                } else {
                  setAvailableTags([]);
                  form.setFieldsValue({ tags: [] });
                }
              }}
            >
              {USER_CATEGORIES.map((cat) => (
                <Select.Option key={cat} value={cat}>
                  {cat}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prevValues, currentValues) => prevValues.user_category !== currentValues.user_category}>
            {({ getFieldValue }) => {
              const userCategory = getFieldValue("user_category");
              return (
                <Form.Item
                  label="子标签"
                  name="tags"
                  extra={userCategory 
                    ? "请从该分类下的子标签中选择" 
                    : "请先选择票据分类以加载子标签"}
                >
                  <Select
                    mode="multiple"
                    placeholder={loadingTags ? "加载中..." : (userCategory ? "请选择子标签" : "请先选择票据分类")}
                    loading={loadingTags}
                    disabled={!userCategory || loadingTags || availableTags.length === 0}
                    style={{ width: "100%" }}
                    options={availableTags.map(tag => ({ label: tag, value: tag }))}
                    notFoundContent={
                      loadingTags ? (
                        <div style={{ padding: "8px 0", textAlign: "center" }}>
                          加载中...
                        </div>
                      ) : availableTags.length === 0 ? (
                        <div style={{ padding: "8px 0", textAlign: "center" }}>
                          {userCategory ? "该分类暂无子标签" : "请先选择票据分类"}
                        </div>
                      ) : null
                    }
                  />
                </Form.Item>
              );
            }}
          </Form.Item>
          <Form.Item
            label="金额"
            name="amount"
          >
            <InputNumber
              placeholder="请输入金额"
              style={{ width: "100%" }}
              min={0}
              precision={2}
              prefix="￥"
            />
          </Form.Item>
          <Form.Item
            label="状态"
            name="status"
          >
            <Select 
              placeholder="请选择状态" 
              allowClear
            >
              {DOCUMENT_STATUSES.map((status) => (
                <Select.Option key={status.value} value={status.value}>
                  {status.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DashboardPage;
