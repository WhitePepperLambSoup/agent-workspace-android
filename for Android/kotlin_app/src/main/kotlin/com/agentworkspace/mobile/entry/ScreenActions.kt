package com.agentworkspace.mobile.entry

/**
 * Circle to act: what the circled words are, and what can be done with them right away. A link
 * opens, a phone number goes to the dialer, an address to the map app; a date, a price, foreign
 * text or anything worth keeping goes to the agent with the picture. Words only: nothing is sent
 * until the user taps an action.
 */
internal object ScreenActions {
    data class Action(val kind: String, val value: String)

    private val URL = Regex("(https?://|www\\.)[\\w./?%&=#:+~-]+", RegexOption.IGNORE_CASE)
    private val PHONE = Regex("(?<![\\d.])(1[3-9]\\d{9}|0\\d{2,3}-?\\d{7,8}|400-?\\d{3}-?\\d{4})(?![\\d.])")
    private val ADDRESS = Regex("[\\u4e00-\\u9fa5A-Za-z0-9]{0,24}(省|市|区|县|镇|乡|路|街|道|巷|弄|大厦|广场|中心|小区|公园|大学|医院|车站|机场)" +
        "[\\u4e00-\\u9fa5A-Za-z0-9-]{0,16}(号|楼|室|座|门)?")
    private val DATE = Regex("\\d{1,2}月\\d{1,2}[日号]|\\d{4}[-/.年]\\d{1,2}[-/.月]\\d{1,2}")
    private val RELATIVE_DAY = Regex("今天|明天|后天|下?周[一二三四五六日天]|星期[一二三四五六日天]")
    private val TIME = Regex("\\d{1,2}[:：]\\d{2}|\\d{1,2}点")
    private val PRICE = Regex("[¥￥]\\s?\\d|\\d+(\\.\\d+)?\\s?元")
    private val CHINESE = Regex("[\\u4e00-\\u9fa5]")
    private val LATIN = Regex("[A-Za-z]")

    /** The actions for these words, most specific first (kinds: url, dial, map, calendar, compare, translate, keep, copy). */
    fun actions(text: String): List<Action> {
        val words = text.trim()
        if (words.isEmpty()) return emptyList()
        val found = ArrayList<Action>()
        URL.find(words)?.let { found += Action("url", it.value.trimEnd('.', ',', '。', '，')) }
        PHONE.find(words)?.let { found += Action("dial", it.value) }
        // An address names a street, a building or a place; "3号柜" alone is not one.
        ADDRESS.findAll(words).map { it.value }.firstOrNull { it.length >= 4 && CHINESE.containsMatchIn(it) }?.let { found += Action("map", it) }
        // A date, or a day like 明天 with a time: "今天心情不错" is not an appointment.
        if (DATE.containsMatchIn(words) || (RELATIVE_DAY.containsMatchIn(words) && TIME.containsMatchIn(words))) found += Action("calendar", words)
        if (PRICE.containsMatchIn(words)) found += Action("compare", words)
        val latin = LATIN.findAll(words).count()
        val chinese = CHINESE.findAll(words).count()
        if (latin >= 12 && latin > chinese * 3) found += Action("translate", words)
        found += Action("keep", words)
        found += Action("copy", words)
        return found
    }
}
