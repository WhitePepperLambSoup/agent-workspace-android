package com.agentworkspace.mobile.automation

import org.json.JSONArray
import java.util.UUID
import kotlin.math.abs
import kotlin.math.hypot

/**
 * What the payment firewall and the delete check decide about a touch, on plain values so it can be
 * tested without a phone. A finger presses what it lands on whatever the action is called: a "swipe"
 * that stays put, or stays inside one button, is a tap to Android.
 */
internal object TouchGuard {
    /** Words on a control that deletes, clears, uninstalls or stops an app (spaces removed). */
    private val CONSEQUENTIAL = Regex(
        "删除|清除|清空|卸载|强行停止|强制停止|恢复出厂|格式化|注销|移除|删掉|撤回|清理|解绑|" +
            "(?i)(delete|clearcache|cleardata|clearstorage|uninstall|forcestop|factory(data)?reset|erase|remove|reset|wipe)"
    )

    /** Such a control's words are at most this long (CJK characters; a Latin letter counts half). */
    private const val CONSEQUENTIAL_LENGTH = 12.0

    /** A shorter swipe is a tap: no list or pager moves for it. */
    private const val MIN_SWIPE_DP = 24f

    /** At most this many readable controls in a window: a game, a canvas, an app without accessibility. */
    private const val SPARSE_WINDOW_LABELS = 2

    /** A wordless control covering at least 1/this of the screen is a picture: a canvas, a game, a drawn page. */
    private const val PICTURE_SHARE = 10

    /** How many earlier children of a list are looked at for the words of an item a page left flat. */
    const val ROW_LOOKBACK = 3

    private val SIDEWAYS_LISTS = listOf("ViewPager", "HorizontalScrollView", "TabLayout", "Gallery", "Carousel")
    private val UPRIGHT_LISTS = listOf("ScrollView", "ListView", "WebView")

    /** What the agent may do with Agent Workspace in front: read nothing of it, or leave it. */
    private val LEAVES_OWN_APP_ALONE = setOf("observe", "verify", "wait_for", "launch_app", "open_page",
        "home", "recents", "notifications", "stop_repeat")

    /** What only reads the screen: everything else taps, types, scrolls or opens something. */
    private val READS_ONLY = setOf("observe", "verify", "wait_for", "stop_repeat", "screenshot", "ocr")

    /** A control as the guards see it. [path]: its child indexes from the window's root. */
    class Control(
        val left: Int, val top: Int, val right: Int, val bottom: Int, val label: String? = null,
        val visible: Boolean = true, val clickable: Boolean = false, val longClickable: Boolean = false,
        val scrollable: Boolean = false, val windowId: Int = 0, val path: List<Int> = emptyList(),
        val className: String? = null,
    ) {
        val area: Long get() = (right - left).toLong() * (bottom - top)

        fun contains(x: Int, y: Int): Boolean = left < right && top < bottom && x in left until right && y in top until bottom

        fun inside(other: Control): Boolean = windowId == other.windowId && path.size > other.path.size &&
            path.subList(0, other.path.size) == other.path

        // A RecyclerView does not say which way it scrolls: a wide, low one is a carousel.
        val scrollsSideways: Boolean get() = className.orEmpty().let { name ->
            SIDEWAYS_LISTS.any { it in name } ||
                (UPRIGHT_LISTS.none { it in name } && right - left >= (bottom - top) * 2)
        }
    }

    /** A line of words read off the screen's picture, in screen coordinates. */
    class Line(val text: String, val left: Int, val top: Int, val right: Int, val bottom: Int)

    private val DIGITS = Regex("[0-9]+")

    /** Words in a step that sends, submits, deletes or pays: marked in an approval's list of steps. */
    private val WEIGHTY = Regex("发送|发出|提交|删除|清空|卸载|支付|付款|转账|(?i)(send|submit|delete|remove|uninstall|pay|transfer)")

    /** The start of a text to be typed as an approval shows it, and whether there is more. */
    fun typedPreview(text: String, length: Int = 60): Pair<String, Boolean> =
        text.replace(Regex("\\s+"), " ").let { flat -> flat.take(length) to (flat.length > length) }

    fun weighty(step: String): Boolean = WEIGHTY.containsMatchIn(step)

