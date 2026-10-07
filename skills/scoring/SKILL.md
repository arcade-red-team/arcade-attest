# Skill — Chọn weight profile khi apply ArcadeAttest Decision API

Dùng skill này khi một agent (hoặc admin) cấu hình điểm 10 tiêu chí (`scoring@1`) cho một Decision Record. Mục tiêu: chọn đúng **template theo khẩu vị** bằng tín hiệu có bằng chứng, rồi để Decision API resolve trọng số một cách deterministic. Agent không tự bịa trọng số và không bao giờ dùng trọng số để hạ threshold hay đổi verdict.

## Cách chọn (đọc manifest JSON cùng thư mục)

Mỗi file `skills/scoring/<profile>.json` là một skill chọn profile: có `apply_when` (tín hiệu), `weights` (trọng số 10 tiêu chí) và `how_to_apply`. Registry trong code (`arcade_attest.scoring.SCORING_PROFILES`) phải khớp 1:1 với các manifest này — test `test_scoring_skills_match_registry` giữ việc đó.

Thứ tự ưu tiên khi chọn (khớp `suggest_profile` trong engine):

1. Admin đã ghi `scoring.profile` cụ thể → dùng profile đó, không gợi ý thêm.
2. Tín hiệu code do AI agent sinh (`ai-agent`, `agent-code`, `ai-generated`) → `ai_agent_code_gate`.
3. Tín hiệu refactor/migration (`refactor`, `migration`, `modernization`) → `refactor_friendly`.
4. Tín hiệu triage OSS (`oss`, `maintainer`, `review-triage`) → `oss_maintainer`.
5. Tín hiệu tốc độ (`ship-fast`, `startup`, `mvp`) → `ship_fast`.
6. Mode `blocking` hoặc rủi ro cao (`regulated`, `architecture board`, `high risk`) → `strict_gate`.
7. Không có tín hiệu nào → `balanced` (default, mọi trọng số = 1).

## Cách apply

Đặt vào Decision Record rồi gọi Decision API (CLI `--scoring-profile`, HTTP `POST /v1/decisions:evaluate`, hoặc MCP `evaluate_decision`):

```json
{"scoring": {"profile": "ai_agent_code_gate"}}
```

Chế độ gợi ý tự động (agent cấp tín hiệu, engine chọn và ghi `suggestion_rule` vào evidence pack):

```json
{"scoring": {"profile": "auto", "context": {"tags": ["ai-agent"]}}}
```

Admin override từng trọng số (ghi đè lên profile, vẫn bị validate: tiêu chí lạ / âm / tất cả bằng 0 đều bị reject):

```json
{"scoring": {"profile": "balanced", "weights": {"coupling_control": 3.0}}}
```

## Ranh giới

- Trọng số chỉ đổi `overall_score` (trung bình có trọng số của các tiêu chí `scored`; `not_run` và trọng số 0 bị loại và được liệt kê). Verdict `PASS | WARN | BLOCK` do predicate quyết, không đổi theo trọng số.
- Mọi lần resolve đều được ghi vào evidence pack: `scoring.profile`, `scoring.config_source`, `scoring.suggestion_rule`, `scoring.weights`, `scoring.effective_weights` — ai cũng audit lại được vì sao điểm tổng ra như vậy.
- Không có profile phù hợp thì đề xuất profile mới bằng 3 artifact (case xấu, case sạch, runtime đo được) theo AGENTS.md, đừng tự thêm trọng số lặng lẽ.
