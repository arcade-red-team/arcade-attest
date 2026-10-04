# Arcade Agent + Decision API — Category & Scoring theo DEV Flow Problems

Generated 2026-10-02. Áp cho 100 decision cases trong `100-decision-cases.md`.

Mục đích: không để 100 cases là list rời rạc. Gom theo **vấn đề chung mọi DEV flow đều gặp**, chấm điểm ưu tiên, biết case nào build trước / demo trước / bán trước.

---

## 1. DEV Flow chuẩn — nơi Decision nảy sinh

Mọi team DEV, dù web / mobile / Web3 / enterprise, đều chảy qua 10 chặng này. Decision API có mặt ở bất kỳ chặng nào có "trước khi làm X, có nên không?"

| # | DEV Flow Stage | Quyết định điển hình | Consumer chính |
|---|---|---|---|
| F1 | Plan & Design (ADR/RFC) | Duyệt thiết kế này không? | Tech lead, Architecture Board |
| F2 | Code (người + AI agent) | Code vừa sinh có sạch không? | Dev, AI agent runner |
| F3 | Commit / Local check | Có nên commit/PR đoạn này không? | Dev cá nhân |
| F4 | Pull Request & Review | Merge PR này không? Review sâu hay lướt? | Maintainer, reviewer |
| F5 | CI / Build / Test | Cho pipeline qua không? | CI system, GitHub Action |
| F6 | Merge & Release | Release này có regress kiến trúc không? | Release manager |
| F7 | Deploy / Operate | Hotfix có được phá lệ không? Rollback không? | On-call, SRE |
| F8 | Maintain / Refactor | Refactor có thật tốt hơn không? Nợ kỹ thuật giảm không? | Dev, CTO |
| F9 | Ecosystem / Collab | Fork, vendor, outsource, contributor lạ có tin được không? | OSS maintainer, DAO |
| F10 | Govern / Audit / Fund | Rót tiền / ký / chứng nhận có căn cứ không? | Investor, grantor, auditor |

100 cases phân bố: F4+F5 chiếm nhiều nhất (PR/CI gate), đó đúng với chỗ đau hằng ngày. F10 ít case nhưng giá trị tiền cao nhất mỗi lần gọi.

---

## 2. 12 vấn đề chung (Common Problems) của toàn bộ DEV flows

Đây là taxonomy gốc. Mỗi case trong 100 đều map về 1 vấn đề chính (primary) + có thể 1-2 vấn đề phụ.

| Code | Vấn đề chung | Biểu hiện ai cũng gặp | Case mẫu trong 100 |
|---|---|---|---|
| P1 | **Architecture Drift** — kiến trúc trượt dần khỏi thiết kế ban đầu | Mỗi PR "nhỏ" lệch 1 chút, 6 tháng sau không ai nhận ra hệ thống | #1, #6, #21, #43, #81 |
| P2 | **God Component / Bloat** — 1 module phình, ôm mọi responsibility | File 2.000 dòng, ai cũng sợ đụng | #3, #11, #34, #65, #87 |
| P3 | **Hidden Coupling & Cycles** — coupling giấu mặt, vòng phụ thuộc | Sửa A vỡ B, không ai thấy đường dây | #9, #12, #31, #52 |
| P4 | **Review Bottleneck** — review quá tải, quyết bằng cảm tính | Maintainer ngập PR, merge theo niềm tin | #4, #41, #42, #48 |
| P5 | **Regression Không Có Bằng Chứng** — "chắc không sao đâu" | Không số trước/sau, cãi nhau bằng ý kiến | #5, #43, #86, #100 |
| P6 | **AI Code Không Kiểm Chứng** — agent sinh code nhanh hơn người review | God file, cycle, thư viện lạ do agent tạo | #61-#70 |
| P7 | **Migration Risk** — đổi framework/tool đầy bất trắc | Migration kéo theo shift ngoài ý muốn | #21-#30 |
| P8 | **Security & Trust Boundary Violation** | Module trust thấp đọc dữ liệu trust cao, agent chạm file cấm | #51-#60, #53 |
| P9 | **Knowledge Silo / Bus Factor** | 1 component "không ai dám đụng", 1 người nắm hết | #82, #89 |
| P10 | **Thiếu Audit Trail** — quyết định không truy vết được | Audit/funding hỏi bằng chứng, chỉ có lời nói | #56, #90, #94 |
| P11 | **Quyết Định Không Có Tiêu Chí Đo Được** | ADR viết xong không ai verify lúc implement | #28, #29, #81, #88 |
| P12 | **Tiền Không Gắn Với Chất Lượng** | Trả tiền/grant/seed xong mới biết code tệ | #68, #72, #75, #83, #91 |

