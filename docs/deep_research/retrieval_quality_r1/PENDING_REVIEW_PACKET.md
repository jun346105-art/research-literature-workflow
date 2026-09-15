# Retrieval Quality R1 — Pending Evidence Review Packet (Revision 2)

> Status: evidence-assisted candidate packet. All 28 records remain `pending_review`; `recommend_keep` is an audit recommendation, not user approval or ground truth.

## Revision outcome

- Retained unchanged in intent: `D010`, `H015`, `H016`.
- Replaced once under user authorization: the other 25 records.
- Final candidate count: 28 (`12` development hard negatives + `16` held-out).
- Audit recommendation: `recommend_keep` for all 28; `recommend_revise=0`, `recommend_replace=0`.
- Held-out composition remains 8 single-paper answerable, 4 cross-paper answerable, 2 in-domain no-answer, and 2 near-miss hard negatives.

## Review rules

- Confirm question/translation, proposed answerability, candidate answer, and every qrel. Do not approve from IDs alone.
- For answerable records, qrels include the substantive overlapping chunks found by claim-term and neighboring-window inspection; the reviewer must still decide whether they are exhaustive.
- For negative records, BM25-EN Top-3 is only a lexical probe. It cannot prove corpus-wide absence.
- A reused passage is allowed only when the answer claim differs. `passage_overlap` and `answer_claim_overlap` are explicit below. Held-out never participates in tuning.
- Locator is the stable `passage_id`; the frozen corpus provides page ranges but no normalized section field.

## Candidate index

| ID | Split/type | Claim family | Recommendation |
|---|---|---|---|
| D001 | `dev_hard_negative` / `hard_negative` | `tpmn_qzudet_121fps_misattribution` | `recommend_keep` |
| D002 | `dev_hard_negative` / `hard_negative` | `yolov8gsp_wtc3k2_misattribution` | `recommend_keep` |
| D003 | `dev_hard_negative` / `hard_negative` | `ssd_cardboardboxes_dataset_misattribution` | `recommend_keep` |
| D004 | `dev_hard_negative` / `hard_negative` | `rgbd_book_defect_categories_misattribution` | `recommend_keep` |
| D005 | `dev_hard_negative` / `hard_negative` | `merge_yolo_qzudet_split_misattribution` | `recommend_keep` |
| D006 | `dev_hard_negative` / `hard_negative` | `ransac_qzudet_angle_error_misattribution` | `recommend_keep` |
| D007 | `dev_hard_negative` / `hard_negative` | `hybrid_2d3d_focal_loss_misattribution` | `recommend_keep` |
| D008 | `dev_hard_negative` / `hard_negative` | `merge_yolo_ifpn_misattribution` | `recommend_keep` |
| D009 | `dev_hard_negative` / `hard_negative` | `tpmn_flute_classes_misattribution` | `recommend_keep` |
| D010 | `dev_hard_negative` / `hard_negative` | `cross_factory_zero_shot_validation` | `recommend_keep` |
| D011 | `dev_hard_negative` / `hard_negative` | `tpmn_90pct_target_misattribution` | `recommend_keep` |
| D012 | `dev_hard_negative` / `hard_negative` | `ssd_qzudet_map_misattribution` | `recommend_keep` |
| H001 | `held_out` / `single_paper` | `two_view_dataset_unit_and_views` | `recommend_keep` |
| H002 | `held_out` / `single_paper` | `cnn_not_class_purpose` | `recommend_keep` |
| H003 | `held_out` / `single_paper` | `double_wall_measured_geometry` | `recommend_keep` |
| H004 | `held_out` / `single_paper` | `two_view_best_classification_model` | `recommend_keep` |
| H005 | `held_out` / `single_paper` | `flute_cnn_best_architecture_accuracy` | `recommend_keep` |
| H006 | `held_out` / `single_paper` | `double_wall_genetic_algorithm_parameters` | `recommend_keep` |
| H007 | `held_out` / `single_paper` | `qzudet_map50_f1` | `recommend_keep` |
| H008 | `held_out` / `single_paper` | `ssd_training_photo_count` | `recommend_keep` |
| H009 | `held_out` / `cross_paper` | `cross_paper_input_sample_construction` | `recommend_keep` |
| H010 | `held_out` / `cross_paper` | `cross_paper_best_classification_models` | `recommend_keep` |
| H011 | `held_out` / `cross_paper` | `cross_paper_geometry_vs_classification_output` | `recommend_keep` |
| H012 | `held_out` / `cross_paper` | `cross_paper_data_quality_limitations` | `recommend_keep` |
| H013 | `held_out` / `in_domain_no_answer` | `two_view_real_warehouse_accuracy_no_answer` | `recommend_keep` |
| H014 | `held_out` / `in_domain_no_answer` | `flute_cnn_delamination_inclination_accuracy_no_answer` | `recommend_keep` |
| H015 | `held_out` / `near_miss_hard_negative` | `rgbd_carton_direct_detection` | `recommend_keep` |
| H016 | `held_out` / `near_miss_hard_negative` | `mri_121fps_attribution` | `recommend_keep` |

## Per-query evidence

