#!/usr/bin/env python3
"""fwd_8003.py: TCP forwarder 0.0.0.0:8003 -> 127.0.0.1:8000 (keeps dsh's minimax31 route, Bluey :8003, pointed
at the MiniMax TP2 lane without restarting dsh or the :8905 proxy). Stdlib only; streams pass through untouched."""
import asyncio

LISTEN, TARGET = ("0.0.0.0", 8003), ("127.0.0.1", 8000)

async def pipe(r, w):
    try:
        while data := await r.read(65536):
            w.write(data)
            await w.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        w.close()

async def handle(cr, cw):
    try:
        ur, uw = await asyncio.open_connection(*TARGET)
    except OSError:
        cw.close(); return
    await asyncio.gather(pipe(cr, uw), pipe(ur, cw))

async def main():
    srv = await asyncio.start_server(handle, *LISTEN)
    async with srv:
        await srv.serve_forever()

asyncio.run(main())
