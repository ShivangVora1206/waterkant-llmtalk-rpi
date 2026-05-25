#!/usr/bin/env python3
"""Benchmark STT, LLM, and TTS latencies on Pi 5."""

import asyncio
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

RUNS = 3

# ------------------------------------------------------------------
async def bench_stt():
    print("\n=== STT Benchmarks ===")
    from voice_assistant.stt.faster_whisper import FasterWhisperBackend
    import numpy as np

    for model in ["tiny.en", "base.en", "small.en"]:
        backend = FasterWhisperBackend(model_name=model, compute_type="int8")
        try:
            await backend.load()
        except Exception as e:
            print(f"  {model}: SKIP ({e})")
            continue
        for duration_s in [1, 3, 5]:
            samples = np.zeros(16000 * duration_s, dtype=np.int16)
            pcm = samples.tobytes()
            latencies = []
            for _ in range(RUNS):
                t0 = time.monotonic()
                await backend.transcribe(pcm, 16000)
                latencies.append((time.monotonic() - t0) * 1000)
            med = statistics.median(latencies)
            print(f"  {model} / {duration_s}s clip: {med:.0f} ms median")
        await backend.unload()


# ------------------------------------------------------------------
async def bench_llm():
    print("\n=== LLM Benchmarks ===")
    from voice_assistant.llm.ollama import OllamaBackend

    backend = OllamaBackend()
    if not await backend.is_available():
        print("  Ollama not running — skipping LLM benchmarks")
        return

    models = await backend.list_models()
    if not models:
        print("  No models installed — skipping")
        return

    for m in models[:3]:
        ttft_list = []
        tok_list = []
        for _ in range(RUNS):
            t0 = time.monotonic()
            count = 0
            first = None
            async for tok in backend.stream(
                [{"role": "user", "content": "Say hello in one sentence."}],
                {"model": m.name, "num_predict": 50},
            ):
                if first is None:
                    first = time.monotonic()
                count += 1
            elapsed = time.monotonic() - t0
            if first:
                ttft_list.append((first - t0) * 1000)
            if elapsed > 0 and count > 0:
                tok_list.append(count / elapsed)
        print(
            f"  {m.name}: TTFT {statistics.median(ttft_list):.0f} ms, "
            f"{statistics.median(tok_list):.1f} tok/s"
        )


# ------------------------------------------------------------------
async def bench_tts():
    print("\n=== TTS Benchmarks ===")
    from voice_assistant.tts.piper import PiperBackend

    backend = PiperBackend()
    texts = [
        "Hello, how are you today?",
        "The quick brown fox jumps over the lazy dog and runs away.",
    ]
    try:
        for text in texts:
            latencies = []
            for _ in range(RUNS):
                t0 = time.monotonic()
                chunks = []
                async for chunk in backend.synthesise(text, {}):
                    if not chunks:
                        latencies.append((time.monotonic() - t0) * 1000)
                    chunks.append(chunk)
            med = statistics.median(latencies)
            print(f"  '{text[:40]}…': first chunk {med:.0f} ms")
    except Exception as e:
        print(f"  TTS error: {e}")


# ------------------------------------------------------------------
async def main():
    print("Voice Assistant — Pi 5 Benchmarks")
    print(f"Runs per measurement: {RUNS}")
    await bench_stt()
    await bench_llm()
    await bench_tts()
    print("\nDone. Results above are medians of", RUNS, "runs.")


if __name__ == "__main__":
    asyncio.run(main())
