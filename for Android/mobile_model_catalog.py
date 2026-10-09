"""Pinned GGUF weights, verified against publisher repository metadata on 2026-09-30."""

_HYBRID_DIGESTS = {
    "qwen3.5-0.8b-q4-k-m": "bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517",
    "qwen3.5-0.8b-q8-0": "0ad885ffd4bb022fc4f0d33a3308fa108ef8613159d3b3a67e23abca056b7a6c",
    "qwen3.5-2b-q4-k-m": "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223",
    "qwen3.5-2b-q8-0": "1b04acba824817554f4ce23639bc8495ff70453b8fcb047900c731521021f2c1",
}


def _model(model_id, title, repository, revision, filename, size, digest, quantization, memory):
    publisher = repository.split("/", 1)[0]
    # Match LocalModelBridge's cold-load guard at the provider's 4096-token context.
    # Round up to 64 MiB and keep any larger catalog allowance.
    quantum = 64 * 1024**2
    verified_hybrid = _HYBRID_DIGESTS.get(model_id) == digest
    # Pinned Qwen3.5 has six full-attention layers (48 MiB F16 KV@4096)
    # and 19.265625 MiB fixed recurrent state, for which we reserve 64 MiB.
    context_ram = (48 + 64 if verified_hybrid else 512) * 1024**2
    # Attention compute: 384 MiB plus 6 KiB per context token (LocalModelMemory).
    cold_start_ram = size + (384 + 24) * 1024**2 + context_ram
    memory = max(memory, ((cold_start_ram + quantum - 1) // quantum) * quantum)
    return {
        "model_id": model_id,
        "title": title,
        "repository": repository,
        "revision": revision,
        "filename": filename,
        "size_bytes": size,
        "sha256": digest,
        "quantization": quantization,
        "publisher": "Unsloth" if publisher == "unsloth" else "Qwen",
        "official_weights": publisher == "Qwen",
        "license": "Apache-2.0",
        "source_page": f"https://huggingface.co/{repository}/tree/{revision}",
        "download_url": f"https://huggingface.co/{repository}/resolve/{revision}/{filename}?download=true",
        "minimum_available_ram_bytes": memory,
        "memory_note": (
            "Conservative 4096-token baseline estimate; choose automatic or a larger "
            "context in Local Models. Actual RAM and optional free swap are checked when loading."
        ),
        "supports_tools": True,
        "kind": "model",
        "supports_vision": model_id.startswith("qwen3.5-"),
        "vision_projector_id": (
            "-".join(model_id.split("-")[:2]) + "-vision-f16"
            if model_id.startswith("qwen3.5-")
            else None
        ),
        "family": "Qwen3.5" if "Qwen3.5" in repository else "Qwen3",
        "verified_at": "2026-09-30",
    }


MODEL_CATALOG = (
    _model(
        "qwen3.5-0.8b-q4-k-m",
        "Qwen3.5 0.8B · Q4_K_M · 轻量离线",
        "unsloth/Qwen3.5-0.8B-GGUF",
        "6ab461498e2023f6e3c1baea90a8f0fe38ab64d0",
        "Qwen3.5-0.8B-Q4_K_M.gguf",
        532517120,
        "bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517",
        "Q4_K_M",
        1024 * 1024**2,
    ),
    _model(
        "qwen3.5-0.8b-q8-0",
        "Qwen3.5 0.8B · Q8_0",
        "unsloth/Qwen3.5-0.8B-GGUF",
        "6ab461498e2023f6e3c1baea90a8f0fe38ab64d0",
        "Qwen3.5-0.8B-Q8_0.gguf",
        811843840,
        "0ad885ffd4bb022fc4f0d33a3308fa108ef8613159d3b3a67e23abca056b7a6c",
        "Q8_0",
        1280 * 1024**2,
    ),
    _model(
        "qwen3.5-2b-q4-k-m",
        "Qwen3.5 2B · Q4_K_M · 更多能力",
        "unsloth/Qwen3.5-2B-GGUF",
        "f6d5376be1edb4d416d56da11e5397a961aca8ae",
        "Qwen3.5-2B-Q4_K_M.gguf",
        1280835840,
        "aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223",
        "Q4_K_M",
        1728 * 1024**2,
    ),
    _model(
        "qwen3.5-2b-q8-0",
        "Qwen3.5 2B · Q8_0",
        "unsloth/Qwen3.5-2B-GGUF",
        "f6d5376be1edb4d416d56da11e5397a961aca8ae",
        "Qwen3.5-2B-Q8_0.gguf",
        2012012800,
        "1b04acba824817554f4ce23639bc8495ff70453b8fcb047900c731521021f2c1",
        "Q8_0",
        2432 * 1024**2,
    ),
    _model(
        "qwen3-0.6b-q4-k-m",
        "Qwen3 0.6B · Q4_K_M",
        "unsloth/Qwen3-0.6B-GGUF",
        "50968a4468ef4233ed78cd7c3de230dd1d61a56b",
        "Qwen3-0.6B-Q4_K_M.gguf",
        396705472,
        "ac2d97712095a558e31573f62f466a3f9d93990898b0ec79d7c974c1780d524a",
        "Q4_K_M",
        768 * 1024**2,
    ),
    _model(
        "qwen3-0.6b-q8-0",
        "Qwen3 0.6B · 官方 Q8_0",
        "Qwen/Qwen3-0.6B-GGUF",
        "23749fefcc72300e3a2ad315e1317431b06b590a",
        "Qwen3-0.6B-Q8_0.gguf",
        639446688,
        "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
        "Q8_0",
        1100 * 1024**2,
    ),
    _model(
        "qwen3-1.7b-q4-k-m",
        "Qwen3 1.7B · Q4_K_M",
        "unsloth/Qwen3-1.7B-GGUF",
        "d7f544eead698dbd1f15126ef60b45a1e1933222",
        "Qwen3-1.7B-Q4_K_M.gguf",
        1107409472,
        "b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897",
        "Q4_K_M",
        1800 * 1024**2,
    ),
    _model(
        "qwen3-1.7b-q8-0",
        "Qwen3 1.7B · 官方 Q8_0",
        "Qwen/Qwen3-1.7B-GGUF",
        "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
        "Qwen3-1.7B-Q8_0.gguf",
        1834426016,
        "061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a",
        "Q8_0",
        2800 * 1024**2,
    ),
)


def _projection(model_family, repository, revision, size, digest):
    filename = "mmproj-F16.gguf"
    return {
        "model_id": model_family + "-vision-f16",
        "kind": "vision_projection",
        "title": model_family.replace("qwen3.5-", "Qwen3.5 ").replace("b", "B") + " · 视觉组件",
        "compatible_models": [model_family + "-q4-k-m", model_family + "-q8-0"],
        "repository": repository,
        "revision": revision,
        "filename": filename,
        "size_bytes": size,
        "sha256": digest,
        "license": "Apache-2.0",
        "publisher": "Unsloth",
        "official_weights": False,
        "source_page": f"https://huggingface.co/{repository}/tree/{revision}",
        "download_url": f"https://huggingface.co/{repository}/resolve/{revision}/{filename}?download=true",
        "verified_at": "2026-10-01",
    }


VISION_CATALOG = (
    _projection(
        "qwen3.5-0.8b",
        "unsloth/Qwen3.5-0.8B-GGUF",
        "6ab461498e2023f6e3c1baea90a8f0fe38ab64d0",
        204987232,
        "56e4c6cfe73b0c82e3e82bc518d7591997e61d81f723fc41a586f4fa69ea2453",
    ),
    _projection(
        "qwen3.5-2b",
        "unsloth/Qwen3.5-2B-GGUF",
        "f6d5376be1edb4d416d56da11e5397a961aca8ae",
        668227264,
        "7035e9cb8d7c6a9681d07eef9a364783e86ea4cd73faab2eabb4f43a101830c7",
    ),
)
