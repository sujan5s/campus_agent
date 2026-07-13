# 06 — Retrieval-Augmented Generation (RAG) Knowledge Assistant

## What the concept is

**RAG** combines information retrieval with an LLM: instead of answering from parametric memory
(which hallucinates), the model retrieves relevant chunks from a trusted document store and
answers grounded in them, **with citations**. Our **Knowledge Agent** (Phase 3) uses RAG over the
college's own documents (circulars, handbook, academic calendar) so campus questions are answered
accurately and verifiably.

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| Domain-Specific Retrieval-Augmented Generation Using Vector Stores, Knowledge Graphs, and Tensor Factorization | [IEEE, 2025](https://ieeexplore.ieee.org/document/10903241/) | Combines vector stores + knowledge graphs for domain-specific RAG accuracy | More complex infra (KG + tensor factorization) | Confirms vector-store RAG for a domain corpus; KG is a future upgrade path |
| QuIM-RAG: Advancing RAG With Inverted Question Matching for Enhanced QA | [IEEE Access, vol. 12, 2024](https://ieeexplore.ieee.org/) (Saha, Saha, Malik) | Inverted question–chunk matching improves QA retrieval precision | Adds a matching layer; more indexing cost | Retrieval-quality technique if naive similarity search underperforms |
| ICCA-RAG: Intelligent Customs Clearance Assistant Using RAG | [IEEE Access, vol. 13, 2025](https://ieeexplore.ieee.org/) (Hu et al.) | Domain assistant (customs) built on RAG answering regulatory questions | Narrow domain; regulatory | **Template for a domain assistant** — ours is the campus equivalent |
| Enhancing Precision & Interpretability of RAG in Legal Technology: A Survey | [IEEE Access, vol. 13, 2025](https://ieeexplore.ieee.org/) (Hindi et al.) | Surveys precision + interpretability (citations) in high-stakes RAG | Survey; legal focus | Motivates our **citation requirement** — answers must be traceable to a source |
| A Novel Framework for Educational Q&A: Leveraging RAG and Code Interpreters | [PMC/NCBI, 2024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12668533/) | RAG + code interpreter for educational question answering | Adds code-exec complexity | Direct evidence RAG works for **educational** Q&A — our exact use case |
| A Research of Challenges and Solutions in RAG Systems | [HSET, 2024](https://drpress.org/ojs/index.php/HSET/article/view/28756) | Catalogues RAG challenges (retrieval quality, hallucination, chunking) + solutions | Survey | Checklist of pitfalls we design around (chunk size, "say I don't know") |

## How it maps to our project

Our **`app/rag/`** module (Phase 3) ingests PDFs → chunks → embeddings → **ChromaDB** vector
store; the Knowledge Agent retrieves top-k chunks and answers grounded in them, **citing the
source document and page**. The domain-assistant papers (ICCA-RAG customs, legal-RAG survey) are
our closest analogues — we build the **campus** version. The educational-QA paper (PMC) confirms
RAG is appropriate for education, and the challenges survey (HSET) gives us the failure list we
guard against, especially the rule that the agent must say "not found" rather than invent policy.
