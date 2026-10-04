package com.agentworkspace.mobile

import android.app.Activity
import android.os.Bundle
import android.widget.FrameLayout

/** Debug instrumentation window; it owns no application bridge, settings, or engine. */
class HtmlPreviewTestActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(FrameLayout(this))
    }
}
