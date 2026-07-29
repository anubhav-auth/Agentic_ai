# 🚀 Fine-Tuning Qwen2.5-7B using Unsloth for Finance Question Answering

<div align="center">

![PyTorch](https://img.shields.io/badge/PyTorch-2.x-red?style=for-the-badge&logo=pytorch)
![Transformers](https://img.shields.io/badge/HuggingFace-Transformers-yellow?style=for-the-badge&logo=huggingface)
![Unsloth](https://img.shields.io/badge/Unsloth-LoRA-green?style=for-the-badge)
![Google Colab](https://img.shields.io/badge/Google-Colab-F9AB00?style=for-the-badge&logo=googlecolab)

###  Model Fine-Tuning using **Qwen2.5-7B**, **LoRA**, and **Unsloth**

</div>

---

# 📖 Overview

This project demonstrates an end-to-end workflow for **fine-tuning the Qwen2.5-7B-Instruct Large Language Model** using **Unsloth** and **LoRA (Low-Rank Adaptation)**.

The model was instruction-tuned on a **Finance Question Answering** dataset and validated using inference after training.

The project covers:

- Dataset Preparation
- Instruction Formatting
- LoRA Fine-Tuning
- Training using Unsloth
- Model Evaluation
- LoRA Adapter Export
- (Optional) GGUF Export for Ollama

---

# ✨ Features

- ✅ Qwen2.5-7B-Instruct
- ✅ LoRA Fine-Tuning
- ✅ Unsloth
- ✅ Hugging Face Transformers
- ✅ Google Colab
- ✅ Finance Instruction Dataset
- ✅ Chat Template Formatting
- ✅ Inference Validation
- ✅ GGUF Export Ready

---

# 🏗️ Architecture

```mermaid
flowchart LR

A[Finance Dataset] --> B[Instruction Formatting]

B --> C[Qwen2.5-7B Base Model]

C --> D[LoRA Adapter]

D --> E[Fine-Tuning with Unsloth]

E --> F[Inference Testing]

F --> G[LoRA Adapter]

G --> H[Optional GGUF Export]
```

---

# 🧠 Fine-Tuning Pipeline

```text
Finance Dataset
       │
       ▼
Instruction Formatting
       │
       ▼
Qwen2.5-7B Base Model
       │
       ▼
LoRA Adapter
       │
       ▼
Unsloth Trainer
       │
       ▼
Fine-Tuned Model
       │
       ├────────► Inference
       │
       └────────► GGUF (Optional)
```

---

# 📂 Project Structure

```text
Qwen2.5-Finance-Finetuning
│
├── notebook/
│     └── Qwen2.5_Finetuning.ipynb
│
├── dataset/
│     └── finance_dataset.jsonl
│
├── outputs/
│     └── finance_qwen_lora/
│
├── screenshots/
│
│     ├── model_loading.png
│     ├── dataset.png
│     ├── training_logs.png
│     ├── inference.png
│     └── architecture.png
│
├── README.md
├── requirements.txt
└── LICENSE
```

---

# ⚙️ Tech Stack

| Component | Technology |
|------------|------------|
| Language | Python |
| Framework | PyTorch |
| LLM | Qwen2.5-7B-Instruct |
| Fine-Tuning | LoRA |
| Library | Unsloth |
| Transformers | Hugging Face |
| Dataset | Finance QA |
| Environment | Google Colab |

---

# 📊 Training Configuration

>(be specific about the models either you gonna burn your system or drain your cloud)

| Parameter | Value |
|------------|------:|
| Base Model | Qwen2.5-7B-Instruct  |
| Fine-Tuning | LoRA |
| Rank (r) | 16 |
| Alpha | 16 |
| Batch Size | 2 |
| Gradient Accumulation | 4 |
| Epochs | 3 |
| Max Sequence Length | 2048 |
| Optimizer | AdamW or SCG |

---

# 📈 Training Results

Training loss decreased consistently throughout fine-tuning, indicating successful adaptation to the finance instruction dataset.

| Step | Loss |
|------:|-----:|
| 1 | 4.11 |
| 2 | 2.86 |
| 3 | 2.45 |
| 4 | 2.04 |
| 5 | 1.92 |

---


---

# 💻 Example Inference

### Input

```text
What is UPI?
```

### Output

```text
UPI (Unified Payments Interface) is a real-time payment system developed by NPCI that enables instant bank-to-bank transfers.
```

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/repo-name.git
```

## Install

```bash
pip install -r requirements.txt
```

## Launch Notebook

Open:

```text
Qwen2.5_Finetuning.ipynb
```

Run all cells.

---

# 📦 Output

The notebook produces:

- Fine-Tuned LoRA Adapter
- Tokenizer
- Training Logs
- Inference Example
- Optional GGUF Model

---

# 🔮 Future Improvements

- Larger Finance Dataset
- RAG Integration
- QLoRA
- Evaluation Benchmarks
- Hugging Face Deployment
- Ollama Integration
- Model Quantization

---

