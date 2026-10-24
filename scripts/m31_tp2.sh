#!/bin/bash
# m31_tp2.sh serve|stop|status|logs   (run on Bluey)
# MiniMax-M3.1-Flash EXL3 SAGE (default 2.15 bpw), TP=2 across Bluey (rank 0, HTTP) + Asusi (rank 1, headless).
# Weights live on Bluey; Asusi reads the same folder over NFS (/mnt/bluey-models).
# Engine: vcruz305's MiniMax-M3.1 recipe image (pinned vLLM + exllamav3 fork + vllm-exl3 plugin)
# with our TP>1 patch for the fused qkv+indexer layer.
set -uo pipefail
NAME=${NAME:-m31-tp2}
IMAGE=${IMAGE:-m31-flash-exl3-spark:dev-fdd77361-4ed38d8}
MODEL=${MODEL:-MiniMax-M3.1-Flash-EXL3-SAGE-2.15bpw}
SERVED=${SERVED:-minimax-m3.1-flash}
PORT=${PORT:-8000}
MAXLEN=${MAXLEN:-300000}
SEQS=${SEQS:-6}
MNBT=${MNBT:-4096}
CAPTURE=${CAPTURE:-1,2,3,4,8,12,16,24}
KVB=${KVB:-20000000000}           # per rank; ~26.9 KiB/token at TP2 -> ~2.4 full 300K requests (re-read the boot log)
GUARD_MIB=${GUARD_MIB:-700}
MASTER=192.168.192.1; MPORT=${MPORT:-29511}
ASUSI=tonyspark3@192.168.192.3
K="-i $HOME/.ssh/id_ed25519_shared -o BatchMode=yes -o ConnectTimeout=10"

