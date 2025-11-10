import { Badge, Button, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { EyeOutlined, EditOutlined, DeleteOutlined, CheckOutlined } from "@ant-design/icons";
import type { DocumentRecord, DocumentStatus } from "../types";
import { formatDateTime, formatAmount, formatDate } from "../utils/format";
import { useState } from "react";

const statusMap: Record<DocumentStatus, { text: string; status: "success" | "processing" | "warning" | "error" }>
 = {
  pending: { text: "待确认", status: "warning" },
  verified: { text: "已入账", status: "success" },
  cancelled: { text: "已取消", status: "error" },
  error: { text: "失败", status: "error" }
};

type DocumentTableProps = {
  data: DocumentRecord[];
  loading?: boolean;
  onView?: (record: DocumentRecord) => void;
  onModify?: (record: DocumentRecord) => void;
  onDelete?: (record: DocumentRecord) => void;
  onConfirm?: (record: DocumentRecord) => void;
  onBatchConfirm?: (documentIds: string[]) => Promise<void>;
  onBatchDelete?: (documentIds: string[]) => Promise<void>;
};

const DocumentTable: React.FC<DocumentTableProps> = ({ 
  data, 
  loading, 
  onView, 
  onModify, 
  onDelete,
  onConfirm,
  onBatchConfirm,
  onBatchDelete
}) => {
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const columns: ColumnsType<DocumentRecord> = [
    {
      title: "上传时间",
      dataIndex: "uploadTime",
      key: "uploadTime",
      width: 180,
      render: (value) => formatDateTime(value)
    },
    {
      title: "票据时间",
      dataIndex: "issuedDate",
      key: "issuedDate",
      width: 160,
      render: (value) => formatDate(value)
    },
    {
      title: "票据类型",
      dataIndex: "documentType",
      key: "documentType",
      width: 120
    },
    {
      title: "票据分类",
      dataIndex: "userCategory",
      key: "userCategory",
      width: 140
    },
    {
      title: "标签",
      dataIndex: "tags",
      key: "tags",
      render: (tags: string[] = []) => (
        <Space size={[0, 8]} wrap>
          {tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      )
    },
    {
      title: "金额",
      dataIndex: "amount",
      key: "amount",
      width: 120,
      align: "right",
      render: (value) => formatAmount(value)
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status: DocumentStatus) => {
        const config = statusMap[status] ?? { text: status, status: "processing" };
        return <Badge status={config.status} text={config.text} />;
      }
    },
    {
      title: "操作",
      key: "action",
      width: 250,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onView?.(record)}
          >
            查看
          </Button>
          {record.status === "pending" && (
            <Button
              size="small"
              type="primary"
              icon={<CheckOutlined />}
              onClick={() => onConfirm?.(record)}
            >
              确认
            </Button>
          )}
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => onModify?.(record)}
          >
            修改
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onDelete?.(record)}
          >
            删除
          </Button>
        </Space>
      )
    }
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
    // 允许选择所有状态的票据（用于批量删除）
  };

  const handleBatchConfirm = async () => {
    const documentIds = selectedRowKeys
      .map((key) => {
        const record = data.find((r) => (r.documentId || `doc-${r.uploadTime}-${r.documentType}`) === key);
        return record?.documentId;
      })
      .filter((id): id is string => !!id)
      .filter((id) => {
        // 只确认待确认状态的票据
        const record = data.find((r) => r.documentId === id);
        return record?.status === "pending";
      });
    
    if (documentIds.length > 0) {
      try {
        await onBatchConfirm?.(documentIds);
        // 成功后清空选择
        setSelectedRowKeys([]);
      } catch (error) {
        // 失败时不清空选择，让用户可以重试
        console.error("批量确认失败:", error);
      }
    }
  };

  const handleBatchDelete = async () => {
    const documentIds = selectedRowKeys
      .map((key) => {
        const record = data.find((r) => (r.documentId || `doc-${r.uploadTime}-${r.documentType}`) === key);
        return record?.documentId;
      })
      .filter((id): id is string => !!id);
    
    if (documentIds.length > 0) {
      try {
        await onBatchDelete?.(documentIds);
        // 成功后清空选择
        setSelectedRowKeys([]);
      } catch (error) {
        // 失败时不清空选择，让用户可以重试
        console.error("批量删除失败:", error);
      }
    }
  };

  return (
    <div>
      {selectedRowKeys.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button 
              type="primary" 
              onClick={handleBatchConfirm}
              disabled={selectedRowKeys.length === 0}
            >
              批量确认选中 ({selectedRowKeys.length})
            </Button>
            <Button 
              danger
              onClick={handleBatchDelete}
              disabled={selectedRowKeys.length === 0}
            >
              批量删除选中 ({selectedRowKeys.length})
            </Button>
          </Space>
        </div>
      )}
      <Table 
        rowKey={(record) => record.documentId || `doc-${record.uploadTime}-${record.documentType}`}
        columns={columns} 
        dataSource={data} 
        loading={loading} 
        pagination={{ pageSize: 10 }}
        rowSelection={rowSelection}
      />
    </div>
  );
};

export default DocumentTable;
