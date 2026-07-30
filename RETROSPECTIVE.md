# 岗位仪表板 - 问题与规避复盘

> 整理日期：2026-07-29
> 用户环境：IE 浏览器（Windows）
> 部署：GitHub Pages (https://gitone-1.github.io/job-dashboard-1/)

---

## 一、今天遇到的核心问题

### 问题1：IE 浏览器顽固缓存（最严重）
**现象**：强制刷新、Ctrl+Shift+R 后仍然看到旧数据（29条而非65条）
**根因**：
- IE 缓存了 index.html 本身和 jobs.json
- fetch 加 `?_t=` 时间戳参数不足以突破 IE 缓存
- 加载逻辑先 fetch `./jobs.json`（相对路径），浏览器拿到缓存的旧文件就停了，不再尝试 GitHub Pages 源

**已修复**：
- ✅ 加载顺序改为优先 GitHub Pages 绝对路径
- ✅ 改用独立文件名 `jobs_v2.json`（旧缓存的 jobs.json 无法命中）
- ✅ HTML 加 `<meta http-equiv="Cache-Control" content="no-store">` 等 meta 标签
- ✅ `fetchStatusFromRemote` 加 XHR fallback（IE fetch CORS 缓存 bug）

**遗留问题**：用户每次打开仍可能需要用 `?v=xxx` 参数强制刷新

---

### 问题2：已标注状态刷新后丢失
**现象**：标记"不匹配"后刷新页面，状态变回"可投递"
**根因**：
- 状态存在 localStorage，用户清缓存时一起清掉了
- `fetchStatusFromRemote` 在 IE 下 fetch 失败，远程状态没加载到
- `restoreStatusFromStorage` 先远程后本地，远程失败就跳过了本地
- `btoa(unescape(encodeURIComponent(...)))` 在 IE 下对中文编码报错，同步到 GitHub 失败

**已修复**：
- ✅ 恢复逻辑改为先本地后远程覆盖
- ✅ 同步用 UTF-8 安全的 base64 编码函数
- ✅ 增加 XHR fallback

---

### 问题3：有效岗位筛选逻辑错误
**现象**：点"可投递"tab 只显示1个，但统计说28个
**根因**：`filters.status`（下拉框）和 `filters.tab`（标签）是独立的两个 if，会双重过滤
**已修复**：改为互斥逻辑（tab 优先，tab=all 时才用 status 下拉）

---

### 问题4：已截止岗位无法标不匹配
**现象**：昆山数智科技（已截止）点不匹配弹窗报错
**已修复**：已截止允许标不匹配/已关闭

---

### 问题5：已截止岗位出现在有效岗位
**现象**：昆山数智科技（已截止）在"有效岗位" tab 下出现
**已修复**：有效岗位默认排除 不匹配+已关闭+已投递+已截止

---

### 问题6：更新数据后状态丢失（下次更新才会暴露）
**现象**：尚未发生，但 pipeline 完全不读 user_status.json
**已修复**：pipeline 新增 restore_user_status，更新后自动恢复用户标注

---

### 问题7：自动爬虫（Playwright）在沙箱中 EPIPE 崩溃
**现象**：2026-07-30 运行 `pipeline.py` 更新时，步骤 [1/5] 大厂 API 抓取阶段 node 子进程抛出 `Error: write EPIPE`，整个 Python 进程崩溃，未写入任何数据
**根因**：
- `api_sources.py`、`scraper_boss.py`、`scraper_guopin.py`、`scraper_wechat.py` 均依赖 Playwright 启动 Chromium；沙箱环境下 Chromium 子进程不稳定，`socket` 上的 `error` 事件未被 try/except 捕获，直接杀进程
- `scraper_liepin.py` 虽优先用 requests，但失败后 fallback 到 Playwright，同样会崩

**已修复（规避方案）**：
- ✅ 放弃依赖 Playwright 的自动爬虫，改用 **WebSearch / WebFetch 定向采集**真实岗位
- ✅ 新增 `update_manual.py`：读取 `data/new_jobs_YYYYMMDD.json` 种子文件，复用 `DedupEngine` / `MatchEngine` / `restore_user_status` / `update_index_data_ref`，完成去重→匹配→状态恢复→版本化写入
- ✅ **关键修正**：只对新岗位计算匹配度，**保留现有岗位的原有（前端算法）匹配度**，避免 Python 匹配引擎与前端算法分差过大导致现有岗位被误判 <50% 而遭删除
- ✅ 运行方式：`python3 update_manual.py`（写入）/ `--dry-run`（试运行）

**后续更新 SOP**：
1. 用 WebSearch 按目标城市+岗位定向搜新鲜岗位（优先补无锡/上海/绍兴/湖州/嘉兴等空白城市）
2. 把核实过的岗位写入 `data/new_jobs_YYYYMMDD.json`（字段与 jobs.json 一致）
3. `python3 update_manual.py --dry-run` 确认新增数量与匹配度
4. `python3 update_manual.py` 正式写入并自动版本化
5. `git add` + `git commit` + `git push` 到 GitHub Pages
6. 给用户带 `?v=日期` 参数的链接

---

## 二、根本原因分析

| 维度 | 问题 |
|------|------|
| 浏览器兼容 | 项目用了大量 ES6+ 特性，未针对 IE 做兼容处理 |
| 缓存策略 | 完全依赖浏览器默认缓存，没有版本化资源管理 |
| 状态持久化 | 云端同步依赖 GitHub Token，且 IE 编码有 bug |
| 筛选逻辑 | tab 和 status 过滤器设计冲突 |
| 数据更新 | 更新流水线没有纳入用户状态保留 |

---

## 三、长期规避措施

### A. 缓存规避（代码层）
1. **数据文件版本化**：每次更新数据用新文件名（jobs_v2.json → jobs_v3.json...）
2. **HTML 禁用缓存 meta 标签**（已加）
3. **fetch 始终加时间戳**（已加）

### B. 状态持久化（架构层）
1. 用户状态默认同步到 GitHub（无需 Token 的方案待开发）
2. 恢复逻辑：本地优先 + 远程覆盖（已改）
3. 更新流水线强制恢复用户状态（已实现）

### C. IE 兼容性（代码层）
1. 避免使用 IE 不支持的 API（fetch cache:no-store、btoa 中文编码）
2. 关键操作提供 XHR fallback
3. **建议用户迁移到 Edge/Chrome**（IE 已停止支持）

### D. 操作流程（用户层）
1. 更新岗位后，用 `?v=日期` 参数打开页面强制刷新
2. 标注状态后点"☁️ 同步状态到云端"确认保存
3. 定期用 Edge/Chrome 打开验证数据完整性

---

## 四、给用户的操作建议

1. **换浏览器**：强烈建议用 Edge 或 Chrome 替代 IE，体验更流畅
2. **打开方式**：用 `https://gitone-1.github.io/job-dashboard-1/index.html?v=今天日期` 打开
3. **标注后同步**：标完一批不匹配后，点工具栏「☁️ 同步状态到云端」按钮
4. **更新后验证**：我说更新完成后，用带参数的链接打开确认数据

---

*本文档每次遇到新问题后更新*