### D001 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `tpmn_qzudet_121fps_misattribution`
- 中文：TPMN是否在QZU-DET数据集上报告了121 FPS的推理速度？
- English: Does TPMN report 121 FPS inference speed on the QZU-DET dataset?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: 121 FPS on QZU-DET belongs to the modified-YOLO paper (`3NLKTSIP`), not TPMN.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0013` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 15–16 | 121, dataset, det, fps, inference, on, qzu, speed | …ods and fully satisfies real-time detection requirements. More importantly, the improved efficiency does not come at the cost of detection accuracy. The proposed model achieves the best performance across all accuracy metrics, including mAP50, mAP50–95, and F1 score. Th… |
| 2 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0005` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 4–5 | 121, dataset, det, fps, inference, on, qzu, speed | …convolutional structures, DBB effectively enhances feature extraction capability without increasing inference-time computational cost. 2. To mitigate the loss of multi-scale information and improve small-object detection, a feature fusion module that combines CCFM and I… |
| 3 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0014` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 16–17 | 121, dataset, det, fps, inference, on, qzu, speed | …89 YOLOv8n 0.561 0.445 0.707 8.2 101 Ours 0.587 0.459 0.716 8.1 121 D. Ablation experiments Table 4 reports an ablation study that explicitly accounts for category heterogeneity by providing per-class AP for NO, WR, and the challenging DE (defect) class, in addition to … |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D002 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `yolov8gsp_wtc3k2_misattribution`
- 中文：YOLOv8-GSP是否使用WT-C3k2作为轻量化骨干模块？
- English: Does YOLOv8-GSP use WT-C3k2 as its lightweight backbone module?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: WT-C3k2 belongs to Merge-YOLO; YOLOv8-GSP uses Ghost convolution and neck attention.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `696N7XZ8` / `696N7XZ8:696N7XZ8_chunk_0003` — Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8 | 2–4 | as, backbone, gsp, its, lightweight, module, yolov8 | …C2f N* Conv Split Bottleneck Concat Conv Bottleneck Conv Conv Conv Conv Output Fig. 1. Structure of YOLOv8 Detecting defects on corrugated cardboard often requires lightweight models to accommodate the large volume of corrugated cardboard being processed and the limited… |
| 2 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0006` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 4–6 | as, backbone, c3k2, its, module, wt | …predictive features for defect classification and detection. In the backbone network, we use the WT-C3k2 module to replace the C3k2 module, separate low-frequency and high-frequency features through multi-level wavelet decomposition, and use different convolution kernel… |
| 3 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0008` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 6–8 | as, c3k2, its, module, wt | …nsion of the feature map and improving computational efficiency. Y = IWT(Conv(W, WT(X))) (4) The WT-C3k2 module structure is shown in Fig 2. In the defect detection scenario of bookstore logistics packaging, the C3k2 module provides powerful feature extraction capabilit… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D003 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `ssd_cardboardboxes_dataset_misattribution`
- 中文：SSD物流纸箱系统是否使用含1210张图像的Cardboard-Boxes-Dataset训练？
- English: Was the SSD logistics-carton system trained on the 1,210-image Cardboard-Boxes-Dataset?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: the 1,210-image Cardboard-Boxes-Dataset belongs to TPMN; the SSD study reports a separately collected 2,000-photo dataset.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | 1, boxes, carton, image, logistics, on, ssd, system | …f cartons. Conclusion With the in-depth promotion of green and sustainabl e development, the modern logistics industry has been developed rapidly. Howe ver, in the logistics supply chain, the detection of carton packaging quality has problems such as slow speed, poor ef… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0003` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 2–3 | boxes, carton, image, logistics, on, ssd, system | … variation during training [11]. SSD-based carton packaging quality defect detection system for the logistics supply chain 119 PANet used ROI alignment for each layer of the pyra mid features and then takes the maximum value for fusion to extract more features [ 12]. NA… |
| 3 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0001` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 1–2 | 1, carton, image, logistics, on, ssd, system, was | …1*, Yan WANG 2 and Li-Ping LOU 3 SSD-BASED CARTON PACKAGING QUALITY DEFECT DETECTION SYSTEM FOR THE LOGISTICS SUPPLY CHAIN Abstract: With the deepening of green and sustainable develo pment and the rapid development of the social economy, the modern logistics industry h… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D004 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `rgbd_book_defect_categories_misattribution`
- 中文：改进的RGB-D平面拟合算法是否在书籍包装的fold、scratch和broken三类缺陷上进行了评估？
- English: Was the improved RGB-D plane-fitting algorithm evaluated on fold, scratch, and broken book-packaging defects?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the relation: the RGB-D paper evaluates plane fitting, while fold/scratch/broken are Merge-YOLO packaging categories.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0014` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 13–14 | algorithm, book, broken, defects, fold, improved, on, packaging | …s paper, the figure below shows the visualization results of the original YOLOv11 algorithm and the improved Merge-YOLO algorithm on the defect dataset. The red boxes indicate missed defects. By comparing the performance differences between the two models in their detec… |
| 2 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0016` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 14–17 | algorithm, book, broken, defects, fold, improved, on, packaging | hin acceptable limits. The QA module continues to improve Table 3. Detection results of the improved and original algorithms on different types of defects. Algorithm Precision (%) / Recall (%) fold scratch broken ours 96.2%/ 95% 95.5%/ 92% 95.7%/ 94% YOLOv11 95%/ 90% 92… |
| 3 | `7VU5R3RT` / `7VU5R3RT:7VU5R3RT_chunk_0003` — Improving Plane Fitting Accuracy with Rigorous Error Models of Structured Light-Based RGB-D Sensors | 2–3 | algorithm, d, fitting, improved, on, plane, rgb, was | …r calibration by applying a precise plane ﬁtting method based on the least-squares and improved the accuracy signiﬁcantly with angle errors of less than a degree and distance errors less than 2 cm. Additionally, their research indicated that the error of the SL-based RG… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D005 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `merge_yolo_qzudet_split_misattribution`
- 中文：Merge-YOLO论文是否将QZU-DET划分为3095张训练、1000张验证和1000张测试图像？
- English: Does the Merge-YOLO paper split QZU-DET into 3,095 training, 1,000 validation, and 1,000 test images?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: the 3,095/1,000/1,000 QZU-DET split is reported by `3NLKTSIP`, not Merge-YOLO.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0011` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 12–14 | 000, 095, 1, 3, det, images, into, qzu | oss-entropy loss. Our method is an improvement upon YOLOv8n, and the overall model structure is shown in Figure 8. Figure 8. Improved YOLOv8 structure. Among them, the background color is added to the improved module. ACCEPTED MANUSCRIPTARTICLE IN PRESSARTICLE IN PRESS … |
| 2 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0012` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 13–15 | 000, 095, 1, 3, det, images, into, qzu | …igure 9. Dataset of the outer packaging tape sealing In this study, the QZU-DET dataset was divided into 3,095 training images, 1,000 validation images, and 1,000 test images, covering the three categories: normal (NO), wrong direction (WD), and defect (DE). The model w… |
| 3 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0004` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 2–4 | 1, 3, images, into, split, test, training, validation | …ckage sample (a) side-view and (b) top-view To accommodate the training and evaluation purposes, we split the dataset into three parts, which are training, validation, and test sets. The training and validation sets are utilized during the trai ning phase. Specifically,… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D006 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `ransac_qzudet_angle_error_misattribution`
- 中文：改进RANSAC是否在QZU-DET数据集上报告了0.5°的平面拟合角度误差？
- English: Does the improved RANSAC method report a 0.5-degree plane-fitting angle error on QZU-DET?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the relation: the 0.5-degree result belongs to RGB-D plane fitting and is not a QZU-DET experiment.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `7VU5R3RT` / `7VU5R3RT:7VU5R3RT_chunk_0018` — Improving Plane Fitting Accuracy with Rigorous Error Models of Structured Light-Based RGB-D Sensors | 14–15 | 0, 5, angle, degree, error, fitting, improved, method | …of about one degree and a distance error less than 6 cm. Meanwhile, the proposed method improved the angle accuracy from 3.8 degrees to 0.5 degrees and the distance error from 16.8 centimeters to 4.7 centimeters, compared to the unweighted perpendicular oﬀset cost funct… |
| 2 | `7VU5R3RT` / `7VU5R3RT:7VU5R3RT_chunk_0001` — Improving Plane Fitting Accuracy with Rigorous Error Models of Structured Light-Based RGB-D Sensors | 1–1 | 0, 5, angle, degree, error, fitting, method, on | …ances with the derived rigorous error model was then proposed for the random sample consensus (RANSAC)-based plane ﬁtting method. The experimental results demonstrated that our method is robust and practical for diﬀerent operating ranges and diﬀerent working conditions.… |
| 3 | `7VU5R3RT` / `7VU5R3RT:7VU5R3RT_chunk_0004` — Improving Plane Fitting Accuracy with Rigorous Error Models of Structured Light-Based RGB-D Sensors | 3–3 | 5, angle, degree, error, fitting, improved, method, on | n this paper, an improved plane-ﬁtting algorithm, based on the standard RANSAC framework, was proposed to address this issue. First, we derived a rigorous error model for the SL-based RGB-D sensor based on its working principle and error propagation law, from which the … |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D007 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `hybrid_2d3d_focal_loss_misattribution`
- 中文：混合2D/3D表面缺陷系统是否采用Focal Loss处理类别不平衡？
- English: Does the hybrid 2D/3D surface-defect system use Focal Loss to address class imbalance?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: Focal Loss is used by the modified-YOLO QZU-DET study, not the hybrid 2D/3D system.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0010` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 11–13 | address, class, focal, imbalance, loss | …a hyper-parameter to adjust the parameter. Although α can balance positive and negative samples, it does not address the balance between easy and complex samples. The one-stage detector's main problem is that many easy and negative samples constitute most of the loss an… |
| 2 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0001` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 1–2 | 2d, 3d, defect, hybrid, surface, system | … Journal homepage: www.tandfonline.com/journals/tpmr20 Deep learning-supported machine vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects Giorgio Cavaliere, Oswald Lanz, Yuri Borgianni & Enrico Savio To cite this … |
| 3 | `GRPLVQ8G` / `GRPLVQ8G:GRPLVQ8G_chunk_0003` — Deep Learning-supported Machine Vision-based hybrid system combining inhomogeneous 2D and 3D data for the identification of surface defects - - | 3–4 | 2d, 3d, defect, hybrid, surface, system | …dentify and classify defects (Tang et al., 2023 ). The starting point of this work is the fact that hybrid 2D/3D systems are poorly diffused according to the literature, while a combination could be deemed beneficial in light of their opposed advantages and disadvantage… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D008 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `merge_yolo_ifpn_misattribution`
- 中文：Merge-YOLO是否采用IFPN降低特征金字塔的计算复杂度？
- English: Does Merge-YOLO use IFPN to reduce feature-pyramid computational complexity?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: IFPN belongs to the improved SSD system, not Merge-YOLO.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0013` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 12–13 | complexity, computational, feature, merge, yolo | recision: The improved Merge-YOLO algorithm achieves a precision of 95.8%, with an extremely high proportion of correctly predicted results in detection outcomes. This represents a 2.1% improvement in precision compared to the original YOLOv11 algorithm. YOLOv8 achieves… |
| 2 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0016` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 14–17 | feature, merge, yolo | …still has the following limitations: the current dataset only includes three major defect types and does not cover niche defect types such as tape misalignment and printing contamination, requiring further expansion of data diversity; Although the number of parameters i… |
| 3 | `696N7XZ8` / `696N7XZ8:696N7XZ8_chunk_0003` — Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8 | 2–4 | complexity, computational, feature, pyramid, reduce | …odule improves spatial pyramid pooling (SPP) [12]. The Neck module retains the PANet structure from YOLOv5, and it comprises a feature pyramid network (FPN) [13] and a path aggregation network (PAN) [14]. The Head module adopts a Decoupled Head, separates localization a… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D009 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `tpmn_flute_classes_misattribution`
- 中文：TPMN是否将瓦楞纸板横截面分为B、C、E、BC、EB、EC、EE和Not八类？
- English: Does TPMN classify corrugated-board cross-sections into B, C, E, BC, EB, EC, EE, and Not?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: the seven flute types plus Not class belong to the corrugated-board CNN study, not TPMN.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `JRIUZQ58` / `JRIUZQ58:JRIUZQ58_chunk_0019` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms | 12–13 | b, bc, board, c, corrugated, e, eb, ec | …e. It can be noticed that the algorithm still solves the sinusoidal function approximation, but does not reﬂect the deformed corrugated layer shape. In this case, the ﬂute period and height are not correctly measured, but can be used to estimate Figure 13. Visualization… |
| 2 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0009` — In-situ classification of highly deformed corrugated board using convolution neural networks | 5–6 | b, bc, board, c, corrugated, cross, e, eb | … relevant samples but also ensured that the experiments were grounded in real-world applications of corrugated board analysis. Using the equipment presented in the previous section, a total number of 646 samples were acquired, and as the results, images of their cross-s… |
| 3 | `JRIUZQ58` / `JRIUZQ58:JRIUZQ58_chunk_0018` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms | 12–12 | b, bc, board, c, corrugated, cross, e, eb | l corrugated board sample in a fully automatic manner. Unfortunately, damaging the structure of the layers or severe cross-section crushing may cause unreliable and false results. Figure 13 presents the results for exemplary corrugated boards samples with BC, EB, EC, an… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D010 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `cross_factory_zero_shot_validation`
- 中文：哪些论文公开了跨工厂零样本验证？
- English: Which papers report cross-factory zero-shot validation?
- Proposed answerability: `false`
- Candidate answer/resolution: No frozen-corpus paper was found to report cross-factory zero-shot validation; author must confirm corpus-wide absence.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0004` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–3 | cross, papers | …st step in the automatization of corrugated board modeling based on their cross-sectional pictures, which can lead to more realistic numerical analyses of these structures with real imperfections. 2. Materials and Methods 2.1. Corrugated Boards and Their Types The basic… |
| 2 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0005` — In-situ classification of highly deformed corrugated board using convolution neural networks | 3–4 | cross, papers | …automatization of corrugated board modeling based on their cross - sectional pictures, which can lead to more reali stic numerical analys e s of these structures with real imperfections. 2. Materials and Methods 2.1. Corrugated Boards and Their Types The basic structure… |
| 3 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0009` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 8–9 | zero | …= soft max(QKT)V (11) Specifically, if the coordinates fall outside the feature map, we abandon the zero-padding method used in the original QA method and instead use mirror padding. This is because when the quadrilateral exceeds the boundary of the feature map, directl… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D011 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `tpmn_90pct_target_misattribution`
- 中文：Cardboard-Boxes-Dataset上的TPMN实验是否把90%设为检测准确率目标？
- English: Do the TPMN experiments on Cardboard-Boxes-Dataset set a 90% detection-accuracy target?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: 90% is a target for the hybrid 2D/3D system, not a TPMN/Cardboard-Boxes-Dataset target.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `L4DLHQUZ` / `L4DLHQUZ:L4DLHQUZ_chunk_0010` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection | 6–7 | accuracy, boxes, cardboard, dataset, detection, experiments, on, set | …as well as the variance of cross entropy and accuracy. We additionally designed the Backbone of the TPMN based on MobileNet, known as MN-TPMN. The model was trained and tested a total of 10 times. All models were trained and tested in the cardboard-boxes dataset for a t… |
| 2 | `L4DLHQUZ` / `L4DLHQUZ:L4DLHQUZ_chunk_0012` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection | 8–9 | boxes, cardboard, dataset, detection, experiments, on, set, tpmn | …onvolutional layer. Fig. 4a Fig. 4b and Fig. 4c demonstrate the advantages of the two main modules. TPMN can more accurately locate and focus on edge features, leading to accurate predictions. Without the two modules, backbone can only make predictions by broadly attend… |
| 3 | `L4DLHQUZ` / `L4DLHQUZ:L4DLHQUZ_chunk_0003` — TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection | 2–2 | boxes, cardboard, dataset, detection, experiments, on, tpmn | …sidering the above challenges, we propose a texture prior-aware multi-level feature fusion network (TPMN). Our method aims to accurately detect defect courier parcels, meeting the logistics company’s need to track packaging defect status and providing crucial informatio… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### D012 — `recommend_keep`

