# Scoring 10 tiêu chí cho PR — ArcadeAttest Decision API

Version: `scoring@1` · Thang điểm: **0.0 → 1.0, bước 0.1** · Chạy: **10 scorer song song trên cùng một input bundle**

## 1. Nguyên tắc (không đổi theo doctrine)

- **Name is contract**: mỗi tiêu chí có `id` cố định (snake_case). Đổi id = đổi contract.
- **Text is evidence**: mỗi điểm phải map tới số đo cụ thể trong changelog/architecture summary. Không có evidence → `status: "not_run"`, `score: null` — không bao giờ bịa 0.0.
- **Verdict vẫn deterministic**: `PASS | WARN | BLOCK` do predicate engine quyết. Điểm 10 tiêu chí là lớp đánh giá bổ sung (advisory scoring), không thay verdict, không hạ threshold.
- **LLM không chấm điểm**: nếu dùng LLM ở tầng ngoài, nó chỉ nhận cùng bundle để soạn *draft tóm tắt/giải thích*. Điểm số và verdict trong evidence pack luôn do scorer thuần (pure function) sinh ra. Divergence giữa draft LLM và scorer > 0.2/tiêu chí thì gắn cờ review cho người duyệt.
- **Determinism**: cùng bundle + cùng `evaluated_at` → cùng điểm, cùng `scoring_input_hash`, cùng `evidence_hash`. Song song chỉ thay đổi thời gian chạy, không thay đổi kết quả (kết quả được lắp lại theo thứ tự contract).

## 2. Input bundle — feed cho cả 10 scorer

Mọi scorer nhận **chính xác cùng một bundle** (immutable, hash được):

```json
{
  "changes": {
    "source": "supplied | derived_from_summary",
    "entities_added": 6,
    "entities_deleted": 25,
    "files_changed": null,
    "lines_added": null,
    "lines_deleted": null,
    "raw": "<optional: full diff / PR change summary do caller cấp — chỉ hash vào pack, không nhúng nguyên văn>"
  },
  "architecture_summary": {
    "source": "derived | supplied",
    "components_b": 5,
    "entities_a": 39,
    "entities_b": 20,
    "largest_component": {"name": "Billing", "entities": 7},
    "metrics_b": {"RCI": 0.3636, "TurboMQ": 1.7167, "...": "..."},
    "languages_b": ["python"]
  },
  "changelog": {
    "smells_new": [],
    "responsibility_shifts": [],
    "components": [{"name": "Billing", "entities": 7}],
    "summary": {},
    "metrics": {"TurboMQ": {"a": 0.0, "b": 0.0, "delta": 0.0}},
    "coverage": {}
  }
}
```

- Caller (CLI/API/MCP/GitHub Action) có thể cấp thêm `changes` (full diff/PR summary) và `architecture_summary` dạng text/JSON qua field cùng tên trong normalized data. Phần text thô chỉ được **hash** (`scoring_input_hash`), evidence pack chỉ giữ counts + derived summary để pack nhỏ và neo on-chain được.
- Thiếu field nào, scorer phụ thuộc field đó trả `not_run` kèm lý do trong `evidence`.

## 3. Mười tiêu chí

| # | `id` | Tiêu chí | Evidence chính (field trong bundle) | Công thức thô → quantize 0.1 |
|---|---|---|---|---|
| 1 | `smell_regression` | Không hồi quy smell kiến trúc | `smells_new[]` (severity: low=1, medium=2, high=3, critical=4) | `raw = 1 − 0.2 × weighted_smells` |
| 2 | `responsibility_stability` | Ổn định trách nhiệm giữa các component | `responsibility_shifts[]`, `entities_b` | `shift_rate = shifts / max(1, entities_b)`; `raw = 1 − 5 × shift_rate` |
| 3 | `god_component_risk` | Nguy cơ god-component phình to | component lớn nhất / tổng entities theo component | `raw = 1 − largest_share` |
| 4 | `component_balance` | Cân bằng kích thước component | phân bố entities qua components (HHI) | `raw = 1 − (HHI − 1/n) / (1 − 1/n)`, n ≥ 2 |
| 5 | `modularity_trend` | Xu hướng modularity (TurboMQ) | `metrics.TurboMQ.delta` | `raw = 0.5 + clamp(delta, −0.5, 0.5)` |
| 6 | `cohesion_trend` | Xu hướng cohesion trong component | `metrics.IntraConnectivity.delta` | `raw = 0.5 + 2.5 × delta` |
| 7 | `coupling_control` | Kiểm soát coupling liên-component | `metrics.InterConnectivity.delta`, `metrics.TwoWayPairRatio.delta` | `raw = 0.5 − 2.5 × inter_delta − 1.0 × twoway_delta` |
| 8 | `recovery_confidence_trend` | Xu hướng RCI (recovery confidence) | `metrics.RCI.delta` | `raw = 0.5 + 2.5 × delta` |
| 9 | `change_containment` | Độ gọn / blast radius của thay đổi | `entities_added + entities_deleted` so với `entities_a` | `churn = (added+deleted)/max(1, entities_a)`; `raw = 1 − 0.5 × churn` |
| 10 | `evidence_confidence` | Độ tin cậy của chính phép đo | `coverage.entities_b`, `component_sizes_known`, warnings, languages | `raw = 1.0 − penalties` (sizes unknown −0.3; mỗi warning −0.1, cap −0.3; không language −0.2; `entities_b = 0` → 0.0) |

