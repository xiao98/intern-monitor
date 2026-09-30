# intern-monitor

LLM / RL / 模型训练 / Agent 方向实习监控（法国 + 美国）。爬虫由 GitHub Actions（`.github/workflows/monitor.yml`）每天 05:17 UTC 跑一次，结果直接 commit 回本仓库；Servitro 上的 systemd timer（06:30 UTC）是旧链路 / 备用，两边同时开也不会冲突（`git_push` 会先合并远端）。有新增就发邮件。

- `monitor.py` 单文件、纯标准库。源：Ashby/Greenhouse/Lever/Workable 公开 API（~90 个看板）+ NVIDIA Workday + Amazon search.json + Google careers HTML + Apple HTML + Inria + LinkedIn guest API（FR/US 关键词，近 7 天）。
- 过滤：实习词（intern/stage/student researcher/co-op）× 主题词（标题命中=A，泛研究标题=B，ESN/咨询=C）× 地区（FR/US 正则）。
- 状态：`state.json`（见过的 URL），`latest_hits.json` / `latest_report.txt` 每次覆盖。
- 邮件：Servitro 和云沙箱都封出站 SMTP，本机 `send()` 只是兜底。实际链路：跑完 `git push` 到公开仓库 github.com/xiao98/intern-monitor（Servitro deploy key），云 routine「Intern Monitor Mailer」(trig_01RHV8n795r8UPHvkpp3uwGe) 每天 07:15 UTC 以该仓库为 source 读 `latest_report.txt`（云沙箱出站白名单只放行 GitHub 等默认域名，自有域名/IP 403），用 Gmail MCP `send_message` 发信（新增>0 或周一；正文>20KB 截断并附 GitHub 全文链接）。`secrets.env`（不入库）SMTP_USER / SMTP_PASS / MAIL_TO。
- 爬取（GitHub Actions）：`monitor.yml` 用 `GITHUB_TOKEN` 提交 `state.json` / `latest_hits.json` / `latest_report.txt` / `meta.json`；`Actions` 页可手动 `Run workflow`（可填 `--full` / `--days 30`）。全部源都失败时脚本退出码 1 且不覆盖旧报告（job 变红），git push 失败同样让 job 变红。可选在仓库 Secrets 配 `SMTP_USER` / `SMTP_PASS` / `MAIL_TO`，脚本会顺带直接发信。
- 排查「实习监控 — 爬虫未更新」邮件：看 GitHub Actions 最近一次 `intern-monitor` run 的日志 / `monitor-log` 附件；若仍用 Servitro，`systemctl status intern-monitor.timer` + `journalctl -u intern-monitor -n 50`。
- 手动：`python3 monitor.py --dry --full --days 30` 干跑全量；`--full` 发全量邮件。
- 未覆盖：Meta（反爬）、Microsoft（API 404）、Kyutai（无岗位页）、Welcome to the Jungle。
