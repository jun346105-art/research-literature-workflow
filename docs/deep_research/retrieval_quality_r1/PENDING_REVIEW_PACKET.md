# Retrieval Quality R1 — Pending Evidence Review Packet

> Status: evidence-assisted audit only. All 28 canonical records remain `pending_review`. Recommendations below are not user approval and are not ground truth.

## How to use this packet

- Check whether the question is answerable from the quoted frozen-corpus text, whether every proposed qrel is relevant, and whether additional passages should be added.
- Record the decision only in the separate review workflow after considering the evidence. This packet does not alter `pending_candidates.json`, its CSV, or the manifest.
- For no-answer/hard-negative records, the listed BM25-EN neighbors are lexical probes, not proof that no answer exists. A human must still inspect the corpus-level claim.
- Locator format is the stable `passage_id`; the corpus has page ranges but no normalized section field.

## Quality audit summary

- `recommend_keep`: 3 (`D010`, `H015`, `H016`).
- `recommend_revise`: 0.
- `recommend_replace`: 25.
- Critical split finding: every answerable held-out candidate `H001`–`H012` reuses at least one passage already present in the 20 reviewed development qrels. These records may be answerable, but they are not independent held-out tests.

Answerable-qrel completeness probes found additional same-paper passages containing the answer terms. These are review leads, not automatic qrel additions:

| Candidate | Possible omitted passage evidence |
|---|---|
| H001 | The 1,210-image statement also appears in `L4DLHQUZ_chunk_0001`, `_0008`, and `_0012`. |
| H002 | The 0.9662/36 result also appears in `Z5HMPJQG_chunk_0005` and `_0006`. |
| H003 | The 95.8/93.7 comparison also appears across `DZ6TYBIQ_chunk_0013`–`_0016`. |
| H004 | The 3,095/1,000/1,000 split also appears in `3NLKTSIP_chunk_0012`. |
| H005 | “Radial distance” recurs in several method/result chunks; review `_0001`, `_0003`, `_0008`, `_0009`, `_0016`, and `_0017` for actual relevance rather than adding them mechanically. |
| H006 | The 90% target recurs in `GRPLVQ8G_chunk_0008` and `_0019`; inspect whether these are substantive duplicates or table/reference noise. |
| H007 | Ghost/attention terms recur in `696N7XZ8_chunk_0001`, `_0004`, `_0006`, and `_0007`; the proposed `_0003` passage alone directly states both requested mechanisms. |
| H008 | Texture/low-level language recurs in `L4DLHQUZ_chunk_0001`, `_0003`, `_0005`, `_0007`, and `_0012`; decide whether the question requires all challenge statements. |
| H009–H012 | Each inherits the single-paper completeness risks above; H010 additionally needs Merge-YOLO QA/DySample passages if “structural improvements” remains broad. |

| ID | Recommendation | Main issue |
|---|---|---|
| D001 | `recommend_replace` | Exact duplicate of reviewed development Q18; adds no new discrimination evidence. |
| D002 | `recommend_replace` | Modality-swap easy negative; millimeter-wave radar has no close approved-corpus premise and is signposted by a rare term. |
| D003 | `recommend_replace` | Near-exact duplicate of reviewed development Q20 and contains the universal cues “zero” and “every”. |
| D004 | `recommend_replace` | Stacked refusal cues (“guarantees”, “zero”, “all-weather”) make this an easy linguistic negative rather than a realistic claim boundary. |
| D005 | `recommend_replace` | Near-duplicate of reviewed development Q19 with MRI changed from detection to localization; still an obvious modality mismatch. |
| D006 | `recommend_replace` | The “100%” plus “every dataset” construction is an obvious universal-claim rejection cue. |
| D007 | `recommend_replace` | Medical diagnosis is outside the frozen packaging/industrial-vision corpus and makes the negative too easy. |
| D008 | `recommend_replace` | “Every illumination condition” is an absolute robustness cue; it tests wording rather than close evidence discrimination. |
| D009 | `recommend_replace` | Ultrasound is a conspicuous unsupported modality, so this is another easy modality-swap negative. |
| D010 | `recommend_keep` | Plausible in-domain evaluation claim: the corpus discusses few-shot, datasets, and validation, so absence of cross-factory zero-shot evidence requires real corpus inspection. |
| D011 | `recommend_replace` | “Proves” and “needs no labeled data” create an obvious absolute training claim, not a hard near miss. |
| D012 | `recommend_replace` | Duplicates H014 semantically and uses an obvious unsupported LiDAR modality. |
| H001 | `recommend_replace` | The answer is supported, but the target passage is already a development qrel; the question also calls the dataset “TPMN” rather than its stated Cardboard-Boxes-Dataset name. |
| H002 | `recommend_replace` | The answer is supported, but its sole target passage is already a development qrel, so it cannot serve as independent held-out evidence. |
| H003 | `recommend_replace` | Near-duplicate of development Q06 using the same passage; “relative to” is ambiguous about whether two values, a difference, or both are required. |
| H004 | `recommend_replace` | The split is supported, but the target passage is already used by development Q07/Q17. |
| H005 | `recommend_replace` | Uses the same passage and closely overlaps the method asked in development Q05/Q14. |
| H006 | `recommend_replace` | The 90% target is supported, but the same passage is already a qrel for development Q14. |
| H007 | `recommend_replace` | The passage supports both Ghost convolution and neck attention, but it is already a qrel for development Q13/Q16. |
| H008 | `recommend_replace` | Near-duplicate of development Q10 with the same passage. |
| H009 | `recommend_replace` | Both comparison passages already occur in development qrels, so the comparison is answerable but not held out. |
| H010 | `recommend_replace` | Both passages leak from development; the Merge-YOLO passage mainly supports WT-C3k2 and does not by itself exhaust the broad phrase “structural improvements”. |
| H011 | `recommend_replace` | Near-duplicate of development Q14 with exactly the same two qrel passages. |
| H012 | `recommend_replace` | Both speed passages are already development qrels (including the 121 FPS Q08 target), so independence fails. |
| H013 | `recommend_replace` | Another conspicuous unsupported sensing-modality negative and conceptually close to reviewed Q18/D001. |
| H014 | `recommend_replace` | Duplicates D012 semantically and remains an easy unsupported-modality negative. |
| H015 | `recommend_keep` | Good near miss: RGB-D evidence exists, and carton-defect evidence exists, but the inspected corpus does not join them into direct RGB-D carton-defect detection. |
| H016 | `recommend_keep` | Good composite near miss: 121 FPS is a real corpus value, while MRI is unsupported; success requires preserving attribute binding rather than rejecting an entirely foreign query. |