- Split/type: `dev_hard_negative` / `hard_negative`
- Claim family: `ssd_qzudet_map_misattribution`
- 中文：SSD纸箱缺陷系统是否在QZU-DET上报告了98.1%的mAP50？
- English: Does the SSD carton-defect system report 98.1% mAP50 on QZU-DET?
- Proposed answerability: `false`
- Candidate answer/resolution: Reject the attribution: 98.1% mAP50 on QZU-DET belongs to the modified-YOLO paper, not the SSD system.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0014` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 16–17 | 1, defect, det, map50, on, qzu | …emonstrate the proposed method’s stronger robustness and more favorable overall trade-off for cloth defect detection under complex conditions. The experimental results in both tables demonstrate that the proposed method achieves the best overall performance on both QZU-… |
| 2 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0013` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 15–16 | 1, defect, det, map50, on, qzu | …ods and fully satisfies real-time detection requirements. More importantly, the improved efficiency does not come at the cost of detection accuracy. The proposed model achieves the best performance across all accuracy metrics, including mAP50, mAP50–95, and F1 score. Th… |
| 3 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0005` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 4–5 | 1, 98, defect, det, map50, on, qzu | …daptability to scale variations and significantly improves the detection performance of small-scale defect targets. 3. To address the high proportion of small-object samples and the class imbalance commonly observed in industrial packaging defect detection, Focal Loss i… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### H001 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `two_view_dataset_unit_and_views`
- 中文：双视图迁移学习包装数据集包含多少个包装样本，每个样本由哪些视图组成？
- English: How many package examples are in the two-view transfer-learning dataset, and which views make up each example?
- Proposed answerability: `true`
- Candidate answer/resolution: The dataset has 200 package examples represented by 400 RGB images; each package has one top view and one side view.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0003`; pages 2–2; normalized section unavailable.
  - Original excerpt: “…ion that utilizes both top view and side view images of the packaging as inputs to determine if the package is defective or not. However, the dataset we have is a small dataset [15]. To address this issue, we em ployed deep learning with transfer learning. This technique leverages a pre -trained model to transfer knowledge from one domain to another. It is faster and less time -consuming than training a model from random initialization [16], [17] . Moreover, it is particularly suitable for training with a limited d…”
- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0004`; pages 2–4; normalized section unavailable.
  - Original excerpt: “we used an Industrial quality control of packages kaggle d ataset that was open to the public [15]. This dataset consists of computer -generated images designed to resemble packages produc ed on an industrial production line. This dataset is composed of 400 RGB images from a ‘virtual’ production line. Each package consists of two images, one top -view image and one side -view image. This means there are only 200 package examples in this datase t. These packages are divided into two classes, ‘intact’ and  ISSN: 250…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H002 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `cnn_not_class_purpose`
- 中文：瓦楞纸板CNN分类器为什么增加Not类，它表示什么情况？
- English: Why does the corrugated-board CNN classifier add a Not class, and what situation does it represent?
- Proposed answerability: `true`
- Candidate answer/resolution: The Not class represents no board sample or an invalid acquisition state such as an open device door, preventing forced assignment to one of seven flute classes.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0009`; pages 5–6; normalized section unavailable.
  - Original excerpt: “… relevant samples but also ensured that the experiments were grounded in real-world applications of corrugated board analysis. Using the equipment presented in the previous section, a total number of 646 samples were acquired, and as the results, images of their cross-sections were obtained. Some samples were deformed manually in a random way or using a creasing machine. Within the group of samples with the same flute type, the numbers for non-deformed, manually deformed and creasing machine deformed were the same.…”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0010`; pages 6–7; normalized section unavailable.
  - Original excerpt: “…the classifiers studied in this paper should also be used to recognize images with no sample of the corrugated board. Therefore, images with an additional class (class Not) were generated to represent situations in which the sample is not present in the acquisition device, the door of the device is not closed, etc. If there were no additional class, the model would give an answer within the seven classes it knows, which would be an obvious mistake. Examples of all eight classes are presented in Figure 5. Sensors 20…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H003 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `double_wall_measured_geometry`
- 中文：双瓦楞纸板几何分析方法测量哪些几何特征？
- English: Which geometric features does the double-walled corrugated-board analysis method measure?
- Proposed answerability: `true`
- Candidate answer/resolution: It measures layer thickness, overall board thickness, flute height, and the center lines of each layer.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `JRIUZQ58` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms
  - Locator `JRIUZQ58:JRIUZQ58_chunk_0001`; pages 1–1; normalized section unavailable.
  - Original excerpt: “…rocessing and genetic algorithms, the research successfully developed an algorithm for precise geometric feature identiﬁcation of double-walled boards. Images were recorded using a special device with a sophisticated camera and image sensor for detailed corrugated board cross-sections. Demonstrating high accuracy, the method only faced limitations with very deformed or damaged samples. This research contributes signiﬁcantly to quality control in the packaging industry and paves the way for further automated materia…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H004 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `two_view_best_classification_model`
- 中文：双视图迁移学习实验中，哪个预训练模型变体取得最高分类得分，其Accuracy和F1是多少？
- English: Which pretrained-model variant achieves the highest classification scores in the two-view experiment, and what are its Accuracy and F1?
- Proposed answerability: `true`
- Candidate answer/resolution: EfficientNetV2-21k-S with RGB input achieves 100% Accuracy and 100% F1.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0010`; pages 7–8; normalized section unavailable.
  - Original excerpt: “… as the feature extractor on the 21k-S variants with a perfect score of 100% accuracy and F1 score, which use RGB image as the input. Despite the perfect performance score, it ranked second if we include the inference speed in the calculation. The model that demonstrated the best balance between classification performance and inference speed is model with a pre-trained ResNetV2-50 variant as the feature extractor with a score of 95% accuracy and 95.24% F1 score, and 91 ms inference speed, which also use RGB image a…”
- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0011`; pages 8–9; normalized section unavailable.
  - Original excerpt: “…co lor spaces, namely RGB and grayscale. Our experiments yielded promising results. The best model, which leverages EfficientNetV2 -21k-S as a feature extractor, achieved a perfect 100% accuracy and F1 score in terms of classification performance. However, the most optimal model in terms of classification performance and inference speed was the one that leveraged ResNetV2-50 as a feature extractor. This model scored 95% accuracy and 95.24% F1 score, with an inference speed of 91 ms. Both models used RGB images as i…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H005 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `flute_cnn_best_architecture_accuracy`
- 中文：瓦楞纸板类型分类中，最高平均准确率的CNN结构是什么，平均准确率是多少？
- English: Which CNN architecture has the highest average accuracy for corrugated-board type classification, and what is that accuracy?
- Proposed answerability: `true`
- Candidate answer/resolution: The 6conv_0dense_128nodes network—six convolutional layers, 128 filters per layer, and no dense layer—has 99.04% average accuracy.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0012`; pages 8–8; normalized section unavailable.
  - Original excerpt: “…ons (blue box in Figure 7). After each convolution, one can observe the MaxPooling layer (red box), which reduces the size of the feature map. After this layer, the Flatten layer (to transform a tensor to a vector) and the Dense layers, with a number of neurons equal to the number of filters and ReLu activation functions, can be applied. However, the structure yielding the best results did not include these elements. Here, a Dropout layer is applied to avoid overfitting. In the end, one Dense layer is applied with …”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0013`; pages 8–9; normalized section unavailable.
  - Original excerpt: “…pared test datasets:dataset1, dataset2, dataset3, and dataset4. This is a kind of cross-validation, which is intended to provide an objective assessment of the suitability of networks with different structures for the issue under consideration. Training and evaluating models with the same hyperparameters for several different arrangements of divisions into training and testing sets ensures the greater reliability of the obtained results. The results for all the trained models, in the form of accuracies obtained on …”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H006 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `double_wall_genetic_algorithm_parameters`
- 中文：双瓦楞几何方法的遗传算法使用了多少次最大迭代、多少种群规模，以及什么变异和交叉概率？
- English: What maximum iterations, population size, mutation probability, and crossover probability are used by the genetic algorithm for double-wall geometry?
- Proposed answerability: `true`
- Candidate answer/resolution: It uses 500 maximum iterations, population size 100, mutation probability 0.15, and crossover probability 0.2.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `JRIUZQ58` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms
  - Locator `JRIUZQ58:JRIUZQ58_chunk_0016`; pages 11–11; normalized section unavailable.
  - Original excerpt: “…𝑇௜. Applying the genetic algorithm, the following parameters were utilized: 1. Maximal number of iterations: 500; 2. Population size: 100; 3. Mutation probability: 0.15; 4. Elite group ratio (portion of population, which contains the individuals achieved the best performance in the current generation, and are directly copied to the next generation without mutation and crossover): 0.01; 5. Crossover probability: 0.2; 6. Parents portion: 0.2; 7. Crossover type: uniform. An example of the genetic algorithm result is p…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H007 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `qzudet_map50_f1`
- 中文：QZU-DET上的改进YOLOv8报告了多少mAP50和F1？
- English: What mAP50 and F1 does the improved YOLOv8 report on QZU-DET?
- Proposed answerability: `true`
- Candidate answer/resolution: It reports 98.1% mAP50 and 91.6% F1 on QZU-DET.
- Development passage overlap: `true`; overlapping queries: `Q08, Q15`.
- Development answer-claim overlap: `false`.
- Independence note: The passages overlap development qrels, but development asks inference speed and small/multi-scale methods, not the mAP50/F1 result.

Proposed qrel evidence:

- `3NLKTSIP` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports
  - Locator `3NLKTSIP:3NLKTSIP_chunk_0002`; pages 2–3; normalized section unavailable.
  - Original excerpt: “…of CNNbased object detection methods. R-CNN 3 was proposed by Kirchick et al., and it significantly improved object detection performance by leveraging CNNs to enhance feature extraction and detection accuracy. Two-stage object detection methods, such as R-CNN, Fast R-CNN4, Faster R-CNN5, and Mask R-CNN6, typically generate candidate regions of interest (ROIs) using a region proposal netw”
- `3NLKTSIP` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports
  - Locator `3NLKTSIP:3NLKTSIP_chunk_0005`; pages 4–5; normalized section unavailable.
  - Original excerpt: “…f small and hard-to-detect objects. Based on the above improvements, the proposed model achieves an mAP50 of 98.1% on the QZU-DET dataset, representing a 3.2 percentage-point improvement over the YOLOv8n baseline. In addition, the model attains an F1 score of 91.6% on QZU-DET, indicating strong detection reliability. Benefiting from its lightweight architecture, the proposed method maintains real-time inference efficiency, achieving 121 FPS, which is higher than the baseline model. These results demonstrate that th…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H008 — `recommend_keep`

- Split/type: `held_out` / `single_paper`
- Claim family: `ssd_training_photo_count`
- 中文：改进SSD纸箱缺陷模型收集了多少张物流纸箱照片用于训练和优化？
- English: How many logistics-carton photos were collected to train and optimize the improved SSD model?
- Proposed answerability: `true`
- Candidate answer/resolution: The study collected 2,000 logistics-carton photos.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `Z5HMPJQG` — SSD-based carton packaging quality defect detection system for the logistics supply chain
  - Locator `Z5HMPJQG:Z5HMPJQG_chunk_0005`; pages 4–6; normalized section unavailable.
  - Original excerpt: “…e proposed model to carton p ackaging quality defect detection, a dataset containing 2000 photos of logistics carto ns was collected to train and optimise the model. The mean Average Precision (mAP) and Frames Per Second (FPS) are used to evaluate the detection accuracy and detection speed of the model. SSD-based carton packaging quality defect detection system for the logistics supply chain 121 Effect of different IOU thresholds on the detection effect IOU is an important parameter in target detection. Generally, …”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H009 — `recommend_keep`

- Split/type: `held_out` / `cross_paper`
- Claim family: `cross_paper_input_sample_construction`
- 中文：双视图迁移学习研究与瓦楞纸板CNN分类研究分别如何构成单个输入样本？
- English: How do the two-view transfer-learning study and the corrugated-board CNN classification study construct one input sample?
- Proposed answerability: `true`
- Candidate answer/resolution: The transfer-learning study pairs top and side package views; the board-classification study records a board cross-section with a dedicated camera/LED acquisition device.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0004`; pages 2–4; normalized section unavailable.
  - Original excerpt: “…d of 400 RGB images from a ‘virtual’ production line. Each package consists of two images, one top -view image and one side -view image. This means there are only 200 package examples in this datase t. These packages are divided into two classes, ‘intact’ and  ISSN: 2502-4752 Indonesian J Elec Eng & Comp Sci, Vol. 34, No. 3, June 2024: 2096-2106 2098 ‘damaged’, indicating the condition of the package box. Specifically, 100 packages are intact and the other 100 are damaged. The images contained in the dataset are p…”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0007`; pages 4–5; normalized section unavailable.
  - Original excerpt: “…were created using 3D printing. Sensors 2024, 24, 1051 5 of 15 Sensors 2024 , 24 , x FOR PEER REVIEW 5 of 16 W/m power, placed on the partition wall. The light is manually operated with a bistable key switch. External connections from the device include a power cable for the lighting and a USB cable fo r image transfer to a computer. The device ’ s components were created using 3D printing. For image capture, the system utilizes an ArduCam B0197 camera, featuring autofocus and an 8 MPx Sony IMX179 (1/3.2 ″ ) image …”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0008`; pages 5–5; normalized section unavailable.
  - Original excerpt: “…ed in JPEG format with a maximum resolution of 3264 × 2448 pixels. ( a ) ( b ) Figure 3. Device for corrugated board image acquisition: ( a ) visualization of the device; ( b ) layout diagram of the most important components of the device ( 1 — corrugated board sample; 2 — camera; 3 — LED strip (all dimensions in this picture are given in mm) ) . 2.3. Dataset The samples used for the presented research were obtained from FEMAT [ 38 ], a company that specializes in the strength analysis of corrugated bo ard and with…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H010 — `recommend_keep`

