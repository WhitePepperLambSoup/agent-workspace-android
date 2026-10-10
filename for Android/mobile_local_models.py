"""Describe embedded Qwen and optional loopback engines without cloud fallback."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import time
from urllib.parse import urlsplit

import httpx

EMBEDDED_BASE_URL = "http://127.0.0.1:8080/embedded-qwen/v1"


def get_local_engine_bridge():
    try:
        from java import jclass

        return jclass("com.agentworkspace.mobile.localmodels.LocalModelBridge")
    except Exception:
        return None


def native_engine_status(bridge=None):
    bridge = bridge if bridge is not None else get_local_engine_bridge()
    try:
        value = json.loads(str(bridge.status())) if bridge is not None else {}
        if not isinstance(value, dict):
            raise ValueError("invalid engine status")
        return value or {"available": False, "generating": False}
    except Exception:
        return {
            "available": False,
            "generating": False,
            "last_error": "Native inference is unavailable on this host",
        }


def local_model_diagnostics(controller, hardware=None, *, model_manager=None):
    url = getattr(controller, "base_url", "") or ""
    host = urlsplit(url).hostname or ""
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host == "localhost"
    protocol = getattr(controller, "protocol", None)
    embedded = protocol == "openai-compatible" and url.rstrip("/") == EMBEDDED_BASE_URL
    native = native_engine_status()
    measured = native.get("last_generation") or {}
    context_plan = None
    if embedded:
        try:
            service = getattr(getattr(controller, "runtime", None), "service", None)
            provider = getattr(getattr(service, "runner", None), "_provider", None)
            configured = getattr(provider, "_configured_context_tokens", 0)
            actual = getattr(provider, "_context_size", configured)
            ready = getattr(provider, "context_plan_ready", True)
            memory_mode = getattr(provider, "_memory_mode", "balanced")
            bridge = get_local_engine_bridge()
            if bridge is not None and hasattr(bridge, "contextPlan"):
                context_plan = json.loads(
                    str(
                        bridge.contextPlan(
                            controller.default_model, actual if ready else configured, memory_mode
                        )
                    )
                )
                if not isinstance(context_plan, dict):
                    raise ValueError("invalid local context plan")
                # A ready provider has a resolved capacity. A deferred plan's
                # internal placeholder must never be treated as a manual choice.
                context_plan["configured_context_tokens"] = configured
                context_plan["context_plan_ready"] = ready
                context_plan["context_plan_error"] = getattr(provider, "context_plan_error", None)
                context_plan["provider_context_tokens"] = actual if ready else None
        except Exception:
            context_plan = None
    return {
        **(model_manager.snapshot() if model_manager is not None else {}),
        "embedded_inference": embedded,
        "engine": "llama.cpp"
        if embedded
        else "ollama"
        if protocol == "ollama"
        else "openai-compatible"
        if protocol == "openai-compatible"
        else protocol,
        "route": "embedded_qwen" if embedded else "local_endpoint" if local else "remote_endpoint",
        "native_engine": native,
        "context_plan": context_plan,
        "endpoint": url,
        "model": controller.default_model,
        "hardware": hardware or {},
        "requirements": {
            "small_quantized_model": "arm64 recommended; check engine memory requirements",
            "large_gui_model": "12 GiB+ RAM and supported acceleration recommended",
        },
        "measurement": {
            "first_token_ms": measured.get("first_token_ms"),
            "tokens_per_second": measured.get("tokens_per_second"),
            # How much of the last prompt the engine reused from the previous step.
            "prompt_tokens": measured.get("prompt_tokens"),
            "prompt_cached_tokens": measured.get("prompt_cached_tokens"),
            "prompt_tokens_per_second": measured.get("prompt_tokens_per_second"),
            # Heat lowers the threads during a generation; threads_lowest is how far.
            "threads": measured.get("threads"),
            "threads_lowest": measured.get("threads_lowest"),
            # Whether the last generation kept its tool calls to the call grammar, and how
            # often it had to steer the model back to a valid token.
            "tool_grammar": measured.get("tool_grammar"),
            "tool_grammar_resamples": measured.get("tool_grammar_resamples"),
            "battery_delta": None,
        },
    }


async def probe_local_model(controller, *, model_manager=None):
    report = await asyncio.to_thread(
        local_model_diagnostics, controller, model_manager=model_manager
    )
    if report["route"] == "remote_endpoint":
        ready = bool(report["native_engine"].get("available"))
        return {
            **report,
            "available": ready,
            "reason": "Native CPU engine is ready; select installed local weights to use it"
            if ready
            else report["native_engine"].get("last_error") or "Native engine unavailable",
        }
    if report["route"] == "embedded_qwen":
        if not report["native_engine"].get("available"):
            return {
                **report,
                "available": False,
                "reason": report["native_engine"].get("last_error") or "Native engine unavailable",
            }
        if model_manager is None:
            raise ValueError("private model storage is unavailable")
        try:
            await asyncio.to_thread(model_manager.installed_path, controller.default_model)
        except ValueError:
            return {
                **report,
                "available": False,
                "reason": "Download and verify the selected model first",
            }
        return {
            **report,
            "available": True,
            "models": [controller.default_model],
            "reason": "Native CPU engine and installed weights verified",
        }
    if report["route"] != "local_endpoint" or report["engine"] not in {
        "ollama",
        "openai-compatible",
    }:
        raise ValueError("select a loopback Ollama or OpenAI-compatible model endpoint first")
    route = "/api/tags" if report["engine"] == "ollama" else "/models"
    base = report["endpoint"].rstrip("/")
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
            response = await client.get(base + route)
            if response.status_code != 200:
                return {
                    **report,
                    "available": False,
                    "reason": f"engine returned HTTP {response.status_code}",
                }
            data = response.json()
        models = data.get("models" if report["engine"] == "ollama" else "data", [])
        return {
            **report,
            "available": True,
            "probe_latency_ms": round((time.monotonic() - start) * 1000),
            "models": [str(item.get("name", item.get("id", "")))[:200] for item in models[:200]],
        }
    except (httpx.HTTPError, ValueError, AttributeError):
        return {**report, "available": False, "reason": "local model engine is not responding"}
