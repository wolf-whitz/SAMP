from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from sentence_transformers import SentenceTransformer, util
import torch
import pickle
import os
import time
import asyncio
from mapping import split_text, generate_variants

app = FastAPI(title="WZDetect")

model = SentenceTransformer("all-MiniLM-L6-v2")

BASE_DIR = os.path.dirname(__file__)
BADWORDS_PATH = os.path.join(BASE_DIR, "model", "badwords_meta.pkl")

if not os.path.exists(BADWORDS_PATH):
    raise FileNotFoundError(f"Could not find badwords_meta.pkl at {BADWORDS_PATH}")

with open(BADWORDS_PATH, "rb") as f:
    badword_meta: Dict[str, Dict] = pickle.load(f)

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

MAX_QUEUE_PER_IP = 20
queues = {}
locks = {}

async def check_rate_limit(client_ip: str):
    if client_ip not in queues:
        queues[client_ip] = asyncio.Queue(maxsize=MAX_QUEUE_PER_IP)
        locks[client_ip] = asyncio.Lock()

    if queues[client_ip].full():
        raise HTTPException(status_code=429, detail="Too many queued requests")

    fut = asyncio.get_event_loop().create_future()
    await queues[client_ip].put(fut)

    while queues[client_ip]._queue[0] is not fut:
        await fut

    await locks[client_ip].acquire()

async def release_rate_limit(client_ip: str):
    locks[client_ip].release()
    if not queues[client_ip].empty():
        finished = await queues[client_ip].get()
        if not finished.done():
            finished.set_result(True)

class DetectRequest(BaseModel):
    text: str
    threshold: Optional[float] = 0.72
    custom_threshold: Optional[Dict[str, float]] = None
    include_variants: Optional[bool] = True
    max_tokens: Optional[int] = 200
    languages: Optional[List[str]] = None
    block: Optional[List[str]] = []
    return_only_flagged: Optional[bool] = False

def detect_bad_words(
    text: str,
    threshold: float = 0.72,
    custom_threshold: Optional[Dict[str, float]] = None,
    include_variants: bool = True,
    block: Optional[List[str]] = None,
    max_tokens: int = 200,
    languages: Optional[List[str]] = None,
    return_only_flagged: bool = False
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

    for tok, emb_variants, variants in zip(tokens, token_embeddings, token_variants_map):
        flagged = False
        scores = util.cos_sim(emb_variants, badword_embeddings)
        max_score, idx = torch.max(scores, dim=1)
        for score_val, i in zip(max_score, idx):
            bw = variant_to_badword[i.item()]
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

            if score_val.item() > effective_threshold:
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

@app.post("/detect")
async def detect(request: DetectRequest, client_ip: Optional[str] = None):
    if client_ip is None:
        client_ip = "default"
    await check_rate_limit(client_ip)
    try:
        result = detect_bad_words(
            text=request.text,
            threshold=request.threshold,
            custom_threshold=request.custom_threshold,
            include_variants=request.include_variants,
            block=request.block,
            max_tokens=request.max_tokens,
            languages=request.languages,
            return_only_flagged=request.return_only_flagged
        )
    finally:
        await release_rate_limit(client_ip)
    return {"input": request.text, "detection": result}