- Split/type: `held_out` / `cross_paper`
- Claim family: `cross_paper_best_classification_models`
- 中文：两项包装分类研究各自取得最高分类得分的模型是什么，报告的得分如何比较？
- English: Which model achieves the highest classification score in each of the two packaging-classification studies, and how do the reported scores compare?
- Proposed answerability: `true`
- Candidate answer/resolution: EfficientNetV2-21k-S reports 100% Accuracy/F1 in the two-view study; 6conv_0dense_128nodes reports 99.04% average accuracy in the flute-classification study.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0010`; pages 7–8; normalized section unavailable.
  - Original excerpt: “… as the feature extractor on the 21k-S variants with a perfect score of 100% accuracy and F1 score, which use RGB image as the input. Despite the perfect performance score, it ranked second if we include the inference speed in the calculation. The model that demonstrated the best balance between classification performance and inference speed is model with a pre-trained ResNetV2-50 variant as the feature extractor with a score of 95% accuracy and 95.24% F1 score, and 91 ms inference speed, which also use RGB image a…”
- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0011`; pages 8–9; normalized section unavailable.
  - Original excerpt: “…co lor spaces, namely RGB and grayscale. Our experiments yielded promising results. The best model, which leverages EfficientNetV2 -21k-S as a feature extractor, achieved a perfect 100% accuracy and F1 score in terms of classification performance. However, the most optimal model in terms of classification performance and inference speed was the one that leveraged ResNetV2-50 as a feature extractor. This model scored 95% accuracy and 95.24% F1 score, with an inference speed of 91 ms. Both models used RGB images as i…”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0012`; pages 8–8; normalized section unavailable.
  - Original excerpt: “…ons (blue box in Figure 7). After each convolution, one can observe the MaxPooling layer (red box), which reduces the size of the feature map. After this layer, the Flatten layer (to transform a tensor to a vector) and the Dense layers, with a number of neurons equal to the number of filters and ReLu activation functions, can be applied. However, the structure yielding the best results did not include these elements. Here, a Dropout layer is applied to avoid overfitting. In the end, one Dense layer is applied with …”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0013`; pages 8–9; normalized section unavailable.
  - Original excerpt: “…pared test datasets:dataset1, dataset2, dataset3, and dataset4. This is a kind of cross-validation, which is intended to provide an objective assessment of the suitability of networks with different structures for the issue under consideration. Training and evaluating models with the same hyperparameters for several different arrangements of divisions into training and testing sets ensures the greater reliability of the obtained results. The results for all the trained models, in the form of accuracies obtained on …”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H011 — `recommend_keep`

- Split/type: `held_out` / `cross_paper`
- Claim family: `cross_paper_geometry_vs_classification_output`
- 中文：双瓦楞几何分析论文与瓦楞纸板CNN论文的主要输出目标有何不同？
- English: How do the primary output goals differ between the double-wall geometry paper and the corrugated-board CNN paper?
- Proposed answerability: `true`
- Candidate answer/resolution: The geometry method estimates physical layer/flute geometry from cross-sections; the CNN method assigns flute/type classes to cross-section images.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `JRIUZQ58` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms
  - Locator `JRIUZQ58:JRIUZQ58_chunk_0001`; pages 1–1; normalized section unavailable.
  - Original excerpt: “Citation: Rogalka, M.; Grabski, J.K.; Garbowski, T. Deciphering Double-Walled Corrugated Board Geometry Using Image Analysis and Genetic Algorithms. Sensors 2024, 24, 1772. https://doi.org/10.3390/ s24061772 Academic Editor: Liang-Jian Deng Received: 23 January 2024 Revised: 5 March 2024 Accepted: 6 March 2024 Published: 9 March 2024 Copyright: © 2024 by the authors. Licensee MDPI, Basel, Switzerland. This article is an open access article distributed under the terms and conditions of the Creative Commons Attributi…”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0004`; pages 3–3; normalized section unavailable.
  - Original excerpt: “…using the CNNs, basing their classiﬁcation on raw cross - section images [27]. Li et al. explored diﬀerent deep le arning techniques to analyze the geometric features of self - piercing riveting cross - section, with SOLOv2 and U - Net architectures yielding the best results [28]. Ma et al. conducted a study on the geometrical parameters of crushed thin - walled carbon ﬁ- ber - r einforced polymer tubes cross - sections [29]. Daigo et al. propose d the use of PSPNet to estimate the thickness of steel in heavy melti…”
