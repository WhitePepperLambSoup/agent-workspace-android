package com.agentworkspace.mobile.browser

/**
 * What a workspace page opened in the agent's browser (open_file) may load from its folder: the
 * kinds of files a web page is made of, and nothing the workspace tools treat as secret. A page's
 * script can fetch any file of its origin, so the rule is applied to every request, by every part of
 * its path. The secret names are those of agent_workspace/tools/paths.py.
 */
internal object WorkspacePageFiles {
    // Not notes, documents, tables or recordings: a page's script could read those and send them on.
    private val WEB_EXTENSIONS = setOf(
        "html", "htm", "css", "js", "mjs", "json", "map", "svg", "png", "jpg", "jpeg", "gif", "webp",
        "avif", "bmp", "ico", "woff", "woff2", "ttf", "otf", "wasm",
    )
    private val SECRET_NAMES = setOf(
        ".env", ".envrc", ".git-credentials", ".netrc", ".npmrc", ".pypirc", "_netrc", "credentials",
        "credentials.json", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa", "id_xmss", "known_hosts",
        "secrets.json", "terraform.rc",
    )
    private val SECRET_FOLDERS = setOf(".git", ".aws", ".azure", ".docker", ".kube", ".ssh", "gcloud")
    private val SECRET_SUFFIXES = listOf(".jks", ".key", ".keystore", ".p12", ".pem", ".pfx", ".ppk")

    /** [segments]: the path from the opened folder, one name each. */
    fun servable(segments: List<String>): Boolean {
        val parts = segments.filter { it.isNotEmpty() }.map { it.lowercase() }
        val name = parts.lastOrNull() ?: return false
        if (parts.any { it in SECRET_FOLDERS }) return false
        if (name in SECRET_NAMES || name.startsWith(".env.") || SECRET_SUFFIXES.any { name.endsWith(it) }) return false
        return name.substringAfterLast('.', "") in WEB_EXTENSIONS
    }
}
