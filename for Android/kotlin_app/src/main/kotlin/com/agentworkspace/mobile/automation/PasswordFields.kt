package com.agentworkspace.mobile.automation

import android.text.InputType

/**
 * Whether a field's input type is a password's. A field stops being "password" to accessibility
 * when the user taps the eye beside it and its text is shown, but its input type stays one of these,
 * so the shown password is still neither read nor typed into.
 */
internal fun passwordInputType(inputType: Int): Boolean {
    val variation = inputType and InputType.TYPE_MASK_VARIATION
    return when (inputType and InputType.TYPE_MASK_CLASS) {
        InputType.TYPE_CLASS_TEXT -> variation == InputType.TYPE_TEXT_VARIATION_PASSWORD ||
            variation == InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD ||
            variation == InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD
        InputType.TYPE_CLASS_NUMBER -> variation == InputType.TYPE_NUMBER_VARIATION_PASSWORD
        else -> false
    }
}
