# StarCape · 我的数字书桌

个人导航和英语精读站，沿用 GitHub Pages。无需前端依赖。

## 本地打开与管理

需要 Python 3.10+。在仓库目录运行：

```sh
python scripts/server.py
```

终端打印首页地址和带临时令牌的管理地址。管理服务仅监听 `127.0.0.1:8765`；关闭终端即可停止。Windows 可使用 `py scripts/server.py`。

后台支持上传 HTML、编辑标题/导读/期次/更新日/来源、替换 HTML、删除文章、导入 Chrome/Edge 导出的书签并逐项筛选、移除导航网站。文件保存到 `readings/`，索引在 `data/articles.json`，导航在 `data/links.json`。写操作自动备份至 `.runtime/trash/`，不进入 Git。恢复时把相应 JSON 和 HTML 复制回原位置。

Chrome 书签管理器或 Edge 收藏夹菜单 → 导出收藏夹/书签为 HTML → 后台选择文件 → 勾选想加入的项目 → 保存。没有读取浏览历史或按访问频率排序的宣称。

## 计数和日期

- 精读数量来自实际 HTML 索引。
- 期次表示学习材料所属日期；更新日历按 `updated` 统计当前收录文章，不是永久审计日志。修改或删除会相应改变统计。
- 八期精读从历史对话中的模板、生成代码恢复，保留正文、词性颜色、红框、练习；2026-11-08 至 11-11 为 11 日补刊，真实更新日为 11 日。
- “本机查看”是当前浏览器打开阅读器的次数，刷新也算一次；收藏和次数保存在 localStorage，不跨设备同步。禁用存储时显示提示。
- 阅读器 iframe 隔离 HTML，脚本禁用。原有内页继续使用旧样式。
- GitHub Pages 没有后端。公开管理页仅显示本机管理说明；要实现远程管理与全站访问量，需要另行部署持久化服务及登录认证。

## 验证、构建和推送

```sh
python -m unittest discover -s tests -v
python scripts/build.py
git add index.html reader.html admin.html assets data readings scripts tests docs README.md package.json .gitignore .github
git commit -m "Update StarCape content"
git push origin HEAD:main
```

首次使用工作流时，在仓库 Settings → Pages 选择 GitHub Actions。之后 main 推送触发测试、构建和发布。若仓库仍使用从 main 根目录发布，静态入口同样可用，但推荐 Actions 以仅发布 dist 中的页面资源。构建产物不含后台程序、备份或会话记录。

使用管理功能导入文章后需要提交相关 HTML 和 JSON，推送才会更新公开网站。不要提交 `.runtime`。

[改版提示词、环境与实施计划](docs/REVAMP.md)
