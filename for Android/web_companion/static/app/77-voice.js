
  // ---- Read aloud and voice conversations (2.0) ------------------------------------------------
  // A reply's ▶ reads it with the phone's text-to-speech. A voice conversation chains the parts that
  // were already there: speak (offline or system voice input) → it is sent → the reply is read aloud
  // → it listens again, until the voice input is cancelled or the conversation is stopped.
  let voiceConversation = false;
  // The next message was said, not typed: its reply continues the voice conversation.
  let voiceTurnPending = false;
  let speakingId = null;

  async function stopReading() {
    const id = speakingId;
    speakingId = null;
    if (id) { try { await apiJson("/mobile/speech/stop", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: id }) }); } catch { /* already done */ } }
  }

  async function readAloud(card, then = null) {
    const text = (card?.querySelector(".message-body")?.innerText || card?.dataset.messageText || "").trim();
    if (!text) { then?.(); return; }
    await stopReading();
    try {
      const started = await apiJson("/mobile/speech/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text.slice(0, 4000) }) });
      const id = started.request_id;
      speakingId = id;
      // Wait for the end of the speech (bounded), then go on.
      for (let tries = 0; tries < 600 && speakingId === id && !disposed; tries += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        let state = "";
        try { state = (await apiJson(`/mobile/speech/status?id=${encodeURIComponent(id)}`)).state || ""; } catch { break; }
        if (["completed", "failed", "stopped", "cancelled", "interrupted", "unknown"].includes(state)) break;
      }
      if (speakingId === id) speakingId = null;
    } catch (error) { notice(t("朗读失败：{0}", error.message)); voiceConversation = false; return; }
    if (!disposed) then?.();
  }

  function listenAgain() {
    if (!voiceConversation || disposed || activeTask) return;
    if (typeof bridge?.requestVoiceInput === "function") bridge.requestVoiceInput();
    else voiceConversation = false;
  }

  // After a reply in a voice conversation: read it, then listen for the next thing said.
  function continueVoiceConversation(task) {
    if (!voiceConversation) return;
    // Typed instead of said: the voice conversation ends there.
    if (!task?.voiceTurn) { voiceConversation = false; return; }
    if (!task.card) return;
    void readAloud(task.card, listenAgain);
  }

  function startVoiceConversation() {
    if (typeof bridge?.requestVoiceInput !== "function") { notice(t("这里没有语音输入")); return; }
    voiceConversation = true;
    notice(t("连续语音对话：说完会自动发送，回复读完后继续听。取消语音输入即可结束。"), "info");
    listenAgain();
  }

  $("btnVoiceConversation")?.addEventListener("click", () => {
    closeAttachMenu();
    if (voiceConversation) { voiceConversation = false; void stopReading(); notice(t("已结束连续语音对话"), "info"); }
    else startVoiceConversation();
  });