## Per-query evidence and review questions

### D001 — `recommend_replace`

- Split/type: `dev_hard_negative` / `no_answer`
- Chinese: 哪些论文使用热成像检测包装缺陷？
- English: Which papers use thermal imaging for packaging defect detection?
- Proposed answerability: `false`
- Audit reason: Exact duplicate of reviewed development Q18; adds no new discrimination evidence.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0002` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 2–3 | defect, detection, imaging | …; T. Wang et al., 2018 ). Specific attention is on surface imperfec - tions that exceed acceptable levels, i.e. surface defects appearing on manufactured surfaces (Mullany et al., 2022 ), such as scratches, cold joints, and stains. Such defects negatively affect not only the aest… |
| 2 | `JRIUZQ58` / `JRIUZQ58:JRIUZQ58_chunk_0005` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms | 3–4 | packaging | …ay be seen as the genetic material. These chromosomes undergo operations, such as selection, crossover, and mutation, which mimic the genetic processes of reproduction and variation. John Henry Holland [22] is renowned as the founding ﬁgure in the ﬁeld of genetic algorithms, whic… |
| 3 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0001` — In-situ classification of highly deformed corrugated board using convolution neural networks | 1–1 | defect, detection, imaging, packaging | …owski@up.poznan.pl * Correspondence: jakub.grabski@put.poznan.pl Abstract: The extensive use of corrugated board in the packaging industry is attributed to its excellent cushioning, mechanical properties, and environmental benefits like recyclability and biodegradability. The int… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D002 — `recommend_replace`

- Split/type: `dev_hard_negative` / `no_answer`
- Chinese: 哪些论文使用毫米波雷达检测纸箱缺陷？
- English: Which papers use millimeter-wave radar for carton defect detection?
- Proposed answerability: `false`
- Audit reason: Modality-swap easy negative; millimeter-wave radar has no close approved-corpus premise and is signposted by a rare term.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0001` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 1–2 | carton, defect, detection | ARTICLE IN PRESS Article in Press Modified YOLO for tape-sealing defects in outer packaging of cigarette carton Scientific Reports Received: 21 June 2025 Accepted: 29 May 2026 Cite this article as: Hou Q., Ru F., Guo Y . et al. Modified YOLO for tapesealing defects in outer packa… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | carton, defect, detection | …acts more feature information from the images. Therefore, the model in this paper can better achieve real-time accurate carton quality defect detection. Ablation experiment To verify the improvement effect of IFPN on FPN, co mparative experiments on the accuracy of the detection … |
| 3 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0003` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 2–3 | carton, defect, detection | ugh the above work has made significant progress, it still performs poorly in target scale diversity and detection of small and dense targets. YOLOV3 algorithm solves the problem of redundant ch annels when channel attention is used to concatenate features of different scales . A… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D003 — `recommend_replace`

- Split/type: `dev_hard_negative` / `hard_negative`
- Chinese: 哪些论文证明所有包装缺陷都零漏检？
- English: Which papers prove zero missed detections for every packaging defect?
- Proposed answerability: `false`
- Audit reason: Near-exact duplicate of reviewed development Q20 and contains the universal cues “zero” and “every”.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0014` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 13–14 | defect, detections, missed, packaging | ithms. The YOLO series of algorithms generally achieve high precision in logistics packaging defect detection. This performance advantage stems from their powerful deep network architectures, which excel at learning abstract and discriminative features from large datasets of defe… |
| 2 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0015` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 14–15 | defect, detections, missed | n their detection results, we explore the effectiveness of the improvements. As shown in Figs 5 and 6, the YOLOv11 model has multiple red missed detection areas, which are scattered across different locations and scales. For example, in some images containing dense small objects,… |
| 3 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0016` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 19–20 | defect, detections, missed, packaging | …calization under different levels of background complexity and target scales. In contrast, YOLOv8 and CFIS-YOLO exhibit missed detections, confidence fluctuations, or localization deviations in some cases. Overall, these qualitative results further demonstrate that the proposed m… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D004 — `recommend_replace`

- Split/type: `dev_hard_negative` / `hard_negative`
- Chinese: 哪篇论文在真实仓库部署中保证全天候无误检？
- English: Which paper guarantees zero false positives in all-weather warehouse deployment?
- Proposed answerability: `false`
- Audit reason: Stacked refusal cues (“guarantees”, “zero”, “all-weather”) make this an easy linguistic negative rather than a realistic claim boundary.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0007` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 5–6 | all, false, positives | …ating whether the package is defective or normal. The process begins with the model receiving two image inputs, each of which is fed into separate instances of pre -trained models. These pre -trained models serve as image input feature extractors. The features extracted from each… |
| 2 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0016` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 14–17 | deployment, false, warehouse | … parameter quantity, and can detect target defects more accurately. 5. Discussion The Merge-YOLO model proposed in this paper demonstrates significant advantages in the detection of defects in book logistics packaging. Merge-YOLO can be deployed on edge computing devices along wa… |
| 3 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0017` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 17–18 | deployment, warehouse | …number of parameters is slightly reduced compared to YOL11, further compression of the model size is still required for deployment on edge devices; Although the model performs excellently in experimental environments, it may face more complex lighting changes and background inter… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D005 — `recommend_replace`

