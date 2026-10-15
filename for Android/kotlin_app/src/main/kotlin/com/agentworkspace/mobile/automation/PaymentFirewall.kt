package com.agentworkspace.mobile.automation

/**
 * The payment firewall: the agent never pays, transfers, withdraws or places an order, whatever
 * the mode and even with confirmed=true; the user finishes those steps on the phone. Fixed rules,
 * not the model's judgment. 支付宝 is an app, not a payment.
 */
internal object PaymentFirewall {
    /** Words on a control that pays or moves money (spaces removed, at most 16 characters). */
    private val CONTROL = Regex(
        "支付(?!宝)|付款|买单|转账|提现|充值|免密|确认收款|提交订单|立即购买|确认购买|确认下单|" +
            "(?i)(^pay|paynow|payment|checkout|placeorder|buynow|transfer|withdraw|topup)"
    )

    /** Words that only show on a payment step: a payment password sheet, a payment or transfer confirmation. */
    private val SCREEN = Regex(
        "支付密码|输入密码完成支付|确认支付|确认付款|确认转账|转账金额|付款金额|指纹支付|面容支付|刷脸支付|" +
            "(?i)(paymentpassword|confirmpayment|confirmtransfer)"
    )

    private fun plain(label: String?) = label?.filterNot { it.isWhitespace() }.orEmpty()

    fun paysOrMovesMoney(label: String?): Boolean = plain(label).let { it.isNotEmpty() && it.length <= 16 && CONTROL.containsMatchIn(it) }

    fun marksPaymentScreen(label: String?): Boolean = plain(label).let { it.isNotEmpty() && SCREEN.containsMatchIn(it) }
}
