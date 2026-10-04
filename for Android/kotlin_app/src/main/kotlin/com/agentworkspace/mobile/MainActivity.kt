package com.agentworkspace.mobile

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import com.agentworkspace.mobile.bridge.AgentStreamChunk
import com.agentworkspace.mobile.bridge.PythonBridge
import com.agentworkspace.mobile.embedded.TermuxBootstrap
import com.agentworkspace.mobile.embedded.TermuxDaemonService
import com.agentworkspace.mobile.ui.ChatMessage
import com.agentworkspace.mobile.ui.TimelineScreen
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // 首次启动解压 Termux 基础环境 (若尚未解压)
        if (!TermuxBootstrap.isInstalled(this)) {
            Thread {
                TermuxBootstrap.installSync(this)
            }.start()
        }

        // 启动后台守护服务
        val daemonIntent = Intent(this, TermuxDaemonService::class.java)
        startForegroundService(daemonIntent)

        setContent {
            val messages = remember { mutableStateListOf<ChatMessage>() }
            val coroutineScope = rememberCoroutineScope()

            TimelineScreen(
                messages = messages,
                onSendMessage = { prompt ->
                    messages.add(ChatMessage(role = "user", content = prompt))

                    coroutineScope.launch {
                        PythonBridge.executePromptFlow(this@MainActivity, "session_mobile", prompt).collect { chunk ->
                            when (chunk) {
                                is AgentStreamChunk.Thinking -> {
                                    // 实时更新思考状态
                                }
                                is AgentStreamChunk.Answer -> {
                                    messages.add(ChatMessage(role = "assistant", content = chunk.text))
                                }
                                is AgentStreamChunk.Error -> {
                                    messages.add(ChatMessage(role = "assistant", content = "❌ 错误: ${chunk.message}"))
                                }
                                else -> {}
                            }
                        }
                    }
                }
            )
        }
    }
}