- Split/type: `dev_hard_negative` / `no_answer`
- Chinese: 哪些论文使用MRI定位瓦楞纸箱裂纹？
- English: Which papers use MRI to localize corrugated carton cracks?
- Proposed answerability: `false`
- Audit reason: Near-duplicate of reviewed development Q19 with MRI changed from detection to localization; still an obvious modality mismatch.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0004` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–3 | corrugated, cracks | …eted joints in carbon fiber-reinforced composites and aluminum alloy [31]. Recently, Kato et al. evaluated the internal cracks of timbers using CNNs [32,33]. The optimal thickness of blending composite laminates was determined by Huynh et al. using the CNN and genetic algorithm [… |
| 2 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0005` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–4 | corrugated, cracks | … joint s in carbon ﬁber - reinforced composites and aluminum alloy [31]. Recently, Kato et al. evaluated the internal cracks of timbers using CNNs [32,33]. The o ptimal thickness of blending composite la minates was determined by Huynh et al. using the CNN and genetic algorithm [… |
| 3 | `JRIUZQ58` / `JRIUZQ58:JRIUZQ58_chunk_0005` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms | 3–4 | corrugated | …ay be seen as the genetic material. These chromosomes undergo operations, such as selection, crossover, and mutation, which mimic the genetic processes of reproduction and variation. John Henry Holland [22] is renowned as the founding ﬁgure in the ﬁeld of genetic algorithms, whic… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D006 — `recommend_replace`

- Split/type: `dev_hard_negative` / `hard_negative`
- Chinese: 哪个模型在所有数据集上达到100% mAP？
- English: Which model reaches 100% mAP on every dataset?
- Proposed answerability: `false`
- Audit reason: The “100%” plus “every dataset” construction is an obvious universal-claim rejection cue.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `696N7XZ8` / `696N7XZ8:696N7XZ8_chunk_0005` — Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8 | 5–7 | 100, dataset, map, model, on | …ce. Projected GAN is highly effective and can generate high-quality image samples. Training Projected GAN to expand the dataset can enhance model performance, which is important in practical production. Y. Zhang et al. / Corrugated Cardboard Defect Detection Based on Attention Me… |
| 2 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0010` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 7–8 | 100, dataset, model, on | … Indonesian J Elec Eng & Comp Sci ISSN: 2502-4752  Efficient packaging defect detection: leveraging pre-trained vision models through … (Wiwi Prastiwinarti) 2103 grayscale image input. The combination of the best model test results for each model variant is detailed in Table 8. … |
| 3 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0008` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 6–7 | 100, dataset, model, on | …N) 3. RESULTS AND DISCUSSION The classification performance of the proposed approach has been e valuated using the test dataset. The findings were presented as tables. The utilization of transfer learning for two image input models shows a promising result presented in Table s 5-… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D007 — `recommend_replace`

- Split/type: `dev_hard_negative` / `no_answer`
- Chinese: 哪篇论文比较了包装缺陷检测与医学影像诊断？
- English: Which paper compares packaging defect detection with medical image diagnosis?
- Proposed answerability: `false`
- Audit reason: Medical diagnosis is outside the frozen packaging/industrial-vision corpus and makes the negative too easy.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | defect, detection, image, packaging, with | bileNetV2-SSD 0.8386 35 SPP+SSD 0.8563 32 FPN+SSD 0.8621 30 Ours 0.9662 36 The proposed model in this paper performs better th an SSD, MobileNetV2-SSD, SPP+SSD, and FPN+SSD in terms of FPS. This is becau se the IFPN proposed in this paper Bing Song, Yan Wang and Li-Ping Lou 122 g… |
| 2 | `L4DLHQUZ` / `L4DLHQUZ:L4DLHQUZ_chunk_0015` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection | 9–10 | defect, detection, image, medical, with | … Applications, Vol. 15, No. 2, 2024 [20] B. Fang, X. Long, F. Sun, H. Liu, S. Zhang, and C. Fang, “Tactile-based fabric defect detection using convolutional neural network with attention mechanism,” IEEE Transactions on Instrumentation and Measurement , vol. 71, pp. 1–9, 2022. [2… |
| 3 | `L4DLHQUZ` / `L4DLHQUZ:L4DLHQUZ_chunk_0003` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection | 2–2 | defect, detection, image, packaging, with | …es suffer from semantic ambiguity due to their small receptive fields [11], [12]. Therefore, when analyzing the overall image and semantics of corrugated cardboard boxes, it is difficult to extract low-level texture image features. Secondly, traditional methods often use the last… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D008 — `recommend_replace`

- Split/type: `dev_hard_negative` / `hard_negative`
- Chinese: 哪些论文报告了对任意光照条件都稳定的检测器？
- English: Which papers report detectors stable under every illumination condition?
- Proposed answerability: `false`
- Audit reason: “Every illumination condition” is an absolute robustness cue; it tests wording rather than close evidence discrimination.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0015` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 17–19 | stable, under | …dels generally converge more slowly, the synergy among the key modules introduced in this study enables faster and more stable early-stage convergence, while maintaining lower bounding-box regression and classification losses throughout training. These observations indicate impro… |
| 2 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0004` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 4–5 | illumination, under | …ignificantly improves the efficiency, quality and reliability of defect detection. In MVS-supported inspection, optical illumination platforms and adequate hardware for image acquisition are prerequisites for high-quality images. However, the 2D MVS suffer from a number of limita… |
| 3 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0004` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–3 | illumination | …]. Daigo et al. proposed the use of PSPNet to estimate the thickness of steel in heavy melting scrap [ 30]. The CNN and conditional generation antagonism model were utilized by Liu et al. to predict the cross-sectional shape and damage morphology of self-piercing riveted joints i… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D009 — `recommend_replace`

- Split/type: `dev_hard_negative` / `no_answer`
- Chinese: 哪篇论文用超声波检测纸箱表面缺陷？
- English: Which paper uses ultrasound to detect carton surface defects?
- Proposed answerability: `false`
- Audit reason: Ultrasound is a conspicuous unsupported modality, so this is another easy modality-swap negative.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0001` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 1–2 | carton, defects, detect, surface | ARTICLE IN PRESS Article in Press Modified YOLO for tape-sealing defects in outer packaging of cigarette carton Scientific Reports Received: 21 June 2025 Accepted: 29 May 2026 Cite this article as: Hou Q., Ru F., Guo Y . et al. Modified YOLO for tapesealing defects in outer packa… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | carton, defects, detect | bileNetV2-SSD 0.8386 35 SPP+SSD 0.8563 32 FPN+SSD 0.8621 30 Ours 0.9662 36 The proposed model in this paper performs better th an SSD, MobileNetV2-SSD, SPP+SSD, and FPN+SSD in terms of FPS. This is becau se the IFPN proposed in this paper Bing Song, Yan Wang and Li-Ping Lou 122 g… |
| 3 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0002` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 2–3 | carton, defects, detect | ng algorithms that can accurately detect industrial defects remains a challenging problem. Consequently, we propose a model that uses YOLOv8 to detect tape-sealing defects of cigarette carton. Using Diverse Branch Blocks (DBB), The backbone extracts multi-scale representations an… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D010 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Chinese: 哪些论文公开了跨工厂零样本验证？
- English: Which papers report cross-factory zero-shot validation?
- Proposed answerability: `false`
- Audit reason: Plausible in-domain evaluation claim: the corpus discusses few-shot, datasets, and validation, so absence of cross-factory zero-shot evidence requires real corpus inspection.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0004` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–3 | cross | cted a study on the geometrical parameters of crushed thin-walled carbon fiber-reinforced polymer tubes cross-sections [29]. Daigo et al. proposed the use of PSPNet to estimate the thickness of steel in heavy melting scrap [ 30]. The CNN and conditional generation antagonism mode… |
| 2 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0005` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–4 | cross | carbon ﬁ- ber - r einforced polymer tubes cross - sections [29]. Daigo et al. propose d the use of PSPNet to estimate the thickness of steel in heavy melting scrap [30]. The CNN and conditional generation antagonism model were utilized by Liu et al. to predict the cross - sectio … |
| 3 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0009` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 8–9 | zero | …d the original Q: F = soft max(QKT)V (11) Specifically, if the coordinates fall outside the feature map, we abandon the zero-padding method used in the original QA method and instead use mirror padding. This is because when the quadrilateral exceeds the boundary of the feature ma… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D011 — `recommend_replace`

- Split/type: `dev_hard_negative` / `hard_negative`
- Chinese: 哪篇论文证明模型不需要标注数据？
- English: Which paper proves that its model needs no labeled data?
- Proposed answerability: `false`
- Audit reason: “Proves” and “needs no labeled data” create an obvious absolute training claim, not a hard near miss.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `696N7XZ8` / `696N7XZ8:696N7XZ8_chunk_0007` — Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8 | 8–9 | labeled, model, that | …emonstrate the advantages of the proposed method. The detection results are shown in Figure 5. (a)Ground True (b)Origin Model (c)Our Model Fig. 5. Cardboard defect detection by different models Figure 5(a) shows the ground truth boxes labeled by labeling, Figure 5(b) shows the de… |
| 2 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0013` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 15–16 | data, model, needs, that | onical, reference-centred view of the object, which greatly reduces the variability in the network input that arises from the variability in object location and pose under which data is acquired. Yet, as suggested in Figure 8 , the 2D- and 3D-based pipelines share the same self-s… |
| 3 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0010` — In-situ classification of highly deformed corrugated board using convolution neural networks | 6–7 | data, model, no, that | BC, C, E, EB, EC, and EE). However, the classifiers studied in this paper should also be used to recognize images with no sample of the corrugated board. Therefore, images with an additional class (class Not) were generated to represent situations in which the sample is not prese… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### D012 — `recommend_replace`