Điểm bán hàng cốt lõi của arcade-agent: biến P1-P12 từ **cảm tính** thành **predicate đo được**. Case nào không diễn đạt được thành predicate thì chưa phải sản phẩm, chỉ là ý kiến.

---

## 3. Scoring Rubric cho từng Decision Case (thang 100)

Mỗi case chấm 6 trục. Tổng 100. Đây là điểm để xếp hạng build/demo/bán, không phải điểm chất lượng case.

| Trục | Max | Câu hỏi chấm | 5đ (thấp) → Max (cao) |
|---|---|---|---|
| **Frequency** — Tần suất quyết định xảy ra | 20 | Quyết này xảy ra bao lâu 1 lần? | Năm 1 lần (5) → Mỗi PR mỗi ngày (20) |
| **Pain** — Giá của quyết định sai | 20 | Sai thì thiệt bao nhiêu? | Khó chịu (5) → Mất tiền / mất an toàn / mất niềm tin (20) |
| **Measurability** — Đo được bằng arcade-agent không | 20 | Predicate viết được ngay, không cần đoán? | Cần edge-diff chưa có (8) → 3 predicates MVP chạy ngay (20) |
| **Automation Leverage** — Verdict tự hành động được không | 15 | PASS/BLOCK có trigger máy được không? | Chỉ để người đọc (5) → CI/contract/agent tự execute (15) |
| **Attestability** — Giá trị khi neo on-chain | 10 | Bên thứ 3 có cần proof không sửa được không? | Chỉ nội bộ (3) → Investor/DAO/auditor cần proof public (10) |
| **Monetization** — Ai trả tiền cho verdict này | 10 | Có người móc ví không? | Hobby (3) → Enterprise/DAO/grantor trả theo lần gọi (10) |

**Công thức xếp hạng nhanh khi cần quyết trong 1 phút:**
`Priority = (Frequency + Pain + Measurability) × Automation` — case nào 3 trục đầu cao mà không automate được thì vẫn kẹt ở "báo cáo đẹp", không thành "gate".

**Ngưỡng hành động:**
- **80-100: Tier S** — build ngay, demo chính, bán được.
- **65-79: Tier A** — build trong MVP mở rộng, demo phụ.
- **50-64: Tier B** — có case thật mới build, đừng build speculatively.
- **<50: Tier C** — ghi roadmap, nói thật với judges là chưa làm.

---

## 4. Scoring theo Category (10 nhóm của 100 cases)

Điểm là trung bình ước lượng của 10 case trong nhóm, chấm theo rubric trên.

