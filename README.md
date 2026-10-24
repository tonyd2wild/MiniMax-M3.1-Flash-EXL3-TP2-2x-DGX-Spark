# MiniMax-M3.1-Flash EXL3 (SAGE 2.15 bpw) on two DGX Sparks: TP2, 300K context

> **Special credit: [vcruz305](https://github.com/vcruz305).** The pack, the serving image and both runtime forks are
> his ([CREDITS.md](CREDITS.md)). His [one-Spark recipe](https://github.com/vcruz305/MiniMax-M3.1-Flash-EXL3-Spark-recipe)
> lists the two-Spark path as "not validated yet, help wanted". This repo is that path: two small plugin patches,
> a two-node launcher and measurements.

[`vcruz305/MiniMax-M3.1-Flash-EXL3-SAGE-2.15bpw`](https://huggingface.co/vcruz305/MiniMax-M3.1-Flash-EXL3-SAGE-2.15bpw)
(428B total / 23B active, MiniMax sparse attention, DSpark draft head) served at **tensor-parallel 2 across two
NVIDIA DGX Spark (GB10) nodes**, weights on one node and read by the other over NFS.

| | |
|---|---|
| nodes | rank 0 + HTTP on one Spark, rank 1 headless on the other; NCCL over RoCE |
| weights | 108.6 GiB pack on rank 0's disk, rank 1 reads the same folder over NFS (no second copy) |
| context | **300,000 tokens** per request |
| KV pool | **726,578 tokens** (2.42 full-length requests at once); q4 main KV, fp8 indexer and draft KV |
| speculative decoding | DSpark, 3 draft tokens per step |
| boot to `/v1/models` | 350 s (rank 1 loads its half in 83 s over NFS) |
| free memory at ready | ~30 GiB per node |

## Results (2026-10-24)

Temperature 0, the model's default reasoning, measured on the head node against the lane itself.
Harness: [`bench/bench_tp2_night.py`](bench/bench_tp2_night.py).

**Single stream** (decode tok/s, median of 2; DSpark acceptance rate and mean accepted tokens per step)

| prompt | decode tok/s | TTFT | acceptance | tokens per step |
|---|---|---|---|---|
| count to 300 | **39.4** | 0.70 s | 99% | 3.98 |
| count to 100 | **38.1** | 0.69 s | 94% | 3.81 |
| tool call | **33.8** | 0.83 s | 86% | 3.57 |
| json | **31.8** | 0.70 s | 74% | 3.21 |
| structured (YAML) | **31.0** | 0.72 s | 72% | 3.17 |
| code | **30.4** | 0.73 s | 71% | 3.13 |
| sql | **29.4** | 0.69 s | 67% | 3.02 |
| math | **28.4** | 0.75 s | 64% | 2.93 |
| prose | **19.8** | 0.67 s | 33% | 2.00 |
| narrative | **19.7** | 0.61 s | 32% | 1.95 |
| summary | **19.5** | 0.65 s | 31% | 1.92 |

**C1 to C6 per prompt type, mixed C1 to C6 throughput, cold prefill:** running; charts and tables land here when
the run finishes.

**Correctness smoke test** ([`bench/smoke.py`](bench/smoke.py)): 4/4. "Paris", "391" for 17 × 23, a correct
`is_prime`, and "Il fait beau aujourd'hui." Reasoning arrives separately from the answer.

## What it took

**1. The 4.26 bpw pack does not fit two Sparks.** vcruz305's two-Spark pack is 209.9 GiB. At TP2 that is
106.1 GiB of weights per node (measured after load), leaving 1.72 GiB free on a 121.7 GiB node before any KV or
the 2.1 GiB draft; our memory guard stopped the lane at 201 MiB free. It also stores every attention projection,
the shared experts and the dense MLPs in MiniMax's native MXFP8, not EXL3, so it needs a config overlay to route
those to vLLM's MXFP8 kernels ([`configs/4.26bpw-quantization-overlay.json`](configs/4.26bpw-quantization-overlay.json)).
With that overlay it should fit at TP4 (about 53 GiB per node); not run yet.

**2. The 2.15 bpw pack at TP2 needed two plugin patches.** The vllm-exl3 plugin refused TP > 1 in two places:

| patch | refusal | fix |
|---|---|---|
| [`tp2-minimax-indexer.patch`](patches/tp2-minimax-indexer.patch) | `EXL3 MiniMax indexer shards are not supported with TP size > 1` | MiniMax fuses its sparse-attention indexer (`index_q`, `index_k`, MXFP8) into the QKV GEMM. vLLM shards `index_q` like the KV heads and replicates `index_k` (one head); the patch cuts each rank's rows of the MXFP8 payload and its E8M0 scales with the same rule the plugin already uses for QKV weights |
| [`tp2-minimax-lmhead.patch`](patches/tp2-minimax-lmhead.patch) | `EXL3 padded linear geometry requires tensor parallel size 1` (LM head) | EXL3 rotates the output dim in 128-row blocks, and a 200,064-row vocab split in two (100,032) is not 128-aligned. Every rank loads the whole 8-bit head (0.6 GiB more per node) and returns only its vocab columns, so vLLM's logits gather is unchanged |

Both are one commit each on top of the plugin pin `41fdb7d`; apply them in this order.

**3. One launch flag.** With the KV pool pinned by `--kv-cache-memory-bytes`, vLLM still compares free memory
against `--gpu-memory-utilization` (default 0.92 × 121.7 GiB) at startup; 0.85 passes it and changes nothing else.

Memory per node at TP2: ~54 GiB of weights, 18.63 GiB of KV (`--kv-cache-memory-bytes 20000000000`), i.e.
26.9 KiB per token per node, and ~30 GiB free at ready.

## Run it

1. Build vcruz305's image on **both** nodes exactly as his recipe says (pinned vLLM digest, his exllamav3 and
   vllm-exl3 forks), with both patches applied to the plugin checkout first, indexer then LM head
   (`git am`; his `build_image.sh` accepts commits on top of the pins). Or build his image unpatched and mount the
   patched `vllm_exl3/exl3.py` over the installed one, which is what [`scripts/m31_tp2.sh`](scripts/m31_tp2.sh)
   does when `~/m31tp2/exl3.py` exists.
2. Download and verify the pack on the head node with his `download_and_verify.sh` (pinned revision
   `99bf3a57`, every file hashed). On the second node, NFS-mount the head's model folder read-only.
3. Edit the hosts, fabric IPs and RoCE device names at the top of `scripts/m31_tp2.sh`, then on the head:

   ```bash
   bash scripts/m31_tp2.sh serve     # rank 1 (headless) first, then rank 0; waits for /v1/models
   bash scripts/m31_tp2.sh status
   bash scripts/m31_tp2.sh stop
   ```

   The launcher arms a memory guard on both nodes (kills the lane below 700 MiB free) and drops the page cache
   every 20 s, because on GB10's unified memory a 100+ GiB load leaves page cache that the GPU allocator cannot
   reclaim in time.

The lane is text only: the 2.15 bpw pack has no vision-tower weights.

## Files

| path | what |
|---|---|
| `scripts/m31_tp2.sh` | two-node launcher (`serve`, `stop`, `status`, `logs`, `render`) |
| `scripts/fwd_8003.py` | stdlib TCP forwarder; keeps an existing client route (`:8003`) pointed at the lane without restarting clients |
| `patches/` | the two plugin patches (AGPL-3.0-only, like the plugin) |
| `configs/4.26bpw-quantization-overlay.json` | quantization block that routes the 4.26 bpw pack's MXFP8 layers to vLLM (for a TP4 attempt) |
| `bench/bench_tp2_night.py` | speed harness: single stream per prompt type, C1 to C6 per type, mixed C1 to C6, cold prefill |
| `bench/smoke.py` | four-question correctness check |
| `results/` | raw JSON from the benchmark runs |

Licensing: the patches are AGPL-3.0-only because the plugin is; everything else here is MIT.
