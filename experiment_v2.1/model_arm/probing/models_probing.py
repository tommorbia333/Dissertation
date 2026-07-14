"""
Model registry + loader for the probing arm.

Probing needs per-layer hidden states (``output_hidden_states=True``) from a
raw causal LM, so this arm is Hugging Face / transformers only (the MLX and
API backends in the behavioural arm cannot expose hidden states). Switching
model or size is a one-line change in a config: list a short key from
``PROBING_MODELS`` or any raw Hugging Face model id.

Base (non-instruct) checkpoints are the default here because the probes measure
what structure is present in the representation as the model *reads*, without a
chat template in the way. Instruct ids work too if you want them.
"""

from __future__ import annotations

from typing import Any

# memory_gb is the approximate fp16 weight footprint. On a 24 GB M5 (MPS) the
# practical ceiling for fp16 is ~7-8B; 14B fp16 (~28 GB) will not fit, and
# 4-bit quant that would fit does not expose hidden states cleanly, so 7B is the
# largest local probing model. Bigger models need a CUDA box.
PROBING_MODELS: dict[str, dict[str, Any]] = {
    "qwen0.5b": {"model_id": "Qwen/Qwen2.5-0.5B", "memory_gb": 1,
                 "notes": "Fastest smoke-test model."},
    "qwen1.5b": {"model_id": "Qwen/Qwen2.5-1.5B", "memory_gb": 3,
                 "notes": "Colab default; good local pilot size."},
    "qwen3b":   {"model_id": "Qwen/Qwen2.5-3B", "memory_gb": 6,
                 "notes": "Mid size."},
    "qwen7b":   {"model_id": "Qwen/Qwen2.5-7B", "memory_gb": 14,
                 "notes": "Largest that fits fp16 on M5 24 GB; the target model."},
    # Instruct variants, in case you want to probe the chat-tuned weights.
    "qwen1.5b-instruct": {"model_id": "Qwen/Qwen2.5-1.5B-Instruct", "memory_gb": 3,
                          "notes": "Instruct variant of qwen1.5b."},
    "qwen7b-instruct":   {"model_id": "Qwen/Qwen2.5-7B-Instruct", "memory_gb": 14,
                          "notes": "Instruct variant; matches the behavioural arm's model."},

    # ---- Cross-generation / cross-family comparison points ----
    "qwen3-8b-base": {"model_id": "Qwen/Qwen3-8B-Base", "memory_gb": 16,
                       "notes": ("Qwen3 generation base checkpoint (ungated, apache-2.0). "
                                 "Same family as qwen7b but next-gen architecture/training "
                                 "-> isolates the generation effect from pure scale.")},
    "mistral7b": {"model_id": "mistralai/Mistral-7B-v0.3", "memory_gb": 14,
                  "notes": ("Cross-family comparison point. GATED on Hugging Face: "
                            "you must accept the licence at "
                            "huggingface.co/mistralai/Mistral-7B-v0.3 with the account "
                            "behind your local HF token before this will download.")},

    # ---- Cloud-only: too large for a 24 GB local box, need a CUDA rental ----
    # pick_device()/pick_dtype() already auto-detect CUDA, so these need no
    # code changes to run remotely -- just enough VRAM. See
    # ../../analysis/../../README or ask the assistant for the cloud-compute
    # writeup (GPU tier per model, cost estimates, deployment steps).
    "qwen14b-base": {"model_id": "Qwen/Qwen2.5-14B", "memory_gb": 28,
                      "notes": "fp16 ~28GB. Fits one 40GB+ GPU (A100 40/80GB, H100)."},
    "qwen32b-base": {"model_id": "Qwen/Qwen2.5-32B", "memory_gb": 64,
                      "notes": "fp16 ~64GB. Needs an 80GB GPU (A100/H100 80GB) with headroom to spare."},
    "qwen72b-base": {"model_id": "Qwen/Qwen2.5-72B", "memory_gb": 144,
                      "notes": ("fp16 ~144GB: needs 2x80GB GPUs with device_map='auto', "
                                "or 8-bit quant (~72GB, load_in_8bit=True) on one 80GB GPU.")},
    "llama70b-base": {"model_id": "meta-llama/Llama-3.1-70B", "memory_gb": 140,
                       "notes": ("Cross-family, ~70B scale. GATED on Hugging Face (Meta licence). "
                                 "Same VRAM story as qwen72b-base.")},
}


def resolve_model(spec: str) -> tuple[str, str]:
    """Map a config entry to (short_key, hf_model_id).

    ``spec`` may be a registry key ('qwen7b') or a raw HF id ('Qwen/Qwen2.5-7B').
    The short key is filesystem-safe and used to namespace outputs.
    """
    if spec in PROBING_MODELS:
        return spec, PROBING_MODELS[spec]["model_id"]
    # raw HF id: derive a short, filesystem-safe key
    for key, cfg in PROBING_MODELS.items():
        if cfg["model_id"] == spec:
            return key, spec
    return spec.replace("/", "-"), spec


def pick_device(device: str | None = None) -> str:
    import torch
    if device and device != "auto":
        return device
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def pick_dtype(device: str, dtype: str | None = None):
    """fp16 on GPU (MPS/CUDA), fp32 on CPU. Override with an explicit dtype name."""
    import torch
    if dtype:
        return getattr(torch, dtype)
    return torch.float16 if device in ("mps", "cuda") else torch.float32


def load_model(model_id: str, *, device: str | None = None, dtype: str | None = None):
    """Load tokenizer + causal LM ready for hidden-state extraction.

    Returns (tokenizer, model, device_str). The model is in eval mode on the
    chosen device. Works on Apple Silicon (MPS), CUDA, or CPU.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dev = pick_device(device)
    torch_dtype = pick_dtype(dev, dtype)

    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch_dtype)
    model.eval().to(dev)
    return tok, model, dev
