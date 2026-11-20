package com.agentworkspace.mobile.automation

/**
 * The payment firewall: the agent never pays, transfers, withdraws or places an order, whatever
 * the mode and even with confirmed=true; the user finishes those steps on the phone. Fixed rules,
 * not the model's judgment. 支付宝 is an app, not a payment.
 */
internal object PaymentFirewall {
    /** Words on a control that pays or moves money (spaces removed). */
    private val CONTROL = Regex(
        "支付(?!宝)|付款|买单|转账|提现|充值|免密|确认收款|提交订单|立即购买|确认购买|确认下单|" +
            // Orders, checkout, memberships, red packets, tips; 确认收货 releases the held payment.
            "立即下单|去下单|一键下单|马上购买|购买(?!记录|须知|说明|历史)|结算|抢购|开通|续费|兑换|打赏|发红包|" +
            "塞钱进红包|确认收货|" +
            "(?i)(pay|checkout|placeorder|ordernow|buy(?!er)|purchase(?!history|d)|subscribe|sendmoney|donate|" +
            "transfer|withdraw|topup)"
    )

    /** Words that only show on a payment step: a payment password sheet, a payment or transfer confirmation. */
    private val SCREEN = Regex(
        "支付密码|输入密码完成支付|确认支付|确认付款|确认转账|转账金额|付款金额|指纹支付|面容支付|刷脸支付|" +
            "(?i)(paymentpassword|confirmpayment|confirmtransfer)"
    )

    /** The payment password sheet itself: counted in a text of any length. */
    private val PASSWORD_SHEET = Regex("支付密码|输入密码完成支付|(?i)paymentpassword")

    /** Amounts and currency signs: "Confirm and pay ¥1,299.00" is a button however long its price. */
    private val AMOUNT = Regex("[¥￥$€£]?[0-9][0-9.,]*|[¥￥$€£]")

    /** A control's words: at most this long (CJK characters; a Latin letter counts half). */
    private const val CONTROL_LENGTH = 16.0

    /** A title, dialog heading or button: longer texts are paragraphs or chat that merely mention a step. */
    private const val SCREEN_LENGTH = 20.0

    private fun plain(label: String?) = label?.filterNot { it.isWhitespace() }.orEmpty()

    /**
     * How long [text] reads: a CJK character counts 1, a Latin letter or digit half, since words
     * run together once spaces are taken out ("Proceedtocheckout").
     */
    fun weight(text: String): Double = text.sumOf { if (it.code < 0x2E80) 0.5 else 1.0 }

    /**
     * The words to judge a control by: the whole label, and each part of a label made of several
     * inner ones ("合计¥1,299.00 / 提交订单"), with amounts taken out.
     */
    private fun controlTexts(label: String?): List<String> {
        val raw = label.orEmpty()
        return (listOf(raw) + raw.split(" / ")).map { plain(it).replace(AMOUNT, "") }.distinct()
    }

    fun paysOrMovesMoney(label: String?): Boolean = controlTexts(label).any {
        it.isNotEmpty() && weight(it) <= CONTROL_LENGTH && CONTROL.containsMatchIn(it)
    }

    fun marksPaymentScreen(label: String?): Boolean = plain(label).let {
        it.isNotEmpty() && ((weight(it) <= SCREEN_LENGTH && SCREEN.containsMatchIn(it)) || PASSWORD_SHEET.containsMatchIn(it))
    }
}
