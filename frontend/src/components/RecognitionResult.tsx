import { Card, Descriptions, Input, Select, Tag, Typography } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEffect, useRef, useState } from "react";
import type { UploadResponse } from "../types";
import { getCategoryTags } from "../api/agent";

const { Title, Text } = Typography;

export type ClassificationModifications = {
  professional_category?: string;
  user_category?: string;
  tags?: string[];
};

type RecognitionResultProps = {
  loading?: boolean;
  result?: UploadResponse | null;
  onModificationsChange?: (modifications: ClassificationModifications | null) => void;
};

const RecognitionResult: React.FC<RecognitionResultProps> = ({ 
  loading, 
  result,
  onModificationsChange 
}) => {
  const [isEditing, setIsEditing] = useState<{
    professional_category: boolean;
    user_category: boolean;
  }>({
    professional_category: false,
    user_category: false,
  });

  const [editedValues, setEditedValues] = useState<ClassificationModifications>({});
  const [availableTags, setAvailableTags] = useState<string[]>([]); // 当前分类下的可选子标签
  const [loadingTags, setLoadingTags] = useState(false);
  
  const professionalCategoryInputRef = useRef<any>(null);
  const userCategoryInputRef = useRef<any>(null);

  // 当结果变化时，重置编辑状态和修改值
  useEffect(() => {
    setIsEditing({
      professional_category: false,
      user_category: false,
    });
    setEditedValues({});
    setAvailableTags([]);
  }, [result]);

  // 根据票据分类加载可选子标签
  useEffect(() => {
    const loadCategoryTags = async () => {
      const currentUserCategory = editedValues.user_category ?? result?.classification?.user_category;
      
      if (!currentUserCategory) {
        setAvailableTags([]);
        return;
      }

      try {
        setLoadingTags(true);
        const response = await getCategoryTags(currentUserCategory);
        setAvailableTags(response.tags || []);
      } catch (error: any) {
        console.error("加载子标签失败:", error);
        // 如果加载失败，不显示错误提示，只清空可选标签
        setAvailableTags([]);
      } finally {
        setLoadingTags(false);
      }
    };

    loadCategoryTags();
  }, [editedValues.user_category, result?.classification?.user_category]);

  // 当修改值变化时，通知父组件
  useEffect(() => {
    if (onModificationsChange) {
      const hasModifications = 
        editedValues.professional_category !== undefined ||
        editedValues.user_category !== undefined ||
        editedValues.tags !== undefined;
      
      onModificationsChange(hasModifications ? editedValues : null);
    }
  }, [editedValues, onModificationsChange]);

  // 聚焦输入框
  useEffect(() => {
    if (isEditing.professional_category && professionalCategoryInputRef.current) {
      professionalCategoryInputRef.current.focus();
    }
  }, [isEditing.professional_category]);

  useEffect(() => {
    if (isEditing.user_category && userCategoryInputRef.current) {
      userCategoryInputRef.current.focus();
    }
  }, [isEditing.user_category]);

  if (loading) {
    return <Card loading title="识别结果" />;
  }

  if (!result || !result.success) {
    return (
      <Card title="识别结果" variant="outlined">
        <Text type="secondary">识别结果将在提交后显示。</Text>
      </Card>
    );
  }

  const classification = result.classification;
  
  // 获取当前显示的值（优先使用修改后的值）
  const currentProfessionalCategory = editedValues.professional_category ?? classification?.professional_category ?? "";
  const currentUserCategory = editedValues.user_category ?? classification?.user_category ?? "";
  const currentTags = editedValues.tags ?? classification?.tags ?? [];

  // 处理专业分类编辑
  const handleProfessionalCategoryClick = () => {
    setIsEditing({ ...isEditing, professional_category: true });
  };

  const handleProfessionalCategoryConfirm = () => {
    setIsEditing({ ...isEditing, professional_category: false });
  };

  const handleProfessionalCategoryCancel = () => {
    setEditedValues({ ...editedValues, professional_category: undefined });
    setIsEditing({ ...isEditing, professional_category: false });
  };

  const handleProfessionalCategoryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEditedValues({ ...editedValues, professional_category: value });
  };

  // 处理用户分类编辑
  const handleUserCategoryClick = () => {
    setIsEditing({ ...isEditing, user_category: true });
  };

  const handleUserCategoryConfirm = () => {
    setIsEditing({ ...isEditing, user_category: false });
  };

  const handleUserCategoryCancel = () => {
    setEditedValues({ ...editedValues, user_category: undefined });
    setIsEditing({ ...isEditing, user_category: false });
  };

  const handleUserCategoryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    const oldCategory = editedValues.user_category ?? result?.classification?.user_category;
    
    // 当票据分类改变时，清空已选标签（因为子标签是基于分类的）
    if (value !== oldCategory) {
      setEditedValues({ ...editedValues, user_category: value, tags: undefined });
    } else {
      setEditedValues({ ...editedValues, user_category: value });
    }
  };

  // 处理标签删除
  const handleTagRemove = (tagToRemove: string) => {
    const newTags = currentTags.filter(tag => tag !== tagToRemove);
    setEditedValues({ ...editedValues, tags: newTags });
  };

  // 处理添加子标签
  const handleTagSelect = (value: string) => {
    if (value && !currentTags.includes(value)) {
      const newTags = [...currentTags, value];
      setEditedValues({ ...editedValues, tags: newTags });
    }
  };

  return (
    <Card title="识别结果" variant="outlined" size="small" style={{ marginBottom: 0 }}>
      <Title level={5} style={{ marginTop: 0, marginBottom: 12, fontSize: 16 }}>
        分类信息
      </Title>
      <Descriptions column={2} size="small" bordered>
        <Descriptions.Item label="票据类型" span={1} style={{ padding: "10px 12px" }}>
          {isEditing.professional_category ? (
            <Input
              ref={professionalCategoryInputRef}
              value={currentProfessionalCategory}
              onChange={handleProfessionalCategoryChange}
              onPressEnter={handleProfessionalCategoryConfirm}
              onBlur={handleProfessionalCategoryConfirm}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  handleProfessionalCategoryCancel();
                }
              }}
              style={{ fontSize: 14 }}
              size="small"
            />
          ) : (
            <Text 
              style={{ fontSize: 14, cursor: "pointer", userSelect: "none" }}
              onClick={handleProfessionalCategoryClick}
              title="点击编辑"
            >
              {currentProfessionalCategory || "-"}
          </Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="票据分类" span={1} style={{ padding: "10px 12px" }}>
          {isEditing.user_category ? (
            <Input
              ref={userCategoryInputRef}
              value={currentUserCategory}
              onChange={handleUserCategoryChange}
              onPressEnter={handleUserCategoryConfirm}
              onBlur={handleUserCategoryConfirm}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  handleUserCategoryCancel();
                }
              }}
              style={{ fontSize: 14 }}
              size="small"
            />
          ) : (
            <Text 
              style={{ fontSize: 14, cursor: "pointer", userSelect: "none" }}
              onClick={handleUserCategoryClick}
              title="点击编辑"
            >
              {currentUserCategory || "-"}
          </Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="子标签" span={2} style={{ padding: "10px 12px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
              {currentTags.length > 0 ? (
                currentTags.map((tag) => (
                  <Tag
                    key={tag}
                    closable
                    onClose={() => handleTagRemove(tag)}
                    style={{ marginBottom: 4 }}
                  >
                    {tag}
                  </Tag>
                ))
              ) : (
                <Text type="secondary" style={{ fontSize: 13 }}>暂无子标签</Text>
              )}
            </div>
            {currentUserCategory ? (
              <Select
                placeholder={loadingTags ? "加载中..." : "选择子标签"}
                value={null}
                onChange={handleTagSelect}
                loading={loadingTags}
                disabled={loadingTags || availableTags.length === 0}
                size="small"
                style={{ width: "100%", fontSize: 13 }}
                options={availableTags
                  .filter(tag => !currentTags.includes(tag))
                  .map(tag => ({ label: tag, value: tag }))}
                notFoundContent={
                  loadingTags ? (
                    <div style={{ padding: "8px 0", textAlign: "center" }}>
                      <Text type="secondary">加载中...</Text>
                    </div>
                  ) : availableTags.length === 0 ? (
                    <div style={{ padding: "8px 0", textAlign: "center" }}>
                      <Text type="secondary">该分类暂无子标签</Text>
                    </div>
                  ) : (
                    <div style={{ padding: "8px 0", textAlign: "center" }}>
                      <Text type="secondary">所有子标签已添加</Text>
                    </div>
                  )
                }
              />
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>
                请先选择票据分类以加载子标签
              </Text>
            )}
          </div>
        </Descriptions.Item>
        <Descriptions.Item label="推理说明" span={2} style={{ padding: "10px 12px" }}>
          <div
            style={{
              maxHeight: "120px",
              overflowY: "auto",
              overflowX: "hidden",
              padding: "4px 0",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: 13,
              lineHeight: 1.6,
            }}
          >
            {classification?.reasoning ? classification.reasoning : "-"}
          </div>
        </Descriptions.Item>
      </Descriptions>

      <Title level={5} style={{ marginTop: 16, marginBottom: 8, fontSize: 16 }}>
        Markdown 结构化内容
      </Title>
      <Card size="small" style={{ maxHeight: 240, overflow: "auto", fontSize: 13, marginBottom: 0 }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {result.recognition?.markdown_content ?? "暂无内容"}
        </ReactMarkdown>
      </Card>
    </Card>
  );
};

export default RecognitionResult;