    /**
     * Whether a control's list row still says what it said when the agent saw it ([then], [now]: the
     * row's first words, null outside a list). Counts and times may change; another item may not: a
     * recycled row shows another item's "删除" at the same place.
     */
    fun sameRow(then: String?, now: String?): Boolean = then?.replace(DIGITS, "#") == now?.replace(DIGITS, "#")

    /**
     * The words an item gives a control of a list that has no row around them: a web page's list
     * holds each item's text and its own "打开" or "删除" side by side, so a recycled item shows only
     * in the text before the button. [earlier]: the list's children before the control, oldest
     * first, as their words and whether each is a control; controls and wordless ones are passed over.
     */
    fun wordsBefore(earlier: List<Pair<String?, Boolean>>): String? = earlier.takeLast(ROW_LOOKBACK).asReversed()
        .firstOrNull { (words, control) -> !control && !words.isNullOrBlank() }?.first

    fun barelyMoves(x: Int, y: Int, x2: Int, y2: Int, density: Float): Boolean =
        hypot((x2 - x).toDouble(), (y2 - y).toDouble()) < MIN_SWIPE_DP * density

    /**
     * What a finger held from one point to another presses, in the topmost window there: the smallest
     * clickable control holding both ends, and the smallest control of any kind (web pages often do
     * not mark theirs clickable).
     */
    fun pressed(controls: Collection<Control>, x: Int, y: Int, x2: Int = x, y2: Int = y): List<Control> {
        val under = controls.filter { it.visible && it.contains(x, y) }
        val window = under.firstOrNull()?.windowId ?: return emptyList()
        val holding = under.filter { it.windowId == window && it.contains(x2, y2) }
        return listOfNotNull(holding.filter { it.clickable || it.longClickable }.minByOrNull { it.area },
            holding.minByOrNull { it.area }).distinct()
    }

    /**
     * What a swipe presses. A control keeps a finger that stays inside it and takes the lift as a tap,
     * unless a list around it takes that movement first (a list going the same way). A control filling
     * much of the screen is a page or a video in a feed, not a button.
     */
    fun pressedBySwipe(controls: Collection<Control>, x: Int, y: Int, x2: Int, y2: Int,
                       screenWidth: Int, screenHeight: Int): List<Control> {
        val sideways = abs(x2 - x) > abs(y2 - y)
        val largest = screenWidth.toLong() * screenHeight / 4
        return pressed(controls, x, y, x2, y2).filter { control ->
            !control.scrollable && control.area <= largest && controls.none { list ->
                list.scrollable && control.inside(list) && list.scrollsSideways == sideways
            }
        }
    }

    /** Whether a swipe starts in a list: it shows more of the list and presses nothing. */
    fun startsInList(controls: Collection<Control>, x: Int, y: Int): Boolean {
        val window = controls.firstOrNull { it.visible && it.contains(x, y) }?.windowId ?: return false
        return controls.any { it.visible && it.scrollable && it.windowId == window && it.contains(x, y) }
    }

    /** Why the firewall stops a press: a payment step on the screen, or a control that pays. */
    fun paymentReason(screen: Iterable<String?>, pressed: Iterable<String?>): String? {
        screen.firstOrNull { PaymentFirewall.marksPaymentScreen(it) }?.let {
            return "this screen is a payment step (“${it.trim().take(30)}”)"
        }
        pressed.firstOrNull { PaymentFirewall.paysOrMovesMoney(it) }?.let {
            return "“${it.trim().take(30)}” pays or moves money"
        }
        return null
    }

    /** The same for the words read off the picture: anywhere for a payment step, under the finger for a control. */
    fun pictureReason(lines: List<Line>, x: Int? = null, y: Int? = null): String? {
        lines.firstOrNull { PaymentFirewall.marksPaymentScreen(it.text) }?.let {
            return "this screen is a payment step (“${it.text.trim().take(30)}” in its picture)"
        }
        if (x == null || y == null) return null
        return lines.firstOrNull { x in it.left until it.right && y in it.top until it.bottom && PaymentFirewall.paysOrMovesMoney(it.text) }
            ?.let { "“${it.text.trim().take(30)}” pays or moves money" }
    }

