from fastapi import Request, HTTPException
import asyncio
from collections import defaultdict, deque

MAX_CONCURRENT_PER_IP = 1  
MAX_QUEUE_PER_IP = 20  

active_requests = defaultdict(int)
queues = defaultdict(deque)
locks = defaultdict(asyncio.Lock)

async def check_rate_limit(client_ip: str):
    if len(queues[client_ip]) >= MAX_QUEUE_PER_IP:
        raise HTTPException(status_code=429, detail="Too many queued requests")
    
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    queues[client_ip].append(future)

    while queues[client_ip][0] is not future:
        try:
            await asyncio.wait_for(future, timeout=None)
        except asyncio.CancelledError:
            queues[client_ip].remove(future)
            raise HTTPException(status_code=500, detail="Request cancelled")

    async with locks[client_ip]:
        active_requests[client_ip] += 1

async def release_rate_limit(client_ip: str):
    async with locks[client_ip]:
        active_requests[client_ip] = max(active_requests[client_ip] - 1, 0)
        if queues[client_ip]:
            finished = queues[client_ip].popleft()
            if not finished.done():
                finished.set_result(True)
