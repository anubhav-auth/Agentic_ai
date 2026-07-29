# Model File Formats & GGUF

*Task: what other model formats exist, and what is GGUF among them?*

Model *file formats* are how trained weights (and sometimes metadata/tokenizer/config) get packaged for storage and inference — separate from the model's architecture or size. Different formats trade off portability, hardware target, and inference speed.

---

## 1. Common Model Formats

| Format | Origin / Ecosystem | Purpose | Typical Hardware |
|---|---|---|---|
| **PyTorch (.pt / .pth)** | PyTorch | Native raw weights from training; requires the full PyTorch framework to load. Uses Python's `pickle`, which can execute arbitrary code — a known security risk with untrusted files. | GPU (training/full-precision inference) |
| **Safetensors** | Hugging Face | A safer replacement for `.pt/.pth` — no arbitrary code execution risk, faster to load. Now the default format on the Hugging Face Hub. | GPU/CPU |
| **ONNX** | Open Neural Network Exchange (Microsoft/community) | Cross-framework interoperable format; export once, run on many runtimes/hardware backends via ONNX Runtime. | CPU/GPU, cross-platform |
| **TensorRT-LLM engine** | NVIDIA | Compiled, hardware-specific engine optimized for maximum inference speed on NVIDIA GPUs. | NVIDIA GPU only |
| **Core ML (.mlmodel / .mlpackage)** | Apple | Native format for deploying models inside iOS/macOS apps. | Apple devices |
| **TensorFlow Lite (.tflite)** | Google/TensorFlow | Lightweight format for mobile/edge deployment in the TensorFlow ecosystem. | Mobile/edge |
| **MLX** | Apple | Format/framework for efficient on-device inference on Apple Silicon (M-series chips). | Mac (Apple Silicon) |
| **GPTQ / AWQ** | Research community | Quantization *schemes* (usually distributed as safetensors variants) optimized for fast, low-memory GPU inference at 4-bit precision. | GPU |
| **GGUF** | llama.cpp / GGML project | See below. | CPU, low-VRAM GPU, edge/mobile |

---

## 2. What Is GGUF?

**GGUF (GPT-Generated Unified Format)** is the successor to the earlier GGML format, built for the `llama.cpp` inference ecosystem.

**What makes it different:**
- **Single-file, self-contained:** weights, tokenizer, and model metadata/config are bundled into one file — no separate config.json/tokenizer files needed, unlike Hugging Face-style checkpoints.
- **Built for quantization:** GGUF is designed around running heavily quantized models (e.g., 4-bit, 5-bit, 8-bit) efficiently, dramatically shrinking file size and memory needs with a controlled quality trade-off. Common quant levels: `Q4_0`, `Q4_K_M`, `Q5_K_M`, `Q8_0` — roughly, lower numbers = smaller/faster/lower quality, higher = larger/slower/closer to full precision.
- **Optimized for CPU and low-resource inference:** GGUF is the format of choice for running LLMs on a laptop CPU, a machine with limited VRAM, or edge/embedded hardware — not just GPU data centers.
- **Ecosystem:** used by `llama.cpp`, **Ollama**, **LM Studio**, `koboldcpp`, and `text-generation-webui` — essentially the standard format for "run an open-weight LLM locally on your own machine" tooling.

**When to use GGUF vs. safetensors/PyTorch:**
- Use **GGUF** when the goal is local/offline/edge deployment, limited hardware, or minimal setup (e.g., running a model via Ollama on a laptop).
- Use **safetensors/PyTorch** when doing training, fine-tuning, or serving from a GPU-backed production environment via the Hugging Face/PyTorch stack.
- Use **ONNX or TensorRT-LLM** when the priority is cross-platform interoperability or maximum production inference throughput on specific hardware, respectively.

---

## 3. Quick Summary

GGUF isn't a competitor to formats like safetensors for training — it's specifically the packaging format that made running capable open-weight LLMs practical on ordinary consumer hardware (a laptop, a desktop with a modest GPU, even some phones), by combining single-file portability with efficient quantization.
