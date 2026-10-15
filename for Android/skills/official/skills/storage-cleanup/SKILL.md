---
name: storage-cleanup
description: 用户说手机空间不够、想清理存储、找大文件或重复截图、删旧安装包时使用。先列清单，确认后才删。
---
# 存储清理

1. 概况：`android_action` open_page storage，读总容量、已用和各分类大小。
2. 找可以清理的文件（用 run_terminal，命令只读）：
   - 大文件：`find /storage/emulated/0 -type f -size +100M 2>/dev/null | head -50`，再对结果 `ls -l` 看大小和日期；
   - 下载目录里的安装包：`find /storage/emulated/0/Download -name "*.apk"`；
   - 截图：`ls -l /storage/emulated/0/DCIM/Screenshots /storage/emulated/0/Pictures/Screenshots 2>/dev/null | tail -100`，按日期看 3 个月以前的；
   - 各文件夹大小：`du -sh /storage/emulated/0/* 2>/dev/null | sort -h | tail -15`。
   提示没有权限时：告诉用户在系统设置里给 Agent Workspace「所有文件访问权限」，或只清理他指定的文件夹。
   查看时只读：系统存储页、应用信息页里的「清除缓存」「清除数据」「清理」「删除」等按钮一律不点，哪怕只是缓存。
3. 列清单给用户：每类的文件数、合计大小、举几个例子（文件名、大小、日期），并估算一共能省多少空间。微信、QQ 的聊天文件只建议在 App 自己的「存储空间清理」里清，不要直接删它们的文件夹。
4. 用户确认要删哪些后再删：逐类用 run_terminal 删除（每条删除命令都会请用户批准），删之前再说一遍要删的范围。照片和视频只删用户明确点名的。
5. 删完再看一次 open_page storage，回复清理前后的可用空间。

绝不删除：DCIM 里的照片视频（除非用户点名）、Android/data、文档和用户自己的文件夹。
