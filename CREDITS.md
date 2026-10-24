# Credits

**Special credit: [vcruz305](https://github.com/vcruz305).** This lane is his work with one patch on top: the
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
| **tonyd2wild** | the TP>1 patch for the fused qkv+indexer layer, the two-node launcher, the speed-night bench harness |

Our change to vcruz305's plugin is one commit, `patches/tp2-minimax-indexer.patch`. The plugin is AGPL-3.0-only, so the
patch is too; publishing it here is the source offer for the patched build we serve. The recipe is MIT.
