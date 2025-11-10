import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  Drawer,
  Tabs,
  Input,
  Button,
  Tag,
  Space,
  message,
  List,
  Card,
  Typography,
  Empty,
  Divider
} from "antd";
import { PlusOutlined, DeleteOutlined, EditOutlined } from "@ant-design/icons";
import {
  getUserProfile,
  addProfileItem,
  removeProfileItem,
  addCategoryTag,
  removeCategoryTag,
  getClassificationRules,
  addClassificationRule,
  updateClassificationRule,
  removeClassificationRule,
  type UserProfileResponse
} from "../api/agent";

const { TextArea } = Input;
const { Title, Text } = Typography;

const MAX_TAGS_PER_CATEGORY = 7;

// 9大分类列表
const CATEGORIES = [
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

interface RoleSettingsProps {
  open: boolean;
  onClose: () => void;
}

const RoleSettings: React.FC<RoleSettingsProps> = ({ open, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [profileItems, setProfileItems] = useState<string[]>([]);
  const [categoryTags, setCategoryTags] = useState<Record<string, string[]>>({});
  const [classificationRules, setClassificationRules] = useState<string[]>([]);
  const [newProfileItem, setNewProfileItem] = useState("");
  const [newTagInputs, setNewTagInputs] = useState<Record<string, string>>({});
  const [newRule, setNewRule] = useState("");
  const [editingRuleIndex, setEditingRuleIndex] = useState<number | null>(null);
  const [editingRuleText, setEditingRuleText] = useState("");

  // 加载用户数据
  const loadUserData = async () => {
    setLoading(true);
    try {
      const data = await getUserProfile();
      setProfileItems(data.profile_items || []);
      setCategoryTags(data.category_tags || {});
      // 初始化新标签输入框
      const inputs: Record<string, string> = {};
      CATEGORIES.forEach(cat => {
        inputs[cat] = "";
      });
      setNewTagInputs(inputs);
      
      // 加载分类规则
      const rulesData = await getClassificationRules();
      setClassificationRules(rulesData.rules || []);
    } catch (error: any) {
      message.error("加载用户数据失败: " + (error.message || "未知错误"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadUserData();
    }
  }, [open]);

  // 添加用户画像条目
  const handleAddProfileItem = useCallback(async () => {
    if (!newProfileItem.trim()) {
      message.warning("请输入画像条目");
      return;
    }

    try {
      await addProfileItem(newProfileItem.trim());
      setProfileItems(prev => [...prev, newProfileItem.trim()]);
      setNewProfileItem("");
      message.success("添加成功");
    } catch (error: any) {
      message.error("添加失败: " + (error.response?.data?.detail || error.message || "未知错误"));
    }
  }, [newProfileItem]);

  // 删除用户画像条目
  const handleRemoveProfileItem = useCallback(async (item: string) => {
    try {
      await removeProfileItem(item);
      setProfileItems(prev => prev.filter(i => i !== item));
      message.success("删除成功");
    } catch (error: any) {
      message.error("删除失败: " + (error.response?.data?.detail || error.message || "未知错误"));
    }
  }, []);

  // 添加分类标签
  const handleAddCategoryTag = useCallback(async (category: string) => {
    setNewTagInputs(prev => {
      const tag = prev[category]?.trim();
      if (!tag) {
        message.warning("请输入标签名称");
        return prev;
      }

      // 检查标签数量限制
      setCategoryTags(currentTags => {
        const tags = currentTags[category] || [];
        if (tags.length >= MAX_TAGS_PER_CATEGORY) {
          message.warning(`该分类的子标签已达到最大数量限制（${MAX_TAGS_PER_CATEGORY}个）`);
          return currentTags;
        }

        // 异步添加标签
        (async () => {
          try {
            await addCategoryTag(category, tag);
            setCategoryTags(prevTags => ({
              ...prevTags,
              [category]: [...(prevTags[category] || []), tag]
            }));
            message.success("添加成功");
          } catch (error: any) {
            const errorMsg = error.response?.data?.detail || error.message || "未知错误";
            message.error("添加失败: " + errorMsg);
          }
        })();

        return currentTags;
      });

      return {
        ...prev,
        [category]: ""
      };
    });
  }, []);

  // 删除分类标签
  const handleRemoveCategoryTag = useCallback(async (category: string, tag: string) => {
    try {
      await removeCategoryTag(category, tag);
      setCategoryTags(prev => ({
        ...prev,
        [category]: (prev[category] || []).filter(t => t !== tag)
      }));
      message.success("删除成功");
    } catch (error: any) {
      message.error("删除失败: " + (error.response?.data?.detail || error.message || "未知错误"));
    }
  }, []);

  // 处理分类标签输入框变化
  const handleTagInputChange = useCallback((category: string, value: string) => {
    setNewTagInputs(prev => ({
      ...prev,
      [category]: value
    }));
  }, []);

  // 添加分类规则
  const handleAddRule = useCallback(async () => {
    if (!newRule.trim()) {
      message.warning("请输入规则内容");
      return;
    }

    try {
      await addClassificationRule(newRule.trim());
      setClassificationRules(prev => [...prev, newRule.trim()]);
      setNewRule("");
      message.success("添加成功");
    } catch (error: any) {
      message.error("添加失败: " + (error.response?.data?.detail || error.message || "未知错误"));
    }
  }, [newRule]);

  // 删除分类规则
  const handleRemoveRule = useCallback(async (index: number) => {
    try {
      await removeClassificationRule(index);
      setClassificationRules(prev => prev.filter((_, i) => i !== index));
      message.success("删除成功");
    } catch (error: any) {
      message.error("删除失败: " + (error.response?.data?.detail || error.message || "未知错误"));
    }
  }, []);

  // 开始编辑规则
  const handleStartEditRule = useCallback((index: number) => {
    setEditingRuleIndex(index);
    setEditingRuleText(classificationRules[index]);
  }, [classificationRules]);

  // 取消编辑规则
  const handleCancelEditRule = useCallback(() => {
    setEditingRuleIndex(null);
    setEditingRuleText("");
  }, []);

  // 保存编辑的规则
  const handleSaveEditRule = useCallback(async () => {
    if (editingRuleIndex === null) return;
    if (!editingRuleText.trim()) {
      message.warning("规则内容不能为空");
      return;
    }

    try {
      await updateClassificationRule(editingRuleIndex, editingRuleText.trim());
      setClassificationRules(prev => {
        const newRules = [...prev];
        newRules[editingRuleIndex] = editingRuleText.trim();
        return newRules;
      });
      setEditingRuleIndex(null);
      setEditingRuleText("");
      message.success("修改成功");
    } catch (error: any) {
      message.error("修改失败: " + (error.response?.data?.detail || error.message || "未知错误"));
    }
  }, [editingRuleIndex, editingRuleText]);

  // 用户画像标签页内容
  const profileTabContent = useMemo(() => (
    <div>
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <div>
          <Title level={5}>添加用户画像条目</Title>
          <Space.Compact style={{ width: "100%" }}>
            <TextArea
              value={newProfileItem}
              onChange={(e) => setNewProfileItem(e.target.value)}
              placeholder="请输入画像条目，例如：职业、收入水平、家庭状况等"
              rows={2}
              onPressEnter={(e) => {
                if (e.shiftKey) return;
                e.preventDefault();
                handleAddProfileItem();
              }}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAddProfileItem}
            >
              添加
            </Button>
          </Space.Compact>
        </div>

        <Divider />

        <div>
          <Title level={5}>当前画像条目</Title>
          {profileItems.length === 0 ? (
            <Empty description="暂无画像条目" />
          ) : (
            <List
              dataSource={profileItems}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="delete"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemoveProfileItem(item)}
                    >
                      删除
                    </Button>
                  ]}
                >
                  <Text>{item}</Text>
                </List.Item>
              )}
            />
          )}
        </div>
      </Space>
    </div>
  ), [newProfileItem, profileItems, handleAddProfileItem, handleRemoveProfileItem]);

  // 分类标签标签页内容
  const categoryTagsTabContent = useMemo(() => (
    <div>
      <Space direction="vertical" style={{ width: "100%" }} size="large">
        {CATEGORIES.map((category) => {
          const tags = categoryTags[category] || [];
          const canAddMore = tags.length < MAX_TAGS_PER_CATEGORY;
          const newTagInput = newTagInputs[category] || "";

          return (
            <Card
              key={category}
              title={
                <Space>
                  <span>{category}</span>
                  <Text type="secondary">
                    ({tags.length}/{MAX_TAGS_PER_CATEGORY})
                  </Text>
                </Space>
              }
              size="small"
            >
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                {/* 标签列表 */}
                <div>
                  {tags.length === 0 ? (
                    <Empty description="暂无子标签" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Space wrap>
                      {tags.map((tag) => (
                        <Tag
                          key={tag}
                          closable
                          onClose={() => handleRemoveCategoryTag(category, tag)}
                          color="blue"
                          style={{ marginBottom: 8 }}
                        >
                          {tag}
                        </Tag>
                      ))}
                    </Space>
                  )}
                </div>

                {/* 添加标签输入框 */}
                {canAddMore && (
                  <Space.Compact style={{ width: "100%" }}>
                    <Input
                      key={`input-${category}`}
                      value={newTagInput}
                      onChange={(e) => handleTagInputChange(category, e.target.value)}
                      placeholder="输入新标签名称"
                      onPressEnter={() => handleAddCategoryTag(category)}
                    />
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => handleAddCategoryTag(category)}
                    >
                      添加
                    </Button>
                  </Space.Compact>
                )}

                {!canAddMore && (
                  <Text type="warning">
                    已达到最大标签数量限制（{MAX_TAGS_PER_CATEGORY}个）
                  </Text>
                )}
              </Space>
            </Card>
          );
        })}
      </Space>
    </div>
  ), [categoryTags, newTagInputs, handleTagInputChange, handleAddCategoryTag, handleRemoveCategoryTag]);

  // 分类规则标签页内容
  const rulesTabContent = useMemo(() => (
    <div>
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <div>
          <Title level={5}>添加分类规则</Title>
          <Space.Compact style={{ width: "100%" }}>
            <TextArea
              value={newRule}
              onChange={(e) => setNewRule(e.target.value)}
              placeholder="请输入分类规则，例如：当票据包含差旅相关要素时，优先分类为'差旅商务出行'"
              rows={3}
              onPressEnter={(e) => {
                if (e.shiftKey) return;
                e.preventDefault();
                handleAddRule();
              }}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAddRule}
              disabled={classificationRules.length >= 20}
            >
              添加
            </Button>
          </Space.Compact>
          {classificationRules.length >= 20 && (
            <Text type="warning" style={{ display: "block", marginTop: 8 }}>
              已达到最大规则数量限制（20条）
            </Text>
          )}
        </div>

        <Divider />

        <div>
          <Title level={5}>当前分类规则 ({classificationRules.length}/20)</Title>
          {classificationRules.length === 0 ? (
            <Empty description="暂无分类规则" />
          ) : (
            <List
              dataSource={classificationRules}
              renderItem={(rule, index) => (
                <List.Item
                  actions={[
                    editingRuleIndex === index ? (
                      [
                        <Button
                          key="save"
                          type="primary"
                          size="small"
                          onClick={handleSaveEditRule}
                        >
                          保存
                        </Button>,
                        <Button
                          key="cancel"
                          size="small"
                          onClick={handleCancelEditRule}
                        >
                          取消
                        </Button>
                      ]
                    ) : (
                      [
                        <Button
                          key="edit"
                          type="text"
                          icon={<EditOutlined />}
                          onClick={() => handleStartEditRule(index)}
                        >
                          修改
                        </Button>,
                        <Button
                          key="delete"
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => handleRemoveRule(index)}
                        >
                          删除
                        </Button>
                      ]
                    )
                  ]}
                >
                  {editingRuleIndex === index ? (
                    <TextArea
                      value={editingRuleText}
                      onChange={(e) => setEditingRuleText(e.target.value)}
                      rows={2}
                      style={{ width: "100%" }}
                      autoFocus
                    />
                  ) : (
                    <Text>{rule}</Text>
                  )}
                </List.Item>
              )}
            />
          )}
        </div>
      </Space>
    </div>
  ), [
    newRule,
    classificationRules,
    editingRuleIndex,
    editingRuleText,
    handleAddRule,
    handleRemoveRule,
    handleStartEditRule,
    handleCancelEditRule,
    handleSaveEditRule
  ]);

  return (
    <Drawer
      title="角色设置"
      placement="right"
      width={600}
      open={open}
      onClose={onClose}
      closable
      maskClosable
    >
      <Tabs
        defaultActiveKey="profile"
        items={[
          {
            key: "profile",
            label: "用户画像",
            children: profileTabContent
          },
          {
            key: "categories",
            label: "分类标签",
            children: categoryTagsTabContent
          },
          {
            key: "rules",
            label: "分类规则",
            children: rulesTabContent
          }
        ]}
      />
    </Drawer>
  );
};

export default RoleSettings;

