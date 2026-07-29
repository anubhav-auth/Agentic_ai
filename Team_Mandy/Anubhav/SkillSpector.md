# 🔍 NVIDIA SkillSpector – AI Skill Security Analysis

A hands-on exploration of **NVIDIA SkillSpector**, a security scanner for AI agent skills. This project demonstrates how to scan AI skills from **ClawHub/OpenClaw** and identify potential security risks using static analysis.

---

## 📌 Overview

This project focuses on:

- Installing and configuring NVIDIA SkillSpector
- Downloading AI skills from ClawHub
- Performing static security analysis
- Understanding LLM-assisted vs static inspection
- Reviewing generated security reports

---

## 🛠 Tech Stack

- Python 3.12+
- NVIDIA SkillSpector
- Virtual Environment (`venv`)
- Markdown (`SKILL.md`)
- macOS

---

## 📂 Skills Analysed

- GitHub
- Weather
- OpenAI Whisper

---

## 📁 Project Structure

```text
SkillSpector-Lab/
├── skills/
│   ├── github/
│   │   └── SKILL.md
│   ├── weather/
│   │   └── SKILL.md
│   └── openaiwhisper/
│       └── SKILL.md
├── reports/
└── README.md
```

---

## ⚙️ Setup

### Clone SkillSpector

```bash
git clone https://github.com/NVIDIA/SkillSpector.git
cd SkillSpector
```

### Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install

```bash
make install
```

---

## 🚀 Running a Scan

Static analysis:

```bash
skillspector scan ~/Downloads/SKILLS/github --no-llm
```

Generate JSON report:

```bash
skillspector scan ~/Downloads/SKILLS/github \
    --format json \
    --output report.json
```

---

## 📊 Sample Results

| Skill | Risk Score | Severity | Result |
|--------|-----------:|----------|--------|
| GitHub | 0/100 (No severity) | Low | ✅ No security issues detected |
| Weather | 0/100 (partial severity) | Low | ✅ No security issues detected |
| OpenAI Whisper | 0/100 (partial severity) | Low | ✅ No security issues detected |

---

## 📖 Key Learnings

- AI agent skills can be inspected before installation.
- Static analysis works without an LLM.
- Semantic analysis requires an LLM provider/API key.
- SkillSpector reports overall risk, coverage, and inspection status.
- Security scanning helps identify unsafe patterns early in the development lifecycle.

---

## 📚 References

- NVIDIA SkillSpector
- ClawHub
- OpenClaw

---

## ⭐ Acknowledgements

Thanks to the NVIDIA SkillSpector project and the OpenClaw ecosystem for providing tools to improve the security of AI agent skills.
