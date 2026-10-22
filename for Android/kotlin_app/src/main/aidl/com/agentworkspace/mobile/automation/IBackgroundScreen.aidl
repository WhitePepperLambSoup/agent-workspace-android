package com.agentworkspace.mobile.automation;

// The background screen, served from a Shizuku user service (shell privileges): an off-screen
// display the agent works on while the user keeps using the phone's own screen.
interface IBackgroundScreen {
    // Shizuku calls this to stop the service.
    void destroy() = 16777114;

    // Creates the display (or returns the one already there): its id, or -1.
    int open(int width, int height, int densityDpi) = 1;

    void close() = 2;

    // The newest picture of the display as JPEG, at most maxEdge pixels on its long side; null
    // before anything was drawn.
    byte[] picture(int maxEdge, int quality) = 3;

    // `am start --display` with an intent written as an intent: URI (Intent.toUri). The app builds
    // these from its own code (launcher entries, the fixed list of pages). Returns "" on success,
    // else what am printed.
    String start(String intentUri) = 4;

    // `input -d <display> keyevent <code>` (back is 4).
    String key(int keyCode) = 5;

    // Moves the display's top task to the phone's own screen, so the user can take over.
    String bringToFront() = 6;
}
