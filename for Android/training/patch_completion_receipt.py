"""Add measured Windows completion receipts to a verified private llama.cpp copy.

The Android engine and original archive stay unchanged. Binary stdout preserves
generated token-piece bytes; stderr records the actual inference branches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

ARCHIVE_SHA256 = "a6861d549427f814dc591c439e08206f67ffaba0248344d421589abf18199e67"
RELATIVE = Path("tools/completion/completion.cpp")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def patched_source(original: bytes) -> bytes:
    source = original.decode("utf-8")

    def replace_once(before, after):
        nonlocal source
        if source.count(before) != 1:
            raise ValueError("Pinned completion receipt patch anchor changed")
        source = source.replace(before, after, 1)

    replace_once(
        "#include <windows.h>\n#include <signal.h>\n#endif\n",
        "#include <windows.h>\n#include <signal.h>\n#include <io.h>\n#include <fcntl.h>\n#endif\n",
    )
    replace_once(
        'int llama_completion(int argc, char ** argv) {\n    std::setlocale(LC_NUMERIC, "C");\n',
        "int llama_completion(int argc, char ** argv) {\n"
        "#if defined(_WIN32)\n"
        "    if (_setmode(_fileno(stdout), _O_BINARY) == -1) {\n"
        '        std::perror("Unable to preserve generated stdout bytes");\n'
        "        return 1;\n    }\n#endif\n"
        '    std::setlocale(LC_NUMERIC, "C");\n',
    )
    replace_once(
        "    // Tokenize negative prompt\n",
        "#if defined(_WIN32)\n"
        "    const int agent_input_tokens = static_cast<int>(embd_inp.size());\n"
        "    int agent_generated_tokens = 0;\n"
        "    bool agent_eog = false;\n"
        "    bool agent_input_truncated = false;\n"
        "    bool agent_context_shifted = false;\n"
        "    bool agent_context_full = false;\n"
        "#endif\n\n    // Tokenize negative prompt\n",
    )
    replace_once(
        "                const int skipped_tokens = (int) embd.size() - max_embd_size;\n",
        "#if defined(_WIN32)\n                agent_input_truncated = true;\n#endif\n"
        "                const int skipped_tokens = (int) embd.size() - max_embd_size;\n",
    )
    replace_once(
        "                if (n_past + (int) embd.size() >= n_ctx) {\n",
        "                if (n_past + (int) embd.size() >= n_ctx) {\n"
        "#if defined(_WIN32)\n                    agent_context_full = true;\n#endif\n",
    )
    replace_once(
        "                    const int n_left    = n_past - params.n_keep;\n",
        "#if defined(_WIN32)\n                    agent_context_shifted = true;\n#endif\n"
        "                    const int n_left    = n_past - params.n_keep;\n",
    )
    replace_once(
        "                while (n_past >= ga_i + ga_w) {\n",
        "                while (n_past >= ga_i + ga_w) {\n"
        "#if defined(_WIN32)\n                    agent_context_full = true;\n"
        "                    agent_context_shifted = true;\n#endif\n",
    )
    replace_once(
        "            const llama_token id = common_sampler_sample(smpl, ctx, -1);\n",
        "            const llama_token id = common_sampler_sample(smpl, ctx, -1);\n"
        "#if defined(_WIN32)\n            ++agent_generated_tokens;\n"
        "            agent_eog = llama_vocab_is_eog(vocab, id);\n#endif\n",
    )
    replace_once(
        "    common_perf_print(ctx, smpl);\n\n    llama_backend_free();\n",
        "    common_perf_print(ctx, smpl);\n"
        "#if defined(_WIN32)\n    common_log_flush(common_log_main());\n"
        '    std::fprintf(stderr, "\\nAGENT_EVALUATION_STATUS {\\"schema_version\\":1,'
        '\\"input_tokens\\":%d,\\"context_tokens\\":%u,\\"generated_tokens\\":%d,'
        '\\"eog\\":%s,\\"input_truncated\\":%s,\\"context_shifted\\":%s,'
        '\\"context_full\\":%s}\\n",\n'
        "        agent_input_tokens, llama_n_ctx(ctx), agent_generated_tokens,\n"
        '        agent_eog ? "true" : "false", agent_input_truncated ? "true" : "false",\n'
        '        agent_context_shifted ? "true" : "false",\n'
        '        agent_context_full ? "true" : "false");\n'
        "    std::fflush(stderr);\n#endif\n\n    llama_backend_free();\n",
    )
    return source.encode("utf-8")


def apply_patch(source: Path, archive: Path, report_path: Path) -> dict:
    if report_path.exists():
        raise ValueError("Preserve prior backend patch evidence")
    if sha(archive) != ARCHIVE_SHA256:
        raise ValueError("llama.cpp source archive does not match pinned engine")
    path = source / RELATIVE
    original = path.read_bytes()
    with tarfile.open(archive, "r:gz") as stream:
        matches = [
            m
            for m in stream.getmembers()
            if m.isfile() and m.name.partition("/")[2] == RELATIVE.as_posix()
        ]
        if len(matches) != 1 or stream.extractfile(matches[0]).read() != original:
            raise ValueError("Private completion source differs from original pinned archive")
    patched = patched_source(original)
    path.write_bytes(patched)
    report = {
        "archive_sha256": ARCHIVE_SHA256,
        "original_source_sha256": hashlib.sha256(original).hexdigest(),
        "patched_source_sha256": hashlib.sha256(patched).hexdigest(),
        "patch_helper_sha256": sha(Path(__file__)),
        "source": str(source.resolve()),
        "scope": "Windows-only measured receipt and binary token-piece stdout",
        "stdout_binary_mode": True,
        "android_jni_modified": False,
        "model_weights_modified": False,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply_patch(args.source, args.source_archive, args.report)), flush=True)


if __name__ == "__main__":
    main()
