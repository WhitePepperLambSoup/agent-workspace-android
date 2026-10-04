package com.agentworkspace.mobile.workspace

import java.io.File
import java.util.Locale

object WorkspaceFolderPath {
    fun resolve(authority: String?, documentId: String, volumes: Map<String, File>): File {
        require(authority == "com.android.externalstorage.documents") {
            "请选择本机或 SD 卡文件夹；云盘位置无法供本地工具使用"
        }
        require(documentId.length <= 4096 && ':' in documentId) { "无法识别所选文件夹" }
        val volumeId = documentId.substringBefore(':')
        val relative = documentId.substringAfter(':')
        require(volumeId.isNotEmpty() && relative.none { it.isISOControl() || it in "\\:" } && !relative.startsWith('/')) {
            "无效的文件夹路径"
        }
        val segments = if (relative.isEmpty()) emptyList() else relative.split('/')
        require(segments.all { it.isNotEmpty() && it != "." && it != ".." }) { "文件夹路径不能包含父目录" }
        require(!restricted(segments)) { "Android 不允许将其他应用的私有目录作为工作区" }
        val root = volumes.entries.firstOrNull { it.key.equals(volumeId, true) }?.value?.canonicalFile
            ?: throw IllegalArgumentException("所选存储卷未挂载或不能访问")
        val directory = if (relative.isEmpty()) root else File(root, relative).canonicalFile
        require(contains(root, directory)) { "所选文件夹超出了存储卷范围" }
        require(!restricted(root.toPath().relativize(directory.toPath()).map { it.toString() })) {
            "Android 不允许将其他应用的私有目录作为工作区"
        }
        require(directory.isDirectory && directory.canRead() && directory.canWrite()) {
            "所选文件夹不可读写；请先授予公共文件夹访问权限"
        }
        return directory
    }

    fun contains(root: File, target: File): Boolean {
        val base = root.canonicalFile.toPath()
        return target.canonicalFile.toPath().startsWith(base)
    }

    private fun restricted(segments: List<String>): Boolean = segments.size >= 2 &&
        segments[0].equals("Android", true) && segments[1].lowercase(Locale.ROOT) in setOf("data", "obb")
}
