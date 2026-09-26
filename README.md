# intern-monitor

LLM / RL / 模型训练 / Agent 方向实习监控（法国 + 美国），部署在 Servitro (`/root/intern-monitor`)，systemd timer 每天 06:30 UTC 跑一次，有新增就发邮件。

- `monitor.py` 单文件、纯标准库。源：Ashby/Greenhouse/Lever/Workable 公开 API（~90 个看板）+ NVIDIA Workday + Amazon search.json + Google careers HTML + Apple HTML + Inria + LinkedIn guest API（FR/US 关键词，近 7 天）。
- 过滤：实习词（intern/stage/student researcher/co-op）× 主题词（标题命中=A，泛研究标题=B，ESN/咨询=C）× 地区（FR/US 正则）。
- 状态：`state.json`（见过的 URL），`latest_hits.json` / `latest_report.txt` 每次覆盖。
- 邮件：Servitro 封出站 SMTP，本机 `send()` 只是兜底。实际链路：报告同步到 `/opt/dingyuanying-chat/nginx/certbot-www/.well-known/acme-challenge/intern-7f3a-latest_report.txt`（公网 `http://dyy.youchun.tech/.well-known/acme-challenge/intern-7f3a-latest_report.txt`，云沙箱只能走域名 80/443），云 routine「Intern Monitor Mailer」(trig_01RHV8n795r8UPHvkpp3uwGe) 每天 07:15 UTC 取报告并 SMTP 发出（新增>0 或周一）。`secrets.env`（不入库）SMTP_USER / SMTP_PASS / MAIL_TO。
- 手动：`python3 monitor.py --dry --full --days 30` 干跑全量；`--full` 发全量邮件。
- 未覆盖：Meta（反爬）、Microsoft（API 404）、Kyutai（无岗位页）、Welcome to the Jungle。
