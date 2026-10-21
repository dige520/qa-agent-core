-- ==============================================================================
-- Open-Core 知识库结构化数据库契约 (Schema Contract)
-- 适用引擎: DuckDB In-Memory / SQLite / Text-to-SQL
-- 定义统一数据实体与分析视图，杜绝大模型 SQL 生成幻觉
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. 历史缺陷表 (historical_bugs)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historical_bugs (
    id                 INTEGER,           -- 自增行号标识
    title              VARCHAR NOT NULL,  -- 缺陷标题 / 核心现象描述
    description        VARCHAR,           -- 缺陷详细复现步骤与上下文描述
    device_model       VARCHAR,           -- 涉及机型 / 硬件平台
    discovered_version VARCHAR,           -- 发现版本
    fixed_version      VARCHAR,           -- 修复版本
    attachment         VARCHAR,           -- 附件说明
    priority           VARCHAR,           -- 优先级 (High, Medium, Low)
    severity           VARCHAR,           -- 严重程度 (致命, 严重, 一般, 轻微)
    module             VARCHAR,           -- 所属业务模块
    owner              VARCHAR,           -- 责任开发人员
    occurred_at        VARCHAR,           -- 发生时间
    progress           VARCHAR,           -- 修复进展与排查结论
    status             VARCHAR,           -- 当前状态 (已关闭, Closed, 待验证)
    verifier           VARCHAR            -- 验收验证人
);

-- ------------------------------------------------------------------------------
-- 2. 测试用例全景表 (test_cases)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_cases (
    case_id            VARCHAR,           -- 用例编号
    title              VARCHAR NOT NULL,  -- 用例场景名称 / 测试标题
    module             VARCHAR,           -- 所属模块
    product            VARCHAR,           -- 产品线归属
    priority           VARCHAR,           -- 优先级 (P0, P1, P2)
    steps              VARCHAR,           -- 详细操作步骤
    expected_result    VARCHAR,           -- 预期结果 / 判定准则
    actual_result      VARCHAR,           -- 实际测试执行结果
    status             VARCHAR,           -- 执行状态 (PASS, FAIL, Untested, Blocked)
    notes              VARCHAR,           -- 备注 / 关键断言日志
    source_file        VARCHAR            -- 来源文件相对路径
);

-- ------------------------------------------------------------------------------
-- 3. 常用便捷分析视图 (Analytical Views)
-- ------------------------------------------------------------------------------

-- 视图 A: 致命级 (Fatal) 高危缺陷视图 (防回归排查专用)
CREATE OR REPLACE VIEW v_fatal_bugs AS
SELECT 
    id,
    device_model,
    discovered_version,
    title,
    description,
    fixed_version,
    owner,
    status
FROM historical_bugs
WHERE severity IN ('致命', 'Fatal', 'Crash', 'Blocker')
ORDER BY id DESC;

-- 视图 B: P0 级冒烟基线用例视图 (发版准入专用)
CREATE OR REPLACE VIEW v_p0_smoke_cases AS
SELECT 
    case_id,
    product,
    module,
    title,
    steps,
    expected_result,
    status,
    source_file
FROM test_cases
WHERE priority IN ('P0', 'Blocker')
ORDER BY product, module, case_id;

-- 视图 C: 模块缺陷分布统计视图
CREATE OR REPLACE VIEW v_module_bug_stats AS
SELECT 
    module,
    COUNT(*) AS total_bugs,
    SUM(CASE WHEN severity IN ('致命', 'Fatal') THEN 1 ELSE 0 END) AS fatal_bugs,
    SUM(CASE WHEN status IN ('已关闭', 'Closed') THEN 1 ELSE 0 END) AS closed_bugs
FROM historical_bugs
GROUP BY module
ORDER BY total_bugs DESC;