- Split/type: `dev_hard_negative` / `no_answer`
- Chinese: 哪些论文使用LiDAR完成纸箱缺陷定位？
- English: Which papers use LiDAR for carton defect localization?
- Proposed answerability: `false`
- Audit reason: Duplicates H014 semantically and uses an obvious unsupported LiDAR modality.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0001` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 1–2 | carton, defect | ARTICLE IN PRESS Article in Press Modified YOLO for tape-sealing defects in outer packaging of cigarette carton Scientific Reports Received: 21 June 2025 Accepted: 29 May 2026 Cite this article as: Hou Q., Ru F., Guo Y . et al. Modified YOLO for tapesealing defects in outer packa… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | carton, defect | …acts more feature information from the images. Therefore, the model in this paper can better achieve real-time accurate carton quality defect detection. Ablation experiment To verify the improvement effect of IFPN on FPN, co mparative experiments on the accuracy of the detection … |
| 3 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0001` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 1–2 | carton, defect | DOI: 10.2478/eces-2023-0011 ECOL CHEM ENG S. 2023; 30(1):117-123 Bing SONG 1*, Yan WANG 2 and Li-Ping LOU 3 SSD-BASED CARTON PACKAGING QUALITY DEFECT DETECTION SYSTEM FOR THE LOGISTICS SUPPLY CHAIN Abstract: With the deepening of green and sustainable develo pment and the rapid d… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### H001 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: TPMN数据集包含多少张包装图像？
- English: How many package images are in the TPMN dataset?
- Proposed answerability: `true`
- Audit reason: The answer is supported, but the target passage is already a development qrel; the question also calls the dataset “TPMN” rather than its stated Cardboard-Boxes-Dataset name.

Evidence proposed by the candidate:

- Paper `L4DLHQUZ` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection
  - Locator: `L4DLHQUZ:L4DLHQUZ_chunk_0003`; pages 2–2; normalized section: unavailable.
  - Development-qrel overlap: `Q04, Q15, Q17`.
  - Original excerpt: “…ng CNN with multiple convolution layers, local texture information may gradually be lost [14]. Moreover, in large-scale images, CNNs pay more attention to the high-level semantic information of the image [15], such as the overall structure and shape of corrugated cardboard boxes. Therefore, it is difficult to capture multi-level image features, which limits the task of surface defect detection on corrugated cardboard boxes. In this paper, considering the above challenges, we propose a texture prior-aware multi-level feature fusion network (TPMN). Our met…”

- Direct candidate answer: The Cardboard-Boxes-Dataset contains 1,210 package images.
- Qrel completeness risk: High: target evidence overlaps development qrels Q04, Q15, Q17. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H002 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: SSD包装缺陷系统报告的mAP和FPS是多少？
- English: What mAP and FPS does the SSD carton defect system report?
- Proposed answerability: `true`
- Audit reason: The answer is supported, but its sole target passage is already a development qrel, so it cannot serve as independent held-out evidence.

Evidence proposed by the candidate:

- Paper `Z5HMPJQG` — SSD-based carton packaging quality defect detection system for the logistics supply chain
  - Locator: `Z5HMPJQG:Z5HMPJQG_chunk_0001`; pages 1–2; normalized section: unavailable.
  - Development-qrel overlap: `Q12`.
  - Original excerpt: “DOI: 10.2478/eces-2023-0011 ECOL CHEM ENG S. 2023; 30(1):117-123 Bing SONG 1*, Yan WANG 2 and Li-Ping LOU 3 SSD-BASED CARTON PACKAGING QUALITY DEFECT DETECTION SYSTEM FOR THE LOGISTICS SUPPLY CHAIN Abstract: With the deepening of green and sustainable develo pment and the rapid development of the social economy, the modern logistics industry has also dev eloped to an unprecedented level. In the logistics supply chain, due to the high value of the items inside the arrival carton, appearance inspection must be carried out before warehousing. However, manua…”

- Direct candidate answer: The system reports mAP 0.9662 and 36 FPS.
- Qrel completeness risk: High: target evidence overlaps development qrels Q12. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H003 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: Merge-YOLO相对YOLO11的Precision是多少？
- English: What Precision does Merge-YOLO report relative to YOLO11?
- Proposed answerability: `true`
- Audit reason: Near-duplicate of development Q06 using the same passage; “relative to” is ambiguous about whether two values, a difference, or both are required.

Evidence proposed by the candidate:

- Paper `DZ6TYBIQ` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One
  - Locator: `DZ6TYBIQ:DZ6TYBIQ_chunk_0012`; pages 11–12; normalized section: unavailable.
  - Development-qrel overlap: `Q06, Q13`.
  - Original excerpt: “erage precision mAP, and frames per second FPS. Precision: The ratio of true positives (TP) to all samples predicted as positive (TP + FP). That is, how many of the samples predicted as defective are actually defective. Recall: The ratio of true positives (TP) to all samples with actual defects (TP + FN). That is, how many of the samples that are actually defective are predicted to be abnormal. mAP (Mean Average Precision): The average precision of all categories, which is an important indicator for evaluating the overall detection performance of a model…”

- Direct candidate answer: Merge-YOLO reports 95.8% Precision; YOLO11 reports 93.7%, a 2.1 percentage-point difference.
- Qrel completeness risk: High: target evidence overlaps development qrels Q06, Q13. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H004 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: QZU-DET的训练验证测试集如何划分？
- English: How is QZU-DET split into training, validation, and test sets?
- Proposed answerability: `true`
- Audit reason: The split is supported, but the target passage is already used by development Q07/Q17.

Evidence proposed by the candidate:

- Paper `3NLKTSIP` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports
  - Locator: `3NLKTSIP:3NLKTSIP_chunk_0011`; pages 12–14; normalized section: unavailable.
  - Development-qrel overlap: `Q07, Q17`.
  - Original excerpt: “…set, details of the experimental configuration, and several indicators for the model assessment. Subsequently, ablation tests are performed to assess the efficacy of our model and juxtapose it with other prominent advanced algorithms. Furthermore, numerous debates and graphic representations are provided. A.Dataset To train and validate the effectiveness of the proposed method, we constructed a dataset named QZU-DET (as illustrated in Fig. 9), which consists of 5,095 images collected from the production line of the Baoji Cigarette Factory in China. The d…”

- Direct candidate answer: 3,095 training, 1,000 validation, and 1,000 test images.
- Qrel completeness risk: High: target evidence overlaps development qrels Q07, Q17. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H005 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: 改进的RGB-D平面拟合使用什么残差方向？
- English: What residual direction does the improved RGB-D plane fitting use?
- Proposed answerability: `true`
- Audit reason: Uses the same passage and closely overlaps the method asked in development Q05/Q14.

Evidence proposed by the candidate:

- Paper `7VU5R3RT` — Improving Plane Fitting Accuracy with Rigorous Error Models of Structured Light-Based RGB-D Sensors
  - Locator: `7VU5R3RT:7VU5R3RT_chunk_0004`; pages 3–3; normalized section: unavailable.
  - Development-qrel overlap: `Q05, Q14`.
  - Original excerpt: “n this paper, an improved plane-ﬁtting algorithm, based on the standard RANSAC framework, was proposed to address this issue. First, we derived a rigorous error model for the SL-based RGB-D sensor based on its working principle and error propagation law, from which the weighted coordinates of each point were established. Then, we proposed using the radial distance—that is, the distance in the ray direction—to calculate the residuals for plane estimation by adopting the error characteristics of the SL depth sensors. Next, we modiﬁed the cost function of t…”

- Direct candidate answer: Residuals are calculated along radial distance, i.e. the camera-ray direction, with weighted coordinates.
- Qrel completeness risk: High: target evidence overlaps development qrels Q05, Q14. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H006 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: 混合2D/3D视觉系统的目标检测准确率设定是多少？
- English: What accuracy target is set for the hybrid 2D/3D vision system?
- Proposed answerability: `true`
- Audit reason: The 90% target is supported, but the same passage is already a qrel for development Q14.

Evidence proposed by the candidate:

- Paper `GRPLVQ8G` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - -
  - Locator: `GRPLVQ8G:GRPLVQ8G_chunk_0003`; pages 3–4; normalized section: unavailable.
  - Development-qrel overlap: `Q14`.
  - Original excerpt: “…, 2019 ). As a consequence, processing times hardly match the required pace of industrial applications. In addition, 3D systems suffer from the complexity of optical imaging, which leads to their scarce diffusion and limited development of systems integrating 2D and 3D information to identify and classify defects (Tang et al., 2023 ). The starting point of this work is the fact that hybrid 2D/3D systems are poorly diffused according to the literature, while a combination could be deemed beneficial in light of their opposed advantages and disadvantages, a…”

- Direct candidate answer: The stated detection-accuracy target is 90%.
- Qrel completeness risk: High: target evidence overlaps development qrels Q14. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H007 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: YOLOv8-GSP如何降低计算量并提高检测精度？
- English: How does YOLOv8-GSP reduce computation and improve detection accuracy?
- Proposed answerability: `true`
- Audit reason: The passage supports both Ghost convolution and neck attention, but it is already a qrel for development Q13/Q16.

Evidence proposed by the candidate:

- Paper `696N7XZ8` — Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8
  - Locator: `696N7XZ8:696N7XZ8_chunk_0003`; pages 2–4; normalized section: unavailable.
  - Development-qrel overlap: `Q13, Q16`.
  - Original excerpt: “…feature fusion; and the Head is responsible for the regression calculation of target categories and positions in target detection. The Backbone module comprises three components, including CBS, C2f, and crossstage partial (SPPF); the CBS module consists of the convolution layer (Conv), batch normalization (BN), and sigmoid linear unit (SiLU) activation function. The C2F module Y. Zhang et al. / Corrugated Cardboard Defect Detection Based on Attention Mechanism476 draws on the Cross Stage Partial structure [11]. The SPPF module improves spatial pyramid po…”

- Direct candidate answer: It replaces backbone convolution with Ghost convolution and adds an attention module to the neck.
- Qrel completeness risk: High: target evidence overlaps development qrels Q13, Q16. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H008 — `recommend_replace`

- Split/type: `held_out` / `single_paper`
- Chinese: TPMN针对快递纸箱提出了哪些纹理挑战？
- English: What texture challenges does TPMN identify for courier boxes?
- Proposed answerability: `true`
- Audit reason: Near-duplicate of development Q10 with the same passage.

Evidence proposed by the candidate:

- Paper `L4DLHQUZ` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection
  - Locator: `L4DLHQUZ:L4DLHQUZ_chunk_0002`; pages 1–2; normalized section: unavailable.
  - Development-qrel overlap: `Q10`.
  - Original excerpt: “ords— logistics; surface defect detection; multi-level feature fusion; prior attention; corrugated cardboard boxes *These authors contributed equally to this work. Corresponding authors. I. I NTRODUCTION Surface defect detection is a widely applied task in various industries, the goal of which is to identify and locate defects on the surface of objects. Nowadays, an increasing number of surface defect detection methods based on deep learning are being proposed. Lv et al. proposed a single shot multiBox detector-based end-to-end defect detection network f…”

- Direct candidate answer: The paper highlights rich non-uniform textures, inconsistent defect scales, loss/ambiguity of low-level texture features, and difficulty combining multi-level information.
- Qrel completeness risk: High: target evidence overlaps development qrels Q10. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H009 — `recommend_replace`

- Split/type: `held_out` / `cross_paper`
- Chinese: TPMN与QZU-DET论文的数据集规模如何比较？
- English: How do the TPMN and QZU-DET dataset sizes compare?
- Proposed answerability: `true`
- Audit reason: Both comparison passages already occur in development qrels, so the comparison is answerable but not held out.

Evidence proposed by the candidate:

- Paper `L4DLHQUZ` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection
  - Locator: `L4DLHQUZ:L4DLHQUZ_chunk_0003`; pages 2–2; normalized section: unavailable.
  - Development-qrel overlap: `Q04, Q15, Q17`.
  - Original excerpt: “…f local information in the image. Specifically, courier parcels vary in size, and there is inconsistency in the texture sizes of corrugated cardboard boxes. When employing CNN with multiple convolution layers, local texture information may gradually be lost [14]. Moreover, in large-scale images, CNNs pay more attention to the high-level semantic information of the image [15], such as the overall structure and shape of corrugated cardboard boxes. Therefore, it is difficult to capture multi-level image features, which limits the task of surface defect dete…”
- Paper `3NLKTSIP` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports
  - Locator: `3NLKTSIP:3NLKTSIP_chunk_0011`; pages 12–14; normalized section: unavailable.
  - Development-qrel overlap: `Q07, Q17`.
  - Original excerpt: “…LE IN PRESSARTICLE IN PRESS Experimental results and analysis This section includes a brief synopsis of the constructed dataset, details of the experimental configuration, and several indicators for the model assessment. Subsequently, ablation tests are performed to assess the efficacy of our model and juxtapose it with other prominent advanced algorithms. Furthermore, numerous debates and graphic representations are provided. A.Dataset To train and validate the effectiveness of the proposed method, we constructed a dataset named QZU-DET (as illustrated …”

- Direct candidate answer: TPMN reports 1,210 images; QZU-DET reports 5,095 images (3,095/1,000/1,000), so QZU-DET is larger by 3,885 images.
- Qrel completeness risk: High: target evidence overlaps development qrels Q04, Q07, Q15, Q17. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H010 — `recommend_replace`

- Split/type: `held_out` / `cross_paper`
- Chinese: Merge-YOLO与YOLOv8-GSP分别采用了哪些结构改进？
- English: What structural improvements do Merge-YOLO and YOLOv8-GSP use?
- Proposed answerability: `true`
- Audit reason: Both passages leak from development; the Merge-YOLO passage mainly supports WT-C3k2 and does not by itself exhaust the broad phrase “structural improvements”.

Evidence proposed by the candidate:

- Paper `DZ6TYBIQ` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One
  - Locator: `DZ6TYBIQ:DZ6TYBIQ_chunk_0008`; pages 6–8; normalized section: unavailable.
  - Development-qrel overlap: `Q01`.
  - Original excerpt: “…to process high-frequency components), a larger receptive field can be obtained. The convolved frequency components are merged into a feature map Y through inverse PLOS One | https://doi.org/10.1371/journal.pone.0340205 January 8, 2026 7 / 19 wavelet transformation. The specific calculation formula is shown in Equation (4). After feature fusion, we retain the original bottleneck structure for feature compression and information processing. This layer further compresses and adjusts information at different frequencies, reducing redundant features while en…”
- Paper `696N7XZ8` — Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8
  - Locator: `696N7XZ8:696N7XZ8_chunk_0003`; pages 2–4; normalized section: unavailable.
  - Development-qrel overlap: `Q13, Q16`.
  - Original excerpt: “…ure [11]. The SPPF module improves spatial pyramid pooling (SPP) [12]. The Neck module retains the PANet structure from YOLOv5, and it comprises a feature pyramid network (FPN) [13] and a path aggregation network (PAN) [14]. The Head module adopts a Decoupled Head, separates localization and classification into two branches, and shifts from Anchor-Based in YOLOv5 to Anchor-Free. CBS CBS C2f CBS CBS CBS SSPF C2f C2f C2f Input C2fConcat Upsample C2f CBS Concat Concat C2f UpsampleCBS Concat C2f CBS CBS Conv Conv CBS CBS Conv Conv CBS CBS Conv Conv (a)Backbo…”

- Direct candidate answer: The cited Merge-YOLO passage describes WT-C3k2/WTConv; the YOLOv8-GSP passage describes Ghost convolution plus neck attention.
- Qrel completeness risk: High: target evidence overlaps development qrels Q01, Q13, Q16. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H011 — `recommend_replace`

