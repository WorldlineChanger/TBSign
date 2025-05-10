# 贴吧签到Github Action版

## 今日签到状态

![Baidu Tieba Auto Sign](https://github.com/WorldlineChanger/TBSign/workflows/Baidu%20Tieba%20Auto%20Sign/badge.svg)

## 使用说明

1. Fork 本仓库，然后点击你的仓库右上角的 Settings，找到 Secrets 这一项，添加一个库秘密变量。其中 `BDUSS` 存放你的 BDUSS。支持同时添加多个帐户，BDUSS 之间用 `#` 隔开即可。

2. 设置好环境变量后点击你的仓库上方的 `Actions` 选项，第一次打开需要点击 `I understand...` 按钮，确认在 Fork 的仓库上启用 GitHub Actions 。

3. 任意发起一次commit，可以参考下图流程修改readme文件。

- 打开`README.md`，点击修改按钮
- 修改任意内容，这里在末尾插入了空格。移动到最下面，点击提交。

4. 至此自动签到就搭建完毕了，可以再次点击`Actions`查看工作记录，如果有`Baidu Tieba Auto Sign`则说明workflow创建成功了。点击右侧记录可以查看详细签到情况。

MODERATOR_BDUSS_INDEX：指定吧主BDUSS账号（从0开始）
MODERATED_BARS：考核贴吧名称，用英文逗号分隔
TARGET_POST_IDS：对应贴吧的测试用帖子ID，用英文逗号分隔（需与MODERATED_BARS顺序严格对应）

BDUSS：账号cookie，用#分隔多个账号
HOST：邮箱SMTP服务器地址
FROM：发件邮箱地址
TO：收件邮箱地址，多个用#分隔
AUTH：邮箱授权码
