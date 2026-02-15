# MediVault AI Healthcare 🏥

**MediVault** is a patient-owned AI medical vault system designed to solve the problem of fragmented medical records in India. It empowers citizens to digitize, understand, and securely share their health data using an autonomous, agentic AI pipeline.

---

## 🚀 Phase 1 Submission: Core Features

### 1. The Trusted Pipeline (HITL & Normalization)
MediVault transforms unstructured, handwritten prescriptions into structured data. 
* **Human-in-the-Loop (HITL):** Patients validate AI extractions before they are stored, ensuring 100% data accuracy.
* **AWS Services:** Uses **Amazon Textract** for OCR and **Amazon Bedrock** for medical text normalization.

### 2. The Safety Engine (RAG-Grounded Reasoning)
The system doesn't just store data; it protects the patient.
* **Autonomous Interaction Checks:** Uses **Retrieval-Augmented Generation (RAG)** to cross-reference new medications against the patient's vault.
* **Zero Hallucinations:** All safety alerts are grounded in authoritative medical databases stored in **Amazon Bedrock Knowledge Bases**.

### 3. The Accessibility Layer (Regional Voice Output)
Built for "Bharat," MediVault breaks literacy and language barriers.
* **Multilingual Voice:** Converts complex medical jargon into simplified audio summaries in 7+ Indian regional languages using **Amazon Polly**.
* **Offline Emergency Access:** Critical life-saving info (allergies, blood group) is cached for offline QR-code access in low-connectivity areas.

---

## 🛠️ Tech Stack (AWS Native)

| Service | Purpose |
| :--- | :--- |
| **Amazon Bedrock** | Agentic reasoning, normalization, and RAG |
| **Amazon Textract** | Handwriting and printed text extraction |
| **Amazon Polly** | Regional voice synthesis (Accessibility) |
| **Knowledge Bases** | Grounded medical data & interaction checking |
| **Amazon RDS** | Secure, structured medical entity storage |

---

## 📂 Project Structure

* [`requirements.md`](./requirements.md): Detailed functional and non-functional requirements (EARS format).
* [`design.md`](./design.md): System architecture, AWS service integration, and Mermaid diagrams.

---

## 🇮🇳 Impact for Bharat
MediVault is designed for rural healthcare settings where medical records are often lost or misunderstood. By combining **Agentic AI** with **Voice Accessibility**, we are making high-quality health data management accessible to every Indian citizen, regardless of their literacy level or location.