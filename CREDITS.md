# Credits

**Special credit: [vcruz305](https://github.com/vcruz305).** This lane is his work with two small patches on top: the
[MiniMax-M3.1-Flash-EXL3-SAGE-4.26bpw](https://huggingface.co/vcruz305/MiniMax-M3.1-Flash-EXL3-SAGE-4.26bpw) pack
(SAGE mixed-precision EXL3), the pinned
[MiniMax-M3.1-Flash-EXL3-Spark-recipe](https://github.com/vcruz305/MiniMax-M3.1-Flash-EXL3-Spark-recipe) (one Spark,
2.15 bpw) whose Dockerfile, build script and measured flag set we reuse, and his forks of
[exllamav3](https://github.com/vcruz305/exllamav3) (`feat/moe-act3-batched`) and
[vllm-exl3](https://github.com/vcruz305/vllm-exl3) (`feat/minimax-q4-prefill`). His recipe lists the two-Spark 4.26 bpw
path as "not validated yet, help wanted"; this repo is that path.

| who | what we use |
|---|---|
| **vcruz305** | the pack, the recipe image and flags, both runtime forks (see above) |
| **MiniMax** ([MiniMax-M3.1-Flash](https://huggingface.co/MiniMaxAI/MiniMax-M3.1-Flash)) | the model; MSA sparse attention; the DSpark draft head |
| **turboderp** ([exllamav3](https://github.com/turboderp-org/exllamav3), MIT) | the EXL3 format and kernels under vcruz305's fork |
| **vLLM project** (Apache-2.0) | the engine (`vllm/vllm-openai:minimax-m31-flash`, pinned by digest), MiniMax-M3 model code, multi-node TP |
| **tonyd2wild** | the two TP>1 patches (fused qkv+indexer layer, LM head), the two-node launcher, the speed-night bench harness |

Our changes to vcruz305's plugin are two commits, `patches/tp2-minimax-indexer.patch` and `patches/tp2-minimax-lmhead.patch`.
The plugin is AGPL-3.0-only, so the patches are too; publishing it here is the source offer for the patched build we serve. The recipe is MIT.
