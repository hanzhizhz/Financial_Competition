import { useMemo } from "react";
import { Card, Col, Row, Statistic, Typography, Table, Tag } from "antd";
import { Pie, Line } from "@ant-design/plots";
import type { DocumentRecord } from "../types";
import type { ColumnsType } from "antd/es/table";

type DashboardChartsProps = {
  documents: DocumentRecord[];
  loading?: boolean;
};

const DashboardCharts: React.FC<DashboardChartsProps> = ({ documents, loading }) => {
  // 解析日期字符串
  const parseDate = (dateStr: string | undefined): Date | null => {
    if (!dateStr) return null;
    try {
      if (dateStr.includes("/")) {
        const [year, month, day] = dateStr.split("/").map(Number);
        return new Date(year, month - 1, day);
      }
      return new Date(dateStr);
    } catch {
      return null;
    }
  };

  // 格式化日期为 YYYY-MM-DD
  const formatDate = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  // 格式化月份为 YYYY-MM
  const formatMonth = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    return `${year}-${month}`;
  };

  // 1. 支出分类分布饼图数据（按金额占比）
  const categoryPieData = useMemo(() => {
    const categoryMap: Record<string, number> = {};
    
    documents.forEach(doc => {
      if (doc.amount && doc.amount > 0) {
        const category = doc.userCategory || "其他";
        categoryMap[category] = (categoryMap[category] || 0) + doc.amount;
      }
    });

    const total = Object.values(categoryMap).reduce((sum, val) => sum + val, 0);
    
    return Object.entries(categoryMap)
      .map(([name, value]) => ({
        name,
        value: Number(value.toFixed(2)),
        percent: total > 0 ? Number(((value / total) * 100).toFixed(1)) : 0
      }))
      .sort((a, b) => b.value - a.value);
  }, [documents]);

  // 2. 支出趋势折线图数据（按日期）
  const trendLineData = useMemo(() => {
    const dateMap: Record<string, number> = {};
    
    documents.forEach(doc => {
      if (doc.amount && doc.amount > 0) {
        const date = parseDate(doc.issuedDate || doc.uploadTime);
        if (date) {
          const dateKey = formatDate(date);
          dateMap[dateKey] = (dateMap[dateKey] || 0) + doc.amount;
        }
      }
    });

    return Object.entries(dateMap)
      .map(([date, amount]) => ({
        date,
        amount: Number(amount.toFixed(2))
      }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [documents]);

  // 3. 子标签使用情况数据（数量 + 百分比）
  const tagTableData = useMemo(() => {
    const tagMap: Record<string, number> = {};
    
    documents.forEach(doc => {
      if (doc.tags && doc.tags.length > 0) {
        doc.tags.forEach(tag => {
          tagMap[tag] = (tagMap[tag] || 0) + 1;
        });
      }
    });

    const total = Object.values(tagMap).reduce((sum, val) => sum + val, 0);

    return {
      total,
      topTags: Object.entries(tagMap)
        .map(([tag, count]) => ({
          tag,
          count,
          percent: total > 0 ? Number(((count / total) * 100).toFixed(1)) : 0
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5) // 只显示前5个
    };
  }, [documents]);

  // 4. 月度对比数据（收入和支出）
  const monthlyComparisonData = useMemo(() => {
    const monthMap: Record<string, { income: number; expense: number }> = {};
    
    documents.forEach(doc => {
      if (doc.amount !== undefined && doc.amount !== null && doc.amount !== 0) {
        const date = parseDate(doc.issuedDate || doc.uploadTime);
        if (date) {
          const monthKey = formatMonth(date);
          if (!monthMap[monthKey]) {
            monthMap[monthKey] = { income: 0, expense: 0 };
          }
          
          // 判断是否为收入类
          if (doc.userCategory === "收入类") {
            // 收入类：确保金额为正数
            monthMap[monthKey].income += Math.abs(doc.amount);
          } else {
            // 其他分类：作为支出，确保金额为正数
            monthMap[monthKey].expense += Math.abs(doc.amount);
          }
        }
      }
    });

    const sortedMonths = Object.keys(monthMap).sort((a, b) => a.localeCompare(b));
    
    return sortedMonths.map((month, index) => {
      const data = monthMap[month];
      const net = data.income - data.expense;
      
      // 计算与上月的差异
      let diff: number | null = null;
      let diffPercent: number | null = null;
      if (index > 0) {
        const prevMonth = sortedMonths[index - 1];
        const prevData = monthMap[prevMonth];
        const prevNet = prevData.income - prevData.expense;
        diff = net - prevNet;
        if (prevNet !== 0) {
          diffPercent = Number(((diff / Math.abs(prevNet)) * 100).toFixed(1));
        }
      }

      return {
        month,
        income: Number(data.income.toFixed(2)),
        expense: Number(data.expense.toFixed(2)),
        net: Number(net.toFixed(2)),
        diff,
        diffPercent
      };
    });
  }, [documents]);

  // 统计信息
  const totalAmount = useMemo(() => {
    return documents
      .filter(doc => doc.amount !== undefined && doc.amount !== null && doc.amount > 0)
      .reduce((sum, doc) => sum + (doc.amount ?? 0), 0);
  }, [documents]);

  const totalDocuments = documents.length;
  const categoryCount = new Set(documents.map(doc => doc.userCategory)).size;

  // 饼图配置
  const pieConfig = {
    data: categoryPieData,
    angleField: "value",
    colorField: "name",
    radius: 0.8,
    label: {
      type: "outer",
      content: "{name}\n{value}元 ({percent}%)",
      style: {
        fontSize: 12
      }
    },
    interactions: [{ type: "element-active" }],
    legend: {
      position: "right" as const
    }
  };

  // 折线图配置
  const lineConfig = {
    data: trendLineData,
    xField: "date",
    yField: "amount",
    smooth: true,
    point: {
      size: 4,
      shape: "circle"
    },
    label: {
      style: {
        fill: "#666",
        fontSize: 12
      },
      formatter: (datum: any) => `￥${datum.amount.toFixed(2)}`
    },
    tooltip: {
      formatter: (datum: any) => ({
        name: "支出金额",
        value: `￥${datum.amount.toFixed(2)}`
      })
    },
    xAxis: {
      label: {
        autoRotate: true
      }
    },
    yAxis: {
      label: {
        formatter: (val: number) => `￥${val.toFixed(0)}`
      }
    }
  };

  // 子标签使用情况表格列定义
  const tagTableColumns: ColumnsType<typeof tagTableData.topTags[0]> = [
    {
      title: "排名",
      key: "rank",
      width: 60,
      align: "center" as const,
      render: (_: any, __: any, index: number) => index + 1
    },
    {
      title: "标签",
      dataIndex: "tag",
      key: "tag",
      width: 150
    },
    {
      title: "使用次数",
      dataIndex: "count",
      key: "count",
      width: 100,
      align: "right" as const,
      render: (value: number) => `${value}次`
    },
    {
      title: "占比",
      dataIndex: "percent",
      key: "percent",
      width: 100,
      align: "right" as const,
      render: (value: number) => `${value}%`
    }
  ];

  // 月度对比表格列定义
  const monthlyTableColumns: ColumnsType<typeof monthlyComparisonData[0]> = [
    {
      title: "月份",
      dataIndex: "month",
      key: "month",
      width: 100,
      fixed: "left"
    },
    {
      title: "收入",
      dataIndex: "income",
      key: "income",
      width: 120,
      align: "right" as const,
      render: (value: number) => (
        <span style={{ color: "#52c41a" }}>￥{value.toFixed(2)}</span>
      )
    },
    {
      title: "支出",
      dataIndex: "expense",
      key: "expense",
      width: 120,
      align: "right" as const,
      render: (value: number) => (
        <span style={{ color: "#ff4d4f" }}>￥{value.toFixed(2)}</span>
      )
    },
    {
      title: "净额",
      dataIndex: "net",
      key: "net",
      width: 120,
      align: "right" as const,
      render: (value: number) => (
        <span style={{ color: value >= 0 ? "#52c41a" : "#ff4d4f" }}>
          ￥{value.toFixed(2)}
        </span>
      )
    },
    {
      title: "差异",
      key: "diff",
      width: 150,
      align: "right" as const,
      render: (_: any, record: typeof monthlyComparisonData[0]) => {
        if (record.diff === null) {
          return <span style={{ color: "#999" }}>-</span>;
        }
        const isPositive = record.diff >= 0;
        return (
          <span>
            <span style={{ color: isPositive ? "#52c41a" : "#ff4d4f" }}>
              {isPositive ? "+" : ""}￥{record.diff.toFixed(2)}
            </span>
            {record.diffPercent !== null && (
              <Tag color={isPositive ? "green" : "red"} style={{ marginLeft: 8 }}>
                {isPositive ? "+" : ""}{record.diffPercent}%
              </Tag>
            )}
          </span>
        );
      }
    }
  ];

  return (
    <Row gutter={[16, 16]}>
      {/* 支出分类分布饼图 */}
      <Col xs={24} md={12}>
        <Card title="支出分类分布" loading={loading} variant="outlined" hoverable>
          {categoryPieData.length > 0 ? (
            <Pie {...pieConfig} />
          ) : (
            <Typography.Text type="secondary">暂无数据</Typography.Text>
          )}
        </Card>
      </Col>

      {/* 支出趋势折线图 */}
      <Col xs={24} md={12}>
        <Card title="支出趋势" loading={loading} variant="outlined" hoverable>
          {trendLineData.length > 0 ? (
            <Line {...lineConfig} />
          ) : (
            <Typography.Text type="secondary">暂无数据</Typography.Text>
          )}
        </Card>
      </Col>

      {/* 统计卡片 */}
      <Col xs={24} md={8}>
        <Card variant="outlined" hoverable loading={loading}>
          <Statistic 
            title="总支出" 
            value={totalAmount} 
            precision={2}
            prefix="￥"
          />
        </Card>
      </Col>
      <Col xs={24} md={8}>
        <Card variant="outlined" hoverable loading={loading}>
          <Statistic title="票据数量" value={totalDocuments} />
        </Card>
      </Col>
      <Col xs={24} md={8}>
        <Card variant="outlined" hoverable loading={loading}>
          <Statistic title="分类数量" value={categoryCount} />
        </Card>
      </Col>

      {/* 子标签使用情况表格 */}
      <Col xs={24} md={12}>
        <Card 
          title="子标签使用情况" 
          loading={loading} 
          variant="outlined" 
          hoverable
          extra={
            <Typography.Text type="secondary">
              总使用数：{tagTableData.total}次
            </Typography.Text>
          }
        >
          {tagTableData.topTags.length > 0 ? (
            <Table
              columns={tagTableColumns}
              dataSource={tagTableData.topTags}
              rowKey="tag"
              pagination={false}
              size="small"
            />
          ) : (
            <Typography.Text type="secondary">暂无标签数据</Typography.Text>
          )}
        </Card>
      </Col>

      {/* 月度对比表格 */}
      <Col xs={24} md={12}>
        <Card 
          title={monthlyComparisonData.length > 1 ? "月度收支对比" : "月度收支"} 
          loading={loading} 
          variant="outlined" 
          hoverable
        >
          {monthlyComparisonData.length > 0 ? (
            <Table
              columns={monthlyTableColumns}
              dataSource={monthlyComparisonData}
              rowKey="month"
              pagination={false}
              size="small"
              scroll={{ x: 600 }}
            />
          ) : (
            <Typography.Text type="secondary">暂无月度数据</Typography.Text>
          )}
        </Card>
      </Col>
    </Row>
  );
};

export default DashboardCharts;