| Rank | Category (100-case) | Freq/20 | Pain/20 | Measure/20 | Auto/15 | Attest/10 | Money/10 | **Tổng/100** | Tier |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **G. AI-Generated Code Gate (#61-70)** | 20 | 18 | 19 | 15 | 8 | 9 | **89** | S |
| 2 | **A. PR & CI Merge Gate (#1-10)** | 20 | 16 | 19 | 15 | 6 | 9 | **85** | S |
| 3 | **E. Monorepo & OSS Maintainer (#41-50)** | 18 | 15 | 19 | 14 | 8 | 7 | **81** | S |
| 4 | **H. Web3 / DAO / Grant (#71-80)** | 12 | 20 | 18 | 13 | 10 | 8 | **81** | S |
| 5 | **B. Refactoring & Tech Debt (#11-20)** | 16 | 14 | 20 | 12 | 6 | 7 | **75** | A |
| 6 | **F. Security & Compliance (#51-60)** | 13 | 20 | 13 | 12 | 9 | 8 | **75** | A |
| 7 | **C. Migration & Modernization (#21-30)** | 11 | 18 | 18 | 11 | 7 | 8 | **73** | A |
| 8 | **J. M&A / Funding / Audit (#91-100)** | 6 | 20 | 18 | 8 | 10 | 10 | **72** | A |
| 9 | **I. Enterprise Architecture Board (#81-90)** | 10 | 16 | 17 | 10 | 8 | 9 | **70** | A |
| 10 | **D. Microservices Boundaries (#31-40)** | 12 | 17 | 12 | 10 | 6 | 8 | **65** | A- |

**Đọc bảng này thế nào:**
- Nhóm G thắng vì AI code đang bùng nổ: quyết định xảy ra *mỗi lần agent chạy*, đau thật, đo được ngay, và verdict cho máy đọc (agent tự sửa/tự dừng) — đúng định nghĩa Decision API, không phải dashboard cho người.
- Nhóm A là bánh mì hằng ngày: tần suất cao nhất, dễ bán nhất cho mọi team DEV.
- Nhóm H điểm Attestability 10/10 duy nhất cùng J: đây là lý do duy nhất cần blockchain. Nội bộ team thì Git log đủ; chỉ khi **bên thứ 3 phải tin mà không được sửa** mới cần EAS. Colosseum chấm đúng chỗ này.
- Nhóm D thấp nhất ở Measurability: ranh giới microservices thật cần edge-level diff + manifest service, MVP chưa có. Khai thật là [EXT], đừng demo giả.

---

## 5. Scoring theo Common Problem (P1-P12) — chỗ đau nào đáng đánh trước

| Rank | Problem | Tần suất toàn ngành | Case mạnh nhất | Tổng điểm ca tốt nhất | Ghi chú chiến lược |
|---|---|---|---|---|---|
| 1 | P6 AI Code Không Kiểm Chứng | Tăng nhanh nhất 2026 | #61, #63, #64, #68 | 90+ | Thị trường mới, chưa ai chiếm "gate cho agent code" |
| 2 | P4 Review Bottleneck | Mọi OSS lớn, mọi team >5 dev | #41, #42 | 85+ | Maintainer kiệt sức là đau có thật, có tên người thật (duydo case) |
| 3 | P1 Architecture Drift | Mọi codebase >1 năm | #1, #43 | 85 | Vấn đề gốc của arcade-agent từ ngày đầu |
| 4 | P12 Tiền Không Gắn Chất Lượng | Mọi grant/seed/outsource | #68, #72, #83 | 85 | Case duy nhất nối code quality → tiền tự động |
| 5 | P5 Regression Không Bằng Chứng | Mọi release | #4, #86 | 82 | Case #4 (react#37187) là demo vàng: -19k dòng mà 0 arch change |
| 6 | P2 God Component | Mọi legacy | #11, #65 | 80 | Dễ hiểu nhất cho người không kỹ thuật (investor) |
| 7 | P11 Quyết Định Không Tiêu Chí Đo | Mọi công ty có ADR | #28, #81 | 78 | ADR-as-code là khác biệt học thuật của mình |
| 8 | P8 Trust Boundary | Ít gặp, sai thì chết | #53, #60 | 76 | Pain 20/20 nhưng Frequency thấp, Measurability cần EXT |
| 9 | P7 Migration Risk | Theo đợt | #22, #28 | 74 | Bán theo project, không bán theo subscription được |
| 10 | P3 Hidden Coupling | Mọi hệ >3 năm | #12, #52 | 72 | Cần edge-diff mới chấm cao được |
| 11 | P10 Thiếu Audit Trail | Enterprise/regulated | #56, #94 | 70 | Attestability cao nhưng Frequency thấp |
| 12 | P9 Knowledge Silo | Chậm, khó thấy | #89 | 62 | Đo gián tiếp qua god component, chưa có predicate riêng |

---

## 6. Tier S — 15 cases build & demo trước (Colosseum 10 ngày)

Chấm riêng từng case, toàn bộ ≥82, toàn bộ [MVP] chạy được ngay hôm nay:

| # | Case | Tổng | Vì sao Tier S |
|---|---|---|---|
| 64 | So 2 agent cùng làm 1 task, chọn bản kiến trúc sạch hơn | 92 | Demo viral nhất: 2 agent đua, verdict chọn thắng, ai cũng hiểu trong 10 giây |
| 61 | Agent code vừa sinh có tạo god module không | 91 | Xảy ra mỗi lần agent chạy, BLOCK trước commit |
| 63 | Khi nào cho agent tự merge code của nó | 90 | Đây là tương lai agentic DEV, judges Web3 lẫn AI đều thích |
| 68 | Agent chỉ được trả tiền khi verdict PASS (escrow đọc attestation) | 90 | Nối Decision API → tiền → on-chain, đủ bộ cho Colosseum |
| 1 | Merge PR có tạo smell mới không | 88 | Case gốc, tần suất cao nhất, CI gate |
| 4 | PR xoá lớn có thật an toàn không (react#37187 thật) | 88 | Có số thật đã chạy: -19.239 dòng, 0 shift, "safe to merge" |
| 41 | Contributor lạ: PR có an toàn để merge nhanh không | 87 | Maintainer OSS là persona judges quen |
| 72 | Grant milestone: query verdict thay vì tin báo cáo tự viết | 87 | Grantor là khách trả tiền có thật trong Web3 |
| 71 | DAO đọc verdict trước khi ký multisig merge protocol PR | 86 | Multisig + verdict = hình ảnh Colosseum nhất |
| 11 | Tách god module có hết smell không | 85 | Trước/sau rõ như ban ngày cho demo video |
| 12 | Phá cycle bằng event có tạo smell mới không | 85 | Kể được như câu chuyện: 41s → 15 phút → PASS |
| 28 | ADR mới áp dụng có hiệu quả thật không (Jaeger thật) | 84 | ADR-as-code, khác biệt không ai copy nhanh được |
| 42 | 100 PR/tuần: cái nào cần người, cái nào auto-pass | 84 | Bán được cho mọi OSS lớn |
| 75 | Investor check repo 1-call trước khi rót seed | 83 | 1 phút, 1 link EAS, investor hiểu ngay |
| 62 | Agent refactor có lén tạo cycle không | 82 | Cặp với #61 thành bộ gate cho agent |

15 case này phủ đủ 4 nhóm Tier S (G, A, E, H) và 3 chặng tiền (code → merge → trả tiền). Đây là bộ demo nên quay cho Colosseum.

---

## 7. Cái không nên build bây giờ (nói thật)

- **P3/P8 ở mức edge (case #7, #52, #53 bản EXT):** cần edge-level diff + trust threading. Điểm Measurability đang 12-13/20. Build cố trong 10 ngày sẽ ra demo giả — đúng điều playbook cấm (mục 4: không fake tính năng). Khai roadmap, demo bằng case Pkl #1645 dạng *mapping tay đã verify* thì được, hứa predicate tự động thì không.
- **Nhóm D microservices đầy đủ:** cần service manifest ngoài repo. Để sau Colosseum.
- **Case #100 (decision health 6 tháng):** là tầm nhìn, không phải demo 10 ngày. Để ở pitch closing, đừng build.

---

## 8. Kết luận 1 dòng cho mỗi đối tượng

- **Cho judges Colosseum:** "Mọi DEV flow đều kẹt ở quyết định không có số. Tụi em biến nó thành predicate, verdict, và bằng chứng on-chain — Tier S 15 cases chạy thật hôm nay."
- **Cho investor:** Nhóm H + J: tiền chỉ chảy khi verdict PASS, proof không sửa được.
- **Cho maintainer/dev:** Nhóm A + G: bớt review bằng niềm tin, chặn agent code bẩn trước khi nó vào PR.
- **Cho chính mình lúc build:** Theo Tier. S trước, A khi có khách thật kéo, EXT khai thật là roadmap.