    /**
     * What a pressed control says, when it deletes, clears, uninstalls or stops an app. Only
     * button-like words count: a long row that merely mentions one of them is not such a control.
     */
    fun consequential(pressed: Iterable<String?>): String? = pressed.filterNotNull()
        .map { label -> label.filterNot { it.isWhitespace() } }
        // Weighed, not counted: "Delete account" or "Delete conversation" is a button too.
        .firstOrNull { it.isNotEmpty() && PaymentFirewall.weight(it) <= CONSEQUENTIAL_LENGTH && CONSEQUENTIAL.containsMatchIn(it) }

    /** Whether the window [windowId] says next to nothing; null: no control is known under the finger. */
    fun saysAlmostNothing(controls: Collection<Control>, windowId: Int?): Boolean = windowId == null ||
        controls.count { it.visible && it.windowId == windowId && !it.label.isNullOrBlank() } <= SPARSE_WINDOW_LABELS

    /**
     * Whether the finger lands on a picture: the smallest control there says nothing, holds nothing
     * that does, and covers a good part of the screen. A canvas or game page in a browser is one, though
     * the browser's own bar has words and so the window is not quiet as a whole.
     */
    fun pictureUnder(controls: Collection<Control>, x: Int, y: Int, screenWidth: Int, screenHeight: Int): Boolean {
        val under = controls.filter { it.visible && it.contains(x, y) }
        val window = under.firstOrNull()?.windowId ?: return false
        val target = under.filter { it.windowId == window }.minByOrNull { it.area } ?: return false
        return target.label.isNullOrBlank() && target.area * PICTURE_SHARE >= screenWidth.toLong() * screenHeight &&
            controls.none { it.visible && it.windowId == window && !it.label.isNullOrBlank() && it.inside(target) }
    }

    /**
     * Whether Agent Workspace in front refuses this action. A screenshot the user asked for themselves
     * (circling something on the screen from the bubble) is theirs.
     */
    fun refusedInOwnApp(action: String, byUser: Boolean): Boolean =
        action !in LEAVES_OWN_APP_ALONE && !(byUser && action in setOf("screenshot", "ocr"))

    /**
     * Whether a locked phone stops this action on the background screen. That screen is drawn
     * whatever the phone's own screen shows, so the lock does not stop it by itself: while the phone
     * is locked it is only read, unless the user started the task on the phone in person (not a
     * schedule, a notification rule, another device or another app).
     */
    fun refusedWhileLocked(action: String, locked: Boolean, inPerson: Boolean): Boolean =
        locked && !inPerson && action !in READS_ONLY

    /** Whether a finger at this point lands on a window of [ownPackage]; [windows] lists them top first. */
    fun ownWindowAt(windows: JSONArray?, x: Int, y: Int, ownPackage: String): Boolean {
        for (index in 0 until (windows?.length() ?: 0)) {
            val window = windows?.optJSONObject(index) ?: continue
            val bounds = window.optJSONObject("bounds") ?: continue
            if (x in bounds.optInt("left") until bounds.optInt("right") && y in bounds.optInt("top") until bounds.optInt("bottom")) {
                return window.optString("package_name") == ownPackage
            }
        }
        return false
    }
}

/**
 * The yes for one control that deletes, clears, uninstalls or stops an app: a refused press gets a
 * token, the engine hands it back only once the user has answered, and it presses that control once.
 * Tokens die on use, also when used on another control, and after five minutes.
 */
internal class ConfirmationBook(private val now: () -> Long, private val newToken: () -> String = { UUID.randomUUID().toString() }) {
    /** What the user is asked about: the app and the words, and the kind of control saying them. */
    data class Control(val app: String?, val label: String, val className: String?, val viewId: String?)

    private class Entry(val control: Control, val issuedAt: Long)

    private val issued = LinkedHashMap<String, Entry>()

    @Synchronized
    fun issue(control: Control): String {
        val token = newToken()
        issued[token] = Entry(control, now())
        while (issued.size > MAX_OPEN) issued.remove(issued.keys.first())
        return token
    }

    @Synchronized
    fun redeem(token: String?, control: Control): Boolean {
        val entry = issued.remove(token ?: return false) ?: return false
        return entry.control == control && now() - entry.issuedAt <= LIFETIME_MS
    }

    private companion object {
        const val LIFETIME_MS = 5 * 60_000L
        const val MAX_OPEN = 8
    }
}
