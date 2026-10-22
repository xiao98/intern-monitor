# intern-monitor

扩散模型 / LLM / Agent / RL 方向实习监控（法国 + 欧洲 + 美国）+ 目标调研。爬虫由 GitHub Actions（`.github/workflows/monitor.yml`）每天跑一次（cron 05:17 UTC，实际常排队到 09–11 UTC），结果直接 commit 回本仓库，网页 https://xiao98.github.io/intern-monitor/ 读同一份数据。不发邮件（2026-10 起只看网页）。Servitro 上的 systemd timer 是旧链路，2026-10 起推送被拒、已不需要。

- `monitor.py` 单文件、纯标准库。源：Ashby/Greenhouse/Lever/Workable 公开 API（~90 个看板）+ NVIDIA Workday + Amazon search.json + Google careers HTML + Apple HTML + Inria + LinkedIn guest API（FR/US 关键词，近 7 天）。
- 过滤：实习词（intern/stage/student researcher/co-op）× 方向标签 `D_PAT`（diff/llm/agent/rl；标题命中=A，方向只在描述里=B，ESN/咨询=C，打不上任何方向=丢弃）× 地区（FR/EU/US 正则）；只招 PhD 的（标题写 PhD 且没写 Master，或描述要求在读博士）剔除。
- 调研：`index.html` 里的 `SURVEY_CO` / `SURVEY_LAB` 常量（企业 / 课题组 × 转正线 / 读博线），改目标就改那里。
- 状态：`state.json`（见过的 URL），`latest_hits.json` / `latest_report.txt` 每次覆盖。
- 邮件：已停用（云 routine「Intern Monitor Mailer」已不存在，仓库也没配 SMTP secrets）。`send()` 代码保留，配了 `SMTP_USER` / `SMTP_PASS` / `MAIL_TO` 才会发。
- 爬取（GitHub Actions）：`monitor.yml` 用 `GITHUB_TOKEN` 提交 `state.json` / `latest_hits.json` / `latest_report.txt` / `meta.json`；`Actions` 页可手动 `Run workflow`（可填 `--full` / `--days 30`）。全部源都失败时脚本退出码 1 且不覆盖旧报告（job 变红），git push 失败同样让 job 变红。可选在仓库 Secrets 配 `SMTP_USER` / `SMTP_PASS` / `MAIL_TO`，脚本会顺带直接发信。
- 排查「实习监控 — 爬虫未更新」邮件：看 GitHub Actions 最近一次 `intern-monitor` run 的日志 / `monitor-log` 附件；若仍用 Servitro，`systemctl status intern-monitor.timer` + `journalctl -u intern-monitor -n 50`。
- 手动：`python3 monitor.py --dry --full --days 30` 干跑全量；`--full` 发全量邮件。
- 未覆盖：Meta（反爬）、Microsoft（API 404）、Kyutai（无岗位页）、Welcome to the Jungle。