run_rank() {  # rank models_dir host_ip extra...
  local rank=$1 mdir=$2 ip=$3; shift 3
  local spec='{"method":"dspark","num_speculative_tokens":3,"attention_backend":"TRITON_ATTN","kv_cache_dtype":"fp8","draft_sample_method":"probabilistic","rejection_sample_method":"block"}'
  local cc='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":['"$CAPTURE"'],"mode":0}'
  cat <<EOF
mkdir -p \$HOME/m31-cache && docker rm -f $NAME >/dev/null 2>&1; sync; echo 1 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null
OV=; [ -f \$HOME/m31tp2/exl3.py ] && OV="-v \$HOME/m31tp2/exl3.py:/usr/local/lib/python3.12/dist-packages/vllm_exl3/exl3.py:ro"
[ -f \$HOME/m31tp2/config-$MODEL.json ] && OV="\$OV -v \$HOME/m31tp2/config-$MODEL.json:/models/$MODEL/config.json:ro"
docker run -d --name $NAME \$OV --network host --ipc host --gpus all --device /dev/infiniband --cap-add IPC_LOCK \\
  --ulimit memlock=-1:-1 --ulimit core=0 --shm-size 2g --memory=118g --memory-swap=118g --oom-score-adj 1000 \\
  --security-opt seccomp=unconfined -v $mdir:/models:ro -v \$HOME/m31-cache:/cache \\
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e VLLM_HOST_IP=$ip \\
  -e NCCL_SOCKET_IFNAME=enp1s0f0np0 -e GLOO_SOCKET_IFNAME=enp1s0f0np0 -e NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0 -e NCCL_IB_GID_INDEX=3 \\
  -e VLLM_EXL3_MODEL_DIR=/models/$MODEL -e VLLM_EXL3_Q4KV=1 -e VLLM_EXL3_INDEXER_MXFP8=1 \\
  -e MIMALLOC_PURGE_DELAY=0 -e MIMALLOC_RESET_DELAY=0 -e MALLOC_ARENA_MAX=2 \\
  -e VLLM_EXL3_TRIM_AFTER_LAYER=1 -e VLLM_EXL3_UMA_POSTLOAD=1 -e VLLM_EXL3_ATS_ALIAS=1 -e VLLM_EXL3_ATS_ALIAS_EMBED=1 \\
  -e VLLM_EXL3_DRAFT_VOCAB_META=1 -e VLLM_EXL3_TRIM_BEFORE_KV=1 -e VLLM_EXL3_MOE_TEMP_ROWS=512 -e VLLM_EXL3_PERIODIC_TRIM_S=30 \\
  -e VLLM_TRITON_JIT_WARMUP_NUM_THREADS=1 -e TORCHINDUCTOR_COMPILE_THREADS=1 \\
  -e TRITON_CACHE_DIR=/cache/triton -e CUDA_CACHE_PATH=/cache/nv-compute -e CUDA_CACHE_MAXSIZE=4294967296 \\
  -e XDG_CACHE_HOME=/cache -e VLLM_CACHE_ROOT=/cache/vllm \\
  --entrypoint vllm $IMAGE serve /models/$MODEL \\
  --tensor-parallel-size 2 --nnodes 2 --node-rank $rank --master-addr $MASTER --master-port $MPORT \\
  --language-model-only --block-size 128 --disable-hybrid-kv-cache-manager \\
  --max-model-len $MAXLEN --max-num-seqs $SEQS --max-num-batched-tokens $MNBT \\
  --gpu-memory-utilization ${GMU:-0.85} --kv-cache-memory-bytes $KVB --kv-cache-dtype nvfp4 --attention-config '{"indexer_kv_dtype":"fp8"}' \\
  --speculative-config '$spec' --compilation-config '$cc' --max-cudagraph-capture-size ${CAPTURE##*,} \\
  --kernel-config '{"enable_flashinfer_autotune":false}' \\
  $* >/dev/null && echo "rank $rank container started"
nohup bash -c 'low=0; t=0; while docker inspect -f "{{.State.Running}}" $NAME 2>/dev/null | grep -q true; do
  a=\$(awk "/MemAvailable/{print int(\\\$2/1024)}" /proc/meminfo); echo "\$(date +%T) \$a" >> \$HOME/m31-guard.log
  if [ "\$a" -lt $GUARD_MIB ]; then low=\$((low+1)); else low=0; fi
  if [ \$low -ge 3 ]; then echo "\$(date +%T) GUARD KILL MemAvailable \${a} MiB" >> \$HOME/m31-guard.log; docker kill $NAME; fi
  t=\$((t+1)); [ \$((t % 20)) -eq 0 ] && { sync; echo 1 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null; }
  sleep 1; done' >/dev/null 2>&1 &
EOF
}

case "${1:-}" in
  serve)
    docker stop comfy-studio >/dev/null 2>&1; ssh $K $ASUSI "docker stop comfy-studio >/dev/null 2>&1"; echo "comfy-studio stopped on Bluey + Asusi (docker start comfy-studio to bring it back)"
    run_rank 1 /mnt/bluey-models 192.168.192.3 --headless | ssh $K $ASUSI bash
    sleep 5
    run_rank 0 /var/tmp/models 192.168.192.1 --host 0.0.0.0 --port $PORT --served-model-name $SERVED \
      --reasoning-parser minimax_m3 --tool-call-parser minimax_m3 --enable-auto-tool-choice \
      --override-generation-config "'{\"max_new_tokens\": 32768}'" | bash
    echo "waiting for :$PORT ..."
    for i in $(seq 1 180); do
      curl -sf localhost:$PORT/v1/models >/dev/null && { echo "UP after $((i*10))s: $(curl -s localhost:$PORT/v1/models)"; exit 0; }
      docker inspect -f '{{.State.Running}}' $NAME 2>/dev/null | grep -q true || { echo "rank 0 container exited"; docker logs --tail 40 $NAME 2>&1; exit 1; }
      sleep 10; done; echo "not up after 30 min"; exit 1 ;;
  render) run_rank 1 /mnt/bluey-models 192.168.192.3 --headless; echo "#####"
          run_rank 0 /var/tmp/models 192.168.192.1 --host 0.0.0.0 --port $PORT --served-model-name $SERVED \
            --reasoning-parser minimax_m3 --tool-call-parser minimax_m3 --enable-auto-tool-choice \
            --override-generation-config "'{\"max_new_tokens\": 32768}'" ;;
  stop) docker rm -f $NAME; ssh $K $ASUSI "docker rm -f $NAME" ;;
  status) for h in local $ASUSI; do if [ $h = local ]; then docker ps --filter name=$NAME --format "bluey {{.Status}}"; else ssh $K $h "docker ps --filter name=$NAME --format 'asusi {{.Status}}'"; fi; done
          curl -s -m 3 localhost:$PORT/v1/models || echo ":$PORT down"; echo; tail -1 ~/m31-guard.log 2>/dev/null ;;
  logs) docker logs --tail ${2:-60} $NAME 2>&1; echo "--- asusi"; ssh $K $ASUSI "docker logs --tail ${2:-30} $NAME 2>&1" ;;
  *) echo "usage: $0 serve|stop|status|logs [n]"; exit 2 ;;
esac
