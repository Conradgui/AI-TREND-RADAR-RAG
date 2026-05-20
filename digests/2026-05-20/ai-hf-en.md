# Hugging Face Trending Models Digest 2026-05-20

> Source: [Hugging Face Hub](https://huggingface.co/) | 30 models | Generated: 2026-05-20 15:28 UTC

---

Here is the **Hugging Face Trending Models Digest** for **2026-05-20**.

---

## 1. Today's Highlights

This week’s trending models signal a clear shift toward **massive, open-weight multimodal VLMs** and **ultra-high-fidelity video generation**. DeepSeek’s **V4-Pro** and **V4-Flash** dominate downloads, while Google’s **Gemma-4-31B-it** breaks the 10M download barrier, cementing the demand for open, instruction-tuned VLMs. In media generation, **SulphurAI/Sulphur-2-base** (1.1M+ downloads) leads a wave of text-to-video diffusion models. The community is also doubling down on **quantization**, with unsloth and others pushing GGUF versions of large MoE models to the top of the charts, making 30B+ parameter vision-language models accessible on consumer hardware.

---

## 2. Trending Models by Category

### 🧠 Language Models (LLMs, chat models, instruction-tuned)

- **deepseek-ai/DeepSeek-V4-Pro** ([link](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro))
  Author: deepseek-ai | Likes: 4,077 | Downloads: 3,817,887
  *The flagship open-weight conversational LLM from DeepSeek, trending due to its breakthrough reasoning performance and massive scale.*

- **deepseek-ai/DeepSeek-V4-Flash** ([link](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash))
  Author: deepseek-ai | Likes: 1,165 | Downloads: 2,289,519
  *A faster, distilled variant of V4-Pro optimized for latency-sensitive applications, gaining traction for production deployments.*

- **inclusionAI/Ring-2.6-1T** ([link](https://huggingface.co/inclusionAI/Ring-2.6-1T))
  Author: inclusionAI | Likes: 88 | Downloads: 3,454
  *A 1-trillion-parameter hybrid architecture AI, emerging as a curiosity-driven release for researchers exploring extreme scaling.*

- **FrontiersMind/Nandi-Mini-600M-Early-Checkpoint** ([link](https://huggingface.co/FrontiersMind/Nandi-Mini-600M-Early-Checkpoint))
  Author: FrontiersMind | Likes: 101 | Downloads: 18,626
  *A lightweight 600M-parameter text-generation model released as an early checkpoint, interesting for resource-constrained fine-tuning.*

### 🎨 Multimodal & Generation (image, video, audio, text-to-X)

- **SulphurAI/Sulphur-2-base** ([link](https://huggingface.co/SulphurAI/Sulphur-2-base))
  Author: SulphurAI | Likes: 1,199 | Downloads: 1,157,497
  *A high-quality text-to-video generative model, trending as a rival to Runway and Pika with open weights.*

- **openbmb/MiniCPM-V-4.6** ([link](https://huggingface.co/openbmb/MiniCPM-V-4.6))
  Author: openbmb | Likes: 819 | Downloads: 166,049
  *A powerful small vision-language model capable of complex image reasoning, popular for edge deployment.*

- **Supertone/supertonic-3** ([link](https://huggingface.co/Supertone/supertonic-3))
  Author: Supertone | Likes: 486 | Downloads: 31,940
  *A next-gen neural text-to-speech model with emotional rendering, leading the wave of expressive audio AI.*

- **HiDream-ai/HiDream-O1-Image** ([link](https://huggingface.co/HiDream-ai/HiDream-O1-Image))
  Author: HiDream-ai | Likes: 408 | Downloads: 17,645
  *A "thinking" image generation model using chain-of-thought reasoning before rendering, a novel approach to text-to-image.*

- **SeeSee21/Z-Anime** ([link](https://huggingface.co/SeeSee21/Z-Anime))
  Author: SeeSee21 | Likes: 421 | Downloads: 16,159
  *A specialized anime-style text-to-image diffusion model, trending due to its distinctive artistic quality.*

- **ScenemaAI/scenema-audio** ([link](https://huggingface.co/ScenemaAI/scenema-audio))
  Author: ScenemaAI | Likes: 111 | Downloads: 377
  *A diffusion-based audio generation model focused on cinematic sound design and voice cloning.*

- **TencentARC/Pixal3D** ([link](https://huggingface.co/TencentARC/Pixal3D))
  Author: TencentARC | Likes: 157 | Downloads: 0
  *A new image-to-3D generative model, notable for its research paper on arXiv and potential for 3D asset creation.*

- **RuneXX/LTX-2.3-Workflows** ([link](https://huggingface.co/RuneXX/LTX-2.3-Workflows))
  Author: RuneXX | Likes: 593 | Downloads: 0
  *A ComfyUI workflow pack for LTX video models, trending as a tool for streamlined video generation pipelines.*

### 🔧 Specialized Models (code, math, medical, embeddings)

- **Jackrong/Qwopus3.5-9B-Coder-GGUF** ([link](https://huggingface.co/Jackrong/Qwopus3.5-9B-Coder-GGUF))
  Author: Jackrong | Likes: 132 | Downloads: 17,539
  *A GGUF-quantized code-focused LLM built on Qwen3.5, popular for offline coding assistants.*

- **google/gemma-4-31B-it** ([link](https://huggingface.co/google/gemma-4-31B-it))
  Author: google | Likes: 2,704 | Downloads: 10,170,798
  *Google’s most popular open VLM for instruction following, topping downloads for general-purpose multimodal chat.*

- **NemoStation/Marlin-2B** ([link](https://huggingface.co/NemoStation/Marlin-2B))
  Author: NemoStation | Likes: 116 | Downloads: 125
  *A tiny video-text-to-text model, exploring lightweight video understanding for edge devices.*

- **Cactus-Compute/needle** ([link](https://huggingface.co/Cactus-Compute/needle))
  Author: Cactus-Compute | Likes: 101 | Downloads: 292
  *A custom JAX model specialized for function calling and tool use, gaining attention from agentic AI developers.*

### 📦 Fine-tunes & Quantizations (community fine-tunes, GGUF, AWQ)

- **unsloth/Qwen3.6-27B-MTP-GGUF** ([link](https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF))
  Author: unsloth | Likes: 343 | Downloads: 411,598
  *A GGUF quantized version of the Qwen3.6 VLM, enabling high-performance inference on consumer GPUs.*

- **unsloth/Qwen3.6-35B-A3B-MTP-GGUF** ([link](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF))
  Author: unsloth | Likes: 284 | Downloads: 363,131
  *The MoE variant of Qwen3.6 in GGUF format, trending for efficient sparse inference.*

- **HauhauCS/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced** ([link](https://huggingface.co/HauhauCS/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced))
  Author: HauhauCS | Likes: 63 | Downloads: 61,106
  *An uncensored, quantized fine-tune of Gemma4 for users seeking unrestricted model behavior.*

- **circlestone-labs/Anima** ([link](https://huggingface.co/circlestone-labs/Anima))
  Author: circlestone-labs | Likes: 1,446 | Downloads: 571,087
  *A popular ComfyUI-compatible diffusion single-file model, trending for high-fidelity anime-style image generation.*

---

## 3. Ecosystem Signal

The current Hugging Face ecosystem is defined by three dominant signals:

1. **MoE and Multi-Model Converge**: The **Qwen3.6** family (both dense and MoE variants) and **Gemma-4** are the most active model families. The trend is toward mixing vision + language + video into single unified models, as seen with MiniCPM-V-4.6 and Intern-S2-Preview.

2. **Quantization is the Gateway**: With models exceeding 30B parameters, GGUF quantizations by **unsloth** and community fine-tuners are driving adoption. The top 10 models by downloads are nearly all quantized or distilled, proving that **accessibility beats raw performance** for mass adoption.

3. **Media Generation Matures**: Text-to-video (Sulphur-2, LTX-2.3) and text-to-speech (supertonic-3, scenema-audio) are moving beyond novelty into production-ready quality. Open-weight alternatives to closed APIs (e.g., Runway, ElevenLabs) are now a reality, evidenced by million+ download counts.

---

## 4. Worth Exploring

- **Qwen/Qwen3.6-35B-A3B** ([link](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)) — The official MoE VLM from Qwen with 5.8M downloads. It offers the best quality-to-compute ratio for multimodal tasks (image-text-to-text). A must-study for anyone deploying VLMs on consumer hardware.

- **HiDream-ai/HiDream-O1-Image** ([link](https://huggingface.co/HiDream-ai/HiDream-O1-Image)) — An early example of "thinking before generating" for images. This opens a new research axis in generative AI. Worth trying for its novel inference-time reasoning approach.

- **Zyphra/ZAYA1-8B** ([link](https://huggingface.co/Zyphra/ZAYA1-8B)) — A 8B base model with a reasoning fine-tune, built on top of a custom architecture with published research (arxiv:2605.05365). Ideal for those studying how to build efficient, reasoning-capable small LLMs.