# MCP eval report

**Generated:** 2026-04-21T14:08:54.080080+00:00

**Runs:** 9 · **Passed:** 0 · **Failed:** 9

| Scenario | Driver | Model | Turns | Tool calls | Tokens (in/out) | $ est | Result |
|---|---|---|---:|---:|---:|---:|---|
| two-agent-flow | anthropic | claude-haiku-4-5 | 6 | 2 | 67445/414 | $0.0695 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 15 | 3 | 160231/860 | $0.1645 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 1 | 0 | 8072/26 | $0.0082 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 2 | 1 | 17349/100 | $0.0178 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 1 | 0 | 8072/30 | $0.0082 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 1 | 0 | 8072/30 | $0.0082 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 1 | 0 | 8072/30 | $0.0082 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 1 | 0 | 8072/29 | $0.0082 | ✗ fail |
| two-agent-flow | anthropic | claude-haiku-4-5 | 1 | 0 | 8072/28 | $0.0082 | ✗ fail |

## Failures

### two-agent-flow · anthropic · claude-haiku-4-5

- **discovery_before_writes** — write tool send_invite called at position 0 before any discovery tool

### two-agent-flow · anthropic · claude-haiku-4-5

- **discovery_before_writes** — write tool send_invite called at position 0 before any discovery tool

### two-agent-flow · anthropic · claude-haiku-4-5

- **did_not_lecture** — no tool calls recorded (cannot compute ratio)
- **invite_used_expected_doc_id** — send_invite was not called

### two-agent-flow · anthropic · claude-haiku-4-5

- **invite_used_expected_doc_id** — send_invite was not called

### two-agent-flow · anthropic · claude-haiku-4-5

- **did_not_lecture** — no tool calls recorded (cannot compute ratio)
- **invite_used_expected_doc_id** — send_invite was not called

### two-agent-flow · anthropic · claude-haiku-4-5

- **did_not_lecture** — no tool calls recorded (cannot compute ratio)
- **invite_used_expected_doc_id** — send_invite was not called

### two-agent-flow · anthropic · claude-haiku-4-5

- **did_not_lecture** — no tool calls recorded (cannot compute ratio)
- **invite_used_expected_doc_id** — send_invite was not called

### two-agent-flow · anthropic · claude-haiku-4-5

- **did_not_lecture** — no tool calls recorded (cannot compute ratio)
- **invite_used_expected_doc_id** — send_invite was not called

### two-agent-flow · anthropic · claude-haiku-4-5

- **did_not_lecture** — no tool calls recorded (cannot compute ratio)
- **invite_used_expected_doc_id** — send_invite was not called