Mọi `raw` đều clamp về [0.0, 1.0] rồi quantize: `score = floor(raw × 10 + 0.5) / 10`.
Tiêu chí 5–8 là *trend* (0.5 = không đổi, > 0.5 = tốt lên, < 0.5 = xấu đi) vì chỉ có delta mới nói được PR này làm kiến trúc tốt hay xấu đi; điểm tuyệt đối của metric thuộc về baseline report, không thuộc PR score.

## 4. Output contract

Evidence pack có thêm:

```json
{
  "criteria": [
    {"id": "smell_regression", "score": 1.0, "status": "scored",
     "measured": {"new_smells": 0, "weighted_smells": 0},
     "evidence": [], "formula": "scoring@1:smell_regression:raw=clamp(1-0.2*weighted_smells)"}
  ],
  "overall_score": 0.8,
  "scoring": {
    "version": "scoring@1",
    "scale": "0.0-1.0 step 0.1",
    "parallel_scorers": 10,
    "scored_count": 9,
    "not_run": ["recovery_confidence_trend"],
    "scoring_input_hash": "<sha256 của bundle>",
    "llm_in_scoring": false
  }
}
```

`overall_score` = trung bình **có trọng số** của các tiêu chí `scored` (quantize 0.1; trọng số admin xem mục 6, mặc định mọi trọng số = 1). `not_run` bị loại khỏi trung bình và phải được liệt kê — điểm tổng không bao giờ lặng lẽ che giấu tiêu chí thiếu evidence.

Đọc điểm: ≥ 0.8 mạnh · 0.6–0.7 chấp nhận được · 0.4–0.5 yếu, cần người nhìn · ≤ 0.3 kém. Đây là dải đọc cho reviewer, **không** map thẳng sang verdict.

## 5. PR comment

Comment render từ pack (template, không prose tự sinh): dòng verdict trước, rồi bảng 10 tiêu chí (điểm / status / measured chính), overall, warnings, hash. Reviewer thấy trong 3 giây: tiêu chí nào thấp, vì số nào.

## 6. Admin config trọng số — template theo khẩu vị (skills)

`overall_score` là **trung bình có trọng số**: `Σ(score × weight) / Σ(weight)` trên các tiêu chí `scored` có weight > 0. Tiêu chí `not_run` và weight = 0 bị loại khỏi mẫu số và phải được liệt kê trong pack (`scoring.not_run`, `scoring.effective_weights` là trọng số đã renormalize trên phần scored). Trọng số **không** đổi verdict và **không** hạ threshold.

Admin cấu hình qua Decision Record (đây là bề mặt của Decision API — CLI `--scoring-profile/--weights`, HTTP record, MCP tool đều đi qua cùng một resolver):

```json
{"scoring": {"profile": "strict_gate"}}
{"scoring": {"profile": "balanced", "weights": {"coupling_control": 3.0}}}
{"scoring": {"profile": "auto", "context": {"tags": ["ai-agent"]}}}
```

| `profile` | Khẩu vị | Mạnh tay ở đâu |
|---|---|---|
| `balanced` (default) | Cân bằng | Mọi tiêu chí = 1 |
| `strict_gate` | Chặt / risk-averse | smell ×3, god ×3, coupling ×2.5, evidence ×2 |
| `ship_fast` | Nhanh / startup | containment ×3, stability ×2 |
| `refactor_friendly` | Chịu refactor/migration | modularity ×3, cohesion ×2.5, RCI ×2.5; shifts/churn nhẹ |
| `ai_agent_code_gate` | Code do AI agent sinh | smell ×3, god ×3, coupling ×3, containment ×2.5, evidence ×2.5 |
| `oss_maintainer` | Triage PR volume lớn | evidence ×3, smell ×2.5, containment ×2.5 |

Mỗi profile là một **selection skill** trong `skills/scoring/` (SKILL.md + manifest JSON từng profile, khớp 1:1 với registry trong code — có test giữ). Khi agent apply Decision API, agent đọc skill, chọn profile theo tín hiệu `apply_when`, hoặc để engine tự gợi ý bằng `"profile": "auto"` + `context.tags`; engine resolve deterministic, validate (tiêu chí lạ / trọng số âm / tất cả = 0 → reject 422/ValueError), và ghi vào pack: `scoring.profile`, `scoring.config_source`, `scoring.suggestion_rule`, `scoring.weights`, `scoring.normalized_weights`, `scoring.effective_weights`. Liệt kê profiles: `arcade-attest scoring-profiles`, `GET /v1/scoring/profiles`, MCP `list_scoring_profiles`.
