# ArXiv AI Research Digest 2026-05-20

> Source: [ArXiv](https://arxiv.org/) (cs.AI, cs.CL, cs.LG) | 50 papers | Generated: 2026-05-20 15:28 UTC

---

Here is the structured ArXiv AI Research Digest for 2026-05-19.

---

## Today's Highlights

Today’s submissions reveal a strong push toward **scalable inference and efficient deployment**, with significant advances in diffusion LLMs (TIDE) and time-series foundation models (Toto 2.0) that challenge the dominance of autoregressive architectures. A clear trend is the **tightening integration of reinforcement learning into post-training pipelines**, not just for verifiable rewards (RLVR) but also for rubric-aware alignment, autonomous driving, and SPARQL generation. Several papers advance **agentic systems in high-stakes domains**, including clinical reasoning (ClinSeekAgent) and theorem proving, while introducing rigorous architectural patterns for production deployment. Finally, **neuro-symbolic and interpretability-focused work** (Neurosymbolic Learning, INSHAPE) suggests a maturing field that is increasingly concerned with trust, safety, and explainability.

---

## Key Papers

### 🧠 Large Language Models (architecture, training, alignment, evaluation)

1. **TIDE: Efficient and Lossless MoE Diffusion LLM Inference with I/O-aware Expert Offload**
   Link: http://arxiv.org/abs/2605.20179v1
   Authors: Zhiben Chen, Youpeng Zhao, Yang Sui et al.
   While MoE diffusion LLMs offer parallel decoding, their memory demands are prohibitive; TIDE introduces an I/O-aware expert offloading strategy that enables lossless, efficient inference at scale.

2. **Not Every Rubric Teaches Equally: Policy-Aware Rubric Rewards for RLVR**
   Link: http://arxiv.org/abs/2605.20164v1
   Authors: Utkarsh Tyagi, Xingang Guo, MohammadHossein Rezaei et al.
   This paper addresses the gap in reinforcement learning with verifiable rewards by introducing *policy-aware* rubric rewards, enabling more nuanced post-training that respects multiple qualitative criteria simultaneously.

3. **Rewarding Beliefs, Not Actions: Consistency-Guided Credit Assignment for Long-Horizon Agents**
   Link: http://arxiv.org/abs/2605.20061v1
   Authors: Wenjie Tang, Minne Li, Sijie Huang et al.
   In partially observable environments, agents suffer from belief drift; this work proposes a novel credit assignment method that rewards internal belief consistency rather than isolated actions, dramatically improving long-horizon LLM agent performance.

4. **BalanceRAG: Joint Risk Calibration for Cascaded Retrieval-Augmented Generation**
   Link: http://arxiv.org/abs/2605.20084v1
   Authors: Zijun Jia, Yuanchang Ye, Sen Jia et al.
   A principled framework for cascaded RAG that jointly calibrates the risk of answering from memory vs. retrieval, reducing unnecessary retrieval costs without sacrificing factual accuracy.

### 🤖 Agents & Reasoning (planning, tool use, multi-agent, chain-of-thought)

5. **ClinSeekAgent: Automating Multimodal Evidence Seeking for Agentic Clinical Reasoning**
   Link: http://arxiv.org/abs/2605.20176v1
   Authors: Juncheng Wu, Letian Zhang, Yuhan Wang et al.
   A clinical agent that actively iterates, plans, and synthesizes multimodal evidence, moving beyond curated benchmarks to realistic, evidence-seeking diagnostic workflows.

6. **Neurosymbolic Learning for Inference-Time Argumentation**
   Link: http://arxiv.org/abs/2605.20098v1
   Authors: Gabriel Freedman, Adam Dejl, Adam Gould et al.
   Combines neural strength with symbolic guarantees for claim verification, providing faithful, explainable arguments even when evidence is incomplete or conflicting—critical for finance and healthcare.

7. **CopT: Contrastive On-Policy Thinking with Continuous Spaces for General and Agentic Reasoning**
   Link: http://arxiv.org/abs/2605.20075v1
   Authors: Dachuan Shi, Hanlin Zhu, Xiangchi Yuan et al.
   Proposes a *contrastive on-policy thinking* paradigm where models learn to think only when necessary, reducing token waste in chain-of-thought while maintaining or improving reasoning accuracy.

8. **A Methodology for Selecting and Composing Runtime Architecture Patterns for Production LLM Agents**
   Link: http://arxiv.org/abs/2605.20173v1
   Authors: Vasundra Srinivasan
   Names and formalizes the stochastic-deterministic boundary (SDB) as a first-class architectural contract, providing a practical methodology for building reliable production-grade LLM agents.

### 🔧 Methods & Frameworks (new techniques, benchmarks, efficiency improvements)

9. **Toto 2.0: Time Series Forecasting Enters the Scaling Era**
   Link: http://arxiv.org/abs/2605.20119v1
   Authors: Emaad Khwaja, Chris Lettieri, Gerald Woo et al.
   Demonstrates that time series foundation models reliably scale from 4M to 2.5B parameters, releasing a state-of-the-art open-weights family that sets a new benchmark for the field.

10. **Draft Less, Retrieve More: Hybrid Tree Construction for Speculative Decoding**
    Link: http://arxiv.org/abs/2605.20104v1
    Authors: Yuhao Shen, Tianyu Liu, Xinyi Hu et al.
    Reduces the VRAM and compute overhead of speculative decoding by replacing expansive draft trees with a hybrid tree construction that retrieves high-probability continuations.

11. **From Seeing to Thinking: Decoupling Perception and Reasoning Improves Post-Training of Vision-Language Models**
    Link: http://arxiv.org/abs/2605.20177v1
    Authors: Juncheng Wu, Hardy Chen, Haoqin Tu et al.
    A systematic study showing that VLM failures are primarily perceptual, not reasoning-based; decoupling these two stages yields substantial gains in downstream task performance.

12. **Active Context Selection Improves Simple Regret in Contextual Bandits**
    Link: http://arxiv.org/abs/2605.20040v1
    Authors: Mohammad Shahverdikondori, Jalal Etesami, Negar Kiyavash
    Provides worst-case guarantees for contextual bandits with finite contexts, introducing an active context selection strategy that improves simple regret over passive approaches.

### 📊 Applications (domain-specific, multimodal, code generation)

13. **KoRe: Compact Knowledge Representations for Large Language Models**
    Link: http://arxiv.org/abs/2605.20170v1
    Authors: Davide Cavicchini, Fausto Giunchiglia, Jacopo Staiano
    Addresses the fundamental flaw of LLMs encoding world knowledge in parameters by introducing compact, externalizable knowledge representations that improve factual recall and reasoning.

14. **What Do Evolutionary Coding Agents Evolve?**
    Link: http://arxiv.org/abs/2605.20086v1
    Authors: Nico Pelleriti, Sree Harsha Nelaturu, Zhanke Zhou et al.
    Provides a rigorous analysis of what evolutionary LLM-based code agents actually optimize, revealing that progress is often driven by subtle code structure changes rather than novel algorithmic discovery.

15. **Does Code Cleanliness Affect Coding Agents? A Controlled Minimal-Pair Study**
    Link: http://arxiv.org/abs/2605.20049v1
    Authors: Priyansh Trivedi, Olivier Schmitt
    A controlled study using minimal pairs of clean vs. messy codebases, demonstrating that code structural quality significantly impacts autonomous coding agent success rates.

16. **VL-DPO: Vision-Language-Guided Finetuning for Preference-Aligned Autonomous Driving**
    Link: http://arxiv.org/abs/2605.20082v1
    Authors: Zhefan Xu, Ghassen Jerfel, Marina Haliem et al.
    Applies direct preference optimization (DPO) guided by vision-language models to finetune motion forecasting, aligning autonomous driving behavior with nuanced human driving preferences.

---

## Research Trend Signal

A notable emerging direction is the **formalization and systematization of LLM agent architectures for production**. Srinivasan’s work on the stochastic-deterministic boundary is a landmark: it names a problem every practitioner faces (the unpredictable interface between LLM outputs and deterministic systems) and provides a structured vocabulary for solving it. This is part of a broader maturation visible today: we see multiple papers moving from "can we build an agent?" to "how do we make it reliable, efficient, and auditable?" (ClinSeekAgent, Neurosymbolic Argumentation). Concurrently, **scaling laws are being actively contested and extended**—Toto 2.0 brings scaling to time series, while the model collapse paper (Wu et al.) warns of fundamental limits in interactive learning loops. The field appears to be entering a phase of **deep engineering maturity** alongside continued theoretical exploration of scaling boundaries.

---

## Worth Deep Reading

1. **Toto 2.0: Time Series Forecasting Enters the Scaling Era** — This paper is essential reading for anyone interested in foundation models outside of NLP/CV. It provides the first clear demonstration that scaling laws apply to time series, releasing reproducible recipes and open models that will likely become a baseline for the entire field.

2. **A Methodology for Selecting and Composing Runtime Architecture Patterns for Production LLM Agents** — If you are building or planning to build production systems with LLMs, this paper introduces a conceptual framework (the SDB) that will directly change how you design your architecture. It is rare to see a paper that is simultaneously practical and formally rigorous.

3. **When Does Model Collapse Occur in Structured Interactive Learning?** — As synthetic data from LLMs becomes ubiquitous, this paper provides a rigorous mathematical treatment of the conditions under which model collapse occurs in interactive settings. It is a must-read for anyone concerned with the long-term sustainability of training on web-scale data increasingly polluted by AI outputs.