- Split/type: `held_out` / `cross_paper`
- Chinese: RGB-D平面拟合与混合2D/3D系统分别面向什么视觉问题？
- English: What visual problems do RGB-D plane fitting and hybrid 2D/3D systems address?
- Proposed answerability: `true`
- Audit reason: Near-duplicate of development Q14 with exactly the same two qrel passages.

Evidence proposed by the candidate:

- Paper `7VU5R3RT` — Improving Plane Fitting Accuracy with Rigorous Error Models of Structured Light-Based RGB-D Sensors
  - Locator: `7VU5R3RT:7VU5R3RT_chunk_0004`; pages 3–3; normalized section: unavailable.
  - Development-qrel overlap: `Q05, Q14`.
  - Original excerpt: “n this paper, an improved plane-ﬁtting algorithm, based on the standard RANSAC framework, was proposed to address this issue. First, we derived a rigorous error model for the SL-based RGB-D sensor based on its working principle and error propagation law, from which the weighted coordinates of each point were established. Then, we proposed using the radial distance—that is, the distance in the ray direction—to calculate the residuals for plane estimation by adopting the error characteristics of the SL depth sensors. Next, we modiﬁed the cost function of t…”
- Paper `GRPLVQ8G` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - -
  - Locator: `GRPLVQ8G:GRPLVQ8G_chunk_0003`; pages 3–4; normalized section: unavailable.
  - Development-qrel overlap: `Q14`.
  - Original excerpt: “…, 2019 ). As a consequence, processing times hardly match the required pace of industrial applications. In addition, 3D systems suffer from the complexity of optical imaging, which leads to their scarce diffusion and limited development of systems integrating 2D and 3D information to identify and classify defects (Tang et al., 2023 ). The starting point of this work is the fact that hybrid 2D/3D systems are poorly diffused according to the literature, while a combination could be deemed beneficial in light of their opposed advantages and disadvantages, a…”

- Direct candidate answer: One paper addresses error-aware RGB-D plane fitting; the other integrates 2D and 3D machine vision for surface-defect identification.
- Qrel completeness risk: High: target evidence overlaps development qrels Q05, Q14. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H012 — `recommend_replace`

- Split/type: `held_out` / `cross_paper`
- Chinese: SSD系统与QZU-DET模型分别报告了什么速度指标？
- English: What speed-related metrics do the SSD system and QZU-DET model report?
- Proposed answerability: `true`
- Audit reason: Both speed passages are already development qrels (including the 121 FPS Q08 target), so independence fails.

Evidence proposed by the candidate:

- Paper `Z5HMPJQG` — SSD-based carton packaging quality defect detection system for the logistics supply chain
  - Locator: `Z5HMPJQG:Z5HMPJQG_chunk_0001`; pages 1–2; normalized section: unavailable.
  - Development-qrel overlap: `Q12`.
  - Original excerpt: “…G S. 2023; 30(1):117-123 Bing SONG 1*, Yan WANG 2 and Li-Ping LOU 3 SSD-BASED CARTON PACKAGING QUALITY DEFECT DETECTION SYSTEM FOR THE LOGISTICS SUPPLY CHAIN Abstract: With the deepening of green and sustainable develo pment and the rapid development of the social economy, the modern logistics industry has also dev eloped to an unprecedented level. In the logistics supply chain, due to the high value of the items inside the arrival carton, appearance inspection must be carried out before warehousing. However, manual inspection is slow and ineffective, re…”
- Paper `3NLKTSIP` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports
  - Locator: `3NLKTSIP:3NLKTSIP_chunk_0005`; pages 4–5; normalized section: unavailable.
  - Development-qrel overlap: `Q08, Q15`.
  - Original excerpt: “…object detection, a feature fusion module that combines CCFM and IRMA is designed in the neck. This module enhances the model adaptability to scale variations and significantly improves the detection performance of small-scale defect targets. 3. To address the high proportion of small-object samples and the class imbalance commonly observed in industrial packaging defect detection, Focal Loss is adopted as the loss function. This strategy reduces the influence of easy samples during training and improves the recognition accuracy of small and hard-to-dete…”

- Direct candidate answer: The SSD system reports 36 FPS; the QZU-DET model reports 121 FPS.
- Qrel completeness risk: High: target evidence overlaps development qrels Q08, Q12, Q15. Also inspect adjacent/overlapping chunks before freezing exhaustive qrels.
- User must confirm: (1) wording and answer are supported; (2) all necessary passages are included; (3) this item must be replaced or assigned outside held-out because of development leakage.

### H013 — `recommend_replace`

