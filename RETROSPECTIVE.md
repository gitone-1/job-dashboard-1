# 岗位仪表板 - 问题与规避复盘

> 整理日期：2026-07-30（持续更新）
> 用户环境：Windows，曾用 IE，现已切到 Edge/Chrome
> 部署：GitHub Pages (https://gitone-1.github.io/job-dashboard-1/)
> ⚠️ 重要经验：遇到「按钮全失效 / 列表空白」，先查「脚本能否运行（语法+渲染）」，再谈「浏览器兼容」。兼容性永远是第二位问题。

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

### 问题8：全浏览器 JS 语法错误（多余右花括号）——本次「-- / 数据加载中 / 按钮全失效」的真正根因

> 时间：2026-07-30。这是用户反馈「总岗位数两个杠、数据加载中、点任何按钮都没反应」的**唯一真因**。

**现象**：
- 用 Edge/Chrome 打开后，总岗位数、匹配度显示「`--`」，状态区显示「数据加载中…」
- 点「可投递 / 已投递 / 已截止 / 匹配度滑块」等**任何按钮都无反应**
- 页面静态骨架（标题、筛选栏）可见，但没有任何数据、没有任何交互

**根因（经 Playwright 真实浏览器捕获 `[PAGEERROR]` 定位）**：
- `index.html` 内联 `<script>` 中存在一个**多余的右花括号 `}`**（位于 `fetchStatusFromRemote` 函数体结束之后），导致整段脚本在解析阶段抛出 `SyntaxError: Unexpected token '}'`
- 脚本一旦解析失败，浏览器**不会执行其中任何一行**：所有事件监听都不会绑定（按钮失效）、`renderJobs` 永不运行（列表空白）、统计数字停留在占位符 `--` / 「数据加载中」
- 这是**全浏览器**灾难，与 IE / Edge / Chrome 无关——只要脚本有语法错误，所有浏览器都会静默失败

**为什么没被提前发现**：
- 此前每次改完 `index.html` 直接 `git push`，**没有「发布前语法校验」这一步**
- 该 `}` 来自早期一次手动编辑（git blame 指向 2026-07-27 的提交 `fe9a4665`），长期潜伏，直到用户反馈才暴露
- 没有任何自动化的 `node --check` / 浏览器渲染校验门禁

**为什么被误判（浪费一轮）**：
- 最初看到「按钮无反应 + 旧数字」，先入为主归因为 IE 缓存 / IE 兼容性，让用户切换 Edge/Chrome
- 但用户在 Edge 下症状**完全一致**，才用 Playwright 抓到真实错误。结论：**先查脚本能否运行，再谈浏览器兼容**——兼容性是第二位问题

**已修复**：
- ✅ 删除多余 `}`，整段脚本恢复正常（已验证：无 pageerror，72 岗位，5 有效，列表渲染，tab / 滑块可用）
- ✅ 新增 **`verify_before_push.py`**：发布前强制 `node --check` 内联脚本 + Playwright 真实渲染校验，任一不过即**阻断 push**（已用注入 `}` 的副本做过负向测试，能精准拦下）
- ✅ 新增 **`publish.sh`**：统一发布入口，先校验后推送，杜绝「忘记校验直接 push」
- ✅ **附带修正**：统计卡「总岗位数」此前误用了 `activeJobs.length`（有效岗位数，显示 5），与「总岗位数」标签不符；已改为 `JOBS.length`（真实总量 72），与标签含义一致

**为此事向用户致歉**：上一轮让我把浏览器从 IE 换成 Edge/Chrome 是**误判**，浪费了你一次操作。真正原因与浏览器无关，是这个多余的 `}`。现已从机制上避免再犯（见下方「六、发布前强制校验」）。

---

## 二、根本原因分析

| 维度 | 问题 |
|------|------|
| 浏览器兼容 | 项目用了大量 ES6+ 特性，未针对 IE 做兼容处理 |
| 缓存策略 | 完全依赖浏览器默认缓存，没有版本化资源管理 |
| 状态持久化 | 云端同步依赖 GitHub Token，且 IE 编码有 bug |
| 筛选逻辑 | tab 和 status 过滤器设计冲突 |
| 数据更新 | 更新流水线没有纳入用户状态保留 |
| **发布前校验** | **改完即 push，无语法 / 渲染灰度校验，一个 `}` 就能让整段脚本静默失败、全浏览器按钮失效** |

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

### E. 发布前强制校验（代码层 · 防回归 · 最重要）
1. **改完 `index.html` 绝不直接 `git push`**，必须先过 `verify_before_push.py`
2. `verify_before_push.py` 做两件事：
   - **【强制】** 抽取内联 `<script>` 跑 `node --check` —— 拦下所有语法错误（含多余 `}`）
   - **【可选增强】** 用 Playwright headless 真实渲染，断言：无 pageerror、`#statTotal` 不是 `--`、`#jobList` 有子节点
3. 任一步失败 → 脚本退出码非 0 → **禁止推送**，先修再发
4. 日常发布走统一入口 `./publish.sh "提交说明"`，它内部先跑校验再 push
5. 负向测试已验证：注入多余 `}` 时脚本精确报错并阻断（exit 1）

---

## 四、给用户的操作建议

1. **换浏览器**：强烈建议用 Edge 或 Chrome 替代 IE，体验更流畅
2. **打开方式**：用 `https://gitone-1.github.io/job-dashboard-1/index.html?v=今天日期` 打开
3. **标注后同步**：标完一批不匹配后，点工具栏「☁️ 同步状态到云端」按钮
4. **更新后验证**：我说更新完成后，用带参数的链接打开确认数据

---

---

## 五、用户永久需求 / 排除项

> 记录用户长期有效的偏好，更新岗位时必须遵守。

### 永久排除：上海
- **生效日期**：2026-07-30
- **用户原话**：「未来再让你帮我更新岗位，都不要给我看上海的了，把上海从需求里面去除」
- **已落地改动**：
  1. `config.yaml` → `cities` 列表移除「上海」（流水线预过滤的权威依据）
  2. `resume_profile.json` → `targetCities` 移除「上海」
  3. `pipeline/wechat_sources.py` → `USER_PROFILE.target_cities` 与 `CORE_SOURCES` 国资小新 `target_cities` 均移除「上海」
- **既有数据**：现有 6 个上海岗位已全部标记为「不匹配」（经 `exclude_shanghai.py`），并从"有效岗位"隐藏；其状态已同步云端，`restore_user_status` 会在每次更新后重新应用，不会回弹。
- **未来更新自动生效**：`update_manual.py` 的预过滤 `should_include(job, config)` 会因 `city='上海' ∉ cities` 直接丢弃任何上海岗位，无需每次手动处理。

---

## 六、发布前强制校验（防回归 · 问题8 的永久对策）

> 这是为避免「问题8（多余花括号导致全浏览器失效）」再次上线而建立的机制。每次改动 `index.html` 后、推送前**必须**执行。

### 文件
- `verify_before_push.py` —— 校验脚本（语法 `node --check` + 可选 Playwright 渲染）
- `publish.sh` —— 统一发布入口（先 `verify_before_push.py`，通过后 `git add/commit/push`）

### 使用方式
```bash
# 方式 A：agent / 开发者日常发布（推荐）
./publish.sh "更新说明"

# 方式 B：只校验不推送
python3 verify_before_push.py
# 想校验别的文件：python3 verify_before_push.py /path/index.html
```

### 通过标准（必须全部满足，否则 exit 1 阻断）
1. 内联 `<script>` 通过 `node --check`（无 `SyntaxError`）
2. （若装了 Playwright）页面真实渲染：无 pageerror、`#statTotal` ≠ `--`、`#jobList` 子节点 > 0

### 为什么这能防住问题8
- 问题8 的本质是「整段脚本解析失败 → 静默不执行」。`node --check` 在解析阶段就报错，比任何浏览器都早、比任何用户反馈都早。
- 已用「注入多余 `}` 的副本」做负向测试：脚本精准报 `SyntaxError: Unexpected token '}'` 并 exit 1，证明门禁有效。
- Playwright 渲染校验作为第二道防线，能拦下「语法通过但运行时崩溃 / 数据加载死循环」这类更隐蔽的问题。

### 硬性规则（写给我自己 / 后续维护者）
> **任何对 `index.html` 的改动，未跑 `verify_before_push.py` 并看到「✅ 全部校验通过」之前，绝不允许 `git push`。**

*本文档每次遇到新问题后更新*
