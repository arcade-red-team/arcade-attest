# Arcade Agent + Decision API — 100 Decision Cases

Generated 2026-10-02 for arcade-red-team / ArcadeAttest.
Legend: [MVP] làm được ngay với 3 predicates hiện tại (no_new_smells, max_responsibility_shifts, component_entity_cap) + metrics delta. [EXT] cần thêm predicate/edge-diff/parser mới — vẫn là case thị trường cần, để lộ roadmap.

Cách đọc: mỗi case là 1 lần gọi Decision API thật: Input (repo/PR/trước-sau) -> Predicate -> Verdict PASS/WARN/BLOCK -> Consumer (người/máy dùng verdict để hành động) -> On-chain (EAS attestation khi cần proof public).

## A. PR & CI Merge Gate (1-10)
1. [MVP] Merge PR này có tạo smell mới không? — no_new_smells=true -> BLOCK nếu có cycle/god module mới — Consumer: GitHub Action chặn merge.
2. [MVP] PR có làm xê dịch responsibility của quá nhiều component không? — max_responsibility_shifts<=1 -> WARN nếu 2-3, BLOCK >3 — Consumer: maintainer review.
3. [MVP] Component được chạm vào có phình quá cap không? — component_entity_cap<=20 entities/component — Consumer: CI gate.
4. [MVP] PR xoá tính năng lớn có thật sự an toàn kiến trúc không? (case react#37187 -19k dòng DevTools) — shifts=0, new_smells=0 -> PASS "safe to merge" — Consumer: maintainer OSS.
5. [MVP] PR migration tooling (Vd Vitest migration) làm lệch responsibility ở đâu? — liệt kê 5 shifts, metrics flat -> WARN kèm evidence — Consumer: tech lead duyệt migration.
6. [MVP] PR thêm tính năng async (Vd async auth backends) có làm metrics xấu đi không? — entities +43 nhưng RCI/TurboMQ không đổi -> PASS — Consumer: reviewer.
7. [EXT] PR có thêm dependency bị cấm không? (UI -> DB trực tiếp) — deny_dependency(UI,DB) — Consumer: CI. Cần edge-level diff.
8. [EXT] PR có tạo coupling ngược tầng không? (domain -> infrastructure) — no_reverse_layer_dependency — Consumer: architecture board.
9. [MVP] PR "chỉ refactor nhỏ" có lén tạo cycle không? — new cycle Billing<->Notifications -> BLOCK — Consumer: tác giả PR tự sửa trước review người.
10. [MVP] Hàng đợi PR: PR nào kiến trúc sạch để merge trước? — sort by verdict + smellsDelta — Consumer: maintainer triage dashboard.

## B. Refactoring & Dọn Tech Debt (11-20)
11. [MVP] Tách god module có hết smell concern-overload không? — entities sau tách <=20, smells resolved>=1 — Consumer: dev khoe kết quả refactor bằng số.
12. [MVP] Phá cycle bằng event (InvoiceIssued) có tạo smell mới không? — cycle resolved, new_smells=0 -> PASS — Consumer: PR description tự sinh evidence.
13. [MVP] Refactor lần này có đáng merge hay chỉ xáo code? — responsibility shifts ít + metrics cải thiện -> PASS, ngược lại WARN "churn vô ích".
14. [MVP] Xoá dead code (16 helpers chết) có phá component nào không? — shifts=0, orphan entities giảm — Consumer: CI.
15. [EXT] Đổi tên/move package hàng loạt có phá public API surface kiến trúc không? — component identity continuity >=90%.
16. [MVP] Sprint này tech debt giảm thật hay tăng? — so baseline đầu sprint: smellsDelta<0 -> PASS cho retro.
17. [MVP] Refactor có làm 1 component thành god component mới không? — cap check trên mọi component bị chạm.
18. [EXT] Tách file lớn có làm tăng coupling afferent/efferent bất thường không? — coupling delta per component <= ngưỡng.
19. [MVP] Hai PR refactor đụng nhau: gộp thứ tự nào an toàn? — evaluate chuỗi PR, chọn thứ tự shifts ít nhất.
20. [MVP] Chứng minh cho sếp: refactor 2 tuần giảm được bao nhiêu % smell? — decision health trend attested theo thời gian.

## C. Migration & Hiện đại hoá (21-30)
21. [MVP] Migration framework (Django async, React Compiler...) có làm lệch kiến trúc không? — shifts + metrics trước/sau.
22. [EXT] Chuyển monolith -> modules: module mới có rò dependency về monolith không? — deny_dependency(newModule, legacyCore) trừ allowlist.
23. [MVP] Nâng version thư viện lớn (Vitest 5, Next 16) có kéo theo responsibility shift ngoài ý muốn không?
24. [MVP] Thay state management (Redux -> Zustand) có tạo god store mới không? — cap + smell check.
25. [EXT] Chuyển REST -> GraphQL/gRPC có tạo coupling client-server vòng không?
26. [MVP] Di trú package: chuyển code từ module A sang B có làm B quá tải responsibility không?
27. [MVP] Sau migration, số component/entity tăng có tương xứng tính năng không? — entity growth vs verdict, tránh phình vô ích.
28. [EXT] Áp dụng ADR mới (Vd facade packages như Jaeger ADR-011) có hiệu quả thật không? — verdict +0.75 style: 0 shifts, 0 new smells, metrics flat -> ADR effective.
29. [MVP] ADR trung tính (Vd sync ES writes ADR-014) có bị agent báo động giả không? — phải PASS yên lặng, test false-positive cho Decision API.
30. [MVP] Rollback migration có an toàn không? — evaluate chiều ngược, shifts quay về baseline -> PASS mới cho rollback tự động.

## D. Microservices & Ranh giới hệ phân tán (31-40)
31. [EXT] Service mới có gọi vòng service khác không? (A->B->C->A ở mức component/package proxy) — cycle ở tầng service manifest.
32. [MVP] Tách 1 service khỏi monolith: phần tách ra có còn bị kéo responsibility về không? — shifts sau tách phải ổn định qua 2 PR liên tiếp.
33. [EXT] Thêm event/async có phá synchronous responsibility chain không?
34. [MVP] Service nào đang thành god service? — entity cap áp cho service-as-component.
35. [EXT] Thay đổi shared library có blast radius bao nhiêu service? — component fan-out + shifts dự kiến. Cần edge diff.
36. [MVP] Gộp 2 microservice lại có tạo smell mới không? — evaluate bản gộp như 1 PR.
37. [MVP] Chuẩn hoá: team có tuân thủ ranh giới bounded context không? — responsibility của context không bị PR ngoài context làm lệch > ngưỡng.
38. [EXT] Thêm cache/queue có tạo hidden coupling không? — dependency type mới phải khai trong Decision Record.
39. [MVP] Đánh giá vendor SDK mới tích hợp vào có làm component tích hợp phình không?
40. [MVP] Quyết định "giữ hay tách tiếp" sau 6 tháng: decision health của service theo quý, attested để board xem.

## E. Monorepo & Maintainer OSS lớn (41-50)
41. [MVP] PR từ contributor lạ có an toàn kiến trúc để merge nhanh không? — PASS + evidence pack thay maintainer đọc tay.
42. [MVP] 100 PR/tuần: PR nào cần architecture review người, PR nào auto-pass? — BLOCK/WARN mới route tới người.
43. [MVP] Release này so release trước kiến trúc regress chỗ nào? — changelog_architecture toàn repo giữa 2 tag.
44. [MVP] Package nào trong monorepo đang mục dần? — smells tăng liên tục 3 release -> WARN cho roadmap.
45. [EXT] PR có chạm package bị cấm sửa (frozen core) không? — protected_component predicate.
46. [MVP] Thêm package mới vào monorepo có trùng responsibility với package cũ không? — shifts/overlap evidence.
47. [MVP] Contributor đề xuất tách package: bản tách có sạch hơn bản gốc không? — so smells/cap trước-sau.
48. [MVP] Bot arch-drift comment: PR này đáng bị bot comment chặn hay chỉ nhắc? — verdict quyết định bot im lặng hay lên tiếng (tránh spam PR).
49. [MVP] Maintainer nghỉ phép: agent có tự approve PR kiến trúc sạch được không? — PASS + attestation làm audit trail thay người.
50. [MVP] Chứng minh với sponsor: repo khoẻ lên theo thời gian — public decision health page, neo EAS theo release.

## F. Security, Compliance & Rủi ro (51-60)
51. [MVP] PR chạm module auth/payment có tạo smell ở vùng nhạy cảm không? — áp cap/shift chặt hơn cho sensitive component list.
52. [EXT] Có đường dependency mới nào từ public API tới module bí mật không? — deny_path(public, secrets). Cần edge diff.
53. [EXT] Trust boundary: module trust thấp (https/remote) có đọc được file trust cao không? (case Pkl #1645) — trust_level predicate, module trust phải >= resource trust khi read.
54. [EXT] Thêm external reader/plugin có vượt sandbox responsibility không?
55. [MVP] PR thêm logging/telemetry có tạo god module observability không?
56. [MVP] Đánh giá trước audit SOC2: evidence kiến trúc 6 tháng có đầy đủ, không sửa được không? — chuỗi attestation EAS.
57. [EXT] Dependency mới có kéo transitive dependency vào vùng cấm license/vùng nhạy cảm không?
58. [MVP] Tách module xử lý PII ra riêng có thật sự cô lập responsibility không? — shifts cho thấy PII responsibility không còn rải.
59. [MVP] Hotfix khẩn cấp có được phá lệ kiến trúc không, và phá bao nhiêu? — WARN có thời hạn, attestation ghi nợ phải trả sau incident.
60. [EXT] Agent AI tự sửa code có chạm file bị cấm (auth, billing, migration DB) không? — protected path + verdict BLOCK cho agent runner.

## G. Code do AI / Agent sinh ra (61-70)
61. [MVP] Code agent vừa sinh có tạo god file/god module không? — cap check trước khi agent được commit.
62. [MVP] Agent refactor có lén tạo cycle không? — no_new_smells làm cổng trước khi mở PR.
63. [MVP] Cho agent tự merge PR của chính nó khi nào? — PASS 2 lần liên tiếp + 0 shifts mới auto-merge, còn lại chờ người.
64. [MVP] So 2 agent (Claude/Codex/local model) cùng làm 1 task: bản nào kiến trúc sạch hơn? — verdict làm điểm chấm tự động, chọn bản thắng.
65. [MVP] Agent có đang "chữa cháy" bằng cách phình 1 file 2000 dòng không? — entity/concern overload trong 1 PR của agent -> BLOCK, bắt tách.
66. [EXT] Agent thêm thư viện lạ có cần thiết không? — new dependency phải có justification trong Decision Record, không có -> WARN.
67. [MVP] Prompt thay đổi làm output agent tốt/xấu đi về kiến trúc? — A/B prompt bằng smellsDelta trung bình 20 task.
68. [MVP] AgentPay: agent chỉ được trả tiền khi code đạt verdict gì? — smart contract/escrow đọc attestation PASS mới release.
69. [MVP] Thuê agent ngoài (marketplace): hồ sơ decision health của agent đó có đáng tin không? — public history attested, không tự khai.
70. [EXT] Multi-agent: agent A giao việc cho agent B có vi phạm ranh giới responsibility đã đăng ký không? — ERC-8004 validation + decision predicate.

## H. Web3 / DAO / Smart Contract (71-80) — ngách Colosseum
71. [MVP] DAO có nên merge PR vào protocol repo không? — multisig đọc verdict PASS/BLOCK trước khi ký execute.
72. [MVP] Grant milestone: team nhận grant có giao code kiến trúc sạch như cam kết không? — milestone attestation theo commit, grantor query API.
73. [MVP] Protocol fork mới có tệ hơn bản gốc không? — so changelog_architecture fork vs upstream.
74. [EXT] Upgrade contract (proxy) có phá ranh giới module đã audit không? — protected component + deny_dependency.
75. [MVP] Trước khi rót seed: repo của startup có god contract/god module không? — investor due-diligence 1-call API + EAS proof.
76. [MVP] Hackathon judging: project này build thật trong window, kiến trúc có tiến bộ thật không? — commits trong window + verdict theo từng ngày, chống nộp đồ cũ.
77. [MVP] Agent on-chain (ERC-8004) xin quyền tự chủ cao hơn: code của nó còn PASS không? — validation registry đọc latest verdict.
78. [MVP] DAO thuê auditor: phần code nào responsibility đang phình cần audit sâu? — cap/shift evidence làm scope audit.
79. [EXT] Thêm oracle/bridge mới có tạo dependency vòng trust không? — trust boundary predicate cho Web3.
80. [MVP] Public goods funding (Gitcoin...): project nào giữ kiến trúc khoẻ bền qua 4 quý? — decision health trend công khai, neo chain.

## I. Enterprise / SaaS / Architecture Review Board (81-90)
81. [MVP] Board duyệt thiết kế mới: bản thiết kế-as-code (ADR) khi implement có đúng như duyệt không? — evaluate PR theo Decision Record đã ký.
82. [MVP] Team mới onboard vào codebase cũ: PR đầu tay của họ có phá kiến trúc không? — gate nhẹ, WARN kèm evidence để mentor.
83. [MVP] Vendor giao phần mềm outsource: nghiệm thu kiến trúc bằng số, không bằng cảm tính — verdict làm điều kiện thanh toán đợt cuối.
84. [MVP] Hai team cùng sửa 1 hệ: PR của team A có làm lệch responsibility của team B không? — shifts theo ownership map.
85. [MVP] Quyết định mua vs tự build 1 module: module tự build có sạch hơn vendor demo không? — cùng predicate, 2 verdict so sánh.
86. [MVP] Trước release lớn cho khách enterprise: kiến trúc có regress so bản đã chứng nhận không? — attestation theo version gửi khách.
87. [MVP] SaaS multi-tenant: thêm tenant-specific code có làm core phình god module không?
88. [EXT] Tuân thủ quy định nội bộ công ty (Vd không dùng thư viện X, không gọi thẳng DB từ controller) — policy pack riêng từng công ty, chạy như predicate.
89. [MVP] Tech lead nghỉ việc: kiến trúc có đang phụ thuộc 1 component "không ai dám đụng" không? — god component + shifts=0 kéo dài = rủi ro người.
90. [MVP] Báo cáo quý cho CTO: decision health toàn org, repo nào PASS bền, repo nào BLOCK nhiều nhất.

## J. M&A, Funding, Grant & Kiểm toán độc lập (91-100)
91. [MVP] M&A tech due diligence: codebase mục tiêu có bao nhiêu smell thật, so với họ tự khai? — chạy độc lập, attested, 2 bên cùng đọc.
92. [MVP] Định giá startup theo chất lượng kiến trúc: verdict + trend 4 quý làm 1 input định giá.
93. [MVP] Grant open-source (NLnet, Ethereum Foundation...): milestone kiến trúc có đạt như proposal không? — grantor gọi API thay vì đọc báo cáo tự viết.
94. [MVP] Bảo hiểm cyber / rủi ro phần mềm: hồ sơ decision health có giảm rủi ro không? — chuỗi attestation không sửa được.
95. [MVP] Freelancer/agency bàn giao: khách tự verify bàn giao sạch bằng 1 link verdict, không cần tin lời agency.
96. [MVP] Chứng nhận "architecture-clean" cho marketplace template/boilerplate: template nào PASS bền qua các bản cập nhật?
97. [MVP] Trường/bootcamp chấm project sinh viên: chấm kiến trúc tự động, công bằng, có evidence từng predicate.
98. [MVP] Thi hackathon nội bộ công ty: chấm PASS/WARN/BLOCK thống nhất cho mọi đội, giám khảo chỉ xem evidence pack.
99. [MVP] Nhà đầu tư thiên thần check nhanh trước khi xuống tiền nhỏ: repo public -> 1 API call -> verdict + link EAS trong 1 phút.
100. [MVP] Câu hỏi cuối của mọi quyết định: "Quyết định này, 6 tháng nữa nhìn lại, có đúng không?" — Decision API lưu Decision Record + verdict + evidence, neo chain, để decision health trả lời bằng dữ liệu, không bằng trí nhớ.

---
MVP coverage: phần lớn 100 case chạy được với 3 predicates hiện tại khi diễn đạt lại theo smells/shifts/cap + metrics. Các case [EXT] (edge dependency, trust boundary, protected path) là roadmap sau khi có edge-level diff — đã khai trong design doc 2026-09-30.
Top 10 để demo Colosseum: #4, #11, #12, #28, #41, #61, #64, #68, #71, #72.