- Split/type: `held_out` / `in_domain_no_answer`
- Chinese: 冻结语料中哪些论文使用高光谱成像检测包装缺陷？
- English: Which papers in the frozen corpus use hyperspectral imaging for packaging defects?
- Proposed answerability: `false`
- Audit reason: Another conspicuous unsupported sensing-modality negative and conceptually close to reviewed Q18/D001.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0002` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 2–3 | defects, imaging | …; T. Wang et al., 2018 ). Specific attention is on surface imperfec - tions that exceed acceptable levels, i.e. surface defects appearing on manufactured surfaces (Mullany et al., 2022 ), such as scratches, cold joints, and stains. Such defects negatively affect not only the aest… |
| 2 | `JRIUZQ58` / `JRIUZQ58:JRIUZQ58_chunk_0005` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms | 3–4 | packaging | …ay be seen as the genetic material. These chromosomes undergo operations, such as selection, crossover, and mutation, which mimic the genetic processes of reproduction and variation. John Henry Holland [22] is renowned as the founding ﬁgure in the ﬁeld of genetic algorithms, whic… |
| 3 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0003` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 3–4 | defects, imaging | …ardly match the required pace of industrial applications. In addition, 3D systems suffer from the complexity of optical imaging, which leads to their scarce diffusion and limited development of systems integrating 2D and 3D information to identify and classify defects (Tang et al… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### H014 — `recommend_replace`

- Split/type: `held_out` / `in_domain_no_answer`
- Chinese: 冻结语料中哪些论文使用激光雷达检测纸箱缺陷？
- English: Which papers in the frozen corpus use LiDAR for carton defect detection?
- Proposed answerability: `false`
- Audit reason: Duplicates D012 semantically and remains an easy unsupported-modality negative.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0001` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 1–2 | carton, defect, detection | ARTICLE IN PRESS Article in Press Modified YOLO for tape-sealing defects in outer packaging of cigarette carton Scientific Reports Received: 21 June 2025 Accepted: 29 May 2026 Cite this article as: Hou Q., Ru F., Guo Y . et al. Modified YOLO for tapesealing defects in outer packa… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | carton, defect, detection | …acts more feature information from the images. Therefore, the model in this paper can better achieve real-time accurate carton quality defect detection. Ablation experiment To verify the improvement effect of IFPN on FPN, co mparative experiments on the accuracy of the detection … |
| 3 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0003` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 2–3 | carton, defect, detection | ugh the above work has made significant progress, it still performs poorly in target scale diversity and detection of small and dense targets. YOLOV3 algorithm solves the problem of redundant ch annels when channel attention is used to concatenate features of different scales . A… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### H015 — `recommend_keep`

- Split/type: `held_out` / `near_miss_hard_negative`
- Chinese: 哪篇论文使用RGB-D直接检测瓦楞纸箱缺陷？
- English: Which paper uses RGB-D to directly detect corrugated carton defects?
- Proposed answerability: `false`
- Audit reason: Good near miss: RGB-D evidence exists, and carton-defect evidence exists, but the inspected corpus does not join them into direct RGB-D carton-defect detection.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0001` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 1–2 | carton, defects, detect, directly | ARTICLE IN PRESS Article in Press Modified YOLO for tape-sealing defects in outer packaging of cigarette carton Scientific Reports Received: 21 June 2025 Accepted: 29 May 2026 Cite this article as: Hou Q., Ru F., Guo Y . et al. Modified YOLO for tapesealing defects in outer packa… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | carton, d, defects, detect | bileNetV2-SSD 0.8386 35 SPP+SSD 0.8563 32 FPN+SSD 0.8621 30 Ours 0.9662 36 The proposed model in this paper performs better th an SSD, MobileNetV2-SSD, SPP+SSD, and FPN+SSD in terms of FPS. This is becau se the IFPN proposed in this paper Bing Song, Yan Wang and Li-Ping Lou 122 g… |
| 3 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0002` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 2–3 | carton, defects, detect | ng algorithms that can accurately detect industrial defects remains a challenging problem. Consequently, we propose a model that uses YOLOv8 to detect tape-sealing defects of cigarette carton. Using Diverse Branch Blocks (DBB), The backbone extracts multi-scale representations an… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

### H016 — `recommend_keep`

- Split/type: `held_out` / `near_miss_hard_negative`
- Chinese: 哪篇论文用MRI达到121 FPS的包装检测？
- English: Which paper uses MRI to achieve 121 FPS packaging inspection?
- Proposed answerability: `false`
- Audit reason: Good composite near miss: 121 FPS is a real corpus value, while MRI is unsupported; success requires preserving attribute binding rather than rejecting an entirely foreign query.

Offline corpus-wide lexical probe (existing BM25-EN, top 3):

| Rank | Paper / passage | Pages | Match reason | Original excerpt |
|---:|---|---:|---|---|
| 1 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0016` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 14–17 | achieve, fps, inspection, packaging | …e addition of DySample optimizes speed and parameter volume while improving performance. Overall, the proposed model focuses on the defects of book logistics packaging, and the use of WTConv, QA and DySample modules can achieve a good balance between precision, speed and paramete… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0005` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 4–6 | 121, fps, packaging | …f different sizes, the downsampling in the multiscale attention mechanism is set to different sizes. Experiment In this paper, the experimental environment is Wind ows 10, the processor is Intel i7-10875H, the memory is 16 GB, and the graphics ca rd is NVIDIA GeForce RTX 2070 wit… |
| 3 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0001` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 1–2 | inspection, packaging | … OPEN ACCESS Citation: Wang Z, Luo Y, Du Y, Li J, Wang Y, Lin Y (2026) Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios. PLoS One 21(1): e0340205. https://doi.org/10.1371/journal. pone.0340205 Editor: Gengpei Zhang, Yangtze Uni… |

- Direct candidate answer: no supported answer is proposed; this remains a hypothesis pending human corpus review.
- Qrel completeness risk: no positive qrel is present. The lexical probe cannot prove absence and may miss synonyms or conceptually relevant passages.
- User must confirm: (1) the proposition is truly unsupported across all 185 passages; (2) the negative is not merely signposted by an impossible/foreign term; (3) the suggested keep/replace decision is appropriate.

## Suggested replacement directions

- Replace duplicate/easy development negatives with close, in-domain boundary cases derived from claims actually present in the corpus: wrong dataset attribution, swapped model/module attribution, metric transferred to the wrong paper, or a method applied to the wrong defect category.
- Replace answerable held-out records with questions whose judged passages do not occur in development qrels. If the 10-paper corpus cannot supply 12 such items, reduce the held-out claim or acquire a separately frozen corpus in a future authorized batch; do not relabel leaked passages as independent.
- For H003 specifically, if retained outside held-out, ask explicitly for Merge-YOLO Precision, YOLO11 Precision, and the percentage-point difference.
- For H007, the existing single passage supports both requested mechanisms; the problem is development leakage, not obvious evidence insufficiency.
- For H010, use a narrower component-level comparison or add all genuinely supporting Merge-YOLO passages after review; one WT-C3k2 passage does not exhaust “structural improvements”.
- H015 and H016 are the strongest current near misses because they combine real corpus concepts while requiring correct relation/attribute binding.

## Dependency reproducibility note

- Metric evaluation itself does not import `jsonschema`; formal package validation calls `validate_json_schema_documents()` and imports `jsonschema.Draft202012Validator` at runtime.
- `pyproject.toml` and `requirements.runtime.lock` do not declare `jsonschema`; a clean project environment therefore cannot reliably reproduce formal Schema validation. The current project `.venv` skips that test, while a separate system Python happened to provide `jsonschema 4.25.0`.
- Minimal future fix: add a pinned evaluation/test extra for `jsonschema==4.25.0`, reflect it in the appropriate lock/packaging contract, and make the R1 Schema test mandatory in that environment. This packet does not change dependencies.
