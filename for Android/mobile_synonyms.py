# ruff: noqa: RUF001 -- the lexicon is Chinese.
"""Built-in synonym groups for knowledge-base search.

Keyword search misses a question that names a thing differently from the document (房租 vs
租金). Each line below is one group of words that people use for the same thing in everyday
documents: contracts, bills, manuals, medical leaflets, work and school papers. Search treats
a word of a group as a weaker match for the others. Single characters are left out: they occur
inside too many unrelated words, and so do pairs like 天天, which turns up across the word
boundary in 今天天气. Users add their own groups on the Knowledge page.
"""

from __future__ import annotations

import re
import unicodedata

BUILTIN = """
房租 租金 月租 租费
押金 保证金 订金 定金
价格 价钱 售价 费用 金额 多少钱 收费 报价 价位
付款 支付 缴费 交费 缴纳 付费 结账 买单
退款 退钱 退费 返还 退还 退回 返款
工资 薪水 薪资 薪酬 报酬 月薪
发票 票据 收据 凭证
折扣 优惠 打折 减免
利息 利率 息费
贷款 借款 借贷
罚款 违约金 罚金 滞纳金
开支 花费 支出 开销
税费 税款 纳税 交税 税金
奖金 提成 分红
账单 对账单 消费明细
到期 期满 截止 过期 届满
期限 有效期 时限
延期 推迟 延后 顺延 延长
提前 预先 事先
每天 每日
每月 每个月 按月 月度
每年 每一年 按年 年度
合同 协议 合约 契约
解约 退租 解除合同 终止合同
签约 签订 签署 签字
续租 续约 续签
甲方 出租方 房东 出租人
乙方 承租方 租客 承租人 房客
条款 规定 约定 条例
赔偿 赔付 补偿 理赔 赔款
责任 义务 职责
纠纷 争议 争端
起诉 诉讼 打官司
维修 修理 修复 检修 修好
损坏 故障 坏了 坏掉 毁坏 破损 失灵 出问题
保修 质保 保固 售后
换货 更换 替换 调换
退货 退换
安装 装机 组装
说明书 手册 使用指南 用户手册 使用说明
清洁 清洗 清理 打扫 除垢 除污
充电器 电源适配器 充电头
电池 电量 续航
开机 启动 打开 开启
关机 关闭 关掉
重启 重新启动 重置 复位 恢复出厂
设置 配置 设定
密码 口令 验证码
账号 账户 帐号 帐户 用户名
登录 登陆 登入
注册 开户
删除 删掉 去掉 移除 清除
网络 联网 上网 无线网
手机 电话机 移动电话 智能手机
电脑 计算机 笔记本 台式机
屏幕 显示屏 显示器
噪音 噪声 异响 响声
医生 大夫 医师
医院 诊所 卫生院
药品 药物 用药 药剂
剂量 用量 用法用量
副作用 不良反应
发烧 发热 高烧 体温高
感冒 着凉 流感
头疼 头痛
肚子疼 腹痛 胃疼 胃痛
过敏 过敏反应
体检 检查 化验
症状 病症 表现
治疗 医治 疗法 诊治
怀孕 妊娠 孕期
孩子 儿童 小孩 宝宝 婴儿 小朋友
老人 老年人 长辈
禁忌 忌口 注意事项
公司 单位 企业 机构
老板 领导 上司 经理 主管
同事 员工 职员
上班 工作日 办公
请假 休假 假期 放假
加班 延时工作
会议 开会 例会 周会
报告 汇报 总结
考试 测验 考核
成绩 分数 得分
老师 教师 讲师 导师
作业 功课 练习题
课程 课堂 上课
学校 学院 大学
简历 履历
面试 应聘 招聘
入职 报到
离职 辞职 辞退 解雇 裁员
社保 社会保险 五险一金
公积金 住房公积金
地址 住址 位置 地点 所在地
电话 联系方式 手机号 号码 联系电话
邮箱 电子邮件 邮件地址
航班 机票 飞机
火车 高铁 动车 列车
汽车 车辆 小车 轿车
停车 泊车 车位
酒店 宾馆 旅馆 住宿
签证 护照
门票 入场券
预订 预定 预约
取消 撤销 作废
房子 房屋 住房 房产 住宅
水电费 水费 电费 燃气费
物业费 管理费 物业
装修 翻新 装潢
空调 冷气
快递 包裹 物流
外卖 送餐 配送
上限 最多 最高 最大
下限 最少 最低 最小
规则 要求 标准
方法 办法 方式 步骤 流程 做法
原因 理由 缘故
注意 留意 小心 当心
允许 准许 许可
禁止 不得 不准 不允许 不许
必须 务必 应当 应该
免费 不收费 不要钱
联系 联络 沟通
通知 告知 提醒
投诉 举报 反映
客服 服务热线 热线电话
申请 办理 提交
审批 批准 审核
证件 身份证 证明
照片 图片 相片 图像
视频 录像 影片
文件 文档 资料 材料
姓名 名字 名称
生日 出生日期
price cost fee charge amount
refund reimbursement repayment
repair fix servicing maintenance
broken damaged faulty defective
warranty guarantee
deposit security
rent rental lease
contract agreement
terminate cancel cancellation
delivery shipping shipment
manual guide handbook instructions
clean wash descale
doctor physician
medicine medication drug
salary wage income
meeting conference
deadline due
error fault failure
start begin launch
buy purchase order
car vehicle automobile
phone mobile cellphone
computer laptop pc
address location
email mail
password passcode
"""

_SEPARATORS = re.compile(r"[\s,，、;；=/|]+")
MAX_USER_GROUPS = 200
MAX_WORD_CHARS = 20


class SynonymError(ValueError):
    """A synonym list the user has to correct."""


def normalize(word: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", word).casefold().split())


def parse_groups(text: str, *, strict: bool = False) -> list[tuple[str, ...]]:
    """Groups of two or more distinct words, one group per line."""
    groups: list[tuple[str, ...]] = []
    for number, line in enumerate(str(text or "").splitlines(), 1):
        words = [normalize(word) for word in _SEPARATORS.split(line) if word.strip()]
        words = list(dict.fromkeys(word for word in words if word))
        if not words:
            continue
        if strict:
            if len(words) < 2:
                raise SynonymError(f"line {number} needs at least two words")
            if any(len(word) > MAX_WORD_CHARS for word in words):
                raise SynonymError(
                    f"line {number} has a word longer than {MAX_WORD_CHARS} characters"
                )
            if any(len(word) < 2 for word in words):
                raise SynonymError(f"line {number} has a single character; use whole words")
        words = [word for word in words if 2 <= len(word) <= MAX_WORD_CHARS]
        if len(words) >= 2:
            groups.append(tuple(words))
    if strict and len(groups) > MAX_USER_GROUPS:
        raise SynonymError(f"at most {MAX_USER_GROUPS} synonym groups")
    return groups


def lexicon(user_text: str = "") -> dict[str, frozenset[str]]:
    """Each word mapped to the other words of every group it belongs to."""
    related: dict[str, set[str]] = {}
    for group in (*parse_groups(BUILTIN), *parse_groups(user_text)):
        for word in group:
            related.setdefault(word, set()).update(other for other in group if other != word)
    return {word: frozenset(others) for word, others in related.items()}


BUILTIN_GROUPS = len(parse_groups(BUILTIN))
