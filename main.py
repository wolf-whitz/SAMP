import streamlit as st
from sentence_transformers import SentenceTransformer
import pickle
import os
import numpy as np
import time
from mapping import split_text, generate_variants

st.set_page_config(page_title="WZDetect", layout="wide")

model = SentenceTransformer("all-MiniLM-L6-v2")

BASE_DIR = os.path.dirname(__file__)
BADWORDS_PATH = os.path.join(BASE_DIR, "model", "badwords_meta.pkl")

with open(BADWORDS_PATH, "rb") as f:
    badword_meta = pickle.load(f)

badwords = list(badword_meta.keys())
variant_cache = {}
all_variant_texts = []
variant_to_badword = []

for bw in badwords:
    variants = list(generate_variants(bw)) or [bw]
    all_variant_texts.extend(variants)
    variant_to_badword.extend([bw] * len(variants))
    variant_cache[bw] = variants

badword_embeddings = model.encode(all_variant_texts, convert_to_tensor=True)

def detect_bad_words(
    text,
    threshold=0.72,
    custom_threshold=None,
    include_variants=True,
    block=None,
    max_tokens=200,
    languages=None,
    return_only_flagged=False
):
    start_time = time.time()
    tokens = split_text(text)[:max_tokens]
    out = {}
    if not tokens:
        return out

    token_embeddings = []
    token_variants_map = []
    for tok in tokens:
        variants = [tok]
        if include_variants:
            variants = list(generate_variants(tok)) or [tok]
        emb = model.encode(variants, convert_to_tensor=True)
        token_embeddings.append(emb)
        token_variants_map.append(variants)

    badword_emb_np = badword_embeddings.cpu().numpy() if hasattr(badword_embeddings, 'cpu') else np.array(badword_embeddings)

    for tok, emb_variants, variants in zip(tokens, token_embeddings, token_variants_map):
        flagged = False
        emb_np = emb_variants.cpu().numpy() if hasattr(emb_variants, 'cpu') else np.array(emb_variants)
        scores = np.matmul(emb_np, badword_emb_np.T)

        max_idx = np.argmax(scores, axis=1)
        max_score = scores[np.arange(len(max_idx)), max_idx]

        for score_val, i in zip(max_score, max_idx):
            bw = variant_to_badword[i]
            bw_meta = badword_meta[bw]
            bw_category = bw_meta.get("profanity_category")
            bw_language = bw_meta.get("language")
            effective_threshold = threshold
            if custom_threshold and bw_category in custom_threshold:
                effective_threshold = custom_threshold[bw_category]

            if block and tok in block:
                out[tok] = {
                    "flagged": True,
                    "profanity_level": 1,
                    "profanity_category": "blocked",
                    "language": "unknown"
                }
                flagged = True
                break

            if score_val > effective_threshold:
                if languages and bw_language not in languages:
                    continue
                out[tok] = {
                    "flagged": True,
                    **bw_meta
                }
                flagged = True
                break

        if not flagged and not return_only_flagged:
            out[tok] = {
                "flagged": False,
                "profanity_level": 0,
                "profanity_category": None,
                "language": None
            }

    end_time = time.time()
    out["_detection_time_seconds"] = round(end_time - start_time, 4)
    return out

st.title("WZDetect UI")

text = st.text_area("Drop your text here")

threshold = st.slider("Threshold", 0.0, 1.0, 0.72)
include_variants = st.checkbox("Include Variants", True)
return_only_flagged = st.checkbox("Return Only Flagged", False)
max_tokens = st.number_input("Max Tokens", 1, 500, 200)

langs_input = st.text_input("Filter Languages (comma separated)")
languages = [l.strip() for l in langs_input.split(",")] if langs_input else None

block_input = st.text_input("Block Specific Tokens (comma separated)")
block = [b.strip() for b in block_input.split(",")] if block_input else None

if st.button("Run Detection"):
    res = detect_bad_words(
        text=text,
        threshold=threshold,
        include_variants=include_variants,
        block=block,
        max_tokens=max_tokens,
        languages=languages,
        return_only_flagged=return_only_flagged
    )
    st.json(res)