- `Q55RU9N6` — In-situ classification of highly deformed corrugated board using convolution neural networks
  - Locator `Q55RU9N6:Q55RU9N6_chunk_0005`; pages 3–4; normalized section unavailable.
  - Original excerpt: “… one ﬂute for a single - wall corrugated board, see Figure 1a. On the other hand, the double - wall corrugated board include s three liners and two ﬂutes — see Figure 1b. ( a ) ( b ) Figure 1. Cross - sections of the corrugated boards for: ( a ) single - walled (3 - ply) board; ( b ) double - walled (5 - ply) board. Figure 1. Cross-sections of the corrugated boards for: ( a) single-walled (3-ply) board; (b) doublewalled (5-ply) board. The corrugated boards can be classified based on their geometrical features. In t…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H012 — `recommend_keep`

- Split/type: `held_out` / `cross_paper`
- Claim family: `cross_paper_data_quality_limitations`
- 中文：双视图包装分类与双瓦楞几何分析分别报告了什么数据或样本质量限制？
- English: What data or sample-quality limitation is reported by the two-view package classifier and by the double-wall geometry method?
- Proposed answerability: `true`
- Candidate answer/resolution: The classifier results come from a small computer-generated dataset and may differ on real-world data; the geometry method degrades with crushed/noisy cross-sections and depends on sample quality.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.

Proposed qrel evidence:

- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0010`; pages 7–8; normalized section unavailable.
  - Original excerpt: “… promising, please keep in mind that this performance was gained using a small computer - generated dataset, which may differ from a big real-world dataset. However, if the real -world image datasets are similar with the dataset we used on our experiments, it may have comparable results with our experiments. 4. CONCLUSION This study introduces a novel approach for detecting physical defects in product packaging boxes by integrating image processing with deep learning, specifically transfer learning with two images …”
- `2V3T43BS` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning
  - Locator `2V3T43BS:2V3T43BS_chunk_0011`; pages 8–9; normalized section unavailable.
  - Original excerpt: “…odel performance. For future research, it may be worthwhile to conduct experiments with real -world datasets instead of computer -generated ones. Exploring real-time model approaches such as YOLO could also be beneficial. While our findings show promising results, they were obtained using a small computer -generated dataset. Therefore, the performance may differ when using real -world datasets. However, if the r eal-world dataset is similar to the one used in our  ISSN: 2502-4752 Indonesian J Elec Eng & Comp Sci, …”
- `JRIUZQ58` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms
  - Locator `JRIUZQ58:JRIUZQ58_chunk_0026`; pages 17–17; normalized section unavailable.
  - Original excerpt: “…nted in Figure 18. Example of the error in recognizing the number of layers in the corrugated board sample: (a) a single-wall C-ﬂute sample with a visible hank of cellulose ﬁbers; ( b) a smoothed row–sum curve of the image with wrongly localized peaks, potentially reﬂecting the liners of the corrugated board. Difﬁculty in the measurements of the liner thickness can also be caused by factors other than cross-section noise. Figure 19 depicts a relatively common (among samples processed in the research) case of both ﬂ…”
- `JRIUZQ58` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms
  - Locator `JRIUZQ58:JRIUZQ58_chunk_0028`; pages 17–18; normalized section unavailable.
  - Original excerpt: “…G.; formal an alysis, M.R.; investigation, M.R. and J.K.G.; resources, M.R. and T.G.; data curation, M.R.; writ ing—original draft preparation, M.R., J.K.G. and Figure 20. (a) The original example (very weak effect) and ( b) the results of the same image after limiting the layer thickness measurement areas. Sensors 2024, 24, 1772 18 of 19 5. Conclusions In this paper, the method for identifying the geometric features of double-wall corrugated board cross-sections is presented. The cross-section images were collecte…”
- `JRIUZQ58` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms
  - Locator `JRIUZQ58:JRIUZQ58_chunk_0029`; pages 18–18; normalized section unavailable.
  - Original excerpt: “….G. and T.G.; formal analysis, M.R.; investigation, M.R. and J.K.G.; resources, M.R. and T.G.; data curation, M.R.; writing—original draft preparation, M.R., J.K.G. and T.G.; writing—review and editing, J.K.G. and T.G.; visualization, M.R.; supervision, J.K.G.; project administration, J.K.G. and T.G.; funding acquisition, J.K.G. and T.G. All authors have read and agreed to the published version of the manuscript. Funding: This research received no external funding. Institutional Review Board Statement: Not applicab…”

- Qrel completeness: candidate includes every substantive duplicate/overlapping chunk identified during local claim-term and adjacent-window inspection; references/table-only keyword hits were excluded. Human confirmation remains required.
- Reviewer must confirm: direct support, complete qrels, precise answer boundary, translation equivalence, and held-out independence.

### H013 — `recommend_keep`

- Split/type: `held_out` / `in_domain_no_answer`
- Claim family: `two_view_real_warehouse_accuracy_no_answer`
- 中文：双视图迁移学习包装分类器在独立真实仓库数据集上的准确率是多少？
- English: What accuracy does the two-view transfer-learning package classifier report on an independent real-warehouse dataset?
- Proposed answerability: `false`
- Candidate answer/resolution: No independent real-warehouse accuracy is reported; the paper warns that results use a small computer-generated dataset.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0011` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 8–9 | accuracy, dataset, learning, on, package, real, transfer, two | …e best model, which leverages EfficientNetV2 -21k-S as a feature extractor, achieved a perfect 100% accuracy and F1 score in terms of classification performance. However, the most optimal model in terms of classification performance and inference speed was the one that … |
| 2 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0003` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 2–2 | accuracy, dataset, learning, on, package, transfer, two, view | …loyed a learning feature for defect classification and have achieved a s atisfactory classification accuracy by employing a deep learning algorithm [3]. Moreover, Liu et al. [10] presented an approach for fabric defect detection based on generative adversarial networks … |
| 3 | `2V3T43BS` / `2V3T43BS:2V3T43BS_chunk_0001` — Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 1–1 | accuracy, learning, on, package, transfer, two, view | …mental findings demonstrate that the best model that leverages EfficientNetV2 variant achieves 100% accuracy and F1 score in terms of classification performance. However, the most optimal model in terms of classification performance and inference speed was the one that … |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### H014 — `recommend_keep`

- Split/type: `held_out` / `in_domain_no_answer`
- Claim family: `flute_cnn_delamination_inclination_accuracy_no_answer`
- 中文：瓦楞纸板CNN对分层或倾斜样本报告了多少分类准确率？
- English: What classification accuracy does the corrugated-board CNN report for delaminated or inclined samples?
- Proposed answerability: `false`
- Candidate answer/resolution: No subgroup accuracy exists because the study states that inclined and delaminated samples were absent.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0017` — In-situ classification of highly deformed corrugated board using convolution neural networks | 11–12 | accuracy, board, classification, corrugated, inclined, or, samples | Figure 10. ( a ) ( b ) ( c ) ( d ) Figure 10. Examples of classification results for: ( a ) flute BC; ( b ) flute B; ( c ) flute C; ( d ) no sample case. 4. Discussion In this section, the analysis of incorrectly recognized corrugated cardboard samples is performed for … |
| 2 | `Q55RU9N6` / `Q55RU9N6:Q55RU9N6_chunk_0018` — In-situ classification of highly deformed corrugated board using convolution neural networks | 12–13 | accuracy, board, classification, corrugated, inclined, or, samples | …. Therefore, the degree of creasing of the sample ha s the most signiﬁcant impact on the correct classiﬁcation of the type of corrugated board among the types of imperfections taken into account. The obtained results also show that the trained network models coped beer… |
| 3 | `JRIUZQ58` / `JRIUZQ58:JRIUZQ58_chunk_0019` — Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms | 12–13 | board, corrugated, or, samples | …e. It can be noticed that the algorithm still solves the sinusoidal function approximation, but does not reﬂect the deformed corrugated layer shape. In this case, the ﬂute period and height are not correctly measured, but can be used to estimate Figure 13. Visualization… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### H015 — `recommend_keep`

