package com.agentworkspace.mobile.embedded

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import com.agentworkspace.mobile.R
import com.agentworkspace.mobile.WebUiActivity
import com.agentworkspace.mobile.voice.MobileVoiceInput

class AgentWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { id ->
            val view = RemoteViews(context.packageName, R.layout.agent_widget)
            view.setOnClickPendingIntent(R.id.widget_open, PendingIntent.getActivity(context, id * 2,
                entryIntent(context, false), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            view.setOnClickPendingIntent(R.id.widget_voice, PendingIntent.getActivity(context, id * 2 + 1,
                entryIntent(context, true), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            manager.updateAppWidget(id, view)
        }
    }

    companion object {
        @JvmStatic
        fun entryIntent(context: Context, voice: Boolean): Intent = Intent(context, WebUiActivity::class.java)
            .setAction(if (voice) Intent.ACTION_VOICE_COMMAND else Intent.ACTION_MAIN)
            .putExtra(MobileVoiceInput.EXTRA_VOICE_INPUT, voice)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
    }
}
