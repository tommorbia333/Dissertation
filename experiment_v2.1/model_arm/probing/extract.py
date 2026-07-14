"""
Reading-pass hidden-state extraction.

Feeds each story (its 8 event paragraphs joined) through the model in a single
forward pass and pulls one hidden-state vector per event, taken at the last
content token of that event's paragraph, at every layer.

Output per condition:
    X : (n_events, n_layers, hidden)   event vectors in presentation order
    y : (n_events,)                    true chronological position 1..8
    g : (n_events,)                    integer story id (index into story_keys)

Plus ``story_keys`` (story id -> normalized domain key). Saved to
``event_vectors.npz``; consumed by every downstream probe.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import stimuli_probing as S

SEP = "\n\n"


def event_last_token_indices(tok, events):
    """Build the full story text and find the last token index of each event.

    Character spans are computed directly from the join, so there is no fragile
    string searching. Returns (encoding, [last_token_index per event]).
    """
    texts = [t for _, t in events]
    full = SEP.join(texts)

    spans, pos = [], 0
    for t in texts:
        spans.append((pos, pos + len(t)))
        pos += len(t) + len(SEP)

    enc = tok(full, return_offsets_mapping=True, return_tensors="pt")
    offsets = enc["offset_mapping"][0].tolist()

    last_idx = []
    for start, end in spans:
        inside = [i for i, (a, b) in enumerate(offsets)
                  if a >= start and b <= end and not (a == 0 and b == 0)]
        last_idx.append(inside[-1])
    return enc, last_idx


def extract_story(tok, model, device, events) -> np.ndarray:
    """One forward pass; return (n_events, n_layers, hidden) in presentation order."""
    import torch
    enc, last_idx = event_last_token_indices(tok, events)
    input_ids = enc["input_ids"].to(device)
    attn = enc["attention_mask"].to(device)

    with torch.no_grad():
        out = model(input_ids=input_ids, attention_mask=attn,
                    output_hidden_states=True)

    hs = out.hidden_states                    # tuple length n_layers+1
    hidden = hs[0].shape[-1]
    vecs = np.zeros((len(last_idx), len(hs), hidden), dtype=np.float32)
    for li, layer in enumerate(hs):
        layer = layer[0]                      # (seq, hidden)
        for ei, ti in enumerate(last_idx):
            vecs[ei, li] = layer[ti].float().cpu().numpy()
    return vecs


def build_dataset(tok, model, device, data: dict):
    """Extract reading vectors for every story unit in ``data``.

    Returns (feats, labels, groups, story_keys) where feats/labels/groups are
    dicts keyed by condition and story_keys[id] is the normalized domain key.
    """
    story_keys = S.story_keys_sorted(data)
    key_to_id = {k: i for i, k in enumerate(story_keys)}
    units = S.to_story_units(data)

    feats = {c: [] for c in S.CONDITIONS}
    labels = {c: [] for c in S.CONDITIONS}
    groups = {c: [] for c in S.CONDITIONS}

    for u in units:
        c = u["condition"]
        vecs = extract_story(tok, model, device, u["events"])   # (8, L, H)
        feats[c].append(vecs)
        labels[c].extend(p for p, _ in u["events"])
        groups[c].extend([key_to_id[u["domain_key"]]] * len(u["events"]))
        print(f"  extracted {u['domain']:<22} {c:<10} {vecs.shape}")

    for c in S.CONDITIONS:
        feats[c] = np.concatenate(feats[c], axis=0)
        labels[c] = np.array(labels[c])
        groups[c] = np.array(groups[c])
    return feats, labels, groups, story_keys


def save_vectors(feats, labels, groups, story_keys, path: str | Path):
    payload = {"story_keys": np.array(story_keys)}
    for c in S.CONDITIONS:
        payload[f"X_{c}"] = feats[c]
        payload[f"y_{c}"] = labels[c]
        payload[f"g_{c}"] = groups[c]
    np.savez_compressed(path, **payload)
    print(f"saved {path}")


def load_vectors(path: str | Path):
    """Return (X, y, g, story_keys, g_to_key) from an event_vectors.npz."""
    d = np.load(path, allow_pickle=True)
    X = {c: d[f"X_{c}"] for c in S.CONDITIONS}
    y = {c: d[f"y_{c}"] for c in S.CONDITIONS}
    g = {c: d[f"g_{c}"] for c in S.CONDITIONS}
    story_keys = [str(k) for k in d["story_keys"]]
    g_to_key = {i: k for i, k in enumerate(story_keys)}
    return X, y, g, story_keys, g_to_key


def run_extraction(tok, model, device, data: dict, out_path: str | Path):
    """Full reading pass -> event_vectors.npz. Returns the load_vectors() tuple."""
    feats, labels, groups, story_keys = build_dataset(tok, model, device, data)
    save_vectors(feats, labels, groups, story_keys, out_path)
    return load_vectors(out_path)