- Split/type: `held_out` / `near_miss_hard_negative`
- Claim family: `rgbd_carton_direct_detection`
- 中文：哪篇论文使用RGB-D直接检测瓦楞纸箱缺陷？
- English: Which paper uses RGB-D to directly detect corrugated carton defects?
- Proposed answerability: `false`
- Candidate answer/resolution: No paper joins RGB-D plane fitting with direct corrugated-carton defect detection.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0001` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 1–2 | carton, defects, detect, directly | …l publication, the manuscript will undergo further editing. Please note there may be errors present which affect the content, and all legal disclaimers apply. If this paper is publishing under a Transparent Peer Review model then Peer Review reports will publish with th… |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0006` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 5–7 | carton, d, defects, detect | …n of carton packaging quality has problems such as slow speed, poor effect, and waste of resources, which is not conducive to susta inable economic development. Therefore, this paper constructs a logistics supply chain carton packaging quality defect detection system ba… |
| 3 | `3NLKTSIP` / `3NLKTSIP:3NLKTSIP_chunk_0002` — Modified YOLO for tape-sealing defects in outer packaging of cigarette carton | Scientific Reports | 2–3 | carton, defects, detect | …proving production efficiency, and enhancing product quality are effective strategies for household paper companies to increase their competitiveness. During production, defects, such as more significant gaps, overlaps, or incomplete connections, inevitably appear in th… |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

### H016 — `recommend_keep`

- Split/type: `held_out` / `near_miss_hard_negative`
- Claim family: `mri_121fps_attribution`
- 中文：哪篇论文用MRI达到121 FPS的包装检测？
- English: Which paper uses MRI to achieve 121 FPS packaging inspection?
- Proposed answerability: `false`
- Candidate answer/resolution: No MRI system reports 121 FPS; 121 FPS belongs to the vision-based QZU-DET model.
- Development passage overlap: `false`; overlapping queries: `none`.
- Development answer-claim overlap: `false`.
- Independence note: No qrel passage overlap with reviewed development; answer intent was audited as distinct.


Corpus-wide lexical probe (existing BM25-EN, Top-3):

| Rank | Paper / passage | Pages | Lexical match | Original excerpt |
|---:|---|---:|---|---|
| 1 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0016` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 14–17 | achieve, fps, inspection, packaging | …wavelet decomposition, combined with the cross-level feature adaptive fusion of the QA Transformer, which solves the problem of small target features being easily lost. In addition, ablation experiments further verify the effectiveness of different modules. Although in … |
| 2 | `Z5HMPJQG` / `Z5HMPJQG:Z5HMPJQG_chunk_0005` — SSD-based carton packaging quality defect detection system for the logistics supply chain | 4–6 | 121, fps, packaging | …he downsampling in the multiscale attention mechanism is set to different sizes. Experiment In this paper, the experimental environment is Wind ows 10, the processor is Intel i7-10875H, the memory is 16 GB, and the graphics ca rd is NVIDIA GeForce RTX 2070 with TensorFl… |
| 3 | `DZ6TYBIQ` / `DZ6TYBIQ:DZ6TYBIQ_chunk_0001` — Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios | PLOS One | 1–2 | inspection, packaging | … is an open access article distributed under the terms of the Creative Commons Attribution License, which permits unrestricted use, distribution, and reproduction in any medium, provided the original author and source are credited. Data availability statement: The data … |

- Qrel completeness: no positive qrel is proposed. The reviewer must verify that no passage supports the complete relation/attribution, not merely that exact wording is absent.
- Reviewer must confirm: corpus-wide unsupported status, absence of a hidden positive relation, translation equivalence, and realistic near-miss difficulty.

## Dependency reproducibility

- Formal R1 package validation uses `jsonschema.Draft202012Validator`; metric calculation remains independent of this package.
- Revision 2 pins `jsonschema==4.25.0` in the existing test extra and test lock. The Schema test is mandatory in that environment rather than silently skipped.

## Human decision target

Use `pending_candidates.review.csv`. Complete `answerable_correct`, `relevant_passages_correct`, `review_decision`, `reviewer`, `reviewed_at`, and `reviewer_notes`. Nothing becomes reviewed until a later, separately authorized freeze.
